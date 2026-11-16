# VERSION_PUBLIQUE : page référencée (page « Pistes à explorer », plan du site)
"""Page « Audit de la donnée » : ce que chaque source couvre (liste CGT, presse, BODACC), recouvrements entre sources sur la période commune, concordance des nombres d'emplois,
journal des corrections manuelles, écarts connus entre montants annoncés et publiés. Produit aussi une version datée et reproductible des données (public/releases/AAAA-MM-JJ/) :
CSV, JSON, notice des champs, somme de contrôle, fiche de citation et métadonnées prêtes pour un dépôt Zenodo (le dépôt lui-même reste à faire par l'éditeur)."""
import csv, datetime as dt, hashlib, json, os, shutil, statistics, sys
H = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, H)
import commun as S
esc, fr = S.esc, S.fr
DEB, FIN = "2025-01-01", "2026-03-31"     # période commune : BODACC depuis janvier 2025, liste CGT jusqu'à mars 2026

def famille(e):
    s = e.get("source") or ""
    return "BODACC" if s == "BODACC" else "CGT" if s.startswith("CGT") else "Accords" if s.startswith("Accords") else "Sirene" if s == "Sirene" else "Presse"
def emp(e): return e.get("emplois_max") or e.get("emplois_min") or 0
def jours(a, b): return (dt.date.fromisoformat(a[:10]) - dt.date.fromisoformat(b[:10])).days

def analyse(EV):
    act = [e for e in EV if not e.get("doublon_de") and not e.get("sans_entreprise") and e.get("siren") and famille(e) in ("BODACC", "CGT", "Presse") and DEB <= (e.get("date") or "") <= FIN]
    E = {"BODACC": {}, "CGT": {}, "Presse": {}}
    for e in act:
        E[famille(e)].setdefault(e["siren"], []).append(e)
    cov = {}
    for a in E:
        n = len(E[a])
        cov[a] = {"n": n, **{b: (sum(1 for s in E[a] if s in E[b]), n) for b in E if b != a}}
    # concordance des nombres d'emplois liste CGT / presse (même SIREN, dates à moins de 400 jours)
    rat, lag = [], []
    for s, L in E["CGT"].items():
        for cg in L:
            if famille(cg) != "CGT" or not emp(cg): continue
            pr = [p for p in E["Presse"].get(s, []) if famille(p) == "Presse" and emp(p) and abs(jours(p["date"], cg["date"])) <= 400]
            if pr:
                p = min(pr, key=lambda p: abs(jours(p["date"], cg["date"])))
                rat.append(emp(p) / emp(cg)); lag.append(jours(p["date"], cg["date"]))
    return cov, rat, lag

