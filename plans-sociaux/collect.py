import unicodedata
import re
"""Tracker plans sociaux — collecte.
Sources :
  1. BODACC (open data DILA) : jugements d'ouverture (liquidation, redressement, sauvegarde), quotidien.
     Effectif et localisation via l'API Recherche d'entreprises (data.gouv). On ne garde que les
     entreprises >= SEUIL salariés (tranche INSEE, donc un ordre de grandeur, pas un chiffre exact).
  2. CGT, « liste noire » des plans de licenciement (PDF parsé par /opt/ca-brule/cgt.py).
Sortie : public/data.json (+ cache.db pour ne pas réinterroger les SIREN déjà vus)."""
import json, os, sqlite3, sys, time, urllib.request, urllib.parse, datetime as dt
import cgt_emplois

HERE = os.path.dirname(os.path.abspath(__file__))
UA = {"User-Agent": "tracker-plans-sociaux/0.1 (+https://oraclemarin.fr/plans-sociaux/)"}
BODACC = "https://bodacc-datadila.opendatasoft.com/api/explore/v2.1/catalog/datasets/annonces-commerciales/records"
RE_API = "https://recherche-entreprises.api.gouv.fr/search"
SEUIL = 50
JOURS = int(os.environ.get("JOURS", "3"))          # fenêtre de collecte BODACC (rattrapage)
TR = {"00": (0, 0), "01": (1, 2), "02": (3, 5), "03": (6, 9), "11": (10, 19), "12": (20, 49), "21": (50, 99),
      "22": (100, 199), "31": (200, 249), "32": (250, 499), "41": (500, 999), "42": (1000, 1999),
      "51": (2000, 4999), "52": (5000, 9999), "53": (10000, 10000)}
TYPES = [("liquidation", "liquidation judiciaire"), ("redressement", "redressement judiciaire"),
         ("sauvegarde", "procédure de sauvegarde")]

db = sqlite3.connect(os.path.join(HERE, "cache.db"), timeout=120)
db.execute("create table if not exists ent(siren text primary key, js text, ts real)")
db.execute("create table if not exists ev(id text primary key, js text)")

def get(url, tries=5):
    for i in range(tries):
        try:
            return json.load(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30))
        except urllib.error.HTTPError as e:
            if e.code == 429: time.sleep(2 + 3 * i); continue
            raise
        except Exception:
            time.sleep(2 + 2 * i)
    return None

_last = [0.0]
def entreprise(siren):
    r = db.execute("select js, ts from ent where siren=?", (siren,)).fetchone()
    if r and time.time() - r[1] < 30 * 86400: return json.loads(r[0])
    wait = 0.15 - (time.time() - _last[0])          # ~7 req/s max autorisé
    if wait > 0: time.sleep(wait)
    _last[0] = time.time()
    d = get(RE_API + "?" + urllib.parse.urlencode({"q": siren, "per_page": 1}))
    e = (d or {}).get("results") or [{}]
    e = e[0] if e and e[0].get("siren") == siren else {}
    s = e.get("siege") or {}
    out = {"nom": e.get("nom_complet"), "tranche": e.get("tranche_effectif_salarie"),
           "annee_tranche": e.get("annee_tranche_effectif_salarie"), "naf": e.get("activite_principale"),
           "commune": s.get("libelle_commune"), "insee": s.get("commune"), "dep": s.get("departement"),
           "lat": s.get("latitude"), "lon": s.get("longitude")}
    if d is not None:
        db.execute("replace into ent values(?,?,?)", (siren, json.dumps(out), time.time())); db.commit()
    return out

