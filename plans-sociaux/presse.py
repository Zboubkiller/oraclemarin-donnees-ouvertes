"""Veille presse : plans sociaux, fermetures et suppressions de postes annoncés dans les médias.
Sans clé API : flux RSS de la presse (mêmes listes que ça brûle) + recherches Google News RSS,
tri par mots-clés, extraction par expressions régulières (nombre d'emplois, commune), dédoublonnage.
Avec GEMINI_API_KEY dans /opt/plans-sociaux/.env : Gemini ne sert qu'à structurer les articles
DÉJÀ retenus par les mots-clés (quelques dizaines par jour, bien sous le quota gratuit)."""
import ast, html, json, os, re, sqlite3, sys, time, unicodedata, urllib.request, urllib.parse
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone

H = os.path.dirname(os.path.abspath(__file__))
UA = {"User-Agent": "Mozilla/5.0 (tracker-plans-sociaux; +https://oraclemarin.fr/plans-sociaux/)"}
db = sqlite3.connect(os.path.join(H, "cache.db"))
db.execute("create table if not exists presse(id text primary key, js text, ts real)")
ENV = dict(l.strip().split("=", 1) for l in open(os.path.join(H, ".env")) if "=" in l) if os.path.exists(os.path.join(H, ".env")) else {}

def norm(s): return unicodedata.normalize("NFD", s or "").encode("ascii", "ignore").decode().lower()

# --- flux : on réutilise les listes de ça brûle sans lancer son serveur
def flux():
    src = open("/opt/ca-brule/app.py", encoding="utf-8").read()
    env = {}
    for node in ast.parse(src).body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", "") in ("ICI_STATIONS", "FEEDS", "FEED_NAMES", "NEW_FEEDS") for t in node.targets):
            try: exec(compile(ast.Module([node], []), "app", "exec"), env)
            except Exception: pass
    out = {u: env.get("FEED_NAMES", {}).get(urllib.parse.urlparse(u).netloc, urllib.parse.urlparse(u).netloc) for u in env.get("FEEDS", [])}
    out.update(env.get("NEW_FEEDS", {}))
    try:
        for f in json.load(open("/opt/ca-brule/cppap_feeds.json")): out.setdefault(f["feed"], f["nom"])
    except Exception: pass
    return out

GOOGLE = ['"plan social"', '"plan de sauvegarde de l\'emploi"', '"suppressions de postes"', '"suppression de postes"',
          '"fermeture de l\'usine"', '"fermeture du site" salariés', '"licenciements" salariés usine',
          '"départs volontaires" salariés', '"ruptures conventionnelles collectives"', '"liquidation judiciaire" salariés']

# presse régionale : mêmes signaux, par région (Bing renvoie surtout la presse nationale sans précision géographique)
REGIONS = ["Bretagne", "Normandie", "Hauts-de-France", "Grand Est", "Bourgogne-Franche-Comté", "Centre-Val de Loire", "Pays de la Loire",
           "Nouvelle-Aquitaine", "Occitanie", "Auvergne-Rhône-Alpes", "Provence-Alpes-Côte d'Azur", "Île-de-France", "Corse", "Guadeloupe Martinique Guyane Réunion"]
GOOGLE += [f'"plan social" {r}' for r in REGIONS] + [f'"suppressions de postes" {r}' for r in REGIONS] + [f'"fermeture" usine salariés {r}' for r in REGIONS]

def items(url):
    try:
        x = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=25).read()
        for it in ET.fromstring(x).iter("item"):
            yield it
    except Exception:
        return

def ts_of(v):
    try: return parsedate_to_datetime(v).timestamp()
    except Exception:
        try: return datetime.fromisoformat((v or "").strip().replace("Z", "+00:00")).timestamp()
        except Exception: return None

