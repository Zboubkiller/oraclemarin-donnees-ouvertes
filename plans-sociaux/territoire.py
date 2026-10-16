"""Poids local des emplois annoncés : emplois supprimés ou menacés rapportés à l'emploi salarié privé de la commune et de
sa zone d'emploi (URSSAF, effectifs au 31 décembre par commune × APE, open.urssaf.fr, sans clé).
Calculé seulement quand la commune du site est connue (presse, ou liste CGT localisée à la commune) et que l'effectif est
un chiffre annoncé ; jamais pour le BODACC, dont la commune est celle du siège et pas forcément celle des salariés."""
import json, os, re, sqlite3, time, unicodedata, urllib.parse, urllib.request
H = os.path.dirname(os.path.abspath(__file__))
DS = "https://open.urssaf.fr/api/explore/v2.1/catalog/datasets/etablissements-et-effectifs-salaries-au-niveau-commune-x-ape-last/records?"
db = sqlite3.connect(os.path.join(H, "cache.db"), timeout=120)
db.execute("create table if not exists urssaf(cle text primary key, js text, ts real)")

def norm(s): return re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFD", (s or "").lower()).encode("ascii", "ignore").decode())
try:
    COM = {}
    for c in json.load(open("/opt/ca-brule/communes.json")):
        COM.setdefault((norm(c["nom"]), c.get("codeDepartement")), c["code"])
except Exception:
    COM = {}

def get(params):
    for i in range(3):
        try: return json.load(urllib.request.urlopen(urllib.request.Request(DS + urllib.parse.urlencode(params), headers={"User-Agent": "tracker-plans-sociaux/0.6"}), timeout=60))
        except Exception: time.sleep(2 + 3 * i)
    return None

ANNEE = [None]
def annee():
    """Dernière année d'effectifs publiée (champ effectifs_salaries_AAAA)."""
    if ANNEE[0]: return ANNEE[0]
    for y in range(time.gmtime().tm_year, 2020, -1):
        d = get({"select": f"sum(effectifs_salaries_{y}) as e", "where": 'code_commune="75056" or code_departement="75"', "limit": 1})
        if d and d.get("results") and d["results"][0].get("e"):
            ANNEE[0] = y; return y
    return None

def cache(cle, f, ttl=30 * 86400):
    r = db.execute("select js, ts from urssaf where cle=?", (cle,)).fetchone()
    if r and time.time() - r[1] < ttl: return json.loads(r[0])
    v = f()
    if v is not None:
        db.execute("replace into urssaf values(?,?,?)", (cle, json.dumps(v, ensure_ascii=False), time.time())); db.commit()
    time.sleep(0.2)
    return v

def nom_arrondissement(insee, nom):
    """L'URSSAF écrit « Lyon 89e Arrondissement » pour 69389 : on reconstruit le nom depuis le code commune."""
    s = str(insee or "")
    if s.startswith("751") and len(s) == 5: return f"Paris {int(s[3:])}e arrondissement"
    if s.startswith("6938") and len(s) == 5: return f"Lyon {int(s[4])}e arrondissement"
    if s.startswith("132") and len(s) == 5 and 1 <= int(s[3:]) <= 16: return f"Marseille {int(s[3:])}e arrondissement"
    return nom

def commune(insee):
    y = annee()
    if not y: return None
    def f():
        d = get({"select": f"code_zone_d_emploi, zone_d_emploi, commune, sum(effectifs_salaries_{y}) as e", "where": f'code_commune="{insee}"',
                 "group_by": "code_zone_d_emploi, zone_d_emploi, commune", "limit": 5})
        if d is None: return None
        r = d.get("results") or []
        return {"annee": y, "effectif": sum(x.get("e") or 0 for x in r), "ze_code": r[0]["code_zone_d_emploi"] if r else None,
                "ze": r[0]["zone_d_emploi"] if r else None, "commune": nom_arrondissement(insee, r[0]["commune"]) if r else None}
    c = cache(f"com:{insee}:{y}", f)
    if c and c.get("commune"): c["commune"] = nom_arrondissement(insee, c["commune"])
    return c

