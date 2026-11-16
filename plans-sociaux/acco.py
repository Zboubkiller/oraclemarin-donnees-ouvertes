"""Accords d'entreprise publiés par la DILA (base ACCO, Légifrance), en données ouvertes : on garde ceux qui touchent à
l'emploi — accords de méthode et accords de PSE, ruptures conventionnelles collectives, plans de départs volontaires,
accords de performance collective, activité partielle de longue durée. Rattachement sûr : chaque accord porte le SIRET.
Les archives (plusieurs centaines de Mo par semaine, 48 Go pour le stock) sont lues en flux : seules les fiches XML
retenues sont conservées, dans acco.db (table acco).
Usage : acco.py semaines   (archives hebdomadaires pas encore lues)
        acco.py stock      (stock complet de juillet 2025 : historique, très long)"""
import json, os, re, sqlite3, sys, tarfile, time, urllib.request
import xml.etree.ElementTree as ET
H = os.path.dirname(os.path.abspath(__file__))
BASE = "https://echanges.dila.gouv.fr/OPENDATA/ACCO/"
UA = {"User-Agent": "Mozilla/5.0 (veille plans-sociaux; +https://oraclemarin.fr/plans-sociaux/)"}
db = sqlite3.connect(os.path.join(H, "acco.db"), timeout=120)   # base séparée : la lecture des archives ne bloque pas cache.db
db.execute("create table if not exists acco(id text primary key, siret text, siren text, cat text, js text)")
db.execute("create table if not exists acco_fichiers(nom text primary key, n integer, ts real)")
CATS = [  # (catégorie, codes thème, motif du titre)
    ("pse", {"075"}, r"sauvegarde de l.emploi|\bpse\b|plan social|licenciements? (?:collectifs? )?(?:pour motif )?[ée]conomique"),
    ("rcc", {"079"}, r"rupture[s]? conventionnelle[s]? collective"),
    ("pdv", set(), r"d[ée]parts? volontaires?|plan de d[ée]part"),
    ("apc", {"080"}, r"accord de performance collective|\bapc\b|maintien dans l.emploi"),
    ("apld", set(), r"activit[ée] partielle|\bapld|chômage partiel"),
]
EXCLURE = r"prime de performance|int[ée]ressement|participation|performance collective.{0,20}prime|r[ée]mun[ée]ration variable"
LIB = {"pse": "accord lié à un plan de sauvegarde de l'emploi", "rcc": "rupture conventionnelle collective", "pdv": "plan de départs volontaires",
       "apc": "accord de performance collective", "apld": "activité partielle (longue durée)"}

def categorie(titre, themes):
    """Le titre prime : les codes thème sont souvent cochés large. Thème seul accepté si le titre est générique (« accord de
    méthode », « mesures d'accompagnement », « réorganisation ») et ne parle pas de gestion prévisionnelle des emplois."""
    t = (titre or "").lower()
    if re.search(EXCLURE, t) and not re.search(r"rupture|sauvegarde|d[ée]part", t): return None
    for cat, codes, rx in CATS:
        if re.search(rx, t): return cat
    if re.search(r"gepp|gpec|gestion (?:pr[ée]visionnelle )?des emplois|parcours professionnels|n[ée]gociation annuelle|\bnao\b", t): return None
    if not re.search(r"m[ée]thode|accompagnement social|mesures d.accompagnement|r[ée]organisation|restructuration|projet de transformation|\bplan\b", t): return None
    for cat, codes, rx in CATS:
        if codes & themes: return cat
    return None

def lire_xml(b):
    try: r = ET.fromstring(b)
    except ET.ParseError: return None
    g = lambda p: (r.findtext(".//" + p) or "").strip()
    themes = {x.findtext("CODE") for x in r.iter("THEME")}
    cat = categorie(g("TITRE_TXT"), themes)
    if not cat: return None
    siret = re.sub(r"\D", "", g("SIRET"))
    return {"id": g("ID"), "cat": cat, "titre": re.sub(r"\s+", " ", g("TITRE_TXT")), "siret": siret, "siren": siret[:9] if len(siret) >= 9 else None,
            "raison_sociale": g("RAISON_SOCIALE"), "ape": g("CODE_APE"), "date_texte": g("DATE_TEXTE") or None, "date_depot": g("DATE_DEPOT") or None,
            "date_diffusion": g("DATE_DIFFUSION") or None, "avenant": bool(re.match(r"\s*(?:l.)?avenant", g("TITRE_TXT"), re.I)),
            "syndicats": [x.findtext("LIBELLE") for x in r.iter("SYNDICAT") if x.findtext("LIBELLE")], "themes": sorted(x for x in themes if x),
            "url": "https://www.legifrance.gouv.fr/acco/id/" + g("ID")}

def lire_archive(nom):
    n = 0
    resp = urllib.request.urlopen(urllib.request.Request(BASE + nom, headers=UA), timeout=300)
    with tarfile.open(fileobj=resp, mode="r|gz") as tf:
        for m in tf:
            if not m.isfile(): continue
            if m.name.endswith("liste_suppression_acco.dat"):
                for l in tf.extractfile(m).read().decode("utf-8", "ignore").split():
                    i = l.strip().split("/")[-1].replace(".xml", "")
                    if i.startswith("ACCOTEXT"): db.execute("delete from acco where id=?", (i,))
                continue
            if "/TEXT/" not in m.name or not m.name.endswith(".xml"): continue
            a = lire_xml(tf.extractfile(m).read())
            if a and a["id"]:
                db.execute("replace into acco values(?,?,?,?,?)", (a["id"], a["siret"], a["siren"], a["cat"], json.dumps(a, ensure_ascii=False))); n += 1
                if n % 200 == 0: db.commit()
    db.commit()
    return n

def archives():
    h = urllib.request.urlopen(urllib.request.Request(BASE, headers=UA), timeout=60).read().decode()
    return sorted(set(re.findall(r"ACCO_\d{8}-\d{6}\.tar\.gz", h)))

def semaines(maxi=None):
    faits = {r[0] for r in db.execute("select nom from acco_fichiers")}
    a_lire = [a for a in archives() if a not in faits][:maxi]
    for nom in a_lire:
        t = time.time()
        try: n = lire_archive(nom)
        except Exception as ex:
            print("acco :", nom, ex, file=sys.stderr); continue
        db.execute("replace into acco_fichiers values(?,?,?)", (nom, n, time.time())); db.commit()
        print(f"acco : {nom} : {n} accords retenus ({round(time.time() - t)} s)", file=sys.stderr, flush=True)

def stock():
    h = urllib.request.urlopen(urllib.request.Request(BASE, headers=UA), timeout=60).read().decode()
    nom = sorted(set(re.findall(r"Freemium_acco_global_\d{8}-\d{6}\.tar\.gz", h)))[-1]
    if db.execute("select 1 from acco_fichiers where nom=?", (nom,)).fetchone(): return
    n = lire_archive(nom)
    db.execute("replace into acco_fichiers values(?,?,?)", (nom, n, time.time())); db.commit()
    print(f"acco : stock {nom} : {n} accords retenus", file=sys.stderr)

def par_siren():
    out = {}
    for s, js in db.execute("select siren, js from acco where siren is not null"):
        out.setdefault(s, []).append(json.loads(js))
    return out

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "stock": stock()
    else: semaines(int(sys.argv[2]) if len(sys.argv) > 2 else None)