# --- tri par score (pas d'IA) : il faut un signal fort dans le TITRE + un signal « entreprise / emploi »
FORT = re.compile(r"plan social|plans sociaux|\bpse\b|sauvegarde de l.emploi|suppressions? d[e']\s*(?:\d[\d\s.]*\s*)?(?:postes|emplois)"
                  r"|(?:postes|emplois) (?:supprimes|menaces)|supprim\w* (?:pres de |plus de |environ )?\d[\d\s.]*\s*(?:postes|emplois)|licenciements?|licencie(?:s|es)? \d|fermeture (?:de l.|d.une |du |de la |des )?(?:usine|site|magasin|entrepot|agence|entreprise|atelier|fonderie|abattoir|imprimerie)"
                  r"|ferme (?:ses|son|sa) |cesse (?:son|ses) activite|liquidation judiciaire|redressement judiciaire|placee? en (?:liquidation|redressement)"
                  r"|departs volontaires|ruptures? conventionnelles? collectives?|reclassement|\brepreneur|menaces? (?:de fermeture|sur l.emploi)|deloc")
EMPLOI = re.compile(r"\bpostes\b|salarie|ouvrier|employe|emplois?|postes?|usine|site|entreprise|societe|groupe|syndicat|cgt|cfdt|intersyndicale|direction|greve|debrayage|tribunal de commerce|reprise|repreneur")
REJET = re.compile(r"entraineur|coach|selectionneur|joueur|footbal|basket|rugby|handball|\bclub\b|ligue 1|ligue 2|mercato|licencie pour faute|horoscope"
                   r"|belgique|bruxell|wallon|suisse|geneve|quebec|canada|allemagne|etats-unis|\bus\b|royaume-uni|espagne|italie|chine"
                   r"|reforme|gouvernement|budget de l.etat|ministre de|assemblee nationale|senat|macronie|festival|climat"
                   r"|lyce|etudiant|mobilisation|manifest|recrut|cree \d|creer|s.installe|entrepreneu|entreprendre|salon |concert|deces|election|saint-john|memorial")
NB = re.compile(r"(\d{1,3}(?:[\s\u202f.]\d{3})+|\d+)\s*(?:postes|emplois|salariés|salaries|licenciements|personnes|CDI|suppressions)", re.I)
ENT = [re.compile(p) for p in (
    r"^([A-Z0-9][\w&'’.\- ]{1,40}?)\s*:",                                   # « Michelin : ... »
    r"\b(?:salariés|ouvriers|CGT|CFDT|FO|syndicats?|direction)\s+(?:de|du groupe|de l'usine|d')\s*([A-Z][\w&'.\-]+(?:\s+[A-Z][\w&'.\-]+){0,3})",
    r"\b(?:saxophoniste|verrier|papetier|fondeur|sous-traitant|imprimeur|volailler|abattoir|chausseur|constructeur|distributeur|spécialiste)\s+([A-Z][\w&'.\-]+(?:\s+[A-Z][\w&'.\-]+){0,2})",
    r"\b(?i:chez|de l'usine|l'usine|le groupe|l'entreprise|la société|du groupe|de l'entreprise|de la société|le fabricant|l'équipementier|l'enseigne)\s+([A-Z][\w&'’.\-]+(?:\s+[A-Z][\w&'’.\-]+){0,3})",
)]

def score(titre, desc):
    t, d = norm(titre), norm(desc)
    if REJET.search(t): return 0
    s = 0
    if FORT.search(t): s += 2
    elif FORT.search(d): s += 1
    if EMPLOI.search(t + " " + d): s += 1
    if NB.search(titre + " " + desc): s += 1
    return s

def entreprise(titre):
    titre = titre.replace("’", "'")
    for r in ENT:
        m = r.search(titre)
        if m:
            e = m.group(1).strip(" -'’")
            if 2 <= len(e) <= 40 and norm(e) not in COM and e.lower() not in ("video", "info", "direct", "temoignage", "carte", "pourquoi", "exclusif"):
                return e
    return None

