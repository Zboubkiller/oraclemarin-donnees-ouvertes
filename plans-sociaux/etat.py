"""État des sources et de la collecte, après chaque passage : public/etat.json (couverture affichée sur le site) et
public/etat.xml (flux RSS d'alerte, non indexé : une entrée par problème et par jour, à suivre dans un lecteur de flux).
Surveille aussi la page « liste noire » de la CGT pour signaler une nouvelle édition."""
import datetime as dt, hashlib, json, os, re, sqlite3, sys, time, urllib.request
from email.utils import format_datetime
H = os.path.dirname(os.path.abspath(__file__)); PUB = os.path.join(H, "public")
db = sqlite3.connect(os.path.join(H, "cache.db"), timeout=60)
db.execute("create table if not exists etat(k text primary key, v text)")
CGT_PAGE = "https://www.cgt.fr/actualites/france/industrie/liste-noire-des-pse-mise-jour"
UA = {"User-Agent": "Mozilla/5.0 (veille plans-sociaux; +https://oraclemarin.fr/plans-sociaux/)"}

def lire(nom):
    try: return json.load(open(os.path.join(PUB, nom), encoding="utf-8"))
    except Exception: return None

def age_h(p):
    try: return (time.time() - os.path.getmtime(p)) / 3600
    except OSError: return None

def get(k):
    r = db.execute("select v from etat where k=?", (k,)).fetchone(); return r[0] if r else None

def cgt():
    """Empreinte de la page CGT (adresse finale, titre, images et PDF cités) : un changement = nouvelle édition probable."""
    try:
        r = urllib.request.urlopen(urllib.request.Request(CGT_PAGE, headers=UA), timeout=40)
        h = r.read().decode("utf-8", "ignore"); fin = r.geturl()
    except Exception as ex:
        return None, f"page CGT injoignable ({ex})"
    titre = (re.search(r"<title>([^<]*)", h) or [None, ""])[1].strip()
    pdfs = sorted(set(re.findall(r"[\w/%.-]*[Ll]iste[\w%.-]*\.pdf", h)))
    vis = sorted(set(re.findall(r"files/inline-images/[^\"' ]*liste[^\"' ]*", h, re.I)))
    emp = hashlib.sha1(json.dumps([fin, titre, pdfs, vis]).encode()).hexdigest()[:12]
    return {"url": fin, "titre": titre, "pdfs": pdfs, "empreinte": emp}, None

