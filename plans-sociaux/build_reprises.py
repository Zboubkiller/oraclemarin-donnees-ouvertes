#!/usr/bin/env python3
"""Reprises à la barre et rechutes : à partir des sociétés de la base en procédure collective, fermeture ou plan social depuis 2023, collecte (avec cache) l'historique BODACC et les dirigeants
du registre des entreprises, puis repère (1) les rechutes : plan de redressement, de sauvegarde ou de cession puis nouvelle procédure ; (2) les chaînes : une société en procédure dont un dirigeant
(personne morale, ou personne physique sans jamais la nommer) dirige aussi une société antérieurement cédée ou liquidée, avant la création de la première. Faits du registre et du BODACC seulement.
Sortie : /opt/plans-sociaux/reprises.json (relu par pages_reprises.py)."""
import fcntl, json, os, re, sys, time, urllib.parse, urllib.request
H = "/opt/plans-sociaux/"
CACHE = "./work/reprises_cache.json"
UA = {"User-Agent": "tracker-plans-sociaux/0.9 (+https://oraclemarin.fr/plans-sociaux/)"}
lock = open("/tmp/reprises.lock", "w")
try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
except OSError: sys.exit("déjà en cours")
EV = json.load(open(H + "public/data.json", encoding="utf-8"))["evenements"]
S = {}
for e in EV:
    if e.get("siren") and not e.get("doublon_de") and not e.get("sans_entreprise") and e.get("source") != "Sirene" and e.get("type") in ("liquidation", "redressement", "sauvegarde", "fermeture", "plan social") and (e.get("date") or "") >= "2023-01-01":
        S.setdefault(e["siren"], []).append(e)
try: C = json.load(open(CACHE, encoding="utf-8"))
except Exception: C = {}
def get(u):
    for k in range(3):
        try: return json.loads(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60).read())
        except Exception: time.sleep(2 + 2 * k)
def collecte(s):
    c = C.get(s)
    if c and c.get("v") == 2: return c
    o = {"v": 2, "bodacc": [], "reg": {}}
    d = get("https://bodacc-datadila.opendatasoft.com/api/explore/v2.1/catalog/datasets/annonces-commerciales/records?" + urllib.parse.urlencode(
        {"where": 'registre like "%s"' % s, "limit": 100, "order_by": "dateparution asc", "select": "dateparution,familleavis_lib,jugement"})) or {}
    for r in d.get("results", []):
        j = r.get("jugement")
        try: j = json.loads(j) if isinstance(j, str) else j
        except Exception: j = {}
        j = j or {}
        if j.get("nature"): o["bodacc"].append({"paru": r["dateparution"], "nature": j["nature"], "date": j.get("date") or r["dateparution"]})
    r = ((get("https://recherche-entreprises.api.gouv.fr/search?q=%s&per_page=1" % s) or {}).get("results") or [{}])[0]
    if r.get("siren") == s:
        dirs = []
        for x in r.get("dirigeants") or []:
            if x.get("type_dirigeant") == "personne morale":
                if x.get("siren") and not re.search(r"commissaire|audit", (x.get("qualite") or ""), re.I): dirs.append("pm:" + x["siren"])
            else:
                nm = (x.get("nom") or "").strip().lower(); pn = (x.get("prenoms") or "").split(" ")[0].strip().lower()
                if nm and x.get("annee_de_naissance"): dirs.append("pp:%s|%s|%s" % (nm, pn, x["annee_de_naissance"]))
        o["reg"] = {"nom": r.get("nom_complet"), "creation": r.get("date_creation"), "etat": r.get("etat_administratif"), "cessation": r.get("date_fermeture"), "dirs": dirs}
    C[s] = o; time.sleep(0.35)
    return o
n = 0
for s in S:
    collecte(s); n += 1
    if n % 100 == 0: json.dump(C, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False); print(n, "/", len(S), flush=True)
json.dump(C, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False)

