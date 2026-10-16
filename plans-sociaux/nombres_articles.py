"""Cherche, dans les articles de presse des annonces sans nombre d'emplois, des nombres de postes supprimés (chiffres ou lettres : « 14 postes », « quatorze licenciements »).
Chromium sans interface (Playwright) ouvre chaque lien (les liens Google Actualités passent par une page de consentement, refusée), lit le texte une seule fois, en mémoire :
seuls le nombre trouvé et un extrait de 200 caractères au plus sont conservés (nombres_articles.json). Rien n'est publié ni appliqué : chaque candidat est confirmé à la main (onglet Nombres de la validation).
Cache : table art_nombres de cache.db (30 jours). Usage : nombres_articles.py [--limite N]"""
import json, os, re, sqlite3, sys, time, urllib.parse
H = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(H, "nombres_articles.json")
C = sqlite3.connect(os.path.join(H, "cache.db"), timeout=120); C.execute("create table if not exists art_nombres(id text primary key, js text, ts real)")
UNITES = {"un": 1, "une": 1, "deux": 2, "trois": 3, "quatre": 4, "cinq": 5, "six": 6, "sept": 7, "huit": 8, "neuf": 9, "dix": 10, "onze": 11, "douze": 12, "treize": 13, "quatorze": 14,
          "quinze": 15, "seize": 16, "vingt": 20, "vingts": 20, "trente": 30, "quarante": 40, "cinquante": 50, "soixante": 60}
MOT = r"(?:quatre[- ]vingt(?:s|[- ]dix)?|(?:soixante|vingt|trente|quarante|cinquante)(?:[- ](?:et[- ])?(?:un|une|deux|trois|quatre|cinq|six|sept|huit|neuf|dix|onze|douze|treize|quatorze|quinze|seize))?|dix[- ](?:sept|huit|neuf)|onze|douze|treize|quatorze|quinze|seize|dix|neuf|huit|sept|six|cinq|quatre|trois|deux|(?:deux|trois|quatre|cinq|six|sept|huit|neuf)[- ]cents?|cents?|mille)"
NUM = rf"(?:\d{{1,3}}(?:[  .]\d{{3}})+|\d+|{MOT})"
OBJ = r"(?:postes?|emplois?|licenciements?|suppressions?(?: de postes| d.emplois)?|salari[ée]s?|personnes|CDI|ETP|collaborateurs|employ[ée]s)"
P1 = re.compile(rf"(?:supprim|licenci|suppression|r[ée]duct|r[ée]duire|retrait|rupture|dégraiss)\w*[^.;\n]{{0,45}}?\b({NUM})\s+{OBJ}\b", re.I)
P2 = re.compile(rf"\b({NUM})\s+(?:postes?|emplois?)\s+(?:seraient\s+|sont\s+|vont\s+|pourraient\s+)?(?:supprim|menac|concern|en moins|sur la sellette|en danger|disparai)\w*", re.I)
P3 = re.compile(rf"\b({NUM})\s+(?:licenciements?|suppressions? de postes?|suppressions? d.emplois)\b", re.I)
P4 = re.compile(rf"\b({NUM})\s+salari[ée]s?\s+(?:licenci|concern|menac|sur le carreau|touch)\w*", re.I)
PAT = (("suppression + nombre", P1), ("nombre + postes supprimés", P2), ("nombre + licenciements", P3), ("nombre + salariés concernés", P4))

def valeur(s):
    s = s.lower().replace(" ", " ").replace("\xa0", " ").strip()
    if re.fullmatch(r"\d{1,3}(?:[ .]\d{3})+", s): return int(re.sub(r"[ .]", "", s))
    if s.isdigit(): return int(s)
    t = re.split(r"[- ]+", s); tot, cur = 0, 0
    for w in t:
        if w == "et": continue
        if w in UNITES: cur += UNITES[w]
        elif w in ("cent", "cents"): cur = max(cur, 1) * 100
        elif w == "mille": cur = max(cur, 1) * 1000
        elif w == "quatre": cur += 4
        else: return None
    if t[:2] == ["quatre", "vingt"] or t[:2] == ["quatre", "vingts"]: cur = 80 + (cur - 4 - 20 if cur > 24 else 0)
    return cur or None

