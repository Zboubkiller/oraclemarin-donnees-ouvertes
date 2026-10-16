"""Groupe d'appartenance des entreprises (société mère ultime), trois sources par ordre de priorité :
1. groupes_manuels.json : liens vérifiés à la main, avec leur source (prioritaires) ;
2. GLEIF (registre mondial des LEI, licence CC0) : société mère directe et ultime, quand l'entité la déclare ;
3. Wikidata : propriété « organisation mère » (P749) uniquement, pas « propriétaire » (P127, qui mélange les actionnaires).
Écrit e["groupe"] = {nom, pays, source, url}. Produit aussi groupes_a_completer.csv : grandes entreprises et ETI sans groupe connu."""
import re
import csv, json, os, sqlite3, sys, time, urllib.parse, urllib.request
H = os.path.dirname(os.path.abspath(__file__))
db = sqlite3.connect(os.path.join(H, "cache.db"), timeout=120)
db.execute("create table if not exists groupes(siren text primary key, js text, ts real)")
UA = "tracker-plans-sociaux/0.8 (https://oraclemarin.fr/plans-sociaux/; quentinclosset@gmail.com)"
GLEIF = "https://api.gleif.org/api/v1/"

def get(u, data=None, accept="application/json"):
    for i in range(3):
        try: return json.load(urllib.request.urlopen(urllib.request.Request(u, data, {"User-Agent": UA, "Accept": accept}), timeout=60))
        except urllib.error.HTTPError as e:
            if e.code == 404: return {}
            time.sleep(3 + 3 * i)
        except Exception: time.sleep(3 + 3 * i)
    return None

def gleif(siren):
    r = get(GLEIF + "lei-records?" + urllib.parse.urlencode({"filter[entity.registeredAs]": siren, "page[size]": 1}), accept="application/vnd.api+json")
    if r is None: return None
    d = r.get("data") or []
    if not d: return {}
    lei = d[0]["id"]; out = {"lei": lei}
    for rel in ("ultimate-parent", "direct-parent"):
        p = get(GLEIF + f"lei-records/{lei}/{rel}", accept="application/vnd.api+json")
        if p and isinstance(p.get("data"), dict):
            ent = p["data"]["attributes"]["entity"]
            out[rel] = {"nom": ent["legalName"]["name"], "pays": ent.get("legalAddress", {}).get("country"), "lei": p["data"]["id"]}
        time.sleep(0.2)
    return out

def wikidata(sirens):
    """{siren: {nom, ultime, pays}} en une requête SPARQL ; chaîne P749 jusqu'au sommet."""
    vals = " ".join(f'"{s}"' for s in sirens)
    q = f"""SELECT ?siren ?parentLabel ?ultLabel ?paysCode WHERE {{ VALUES ?siren {{ {vals} }} ?item wdt:P1616 ?siren . ?item p:P749 ?st . ?st ps:P749 ?parent . FILTER NOT EXISTS {{ ?st pq:P582 ?fin }} FILTER NOT EXISTS {{ ?parent wdt:P576 ?dissous }}
      OPTIONAL {{ ?item wdt:P749+ ?ult . FILTER NOT EXISTS {{ ?ult wdt:P749 ?y }} OPTIONAL {{ ?ult wdt:P17 ?pays . ?pays wdt:P297 ?paysCode }} }}
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "fr,en". }} }}"""
    r = get("https://query.wikidata.org/sparql", urllib.parse.urlencode({"query": q, "format": "json"}).encode(), "application/sparql-results+json")
    out = {}
    for x in (r or {}).get("results", {}).get("bindings", []):
        s = x["siren"]["value"]; o = out.setdefault(s, {"parents": set(), "ultimes": set(), "pays": set()})
        o["parents"].add(x["parentLabel"]["value"])
        if "ultLabel" in x: o["ultimes"].add(x["ultLabel"]["value"])
        if "paysCode" in x: o["pays"].add(x["paysCode"]["value"])
    return out

def manuels():
    try: return json.load(open(os.path.join(H, "groupes_manuels.json"), encoding="utf-8")).get("groupes", {})
    except Exception: return {}

def remplir_cache(sirens):
    a_faire = [s for s in sorted(set(sirens)) if not (lambda r: r and time.time() - r[0] < 30 * 86400)(db.execute("select ts from groupes where siren=?", (s,)).fetchone())]
    wd = wikidata(a_faire) if a_faire else {}
    for s in a_faire:
        g = gleif(s)
        if g is None: continue
        w = wd.get(s)
        db.execute("replace into groupes values(?,?,?)", (s, json.dumps({"gleif": g, "wikidata": {k: sorted(v) for k, v in w.items()} if w else None}, ensure_ascii=False), time.time()))
        db.commit(); time.sleep(0.2)

try:
    REFUS_GROUPE = {x["siren"] for x in json.load(open(os.path.join(H, "rapprochements.json"), encoding="utf-8")).get("groupes_refus", [])}
except Exception:
    REFUS_GROUPE = set()

def groupe_de(s, man=None):
    """Groupe d'une unité légale (SIREN) : vérifié à la main > GLEIF > Wikidata (sommet unique), sinon None."""
    man = manuels() if man is None else man
    if s in REFUS_GROUPE: return None
    if s in man:
        m = man[s]; return {"nom": m["groupe"], "pays": m.get("pays"), "source": "vérifié", "url": m.get("source")}
    r = db.execute("select js from groupes where siren=?", (s,)).fetchone()
    if not r: return None
    c = json.loads(r[0]); g = c.get("gleif") or {}; w = c.get("wikidata")
    fonds = lambda x: x and re.search(r"(?i)pension|trust|fund|retirement|benefit|fonds de|employee", x.get("nom") or "")
    up = next((x for x in (g.get("ultimate-parent"), g.get("direct-parent")) if x and not fonds(x)), None)   # GLEIF renvoie parfois un fonds de pension
    if up: return {"nom": up["nom"], "pays": up.get("pays"), "source": "GLEIF", "url": f"https://search.gleif.org/#/record/{up['lei']}"}
    ult = (w or {}).get("ultimes") or (w or {}).get("parents") or []
    if len(ult) == 1:                 # plusieurs sommets possibles : ambigu, on ne publie pas ; pays Wikidata peu fiable, non repris
        return {"nom": ult[0], "pays": None, "source": "Wikidata", "url": "https://www.wikidata.org/w/index.php?search=" + urllib.parse.quote(s)}
    return None

def enrichir(evs):
    man = manuels()
    remplir_cache(e["siren"] for e in evs if e.get("siren"))
    for e in evs:
        if e.get("siren"):
            g = groupe_de(e["siren"], man)
            if g: e["groupe"] = g
    # à compléter à la main : grandes entreprises et ETI citées dans un plan, sans groupe connu
    vus, lignes = set(), []
    for e in evs:
        if e.get("siren") and not e.get("groupe") and e.get("categorie") in ("GE", "ETI") and e["siren"] not in vus:
            vus.add(e["siren"]); lignes.append([e["siren"], e.get("entreprise"), e.get("categorie"), e.get("naf"), e.get("source"), "", "", ""])
    with open(os.path.join(H, "groupes_a_completer.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f); w.writerow(["siren", "nom_cite", "categorie", "naf", "source", "groupe", "pays", "source_du_lien"]); w.writerows(lignes)
    print("groupes :", sum(1 for e in evs if e.get("groupe")), "événements avec groupe ;", len(lignes), "entreprises à compléter", file=sys.stderr)
    return evs
