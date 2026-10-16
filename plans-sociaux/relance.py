"""France Relance : lauréats nominatifs des projets industriels (data.economie.gouv.fr, dataset plan-de-relance).
Chaque ligne = un projet soutenu, avec SIREN, mesure et date ; le montant n'est PAS publié par entreprise.
Stocké dans cache.db (table relance), rechargé au plus une fois par semaine par aides.py."""
import csv, io, json, sys, time, urllib.request
URL = "https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets/plan-de-relance/exports/csv?use_labels=true"

def charge(db):
    db.execute("create table if not exists relance(siren text, js text)")
    db.execute("create table if not exists relance_ts(ts real)")
    r = db.execute("select max(ts) from relance_ts").fetchone()[0]
    if r and time.time() - r < 7 * 86400: return
    txt = urllib.request.urlopen(urllib.request.Request(URL, headers={"User-Agent": "tracker-plans-sociaux/0.3"}), timeout=120).read().decode("utf-8-sig")
    rows = [x for x in csv.DictReader(io.StringIO(txt), delimiter=";") if (x.get("SIREN") or "").strip().isdigit()]
    if len(rows) < 1000: raise RuntimeError("export Relance incomplet : %d lignes" % len(rows))
    db.execute("delete from relance")
    for x in rows:
        db.execute("insert into relance values(?,?)", (x["SIREN"].strip().zfill(9), json.dumps({
            "entreprise": x["ENTREPRISE"], "mesure": x["MESURE"], "date": (x.get("MISE À JOUR ") or "")[:10], "volet": x["VOLET_RELANCE"],
            "lieu": x["NOM_COMMUNE"], "projet": (x["DESCRIPTION_PROJET"] or "")[:220]}, ensure_ascii=False)))
    db.execute("delete from relance_ts"); db.execute("insert into relance_ts values(?)", (time.time(),)); db.commit()
    print("relance :", len(rows), "projets", file=sys.stderr)