def bodacc(debut=None, fin=None):
    debut = debut or (dt.date.today() - dt.timedelta(days=JOURS)).isoformat()
    where = f'familleavis="collective" and dateparution>="{debut}" and jugement like "*ouverture*"'
    if fin: where += f' and dateparution<"{fin}"'
    off, n = 0, 0
    while True:
        q = urllib.parse.urlencode({"where": where, "limit": 100, "offset": off, "order_by": "dateparution",
              "select": "id,dateparution,commercant,ville,cp,numerodepartement,registre,jugement,tribunal,url_complete"})
        d = get(BODACC + "?" + q)
        if not d: break
        for a in d["results"]:
            j = json.loads(a.get("jugement") or "{}")
            nat = (j.get("nature") or "").lower()
            if not (nat.startswith("jugement d'ouverture") or nat.startswith("jugement d'extension")): continue
            typ = next((t for t, k in TYPES if k.split()[0] in nat), None)
            if not typ or not a.get("registre"): continue
            siren = a["registre"][0].replace(" ", "")
            e = entreprise(siren); n += 1
            lo, hi = TR.get(e.get("tranche") or "", (None, None))
            if lo is None or lo < SEUIL: continue
            ev = {"id": "bodacc-" + a["id"], "source": "BODACC", "type": typ,
                  "entreprise": e.get("nom") or a.get("commercant"), "siren": siren, "naf": e.get("naf"),
                  "commune": e.get("commune") or a.get("ville"), "dep": e.get("dep") or a.get("numerodepartement"),
                  "lat": e.get("lat"), "lon": e.get("lon"), "insee": e.get("insee"),
                  "emplois_min": lo, "emplois_max": hi, "emplois_precision": "tranche INSEE " + str(e.get("annee_tranche") or ""),
                  "date": j.get("date") or a["dateparution"], "date_publication": a["dateparution"],
                  "detail": j.get("nature"), "tribunal": a.get("tribunal"), "url": a.get("url_complete")}
            db.execute("replace into ev values(?,?)", (ev["id"], json.dumps(ev, ensure_ascii=False)))
        db.commit()
        off += 100
        if off >= d["total_count"] or off >= 9900: break
    print("BODACC : %d annonces vérifiées" % n, file=sys.stderr)

def cgt():
    p = "/opt/ca-brule/licenciements.json"
    if not os.path.exists(p): return []
    d = json.load(open(p)); it = d if isinstance(d, list) else next(v for v in d.values() if isinstance(v, list))
    out = []
    for i, x in enumerate(it):
        date = dt.datetime.fromtimestamp(x["ts"], dt.timezone.utc).date().isoformat() if x.get("ts") and x["ts"] < 2e9 else None
        fin_pse = None
        if date and date > dt.date.today().isoformat(): fin_pse, date = date, None   # date de clôture du PSE, pas d'annonce
        try: date = json.load(open(os.path.join(HERE, "dates_cgt.json"), encoding="utf-8")).get("cgt-%d" % i, date)   # dates d'annonce retrouvées à la main
        except Exception: pass
        if (x.get("title") or "").strip().lower() in cgt_emplois.NON_ENTREPRISES: continue
        n, note = cgt_emplois.relire(x.get("text"), x.get("jobs"), x.get("title"))   # effectif visé en France, relu dans le texte
        ev = {"id": "cgt-%d" % i, "source": "CGT (liste noire)", "type": "plan social",
              "entreprise": x.get("title"), "commune": None if "(département)" in (x.get("place") or "") else x.get("place"), "dep": x.get("dep"),
              "lat": x.get("lat"), "lon": x.get("lon"), "approx": x.get("approx"),
              "emplois_min": n, "emplois_max": n, "emplois_precision": "annoncé" if n else None,
              "date": date, "date_precision": "mois", "detail": x.get("text"), "url": x.get("url")}
        if note: ev.update(emplois_cgt_brut=x.get("jobs"), emplois_note=note)
        if fin_pse: ev["date_fin_pse"] = fin_pse
        out.append(ev)
    try: out += json.load(open(os.path.join(HERE, "cgt_lignes_manquantes.json"), encoding="utf-8"))     # lignes du PDF que l'extraction automatique n'a pas produites, saisies à la main
    except Exception: pass
    # doublons de la liste CGT : même date, même effectif, un nom qui prolonge l'autre (« Albany » / « Albany International »)
    import commun
    garde = []
    for ev in sorted(out, key=lambda v: len(v.get("entreprise") or "")):
        a = commun.cle_nom(ev.get("entreprise"))
        if a and any(g["date"] == ev["date"] and g["emplois_min"] == ev["emplois_min"] and commun.cle_nom(g.get("entreprise"))
                     and a.startswith(commun.cle_nom(g.get("entreprise"))) for g in garde): continue
        garde.append(ev)
    try:                                                        # page exacte du PDF de la CGT pour chaque ligne
        import cgt_pdf; cgt_pdf.analyser()
        I = json.load(open(os.path.join(HERE, "cgt", "index.json"), encoding="utf-8"))
        for ev in garde:
            k = I["items"].get(ev["id"])
            if k is None: continue
            l = I["lignes"][k]
            ev.update(url=I["pdf"] + "#page=" + str(l["page"]), cgt_ligne=k, cgt_page=l["page"], cgt_secteur=l["secteur"].title())
    except Exception as ex:
        print("cgt_pdf :", ex, file=sys.stderr)
    return garde

def geocode(evs):
    try: com = {c["code"]: c for c in json.load(open("/opt/ca-brule/communes.json"))}
    except Exception: com = {}
    for e in evs:
        if e.get("lat") is None and e.get("insee") in com:
            c = com[e["insee"]]["centre"]["coordinates"]; e["lon"], e["lat"] = c[0], c[1]
        for k in ("lat", "lon"):
            if e.get(k) is not None: e[k] = round(float(e[k]), 4)