def nom(s): return (S[s][0]["entreprise"] if s in S else (C[s]["reg"].get("nom") if s in C else s))
def evt(s):
    b = C[s]["bodacc"]
    cess = [x for x in b if re.search(r"plan de cession", x["nature"], re.I)]
    liq = [x for x in b if re.search(r"liquidation judiciaire", x["nature"], re.I) and not re.search(r"cl[oô]ture", x["nature"], re.I)]
    plan = [x for x in b if re.search(r"plan de (redressement|sauvegarde)|arr[eê]tant le plan", x["nature"], re.I) and not re.search(r"cession", x["nature"], re.I)]
    ouv = [x for x in b if re.search(r"ouverture", x["nature"], re.I)]
    return {"cession": min((x["date"] for x in cess), default=None), "liq": min((x["date"] for x in liq), default=None), "plan": min((x["date"] for x in plan), default=None),
            "ouv": sorted(x["date"] for x in ouv), "derniere": max((e["date"][:10] for e in S[s]), default=None)}
EVT = {s: evt(s) for s in S if s in C}
# 1) rechutes : plan de redressement / sauvegarde / cession, puis ouverture ou liquidation au moins 6 mois plus tard
def mois(a, b):
    try: return (int(b[:4]) - int(a[:4])) * 12 + int(b[5:7]) - int(a[5:7])
    except Exception: return 0
rech = []
for s, v in EVT.items():
    base = v["plan"] or v["cession"]
    if not base: continue
    suite = [d for d in v["ouv"] + ([v["liq"]] if v["liq"] else []) if d and mois(base, d) >= 6]
    if suite:
        rech.append({"siren": s, "nom": nom(s), "dep": S[s][0].get("dep"), "type": "plan de cession" if (not v["plan"] and v["cession"]) or (v["cession"] and v["cession"] <= (v["plan"] or "9")) else "plan de redressement ou de sauvegarde",
                     "plan": base, "puis": min(suite), "liq": v["liq"], "emplois": max(((e.get("emplois_max") or e.get("emplois_min") or 0) if e.get("emplois_precision") == "annoncé" else 0) for e in S[s]), "actif": C[s]["reg"].get("etat") == "A"})
rech.sort(key=lambda r: -r["emplois"])
# 2) chaînes : dirigeant commun A -> B, B créée après la cession ou la liquidation de A, B en procédure ensuite
idx = {}
for s in EVT:
    for d in C[s]["reg"].get("dirs", []): idx.setdefault(d, set()).add(s)
cha = []
for d, L in idx.items():
    if len(L) < 2 or len(L) > 8: continue      # un dirigeant dans plus de 8 sociétés : holding, mandataire ou investisseur, pas une chaîne
    for a in L:
        va = EVT[a]; da = va["cession"] or va["liq"]
        if not da: continue
        for b in L:
            if a == b: continue
            cb = C[b]["reg"].get("creation")
            vb = EVT[b]; db = vb["derniere"]
            if cb and cb > "2015" and cb >= ((min(va["ouv"])[:4] + "-01-01") if va["ouv"] else da[:10]) and db and db > cb and mois(cb, db) <= 60:
                cha.append({"a": a, "b": b, "type_dir": "personne morale" if d.startswith("pm:") else "personne physique", "da": da, "nature_a": "plan de cession" if va["cession"] else "liquidation judiciaire", "cb": cb, "db": db})
vus = {}
for c in cha:
    k = (c["a"], c["b"])
    if k not in vus or c["type_dir"] == "personne physique": vus[k] = c
CH = []
for (a, b), c in vus.items():
    pm = [d for d in C[a]["reg"].get("dirs", []) if d in C[b]["reg"].get("dirs", [])]
    CH.append({"a": a, "nom_a": nom(a), "nature_a": c["nature_a"], "date_a": c["da"], "b": b, "nom_b": nom(b), "creation_b": c["cb"], "date_b": c["db"], "type_b": S[b][0]["type"], "emplois_b": max(((e.get("emplois_max") or e.get("emplois_min") or 0) if e.get("emplois_precision") == "annoncé" else 0) for e in S[b]),
               "dep_b": S[b][0].get("dep"), "dirigeant_commun": c["type_dir"], "n_communs": len(pm)})
CH.sort(key=lambda c: -c["emplois_b"])
json.dump({"genere": time.strftime("%Y-%m-%d"), "n_societes": len(EVT), "rechutes": rech, "chaines": CH}, open(H + "reprises.json", "w", encoding="utf-8"), ensure_ascii=False)
print(len(EVT), "sociétés ;", len(rech), "rechutes ;", len(CH), "chaînes")
