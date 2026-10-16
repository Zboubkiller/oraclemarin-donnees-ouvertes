"""Tendance des défaillances d'entreprises (BODACC) : public/tendance.json.
 1. Toutes tailles : nombre de jugements d'ouverture par mois et par département, comptage exact côté BODACC (agrégat).
 2. 50 salariés et plus : nécessite l'effectif de chaque entreprise (API Recherche d'entreprises, ~7 requêtes/s) ;
    `python3 tendance.py rattrapage [mois]` remplit l'historique par semaines, reprenable (table bk_done), et se
    termine seul. Les mois non encore couverts ne sont pas comparés.
Usage : python3 tendance.py            -> recalcule tendance.json
        python3 tendance.py rattrapage -> comble l'historique BODACC 50+ (long : plusieurs heures)"""
import json, os, sys, sqlite3, urllib.parse, datetime as dt
import collect

H = os.path.dirname(os.path.abspath(__file__))
db = collect.db
db.execute("create table if not exists bk_done(sem text primary key)")
db.execute("create table if not exists tend_dep(m text, dep text, n integer, primary key(m, dep))")
BODACC = collect.BODACC
WHERE = 'familleavis="collective" and typeavis_lib="Avis initial" and jugement like "*Jugement d\'ouverture*"'
MOIS = "date_format(dateparution,\"YYYY-MM\")"

SECTIONS = [(1, 3, "Agriculture"), (5, 9, "Industries extractives"), (10, 33, "Industrie manufacturière"), (35, 35, "Énergie"),
            (36, 39, "Eau, déchets"), (41, 43, "Construction"), (45, 47, "Commerce"), (49, 53, "Transports et entreposage"),
            (55, 56, "Hébergement, restauration"), (58, 63, "Information, communication"), (64, 66, "Finance, assurance"),
            (68, 68, "Immobilier"), (69, 75, "Services spécialisés"), (77, 82, "Services administratifs et soutien"),
            (84, 84, "Administration"), (85, 85, "Enseignement"), (86, 88, "Santé, action sociale"), (90, 93, "Arts, loisirs"),
            (94, 96, "Autres services")]
DIVISIONS = {10: "Industries alimentaires", 11: "Boissons", 13: "Textile", 14: "Habillement", 15: "Cuir, chaussure", 16: "Bois",
             17: "Papier, carton", 18: "Imprimerie", 20: "Chimie", 21: "Pharmacie", 22: "Caoutchouc, plastique", 23: "Verre, matériaux non métalliques",
             24: "Métallurgie", 25: "Produits métalliques", 26: "Électronique, informatique", 27: "Équipements électriques", 28: "Machines",
             29: "Automobile", 30: "Autres matériels de transport", 31: "Meubles", 32: "Autres industries", 33: "Réparation et installation"}

def section(naf):
    try: d = int((naf or "")[:2])
    except ValueError: return None
    return next((l for a, b, l in SECTIONS if a <= d <= b), None)

def agrege_total():
    """Jugements d'ouverture par mois et par département (tous effectifs), 36 derniers mois."""
    debut = (dt.date.today().replace(day=1) - dt.timedelta(days=36 * 31)).replace(day=1).isoformat()
    off, rows = 0, 0
    db.execute("delete from tend_dep")
    while True:
        p = {"select": f"{MOIS} as m, numerodepartement as d, count(*) as n", "where": WHERE + f' and dateparution>="{debut}"',
             "group_by": f"{MOIS}, numerodepartement", "limit": 100, "offset": off}
        d = collect.get(BODACC + "?" + urllib.parse.urlencode(p))
        if not d or not d["results"]: break
        for r in d["results"]:
            m, dep = r.get(MOIS) or r.get("m"), r.get("numerodepartement") or r.get("d")
            if m and dep: db.execute("insert or replace into tend_dep values(?,?,?)", (m, dep, r["n"])); rows += 1
        off += 100
        if len(d["results"]) < 100 or off >= 9900: break
    db.commit()
    return rows

