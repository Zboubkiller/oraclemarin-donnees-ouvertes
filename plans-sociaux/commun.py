"""Briques communes aux pages générées (accueil, pages thématiques, départements) : chargement des données, « faits du
jour » (phrases chiffrées et datées, réutilisées dans la FAQ, le llms.txt, les données structurées et l'image de partage),
gabarit HTML des pages secondaires."""
import json, os, html, sqlite3, datetime as dt

H = os.path.dirname(os.path.abspath(__file__))
PUB = os.path.join(H, "public")
BASE_URL = "https://oraclemarin.fr/plans-sociaux"
BASE = "/plans-sociaux"
NOM = "Plans sociaux et faillites en France"
EDITEUR = "Quentin Closset"
CONTACT = "quentinclosset@gmail.com"
RUPTURES = {"57", "67", "68"}        # Alsace-Moselle : rupture de série BODACC fin 2025 (voir la page méthode)

DEPS = {"01": "Ain", "02": "Aisne", "03": "Allier", "04": "Alpes-de-Haute-Provence", "05": "Hautes-Alpes", "06": "Alpes-Maritimes",
        "07": "Ardèche", "08": "Ardennes", "09": "Ariège", "10": "Aube", "11": "Aude", "12": "Aveyron", "13": "Bouches-du-Rhône",
        "14": "Calvados", "15": "Cantal", "16": "Charente", "17": "Charente-Maritime", "18": "Cher", "19": "Corrèze", "2A": "Corse-du-Sud",
        "2B": "Haute-Corse", "21": "Côte-d'Or", "22": "Côtes-d'Armor", "23": "Creuse", "24": "Dordogne", "25": "Doubs", "26": "Drôme",
        "27": "Eure", "28": "Eure-et-Loir", "29": "Finistère", "30": "Gard", "31": "Haute-Garonne", "32": "Gers", "33": "Gironde",
        "34": "Hérault", "35": "Ille-et-Vilaine", "36": "Indre", "37": "Indre-et-Loire", "38": "Isère", "39": "Jura", "40": "Landes",
        "41": "Loir-et-Cher", "42": "Loire", "43": "Haute-Loire", "44": "Loire-Atlantique", "45": "Loiret", "46": "Lot",
        "47": "Lot-et-Garonne", "48": "Lozère", "49": "Maine-et-Loire", "50": "Manche", "51": "Marne", "52": "Haute-Marne",
        "53": "Mayenne", "54": "Meurthe-et-Moselle", "55": "Meuse", "56": "Morbihan", "57": "Moselle", "58": "Nièvre", "59": "Nord",
        "60": "Oise", "61": "Orne", "62": "Pas-de-Calais", "63": "Puy-de-Dôme", "64": "Pyrénées-Atlantiques", "65": "Hautes-Pyrénées",
        "66": "Pyrénées-Orientales", "67": "Bas-Rhin", "68": "Haut-Rhin", "69": "Rhône", "70": "Haute-Saône", "71": "Saône-et-Loire",
        "72": "Sarthe", "73": "Savoie", "74": "Haute-Savoie", "75": "Paris", "76": "Seine-Maritime", "77": "Seine-et-Marne",
        "78": "Yvelines", "79": "Deux-Sèvres", "80": "Somme", "81": "Tarn", "82": "Tarn-et-Garonne", "83": "Var", "84": "Vaucluse",
        "85": "Vendée", "86": "Vienne", "87": "Haute-Vienne", "88": "Vosges", "89": "Yonne", "90": "Territoire de Belfort",
        "91": "Essonne", "92": "Hauts-de-Seine", "93": "Seine-Saint-Denis", "94": "Val-de-Marne", "95": "Val-d'Oise",
        "971": "Guadeloupe", "972": "Martinique", "973": "Guyane", "974": "La Réunion", "976": "Mayotte"}

MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
MOIS_C = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]
esc = lambda s: html.escape(str(s if s is not None else ""), quote=True)
def fr(n): return f"{int(round(n)):,}".replace(",", " ")
def pct(v, dec=1):
    if v is None: return "—"
    s = f"{abs(v):.{dec}f}".replace(".", ",").replace(",0", "") if dec else str(abs(round(v)))
    return ("+" if v > 0 else "−" if v < 0 else "") + s + " %"
