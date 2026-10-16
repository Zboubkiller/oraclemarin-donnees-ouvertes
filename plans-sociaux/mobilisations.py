"""Croisement avec ça brûle (oraclemarin.fr/cabrule/) : mobilisations (grèves, rassemblements, débrayages) et décès au travail
signalés par la presse sur le site d'une entreprise du tracker. Lecture seule des données de ça brûle.
Règle : le nom complet de l'entreprise (sans forme juridique) doit figurer dans le titre de l'article ; l'article doit être
classé « travail » par ça brûle, daté de 30 jours avant à un an après l'annonce, et dans le même département quand les deux
sont connus. Les données de ça brûle ne sont conservées que depuis le 30 septembre 2026."""
import json, re, sqlite3, sys, unicodedata, datetime as dt
CB = "/opt/ca-brule"
FORMES = r"(?:sa|sas|sasu|sarl|scop|snc|eurl|se|groupe|group|ste|societe|etablissements?|ets|france|holding)"
# noms qui sont aussi des mots courants ou des médias : trop de faux positifs dans les titres
GENERIQUES = {"le point", "le parisien", "la provence", "nature et decouvertes", "solutions", "general electric", "sncf", "la poste",
              "orange", "total", "casino", "metro", "cours galien", "centrale de cordemais", "des marques et vous", "generale", "general"}
PUBLICS = ("conseil ", "ville ", "metropole ", "hopital ", "commune ", "protection judiciaire", "secours ", "association ", "finances publiques")

def norm(s): return unicodedata.normalize("NFD", s or "").encode("ascii", "ignore").decode().lower()

def nom_propre(nom):
    n = norm(re.split(r"[/(]", nom or "")[0])
    n = re.sub(r"[^a-z0-9&' -]", " ", n)
    n = re.sub(r"\s+", " ", n).strip()
    n = re.sub(r"^(?:%s )+" % FORMES, "", n)
    n = re.sub(r"(?: %s)+$" % FORMES, "", n)
    return n.strip()

def motif(nom):
    n = nom_propre(nom)
    if len(n.replace(" ", "")) < 5 or (" " not in n and len(n) < 6) or n in GENERIQUES or n.startswith(PUBLICS): return None
    # pas de trait d'union autour : « Saint-André » n'est pas l'entreprise André
    return re.compile(r"(?<![a-z0-9-])" + r"[\s-]+".join(map(re.escape, n.split())) + r"(?![a-z0-9-])")

def articles():
    db = sqlite3.connect(f"file:{CB}/history.db?mode=ro", uri=True, timeout=30)
    vus, out = set(), []
    for day, title, src, link, nom, dep, themes in db.execute("select day, title, src, link, nom, dep, themes from articles where themes like '%travail%'"):
        k = norm(title)[:90]
        if k in vus: continue
        vus.add(k); out.append({"date": day, "titre": title, "source": src, "url": link, "commune": nom, "dep": dep})
    return out

def deces():
    try: it = json.load(open(f"{CB}/travail.json", encoding="utf-8"))["items"]
    except Exception: return []
    return [{"date": dt.datetime.fromtimestamp(x["ts"], dt.timezone.utc).date().isoformat() if x.get("ts") else None, "texte": x.get("text"),
             "url": x.get("url"), "commune": x.get("place"), "dep": x.get("dep")} for x in it]

def enrichir(evs):
    A, D = articles(), deces()
    n_m = n_d = 0
    for e in evs:
        e.pop("mobilisations", None); e.pop("deces_travail", None)
        if e.get("sans_entreprise") or not e.get("entreprise") or e.get("entreprise") == e.get("titre") or not e.get("date"): continue
        rx = motif(e["entreprise"])
        if not rx: continue
        dep = e.get("dep")
        j = dt.date.fromisoformat(e["date"][:10]); lo, hi = (j - dt.timedelta(days=30)).isoformat(), (j + dt.timedelta(days=365)).isoformat()
        m = [a for a in A if lo <= a["date"] <= hi and rx.search(norm(a["titre"])) and (not dep or not a["dep"] or a["dep"] == dep)]
        if m: e["mobilisations"] = sorted(m, key=lambda a: a["date"])[:6]; n_m += 1
        d = [x for x in D if x["texte"] and x["date"] and lo <= x["date"] <= hi and rx.search(norm(x["texte"])) and (not dep or not x["dep"] or x["dep"] == dep)]
        if d: e["deces_travail"] = d[:3]; n_d += 1
    print(f"ça brûle : {n_m} événements avec mobilisation, {n_d} avec décès au travail ({len(A)} articles « travail », {len(D)} décès)", file=sys.stderr)