def communes():
    try: c = json.load(open("/opt/ca-brule/communes.json"))
    except Exception: return {}
    return {norm(x["nom"]): x for x in sorted(c, key=lambda x: x.get("population") or 0) if x.get("population", 0) >= 3000 and len(x["nom"]) > 3}   # homonymes : la plus peuplée
COM = communes()
try: COM_ALL = {norm(x["nom"]): x for x in sorted(json.load(open("/opt/ca-brule/communes.json")), key=lambda x: x.get("population") or 0)}   # toutes tailles, pour les communes citées par Gemini
except Exception: COM_ALL = COM
COM_RE = re.compile(r"\b(" + "|".join(sorted(map(re.escape, COM), key=len, reverse=True)) + r")\b") if COM else None

def regex_extract(titre, desc):
    t = norm(titre + " " + desc)
    nbs = [int(re.sub(r"\D", "", m.group(1))) for m in NB.finditer(titre + " " + desc)]
    nbs = [n for n in nbs if 5 <= n <= 50000]
    c = None
    if COM_RE:
        m = COM_RE.search(norm(titre)) or COM_RE.search(t)
        if m: c = COM[m.group(1)]
    typ = ("liquidation" if "liquidation" in t else "redressement" if "redressement" in t else
           "fermeture" if "fermeture" in t else "plan social")
    return {"emplois": max(nbs) if nbs else None, "commune": c["nom"] if c else None, "dep": c["codeDepartement"] if c else None,
            "lat": c["centre"]["coordinates"][1] if c else None, "lon": c["centre"]["coordinates"][0] if c else None, "type": typ}

def gemini(arts):
    key = ENV.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not key or not arts: return {}
    prompt = ("Pour chaque article (titre + chapô) ci-dessous, réponds en JSON : liste d'objets {i, pertinent (bool : annonce "
              "de suppressions d'emplois, plan social, fermeture de site ou procédure collective d'une entreprise en France), "
              "entreprise, commune, emplois (nombre d'emplois supprimés ou menacés, null si absent), type (plan social|fermeture|"
              "liquidation|redressement|départs volontaires)}. N'invente rien : null si l'info n'est pas dans le texte.\n\n" +
              "\n".join(f"[{i}] {a['titre']} — {a['desc'][:300]}" for i, a in enumerate(arts)))
    body = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"responseMimeType": "application/json", "temperature": 0}}
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-lite-latest:generateContent?key=" + key
    try:
        r = json.load(urllib.request.urlopen(urllib.request.Request(url, json.dumps(body).encode(), {"Content-Type": "application/json"}), timeout=90))
        u = r.get("usageMetadata", {})
        with open(os.path.join(H, "gemini_usage.log"), "a") as f:   # suivi de la consommation
            f.write(f"{datetime.now().isoformat(timespec='minutes')} articles={len(arts)} in={u.get('promptTokenCount')} out={u.get('candidatesTokenCount')}\n")
        return {int(x["i"]): x for x in json.loads(r["candidates"][0]["content"]["parts"][0]["text"])}
    except Exception as e:
        print("gemini:", e, file=sys.stderr); return {}

def run():
    now = time.time(); vus, arts = set(), []
    sources = [(u, n) for u, n in flux().items()]
    # Google News bloque l'IP du serveur (captcha) : recherches via Bing News RSS
    sources += [("https://www.bing.com/news/search?" + urllib.parse.urlencode({"q": q, "format": "rss", "setmkt": "fr-FR", "qft": 'interval="7"'}), None) for q in GOOGLE]
    for url, nom in sources:
        for it in items(url):
            titre = html.unescape((it.findtext("title") or "").strip()); lien = it.findtext("link") or ""
            if not nom and "bing.com" in lien:
                lien = urllib.parse.parse_qs(urllib.parse.urlparse(lien).query).get("url", [lien])[0]
            src = nom or urllib.parse.urlparse(lien).netloc.replace("www.", "")
            desc = re.sub(r"<[^>]+>", " ", html.unescape(it.findtext("description") or ""))[:600]
            ts = ts_of(it.findtext("pubDate"))
            if not ts or now - ts > 3 * 86400 or ts > now + 3600: continue
            n = norm(titre + " " + desc)
            sc = score(titre, desc)
            if sc < 2: continue
            cle = re.sub(r"\W+", "", norm(titre))[:80]
            if cle in vus or db.execute("select 1 from presse where id=?", (cle,)).fetchone(): continue
            vus.add(cle); arts.append({"cle": cle, "titre": titre, "desc": desc.strip(), "url": lien, "source": src, "ts": ts, "score": sc})
        time.sleep(0.3)
    traiter(arts, len(sources))

