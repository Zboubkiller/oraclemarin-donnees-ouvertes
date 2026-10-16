"""Sociétés liées à une société suivie, avec la PREUVE de chaque lien (aucun lien n'est posé sans preuve, et aucun lien n'est « le groupe X ») :
 1. dirigeant personne morale (API Recherche d'entreprises) : la société est dirigée par X, ou deux sociétés suivies ont le même dirigeant personne morale ;
 2. adresse commune d'un établissement (base Sirene locale, adresses de voie et code postal) : indice seulement, « probable » si les noms partagent un mot distinctif ;
    les adresses partagées par plus de 5 sociétés (domiciliation) sont ignorées ;
 3. cession de fonds publiée au BODACC (acheteur identifié par son SIREN).
Écrit e["societes_liees"] (8 liens au plus, par force : fort, probable, indice) et public/societes_liees.csv. Cache : table liens_api (dirigeants, 30 jours).
Usage : liens_societes.py [complet]  (complet : interroge l'API pour toutes les sociétés non encore en cache)"""
import csv, json, os, re, sqlite3, sys, time, unicodedata, urllib.request
H = os.path.dirname(os.path.abspath(__file__))
S = sqlite3.connect(os.path.join(H, "sirene.db"))
C = sqlite3.connect(os.path.join(H, "cache.db"), timeout=120)
C.execute("create table if not exists liens_api(siren text primary key, js text, ts real)")
UA = "plans-sociaux-liens (quentinclosset@gmail.com)"
GEN = {"france", "groupe", "group", "societe", "sas", "sarl", "sa", "ste", "des", "les", "de", "du", "la", "le", "industrie", "industries", "services", "service", "holding", "international",
       "distribution", "commerce", "immobilier", "gestion", "finance", "finances", "participations", "invest", "europe", "retail", "logistique", "production", "developpement", "conseil", "ingenierie"}
norm = lambda x: re.sub(r"[^a-z0-9 ]", " ", unicodedata.normalize("NFD", (x or "").lower().replace("’", "'")).encode("ascii", "ignore").decode())
jetons = lambda x: {w for w in norm(x).split() if len(w) >= 4 and w not in GEN}
ORDRE = {"fort": 0, "probable": 1, "indice": 2}

AUDIT = re.compile(r"commissaire|audit|kpmg|deloitte|pricewaterhouse|ernst|mazars|grant thornton|forvis|\bbdo\b|exco|expertise comptable|cabinet|fiduciaire|\bpwc\b|\bey\b|rsm|baker tilly|crowe|orfis|ficorec|selarl|selas|\\bmj\\b|\\baj\\b|mandataire|administrateur judiciaire|pouvoir de diriger|gladel|minerva|ajassocies|\\bscp\\b|huissier|notaire", re.I)
def audit(nom, qualite):
    """Commissaires aux comptes et cabinets d'audit ou d'expertise comptable : un auditeur commun ne prouve aucun lien de groupe."""
    return bool(AUDIT.search((nom or "") + " " + (qualite or "")))

def dirigeants(siren, budget):
    r = C.execute("select js, ts from liens_api where siren=?", (siren,)).fetchone()
    if r and time.time() - r[1] < 30 * 86400: return [y for y in json.loads(r[0]) if not audit(y.get("nom"), y.get("qualite"))]
    if budget[0] <= 0: return None
    budget[0] -= 1
    try:
        d = json.load(urllib.request.urlopen(urllib.request.Request("https://recherche-entreprises.api.gouv.fr/search?q=" + siren + "&per_page=1", headers={"User-Agent": UA}), timeout=30))
        x = next((x for x in d.get("results", []) if x.get("siren") == siren), None)
        out = [{"siren": y.get("siren"), "nom": y.get("denomination"), "qualite": y.get("qualite")} for y in (x or {}).get("dirigeants", [])
               if y.get("denomination") and not audit(y.get("denomination"), y.get("qualite"))]
        C.execute("replace into liens_api values(?,?,?)", (siren, json.dumps(out, ensure_ascii=False), time.time())); C.commit(); time.sleep(0.25)
        return out
    except Exception:
        return None

NOMS = {}
def nom_de(siren):
    r = S.execute("select nom from ul where siren=?", (siren,)).fetchone()
    return r[0] if r else NOMS.get(siren)