def _sansacc(x):
    return unicodedata.normalize("NFD", (x or "").replace("’", "'").replace("‘", "'").replace("ʼ", "'")).encode("ascii", "ignore").decode()

def _majsansacc(x):
    """Accents retirés des seules majuscules (« EVREUX », « Evreux » valent Évreux ; « Vire » ne vaut pas Viré)."""
    x = (x or "").replace("’", "'").replace("‘", "'").replace("ʼ", "'")
    return "".join(unicodedata.normalize("NFD", ch)[0] if ch.isupper() else ch for ch in x)

def commune_ecrite(c, t):
    """Vrai si la commune c figure dans t comme nom propre : majuscule initiale, ni précédée d'une lettre ou d'un trait d'union
    (partie d'un nom plus long), ni suivie d'une lettre. Accents et apostrophes courbes ignorés."""
    c2, t2 = _majsansacc(c), _majsansacc(t)
    for m in re.finditer(re.escape(c2), t2, re.I):
        i, j = m.start(), m.end()
        if not t2[i].isupper(): continue
        if i > 0 and (t2[i - 1].isalnum() or t2[i - 1] == "-"): continue
        if j < len(t2) and t2[j].isalnum(): continue
        return True
    return False

_GRANDES = None
_HOM = None
def _HOMONYMES():
    global _HOM
    if _HOM is None:
        _HOM = {}
        try: C = json.load(open("/opt/ca-brule/communes.json"))
        except Exception: C = []
        for c in sorted(C, key=lambda c: c.get("population") or 0): _HOM.setdefault(_sansacc(c["nom"]).lower(), []).append(c)
    return _HOM

def grande_ville(e):
    """« Charleville » lu dans un article est Charleville-Mézières (45 000 hab.), pas le village de Charleville (Marne) : un village
    de moins de 2 000 habitants dont le nom ouvre celui d'une seule ville de 20 000 habitants et plus est remplacé par celle-ci."""
    global _GRANDES
    if not e.get("commune") or e.get("siret"): return
    if _GRANDES is None:
        try: C = json.load(open("/opt/ca-brule/communes.json"))
        except Exception: C = []
        _GRANDES = ({_sansacc(c["nom"]).lower().replace(" ", "-"): c for c in C if (c.get("population") or 0) >= 10000 and ("-" in c["nom"] or " " in c["nom"])},
                    {c["code"]: c.get("population") or 0 for c in C}, {})
        for c in C:     # population maximale par nom : « Saint-Étienne » sans code INSEE reste la grande ville
            k = _sansacc(c["nom"]).lower(); _GRANDES[2][k] = max(_GRANDES[2].get(k, 0), c.get("population") or 0)
    G, P, PN = _GRANDES
    # homonyme exact (Saint-Nazaire 66 / 44) : sans code INSEE, la commune 5 fois plus peuplée que celle du département lu l'emporte
    if not e.get("insee"):
        H_ = _HOMONYMES().get(_sansacc(e["commune"]).lower(), [])
        if len(H_) > 1:
            ici = [c for c in H_ if c["codeDepartement"] == e.get("dep")]
            top = H_[-1]
            if ici and ici[0] is not top and (top.get("population") or 0) >= 5 * (ici[0].get("population") or 0) and (top.get("population") or 0) >= 10000:
                e.update(commune=top["nom"], insee=top["code"], dep=top["codeDepartement"], lon=top["centre"]["coordinates"][0], lat=top["centre"]["coordinates"][1], commune_homonyme=True)
                return
    if P.get(e.get("insee"), 0) >= 2000 or (not e.get("insee") and PN.get(_sansacc(e["commune"]).lower(), 0) >= 2000): return
    n = _sansacc(e["commune"]).lower() + "-"
    L = [c for k, c in G.items() if k.startswith(n) and _majsansacc(c["nom"]).lower().replace(" ", "-").startswith(_majsansacc(e["commune"]).lower() + "-")]
    if len(L) != 1: return
    c = L[0]
    e.update(commune=c["nom"], insee=c["code"], dep=c["codeDepartement"], lon=c["centre"]["coordinates"][0], lat=c["centre"]["coordinates"][1], commune_grande_ville=True)

