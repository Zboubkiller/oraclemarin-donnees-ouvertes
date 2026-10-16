"""Argent public et comptes des entreprises du tracker (recoupement par SIREN).
- Commande publique : DECP v3 (data.economie.gouv.fr). Les accords-cadres (plafonds pluriannuels, souvent partagés entre
  plusieurs titulaires) et les marchés en co-traitance sont comptés à part : seuls les marchés fermes à titulaire unique
  forment le « montant notifié ».
- Aides de l'ADEME (data.ademe.fr) : aides réelles, datées, par SIRET.
- Aides d'État de minimis (registre public, aides octroyées depuis 2026).
- Comptes : chiffre d'affaires et résultat net (API Recherche d'entreprises, comptes déposés).
- Fiabilité du rapprochement (champ `lien`) :
    siren_source   le SIREN vient de la source (BODACC)
    nom+dep        nom exact, l'entreprise a un établissement dans le département de l'événement
    nom_seul       nom exact seulement : peut être la maison mère ou un homonyme, montants à titre indicatif
- `avant_annonce` : montants des années strictement antérieures à l'année de l'événement."""
import json, os, re, sqlite3, time, unicodedata, urllib.parse, urllib.request
H = os.path.dirname(os.path.abspath(__file__))
API = "https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets/"
ADEME = "https://data.ademe.fr/data-fair/api/v1/datasets/les-aides-financieres-de-l%27ademe/lines"
RE_API = "https://recherche-entreprises.api.gouv.fr/search"
UA = {"User-Agent": "tracker-plans-sociaux/0.2 (+https://oraclemarin.fr/plans-sociaux/)"}
GROS = {"21", "22", "31", "32", "41", "42", "51", "52", "53"}
db = sqlite3.connect(os.path.join(H, "cache.db"), timeout=120)
db.execute("create table if not exists nom2siren3(cle text primary key, siren text, ts real)")
for t, c in (("aides4", "siren text primary key, js text, ts real"), ("comptes", "siren text primary key, js text, ts real"),
             ("nom2siren2", "cle text primary key, siren text, ts real")):
    db.execute(f"create table if not exists {t}({c})")

def norm(s): return re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFD", (s or "").lower()).encode("ascii", "ignore").decode())
def get(url):
    for i in range(4):
        try: return json.load(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40))
        except Exception: time.sleep(2 + 3 * i)
    return None
def q(ds, select, where, extra=""):
    return get(API + ds + "/records?" + urllib.parse.urlencode({"select": select, "where": where}) + extra)
def cache(table, key, ttl):
    r = db.execute(f"select js, ts from {table} where siren=?", (key,)).fetchone()
    return json.loads(r[0]) if r and time.time() - r[1] < ttl else None
def store(table, key, val): db.execute(f"replace into {table} values(?,?,?)", (key, json.dumps(val), time.time())); db.commit()
def annee(d): return int(d[:4]) if d and d[:4].isdigit() else None
FIN_VALIDES = "2024-02-09"     # le jeu « marchés valides » s'arrête début février 2024 ; le relais est la table decp (decp_ingest.py)
PLAFOND_MARCHE = 1e9          # un marché ferme à titulaire unique au-delà d'1 Md€ est presque toujours une erreur de saisie

