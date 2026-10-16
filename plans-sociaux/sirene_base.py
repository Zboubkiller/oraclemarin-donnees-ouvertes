"""Base locale des entreprises employeuses (répertoire Sirene, fichiers stock mensuels de data.gouv.fr, sans clé).
Garde (avec l'adresse de chaque établissement : voie, code postal) : unités légales diffusibles, hors entrepreneurs individuels, de 10 salariés et plus (actives, ou cessées depuis 2024) ;
leurs établissements (actifs, ou fermés depuis 2024) qui ont des salariés ou sont le siège. Index plein texte sur les noms,
sigles, noms d'usage et enseignes. Résultat : sirene.db (SQLite). Les fichiers bruts (≈3 Go) sont supprimés après coup.
Usage : sirene_base.py [construire|telecharger]"""
import json, os, sqlite3, sys, time, urllib.request
import duckdb
H = os.path.dirname(os.path.abspath(__file__)); T = os.path.join(H, "sirene_tmp"); DB = os.path.join(H, "sirene.db")
DS = "https://www.data.gouv.fr/api/1/datasets/base-sirene-des-entreprises-et-de-leurs-etablissements-siren-siret/"

def telecharger():
    os.makedirs(T, exist_ok=True)
    res = json.load(urllib.request.urlopen(DS, timeout=60))["resources"]
    for r in res:
        if r.get("format") != "parquet": continue
        for cle, f in (("StockUniteLegale -", "ul.parquet"), ("StockEtablissement -", "etab.parquet"), ("StockEtablissementLiensSuccession -", "succ.parquet")):
            if cle in r["title"]:
                print("téléchargement", r["title"], file=sys.stderr)
                urllib.request.urlretrieve(r["url"], os.path.join(T, f))