def enrichir(evs, limite=250, complet=False):
    sirens = sorted({e["siren"] for e in evs if e.get("siren")})
    NOMS.clear(); NOMS.update({e["siren"]: e.get("entreprise") for e in evs if e.get("siren") and e.get("entreprise") and e.get("entreprise") != e.get("titre")})
    budget = [10 ** 9 if complet else limite]
    dirs = {s: dirigeants(s, budget) for s in sirens}
    liens = {s: {} for s in sirens}            # s -> {autre siren: {"nom", "force", "preuves": []}}
    def lier(a, b, nom_b, force, preuve):
        if a == b or not b: return
        d = liens.setdefault(a, {}).setdefault(b, {"siren": b, "nom": nom_b or nom_de(b), "force": force, "preuves": []})
        if ORDRE[force] < ORDRE[d["force"]]: d["force"] = force
        if preuve not in d["preuves"]: d["preuves"].append(preuve)
    # 1. dirigeants personnes morales
    par_dir = {}
    for s, L in dirs.items():
        for y in L or []:
            if not y.get("siren") or y["siren"] == s: continue
            lier(s, y["siren"], y["nom"], "fort", f"dirigée par {y['nom']} ({y['qualite'] or 'dirigeant'})")
            par_dir.setdefault(y["siren"], []).append((s, y["nom"]))
    for d, L in par_dir.items():                # sociétés suivies qui ont le même dirigeant personne morale
        for a, nom_d in L:
            for b, _ in L:
                if a != b: lier(a, b, nom_de(b), "fort", f"même dirigeant personne morale : {nom_d}")
            if d in liens: lier(d, a, nom_de(a), "fort", f"dirige cette société ({nom_d})")
    # 2. adresse
    for s in sirens:
        sg = S.execute("select adresse, cp from etab where siren=? and siege=1 and adresse is not null and adresse<>'' limit 1", (s,)).fetchone()
        if not sg: continue
        voisins = S.execute("select distinct siren from etab where cp=? and adresse=? and etat='A'", (sg[1], sg[0])).fetchall()
        autres = [v[0] for v in voisins if v[0] != s]
        if not autres or len(autres) > 5: continue
        nj = jetons(nom_de(s) or "")
        for b in autres:
            force = "probable" if jetons(nom_de(b) or "") & nj else "indice"
            lier(s, b, nom_de(b), force, f"même adresse : {sg[0].title()}, {sg[1]}")
    # 3. cessions de fonds au BODACC
    try:
        for s, js in C.execute("select siren, js from fusion_bodacc"):
            if s not in liens: continue
            for x in json.loads(js):
                if x.get("type") == "cession" and x.get("acheteur_siren"):
                    lier(s, x["acheteur_siren"], x.get("acheteur"), "fort", f"a cédé son fonds de commerce ({x['date']}, BODACC)")
                    if x["acheteur_siren"] in liens: lier(x["acheteur_siren"], s, nom_de(s), "fort", f"a repris le fonds de commerce ({x['date']}, BODACC)")
    except sqlite3.OperationalError: pass
    n = 0
    for e in evs:
        L = sorted(liens.get(e.get("siren"), {}).values(), key=lambda d: (ORDRE[d["force"]], d["nom"] or ""))[:8]
        e.pop("societes_liees", None)
        if L and e.get("source") != "BODACC": e["societes_liees"] = [{"siren": d["siren"], "nom": d["nom"], "force": d["force"], "preuves": d["preuves"][:3]} for d in L]; n += 1
    nf = sum(1 for s in liens.values() for d in s.values() if d["force"] == "fort")
    sans = sum(1 for v in dirs.values() if v is None)
    print(f"sociétés liées : {n} annonces avec au moins un lien ; {nf} liens forts ; {sans} sociétés pas encore interrogées (API)", file=sys.stderr)
    with open(os.path.join(H, "public", "societes_liees.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f); w.writerow(["siren", "societe", "siren_lie", "societe_liee", "force", "preuves"])
        for s, d in sorted(liens.items()):
            for b in sorted(d.values(), key=lambda x: ORDRE[x["force"]]): w.writerow([s, nom_de(s) or "", b["siren"], b["nom"] or "", b["force"], " ; ".join(b["preuves"])])

if __name__ == "__main__":
    E = json.load(open(os.path.join(H, "public", "data.json")))["evenements"]
    enrichir(E, complet=len(sys.argv) > 1 and sys.argv[1] == "complet")
    for e in E:
        if e.get("societes_liees") and e.get("valide_humain"):
            print((e.get("entreprise") or "")[:26], "|", [(d["nom"] or "")[:24] + " [" + d["force"] + "] " + d["preuves"][0][:44] for d in e["societes_liees"][:2]])