def argent_public(siren):
    c = cache("aides4", siren, 7 * 86400)
    if c is not None: return c
    s = int(siren); w = f"titulaire_id_1>={s * 100000} and titulaire_id_1<{(s + 1) * 100000}"
    dec = "decp-v3-marches-valides"
    nat = q(dec, "nature, count(*) as n, sum(montant) as total", w, "&group_by=nature")
    ferme_w = w + ' and lower(nature)!="accord-cadre" and titulaire_id_2 is null'
    an = q(dec, "year(datenotification) as y, count(*) as n, sum(montant) as total", ferme_w, "&group_by=year(datenotification)")
    top = q(dec, "acheteur_nom, sum(montant) as total", ferme_w, "&group_by=acheteur_nom&order_by=total%20desc&limit=3")
    mi = q("aides_minimis", "count(*) as n, sum(montant_esb) as total", f'identifiant_beneficiaire="{siren}"')
    ad = get(ADEME + "?" + urllib.parse.urlencode({"qs": f"idBeneficiaire:{siren}*", "size": 1000,
             "select": "dateConvention,montant,objet,dispositifAide"}))
    if None in (nat, an, mi, ad): return None
    out = {}
    ac = [x for x in nat.get("results", []) if (x.get("nature") or "").lower().startswith("accord")]
    par_an = {str(x["year(datenotification)"]): round(x.get("total") or 0) for x in an.get("results", []) if x.get("year(datenotification)")}
    n_ferme = sum(x.get("n") or 0 for x in an.get("results", []))
    # relais : DECP consolidé (data.gouv.fr) pour les marchés notifiés après la fin du jeu « marchés valides »
    acc = (0, 0)
    try:
        for y, n, t in db.execute("select substr(date,1,4), count(*), sum(montant) from decp where siren=? and n_tit=1 and ac=0 and montant<? "
                                  "and date>=? and date<'2027-01-01' group by 1", (siren, PLAFOND_MARCHE, FIN_VALIDES)):
            par_an[y] = par_an.get(y, 0) + round(t or 0); n_ferme += n
        acc = db.execute("select count(*), coalesce(sum(montant),0) from decp where siren=? and ac=1 and date>=? and date<'2027-01-01'",
                         (siren, FIN_VALIDES)).fetchone()
    except sqlite3.OperationalError:
        pass
    if acc[0]: ac = ac + [{"n": acc[0], "total": acc[1]}]
    if n_ferme or ac:
        out["marches"] = {"n": n_ferme, "total": sum(par_an.values()), "par_annee": par_an,
                          "de": min(par_an, default=""), "a": max(par_an, default=""),
                          "acheteurs": [x["acheteur_nom"] for x in (top or {}).get("results", []) if x.get("acheteur_nom")],
                          "accords_cadres": {"n": sum(x["n"] for x in ac), "plafond": round(sum(x.get("total") or 0 for x in ac))} if ac else None,
                          "url": "https://data.economie.gouv.fr/explore/dataset/decp-v3-marches-valides/table/?q=" + urllib.parse.quote(w)}
    rows = ad.get("results", [])
    if rows:
        pa = {}
        for r in rows:
            y = annee(r.get("dateConvention"))
            if y: pa[str(y)] = pa.get(str(y), 0) + round(r.get("montant") or 0)
        gros = sorted(rows, key=lambda r: -(r.get("montant") or 0))[:2]
        out["ademe"] = {"dates": [[r.get("dateConvention"), round(r.get("montant") or 0), (r.get("objet") or r.get("dispositifAide") or "")[:110]]
                                  for r in sorted(rows, key=lambda r: r.get("dateConvention") or "", reverse=True)[:80]],
                        "n": ad.get("total", len(rows)), "total": round(sum(r.get("montant") or 0 for r in rows)), "par_annee": pa,
                        "exemples": [{"montant": round(r.get("montant") or 0), "date": r.get("dateConvention"),
                                      "objet": (r.get("objet") or r.get("dispositifAide") or "")[:140]} for r in gros],
                        "url": "https://data.ademe.fr/datasets/les-aides-financieres-de-l'ademe"}
    m0 = (mi.get("results") or [{}])[0]
    if m0.get("n"):
        out["minimis"] = {"n": m0["n"], "total": round(m0.get("total") or 0),
                          "url": "https://data.economie.gouv.fr/explore/dataset/aides_minimis/table/?q=" + siren}
    store("aides4", siren, out); time.sleep(0.2)
    return out

def comptes(siren):
    c = cache("comptes", siren, 30 * 86400)
    if c is not None: return c or None
    d = get(RE_API + "?" + urllib.parse.urlencode({"q": siren, "per_page": 1}))
    if d is None: return None
    r = (d.get("results") or [{}])[0]
    f = r.get("finances") if r.get("siren") == siren else None
    out = {y: {"ca": v.get("ca") or None, "resultat_net": v.get("resultat_net") or None} for y, v in (f or {}).items()}   # 0 € = comptes confidentiels ou simplifiés
    store("comptes", siren, out); time.sleep(0.2)
    return out or None

