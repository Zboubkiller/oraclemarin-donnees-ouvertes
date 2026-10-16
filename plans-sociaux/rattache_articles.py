"""Cherche, pour chaque entreprise de la base sans article de presse, des articles qui en parlent (Google Actualités RSS).
Ne rattache RIEN tout seul : écrit articles_candidats.json (niveau A = très probable, B = à vérifier), relu avant tout usage.
Reprend là où il s'est arrêté (cache 21 jours dans cache.db). Usage : rattache_articles.py [--limite N] [--test NOM]"""
import json, os, re, sqlite3, sys, time, unicodedata, urllib.parse, urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
import datetime as dt
H = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, H)
import auto_ident as AI, cgt_stats
UA = {"User-Agent": "Mozilla/5.0 (tracker-plans-sociaux; +https://oraclemarin.fr/plans-sociaux/)"}
OUT = os.path.join(H, "articles_candidats.json")
C = sqlite3.connect(os.path.join(H, "cache.db")); C.execute("create table if not exists presse_cible(k text primary key, js text, ts real)")
MOTS = re.compile(r"licenci|plan social|\bpse\b|ferm|liquidation|redressement|suppression|sauvegarde|cessation|plan de depart|rupture conventionnelle collective|\brcc\b", re.I)
REQ = '(licenciements OR "plan social" OR PSE OR fermeture OR liquidation OR redressement OR "suppressions de postes")'

def cibles(E):
    out = []
    for e in E:
        n = (e.get("entreprise") or "").strip()
        if not n or e.get("employeur_public_nom") or cgt_stats.src_indep(e): continue
        if e.get("source") not in ("BODACC", "CGT (liste noire)", "Accords d'entreprise") and not str(e.get("source", "")).startswith("CGT"): continue
        if not AI.toks(n): continue
        out.append(e)
    return out

def chercher(nom):
    k = AI.norm(nom); r = C.execute("select js, ts from presse_cible where k=?", (k,)).fetchone()
    if r and time.time() - r[1] < 21 * 86400: return json.loads(r[0])
    u = "https://news.google.com/rss/search?" + urllib.parse.urlencode({"q": f'"{nom}" {REQ}', "hl": "fr", "gl": "FR", "ceid": "FR:fr"})
    d = urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=25).read()
    items = []
    for it in ET.fromstring(d).iter("item"):
        try: dtp = parsedate_to_datetime(it.findtext("pubDate")).date().isoformat()
        except Exception: dtp = None
        src = it.find("source")
        items.append({"titre": it.findtext("title") or "", "url": it.findtext("link"), "date": dtp, "source": (src.text if src is not None else "")})
    C.execute("replace into presse_cible values(?,?,?)", (k, json.dumps(items, ensure_ascii=False), time.time())); C.commit()
    time.sleep(1.3)
    return items

def classer(e, items):
    T = AI.toks(e["entreprise"]); com = AI.norm(e.get("commune") or "")
    ed = None
    try: ed = dt.date.fromisoformat((e.get("date") or "")[:10])
    except Exception: pass
    res = []
    for a in items:
        titre = re.sub(r"\s+-\s+[^-]+$", "", a["titre"]); tn = set(AI.norm(titre).split())
        if not MOTS.search(AI.norm(titre)): continue
        nom_ok = all(t in tn for t in T)
        if not nom_ok:
            # nom absent du titre : retenu seulement si le titre donne le même nombre d'emplois que la ligne, à une date voisine (niveau B, à relire)
            n = e.get("emplois_min")
            if not (n and ed and a["date"] and re.search(r"(?<![\d,.])" + str(int(n)) + r"(?![\d])", titre)): continue
            delta = (dt.date.fromisoformat(a["date"]) - ed).days
            if -45 <= delta <= 270: res.append({**a, "niveau": "B", "nom_absent": True})
            continue
        niveau = "B"
        if ed and a["date"]:
            delta = (dt.date.fromisoformat(a["date"]) - ed).days
            if not -120 <= delta <= 400: continue
            if -45 <= delta <= 120 and (len(T) >= 2 or max(map(len, T)) >= 7 or (com and com in AI.norm(titre))): niveau = "A"
        res.append({**a, "niveau": niveau})
    return res

def main():
    E = json.load(open(os.path.join(H, "public", "data.json"), encoding="utf-8"))["evenements"]
    L = cibles(E)
    if "--test" in sys.argv:
        nom = sys.argv[sys.argv.index("--test") + 1]; L = [e for e in L if nom.lower() in e["entreprise"].lower()]
    if "--limite" in sys.argv: L = L[:int(sys.argv[sys.argv.index("--limite") + 1])]
    R = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {}
    echecs = 0
    for i, e in enumerate(L):
        try: items = chercher(e["entreprise"]); echecs = 0
        except Exception as ex:
            echecs += 1; print("échec", e["entreprise"], ex, file=sys.stderr)
            if echecs >= 5: print("trop d'échecs : arrêt (relancer plus tard, le cache est conservé)", file=sys.stderr); break
            time.sleep(30 * echecs); continue
        r = classer(e, items)
        if r: R[e["id"]] = {"entreprise": e["entreprise"], "siren": e.get("siren"), "source": e.get("source"), "emplois": e.get("emplois_min"), "date": e.get("date"), "articles": r}
        else: R.pop(e["id"], None)
        if i % 40 == 0:
            json.dump(R, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1); print(f"{i}/{len(L)} · {len(R)} avec article", file=sys.stderr)
    json.dump(R, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    n = {"A": 0, "B": 0}
    for v in R.values(): n[min(a["niveau"] for a in v["articles"])] += 1
    print(f"fini : {len(L)} entreprises interrogées, {len(R)} avec au moins un article (A : {n['A']}, B seulement : {n['B']})", file=sys.stderr)

if __name__ == "__main__": main()