DEPARTEMENTS = {'01': 'Ain', '02': 'Aisne', '03': 'Allier', '04': 'Alpes-de-Haute-Provence', '05': 'Hautes-Alpes', '06': 'Alpes-Maritimes', '07': 'Ardèche', '08': 'Ardennes', '09': 'Ariège', '10': 'Aube', '11': 'Aude', '12': 'Aveyron', '13': 'Bouches-du-Rhône', '14': 'Calvados', '15': 'Cantal', '16': 'Charente', '17': 'Charente-Maritime', '18': 'Cher', '19': 'Corrèze', '2A': 'Corse-du-Sud', '2B': 'Haute-Corse', '21': "Côte-d'Or", '22': "Côtes-d'Armor", '23': 'Creuse', '24': 'Dordogne', '25': 'Doubs', '26': 'Drôme', '27': 'Eure', '28': 'Eure-et-Loir', '29': 'Finistère', '30': 'Gard', '31': 'Haute-Garonne', '32': 'Gers', '33': 'Gironde', '34': 'Hérault', '35': 'Ille-et-Vilaine', '36': 'Indre', '37': 'Indre-et-Loire', '38': 'Isère', '39': 'Jura', '40': 'Landes', '41': 'Loir-et-Cher', '42': 'Loire', '43': 'Haute-Loire', '44': 'Loire-Atlantique', '45': 'Loiret', '46': 'Lot', '47': 'Lot-et-Garonne', '48': 'Lozère', '49': 'Maine-et-Loire', '50': 'Manche', '51': 'Marne', '52': 'Haute-Marne', '53': 'Mayenne', '54': 'Meurthe-et-Moselle', '55': 'Meuse', '56': 'Morbihan', '57': 'Moselle', '58': 'Nièvre', '59': 'Nord', '60': 'Oise', '61': 'Orne', '62': 'Pas-de-Calais', '63': 'Puy-de-Dôme', '64': 'Pyrénées-Atlantiques', '65': 'Hautes-Pyrénées', '66': 'Pyrénées-Orientales', '67': 'Bas-Rhin', '68': 'Haut-Rhin', '69': 'Rhône', '70': 'Haute-Saône', '71': 'Saône-et-Loire', '72': 'Sarthe', '73': 'Savoie', '74': 'Haute-Savoie', '76': 'Seine-Maritime', '77': 'Seine-et-Marne', '78': 'Yvelines', '79': 'Deux-Sèvres', '80': 'Somme', '81': 'Tarn', '82': 'Tarn-et-Garonne', '83': 'Var', '84': 'Vaucluse', '85': 'Vendée', '86': 'Vienne', '87': 'Haute-Vienne', '88': 'Vosges', '89': 'Yonne', '90': 'Territoire de Belfort', '91': 'Essonne', '92': 'Hauts-de-Seine', '93': 'Seine-Saint-Denis', '94': 'Val-de-Marne', '95': "Val-d'Oise", '971': 'Guadeloupe', '972': 'Martinique', '973': 'Guyane', '974': 'La Réunion', '976': 'Mayotte'}

def departement_cite(t):
    """Département nommé dans un titre, introduit par « dans le/la/l'/les », « en », « du », « de l' », une parenthèse, ou en tête
    (« Pas-de-Calais. … »). Renvoie le code s'il n'y en a qu'un, sinon None. Les noms ambigus (Nord, Var, Cher, Lot…) exigent
    cette introduction, et un nom inclus dans un autre (Vienne dans Haute-Vienne) ne compte pas."""
    t2 = _sansacc(t)
    trouves = set()
    for code, nom in DEPARTEMENTS.items():
        n = re.escape(_sansacc(nom)).replace("\\-", "[- ]")
        if re.search(r"(?:^|(?:dans (?:le |la |les |l')|\ben |\bdu |\bde l'|\bdes |\())" + n + r"(?![\w-])", t2) and not re.search(r"[\w-]" + n + r"(?![\w-])", t2.replace("dans l'", "dans ").replace("de l'", "de ")):
            trouves.add(code)
    return trouves.pop() if len(trouves) == 1 else None

def lev1(a, b):
    """Vrai si a et b diffèrent d'au plus une lettre (ajout, suppression ou substitution)."""
    if a == b: return True
    if abs(len(a) - len(b)) > 1: return False
    i = 0
    while i < min(len(a), len(b)) and a[i] == b[i]: i += 1
    return a[i + 1:] == b[i + 1:] or a[i:] == b[i + 1:] or a[i + 1:] == b[i:]