def identite(siren):
    """Secteur (NAF), catégorie (PME, ETI, GE) et tranche d'effectif de l'unité légale (API Recherche d'entreprises, cache 30 jours)."""
    db.execute("create table if not exists ident(siren text primary key, js text, ts real)")
    r = db.execute("select js, ts from ident where siren=?", (siren,)).fetchone()
    if r and time.time() - r[1] < 30 * 86400: return json.loads(r[0])
    d = get(RE_API + "?" + urllib.parse.urlencode({"q": siren, "per_page": 1}))
    if d is None: return None
    e = (d.get("results") or [{}])[0]
    out = {"naf": e.get("activite_principale"), "categorie": e.get("categorie_entreprise"), "tranche": e.get("tranche_effectif_salarie"),
           "nom": e.get("nom_complet")} if e.get("siren") == siren else {}
    db.execute("replace into ident values(?,?,?)", (siren, json.dumps(out), time.time())); db.commit(); time.sleep(0.2)
    return out

MOTS_VIDES = {"sa", "sas", "sasu", "sarl", "eurl", "snc", "france", "groupe", "group", "et", "de", "la", "le", "les", "du", "des", "site", "usine", "societe"}
def mots(s): return {t for t in re.findall(r"[a-z0-9]+", unicodedata.normalize("NFD", (s or "").lower()).encode("ascii", "ignore").decode()) if len(t) > 1 and t not in MOTS_VIDES}
DIX_PLUS = {"11", "12", "21", "22", "31", "32", "41", "42", "51", "52", "53"}
NON_EMPLOYEUR = re.compile(r"\b(comite|cse|amicale|association|syndicat|mutuelle)\b", re.I)

def correspond(nom, r):
    """2 : nom identique ; 1 : tous les mots significatifs du nom cité figurent dans un nom de l'unité légale ; 0 sinon.
    L'API fait une recherche floue (« Ferropem » renvoie une caisse de retraite) : on ne garde que ces deux cas."""
    noms = [r.get("nom_complet"), r.get("nom_raison_sociale"), r.get("sigle"), (r.get("siege") or {}).get("nom_commercial")]
    # pas les enseignes des établissements : un restaurant d'entreprise géré par Elior porte l'enseigne « IBM »
    k = norm(nom)
    if k and k in {norm(n) for n in noms if n}: return 2
    q = mots(nom)
    return 1 if q and any(q <= mots(n) for n in noms if n) else 0

def corrections_manuelles():
    try: return json.load(open(os.path.join(H, "rapprochements.json"), encoding="utf-8"))
    except Exception: return {}
REFUS = {(norm(r["cite"]), r["siren"]) for r in corrections_manuelles().get("refus", [])}

