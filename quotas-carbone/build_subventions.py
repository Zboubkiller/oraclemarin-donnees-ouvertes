#!/usr/bin/env python3
"""Subventions des collectivités : jeux ouverts de conventions de subvention (data.gouv.fr, schéma des « données essentielles »),
aides régionales aux entreprises. Rapprochées par SIREN (les 9 premiers chiffres du SIRET du bénéficiaire) avec les sociétés de la base.
Sortie : subventions_locales_auto.json {siren: [{financeur, jeu, url, nom, date, montant, objet}, ...]}, lu par pages_fiche.py.
Couverture partielle : seules les collectivités qui publient leurs conventions ; montants attribués, pas forcément versés.
À relancer environ une fois par semaine (cron)."""
import csv, io, json, os, re, sys, time, urllib.parse, urllib.request
H = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(H, "subventions_locales_auto.json")
EV = json.load(open(os.path.join(H, "public/data.json"), encoding="utf-8"))["evenements"]
SIR = {e["siren"] for e in EV if e.get("siren")}
UA = {"User-Agent": "tracker-plans-sociaux/0.9 (https://oraclemarin.fr/plans-sociaux/; quentinclosset@gmail.com)"}
API = "https://www.data.gouv.fr/api/1/datasets/?"
def get(u, raw=False, timeout=60):
    for _ in range(3):
        try:
            b = urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=timeout).read()
            return b if raw else json.loads(b)
        except Exception: time.sleep(2)
    return None
QUERIES = ["conventions de subvention", "subventions", "aides aux entreprises région", "aides financières entreprises", "subventions aux entreprises", "aides économiques collectivité",
           "subventions attribuées", "subventions versées", "conventions de subventions attribuées", "aides aux entreprises", "soutien aux entreprises", "fonds de solidarité entreprises",
           "projets implantation reporting", "aides covid entreprises région", "aides économiques département", "subventions métropole", "subventions communauté d'agglomération",
           "subventions communauté de communes", "aides directes aux entreprises", "développement économique aides attribuées", "dispositifs d'aide économique bénéficiaires",
           "Occitanie aides entreprises", "Hauts-de-France aides entreprises", "Grand Est aides entreprises", "Nouvelle-Aquitaine aides entreprises",
           "Auvergne-Rhône-Alpes aides entreprises", "Sud Provence-Alpes-Côte d'Azur aides entreprises", "Pays de la Loire aides entreprises", "Bourgogne-Franche-Comté aides entreprises",
           "Corse aides entreprises", "Normandie aides entreprises", "Centre-Val de Loire aides entreprises", "Bretagne aides entreprises", "Île-de-France aides entreprises"]
TAGS = ["subventions", "scdl", "conventions-de-subvention", "subvention", "aides-aux-entreprises", "aides-economiques", "donnees-essentielles"]
datasets = {}
def collecte(params):
    for page in range(1, 7):
        d = get(API + urllib.parse.urlencode(dict(params, page_size=100, page=page)))
        if not d: break
        for x in d.get("data", []): datasets[x["id"]] = x
        if len(d.get("data", [])) < 100: break
for q in QUERIES: collecte({"q": q})
for t in TAGS: collecte({"tag": t})
print(len(datasets), "jeux candidats", flush=True)
RE_ID = re.compile(r"(siret|siren|idbenef|id_benef|identifiant.*benef|beneficiaire.*(id|siret|siren))", re.I)
def fix(x):
    """Texte lu en UTF-8 puis réencodé en Latin-1 par certaines collectivités (« mobilitÃ© ») : on le remet d'aplomb."""
    x = x or ""
    if "Ã" in x or "â€" in x:
        try: return x.encode("cp1252").decode("utf-8")
        except Exception:
            try: return x.encode("latin-1").decode("utf-8")
            except Exception: return x
    return x
def num(x):
    try: return float(str(x).replace(" ", "").replace("\xa0", "").replace(",", "."))
    except Exception: return 0.0
def datefr(x):
    x = str(x or "").strip()
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", x)
    if m: return m.group(0)
    m = re.match(r"(\d{2})/(\d{2})/(\d{4})", x)
    if m: return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    m = re.match(r"(\d{4})$", x)
    return x if m else ""
res, vus, n_jeux = {}, set(), 0
for ds in datasets.values():
    titre = ds["title"]
    if not re.search(r"subvention|aide|soutien|fonds|dispositif|implantation|financement|convention", titre, re.I): continue
    for r in ds.get("resources", []):
        if (r.get("format") or "").lower() not in ("csv", "") and not (r.get("url") or "").lower().endswith(".csv"): continue
        if (r.get("filesize") or 0) > 60_000_000: continue
        b = get(r["url"], raw=True, timeout=90)
        if not b: continue
        txt = b.decode("utf-8-sig", "replace")
        try: dialect = csv.Sniffer().sniff(txt[:4000], delimiters=";,\t")
        except Exception: dialect = csv.excel
        try:
            rd = csv.DictReader(io.StringIO(txt, newline=""), dialect=dialect); cols = rd.fieldnames or []
        except Exception: continue
        idc = [c for c in cols if RE_ID.search(c or "")]
        nomc = [c for c in cols if re.search(r"nom.*benef|benef.*nom|raison|denomination", c or "", re.I)]
        montc = [c for c in cols if re.search(r"montant|somme", c or "", re.I)]
        datec = [c for c in cols if re.search(r"date", c or "", re.I)]
        objc = [c for c in cols if re.search(r"objet|nature|libell", c or "", re.I)]
        orga = (ds.get("organization") or {}).get("name") or ""
        n_jeux += 1
        try:
            for row in rd:
                for c in idc:
                    v = re.sub(r"\D", "", row.get(c) or "")
                    if len(v) >= 9 and v[:9] in SIR:
                        sir = v[:9]
                        l = {"financeur": orga, "jeu": titre, "url": "https://www.data.gouv.fr/datasets/" + ds["id"],
                             "nom": fix(row.get(nomc[0]) or "")[:80] if nomc else "", "montant": round(num(row.get(montc[0]))) if montc else 0,
                             "date": datefr(row.get(datec[0])) if datec else "", "objet": re.sub(r"\s+", " ", fix(row.get(objc[0]) or ""))[:200] if objc else ""}
                        k = (sir, l["financeur"], l["date"], l["montant"], l["objet"][:60])
                        if k in vus or l["montant"] <= 0: break
                        vus.add(k); res.setdefault(sir, []).append(l)
                        break
        except Exception: pass
        break   # une ressource CSV par jeu
for sir in res: res[sir].sort(key=lambda l: l["date"], reverse=True)
json.dump({"genere": time.strftime("%Y-%m-%d"), "jeux_lus": n_jeux, "par_siren": res}, open(OUT + ".tmp", "w", encoding="utf-8"), ensure_ascii=False)
os.replace(OUT + ".tmp", OUT)
print(n_jeux, "jeux lus ;", sum(len(v) for v in res.values()), "lignes ;", len(res), "sociétés de la base")
