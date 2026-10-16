"""Direction et actionnariat visibles : (1) changements d'administration publiés au BODACC (« Modification survenue sur l'administration ») dans les 24 mois
précédant l'annonce ; (2) dirigeants personnes morales (société, holding ou fonds) d'après le registre des entreprises (API Recherche d'entreprises).
Le BODACC dit qu'un changement a eu lieu, pas lequel (pas de noms) ; les cessions de titres et l'arrivée d'un fonds au capital ne sont pas publiées : on ne conclut à aucun rachat.
Écrit e["direction"] = {changements, proximite {n, plus_recent}, dirigeants_pm [{nom, siren, qualite, naf, holding}]}. Cache : table bodacc_admin (30 jours)."""
import json, os, re, sqlite3, sys, time, urllib.parse
H = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, H)
import collect
C = sqlite3.connect(os.path.join(H, "cache.db"), timeout=120)
C.execute("create table if not exists bodacc_admin(siren text primary key, js text, ts real)")
S = sqlite3.connect(os.path.join(H, "sirene.db"))
ADMIN = re.compile(r"administration|direction|dirigeant|g[ée]rance|g[ée]rant|pr[ée]sident|nomination|d[ée]mission", re.I)
HOLDING = ("64.2", "64.3", "66.3")            # sociétés de portefeuille, fonds de placement, gestion de fonds

def mois(d): return int(d[:4]) * 12 + int(d[5:7]) if d and len(d) >= 7 and d[:4].isdigit() else None

def changements(siren, budget):
    r = C.execute("select js, ts from bodacc_admin where siren=?", (siren,)).fetchone()
    if r and time.time() - r[1] < 30 * 86400: return json.loads(r[0])
    if budget[0] <= 0: return None
    budget[0] -= 1
    sp = f"{siren[:3]} {siren[3:6]} {siren[6:]}"
    d = collect.get(collect.BODACC + "?" + urllib.parse.urlencode({"where": f'familleavis="modification" and registre like "*{sp}*" and dateparution>="2023-01-01"', "limit": 40,
                    "order_by": "dateparution desc", "select": "dateparution,modificationsgenerales"}))
    if d is None: return None
    out = []
    for x in d.get("results", []):
        try: m = json.loads(x.get("modificationsgenerales") or "{}")
        except ValueError: m = {}
        t = str((m or {}).get("descriptif") or "")
        if ADMIN.search(t): out.append({"date": x["dateparution"][:10], "descriptif": t[:160]})
    C.execute("replace into bodacc_admin values(?,?,?)", (siren, json.dumps(out, ensure_ascii=False), time.time())); C.commit(); time.sleep(0.15)
    return out

def enrichir(evs, limite=400):
    import liens_societes as L
    budget, b2 = [limite], [limite]
    n = nc = nh = 0
    for e in evs:
        e.pop("direction", None)
        s = e.get("siren")
        if not s or e.get("source") == "BODACC" or e.get("partie_de"): continue
        ch = changements(s, budget) or []
        pm = []
        for y in (L.dirigeants(s, b2) or []):
            if not y.get("siren"): continue
            u = S.execute("select naf from ul where siren=?", (y["siren"],)).fetchone(); naf = u[0] if u else None
            pm.append({"nom": y.get("nom"), "siren": y["siren"], "qualite": y.get("qualite"), "naf": naf, "holding": bool(naf and naf.startswith(HOLDING))})
        if not ch and not pm: continue
        d = {"changements": ch[:6], "dirigeants_pm": pm[:6]}
        me = mois(e.get("date"))
        if me is not None:
            dans = [{**c, "delai_mois": me - mois(c["date"])} for c in ch if mois(c["date"]) is not None and 0 <= me - mois(c["date"]) <= 24]
            if dans: d["proximite"] = {"n": len(dans), "plus_recent": dans[0]}; nc += 1
        if any(p["holding"] for p in pm): nh += 1
        e["direction"] = d; n += 1
    print(f"direction : {n} annonces documentées, dont {nc} avec un changement d'administration dans les 24 mois avant l'annonce et {nh} dirigées par une holding ou un fonds", file=sys.stderr)