def identifier(nom, dep, insee):
    """(siren, lien, siret) ou (None, motif, None). Trois essais, du plus précis au plus large :
    1. un établissement actif de l'entreprise dans la commune de l'annonce  -> « siret_commune » (sûr) ;
    2. l'entreprise a un établissement dans le département, 50 salariés ou plus -> « nom+dep » (probable) ;
    3. nom identique au niveau national, 50 salariés ou plus                 -> « nom_seul » (indicatif).
    Deux entreprises différentes à égalité : on ne choisit pas (homonymes)."""
    k = norm(nom)
    if len(k) < 3: return None, None, None
    sigle = len(mots(nom)) <= 1 and len(k) <= 4          # « ACC », « AIM », « SMP » : trop ambigus sans nom identique
    essais = [("siret_commune", {"code_commune": insee}) if insee else None, ("nom+dep", {"departement": dep}) if dep else None, ("nom_seul", {})]
    for essai in [x for x in essais if x]:
        lien, params = essai
        ck = f"{k}|{lien}|{params.get('code_commune') or params.get('departement') or ''}"
        r = db.execute("select siren, ts from nom2siren3 where cle=?", (ck,)).fetchone()
        if r and time.time() - r[1] < 30 * 86400:
            if r[0]:
                s, _, siret = r[0].partition("|"); return s, lien, siret or None
            continue
        d = get(RE_API + "?" + urllib.parse.urlencode({"q": nom, "per_page": 10, **params}))
        if d is None: continue
        cands = {}
        for x in d.get("results", []):
            cp = x.get("complements") or {}
            if x.get("etat_administratif") != "A" or NON_EMPLOYEUR.search(x.get("nom_complet") or "") or cp.get("est_association") or cp.get("est_entrepreneur_individuel"): continue
            m = correspond(nom, x)
            if not m or (k, x["siren"]) in REFUS: continue
            if sigle and (m < 2 or lien == "nom_seul"): continue
            etab = next((y for y in x.get("matching_etablissements") or [] if y.get("commune") == insee and y.get("etat_administratif") == "A"), None) if lien == "siret_commune" else None
            gros = x.get("tranche_effectif_salarie") in GROS
            # nom seulement contenu (« Epicure » dans « Agence Epicure ») : il faut au moins 10 salariés dans l'entreprise ou l'établissement
            if m == 1 and not (gros or x.get("tranche_effectif_salarie") in DIX_PLUS or (etab or {}).get("tranche_effectif_salarie") in DIX_PLUS): continue
            if lien == "siret_commune" and not etab: continue
            if lien == "nom+dep" and not gros: continue
            if lien == "nom_seul" and not (m == 2 and gros): continue
            score = 2 * m + (1 if gros else 0)
            if x["siren"] not in cands or cands[x["siren"]][0] < score: cands[x["siren"]] = (score, (etab or {}).get("siret"))
        choix = None
        if cands:
            tri = sorted(cands.items(), key=lambda kv: -kv[1][0])
            if len(tri) == 1 or tri[0][1][0] > tri[1][1][0]: choix = tri[0]
        val = f"{choix[0]}|{choix[1][1] or ''}" if choix else ""
        db.execute("replace into nom2siren3 values(?,?,?)", (ck, val, time.time())); db.commit(); time.sleep(0.25)
        if choix: return choix[0], lien, choix[1][1]
    return None, None, None

try:
    import relance as _rel; _rel.charge(db)
except Exception as _e:
    print("relance :", _e)

def mois(d): return int(d[:4]) * 12 + int(d[5:7]) if d and len(d) >= 7 and d[:4].isdigit() else None

def proximite(e, a, fenetre=24):
    """Aides datées (ADEME, lauréat France Relance) dans les `fenetre` mois précédant l'annonce. Précision : le mois."""
    me = mois(e.get("date"))
    if me is None: return None
    items = [{"source": "ADEME", "date": d, "montant": m, "libelle": o} for d, m, o in ((a or {}).get("ademe") or {}).get("dates", [])]
    items += [{"source": "France Relance", "date": r["date"], "montant": None, "libelle": r["mesure"] + " : " + r["projet"][:100]}
              for r in e.get("relance", [])]
    dans = []
    for i in items:
        mi = mois(i.get("date"))
        if mi is not None and 0 <= me - mi <= fenetre: dans.append({**i, "delai_mois": me - mi})
    if not dans: return None
    dans.sort(key=lambda i: i["delai_mois"])
    return {"fenetre_mois": fenetre, "n": len(dans), "montant": sum(i["montant"] or 0 for i in dans),
            "plus_recente": dans[0], "plus_grosse": max(dans, key=lambda i: i["montant"] or 0)}

db.execute("create table if not exists marches_l(siren text primary key, js text, ts real)")

def marches_lignes(siren):
    """[date, montant, durée en mois] des marchés fermes à titulaire unique (hors accords-cadres)."""
    c = cache("marches_l", siren, 7 * 86400)
    if c is not None: return c
    s = int(siren); w = (f"titulaire_id_1>={s * 100000} and titulaire_id_1<{(s + 1) * 100000} and lower(nature)!=\"accord-cadre\" "
                         f"and titulaire_id_2 is null and datenotification<\"{FIN_VALIDES}\"")
    rows, off = [], 0
    while off < 3000:
        d = q("decp-v3-marches-valides", "datenotification, montant, dureemois", w, f"&limit=100&offset={off}&order_by=datenotification")
        if d is None: return None
        r = d.get("results", [])
        rows += [[(x.get("datenotification") or "")[:10], x.get("montant") or 0, x.get("dureemois")] for x in r]
        if len(r) < 100: break
        off += 100
    try:
        rows += [[d0, m, du] for d0, m, du in db.execute(
            "select date, montant, duree from decp where siren=? and n_tit=1 and ac=0 and montant<? and date>=? and date<'2027-01-01'", (siren, PLAFOND_MARCHE, FIN_VALIDES))]
    except sqlite3.OperationalError:
        pass
    store("marches_l", siren, rows)
    return rows