def mois_complets(n, fin=None):
    """Les n derniers mois entiers (le mois en cours est exclu : il est partiel)."""
    t = (fin or dt.date.today()).replace(day=1); out = []
    for _ in range(n):
        t = (t - dt.timedelta(days=1)).replace(day=1); out.append(t.strftime("%Y-%m"))
    return out[::-1]
def an_avant(m): return f"{int(m[:4]) - 1}{m[4:]}"
def var(a, b): return None if not b else round(100 * (a - b) / b)

def calcul_total():
    ms = mois_complets(24)
    ser = {m: db.execute("select coalesce(sum(n),0) from tend_dep where m=?", (m,)).fetchone()[0] for m in set(ms) | {an_avant(m) for m in ms}}
    r6, p6 = mois_complets(6), [an_avant(m) for m in mois_complets(6)]
    r12, p12 = mois_complets(12), [an_avant(m) for m in mois_complets(12)]
    S = lambda L: sum(ser[m] for m in L)
    deps = []
    for (dep,) in db.execute("select distinct dep from tend_dep").fetchall():
        par_m = {m: (db.execute("select coalesce(sum(n),0) from tend_dep where dep=? and m=?", (dep, m)).fetchone()[0]) for m in r6 + p6}
        a, b = sum(par_m[m] for m in r6), sum(par_m[m] for m in p6)
        if b < 40: continue
        v = var(a, b); alerte = None
        if v <= -50: alerte = "rupture probable de la source (effondrement brutal), à ne pas lire comme une amélioration"
        elif a and max(par_m[m] for m in r6) > 0.3 * a and v > 20: alerte = "hausse portée par un seul mois"
        deps.append({"dep": dep, "recent": a, "precedent": b, "variation_pct": v, "alerte": alerte})
    deps.sort(key=lambda x: -x["variation_pct"])
    rup = [x["dep"] for x in deps if x["alerte"] and x["variation_pct"] <= -50]
    def SX(L):
        q = "select coalesce(sum(n),0) from tend_dep where m in (%s)" % ",".join("?" * len(L))
        if rup: q += " and dep not in (%s)" % ",".join("?" * len(rup))
        return db.execute(q, list(L) + rup).fetchone()[0]
    return {"serie": [{"mois": m, "n": ser[m], "n_an_avant": ser[an_avant(m)]} for m in ms],
            "recent_6_mois": {"periode": [r6[0], r6[-1]], "n": S(r6), "n_an_avant": S(p6), "variation_pct": var(S(r6), S(p6))},
            "recent_12_mois": {"periode": [r12[0], r12[-1]], "n": S(r12), "n_an_avant": S(p12), "variation_pct": var(S(r12), S(p12))},
            # même calcul sans les départements en rupture de série (effondrement brutal = changement dans la source)
            "ruptures": sorted(rup),
            "recent_6_mois_hors_ruptures": {"periode": [r6[0], r6[-1]], "n": SX(r6), "n_an_avant": SX(p6), "variation_pct": var(SX(r6), SX(p6))},
            "recent_12_mois_hors_ruptures": {"periode": [r12[0], r12[-1]], "n": SX(r12), "n_an_avant": SX(p12), "variation_pct": var(SX(r12), SX(p12))},
            "departements": deps}