def eu(n):
    s, v = ("−" if n < 0 else ""), abs(n)
    return s + (f"{v/1e9:.1f} Md€".replace(".", ",") if v >= 1e9 else f"{v/1e6:.1f} M€".replace(".", ",") if v >= 1e6 else fr(v) + " €")
def mois_long(m): return f"{MOIS[int(m[5:7]) - 1]} {m[:4]}"
def de_mois(m):
    """« de mars 2026 », mais « d'août 2025 » : élision devant voyelle."""
    s = mois_long(m); return ("d'" if s[0] in "aeiouéâ" else "de ") + s
def de_nom(n):
    """« de Grenoble », « d'Amiens », « du Havre », « des Sables-d'Olonne »."""
    n = n or ""
    if n.startswith("Le "): return "du " + n[3:]
    if n.startswith("Les "): return "des " + n[4:]
    return ("d'" if n[:1].lower() in "aeiouyéèêâîôû" else "de ") + n
def mois_court(m): return f"{MOIS_C[int(m[5:7]) - 1]} {m[:4]}"
def date_long(d):
    try: x = dt.date.fromisoformat(d[:10]); return f"{x.day}{'er' if x.day == 1 else ''} {MOIS[x.month - 1]} {x.year}"
    except Exception: return d or ""
def slug(s):
    import unicodedata, re
    return re.sub(r"[^a-z0-9]+", "-", unicodedata.normalize("NFD", s.lower()).encode("ascii", "ignore").decode()).strip("-")
REGIONS = {}
for _r, _ds in (("Auvergne-Rhône-Alpes", "01 03 07 15 26 38 42 43 63 69 73 74"), ("Bourgogne-Franche-Comté", "21 25 39 58 70 71 89 90"),
                ("Bretagne", "22 29 35 56"), ("Centre-Val de Loire", "18 28 36 37 41 45"), ("Corse", "2A 2B"),
                ("Grand Est", "08 10 51 52 54 55 57 67 68 88"), ("Hauts-de-France", "02 59 60 62 80"), ("Île-de-France", "75 77 78 91 92 93 94 95"),
                ("Normandie", "14 27 50 61 76"), ("Nouvelle-Aquitaine", "16 17 19 23 24 33 40 47 64 79 86 87"),
                ("Occitanie", "09 11 12 30 31 32 34 46 48 65 66 81 82"), ("Pays de la Loire", "44 49 53 72 85"),
                ("Provence-Alpes-Côte d'Azur", "04 05 06 13 83 84"), ("Outre-mer", "971 972 973 974 976")):
    for _d in _ds.split(): REGIONS[_d] = _r

SECTIONS = [(1, 3, "Agriculture"), (5, 9, "Industries extractives"), (10, 33, "Industrie manufacturière"), (35, 35, "Énergie"),
            (36, 39, "Eau, déchets"), (41, 43, "Construction"), (45, 47, "Commerce"), (49, 53, "Transports et entreposage"),
            (55, 56, "Hébergement, restauration"), (58, 63, "Information, communication"), (64, 66, "Finance, assurance"),
            (68, 68, "Immobilier"), (69, 75, "Services spécialisés"), (77, 82, "Services administratifs et soutien"),
            (84, 84, "Administration"), (85, 85, "Enseignement"), (86, 88, "Santé, action sociale"), (90, 93, "Arts, loisirs"),
            (94, 96, "Autres services")]
def secteur(naf):
    try: d = int((naf or "")[:2])
    except ValueError: return None
    return next((l for a, b, l in SECTIONS if a <= d <= b), None)

import re as _re
NATURES = ("suppressions annoncées", "départs volontaires", "emplois menacés")
def nature_emplois(e):
    """Nature des emplois concernés, d'après le type d'événement et le texte de la source :
    départs volontaires (rupture conventionnelle collective, plan de départs) ; emplois menacés (redressement, sauvegarde,
    recherche de repreneur) ; sinon suppressions annoncées (PSE, licenciements, fermeture, liquidation). « Menacés » dans un titre
    de presse ne suffit pas : il s'emploie aussi pour des fermetures actées."""
    t = ((e.get("detail") or "") + " " + (e.get("titre") or "")).lower()
    if _re.search(r"ruptures? conventionnelles? collectives?|départs? volontaires?|\brcc\b|plan de départs", t): return NATURES[1]
    if e.get("type") in ("liquidation", "fermeture") or _re.search(r"liquidation|ferm(e|eture|er)|cessation d.activité|arrêt de (la )?production", t): return NATURES[0]
    if e.get("type") in ("redressement", "sauvegarde") or _re.search(r"redressement|sauvegarde|repreneur|offres? de reprise", t): return NATURES[2]
    return NATURES[0]