def part_commande_publique(rows, annee):
    """Part estimée du CA venant de marchés publics notifiés avant/pendant `annee` : chaque marché est étalé sur sa durée."""
    deb, fin = annee * 12, annee * 12 + 12          # mois absolus [deb, fin)
    tot, n = 0.0, 0
    for d, m, du in rows:
        mo = mois(d)
        if mo is None or not m or not (2015 <= int(d[:4]) <= annee): continue
        du = min(max(int(du or 12), 1), 120)
        ov = min(mo + du, fin) - max(mo, deb)
        if ov > 0: tot += m * ov / du; n += 1
    return round(tot), n

def avant(par_an, an_evt):
    return sum(v for y, v in par_an.items() if int(y) < an_evt) if an_evt else None

def dep_code(x):
    """« 60 », « Oise », « 2A » -> code département, sinon None."""
    if not x: return None
    x = str(x).strip()
    if re.fullmatch(r"\d{2,3}|2[AB]", x, re.I): return x.upper().zfill(2) if len(x) < 3 else x
    import commun
    inv = {norm(v): k for k, v in commun.DEPS.items()}
    return inv.get(norm(x))

db.execute("create table if not exists aides_gpid(k text primary key, js text, ts real)")
def contrats_gpid():
    """Contrats de soutien de l'appel d'offres « Grands projets industriels de décarbonation » (ADEME) : montants de contrats pluriannuels attribués (plafonds de soutien), pas des aides versées.
    Ils sont retirés des totaux d'aides et présentés à part. Retourne l'ensemble des couples (date, montant arrondi)."""
    r = db.execute("select js, ts from aides_gpid where k='all'").fetchone()
    if r and time.time() - r[1] < 86400: return {tuple(x) for x in json.loads(r[0])}
    d = get(ADEME + "?" + urllib.parse.urlencode({"size": 500, "sort": "-montant", "select": "dateConvention,montant,dispositifAide"}))        # les plus gros montants d'abord, filtre côté client (le filtre sur le dispositif ne fonctionne pas)
    if d is not None: d = {"results": [x for x in d.get("results", []) if "Grands Projets Industriels" in (x.get("dispositifAide") or "")]}
    if d is None: return {tuple(x) for x in json.loads(r[0])} if r else set()
    L = [[x.get("dateConvention"), round(x.get("montant") or 0)] for x in d.get("results", [])]
    db.execute("replace into aides_gpid values('all', ?, ?)", (json.dumps(L), time.time())); db.commit()
    return {tuple(x) for x in L}

