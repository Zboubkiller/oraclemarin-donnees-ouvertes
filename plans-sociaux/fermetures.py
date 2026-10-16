"""Fermetures d'établissements de 50 salariés et plus selon le répertoire Sirene (base locale sirene.db), depuis janvier 2025.
Filtres : pas de successeur déclaré (fichier officiel des successions : transfert, reprise), pas d'autre établissement actif de
l'entreprise dans la même commune (ou la même ville pour Paris, Lyon, Marseille, hors commerces) ni, pour les bureaux (conseil, informatique, ingénierie, publicité), dans le même département, ni de nouvel établissement ouvert dans le même département autour de la date (déménagement), hors employeurs publics, sociétés de droit étranger, intérim, banques et assurances, hôpitaux, administration, enseignement, et secteurs où les salariés sont repris au changement de prestataire (nettoyage, sécurité, restauration collective, transport urbain et lignes régulières d'autocars). Ces candidats restent bruités (fusions,
changements de prestataire, réorganisations au 31 décembre) : ils ne deviennent des événements qu'après validation humaine
(validations.json). Sans validation, ils sont seulement signalés sur les fiches des entreprises déjà suivies."""
import json, os, re, sqlite3, sys
import collect
H = os.path.dirname(os.path.abspath(__file__))
SQL = """select e.siret, e.siren, u.nom, e.enseigne, e.commune, e.insee, e.dep, e.tranche, e.date_etat, e.naf, u.etat, u.tranche
 from etab e join ul u using(siren)
 where e.etat='F' and e.date_etat >= '2025-01-01' and e.tranche in ('21','22','31','32','41','42','51','52','53')
 and not exists (select 1 from succession x where x.pred = e.siret)
 and substr(coalesce(u.cj,''),1,1) not in ('7', '3')
 and substr(coalesce(e.naf,''),1,2) not in ('78', '64', '65', '66', '84', '85')
 and coalesce(e.naf,'') not like '86.10%' and coalesce(e.naf,'') not like '81.2%' and coalesce(e.naf,'') not like '80.%'
 and coalesce(e.naf,'') not like '68.20%' and coalesce(e.naf,'') not like '56.29%' and coalesce(e.naf,'') not like '49.31%' and coalesce(e.naf,'') not like '49.39A%'
 and not exists (select 1 from etab f where f.siren = e.siren and f.insee = e.insee and f.siret <> e.siret and f.etat = 'A')
 and not exists (select 1 from actifs a where a.siren = e.siren and a.insee = e.insee)"""

COMMERCE = ("45", "47", "55", "56")
BUREAUX = ("58.2", "62", "63", "69", "70", "71", "72", "73", "74", "82.1")
ville = lambda i: (i or "")[:3] if (i or "")[:3] in ("751", "132") else "6938" if (i or "").startswith("6938") else i

GENERIQUES = set("""SOCIETE SOC GROUPE COMPAGNIE CIE FRANCE ETABLISSEMENTS ETS ENTREPRISE ASSOCIATION ASS SARL CENTRE CTRE INSTITUT CLINIQUE HOPITAL FONDATION
 TRANSPORTS SERVICES SERVICE INDUSTRIE INDUSTRIES LABORATOIRES CAISSE MUTUELLE BANQUE UNION COOPERATIVE GIE SAS LES DES LA LE DU DE ATELIERS ATELIER MAISON
 HOTEL RESIDENCE EHPAD FEDERATION SYNDICAT OFFICE AGENCE CABINET GARAGE DISTRIBUTION CONSTRUCTIONS CONSTRUCTION NOUVELLE NOUVELLES PREMIUM SAINT SAINTE
 AUTO AUTOMOBILES PARIS LYON MARSEILLE PROMOTION INSPIRATION ORLY THE INTERNATIONAL GENERALE NATIONALE EUROPE EUROPEENNE""".split())

def meme_groupe(s, siren, nom, insee):
    """Autre société active dans la même commune dont le nom commence par le même mot distinctif (BASF France -> BASF Agri Production)."""
    import re
    t = [w for w in re.split(r"[\s\-.,']+", (nom or "").upper()) if w and w not in GENERIQUES]
    if not t or len(t[0]) < 3: return []
    # tous les établissements actifs (table actifs), même sans salarié déclaré (Daher Logistics à Tremblay-en-France)
    return [{"nom": x[0], "siren": x[1]} for x in s.execute("select distinct u.nom, u.siren from actifs a join ul u using(siren) where a.insee=? and a.siren<>? and u.etat='A' and (u.nom like ? or u.nom = ?) limit 3",
                                    (insee, siren, t[0] + " %", t[0]))]

