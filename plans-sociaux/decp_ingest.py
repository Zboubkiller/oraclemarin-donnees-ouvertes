"""DECP consolidé (data.gouv.fr, fichiers mensuels decp-AAAA-MM.json) -> table decp de cache.db.
Complète decp-v3-marches-valides (data.economie.gouv.fr), dont la dernière notification date de février 2024.
Un fichier à la fois (~140 Mo) : téléchargé dans /tmp, chargé, versé en base, supprimé.
Usage : python3 decp_ingest.py [AAAA-MM de départ]   (défaut 2024-01)
Une ligne par (marché, titulaire) ; on garde les SIRET/SIREN uniquement."""
import json, os, re, sqlite3, sys, time, urllib.request
H = os.path.dirname(os.path.abspath(__file__))
db = sqlite3.connect(os.path.join(H, "cache.db"), timeout=120)
db.execute("create table if not exists decp(id text, siren text, n_tit integer, montant real, date text, duree integer, ac integer, "
           "acheteur text, nature text, primary key(id, siren))")
db.execute("create table if not exists decp_fichiers(f text primary key, ts real, n integer)")
UA = {"User-Agent": "tracker-plans-sociaux/0.4"}

def fichiers(depuis):
    d = json.load(urllib.request.urlopen(urllib.request.Request("https://www.data.gouv.fr/api/1/datasets/5cd57bf68b4c4179299eb0e9/", headers=UA), timeout=60))
    out = [(x["title"], x["url"]) for x in d["resources"] if re.fullmatch(r"decp-\d{4}-\d{2}\.json", x["title"]) and x["title"][5:12] >= depuis]
    return sorted(out)

def ingere(titre, url):
    tmp = "/tmp/" + titre
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=300) as r, open(tmp, "wb") as f:
        while True:
            b = r.read(1 << 20)
            if not b: break
            f.write(b)
    d = json.load(open(tmp, encoding="utf-8")); os.remove(tmp)
    ms = d.get("marches", d)
    ms = ms.get("marche", ms) if isinstance(ms, dict) else ms
    n = 0
    for m in ms:
        try:
            tits = [t["titulaire"] for t in (m.get("titulaires") or []) if t.get("titulaire")]
            sirens = []
            for t in tits:
                i = (t.get("id") or "").replace(" ", "")
                if t.get("typeIdentifiant") == "SIRET" and len(i) == 14 and i.isdigit(): sirens.append(i[:9])
                elif t.get("typeIdentifiant") == "SIREN" and len(i) == 9 and i.isdigit(): sirens.append(i)
            mt = m.get("montant")
            if not sirens or not isinstance(mt, (int, float)) or mt <= 0 or not m.get("dateNotification"): continue
            tech = " ".join((m.get("techniques") or {}).get("technique", []) if isinstance(m.get("techniques"), dict) else [])
            ac = int("accord" in (m.get("nature") or "").lower() or "accord" in tech.lower())
            for s in set(sirens):
                db.execute("insert or replace into decp values(?,?,?,?,?,?,?,?,?)", (m["id"], s, len(set(sirens)), float(mt), m["dateNotification"][:10],
                           m.get("dureeMois"), ac, (m.get("acheteur") or {}).get("id"), m.get("nature")))
                n += 1
        except Exception:
            continue
    db.commit()
    return n

if __name__ == "__main__":
    depuis = sys.argv[1] if len(sys.argv) > 1 else "2024-01"
    for titre, url in fichiers(depuis):
        r = db.execute("select ts from decp_fichiers where f=?", (titre,)).fetchone()
        courant = titre[5:12] == time.strftime("%Y-%m")
        if r and not (courant or time.time() - r[0] > 14 * 86400 and titre[5:12] >= time.strftime("%Y-%m", time.gmtime(time.time() - 90 * 86400))): continue
        try:
            n = ingere(titre, url)
            db.execute("insert or replace into decp_fichiers values(?,?,?)", (titre, time.time(), n)); db.commit()
            print(titre, n, "lignes", file=sys.stderr, flush=True)
        except Exception as e:
            print(titre, "ERREUR", e, file=sys.stderr, flush=True)