def enrichir(evs):
    try:
        import gemini_ident; IA = gemini_ident.extraire(evs)
    except Exception as ex:
        print("gemini_ident :", ex); IA = {}
    GP = contrats_gpid()
    for e in evs:
        ia = IA.get(e.get("id")) if not e.get("siren") else None
        if ia and ia.get("est_entreprise") is False and not ia.get("entreprise"): e["sans_entreprise"] = True
        if ia and ia.get("en_france") is False and not str(e.get("source", "")).startswith("CGT"): e["hors_france"] = True   # la liste CGT ne recense que la France   # article sans employeur nommé (les employeurs publics restent visibles)
        if e.get("siren_rapproche") and not e.get("lien"): e.pop("siren_rapproche", None)   # sorties de la v1
        if e.get("siren") and not e.get("lien"): e["lien"] = "siren_source"
        if not e.get("siren") and e.get("entreprise") and e.get("entreprise") != e.get("titre"):
            try:
                import territoire; insee = territoire.insee_de(e) if not (str(e.get("source", "")).startswith("CGT") and e.get("approx")) else None
            except Exception:
                insee = None
            s, lien, siret = identifier(e["entreprise"], e.get("dep"), insee)
            if not s and ia and (ia.get("entreprise") or ia.get("commune")) and not e.get("sans_entreprise"):
                # second essai : nom et commune lus dans le texte par Gemini, puis le même rapprochement strict
                dep2 = dep_code(ia.get("departement")) or e.get("dep")
                ins2 = None
                if ia.get("commune"):
                    try:
                        import territoire; ins2 = territoire.COM.get((territoire.norm(ia["commune"]), dep2)) if dep2 else None
                    except Exception: ins2 = None
                s, lien, siret = identifier(ia.get("entreprise") or e["entreprise"], dep2, ins2 or insee)
                if s: e["ident_ia"] = True
                if ins2 and not e.get("commune") or (ins2 and e.get("approx") and str(e.get("source", "")).startswith("CGT")):
                    e.update(commune=ia["commune"], dep=dep2, insee=ins2, approx=False, commune_ia=True)
            if s:
                e["siren"] = s; e["lien"] = lien; e["siren_rapproche"] = True
                if siret: e["siret"] = siret
        if not e.get("siren"): continue
        an_evt = annee(e.get("date"))
        a = argent_public(e["siren"])
        if a:
            if a.get("marches") and a["marches"].get("accords_cadres") is None: a["marches"].pop("accords_cadres", None)
            ar = {k: v for k, v in a.items()}
            if a.get("ademe") and GP:
                dates = a["ademe"].get("dates", []); gp = [d for d in dates if (d[0], d[1]) in GP]
                if gp:
                    reste = [d for d in dates if (d[0], d[1]) not in GP]
                    ar["contrats_soutien"] = [{"date": d[0], "montant": d[1], "objet": d[2]} for d in gp]
                    if reste:
                        pa = {}
                        for d in reste:
                            y = annee(d[0])
                            if y: pa[str(y)] = pa.get(str(y), 0) + d[1]
                        ar["ademe"] = {**a["ademe"], "dates": reste, "n": len(reste), "total": sum(d[1] for d in reste), "par_annee": pa,
                                       "exemples": [x for x in a["ademe"].get("exemples", []) if (x.get("date"), x.get("montant")) not in GP]}
                    else: ar.pop("ademe", None)
            av = {k: avant(ar[k]["par_annee"], an_evt) for k in ("marches", "ademe") if ar.get(k) and ar[k].get("par_annee")}
            if av and an_evt:
                ar["avant_annonce"] = {"annee": an_evt, "total": sum(v or 0 for v in av.values()), **av}
            e["argent_public"] = ar
        idt = identite(e["siren"])
        if idt:
            e.setdefault("naf", idt.get("naf")); e["categorie"] = idt.get("categorie")
        rl = [json.loads(r[0]) for r in db.execute("select js from relance where siren=?", (e["siren"],))]
        if rl: e["relance"] = rl
        c = comptes(e["siren"])
        if c:
            ys = sorted(c)
            ans = [y for y in ys if c[y].get("resultat_net")]   # 0 € (cache ancien) = non publié
            last = ans[-1] if ans else None
            e["comptes"] = {"derniere_annee": last, "ca": c[last].get("ca") if last else None,
                            "resultat_net": c[last].get("resultat_net") if last else None,
                            "profitable": (c[last]["resultat_net"] > 0) if last else None,
                            "annees_benefice": sum(1 for y in ans if c[y]["resultat_net"] > 0), "annees": len(ans),
                            "serie": {y: c[y]["resultat_net"] for y in ans[-4:]},
                            "profitable_3ans": (len(ans) >= 3 and all(c[y]["resultat_net"] > 0 for y in ans[-3:])) if ans else None,
                            "url": "https://annuaire-entreprises.data.gouv.fr/entreprise/" + e["siren"]}
        cc = e.get("comptes")
        if cc and cc.get("profitable") and e.get("date") and cc.get("derniere_annee"):
            import datetime as _dt
            ecart = int(e["date"][:4]) - int(cc["derniere_annee"]); recent = e["date"][:10] >= (_dt.date.today() - _dt.timedelta(days=365)).isoformat()
            if ecart >= 2 and not (ecart == 2 and recent):      # comptes d'au moins 2 ans plus anciens que l'annonce (hors annonce récente : les derniers comptes ne sont pas encore publiés)
                cc["profitable"] = None; cc["comptes_trop_anciens"] = True
        try: SANS_ALERTE = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "sans_alerte_benefice.json"), encoding="utf-8"))
        except Exception: SANS_ALERTE = {}
        if cc and e.get("id") in SANS_ALERTE: cc["profitable"] = None; cc["alerte_neutralisee"] = True
        pr = proximite(e, e.get("argent_public"))
        if pr: e["proximite"] = pr
        aides24 = (pr or {}).get("montant") or 0
        r = {}
        if e.get("emplois_min") and aides24: r["aide_par_emploi"] = round(aides24 / e["emplois_min"])
        rn = (e.get("comptes") or {}).get("resultat_net")
        if rn and rn > 0 and aides24: r["aide_sur_benefice_pct"] = round(100 * aides24 / rn, 2)
        if r: e["ratios"] = r
        # fiable = identification sûre + comptes récents (au plus 2 ans avant l'annonce)
        da, ya = (e.get("comptes") or {}).get("derniere_annee"), annee(e.get("date"))
        e["fiable"] = bool(e.get("lien") in ("siren_source", "siret_commune", "nom+dep") and da and ya and 0 <= ya - int(da) <= 2)
        ca = (e.get("comptes") or {}).get("ca")
        if e["fiable"] and ca and ca > 0 and int(da) <= 2025:
            rows = marches_lignes(e["siren"])
            if rows is not None:
                est, nm = part_commande_publique(rows, int(da))
                if nm and est > 0 and est <= ca:        # au-delà du CA : donnée incohérente, on n'affiche rien
                    e["dependance_publique"] = {"annee": int(da), "estimation": est, "ca": ca, "part_pct": round(100 * est / ca, 1), "n_marches": nm}
    return evs