def release(EV, nb_ev):
    """Version datée dans public/releases/AAAA-MM-JJ/ (une par mois au plus, la première du mois)."""
    mois = dt.date.today().strftime("%Y-%m")
    R = os.path.join(S.PUB, "releases"); os.makedirs(R, exist_ok=True)
    exist = sorted(d for d in os.listdir(R) if d.startswith(mois) and os.path.isdir(os.path.join(R, d)))
    if exist: return exist[0]
    d = dt.date.today().isoformat(); P = os.path.join(R, d); os.makedirs(P)
    for f in ("evenements.csv", "data.json", "restructurations.csv", "societes_liees.csv", "recoupements-aidees.csv", "recoupements-holdings.csv", "territoires-exposes.csv", "fermetures-sites-classes.csv"):
        if os.path.exists(os.path.join(S.PUB, f)): shutil.copy(os.path.join(S.PUB, f), P)
    CH = {"id": "Identifiant de la ligne.", "evenement_id": "Regroupe les mentions d’une même entreprise à moins de 180 jours d’écart : comptez les evenement_id distincts, pas les lignes.",
          "date": "Date de l’annonce, du jugement ou de l’accord (au mois près pour la liste CGT : le 15 du mois).", "date_publication": "Date de publication de la source (BODACC notamment).",
          "type": "Type d’événement : plan social, fermeture, liquidation, redressement, sauvegarde, départs volontaires.", "source": "Source de la ligne (BODACC, CGT (liste noire), Accords d’entreprise, titre de presse).",
          "entreprise": "Nom de l’entreprise tel que rapproché.", "siren": "SIREN rapproché (vide si non identifié).", "fiabilite_rapprochement": "Fiabilité du rapprochement avec le SIREN : sûr, probable ou indicatif.",
          "commune": "Commune du site concerné, quand elle est connue.", "departement": "Département.", "postes_annonces": "Nombre de postes supprimés annoncé par la source (liste CGT, presse). Ne pas confondre avec l’effectif de l’entreprise.",
          "effectif_entreprise_min": "Borne basse de la tranche d’effectif INSEE de toute l’entreprise.", "effectif_entreprise_max": "Borne haute de la tranche d’effectif INSEE de toute l’entreprise.",
          "exclu_des_totaux": "Oui si la ligne n’est pas comptée sur le site (pas d’entreprise précise, chiffre invérifiable).", "url_source": "Lien vers la source.",
          "resultat_net": "Dernier résultat net publié rapproché de l’annonce.", "annee_comptes": "Année des comptes correspondants.", "chiffre_affaires": "Chiffre d’affaires du dernier exercice publié.",
          "part_commande_publique_pct": "Part estimée du chiffre d’affaires issue de la commande publique, si calculable.", "part_emploi_commune_pct": "Poids des postes annoncés dans l’emploi salarié privé de la commune (URSSAF).",
          "suite_procedure": "Suite connue de la procédure collective (plan, cession, liquidation).", "resultat_net_dernier_exercice": "Résultat net du dernier exercice publié.", "annee_dernier_exercice": "Année de ce dernier exercice.",
          "procedure_bodacc_liee": "Procédure collective du BODACC rapprochée de l’annonce.", "operation_bodacc_recente": "Opération récente (cession, fusion…) du BODACC pour la société.",
          "date_operation_bodacc": "Date de cette opération.", "delai_operation_mois": "Délai en mois entre l’opération et l’annonce.", "a_creuser_reprise": "Indicateur : annonce proche d’une opération de reprise, à examiner (pas un constat).",
          "lieu_verifie": "Lieu corroboré par un établissement dans la commune ou le département (Sirene).", "empreinte": "Empreinte de la ligne permettant d’en retrouver l’origine.", "credit": "Mention de source à reprendre."}
    cols = next(csv.reader(open(os.path.join(P, "evenements.csv"), encoding="utf-8-sig")))
    notice = (f"# Plans sociaux et faillites en France : version du {d}\n\nÉditeur : Quentin Closset, Perros-Guirec (ADRESSE_DE_CONTACT). Site : https://oraclemarin.fr/plans-sociaux/\n\n"
              "Licence : CC BY-NC-SA 4.0 (mention de la source, pas d’usage commercial, partage dans les mêmes conditions). La presse, la recherche, les syndicats et les associations peuvent réutiliser librement. "
              "Les données publiques d’origine (BODACC, Sirene, ADEME, HATVP, URSSAF, Géorisques…) gardent leur propre licence.\n\n"
              f"Cette version est figée au {d}. Les fichiers du site, eux, changent chaque jour : citez la date de cette version.\n\n## Fichiers\n\n"
              "- `evenements.csv` : une ligne par mention (annonce de presse, ligne de la liste CGT, procédure du BODACC, accord d’entreprise).\n- `data.json` : mêmes événements avec tous les champs (aides, comptes, direction, liens).\n"
              "- `restructurations.csv`, `societes_liees.csv` : opérations de restructuration et sociétés liées.\n- `recoupements-*.csv`, `territoires-exposes.csv`, `fermetures-sites-classes.csv` : recoupements publiés sur le site.\n- `SHA256SUMS` : sommes de contrôle.\n\n"
              "## Règles avant de compter\n\n- Comptez les `evenement_id` distincts, pas les lignes.\n- `postes_annonces` est un nombre de postes annoncé ; `effectif_entreprise_*` est la taille de toute l’entreprise.\n- Une case vide veut dire « inconnu », pas « non ».\n"
              "- Les sources ne couvrent pas les mêmes périodes (BODACC depuis " + __import__('commun').bodacc_depuis() + ", liste CGT d’août 2023 à mars 2026, presse depuis janvier 2023) : une courbe mensuelle montre l’arrivée des sources autant que la conjoncture.\n"
              "- Ne publiez que les rapprochements `sûr` ou, après vérification, `probable`. Un recoupement rapproche des faits publics ; il n’établit aucun lien de cause.\n\n## Champs de `evenements.csv`\n\n| Champ | Sens |\n|---|---|\n"
              + "\n".join(f"| `{c}` | {CH.get(c, '—')} |" for c in cols) + "\n\nLes champs de `data.json` sont décrits sur https://oraclemarin.fr/plans-sociaux/donnees/.\n")
    open(os.path.join(P, "README.md"), "w", encoding="utf-8").write(notice)
    open(os.path.join(P, "CITATION.cff"), "w", encoding="utf-8").write(
        f"cff-version: 1.2.0\nmessage: \"Merci de citer ce jeu de données.\"\ntitle: \"Plans sociaux et faillites en France (version du {d})\"\nauthors:\n  - family-names: Closset\n    given-names: Quentin\n"
        f"version: \"{d}\"\ndate-released: \"{d}\"\nlicense: CC-BY-NC-SA-4.0\nurl: \"https://oraclemarin.fr/plans-sociaux/releases/{d}/\"\nrepository: \"https://oraclemarin.fr/plans-sociaux/donnees/\"\n")
    json.dump({"title": f"Plans sociaux et faillites en France (version du {d})", "upload_type": "dataset", "version": d, "publication_date": d, "license": "cc-by-nc-sa-4.0",
               "creators": [{"name": "Closset, Quentin"}], "description": "Annonces de suppressions d’emplois, fermetures et procédures collectives en France (liste CGT, presse, BODACC, accords d’entreprise), rapprochées par SIREN, avec recoupements (aides publiques, lobbying, quotas de CO₂, sites classés). Voir README.md pour les règles de lecture.",
               "keywords": ["plans sociaux", "faillites", "BODACC", "emploi", "France", "open data"], "access_right": "open"},
              open(os.path.join(P, "zenodo.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    with open(os.path.join(P, "SHA256SUMS"), "w") as f:
        for n in sorted(os.listdir(P)):
            if n != "SHA256SUMS": f.write(f"{hashlib.sha256(open(os.path.join(P, n), 'rb').read()).hexdigest()}  {n}\n")
    return d

def p_audit(EV, FICHES):
    cov, rat, lag = analyse(EV)
    rel = release(EV, len(EV))
    try: V = json.load(open(os.path.join(H, "validations.json"), encoding="utf-8"))
    except Exception: V = {}
    lib = {"CGT": "Liste CGT", "Presse": "Presse", "BODACC": "BODACC (procédures)"}
    lig = ""
    for a in ("CGT", "Presse", "BODACC"):
        c = cov[a]
        cell = lambda b: (f'{c[b][0] * 100 / c[b][1]:.0f} % <small>({fr(c[b][0])} sur {fr(c[b][1])})</small>' if c[b][1] and b in c else "—")
        lig += f'<tr><td>{lib[a]}</td><td class="n">{fr(c["n"])}</td>' + "".join(f'<td class="n">{cell(b)}</td>' if b != a else '<td class="n">—</td>' for b in ("CGT", "Presse", "BODACC")) + "</tr>"
    ok = sum(1 for r in rat if 0.8 <= r <= 1.25)
    conc = (f"<p>Pour {len(rat)} annonces de la liste CGT dont un article de presse du même SIREN donne aussi un nombre de postes (écart de dates inférieur à 400 jours), {ok} concordent à 25 % près. "
            f"Rapport médian presse / CGT : {statistics.median(rat):.2f}. Écart de date médian : {statistics.median(lag):.0f} jours (presse moins CGT). "
            "L’échantillon est petit et mélange parfois plusieurs annonces de la même société : lisez cela comme un ordre de grandeur de l’incertitude, pas comme une mesure précise.</p>") if len(rat) >= 10 else "<p>Échantillon trop petit pour une comparaison chiffrée.</p>"
    corr = " · ".join(f"{fr(len(V.get(k, {})))} {lib2}" for k, lib2 in (("rattachement", "rattachements société vérifiés"), ("identification", "identifications SIREN"), ("nombre", "nombres de postes"), ("presse", "articles de presse"), ("fermeture", "fermetures"), ("doublon", "doublons")))
    nco = sum(1 for e in EV if e.get("emplois_corrige_a_la_main")); nvh = sum(1 for e in EV if e.get("valide_humain"))
    css = ("<style>.tq{overflow-x:auto;margin:12px 0}.tq table{border-collapse:collapse;width:100%;font-size:14px;background:#fff}.tq th,.tq td{border-bottom:1px solid #E3E6EA;padding:7px 9px;text-align:left;vertical-align:top}"
           ".tq th{background:#F2F3F5;font-size:12.5px}.tq td.n,.tq th.n{text-align:right}small{color:#5A6371}</style>")
    corps = (css + "<h1>Audit de la donnée</h1><p class=\"chapo\">Que couvre chaque source, où se recouvrent-elles, et à quel point peut-on se fier aux nombres ? Cette page documente les limites de la base pour les chercheurs, et propose une version datée et reproductible des données.</p>"
             f'<p class="meta">Sommaire : <a href="#recouvrement">recouvrement des sources</a> · <a href="#concordance">concordance des nombres</a> · <a href="#corrections">corrections manuelles</a> · <a href="#ecarts">écarts de montants</a> · <a href="#version">version datée</a></p>'
             f'<h2 id="recouvrement">Recouvrement des sources</h2><p>Sur la période commune aux trois sources ({DEB[:7]} à {FIN[:7]}), part des sociétés identifiées (SIREN) d’une source qui figurent aussi dans une autre. '
             'Les définitions diffèrent : le BODACC recense des procédures collectives (pas forcément des suppressions d’emplois, entreprises de 50 salariés et plus), la liste CGT des plans de licenciement connus du syndicat, la presse ce que les rédactions ont écrit.</p>'
             '<div class="tq"><table><thead><tr><th>Source</th><th class="n">Sociétés</th><th class="n">Aussi dans la liste CGT</th><th class="n">Aussi dans la presse</th><th class="n">Aussi dans le BODACC</th></tr></thead><tbody>' + lig + '</tbody></table></div>'
             '<p>Seuls les articles de presse indépendants sont comptés (pas ceux que la base a cherchés pour confirmer une ligne de la liste CGT). Lecture : aucune source ne suffit seule. Un faible recouvrement ne mesure pas l’exhaustivité, il montre que les sources voient des choses différentes ; la couverture de la presse est plus faible pour les petits titres régionaux.</p>'
             f'<h2 id="concordance">Concordance des nombres de postes</h2>{conc}'
             f'<h2 id="corrections">Corrections manuelles</h2><p>Chaque correction est appliquée par un humain à partir d’une page de validation et conservée dans un journal : {corr}. {fr(nco)} lignes portent un nombre de postes corrigé à la main (colonne de note dans <code>data.json</code>), {fr(nvh)} lignes un rapprochement validé à la main. '
             'Le journal des corrections est publié sur la page <a href="' + S.BASE + '/methode/">Méthode</a>.</p>'
             '<h2 id="ecarts">Écarts connus entre montants annoncés et publiés</h2><ul><li>La base ouverte de l’ADEME montre moins que les montants annoncés : environ 107 M€ de moins pour Heidelberg Materials (309 M€ dans la base) et 141 M€ de moins pour Vicat (190 M€), alors que les montants annoncés sont confirmés. Plusieurs explications sont possibles (cumul avec le Fonds Innovation de l’UE, contrats pluriannuels, périmètre) mais aucune n’est confirmée : voir la <a href="https://oraclemarin.fr/quotas-carbone/verif.html">page des points à vérifier</a>.</li>'
             '<li>Les contrats de soutien de l’appel d’offres « Grands projets industriels de décarbonation » sont des plafonds pluriannuels, pas des sommes versées.</li></ul>'
             f'<h2 id="version">Version datée et reproductible</h2><p>Pour citer un état précis des données, utilisez une version figée : <a href="{S.BASE}/releases/{rel}/">version du {rel}</a> (CSV, JSON, notice des champs, somme de contrôle, fiche de citation et métadonnées prêtes pour un dépôt Zenodo). '
             'Une nouvelle version est figée au début de chaque mois. Les fichiers du site (<a href="' + S.BASE + '/donnees/">page Données</a>) changent chaque jour.</p>'
             f'<p class="meta">Données arrêtées au {dt.date.today().strftime("%d/%m/%Y")}. Édité par Quentin Closset, Perros-Guirec.</p>')
    S.ecrire("audit-donnee/index.html", S.page("Audit de la donnée : ce que couvrent la liste CGT, la presse et le BODACC",
             "Recouvrement entre la liste CGT, la presse et le BODACC, concordance des nombres de postes, corrections manuelles, écarts de montants et version datée reproductible des données.",
             "audit-donnee/", corps, None, "", robots="index,follow"))
    print(f"audit donnée : version {rel}, {len(rat)} paires CGT/presse")
    return S.BASE_URL + "/audit-donnee/"