def fusion(evs):
    """Annonces (CGT, presse) : une seule ligne par entreprise et par période de 120 jours. Clé : SIREN si connu, sinon le nom
    normalisé (un nom qui prolonge l'autre, même département). La ligne CGT est prioritaire (effectif relu) ; les autres
    deviennent des sources (« sources »), et complètent ce qui manque (effectif, commune, SIREN)."""
    nom = lambda x: re.sub(r"[^a-z0-9]", "", re.sub(r"^(?:groupe|group|societe|ste)\s+", "", unicodedata.normalize("NFD", (x or "").lower()).encode("ascii", "ignore").decode().strip()))
    jour = lambda e: dt.date.fromisoformat(e["date"][:10])
    cand = lambda e: e.get("source") != "BODACC" and e.get("date") and e.get("entreprise") and e.get("entreprise") != e.get("titre") and not e.get("sans_entreprise") and not e.get("partie_de")
    prim, garde = [], []
    ACC = "Accords d'entreprise"
    rang = lambda e: (0 if str(e.get("source", "")).startswith("CGT") else 2 if e.get("source") == ACC else 1, e.get("date") or "")
    for e in sorted(evs, key=rang):
        if not cand(e): garde.append(e); continue
        for x in e.pop("autres_sources", []) or []:
            e.setdefault("sources", []).append({"source": x.get("source"), "url": x.get("url"), "date": None})
        n = nom(e["entreprise"]); p = None
        for q in prim:
            ecart = abs((jour(q) - jour(e)).days)
            if q.get("siren") and e.get("siren"):
                # même SIREN : un accord d'entreprise se signe souvent plusieurs mois après l'annonce, et la presse revient sur un plan des mois plus tard
                if q["siren"] != e["siren"]: continue
                deux_cgt = str(q.get("source", "")).startswith("CGT") and str(e.get("source", "")).startswith("CGT")
                lim = 120 if deux_cgt else 365 if ACC in (q.get("source"), e.get("source")) else 270
                if ecart <= lim: p = q; break
                continue
            if ecart > 120: continue
            m = nom(q["entreprise"]); court, long_ = sorted((m, n), key=len)
            meme_dep = not q.get("dep") or not e.get("dep") or q["dep"] == e["dep"]
            if meme_dep and ((m == n and len(n) >= 3) or (len(court) >= 5 and long_.startswith(court))): p = q; break
            if m == n and len(n) >= 4 and ecart <= 60: p = q; break      # même nom exact, même période : le département peut différer (siège / site)
            # faute de frappe (« Wordline » / « Worldline ») : une lettre d'écart, même département connu, moins d'un mois
            if q.get("dep") and q.get("dep") == e.get("dep") and len(court) >= 6 and ecart <= 30 and abs(len(m) - len(n)) <= 1 and lev1(m, n): p = q; break
        if not p:
            prim.append(e); garde.append(e); continue
        p.setdefault("sources", []).append({"source": e.get("source"), "url": e.get("url"), "date": e.get("date"), "titre": e.get("titre") or e.get("titre_accord") or e.get("entreprise"), "cgt_ligne": e.get("cgt_ligne")})
        p["sources"] += e.get("sources", [])
        if not p.get("emplois_min") and e.get("emplois_min"):
            p.update(emplois_min=e["emplois_min"], emplois_max=e.get("emplois_max"), emplois_precision=e.get("emplois_precision"))
        if (not p.get("commune") or p.get("approx")) and e.get("commune") and not e.get("approx") and (not p.get("dep") or p["dep"] == e.get("dep")):
            p.update({k: e.get(k) for k in ("commune", "dep", "insee", "lat", "lon")}, approx=False)
        if not p.get("siren") and e.get("siren") and (p.get("rattachement_retire") or {}).get("siren") != e.get("siren") and not p.get("rattachement_retire"):
            p.update({k: e.get(k) for k in ("siren", "lien", "siren_rapproche", "siret", "comptes", "argent_public", "proximite", "fiable", "naf", "categorie", "tranche") if e.get(k) is not None})
    # un article de presse sur une procédure (redressement, liquidation, sauvegarde) rejoint la ligne BODACC du même SIREN à 90 jours près
    B = {}
    for x in garde:
        if x.get("source") == "BODACC" and x.get("siren") and x.get("date"): B.setdefault(x["siren"], []).append(x)
    reste = []
    for x in garde:
        s = str(x.get("source", ""))
        if (x in prim and x.get("source") != ACC and not s.startswith("CGT") and x.get("siren") in B and x.get("date")
                and x.get("type") in ("redressement", "liquidation", "sauvegarde")):
            b = min(B[x["siren"]], key=lambda b: abs((jour(b) - jour(x)).days))
            if abs((jour(b) - jour(x)).days) <= 90:
                b.setdefault("sources", []).append({"source": x.get("source"), "url": x.get("url"), "date": x.get("date"), "titre": x.get("titre") or x.get("entreprise")})
                b["sources"] += x.get("sources", []); prim.remove(x); continue
        reste.append(x)
    garde = reste
    vus = set()
    for p in prim + [b for L in B.values() for b in L]:   # dédoublonnage des URL
        if p.get("sources"):
            s, vus = [], {p.get("url")}
            for x in p["sources"]:
                if x.get("url") and x["url"] not in vus: vus.add(x["url"]); s.append(x)
            p["sources"] = s
    print("fusion des sources : %d annonces -> %d (%d lignes avec plusieurs sources)" % (sum(1 for e in evs if cand(e)), len(prim), sum(1 for p in prim if p.get("sources"))), file=sys.stderr)
    return garde

