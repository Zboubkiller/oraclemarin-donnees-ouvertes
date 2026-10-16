"""Tri des fermetures Sirene avant validation humaine (rien n'est ajouté au tracker sans validation) :
1. BODACC : une société entièrement cessée qui a publié une fusion, une absorption, un apport partiel d'actif ou une transmission
   universelle de patrimoine, ou qui a vendu son fonds de commerce (12 mois avant à 3 mois après), n'a pas licencié : ses fermetures
   sont retirées de la file ; pour une société active, seule une vente de fonds qui cite la commune du site compte (table fusion_bodacc,
   lue par fermetures.candidats et fermetures.restructurations, qui garde le repreneur) ;
2. état du jour (API Recherche d'entreprises) : la base locale est mensuelle ; un établissement redevenu actif (fermeture annulée ou
   corrigée dans Sirene, ex. Magnesita Valenciennes) est retiré de la file ;
3. corpus presse du projet : article dont le titre cite l'entreprise et la commune, autour de la date (table tri_fermeture), affiché
   sur la carte et mis en tête de file.
Un essai de tri par Gemini (octobre 2026) a été abandonné : sans accès à la presse, ses verdicts reformulaient les faits Sirene avec
une logique fragile (un site fermé dans un groupe multi-sites jugé « réorganisation »). Usage : tri_fermetures.py"""
import datetime as dt, json, os, re, sqlite3, sys, time, unicodedata, urllib.parse
H = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, H)
import fermetures, collect
db = sqlite3.connect(os.path.join(H, "cache.db"), timeout=120, check_same_thread=False)
db.execute("create table if not exists tri_fermeture(siret text primary key, js text, ts real)")
db.execute("create table if not exists fusion_bodacc(siren text primary key, js text, ts real)")
norm = lambda x: re.sub(r"[^a-z0-9 ]", " ", unicodedata.normalize("NFD", (x or "").lower()).encode("ascii", "ignore").decode())
MOTS = re.compile(r"fusion|absorb|transmission universelle|dissolution sans liquidation|apport partiel d.actif|confusion de patrimoine", re.I)

def mot_cle(nom):
    t = [w for w in re.split(r"[\s\-.,'()]+", (nom or "").upper()) if w and w not in fermetures.GENERIQUES and not w.isdigit()]
    return norm(t[0]).strip() if t and len(t[0]) >= 3 else None

def fusions(siren):
    """Annonces BODACC depuis juin 2024 qui expliquent une fermeture sans perte d'emplois immédiate (cache 30 jours) :
    fusion / absorption / TUP / apport partiel d'actif ({"type": "fusion"}), et vente du fonds de commerce par la société
    ({"type": "cession", "acheteur", "acheteur_siren"} : les contrats de travail passent au repreneur, art. L. 1224-1)."""
    r = db.execute("select js, ts from fusion_bodacc where siren=?", (siren,)).fetchone()
    if r and time.time() - r[1] < 30 * 86400: return json.loads(r[0])
    sp = f"{siren[:3]} {siren[3:6]} {siren[6:]}"
    out = []
    for where in (f'registre like "*{sp}*" and dateparution >= "2024-06-01"',
                  f'familleavis="vente" and (listeprecedentproprietaire like "*{siren}*" or listeprecedentproprietaire like "*{sp}*" or listeprecedentexploitant like "*{siren}*" or listeprecedentexploitant like "*{sp}*") and dateparution >= "2024-06-01"'):
        d = collect.get(collect.BODACC + "?" + urllib.parse.urlencode({"where": where, "limit": 30, "order_by": "dateparution desc"}))
        if d is None: return None
        for x in d.get("results", []):
            t = json.dumps(x, ensure_ascii=False)
            prec = (x.get("listeprecedentproprietaire") or "") + (x.get("listeprecedentexploitant") or "")
            if x.get("familleavis") == "vente" and (siren in prec or sp in prec):
                rg = x.get("registre") or ""
                rg = rg[0] if isinstance(rg, list) and rg else rg if isinstance(rg, str) else ""
                reg = re.sub(r"\D", "", rg.split(",")[0])[:9]
                out.append({"type": "cession", "date": x.get("dateparution"), "acheteur": (x.get("commercant") or "").split(",")[0].strip() or None,
                            "acheteur_siren": reg if len(reg) == 9 and reg != siren else None, "url": x.get("url_complete"), "texte": norm(t)[:3000]})
                continue
            m = MOTS.search(t)
            if m: out.append({"type": "fusion", "date": x.get("dateparution"), "famille": x.get("familleavis_lib"), "mot": m.group(0).lower(), "url": x.get("url_complete")})
    vus, uniq = set(), []
    for x in out:
        if x["url"] not in vus: vus.add(x["url"]); uniq.append(x)
    db.execute("replace into fusion_bodacc values(?,?,?)", (siren, json.dumps(uniq, ensure_ascii=False), time.time())); db.commit()
    time.sleep(0.15)
    return uniq

def etat_du_jour(siret):
    """'A' (actif) ou 'F' (fermé) selon l'API Recherche d'entreprises, None si indisponible."""
    try:
        d = collect.get("https://recherche-entreprises.api.gouv.fr/search?" + urllib.parse.urlencode({"q": siret, "per_page": 1}))
        for r in (d or {}).get("results", []):
            for m in r.get("matching_etablissements") or []:
                if m.get("siret") == siret: return m.get("etat_administratif")
            if (r.get("siege") or {}).get("siret") == siret: return r["siege"].get("etat_administratif")
    except Exception as ex:
        print("état du jour :", ex, file=sys.stderr)
    return None

def corpus():
    return [(norm(e.get("titre")), e.get("titre"), e.get("url"), e.get("source"), e.get("date") or "")
            for e in (json.loads(j) for (j,) in db.execute("select js from presse"))]

def articles(c, CP):
    cles = {k for k in (mot_cle(c["enseigne"]), mot_cle(c["nom"])) if k}
    com = norm(re.sub(r"\s+\d+(er|e)?$", "", c["commune"] or "")).strip()
    if not cles or not com: return []
    try: d = dt.date.fromisoformat(c["date"][:10]); bas, haut = (d - dt.timedelta(days=550)).isoformat(), (d + dt.timedelta(days=120)).isoformat()
    except (TypeError, ValueError): return []
    return [{"titre": t, "url": u, "source": s, "date": dd} for tn, t, u, s, dd in CP if bas <= dd <= haut
            and any(re.search(r"\b" + re.escape(k) + r"\b", tn) for k in cles) and re.search(r"\b" + re.escape(com) + r"\b", tn)][:3]

def trier():
    C = fermetures.candidats(tout=True); CP = corpus()
    for s in sorted({c["siren"] for c in C}): fusions(s)
    n = r = 0
    for c in C:
        a = articles(c, CP); n += bool(a)
        e = etat_du_jour(c["siret"]); r += e == "A"; time.sleep(0.2)
        db.execute("replace into tri_fermeture values(?,?,?)", (c["siret"], json.dumps({"articles": a, "etat_du_jour": e}, ensure_ascii=False), time.time()))
    db.commit()
    print(f"tri des fermetures : {r} établissements redevenus actifs selon l'état du jour", file=sys.stderr)
    print(f"tri des fermetures : {len(C)} candidates, {len(fermetures.candidats())} après fusions BODACC, {n} avec article de presse", file=sys.stderr)

def avis(siret):
    r = db.execute("select js from tri_fermeture where siret=?", (siret,)).fetchone()
    return json.loads(r[0]) if r else {}

if __name__ == "__main__":
    trier()