def calcul_gros():
    evs = [json.loads(r[0]) for r in db.execute("select js from ev")]
    evs = [e for e in evs if e.get("source") == "BODACC" and e.get("date_publication")]
    sem = [r[0] for r in db.execute("select sem from bk_done order by sem")]
    if not sem: return {"couverture": None}
    cov = [min(sem), (dt.date.fromisoformat(max(sem)) + dt.timedelta(days=7)).isoformat()]
    ms = mois_complets(6)                       # 6 mois récents contre les mêmes mois un an plus tôt (19 mois d'historique suffisent)
    pas = [an_avant(m) for m in ms]
    debut_besoin = min(pas) + "-01"
    fin_besoin = (dt.date.fromisoformat(ms[-1] + "-01") + dt.timedelta(days=32)).replace(day=1).isoformat()
    comparable = cov[0] <= debut_besoin and cov[1] >= fin_besoin
    cnt = lambda L, f=lambda e: True: sum(1 for e in evs if e["date_publication"][:7] in L and f(e))
    out = {"couverture": cov, "comparable": comparable, "n_total": len(evs),
           "serie": [{"mois": m, "n": cnt([m]), "emplois_min": sum(e.get("emplois_min") or 0 for e in evs if e["date_publication"][:7] == m)} for m in mois_complets(18)]}
    if comparable:
        out["recent_6_mois"] = {"periode": [ms[0], ms[-1]], "n": cnt(ms), "n_an_avant": cnt(pas), "variation_pct": var(cnt(ms), cnt(pas)),
                                 "emplois_min": sum(e.get("emplois_min") or 0 for e in evs if e["date_publication"][:7] in ms),
                                 "emplois_min_an_avant": sum(e.get("emplois_min") or 0 for e in evs if e["date_publication"][:7] in pas)}
        for nom, key in (("secteurs", section), ("industrie", lambda naf: DIVISIONS.get(int((naf or "00")[:2])) if 10 <= int((naf or "00")[:2] or 0) <= 33 else None),
                         ("departements", None)):
            groupes = {}
            for e in evs:
                k = e.get("dep") if key is None else key(e.get("naf"))
                if not k: continue
                g = groupes.setdefault(k, [0, 0])
                if e["date_publication"][:7] in ms: g[0] += 1
                elif e["date_publication"][:7] in pas: g[1] += 1
            out[nom] = sorted(({"nom": k, "recent": a, "precedent": b, "variation_pct": var(a, b)} for k, (a, b) in groupes.items() if a + b >= 6),
                              key=lambda x: -(x["recent"] + x["precedent"]))[:15]
    return out

def ecrire():
    n = agrege_total()
    out = {"maj": dt.datetime.now(dt.timezone.utc).isoformat(timespec="minutes"), "source": "BODACC (DILA), jugements d'ouverture de procédures collectives, date de publication",
           "toutes_tailles": calcul_total(), "plus_de_50_salaries": calcul_gros()}
    try:
        import suites; out["suites"] = suites.cohortes()
    except Exception as ex:
        print("suites :", ex, file=sys.stderr)
    tmp = os.path.join(H, "public", "tendance.json.tmp")
    json.dump(out, open(tmp, "w"), ensure_ascii=False, separators=(",", ":")); os.replace(tmp, os.path.join(H, "public", "tendance.json"))
    print("tendance.json : %d lignes mois×département, 50+ : %s" % (n, out["plus_de_50_salaries"].get("couverture")), file=sys.stderr)

def rattrapage(mois=19):
    """Semaine par semaine, de la plus récente à la plus ancienne ; une semaine terminée n'est pas refaite."""
    fin = dt.date.today() - dt.timedelta(days=dt.date.today().weekday())     # lundi de la semaine en cours (exclue)
    d = fin
    while d > dt.date.today() - dt.timedelta(days=30 * mois):
        d0 = d - dt.timedelta(days=7)
        if not db.execute("select 1 from bk_done where sem=?", (d0.isoformat(),)).fetchone():
            collect.bodacc(d0.isoformat(), d.isoformat())
            db.execute("insert or replace into bk_done values(?)", (d0.isoformat(),)); db.commit()
            print("semaine", d0, "ok", file=sys.stderr, flush=True)
            ecrire()
        d = d0

if __name__ == "__main__":
    if sys.argv[1:2] == ["rattrapage"]: rattrapage(int(sys.argv[2]) if len(sys.argv) > 2 else 19)
    else: ecrire()