def absorbee(L, date, commune=None, cessee=True):
    """Annonce BODACC (fusion, absorption, TUP, apport ; vente du fonds) de 12 mois avant à 3 mois après la fermeture. Pour une société
    encore active, seule une vente de fonds qui cite la commune du site compte. Renvoie l'annonce retenue, ou None."""
    import datetime as dt, unicodedata
    try: d = dt.date.fromisoformat((date or "")[:10])
    except ValueError: return None
    com = re.sub(r"[^a-z0-9 ]", " ", unicodedata.normalize("NFD", (commune or "").lower()).encode("ascii", "ignore").decode()).strip()
    for x in L or []:
        try: dx = dt.date.fromisoformat(x["date"][:10])
        except (KeyError, TypeError, ValueError): continue
        if not -90 <= (d - dx).days <= 365: continue
        if x.get("type", "fusion") == "fusion" and cessee: return x
        if x.get("type") == "cession" and (cessee or (com and re.search(r"\b" + re.escape(com) + r"\b", x.get("texte") or ""))): return x
    return None

def candidats(tout=False):
    try: s = sqlite3.connect(os.path.join(H, "sirene.db"))
    except Exception: return []
    try: rows = s.execute(SQL).fetchall()
    except sqlite3.OperationalError: return []
    import datetime as dt
    dep_ = lambda i: (i or "")[:3] if (i or "").startswith("97") else (i or "")[:2]
    # sociétés absorbées ou fusionnées (BODACC, vérifié par tri_fermetures.py) : disparition juridique, pas fermeture de site
    F, ACTIFS_JOUR = {}, set()
    try:
        cdb = sqlite3.connect(os.path.join(H, "cache.db"), timeout=60)
        F = {x: json.loads(j) for x, j in cdb.execute("select siren, js from fusion_bodacc")}
        ACTIFS_JOUR = {x for x, j in cdb.execute("select siret, js from tri_fermeture") if json.loads(j).get("etat_du_jour") == "A"}
    except sqlite3.OperationalError: pass
    out = []
    for r in rows:
        if not tout and absorbee(F.get(r[1]), r[8], r[4], r[10] == "C"): continue
        if not tout and r[0] in ACTIFS_JOUR: continue          # redevenu actif depuis le dernier stock mensuel
        lo, hi = collect.TR.get(r[7] or "", (None, None))
        # déménagement : autre établissement de l'entreprise ouvert de 12 mois avant à 3 mois après la fermeture
        try:
            df = dt.date.fromisoformat(r[8][:10]); bas, haut = (df - dt.timedelta(days=365)).isoformat(), (df + dt.timedelta(days=90)).isoformat()
        except (TypeError, ValueError):
            bas = haut = None
        nouveaux = s.execute("select insee, creation from actifs where siren=? and insee<>? and creation between ? and ?", (r[1], r[5], bas, haut)).fetchall() if bas else []
        if any(dep_(i) == r[6] for i, _ in nouveaux): continue          # déménagement dans le même département
        transfert = []
        for i, c in nouveaux[:3]:
            nm = s.execute("select commune from etab where insee=? limit 1", (i,)).fetchone()
            transfert.append({"commune": (nm[0].title() if nm and nm[0] else i), "dep": dep_(i), "date": c})
        # Paris, Lyon, Marseille : un autre arrondissement est la même ville (hors commerces, hôtels, restaurants : un magasin qui ferme reste une fermeture)
        if not (r[9] or "").startswith(COMMERCE):
            v = ville(r[5])
            if v != r[5] and any(ville(i) == v for (i,) in s.execute("select insee from actifs where siren=? and insee<>?", (r[1], r[5]))): continue
        # autres établissements encore actifs dans le département (regroupement de bureaux, siège voisin)
        meme_dep = [{"commune": (x[0] or "").title(), "siege": bool(x[1])} for x in
                    s.execute("select commune, siege from etab where siren=? and dep=? and etat='A' and siret<>? order by siege desc limit 4", (r[1], r[6], r[0]))]
        if (r[9] or "").startswith(BUREAUX) and meme_dep: continue      # bureaux (conseil, informatique, ingénierie, pub) : regroupement dans le département
        mg = meme_groupe(s, r[1], r[2], r[5])
        out.append({"siret": r[0], "siren": r[1], "nom": r[2], "enseigne": (r[3] or "").split(" | ")[0] or None, "commune": (r[4] or "").title(),
                    "insee": r[5], "dep": r[6], "effectif": [lo, hi], "date": r[8], "naf": r[9], "entreprise_cessee": r[10] == "C", "transfert": transfert, "meme_dep": meme_dep, "meme_groupe": [x["nom"] for x in mg], "meme_groupe_siren": [x["siren"] for x in mg]})
    return out

def presse_nom(u):
    import urllib.parse
    return re.sub(r"^www\.", "", urllib.parse.urlparse(u).netloc) or "presse"

def decisions():
    try: return json.load(open(os.path.join(H, "validations.json"), encoding="utf-8"))
    except Exception: return {}