def traiter(arts, n_sources=0):
    """Structuration (Gemini, sinon regex) et enregistrement des articles retenus par les mots-clés."""
    g = {}
    for k in range(0, len(arts), 60):                     # plafond : 60 articles par appel
        g.update({i + k: v for i, v in gemini(arts[k:k + 60]).items()})
    n_ok = 0
    for i, a in enumerate(arts):
        x = regex_extract(a["titre"], a["desc"])
        gi = g.get(i)
        if gi is not None:
            if not gi.get("pertinent"): continue
            try: x["emplois"] = int(float(str(gi.get("emplois")).replace(" ", "").replace(" ", ""))) or x["emplois"]
            except (TypeError, ValueError): pass
            if gi.get("type"): x["type"] = gi["type"]
            if gi.get("commune") and norm(gi["commune"]) in COM_ALL:
                c = COM_ALL[norm(gi["commune"])]; x.update(commune=c["nom"], dep=c["codeDepartement"], lat=c["centre"]["coordinates"][1], lon=c["centre"]["coordinates"][0])
        ev = {"id": "presse-" + a["cle"][:40], "source": a["source"], "type": x["type"],
              "entreprise": (gi or {}).get("entreprise") or entreprise(a["titre"]) or a["titre"], "titre": a["titre"], "score": a["score"],
              "commune": x["commune"], "dep": x["dep"], "lat": x["lat"], "lon": x["lon"], "approx": True,
              "emplois_min": x["emplois"], "emplois_max": x["emplois"], "emplois_precision": "annoncé" if x["emplois"] else None,
              "date": datetime.fromtimestamp(a["ts"], timezone.utc).date().isoformat(), "detail": a["titre"],
              "url": a["url"], "statut": None,
              "extraction": "gemini" if gi else ("regex" if a["score"] >= 3 else "regex-faible")}
        db.execute("replace into presse values(?,?,?)", (a["cle"], json.dumps(ev, ensure_ascii=False), a["ts"])); n_ok += 1
    db.commit()
    print(f"presse : {n_sources} flux, {len(arts)} articles retenus par mots-clés, {n_ok} enregistrés", file=sys.stderr)

def rattrapage(chemin):
    """Articles plus anciens (fichier JSON : titre, desc, url, source, ts), par exemple Google Actualités par semaine."""
    vus, arts = set(), []
    for a in json.load(open(chemin, encoding="utf-8")):
        titre, desc = a["titre"], a.get("desc") or ""
        if norm(desc).startswith(norm(titre)[:40]): desc = ""        # Google répète le titre dans la description
        sc = score(titre, desc)
        if sc < 2: continue
        cle = re.sub(r"\W+", "", norm(titre))[:80]
        if cle in vus or db.execute("select 1 from presse where id=?", (cle,)).fetchone(): continue
        vus.add(cle); arts.append({"cle": cle, "titre": titre, "desc": desc, "url": a["url"], "source": a.get("source") or "", "ts": a["ts"], "score": sc})
    print(f"rattrapage : {len(arts)} articles retenus par mots-clés", file=sys.stderr)
    for k in range(0, len(arts), 120):
        traiter(arts[k:k + 120]); time.sleep(3)

if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "rattrapage": rattrapage(sys.argv[2])
    else: run()