def construire():
    c = duckdb.connect()
    ul, et = os.path.join(T, "ul.parquet"), os.path.join(T, "etab.parquet")
    c.execute(f"""create table u as select siren, denominationUniteLegale as nom, sigleUniteLegale as sigle,
        concat_ws(' | ', denominationUsuelle1UniteLegale, denominationUsuelle2UniteLegale, denominationUsuelle3UniteLegale) as usuels,
        activitePrincipaleUniteLegale as naf, trancheEffectifsUniteLegale as tranche, categorieEntreprise as cat,
        etatAdministratifUniteLegale as etat, dateDebut as date_etat, nicSiegeUniteLegale as nic_siege, categorieJuridiqueUniteLegale as cj, dateCreationUniteLegale as creation
        from '{ul}' where statutDiffusionUniteLegale = 'O' and categorieJuridiqueUniteLegale <> '1000' and denominationUniteLegale is not null
        and trancheEffectifsUniteLegale in ('11','12','21','22','31','32','41','42','51','52','53')
        and (etatAdministratifUniteLegale = 'A' or dateDebut >= '2024-01-01')""")
    print("unités légales :", c.execute("select count(*) from u").fetchone()[0], file=sys.stderr)
    c.execute(f"""create table e as select siret, siren, codeCommuneEtablissement as insee, libelleCommuneEtablissement as commune,
        trancheEffectifsEtablissement as tranche, etatAdministratifEtablissement as etat, dateDebut as date_etat,
        concat_ws(' | ', enseigne1Etablissement, enseigne2Etablissement, enseigne3Etablissement, denominationUsuelleEtablissement) as enseigne,
        activitePrincipaleEtablissement as naf, etablissementSiege as siege, dateCreationEtablissement as creation,
        trim(concat_ws(' ', numeroVoieEtablissement, indiceRepetitionEtablissement, typeVoieEtablissement, libelleVoieEtablissement)) as adresse,
        codePostalEtablissement as cp
        from '{et}' where siren in (select siren from u) and statutDiffusionEtablissement = 'O'
        and (etatAdministratifEtablissement = 'A' or dateDebut >= '2024-01-01')
        and (etablissementSiege or trancheEffectifsEtablissement not in ('NN', '00'))""")
    print("établissements :", c.execute("select count(*) from e").fetchone()[0], file=sys.stderr)
    # tous les établissements actifs (même sans effectif déclaré) : sert à reconnaître un déménagement dans la même commune
    c.execute(f"""create table act as select siren, codeCommuneEtablissement as insee, max(cast(dateCreationEtablissement as varchar)) as creation from '{et}'
        where siren in (select siren from u) and etatAdministratifEtablissement = 'A' group by 1, 2""")
    print("couples entreprise-commune actifs :", c.execute("select count(*) from act").fetchone()[0], file=sys.stderr)
    tmp = DB + ".tmp"
    if os.path.exists(tmp): os.remove(tmp)
    s = sqlite3.connect(tmp)
    s.executescript("""create table ul(siren text primary key, nom text, sigle text, usuels text, naf text, tranche text, cat text, etat text, date_etat text, cj text, creation text);
        create table etab(siret text primary key, siren text, insee text, dep text, commune text, tranche text, etat text, date_etat text, enseigne text, naf text, siege int, creation text, adresse text, cp text);
        create virtual table noms using fts5(nom, siren unindexed, siret unindexed, genre unindexed, tokenize='unicode61 remove_diacritics 2');""")
    for row in c.execute("select siren, nom, sigle, usuels, naf, tranche, cat, etat, cast(date_etat as varchar), cj, cast(creation as varchar) from u").fetchall():
        s.execute("insert into ul values(?,?,?,?,?,?,?,?,?,?,?)", row)
        s.execute("insert into noms values(?,?,?,?)", (row[1], row[0], None, "nom"))
        if row[2]: s.execute("insert into noms values(?,?,?,?)", (row[2], row[0], None, "sigle"))
        for x in (row[3] or "").split(" | "):
            if x.strip(): s.execute("insert into noms values(?,?,?,?)", (x.strip(), row[0], None, "usuel"))
    cur = c.execute("select siret, siren, insee, commune, tranche, etat, cast(date_etat as varchar), enseigne, naf, siege, cast(creation as varchar), adresse, cp from e")
    n = 0
    while True:
        rows = cur.fetchmany(50000)
        if not rows: break
        for r in rows:
            insee = r[2] or ""
            dep = insee[:3] if insee.startswith("97") else insee[:2]
            s.execute("insert into etab values(?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (r[0], r[1], insee, dep, r[3], r[4], r[5], r[6], r[7], r[8], int(bool(r[9])), r[10], r[11], r[12]))
            for x in (r[7] or "").split(" | "):
                if x.strip(): s.execute("insert into noms values(?,?,?,?)", (x.strip(), r[1], r[0], "enseigne"))
            n += 1
    s.execute("create table actifs(siren text, insee text, creation text)")
    s.executemany("insert into actifs values(?,?,?)", c.execute("select siren, insee, creation from act").fetchall())
    # liens de succession depuis 2024 (transferts, reprises) : un établissement fermé avec un successeur n'est pas une fermeture
    s.execute("create table succession(pred text, succ text, date text, transfert int, continuite int)")
    sp = os.path.join(T, "succ.parquet")
    if os.path.exists(sp):
        s.executemany("insert into succession values(?,?,?,?,?)", c.execute(f"""select siretEtablissementPredecesseur, siretEtablissementSuccesseur,
            cast(dateLienSuccession as varchar), transfertSiege, continuiteEconomique from '{sp}' where dateLienSuccession >= '2024-01-01'""").fetchall())
    s.executescript("create index succ_pred on succession(pred); create index actifs_i on actifs(siren, insee); create index etab_siren on etab(siren); create index etab_insee on etab(insee); create index etab_dep on etab(dep); create index etab_cp on etab(cp, adresse);")
    s.commit(); s.close(); os.replace(tmp, DB)
    print("base :", DB, round(os.path.getsize(DB) / 1e6), "Mo,", n, "établissements", file=sys.stderr)

if __name__ == "__main__":
    a = sys.argv[1] if len(sys.argv) > 1 else "tout"
    if a in ("telecharger", "tout"): telecharger()
    if a in ("construire", "tout"): construire()
    if a == "tout":
        for f in ("ul.parquet", "etab.parquet", "succ.parquet"):
            try: os.remove(os.path.join(T, f))
            except OSError: pass
