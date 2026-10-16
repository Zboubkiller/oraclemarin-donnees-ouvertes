"""Données de la carte des liens entre sociétés (page privée /graphe) : nœuds = sociétés (SIREN), liens = societes_liees.csv (avec preuve).
Taille d'un nœud = effectif de la société (tranche INSEE) ; couleur = ce qu'on sait d'elle (plan social, procédure collective, simple lien)."""
import csv, json, os, sqlite3, sys, math
H = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, H)
import collect, commun

def donnees():
    E = json.load(open(os.path.join(H, "public", "data.json")))["evenements"]
    S = sqlite3.connect(os.path.join(H, "sirene.db"))
    C = sqlite3.connect(os.path.join(H, "cache.db"), timeout=60)
    api = {}
    try: api = {s: json.loads(j) for s, j in C.execute("select siren, js from audit_api")}
    except sqlite3.OperationalError: pass
    info = {}
    for e in E:
        s = e.get("siren")
        if not s: continue
        d = info.setdefault(s, {"noms": {}, "annonces": 0, "emplois": 0, "proc": [], "types": set()})
        nom = e.get("entreprise")
        if nom and nom != e.get("titre"): d["noms"][nom] = d["noms"].get(nom, 0) + 1
        if e.get("source") == "BODACC":
            d["proc"].append((e.get("date") or "", e.get("type") or ""))
        elif e.get("partie_de"):
            d["annonces"] += 1; d["types"].add(e.get("type") or "")      # société rattachée à un plan multi-sociétés : l'annonce la concerne, sans chiffre propre
        else:
            d["annonces"] += 1
            if not commun.exclu_totaux(e): d["emplois"] += e.get("emplois_min") or 0
            d["types"].add(e.get("type") or "")
    liens, vus, noms_csv = [], set(), {}
    for r in csv.DictReader(open(os.path.join(H, "public", "societes_liees.csv"), encoding="utf-8-sig")):
        if r["societe"]: noms_csv.setdefault(r["siren"], r["societe"])
        if r["societe_liee"]: noms_csv.setdefault(r["siren_lie"], r["societe_liee"])
        a, b = r["siren"], r["siren_lie"]
        cle = (min(a, b), max(a, b), r["force"])
        if not a or not b or a == b: continue
        liens.append({"s": a, "t": b, "force": r["force"], "preuve": r["preuves"][:200]}) if cle not in vus else None
        vus.add(cle)
    ids = {l["s"] for l in liens} | {l["t"] for l in liens}
    noeuds = []
    for s in sorted(ids):
        u = S.execute("select nom, tranche, naf, etat from ul where siren=?", (s,)).fetchone()
        a = api.get(s) or {}
        nom = (info.get(s, {}).get("noms") and max(info[s]["noms"], key=info[s]["noms"].get)) or (u[0] if u else a.get("nom")) or noms_csv.get(s) or s
        tr = (u[1] if u else a.get("tranche")) or ""
        lo, hi = collect.TR.get(tr, (None, None))
        d = info.get(s, {})
        proc = sorted(d.get("proc", []))
        noeuds.append({"id": s, "nom": (u[0] if u else a.get("nom")) or noms_csv.get(s) or nom, "cite": nom if u and nom != u[0] else None,
                       "eff": [lo, hi] if lo is not None else None, "annonces": d.get("annonces", 0), "emplois": d.get("emplois", 0),
                       "proc": proc[-1][1] + " (" + proc[-1][0][:7] + ")" if proc else None, "types": sorted(t for t in d.get("types", []) if t),
                       "cessee": (u[3] == "C") if u else (a.get("etat") == "C"),
                       "url": commun.BASE + "/entreprise/" + s + "-" + commun.slug(nom or "")[:60].strip("-") + "/" if d.get("annonces") or proc else None})
    return {"noeuds": noeuds, "liens": liens}

if __name__ == "__main__":
    d = donnees(); print(len(d["noeuds"]), "nœuds,", len(d["liens"]), "liens"); print(d["noeuds"][0])