PROC = ("redressement", "liquidation", "sauvegarde")

def restructurations(evs):
    """Transferts internes et absorptions : fermetures Sirene qui ne sont pas des pertes d'emplois immédiates mais des mouvements
    juridiques (site transféré à une société sœur, validé à la main ; société absorbée ou fusionnée, prouvé par une annonce BODACC).
    Hors des totaux d'emplois. Alerte « à creuser » si la société qui a reçu le site entre ensuite en procédure collective."""
    import sqlite3 as sq
    V = (decisions().get("fermeture") or {})
    try: F = {x: json.loads(j) for x, j in sq.connect(os.path.join(H, "cache.db"), timeout=60).execute("select siren, js from fusion_bodacc")}
    except sq.OperationalError: F = {}
    P = {}
    for e in evs:
        if e.get("source") == "BODACC" and e.get("siren") and e.get("type") in PROC: P.setdefault(e["siren"], []).append(e)
    out = []
    for c in candidats(tout=True):
        d = V.get(c["siret"], {})
        base = {"siret": c["siret"], "siren": c["siren"], "entreprise": c["enseigne"] or c["nom"], "commune": c["commune"], "dep": c["dep"], "date": c["date"],
                "effectif_site": c["effectif"]}
        if d.get("choix") == "restructuration":
            vers, vsiren = c["meme_groupe"], c["meme_groupe_siren"]
            if d.get("repreneur"):          # repreneur désigné à la main (SIREN)
                import sqlite3 as sq
                u = sq.connect(os.path.join(H, "sirene.db")).execute("select nom from ul where siren=?", (d["repreneur"],)).fetchone()
                vers, vsiren = [u[0] if u else d["repreneur"]], [d["repreneur"]]
            r = dict(base, nature="fusion ou transfert vers une société du groupe (vérifié à la main)", vers=vers, vers_siren=vsiren,
                     preuve=d.get("url") or f"https://annuaire-entreprises.data.gouv.fr/etablissement/{c['siret']}")
        elif absorbee(F.get(c["siren"]), c["date"], c["commune"], c["entreprise_cessee"]):
            f = absorbee(F.get(c["siren"]), c["date"], c["commune"], c["entreprise_cessee"])
            if f.get("type") == "cession":
                r = dict(base, nature="fonds de commerce cédé à un repreneur (BODACC) : contrats de travail transférés", vers=[f["acheteur"]] if f.get("acheteur") else [],
                         vers_siren=[f["acheteur_siren"]] if f.get("acheteur_siren") else [], preuve=f.get("url"), annonce_bodacc=f.get("date"))
            else:
                r = dict(base, nature="société absorbée, fusionnée ou ayant apporté son activité (BODACC)", vers=[], vers_siren=[], preuve=f.get("url"),
                         annonce_bodacc=f.get("date"))
        else: continue
        al = [b for sv in r["vers_siren"] for b in P.get(sv, []) if (b.get("date") or "") >= (c["date"] or "")]
        if al: r["alerte"] = f"{al[0].get('entreprise')} : {al[0]['type']} le {al[0]['date']} (BODACC), après la reprise ou le transfert du site"
        out.append(r)
    return out

def ecrire_restructurations(R):
    import csv, io
    champs = ["entreprise", "siren", "siret", "commune", "dep", "date", "effectif_site", "nature", "vers", "vers_siren", "preuve", "annonce_bodacc", "alerte"]
    b = io.StringIO(); w = csv.DictWriter(b, champs, extrasaction="ignore"); w.writeheader()
    for r in R: w.writerow({**r, "effectif_site": "–".join(map(str, r["effectif_site"])), "vers": " | ".join(r["vers"]), "vers_siren": " | ".join(r["vers_siren"])})
    open(os.path.join(H, "public", "restructurations.csv"), "w", encoding="utf-8").write(chr(0xfeff) + b.getvalue())
    json.dump(R, open(os.path.join(H, "public", "restructurations.json"), "w", encoding="utf-8"), ensure_ascii=False)