CREDIT = "Plans sociaux et faillites en France, oraclemarin.fr/plans-sociaux, Quentin Closset (quentinclosset@gmail.com)"
LICENCE_URL = "https://creativecommons.org/licenses/by-nc-sa/4.0/deed.fr"
LICENCE = ("Licence CC BY-NC-SA 4.0 (mention de la source, pas d'usage commercial, partage dans les mêmes conditions) ; la presse, la recherche, les syndicats et les "
           "associations peuvent réutiliser librement, y compris dans un article ou une infographie. Usage commercial : demander l'accord de l'éditeur. "
           "Les données publiques d'origine gardent leur propre licence. Mention : « Plans sociaux et faillites en France, oraclemarin.fr/plans-sociaux »")

def empreinte(ident):
    """Empreinte d'une ligne : HMAC de son identifiant avec une clé secrète. Permet de prouver qu'une ligne reprise ailleurs vient
    de ce jeu de données (seul l'éditeur peut recalculer l'empreinte), sans altérer les données."""
    import hmac, hashlib
    try: cle = dict(l.strip().split("=", 1) for l in open(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")) if "=" in l).get("DATA_SECRET", "")
    except OSError: cle = ""
    return hmac.new(cle.encode(), str(ident).encode(), hashlib.sha256).hexdigest()[:12] if cle else ""

_DOUTEUX_DEBUT = _re.compile(r"^(c est|pres de|dans |en |ce |cet |cette |ces |voici|comment|pourquoi|apres|avant|face a|suite a|vers |sur |avec |pour |\\d|des |une |un |plusieurs|trois |deux |quatre |cinq |coupes |postes |emplois |salaries )")
_DOUTEUX_MOTS = _re.compile(r"\\b(menaces?|salaries|suppressions?|licenciements?|emplois|postes|carreau|confirme|plan social|redressement|liquidation|manifestation|greve)\\b")
_ZONES = None

def _sans(x):
    import unicodedata
    return _re.sub(r"[^a-z0-9 ]", " ", unicodedata.normalize("NFD", (x or "").lower().replace("\u2019", "'")).encode("ascii", "ignore").decode()).strip()

def nom_douteux(nom, sources=(), titre=None):
    """Vrai si le « nom d'entreprise » lu par l’IA est en fait un morceau du titre (début de phrase, « 67 emplois menacés »), le nom d'un
    département, d'une région ou d'un média : il ne faut ni l’afficher comme employeur ni chercher une société avec lui."""
    global _ZONES
    n = _sans(nom)
    if not n: return False
    if _ZONES is None:
        try:
            import collect; _ZONES = {_sans(v) for v in collect.DEPARTEMENTS.values()}
        except Exception: _ZONES = set()
        _ZONES |= {_sans(x) for x in ("Île-de-France", "Pays de la Loire", "Bretagne", "Normandie", "Hauts-de-France", "Grand Est", "Nouvelle-Aquitaine", "Occitanie",
                   "Auvergne-Rhône-Alpes", "Bourgogne-Franche-Comté", "Centre-Val de Loire", "Provence-Alpes-Côte d'Azur", "PACA", "Corse", "Alsace", "Lorraine")}
    n2 = n.replace("'", " ").strip()
    return bool(_DOUTEUX_DEBUT.match(n2 + " ") or _DOUTEUX_MOTS.search(n2) or n2 in _ZONES or (n2 in {_sans(x) for x in sources} and (titre is None or _re.sub(r"^(le|la|les|l) ", "", n2) not in _sans(titre))))

def exclu_totaux(e):
    """Annonces écartées des totaux d'emplois : fermeture Sirene sans article de presse, pas d'entreprise précise, entreprise non identifiée, hors de France, ou très gros
    chiffre de presse (5 000 emplois et plus) sans entreprise française identifiée (souvent un plan mondial ou un secteur entier)."""
    if e.get("source") == "BODACC": return False
    if e.get("doublon_de"): return True        # même plan déjà compté sur une autre annonce (voir doublons.py)
    if e.get("employeur_public"): return True   # État, collectivité, établissement public (catégorie juridique Sirene 7) : pas une entreprise, hors des totaux
    if e.get("partie_de"): return True          # société rattachée à un plan multi-sociétés : les emplois sont comptés une fois, sur l'annonce d'origine
    # fermeture d'établissement vue dans Sirene : l'effectif est celui du site avant fermeture, pas un nombre de licenciements ;
    # comptée seulement si un article de presse confirme des pertes d'emplois
    if str(e.get("source", "")).startswith("Sirene") and not e.get("sources"): return True
    if e.get("sans_entreprise") or e.get("hors_france") or (e.get("entreprise") and e.get("entreprise") == e.get("titre")): return True
    presse = not str(e.get("source", "")).startswith("CGT") and e.get("source") != "Accords d'entreprise"
    n = e.get("emplois_min") or 0
    if presse and e.get("en_france") is None and "en_france" in e and not e.get("siren") and not e.get("dep"): return True   # pays inconnu, rien de localisable
    return bool(presse and (n >= 5000 or (not e.get("siren") and n >= 5000)))   # 5 000 et plus en presse : plan mondial ou estimation, pas une annonce française vérifiable

PAYS = ["Inde", "Chine", "Maroc", "Tunisie", "Algérie", "Turquie", "Roumanie", "Pologne", "Hongrie", "Bulgarie", "République tchèque", "Tchéquie",
        "Slovaquie", "Portugal", "Espagne", "Italie", "Allemagne", "Belgique", "Pays-Bas", "Irlande", "Royaume-Uni", "Suisse", "Serbie", "Ukraine",
        "Vietnam", "Viêt Nam", "Thaïlande", "Malaisie", "Indonésie", "Philippines", "Bangladesh", "Mexique", "Brésil", "États-Unis", "Canada", "Égypte",
        "Madagascar", "Maurice", "Sénégal", "Slovénie", "Croatie", "Lituanie", "Lettonie", "Estonie", "Grèce", "Asie", "Europe de l'Est", "Afrique du Nord", "Maghreb"]
_PAYS_RE = _re.compile(r"\b(" + "|".join(sorted(map(_re.escape, PAYS), key=len, reverse=True)) + r")\b")
def delocalisation(e):
    """{'pays': … ou None} si la source parle de délocalisation ou de transfert de production à l'étranger, sinon None."""
    t = (e.get("detail") or "") + " " + (e.get("titre") or "")
    m = _re.search(r"délocalis\w*|transf[eé]r\w* (?:de (?:la )?production|d.activité|de l.activité)|production (?:sera )?transférée", t, _re.I)
    if not m: return None
    p = _PAYS_RE.search(t[m.start():m.start() + 160]) or _PAYS_RE.search(t)
    return {"pays": p.group(1) if p else None}

def cle_nom(s):
    import unicodedata
    return _re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFD", (s or "").lower()).encode("ascii", "ignore").decode())[:12]

def dep_url(code, absolu=False): return f"{BASE_URL if absolu else BASE}/departement/{code.lower()}-{slug(DEPS.get(code, code))}/"

def lire(nom, defaut=None):
    try: return json.load(open(os.path.join(PUB, nom), encoding="utf-8"))
    except Exception: return defaut

def charge():
    return {"data": lire("data.json", {"evenements": [], "maj": dt.datetime.now(dt.timezone.utc).isoformat()}),
            "tendance": lire("tendance.json", {}), "officiel": lire("officiel.json", {}), "compteur": lire("compteur.json", {})}

def tend_dep():
    """{(mois, dep): n} des jugements d'ouverture (tous effectifs) depuis cache.db."""
    try:
        db = sqlite3.connect(os.path.join(H, "cache.db"), timeout=60)
        return {(m, d): n for m, d, n in db.execute("select m, dep, n from tend_dep")}
    except sqlite3.OperationalError:
        return {}

def faits(D):
    """Les chiffres clés du jour, chacun avec sa source et sa date : base de la FAQ, du llms.txt et de l'image de partage."""
    o, c, t = D["officiel"] or {}, D["compteur"] or {}, D["tendance"] or {}
    f = {"aujourdhui": dt.date.today().isoformat()}
    de = o.get("defaillances")
    if de:
        f["bdf"] = {"n": de["cumul_12_mois"], "var": de.get("variation_pct"), "mois": de["dernier_mois"], "n_avant": de.get("cumul_12_mois_an_avant"),
                    "debut": None, "url": de.get("url")}
        m = de["dernier_mois"]; y, mo = int(m[:4]), int(m[5:7]) + 1
        if mo > 12: y, mo = y + 1, 1
        f["bdf"]["debut"] = f"{y - 1}-{mo:02d}"
        sec = [s for s in de.get("secteurs", []) if s.get("variation_pct") is not None and s["cumul_12_mois"] >= 2000]
        f["secteurs_hausse"] = sorted(sec, key=lambda s: -s["variation_pct"])[:3]
        f["secteurs"] = de.get("secteurs", [])
    if o.get("creations"): f["creations"] = o["creations"]
    if o.get("comparaison"): f["comparaison"] = o["comparaison"]
    pa = (c.get("periodes") or {}).get("annee")
    if pa:
        f["annee"] = {"depuis": pa["depuis"], "procedures": pa["reel"], "maj": c.get("maj"), "plans": pa.get("emplois_annonces", {}),
                      "procedures_50": pa.get("salaries_procedures", {})}
    tt = t.get("toutes_tailles")
    if tt:
        f["bodacc_6"] = tt.get("recent_6_mois_hors_ruptures") or tt.get("recent_6_mois")
        f["deps_hausse"] = [x for x in tt.get("departements", []) if not x.get("alerte") and (x.get("variation_pct") or 0) > 0][:5]
    da = lire("dares.json")
    if da and da.get("licenciements_eco"):
        L, V = da["licenciements_eco"], da["pse_valides"]
        def cumul(s, k, t_fin):
            i = [x["t"] for x in s].index(t_fin); return sum(x[k] for x in s[max(0, i - 3):i + 1]) if i >= 3 else None
        der = L[-1]; un_an = next((x for x in L if x["t"] == f"{int(der['t'][:4]) - 1}{der['t'][4:]}"), None)
        f["dares"] = {"t": der["t"], "inscriptions": der["inscriptions"], "provisoire": der["provisoire"],
                      "var_an": round(100 * (der["inscriptions"] - un_an["inscriptions"]) / un_an["inscriptions"], 1) if un_an else None,
                      "pse": V[-1]["pse"], "ruptures": V[-1]["ruptures"], "t_pse": V[-1]["t"],
                      "ruptures_annee": {y: sum(x["ruptures"] for x in V if x["t"].startswith(y)) for y in {x["t"][:4] for x in V} if sum(1 for x in V if x["t"].startswith(y)) == 4},
                      "url": da["url"], "publication": da.get("publication")}
    ev = D["data"].get("evenements", [])
    f["derniers_50"] = [e for e in ev if e.get("source") == "BODACC"][:6]
    an0 = dt.date.today().replace(month=1, day=1).isoformat()
    f["plans_annee"] = [e for e in ev if e.get("source") != "BODACC" and (e.get("date") or "") >= an0]
    return f

def faq(f):
    """Questions-réponses « réponse d'abord » : la réponse tient dans les deux premières phrases, avec chiffre, date et source."""
    q = []
    b, a = f.get("bdf"), f.get("annee")
    if b:
        rep = (f"Selon la Banque de France, {fr(b['n'])} défaillances d'entreprises ont été prononcées en France sur les douze mois "
               f"{de_mois(b['debut'])} à {mois_long(b['mois'])}, soit {pct(b['var'])} sur un an (série publiée par l'INSEE).")
        if a: rep += (f" Depuis le 1er janvier {a['depuis'][:4]}, le BODACC a publié {fr(a['procedures'])} jugements d'ouverture de procédure collective "
                      f"(sauvegardes comprises), d'après le décompte de ce site au {date_long(a['maj'] or f['aujourdhui'])}.")
        q.append((f"Combien de faillites d'entreprises en France en {f['aujourdhui'][:4]} ?", rep))
        sh = f.get("secteurs_hausse") or []
        v = b["var"] or 0
        verdict = "Oui" if v >= 3 else "Légèrement" if v > 1 else "Non, elles reculent" if v <= -1 else "Elles sont stables"
        rep2 = (f"{verdict} : {pct(b['var'])} sur douze mois glissants à fin {mois_long(b['mois'])} selon la Banque de France "
                f"({fr(b['n'])} contre {fr(b['n_avant'])} un an plus tôt).")
        if sh: rep2 += " Les plus fortes hausses parmi les grands secteurs : " + ", ".join(f"{s['secteur'].lower()} ({pct(s['variation_pct'])})" for s in sh) + "."
        rep2 += (" Les chiffres de la Banque de France sont publiés avec environ deux mois de retard ; le décompte quotidien du BODACC donne un signal plus récent "
                 "mais plus irrégulier.")
        q.append(("Les faillites d'entreprises augmentent-elles en France ?", rep2))
    dr = f.get("dares")
    if dr:
        trim = f"{dr['t'][-1]}{'er' if dr['t'][-1] == '1' else 'e'} trimestre {dr['t'][:4]}"
        q.append(("Combien de licenciements économiques en France ?",
                  f"Au {trim}, {fr(dr['inscriptions'])} personnes se sont inscrites à France Travail à la suite d'un licenciement économique "
                  f"({pct(dr['var_an'])} sur un an{', données provisoires' if dr['provisoire'] else ''}), selon la Dares. Sur le même trimestre, {dr['pse']} plans de sauvegarde "
                  f"de l'emploi ont été validés ou homologués par l'administration, prévoyant {fr(dr['ruptures'])} ruptures de contrat de travail. Ce sont les chiffres officiels ; "
                  "les plans recensés sur ce site (liste CGT, presse) n'en couvrent qu'une partie."))
    if a and a.get("plans"):
        p = a["plans"]
        q.append((f"Combien de plans sociaux en France en {a['depuis'][:4]} ?",
                  f"Ce site recense {fr(p['plans'])} plans de licenciement, suppressions de postes ou fermetures annoncés depuis le 1er janvier {a['depuis'][:4]}, "
                  f"pour au moins {fr(p['min'])} emplois (chiffres annoncés, dédoublonnés par entreprise). La liste vient de la « liste noire » publiée par la CGT (depuis 2023) "
                  "et de la presse (suivie depuis janvier 2025) : ce n'est pas un décompte officiel des plans de sauvegarde de l'emploi."))
    d5 = f.get("derniers_50") or []
    if d5:
        q.append(("Quelles entreprises de plus de 50 salariés sont en redressement ou en liquidation judiciaire ?",
                  "Les dernières publiées au BODACC : " + "; ".join(f"{e['entreprise']} ({e.get('commune') or ''}{' ' + e['dep'] if e.get('dep') else ''}), "
                  f"{e['type']} le {date_long(e.get('date') or '')}" for e in d5[:5]) + ". La liste complète, mise à jour chaque jour, est sur la page d'accueil du site."))
    cr = f.get("creations")
    if cr:
        q.append(("Combien d'entreprises sont créées en France chaque année ?",
                  f"{fr(cr['cumul_12_mois'])} créations d'entreprises sur les douze mois à fin {mois_long(cr['dernier_mois'])} ({pct(cr['variation_pct'])} sur un an, INSEE), "
                  f"dont {str(cr['dont_micro_pct']).replace('.', ',')} % de micro-entrepreneurs. Comparer créations et faillites ne donne pas un solde d'emplois : "
                  "la plupart des créations n'ont pas de salarié."))
    q.append(("D'où viennent ces chiffres et sont-ils fiables ?",
              "Des sources publiques : BODACC (jugements des tribunaux de commerce), Banque de France et INSEE (séries officielles), API Recherche d'entreprises "
              "(effectifs, comptes), URSSAF (emploi local), DECP et ADEME (marchés et aides), liste CGT des plans de licenciement et presse. Les effectifs sont des "
              "ordres de grandeur, les rapprochements par nom d'entreprise peuvent se tromper de filiale ; la page Méthode détaille les écarts connus et les corrections."))
    return q

def faq_ld(q): return {"@type": "FAQPage", "mainEntity": [{"@type": "Question", "name": a, "acceptedAnswer": {"@type": "Answer", "text": b}} for a, b in q]}

def dataset_ld(D, url=BASE_URL + "/", nom=None, desc=None):
    maj = (D["data"].get("maj") or "")[:10] or dt.date.today().isoformat()
    return {"@type": "Dataset", "@id": url + "#dataset", "name": nom or "Plans sociaux, fermetures et procédures collectives en France",
            "description": desc or ("Suivi quotidien des procédures collectives (BODACC) des entreprises de 50 salariés et plus, des plans de licenciement "
                                    "et fermetures annoncés (liste CGT, presse), recoupés avec les séries officielles de défaillances (Banque de France, INSEE), "
                                    "les effectifs, les comptes, les marchés publics et les aides."),
            "url": url, "inLanguage": "fr-FR", "isAccessibleForFree": True, "dateModified": maj,
            "temporalCoverage": f"2023-01-01/{maj}", "spatialCoverage": {"@type": "Place", "name": "France"},
            "creator": {"@type": "Person", "name": EDITEUR, "url": "https://oraclemarin.fr/apropos/"},
            "license": "https://creativecommons.org/licenses/by-nc-sa/4.0/",
            "keywords": ["faillites d'entreprises", "défaillances d'entreprises", "plans sociaux", "licenciements", "liquidation judiciaire",
                         "redressement judiciaire", "BODACC", "France"],
            "measurementTechnique": "Agrégation quotidienne de sources publiques ; méthode : " + BASE_URL + "/methode/",
            "distribution": [{"@type": "DataDownload", "encodingFormat": "text/csv", "contentUrl": BASE_URL + "/evenements.csv"},
                             {"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": BASE_URL + "/data.json"},
                             {"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": BASE_URL + "/officiel.json"}]}

def site_ld():
    return {"@type": "WebSite", "@id": BASE_URL + "/#site", "name": NOM, "url": BASE_URL + "/", "inLanguage": "fr-FR",
            "publisher": {"@type": "Person", "name": EDITEUR, "url": "https://oraclemarin.fr/apropos/"}}

def ld_tag(graph): return '<script type="application/ld+json">%s</script>' % json.dumps({"@context": "https://schema.org", "@graph": graph}, ensure_ascii=False).replace("</", "<\\/")

def head_meta(titre, desc, url, image=BASE_URL + "/og.png", robots="index,follow"):
    return (f'<link rel="canonical" href="{esc(url)}"><meta name="robots" content="{robots},max-image-preview:large">'
            f'<meta property="og:type" content="website"><meta property="og:locale" content="fr_FR"><meta property="og:site_name" content="{esc(NOM)}">'
            f'<meta property="og:title" content="{esc(titre)}"><meta property="og:description" content="{esc(desc)}"><meta property="og:url" content="{esc(url)}">'
            f'<meta property="og:image" content="{esc(image)}"><meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">'
            f'<meta name="twitter:card" content="summary_large_image"><meta name="twitter:image" content="{esc(image)}">'
            f'<link rel="alternate" type="application/rss+xml" href="{BASE}/rss.xml" title="{esc(NOM)} : derniers événements">'
            f'<link rel="icon" href="{BASE}/favicon.png" type="image/png">')

NAV = [("", "Carte et liste"), ("explorer/", "Explorer"), ("carte-departements/", "Carte par département"), ("cette-semaine/", "Cette semaine"), ("faillites-entreprises/", "Chiffres"),
       ("departements/", "Départements"), ("presse/", "Presse"), ("groupes/", "Carte des groupes"), ("cgt/", "Liste noire CGT")]
COURANT = ' aria-current="page"'
def nav_html(actif=""):
    return '<nav class="nav" aria-label="Pages du site">' + " ".join(
        f'<a href="{BASE}/{p}"{COURANT if p == actif else ""}{' class="nav-cgt"' if p == "cgt/" else ""}>{esc(l)}</a>' for p, l in NAV) + "</nav>"

PIED = (f'<footer>Projet indépendant, édité par <strong>{EDITEUR}</strong>, développeur à Perros-Guirec · '
        f'<a href="https://oraclemarin.fr/apropos/">À propos</a> · <a href="{BASE}/presse/">Presse</a> · <a href="mailto:{CONTACT}">Signaler une erreur</a> · <a href="https://buymeacoffee.com/capoupascap" rel="noopener" target="_blank">Soutenir</a> · '
        f'<a href="https://oraclemarin.fr/rgpd/#plans-sociaux">Mentions légales et données personnelles</a> · <a href="{BASE}/methode/">Méthode et corrections</a> · '
        f'<a href="{BASE}/en-un-an/">Infographie</a> · <a href="{BASE}/liste/">Plans sociaux {dt.date.today().year}</a> · <a href="{BASE}/alertes/">Alertes</a> · '
        f'<a href="{BASE}/donnees/">Données</a> · <a href="{BASE}/rss.xml">Flux RSS</a> · <a href="{BASE}/llms.txt">llms.txt</a> · '
        f'<a href="https://oraclemarin.fr/cabrule/">ça brûle, la carte des mobilisations</a></footer>')

CSS = """:root{--acier:#E9ECEF;--papier:#F7F8F9;--encre:#17202E;--gris:#5B6573;--trait:#C9CFD6;--signal:#E8B21E;--liq:#B8361E;--red:#D9822B;--sauv:#3E7CB1}
*{box-sizing:border-box}body{margin:0;background:var(--acier);color:var(--encre);font:16px/1.6 Barlow,system-ui,sans-serif}
a{color:inherit;text-underline-offset:3px}a:focus-visible{outline:3px solid var(--signal);outline-offset:2px}
header,main,footer,.nav{max-width:980px;margin:0 auto;padding:0 20px}header{padding-top:24px}
.marque{font:700 1.15rem "Barlow Condensed",sans-serif;text-decoration:none;letter-spacing:.02em;text-transform:uppercase}
h1{font:700 clamp(2rem,6vw,3.4rem)/1 "Barlow Condensed",sans-serif;margin:14px 0 10px}
h2{font:700 1.6rem/1.15 "Barlow Condensed",sans-serif;margin:30px 0 8px}h3{font-size:1.05rem;margin:18px 0 4px}
.nav{display:flex;flex-wrap:wrap;gap:6px 14px;font-size:15px;padding-top:6px;padding-bottom:6px;border-bottom:1px solid var(--trait)}
.nav a{text-decoration:none;color:var(--gris)}.nav a[aria-current]{color:var(--encre);font-weight:600;text-decoration:underline}.nav a.nav-cgt{color:#B8361E;font-weight:700}.nav a.nav-cgt[aria-current]{color:#B8361E}
.chapo{font-size:18px;max-width:70ch}.meta{color:var(--gris);font-size:14px}.bloc{background:var(--papier);border:1px solid var(--trait);border-top:3px solid var(--encre);padding:6px 18px 14px;margin:18px 0}
.gros b{font:700 1.5rem "Barlow Condensed",sans-serif}table{border-collapse:collapse;width:100%;font-size:15px;margin:8px 0}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--trait);vertical-align:top}th{font-weight:600;background:var(--papier)}
td.n,th.n{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}.tablo{overflow-x:auto}
ul{padding-left:20px}li{margin:5px 0}.alerte{font-weight:600;color:#9a2b1a}
footer{color:var(--gris);font-size:14px;padding-top:16px;padding-bottom:40px;margin-top:36px;border-top:1px solid var(--trait)}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}"""

def page(titre, desc, chemin, corps, graph=None, actif="", robots="index,follow"):
    url = BASE_URL + "/" + chemin
    return ('<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{esc(titre)}</title><meta name="description" content="{esc(desc)}">{head_meta(titre, desc, url, robots=robots)}'
            f'<link rel="stylesheet" href="{BASE}/fonts/fonts.css">'
            f'<style>{CSS}</style>{ld_tag(graph) if graph else ""}</head><body>'
            f'<header><a class="marque" href="{BASE}/">{esc(NOM)}</a></header>{nav_html(actif)}<main>{corps}</main>{PIED}</body></html>')

def ecrire(chemin, contenu):
    p = os.path.join(PUB, chemin)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh: fh.write(contenu)
    os.replace(tmp, p)
