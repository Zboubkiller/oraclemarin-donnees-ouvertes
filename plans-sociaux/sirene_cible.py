"""Établissements COMPLETS (principal et secondaires, ouverts et fermés, toutes tailles) de toutes les sociétés rattachées à une annonce (hors événements BODACC).
La base locale sirene.db ne garde que les entreprises de 10 salariés et plus et leurs établissements avec salariés : une petite société liquidée ou un site fermé n'y figure pas.
Source : le même stock Sirene (data.gouv.fr) que l'Annuaire des entreprises ; fichier brut supprimé après extraction. Table etab_tous dans sirene_cible.db (séparée de sirene.db, qui est reconstruite chaque mois). Usage : sirene_cible.py"""
import json, os, sqlite3, sys, urllib.request
import duckdb
H = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, H)
T = os.path.join(H, "sirene_tmp"); DB = os.path.join(H, "sirene_cible.db")
DS = "https://www.data.gouv.fr/api/1/datasets/base-sirene-des-entreprises-et-de-leurs-etablissements-siren-siret/"

def cibles():
    E = json.load(open(os.path.join(H, "public", "data.json"), encoding="utf-8"))["evenements"]
    out = set()
    for e in E:
        if e.get("siren") and e.get("source") != "BODACC": out.add(e["siren"])
    return sorted(out)

def main():
    L = cibles()
    if not L: print("aucune cible", file=sys.stderr); return
    S = sqlite3.connect(DB)
    S.execute("create table if not exists etab_tous(siret text primary key, siren text, insee text, commune text, cp text, adresse text, etat text, date_etat text, siege int, creation text, enseigne text, naf text, tranche text)")
    S.execute("create table if not exists faits(siren text primary key)")
    faits = {r[0] for r in S.execute("select siren from faits")}
    L = [x for x in L if x not in faits]
    if len(L) < 15 and faits:                      # le stock fait plus de 2 Go : on ne le télécharge que quand il y a assez de nouvelles sociétés
        print(f"établissements complets : {len(L)} nouvelles sociétés, en attente (seuil 15)", file=sys.stderr); return
    os.makedirs(T, exist_ok=True); f = os.path.join(T, "etab_cible.parquet")
    res = json.load(urllib.request.urlopen(DS, timeout=60))["resources"]
    url = next(r["url"] for r in res if r.get("format") == "parquet" and "StockEtablissement -" in r["title"])
    print("téléchargement du stock des établissements…", file=sys.stderr)
    urllib.request.urlretrieve(url, f)
    c = duckdb.connect()
    ids = ",".join("'" + s + "'" for s in L)
    rows = c.execute(f"""select siret, siren, codeCommuneEtablissement, libelleCommuneEtablissement, codePostalEtablissement,
        trim(concat_ws(' ', numeroVoieEtablissement, indiceRepetitionEtablissement, typeVoieEtablissement, libelleVoieEtablissement)) as adresse,
        etatAdministratifEtablissement, dateDebut, etablissementSiege, dateCreationEtablissement,
        concat_ws(' | ', enseigne1Etablissement, enseigne2Etablissement, enseigne3Etablissement, denominationUsuelleEtablissement),
        activitePrincipaleEtablissement, trancheEffectifsEtablissement
        from '{f}' where siren in ({ids}) and statutDiffusionEtablissement = 'O'""").fetchall()
    S.executemany("insert or replace into etab_tous values(?,?,?,?,?,?,?,?,?,?,?,?,?)", [(r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7], 1 if r[8] else 0, r[9], r[10], r[11], r[12]) for r in rows])
    S.executemany("insert or ignore into faits values(?)", [(x,) for x in L])
    S.execute("create index if not exists i_et_siren on etab_tous(siren)"); S.commit()
    print(f"établissements complets : {len(rows)} pour {len(L)} sociétés", file=sys.stderr)
    os.remove(f)

if __name__ == "__main__":
    main()