def zone(code):
    y = annee()
    def f():
        d = get({"select": f"sum(effectifs_salaries_{y}) as e", "where": f'code_zone_d_emploi="{code}"', "limit": 1})
        return None if d is None else {"annee": y, "effectif": (d.get("results") or [{}])[0].get("e") or 0}
    return cache(f"ze:{code}:{y}", f)

def emploi_secteur(insee, ape):
    """Effectifs salariés privés de la commune dans le code APE donné, par année (URSSAF, au 31 décembre)."""
    def f():
        d = get({"select": ", ".join(f"sum(effectifs_salaries_{y}) as e{y}" for y in range(2019, (annee() or 2025) + 1)),
                 "where": f'code_commune="{insee}" and code_ape="{ape}"', "limit": 1})
        if d is None: return None
        r = (d.get("results") or [{}])[0]
        return {str(y): r.get(f"e{y}") for y in range(2019, (annee() or 2025) + 1) if r.get(f"e{y}") is not None}
    return cache(f"ape:{insee}:{ape}:{annee()}", f)

def verifier(e):
    """Vérification indépendante : l'emploi du secteur de l'entreprise dans la commune a-t-il baissé après l'annonce ?
    Ne vaut que si l'annonce est antérieure à la dernière année publiée par l'URSSAF."""
    ape = (e.get("naf") or "").replace(".", "")
    an = int((e.get("date") or "0000")[:4] or 0)
    if not ape or not an or an > (annee() or 0) - 1: return None      # il faut au moins une année complète après l'annonce
    code = e.get("insee") or insee_de(e)
    if not code: return None
    s = emploi_secteur(code, ape)
    if not s: return None
    avant, apres = s.get(str(an - 1)), s.get(str(annee()))
    if avant is None or apres is None or avant == 0: return None
    n = e.get("emplois_min") if e.get("emplois_precision") == "annoncé" else None
    if n and avant < 0.5 * n: return None          # le secteur de l'unité légale ne contient visiblement pas le site (ex. siège classé en commerce)
    return {"ape": e.get("naf"), "commune": (e.get("poids_local") or {}).get("commune") or e.get("commune"), "annee_avant": an - 1, "avant": avant,
            "annee_apres": annee(), "apres": apres, "ecart": apres - avant, "serie": s,
            "annonce": e.get("emplois_min") if e.get("emplois_precision") == "annoncé" else None}

def insee_de(e):
    if e.get("insee"): return e["insee"]
    return COM.get((norm(e.get("commune")), e.get("dep"))) if e.get("commune") and e.get("dep") else None

def enrichir(evs):
    for e in evs:
        if e.get("source") == "BODACC" or e.get("emplois_precision") != "annoncé" or not e.get("emplois_min"): continue
        if str(e.get("source", "")).startswith("CGT") and e.get("approx"): continue     # localisée au département seulement
        code = insee_de(e)
        if not code: continue
        c = commune(code)
        if not c or not c.get("effectif"): continue
        z = zone(c["ze_code"]) if c.get("ze_code") else None
        try: n = float(e["emplois_min"]); ef = float(c["effectif"])
        except (TypeError, ValueError): continue
        if n > ef: continue      # plus d'emplois annoncés que de salariés privés recensés dans la commune : site compté ailleurs par l'URSSAF ou secret statistique
        p = {"annee": c["annee"], "commune": c.get("commune") or e.get("commune"), "insee": code, "effectif_commune": c["effectif"],
             "part_commune_pct": round(100 * n / ef, 1)}
        if z and z.get("effectif"):
            p.update(zone_emploi=c["ze"], effectif_zone=z["effectif"], part_zone_pct=round(100 * n / z["effectif"], 2))
        e["poids_local"] = p
    # vérification par l'URSSAF : annonces localisées à la commune, entreprise identifiée (code APE connu)
    for e in evs:
        if e.get("source") == "BODACC" or not e.get("poids_local") or not e.get("naf"): continue
        try:
            v = verifier(e)
            if v: e["verif_urssaf"] = v
        except Exception:
            pass
    return evs