def candidats(texte):
    out, vus = [], set()
    for motif, rx in PAT:
        for m in rx.finditer(texte):
            n = valeur(m.group(1))
            if n is None or not 2 <= n <= 20000: continue
            if 1990 <= n <= 2035 and not re.search(r"postes|emplois|licenci", m.group(0), re.I): continue
            a, b = max(0, m.start() - 70), min(len(texte), m.end() + 90)
            ctx = re.sub(r"\s+", " ", texte[a:b]).strip()[:200]
            k = (n, ctx[:60])
            if k in vus: continue
            vus.add(k); out.append({"n": n, "contexte": ctx, "motif": motif})
    return out[:8]

def ouvrir(c, url):
    pg = c.new_page(); pg.goto(url, wait_until="domcontentloaded", timeout=20000)
    if "consent.google" in pg.url:
        for lab in ("Tout refuser", "Reject all"):
            b = pg.get_by_role("button", name=lab)
            if b.count(): b.first.click(); break
        pg.wait_for_load_state("domcontentloaded", timeout=25000)
    pg.wait_for_timeout(1500); return pg

def lire(c, url):
    pg = ouvrir(c, url)
    try:
        txt = pg.inner_text("body")[:300000]
        meta = pg.evaluate("() => [...document.querySelectorAll('meta[property=\"og:description\"],meta[name=\"description\"]')].map(m => m.content).join(' ')")
        return pg.url, (meta or "") + "\n" + txt
    finally: pg.close()

def agreger(L):
    R = {}
    for e in L:
        r = C.execute("select js from art_nombres where id=?", (e["id"],)).fetchone()
        if not r: continue
        res = json.loads(r[0])
        if res.get("candidats"): R[e["id"]] = {"entreprise": e["entreprise"], "titre": (e.get("titre") or e.get("detail") or "")[:160], "source": e.get("source"), "date": e.get("date"), "url": e.get("url"),
                                               "site": res.get("site"), "acces": res["acces"], "candidats": res["candidats"]}
    tmp = OUT + ".tmp%d" % os.getpid(); json.dump(R, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1); os.replace(tmp, OUT)
    return R

def main():
    from playwright.sync_api import sync_playwright
    E = json.load(open(os.path.join(H, "public", "data.json"), encoding="utf-8"))["evenements"]
    L = [e for e in E if str(e.get("source")) != "BODACC" and not str(e.get("source")).startswith(("CGT", "Accords", "Sirene")) and not e.get("emplois_min") and e.get("url") and e.get("entreprise")]
    if "--limite" in sys.argv: L = L[:int(sys.argv[sys.argv.index("--limite") + 1])]
    TOUT = L
    if "--part" in sys.argv:
        k, n = map(int, sys.argv[sys.argv.index("--part") + 1].split("/")); L = [e for i, e in enumerate(L) if i % n == k]
    fait = acces = 0
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True, args=["--no-sandbox"])
        c = b.new_context(locale="fr-FR", user_agent="Mozilla/5.0 (compatible; plans-sociaux-verif; +https://oraclemarin.fr/plans-sociaux/)")
        for i, e in enumerate(L):
            r = C.execute("select js, ts from art_nombres where id=?", (e["id"],)).fetchone()
            if r and time.time() - r[1] < 30 * 86400: res = json.loads(r[0])
            else:
                try:
                    url, txt = lire(c, e["url"]); cand = candidats(txt)
                    res = {"acces": "ok" if len(txt) > 1500 else "partiel", "site": urllib.parse.urlparse(url).netloc, "url_finale": url, "candidats": cand}
                except Exception as ex:
                    res = {"acces": "erreur", "erreur": str(ex)[:80], "candidats": []}
                C.execute("replace into art_nombres values(?,?,?)", (e["id"], json.dumps(res, ensure_ascii=False), time.time())); C.commit(); time.sleep(1.0)
            fait += 1; acces += res["acces"] == "ok"
            if i % 25 == 0: R = agreger(TOUT); print(f"{i}/{len(L)} · {len(R)} annonces avec candidats · {acces} pages lues en entier", file=sys.stderr)
        b.close()
    R = agreger(TOUT)
    print(f"fini : {fait} articles, {acces} lus en entier, {len(R)} annonces avec au moins un nombre candidat", file=sys.stderr)

if __name__ == "__main__": main()