if __name__ == "__main__":
    bodacc()
    # l'historique BODACC (rattrapage de tendance.py) reste en base ; seule la dernière année est publiée dans data.json
    coupe = min("2025-01-01", (dt.date.today() - dt.timedelta(days=400)).isoformat())   # toute l'année 2025 et la suite
    evs = [e for e in (json.loads(r[0]) for r in db.execute("select js from ev")) if (e.get("date_publication") or "") >= coupe] + cgt()
    # presse : publié seulement si l'article a été structuré et jugé pertinent par Gemini ; le reste attend une validation
    try:
        pr = [json.loads(r[0]) for r in db.execute("select js from presse")]
        for e in pr:   # effectifs parfois rendus en texte par Gemini
            for k in ("emplois_min", "emplois_max"):
                try: e[k] = int(float(str(e[k]).replace(" ", ""))) if e.get(k) not in (None, "") else None
                except ValueError: e[k] = None
        # types de presse ramenés aux catégories du site ; communes ambiguës (« Orange », nom de ville tiré du nom du média) écartées
        TYPES_P = {"licenciement": "plan social", "licenciements": "plan social", "pse": "plan social", "plan de sauvegarde de l'emploi": "plan social",
                   "redressement judiciaire": "redressement", "liquidation judiciaire": "liquidation", "sauvegarde": "sauvegarde",
                   "plan social": "plan social", "fermeture": "fermeture", "liquidation": "liquidation", "redressement": "redressement", "départs volontaires": "départs volontaires"}
        sa = lambda x: unicodedata.normalize("NFD", (x or "").lower()).encode("ascii", "ignore").decode()
        SRC_PRESSE = {x.get("source") for x in pr if x.get("source")}
        for e in pr:
            if str(e.get("source", "")).startswith("CGT"): e["source"] = "cgt.fr (site syndical)"   # à ne pas confondre avec la liste CGT
            t = (e.get("type") or "").lower().strip()
            e["type_brut"] = t
            e["type"] = TYPES_P.get(t, "chômage partiel" if "partiel" in t else "plan social")
            # une commune lue dans le titre doit y figurer comme nom propre (« GTT change de DG » n'est pas Changé, « Pas-de-Calais » n'est pas Calais)
            if e.get("commune") and e.get("extraction") != "gemini_commune" and sa(e["commune"]) in sa(e.get("titre"))                     and not commune_ecrite(e["commune"], (e.get("titre") or "") + " " + (e.get("detail") or "")):
                # même mot écrit sans l'accent (« Vire » lu comme Viré) : on garde le mot du titre, que la règle des grandes villes peut reconnaître
                mots = [w.split("'")[-1] for w in re.findall(r"[\w'-]+", e.get("titre") or "") if _sansacc(w.split("'")[-1]).lower() == _sansacc(e["commune"]).lower() and w.split("'")[-1][:1].isupper()]
                e.update(commune=mots[0] if mots else None, dep=None, lat=None, lon=None, insee=None)
            # commune tirée du nom de l'entreprise (« Fleury » dans « Fleury Michon ») : retirée si le titre ne la cite pas ailleurs
            if e.get("commune") and e.get("entreprise") and e.get("entreprise") != e.get("titre") and commune_ecrite(e["commune"], e["entreprise"]):
                reste = re.sub(re.escape(e["entreprise"]), " ", e.get("titre") or "", flags=re.I)
                if not commune_ecrite(e["commune"], reste): e.update(commune=None, dep=None, lat=None, lon=None, insee=None)
            grande_ville(e)
            if e.get("entreprise") and e["entreprise"] != e.get("titre") and __import__("commun").nom_douteux(e["entreprise"], SRC_PRESSE, e.get("titre")):
                e["entreprise_ia"] = e["entreprise"]; e["entreprise"] = e.get("titre")      # employeur non nommé dans le titre : identification à la main
            dc = departement_cite(e.get("titre"))      # « 31 postes supprimés chez NTN dans l'Aisne » : le département du titre prime
            if dc:
                if e.get("dep") and e["dep"] != dc: e.update(commune=None, insee=None, lat=None, lon=None)
                e["dep"] = dc
            if e.get("commune") and (sa(e["commune"]) in ("orange", "saint-gobain") or sa(e["commune"]) in sa(e.get("source"))):
                e.update(commune=None, dep=None, lat=None, lon=None, insee=None)
        pr = [e for e in pr if e["type"] != "chômage partiel"]      # activité partielle : pas une suppression d'emplois
        # médias étrangers (Suisse, Belgique, Luxembourg, Canada, Afrique) et sites qui ne sont pas des médias (cabinets d'avocats)
        ETRANGERS = ("24 heures", "l'essentiel", "lessentiel", "senego", "seneweb", "rtbf", "le soir", "la libre", "lalibre", "dhnet", "sudinfo", "l'avenir", "7sur7",
                     "le temps", "tribune de geneve", "rts", "lematin.ch", "20 minutes suisse", "pme magazine", "bilan.ch", "watson", "luxemburger", "wort", "virgule",
                     "radio-canada", "ici radio-canada", "journal les 2 rives", "les 2 rives", "journal de quebec", "journal de québec", "le nouvelliste", "la presse", "le devoir", "tva nouvelles", "journal de montreal", "le360", "hespress", "kapitalis", "ilboursa",
                     "aps.dz", "tsa-algerie", "abidjan", "fratmat", "jeune afrique", "rfi afrique", "lequotidien.lu", "paperjam")
        def etranger(e):
            s = sa(e.get("source"))
            if any(s == sa(x) or s.startswith(sa(x) + " ") or sa(x) in s.split(".")[0:1] for x in ETRANGERS): return True
            u = (e.get("url") or "").split("/")[2] if (e.get("url") or "").startswith("http") else ""
            return bool(re.search(r"\.(ch|be|lu|ca|sn|ma|tn|dz|ci|cm)$", u)) and "news.google" not in u
        pr = [e for e in pr if not etranger(e) and "avocat" not in sa(e.get("source"))]
        try:
            import gemini_ident
            V = gemini_ident.verifier_presse(pr)
            # garde-fou : un titre qui parle explicitement de suppressions de postes reste, même si Gemini le juge hors sujet
            EXPLICITE = re.compile(r"suppressions? de postes|lettres? de licenciement|plan de reclassement|plan de sauvegarde de l.emploi|licenciements? collectifs?", re.I)
            hors = [e for e in pr if (V.get(e["id"]) or {}).get("en_france") is False
                    or ((V.get(e["id"]) or {}).get("collectif") is False and not EXPLICITE.search(e.get("titre") or ""))]
            print(f"presse : {len(hors)} articles retirés (hors de France ou sans suppression collective)", file=sys.stderr)
            pr = [e for e in pr if e not in hors]
            for e in pr: e["en_france"] = (V.get(e["id"]) or {}).get("en_france")
        except Exception as ex:
            print("verifier_presse :", ex, file=sys.stderr)
        ok = lambda e: e.get("extraction") in ("gemini", "regex")
        # dédoublonnage : un seul événement par entreprise sur 21 jours, les autres articles deviennent des sources secondaires
        import unicodedata
        cle = lambda x: unicodedata.normalize("NFD", (x or "").lower()).encode("ascii", "ignore").decode().replace(" ", "")[:24]
        garde = {}
        for e in sorted([e for e in pr if ok(e)], key=lambda e: e.get("date") or "", reverse=True):
            k = cle(e.get("entreprise")) if e.get("entreprise") != e.get("titre") else e["id"]
            g = garde.get(k)
            if g and (dt.date.fromisoformat(g["date"]) - dt.date.fromisoformat(e["date"])).days <= 21:
                g.setdefault("autres_sources", []).append({"source": e["source"], "url": e["url"]})
                g["emplois_min"] = g["emplois_min"] or e.get("emplois_min"); g["emplois_max"] = g["emplois_max"] or e.get("emplois_max")
                if g.get("lat") is None and e.get("lat") is not None and (not g.get("dep") or g["dep"] == e.get("dep")): g.update(lat=e["lat"], lon=e["lon"], commune=e["commune"], dep=e["dep"])
            else:
                garde[k] = e
        evs += list(garde.values())
        json.dump([e for e in pr if not ok(e)], open(os.path.join(HERE, "a_valider.json"), "w"), ensure_ascii=False, indent=1)
    except sqlite3.OperationalError:
        pass
    try:   # accords d'entreprise (Légifrance) : PSE, ruptures conventionnelles collectives, départs volontaires
        import accords; evs += accords.creer(evs)
    except Exception as ex:
        print("accords :", ex, file=sys.stderr)
    # corrections manuelles (audit) : événements exclus ; doublons BODACC (même entreprise, même date)
    try: exclus = {x["id"] for x in json.load(open(os.path.join(HERE, "rapprochements.json"), encoding="utf-8")).get("exclure", [])}
    except Exception: exclus = set()
    vus, propres = set(), []
    # même entreprise, même type de procédure à moins de 120 jours (jugement d'extension, double publication) : on garde le premier jugement
    premiers = {}
    for e in sorted([x for x in evs if x.get("source") == "BODACC" and x.get("siren") and x.get("date")], key=lambda x: x["date"]):
        k = (e["siren"], e.get("type")); p = premiers.get(k)
        if p and (dt.date.fromisoformat(e["date"]) - dt.date.fromisoformat(p["date"])).days <= 120:
            p.setdefault("jugements_suivants", []).append({"date": e["date"], "detail": e.get("detail"), "url": e.get("url")})
            e["_suivant"] = True
        else: premiers[k] = e
    evs = [e for e in evs if not e.pop("_suivant", False)]
    for e in evs:
        if e.get("id") in exclus: continue
        if e.get("source") == "BODACC":
            k = (e.get("siren"), e.get("date"))
            if k in vus: continue
            vus.add(k)
        propres.append(e)
    evs = propres
    geocode(evs); synth = None
    try:
        import aides; aides.enrichir(evs); evs = [e for e in evs if not e.get("hors_france")]
        import verif_ident; verif_ident.verifier(evs)
        try:   # annonces encore sans entreprise : recherche dans la base Sirene locale, choix par Gemini parmi les candidats
            import sirene_rag; nouv = sirene_rag.completer(evs)
            if nouv: aides.enrichir(nouv)
            import validation; validation.appliquer(evs)
            import regles_ident; regles_ident.appliquer(evs)
        except Exception as ex:
            print("sirene_rag :", ex, file=sys.stderr)
        evs = fusion(evs)
        validation.appliquer(evs); regles_ident.appliquer(evs)   # aussi après la fusion : les décisions portent sur les lignes fusionnées
        synth = aides.synthese(evs)
    except Exception as ex:
        print("aides :", ex, file=sys.stderr)
    for mod in ("cgt_decoupe", "bodacc_details", "suites", "complements", "fermetures", "territoire", "groupes", "lobbying", "sanctions", "bonneboite", "mobilisations", "accords", "operations", "programmes_etat", "reprise", "liens_societes", "direction", "doublons"):          # chacun dans son bloc : une panne de l'un n'empêche pas les autres
        try:
            __import__(mod).enrichir(evs)
        except Exception as ex:
            print(mod, ":", ex, file=sys.stderr)
    # première apparition de chaque événement dans le tracker (pour « nouveau depuis votre dernière visite »)
    db.execute("create table if not exists vu(id text primary key, d text)")
    maint = dt.datetime.now(dt.timezone.utc).isoformat(timespec="minutes"); lim = (dt.date.today() - dt.timedelta(days=3)).isoformat()
    for e in evs:
        if not e.get("id"): continue
        r = db.execute("select d from vu where id=?", (e["id"],)).fetchone()
        if not r:
            d0 = (e.get("date_publication") or e.get("date") or "")[:10]
            v = "2000-01-01T00:00+00:00" if not d0 else (maint if d0 >= lim else d0 + "T12:00+00:00")   # sans date (CGT) : jamais « nouveau »     # déjà ancien au premier passage : daté de sa publication
            db.execute("insert into vu values(?,?)", (e["id"], v)); r = (v,)
        e["vu_le"] = r[0]
    db.commit()
    import commun
    for e in evs:
        if commun.exclu_totaux(e): e["exclu_totaux"] = True
    par_siren = {}
    for e in sorted([e for e in evs if e.get("date")], key=lambda e: e["date"]):
        if not e.get("siren"): e["evenement_id"] = e.get("id"); continue
        L = par_siren.setdefault(e["siren"], [])
        if L and (dt.date.fromisoformat(e["date"][:10]) - dt.date.fromisoformat(L[-1][1][:10])).days <= 180: L[-1][1] = e["date"]
        else: L.append([f"{e['siren']}-{e['date'][:7]}", e["date"]])
        e["evenement_id"] = L[-1][0]
    for e in evs:
        e.setdefault("evenement_id", e.get("id"))
    evs.sort(key=lambda e: e.get("date") or "", reverse=True)
    out = {"credit": commun.CREDIT, "licence": commun.LICENCE, "contact": "quentinclosset@gmail.com",
           "maj": dt.datetime.now(dt.timezone.utc).isoformat(timespec="minutes"), "seuil_salaries": SEUIL,
           "n": len(evs), "synthese": synth, "evenements": evs}
    tmp = os.path.join(HERE, "public", "data.json.tmp")
    json.dump(out, open(tmp, "w"), ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, os.path.join(HERE, "public", "data.json"))
    print("data.json : %d événements" % len(evs), file=sys.stderr)