def enrichir(evs):
    C = candidats()
    par = {}
    for c in C: par.setdefault(c["siren"], []).append(c)
    n = 0
    for e in evs:                       # fait brut sur les entreprises suivies
        L = par.get(e.get("siren"))
        if L:
            e["etablissements_fermes"] = [{"siret": c["siret"], "commune": c["commune"], "date": c["date"], "effectif": c["effectif"]} for c in L][:5]; n += 1
    V = (decisions().get("fermeture") or {})
    nouveaux = []
    for c in C:                          # fermetures validées à la main -> événements
        if V.get(c["siret"], {}).get("choix") != "oui": continue
        nouveaux.append({"id": "sirene-" + c["siret"], "source": "Sirene (fermeture vérifiée)", "type": "fermeture", "entreprise": c["enseigne"] or c["nom"],
                         "siren": c["siren"], "siret": c["siret"], "lien": "siren_source", "commune": c["commune"], "insee": c["insee"], "dep": c["dep"],
                         "naf": c["naf"], **({"emplois_min": V[c["siret"]]["emplois"], "emplois_max": V[c["siret"]]["emplois"],
                            "emplois_precision": "annoncé" if V[c["siret"]]["emplois"] else "aucune perte d'emploi connue (salariés reclassés)"} if V[c["siret"]].get("emplois") is not None else
                         {"emplois_min": c["effectif"][0], "emplois_max": c["effectif"][1], "emplois_precision": "effectif du site avant fermeture (tranche INSEE), pas un nombre de licenciements"}),
                         "date": c["date"], "detail": f"Établissement de {c['nom']} à {c['commune']} fermé le {c['date']} selon le répertoire Sirene, où il déclarait {c['effectif'][0]} à {c['effectif'][1]} salariés. "
                                   + (("Fermeture confirmée par la presse ; aucune perte d'emploi connue (salariés reclassés)." if V[c["siret"]]["emplois"] == 0 else f"{V[c['siret']]['emplois']} emplois supprimés selon la presse.") if V[c["siret"]].get("emplois") is not None else "Pertes d'emplois confirmées par un article de presse." if V[c["siret"]].get("url") else "Fermeture vérifiée à la main ; le nombre de licenciements n'est pas connu (transferts possibles)."),
                         "url": f"https://annuaire-entreprises.data.gouv.fr/etablissement/{c['siret']}", "valide_humain": True,
                         **({"sources": [{"source": presse_nom(V[c["siret"]]["url"]), "url": V[c["siret"]]["url"], "date": None, "titre": "article de presse (vérification)"}]} if V[c["siret"]].get("url") else {})})
    # une fermeture validée sur un site qui a déjà une annonce chiffrée (même société, même lieu, de 18 mois avant à 3 mois après) la CONFIRME :
    # elle s'ajoute comme source de l'annonce existante, sans second chiffre (sinon les emplois du site seraient comptés deux fois)
    import datetime as dt
    ajoutes = rattaches = 0
    for ne in nouveaux:
        cible = None
        try: dn = dt.date.fromisoformat(ne["date"][:10])
        except (KeyError, ValueError): dn = None
        for e in evs:
            if e is ne or e.get("source") == "BODACC" or e.get("partie_de") or e.get("siren") != ne["siren"] or not e.get("date") or str(e.get("source", "")).startswith("Sirene"): continue
            try: de = dt.date.fromisoformat(e["date"][:10])
            except ValueError: continue
            ecart = (dn - de).days if dn else None
            if ecart is None or not -90 <= ecart <= 548: continue
            meme_lieu = (not e.get("dep")) or e.get("dep") == ne["dep"] or (e.get("commune") or "").lower() == (ne.get("commune") or "").lower()
            if not meme_lieu: continue
            if cible is None or abs(ecart) < abs((dn - dt.date.fromisoformat(cible["date"][:10])).days): cible = e
        if cible is None:
            evs.append(ne); ajoutes += 1; continue
        cible.setdefault("sources", []).append({"source": "Sirene (fermeture vérifiée)", "url": ne["url"], "date": ne["date"],
                                                "titre": f"Fermeture de l'établissement de {ne['commune']} confirmée (répertoire Sirene, {ne['date']})"})
        for x in ne.get("sources") or []: cible["sources"].append(x)
        if not cible.get("emplois_min") and ne.get("emplois_precision") == "annoncé": cible.update(emplois_min=ne["emplois_min"], emplois_max=ne["emplois_max"], emplois_precision="annoncé")
        cible["fermeture_confirmee"] = {"date": ne["date"], "commune": ne["commune"], "siret": ne["siret"]}
        rattaches += 1
    nouveaux = [x for x in nouveaux if x in evs]
    print(f"fermetures validées : {ajoutes} nouvelles lignes, {rattaches} rattachées à une annonce existante du même site (sans second chiffre)", file=sys.stderr)
    try:
        R = restructurations(evs); ecrire_restructurations(R)
        par_r = {}
        for r in R:
            for x in [r["siren"]] + r["vers_siren"]: par_r.setdefault(x, []).append(r)
        for e in evs:
            if e.get("siren") in par_r: e["restructurations"] = par_r[e["siren"]][:6]
        print(f"restructurations : {len(R)} (dont {sum(1 for r in R if r.get('alerte'))} avec alerte)", file=sys.stderr)
    except Exception as ex:
        print("restructurations :", ex, file=sys.stderr)
    print(f"fermetures Sirene : {len(C)} candidates, {n} événements suivis concernés, {len(nouveaux)} validées ajoutées", file=sys.stderr)