def synthese(evs):
    """Chiffres clés, comptés par entreprise (SIREN) et uniquement sur les rapprochements fiables."""
    uniq = lambda L: list({e["siren"]: e for e in L}.values())
    plan = [e for e in evs if e["type"] in ("plan social", "fermeture") and e.get("siren") and e.get("comptes")]
    fiab = uniq([e for e in plan if e.get("fiable")])
    ben = [e for e in fiab if e["comptes"]["profitable"]]
    prox = uniq([e for e in evs if e.get("proximite") and e.get("fiable")
                 and (e["proximite"]["montant"] >= 50000 or e["proximite"]["plus_recente"]["source"] == "France Relance")])
    return {"plans_avec_comptes_fiables": len(fiab), "dont_benefice": len(ben),
            "cas_benefice": sorted([{"entreprise": e["entreprise"], "date": e.get("date"), "emplois": e.get("emplois_min"), "siren": e["siren"],
                                     "resultat_net": e["comptes"]["resultat_net"], "annee_comptes": e["comptes"]["derniere_annee"]} for e in ben],
                                   key=lambda c: -(c["emplois"] or 0))[:12],
            "proximite_aide_24_mois": len(prox),
            "cas_proximite": sorted([{"entreprise": e["entreprise"], "date": e.get("date"), "emplois": e.get("emplois_min"), "siren": e["siren"],
                                      **{k: e["proximite"][k] for k in ("n", "montant", "plus_recente")}} for e in prox],
                                    key=lambda c: -c["montant"])[:12],
            "cas_dependance": sorted([{"entreprise": e["entreprise"], "date": e.get("date"), "emplois": e.get("emplois_min"), "siren": e["siren"],
                                       **e["dependance_publique"]} for e in uniq([x for x in evs if x.get("dependance_publique") and x["dependance_publique"]["part_pct"] >= 20])],
                                     key=lambda c: -c["part_pct"])[:12],
            "definition": "Entreprises distinctes (SIREN), plans sociaux et fermetures, identification sûre (SIREN fourni, établissement de l'entreprise dans la commune, ou nom avec établissement dans le département) et comptes d'un exercice antérieur ou égal à l'année de l'annonce (au plus 2 ans avant). Un seul exercice (le dernier publié) est disponible par entreprise : « bénéficiaire » signifie résultat net positif sur cet exercice."}