def main():
    pb, info = [], {}
    d = lire("data.json") or {}
    ev = d.get("evenements", [])
    a = age_h(os.path.join(PUB, "data.json"))
    if a is None or a > 14: pb.append(f"data.json n'a pas été régénéré depuis {a and round(a)} h : la collecte a probablement échoué (voir collect.log)")
    pub = sorted((e.get("date_publication") or "")[:10] for e in ev if e.get("source") == "BODACC")
    if pub and (dt.date.today() - dt.date.fromisoformat(pub[-1])).days > 5: pb.append(f"BODACC : dernière annonce publiée le {pub[-1]} (plus de 5 jours)")
    n24 = db.execute("select count(*) from presse where ts > ?", (time.time() - 36 * 3600,)).fetchone()[0]
    if n24 == 0: pb.append("Presse : aucun article enregistré en 36 h (flux, Bing ou Gemini en panne ?)")
    dares = age_h(os.path.join(PUB, "dares.json"))
    if dares is not None and dares > 10 * 24: pb.append(f"DARES : fichier vieux de {round(dares / 24)} jours (le cron du lundi a échoué ?)")
    try:
        import sqlite3 as _s
        r = _s.connect(os.path.join(H, "acco.db")).execute("select max(ts) from acco_fichiers").fetchone()[0]
        if r and (time.time() - r) > 10 * 86400: pb.append(f"Accords d'entreprise : aucune archive DILA lue depuis {round((time.time() - r) / 86400)} jours")
    except Exception: pass
    import shutil
    du = shutil.disk_usage("/")
    if du.used / du.total > 0.9: pb.append(f"Disque du serveur plein à {round(100 * du.used / du.total)} % ({round(du.free / 1e9, 1)} Go libres)")
    comp = age_h(os.path.join(PUB, "compteur.json"))
    if comp is not None and comp > 2: pb.append(f"Compteur : pas mis à jour depuis {round(comp)} h")
    try:
        log = open(os.path.join(H, "collect.log"), encoding="utf-8", errors="ignore").read()[-20000:]
        dernier = log[log.rfind("data.json :"):] if "data.json :" in log else log
        for l in dernier.splitlines():
            if re.search(r"Traceback|Error|: HTTP Error|injoignable", l): pb.append("collect.log : " + l.strip()[:200]); break
    except OSError: pass
    c, err = cgt()
    if err: pb.append("CGT : " + err)
    elif c:
        avant = get("cgt_empreinte")
        if avant and avant != c["empreinte"]:
            pb.append(f"CGT : la page « liste noire » a changé ({c['titre']}) — nouvelle édition probable, à importer : {c['url']}")
        if not avant or avant != c["empreinte"]:
            db.execute("replace into etat values('cgt_empreinte', ?)", (c["empreinte"],)); db.execute("replace into etat values('cgt_vu', ?)", (dt.date.today().isoformat(),)); db.commit()
        info["cgt_page"] = c
    # couverture, affichée sur le site
    pr = sorted(e["date"] for e in ev if e.get("source") not in ("BODACC", "Accords d'entreprise") and not str(e.get("source", "")).startswith("CGT") and e.get("date"))
    cg = [e.get("url") or "" for e in ev if str(e.get("source", "")).startswith("CGT")]
    m = next((re.search(r"/(\d{4})(\d{2})(\d{2})_", u) for u in cg if re.search(r"/(\d{4})(\d{2})(\d{2})_", u)), None)
    try: tend = json.load(open(os.path.join(PUB, "tendance.json"), encoding="utf-8")).get("debut_50")
    except Exception: tend = None
    couv = {"bodacc_depuis": pub[0] if pub else None, "bodacc_jusqu_a": pub[-1] if pub else None, "bodacc_historique_depuis": tend or "2025-03-17",
            "presse_depuis": pr[0] if pr else None, "cgt_edition": f"{m[1]}-{m[2]}-{m[3]}" if m else None, "verifie": dt.datetime.now(dt.timezone.utc).isoformat(timespec="minutes")}
    out = {"maj": couv["verifie"], "ok": not pb, "problemes": pb, "couverture": couv, **info}
    json.dump(out, open(os.path.join(PUB, "etat.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    # flux d'alerte : on garde 30 jours d'entrées
    hist = json.loads(get("historique") or "[]")
    j = dt.date.today().isoformat()
    for p in pb:
        g = hashlib.sha1((j + p[:60]).encode()).hexdigest()[:16]
        if not any(h["g"] == g for h in hist): hist.append({"g": g, "d": dt.datetime.now(dt.timezone.utc).isoformat(), "t": p})
    hist = [h for h in hist if h["d"][:10] >= (dt.date.today() - dt.timedelta(days=30)).isoformat()]
    db.execute("replace into etat values('historique', ?)", (json.dumps(hist, ensure_ascii=False),)); db.commit()
    esc = lambda s: s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    items = "".join(f"<item><title>{esc(h['t'][:120])}</title><description>{esc(h['t'])}</description><guid isPermaLink=\"false\">{h['g']}</guid>"
                    f"<pubDate>{format_datetime(dt.datetime.fromisoformat(h['d']))}</pubDate></item>" for h in reversed(hist))
    open(os.path.join(PUB, "etat.xml"), "w", encoding="utf-8").write(
        '<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>Plans sociaux : état de la collecte</title>'
        f"<link>https://oraclemarin.fr/plans-sociaux/etat.json</link><description>Alertes techniques (pannes de collecte, nouvelle liste CGT).</description>{items}</channel></rss>")
    print("état :", "OK" if not pb else f"{len(pb)} problème(s) : " + " | ".join(pb), file=sys.stderr)

if __name__ == "__main__":
    main()
