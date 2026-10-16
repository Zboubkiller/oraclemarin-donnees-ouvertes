"""Programmes d'État (PIA, France 2030) financés par l'ADEME : projets par bénéficiaire (SIREN), jeu de données « Programmes d'État - Bénéficiaires des projets
financés par l'ADEME » (data.ademe.fr, Licence Ouverte). Les projets datés dans les 24 mois avant l'annonce sont signalés. Ces aides ne sont pas additionnées
à celles de « Les aides financières de l'ADEME » : un même projet peut figurer dans les deux jeux.
Écrit e["programmes_etat"] = {n, total, projets (5 plus récents), proximite {n, montant, plus_recent}}. Table pe_ademe de cache.db, rafraîchie chaque semaine."""
import json, os, sqlite3, sys, time, urllib.parse, urllib.request
H = os.path.dirname(os.path.abspath(__file__))
DS = "https://data.ademe.fr/data-fair/api/v1/datasets/meiumzclegltc9gw3srk8dz5/lines"
SEL = "siren,tiers_nom,date_contractualisation,montant_aide_modalite,pia_france_2030_reporting,nom_du_projet,dossier_objet,dossier_code,aap_objet_reporting"
db = sqlite3.connect(os.path.join(H, "cache.db"))
db.execute("create table if not exists pe_ademe(siren text, dossier text, date text, montant real, programme text, projet text, objet text, ao text, nom text)")
db.execute("create table if not exists pe_ademe_ts(k text primary key, ts real)")

def mois(d): return int(d[:4]) * 12 + int(d[5:7]) if d and len(d) >= 7 and d[:4].isdigit() else None

def charger():
    r = db.execute("select ts from pe_ademe_ts where k='pe'").fetchone()
    if r and time.time() - r[0] < 7 * 86400: return True
    rows, after = [], None
    while True:
        u = f"{DS}?size=1000&select={SEL}" + (f"&after={after}" if after else "")
        d = json.load(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "plans-sociaux"}), timeout=60))
        rows += d.get("results", [])
        if not d.get("next"): break
        after = urllib.parse.parse_qs(urllib.parse.urlparse(d["next"]).query).get("after", [None])[0]
        if not after: break
    if len(rows) < 1000: raise RuntimeError("jeu de données incomplet : %d lignes" % len(rows))
    db.execute("delete from pe_ademe")
    db.executemany("insert into pe_ademe values(?,?,?,?,?,?,?,?,?)", [(str(x.get("siren") or ""), x.get("dossier_code"), (x.get("date_contractualisation") or "")[:10], x.get("montant_aide_modalite") or 0,
                   x.get("pia_france_2030_reporting"), x.get("nom_du_projet"), (x.get("dossier_objet") or "")[:200], (x.get("aap_objet_reporting") or "")[:120], x.get("tiers_nom")) for x in rows])
    db.execute("replace into pe_ademe_ts values('pe', ?)", (time.time(),)); db.commit()
    return True

def enrichir(evs):
    try: charger()
    except Exception as ex:
        print("programmes d'État :", ex, file=sys.stderr)
        if not db.execute("select count(*) from pe_ademe").fetchone()[0]: return
    P = {}
    for s, dos, d, m, prog, pj, ob, ao, nom in db.execute("select * from pe_ademe where siren<>''"):
        P.setdefault(s, []).append({"dossier": dos, "date": d, "montant": round(m or 0), "programme": prog, "projet": pj, "objet": ob, "appel": ao})
    n = a = 0
    for e in evs:
        e.pop("programmes_etat", None)
        L = P.get(e.get("siren") or "")
        if not L or e.get("source") == "BODACC": continue
        L = sorted(L, key=lambda x: x["date"] or "", reverse=True)
        out = {"n": len(L), "total": sum(x["montant"] for x in L), "projets": L[:5],
               "url": "https://data.ademe.fr/datasets/meiumzclegltc9gw3srk8dz5"}
        me = mois(e.get("date"))
        if me is not None:
            dans = [{**x, "delai_mois": me - mois(x["date"])} for x in L if mois(x["date"]) is not None and 0 <= me - mois(x["date"]) <= 24]
            if dans: out["proximite"] = {"n": len(dans), "montant": sum(x["montant"] for x in dans), "plus_recent": dans[0]}; a += 1
        e["programmes_etat"] = out; n += 1
    print(f"programmes d'État : {n} annonces rattachées à des projets PIA / France 2030, dont {a} dans les 24 mois avant l'annonce", file=sys.stderr)
