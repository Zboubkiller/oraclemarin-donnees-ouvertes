# VERSION_PUBLIQUE : page référencée (barre de navigation, plan du site)
"""Page « Pistes à explorer » : chaque recoupement de la base en une carte (idée, chiffres du jour, public visé, précautions) qui renvoie vers la page de détail.
Les chiffres sont lus dans les fichiers produits par les autres pages, donc à jour à chaque exécution. Aucun lien de cause n'est affirmé."""
import csv, datetime as dt, json, os, sys
H = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, H)
import commun as S
esc, fr = S.esc, S.fr
Q = "https://oraclemarin.fr/quotas-carbone/"

def lire(chemin, defaut=None):
    try: return json.load(open(chemin, encoding="utf-8"))
    except Exception: return defaut

def p_pistes(EV, FICHES):
    rc = lire(os.path.join(H, "recoupements_counts.json"), {})
    arret = lire("/var/www/quotas-carbone/arret.json", {}).get("meta", {})
    lob = lire("/var/www/quotas-carbone/lobbying.json", {}).get("lignes", [])
    radar = lire("/var/www/quotas-carbone/radar_full.json", {}).get("lignes", [])
    dos = lire(os.path.join(H, "dossier_pilote.json"), [])
    dec = lire(os.path.join(H, "validations.json"), {}).get("dossier", {})
    terr = []
    try: terr = list(csv.DictReader(open(os.path.join(S.PUB, "territoires-exposes.csv"), encoding="utf-8-sig"), delimiter=";"))
    except Exception: pass
    par = arret.get("par_niveau", {})
    _r = lire(os.path.join(H, "reprises.json"), {})
    rep_n = len(_r.get("rechutes", [])) if _r else "—"; rep_c = len(_r.get("chaines", [])) if _r else "—"
    try:
        _s = list(csv.DictReader(open(os.path.join(S.PUB, "fermetures-sites-classes.csv"), encoding="utf-8-sig"), delimiter=";"))
        sols_n = len({r["siren"] for r in _s}); sols_m = len({r["siren"] for r in _s if r["site_de_l_annonce"] == "oui"})
    except Exception: sols_n = sols_m = "—"
    nret = sum(1 for v in dec.values() if v.get("choix") == "retenu")
    quotas_tot = sum(r.get("g", 0) for r in radar)
    C = [
     ("Argent public et emplois", [
      ("Aide locale à l’emploi, puis suppressions", f"{BASE}/recoupements/#emploi",
       "Une collectivité subventionne une société avec un objectif de créations ou de maintiens d’emplois ; la société annonce ensuite un plan social, une fermeture ou une procédure collective.",
       f"{rc.get('subventions_emploi', '—')} sociétés dans la base. Dossier pilote : {len(dos)} cas audités (bretons surtout), dont {nret} retenus après contrôle du site, de l’entité, des emplois et des ordres de grandeur.",
       "Presse régionale, élus de l’opposition, Chambres régionales des comptes.",
       "L’aide peut concerner un autre site que celui qui ferme ; un objectif d’emplois n’est pas un engagement contractuel dont le suivi est public."),
      ("Aides publiques dans les 24 mois avant une annonce", f"{BASE}/recoupements/#aides",
       "Aides ADEME, aides d’État (TAM) et autres, rapprochées par SIREN dans les 24 mois précédant une suppression d’emplois d’au moins 30 postes.",
       f"{rc.get('aidees_licenciantes', '—')} sociétés, classées par montant, avec l’aide par emploi supprimé et la rentabilité du dernier exercice.",
       "Journalistes économiques, syndicats, chercheurs en politique industrielle.",
       "Une aide proche d’une annonce ne dit rien du lien entre les deux ; les contrats pluriannuels sont des plafonds, pas des sommes versées."),
     ]),
     ("Climat et quotas de CO₂", [
      ("Quotas gratuits sur des sites à l’arrêt", Q + "arret.html",
       "Des sites reçoivent encore des quotas de CO₂ gratuits alors que leurs émissions vérifiées sont nulles ou en chute. Cas phare : le four de Gargenville, environ 505 000 quotas alloués en 2022-2025 pour zéro émission.",
       f"{arret.get('n', '—')} sites : {par.get('confirme', 0)} arrêts corroborés, {par.get('probable', 0)} probables, {par.get('non_etabli', 0)} non établis, {par.get('actif', 0)} sites actifs dont la baisse vient d’un changement de combustible.",
       "Reporterre, Contexte, chercheurs sur le marché carbone, DGEC à interroger.",
       "Un quota alloué n’est pas un quota vendu ; l’ajustement après cessation existe, avec délai ; le registre ne publie les transferts qu’avec plusieurs années de retard."),
      ("Qui reçoit les quotas : concentration", Q + "radar.html",
       "Radar de toutes les sociétés qui reçoivent des quotas gratuits, avec la valeur indicative, les aides ADEME, les résultats et le lobbying.",
       f"{len(radar)} sociétés, {quotas_tot / 1e6:.0f} millions de quotas gratuits sur 2021-2025.",
       "Journalistes climat et économie, ONG, chercheurs.",
       "Valeur indicative entre 65 et 80 €/t ; les groupes sont à regrouper à la main quand le SIREN diffère."),
      ("Carte des quotas de CO₂", Q,
       "Carte des installations françaises soumises au marché carbone européen, avec leur allocation gratuite, leurs émissions vérifiées, les sols pollués et les inspections proches.",
       "1 055 installations, 2013-2025.", "Rédactions locales : trouvez le site de votre territoire.", "Les coordonnées viennent du registre européen ; certaines sont approximatives."),
     ]),
     ("Influence et réseaux", [
      ("Lobbying, puis soutien public", Q + "lobbying.html",
       "Industriels qui déclarent du lobbying sur les quotas ou les aides, puis figurent parmi les bénéficiaires de l’ADEME ou des contrats de décarbonation : chronologie par société.",
       f"{len(lob)} industriels du radar (ArcelorMittal, Vicat, Eqiom, Roquette…).",
       "Observatoire des multinationales, Disclose, Contexte.",
       "La HATVP ne publie que l’année ; les aides résultent d’appels à projets ouverts à tous. Aucun lien de cause."),
      ("Lobbying déclaré et suppressions d’emplois", f"{BASE}/recoupements/#lobbying",
       "Sociétés qui déclarent du lobbying à la HATVP et qui annoncent ensuite 50 suppressions d’emplois ou plus.",
       f"{rc.get('lobbyistes', '—')} sociétés, avec l’objet de la dernière déclaration.",
       "Journalistes d’enquête, parlementaires.", "L’absence de déclaration ne prouve pas l’absence de lobbying (groupe, fédération)."),
      ("Holdings à la tête de plusieurs sociétés touchées", f"{BASE}/recoupements/#holdings",
       "Dirigeants personnes morales qui apparaissent au registre à la tête d’au moins deux sociétés ayant annoncé un plan social, une fermeture ou une procédure collective.",
       f"{rc.get('holdings', '—')} holdings depuis 2024.", "Observatoire des multinationales, journalistes judiciaires, syndicats.",
       "Dirigeant personne morale n’est pas actionnaire ; Bpifrance et la Caisse des dépôts sont des investisseurs publics, signalés."),
      ("Reprises et rechutes", f"{BASE}/reprises/",
       "Sociétés dont le tribunal a arrêté un plan (redressement, sauvegarde, cession) puis qui rouvrent une procédure ; et recherche de chaînes : une société créée après la cession ou la liquidation d’une autre, avec un dirigeant commun.",
       f"{rep_n} rechutes repérées ; chaînes de sociétés à dirigeant commun : {rep_c}.",
       "Journalistes judiciaires et d’enquête, syndicats, mandataires.",
       "Faits du BODACC et du registre seulement ; les personnes physiques ne sont pas nommées ; une rechute ou un dirigeant commun n’a rien d’illégal en soi."),
      ("Carte des groupes et sociétés liées", f"{BASE}/groupes/", "Qui est lié à qui : filiales, dirigeants communs, groupes touchés par plusieurs annonces.", "Carte interactive.", "Journalistes, syndicats.", "Un lien de gouvernance n’est pas une décision commune."),
     ]),
     ("Environnement", [
      ("Fermetures et sites classés", f"{BASE}/sites-classes/",
       "Quand une société qui exploite une installation classée (ICPE, Seveso) est liquidée ou ferme, qui assure la remise en état du site ? Les sites sont rapprochés des mises en demeure, mesures d’urgence, servitudes et inspections publiées.",
       f"{sols_n} sociétés en liquidation ou fermeture depuis 2024 avec un site classé soumis à autorisation ou Seveso ; {sols_m} avec un site dans la commune de l’annonce.",
       "Journalistes environnement et locaux, élus, associations de riverains.",
       "La page ne constate aucune pollution ; mises en demeure et mesures sont comptées sans lire leur contenu ; le registre peut avoir du retard."),
     ]),
     ("Territoires", [
      ("Les territoires les plus exposés", f"{BASE}/territoires/",
       "Communes où une seule annonce de suppression d’emplois pèse plusieurs pour cent de l’emploi salarié privé, avec l’argent public rapproché.",
       f"{len(terr)} cas depuis 2024 ; classement par région et par département ; 3 à 5 cas par région à reprendre.",
       "Presse régionale et locale, élus, services de l’État en région.", "Les emplois annoncés sont parfois ceux d’un groupe entier ; un cas passe « contrôles OK » si lieu, SIREN et emplois sont corroborés."),
      ("Audit de la donnée : CGT, presse, BODACC", f"{BASE}/audit-donnee/",
       "Que couvre chaque source, où se recouvrent-elles, à quel point les nombres de postes concordent, quelles corrections manuelles ont été faites ; avec une version datée des données (CSV, notice des champs, métadonnées Zenodo).",
       "Recouvrement mesuré sur la période commune aux trois sources ; version figée chaque mois.",
       "Chercheurs, statisticiens, syndicats, journalistes de données.", "Les définitions diffèrent d’une source à l’autre ; le recouvrement ne mesure pas l’exhaustivité."),
     ]),
    ]
    sections = ""
    for titre, cartes in C:
        li = "".join(f'<a class="piste" href="{esc(u)}"><h3>{esc(t)}</h3><p>{esc(idee)}</p><p class="chiffre"><b>Aujourd’hui :</b> {esc(chif)}</p>'
                      f'<p class="pour"><b>Pour qui :</b> {esc(pour)}</p><p class="prec"><b>Précautions :</b> {esc(prec)}</p><span class="aller">Ouvrir le détail →</span></a>' for t, u, idee, chif, pour, prec in cartes)
        sections += f'<h2>{esc(titre)}</h2><div class="grille">{li}</div>'
    avenir = ""
    css = ("<style>.grille{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:12px;margin:10px 0}.piste{display:block;background:#fff;border:1px solid var(--trait);border-top:3px solid var(--encre);padding:12px 14px;text-decoration:none;color:inherit}"
           ".piste:hover{border-top-color:var(--signal);box-shadow:0 2px 8px rgba(0,0,0,.12)}.piste h3{font:700 1.25rem/1.15 'Barlow Condensed',sans-serif;margin:0 0 6px}.piste p{margin:5px 0;font-size:14.5px}"
           ".piste .chiffre{background:#F2F3F5;padding:5px 8px}.piste .pour,.piste .prec{color:var(--gris);font-size:13.5px}.piste .aller{font-weight:600;font-size:14px;text-decoration:underline}</style>")
    corps = (css + "<h1>Pistes à explorer</h1><p class=\"chapo\">Chaque carte est un recoupement entre des données publiques : l’idée, ce qu’il donne aujourd’hui, à qui il peut servir et ses précautions. Cliquez sur une carte pour ouvrir le détail. "
             "Ces rapprochements mettent des faits côte à côte ; ils n’établissent aucun lien de cause, et chaque piste doit être vérifiée avant publication.</p>"
             f'<p class="meta">Chiffres arrêtés au {dt.date.today().strftime("%d/%m/%Y")}. Réutilisation libre avec mention de la source (CC BY-NC-SA 4.0). Édité par Quentin Closset, Perros-Guirec.</p>' + sections + avenir)
    S.ecrire("pistes/index.html", S.page("Pistes à explorer : les recoupements de la base Plans sociaux et faillites",
             "Aides publiques puis suppressions d'emplois, quotas de CO₂ gratuits sur des sites à l'arrêt, lobbying, holdings, territoires exposés : chaque recoupement expliqué avec ses chiffres et ses précautions.",
             "pistes/", corps, None, "", robots="index,follow"))
    print("pistes :", sum(len(c) for _, c in C), "cartes")
    return S.BASE_URL + "/pistes/"
BASE = S.BASE
