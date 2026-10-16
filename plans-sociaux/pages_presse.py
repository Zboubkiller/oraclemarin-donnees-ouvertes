"""Page « Presse » : ce qu'est l'outil, ce qu'il permet de recouper, sources et limites, chiffres du jour, comment citer et
réutiliser, textes de présentation prêts à copier, contact et partenariats."""
import json, os
import commun as S
from commun import esc, fr

CSS = """.pr-grille{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px;margin:12px 0}
.pr-c{background:#fff;border:1px solid #DDE1E6;border-top:3px solid #17202E;padding:8px 12px}.pr-c .v{font:700 1.7rem/1.1 "Barlow Condensed",sans-serif}.pr-c .l{font-size:14px;color:#3D4654}
.copie{background:#F7F8F9;border:1px solid #DDE1E6;padding:10px 14px;margin:8px 0;position:relative}.copie p{margin:0;max-width:95ch}
.copie button{position:absolute;top:6px;right:6px;font:600 12px Barlow,sans-serif;border:1px solid #17202E;background:#fff;border-radius:3px;cursor:pointer;padding:2px 8px}
table.src td,table.src th{padding:5px 8px;border-bottom:1px solid #E3E6EA;text-align:left;vertical-align:top}"""

def p_presse(D, EV, fiches):
    etat = S.lire("etat.json", {}) or {}
    cv = etat.get("couverture") or {}
    n_acc = sum(1 for e in EV if e.get("source") == "Accords d'entreprise")
    n_proc = sum(1 for e in EV if e.get("source") == "BODACC")
    n_ann = sum(1 for e in EV if e.get("source") not in ("BODACC", "Accords d'entreprise") and not e.get("exclu_totaux") and not e.get("sans_entreprise"))
    n_rec = sum(1 for e in EV if e.get("comptes") or e.get("argent_public") or e.get("lobbying") or e.get("accords") or e.get("mobilisations"))
    court = ("Plans sociaux et faillites en France est un outil gratuit et ouvert qui recense les procédures collectives des entreprises de 50 salariés et plus, "
             "les plans sociaux et les accords de suppression de postes, et les croise avec les comptes, l'argent public reçu, le lobbying déclaré et les mobilisations.")
    long_ = (court + " Mis à jour plusieurs fois par jour à partir de sources publiques (BODACC, Légifrance, INSEE, URSSAF, Banque de France, data.gouv.fr, HATVP, liste CGT, presse), "
             "il propose une fiche par entreprise, un explorateur filtrable, des alertes par département, secteur ou entreprise, et l'export des données. "
             "Méthode, limites et corrections sont publiques. Projet indépendant de Quentin Closset, développeur à Perros-Guirec.")
    def copie(t, i):
        return (f'<div class="copie"><p id="t{i}">{esc(t)}</p><button type="button" data-c="t{i}">Copier</button></div>')
    titre = "Presse : présentation, chiffres, méthode et contact"
    desc = "Pour les journalistes et les rédactions : ce que permet l'outil Plans sociaux et faillites, ses sources et limites, les chiffres du jour, comment citer et réutiliser les données, et le contact."
    corps = (f"<style>{CSS}</style><h1>Presse</h1>"
             f'<p class="chapo">Un outil de recoupement, gratuit et ouvert, pour enquêter sur les suppressions d\'emplois en France : qui ferme, qui licencie, '
             f'avec quel argent public et quels bénéfices, et qui appeler. C\'est à vous de l\'essayer sur vos propres sujets.</p>'
             f'<div class="pr-grille">'
             f'<div class="pr-c"><div class="v">{fr(len(fiches))}</div><div class="l">fiches entreprise</div></div>'
             f'<div class="pr-c"><div class="v">{fr(n_proc)}</div><div class="l">procédures collectives d’entreprises de 50 salariés et plus (depuis mars 2025)</div></div>'
             f'<div class="pr-c"><div class="v">{fr(n_ann)}</div><div class="l">plans sociaux et fermetures annoncés (liste CGT depuis 2023, presse depuis janvier 2025)</div></div>'
             f'<div class="pr-c"><div class="v">{fr(n_acc)}</div><div class="l">accords de PSE et de départs volontaires signés depuis 2024 (Légifrance)</div></div>'
             f'<div class="pr-c"><div class="v">{fr(n_rec)}</div><div class="l">événements avec au moins une donnée croisée (comptes, argent public, lobbying, accords, mobilisations)</div></div></div>'
             '<p class="meta">Chiffres recalculés à chaque mise à jour.</p>'
             "<h2>Ce que l'outil permet de recouper</h2><ul>"
             "<li><b>Procédures collectives</b> (BODACC) : redressements, liquidations, sauvegardes, avec la chronologie des jugements, le tribunal, l'administrateur et le mandataire judiciaires.</li>"
             "<li><b>Plans sociaux et fermetures</b> annoncés (liste noire de la CGT, presse) et <b>accords d'entreprise</b> publiés sur Légifrance : accords de PSE, ruptures conventionnelles collectives, plans de départs volontaires, activité partielle de longue durée.</li>"
             "<li><b>Argent</b> : dernier résultat net publié, aides de l'ADEME et de France Relance dans les 24 mois avant l'annonce, part estimée du chiffre d'affaires venant de marchés publics.</li>"
             "<li><b>Influence</b> : lobbying déclaré à la HATVP (montants et objets), groupe et société mère.</li>"
             "<li><b>Territoire</b> : poids de l'entreprise dans l'emploi privé de la commune (URSSAF), mobilisations relevées par <a href=\"https://oraclemarin.fr/cabrule/\">ça brûle</a>.</li></ul>"
             f'<p><a href="{S.BASE}/explorer/">Explorateur</a> (filtres, tri par nombre de recoupements, export CSV) · <a href="{S.BASE}/alertes/">Alertes RSS</a> · '
             f'<a href="{S.BASE}/cette-semaine/">Cette semaine</a> · <a href="{S.BASE}/donnees/">Données ouvertes</a> · <a href="{S.BASE}/methode/">Méthode et corrections</a></p>'
             "<h2>Fiabilité et limites</h2><ul>"
             "<li>Chaque fait renvoie à son document d'origine. Le degré de certitude du rattachement d'une annonce à une entreprise est affiché : <b>sûr</b> (SIREN ou SIRET dans la source), <b>probable</b> (nom et établissement dans le département, puis relecture confirmant qu’il s’agit de la même entreprise), <b>indicatif</b> (nom seul, exclu des chiffres). Une taille incohérente ou une relecture négative retire le rattachement.</li>"
             "<li>Une coïncidence n'est pas une cause : une aide reçue avant une annonce ne finance pas le plan social. L'outil juxtapose des faits publics ; l'enquête reste à faire.</li>"
             f"<li>Couverture : procédures collectives complètes depuis le {esc(cv.get('bodacc_historique_depuis') or '—')} ; presse en continu depuis le {esc(cv.get('presse_depuis') or '—')} ; "
             f"liste CGT : dernière édition publiée par la CGT le {esc(cv.get('cgt_edition') or '—')}. Les entreprises de moins de 50 salariés en procédure ne sont pas suivies, ni les suppressions de postes non publiées.</li>"
             "<li>Les effectifs des plans sociaux sont ceux annoncés par la source (CGT, presse) ; ceux des procédures sont des tranches INSEE. Les chiffres officiels de défaillances sont ceux de la Banque de France.</li></ul>"
             "<h2>Citer et réutiliser</h2>"
             "<p>Citation : « Plans sociaux et faillites en France, oraclemarin.fr/plans-sociaux, consulté le [date] ». Pour un chiffre officiel, citez aussi la source d'origine (Banque de France, INSEE, BODACC).</p>"
             f"<p>Les données compilées (<a href=\"{S.BASE}/donnees/\">CSV et JSON</a>) sont réutilisables librement par la presse, la recherche, les syndicats et les associations, y compris dans un article ou une infographie, avec mention de la source (licence CC BY-NC-SA 4.0 ; usage commercial : sur accord). "
             "Les données d'origine restent soumises à leurs propres conditions (Licence Ouverte pour les données publiques ; les titres de presse appartiennent à leurs éditeurs).</p>"
             "<h2>Textes de présentation</h2>" + copie(court, 1) + copie(long_, 2) +
             "<h2>Rédactions, syndicats, fondations</h2>"
             "<p>Je peux construire pour une rédaction ou une organisation : une veille sur un territoire ou un secteur, une extraction et un recoupement de données pour une enquête, une carte ou une infographie. "
             "Je cherche aussi des <b>partenaires et des financements</b> pour que l'outil reste gratuit et ouvert à tous.</p>"
             f'<p><b>Contact</b> : Quentin Closset, <a href="mailto:{S.CONTACT}">{esc(S.CONTACT)}</a> · <a href="https://oraclemarin.fr/apropos/">qui suis-je</a> · '
             f'<a href="https://oraclemarin.fr/cabrule/presse">dossier de presse de ça brûle</a></p>'
             f'<p class="meta">Visuel de partage : <a href="{S.BASE}/og.png">og.png</a>. Données personnelles : <a href="https://oraclemarin.fr/rgpd/#plans-sociaux">mentions légales</a>.</p>'
             "<script>document.querySelectorAll('.copie button').forEach(b=>b.addEventListener('click',()=>{const t=document.getElementById(b.dataset.c).innerText;"
             "navigator.clipboard&&navigator.clipboard.writeText(t).then(()=>{b.textContent='Copié'})}))</script>")
    graph = [S.site_ld(), {"@type": "WebPage", "name": titre, "url": S.BASE_URL + "/presse/", "inLanguage": "fr-FR", "isPartOf": {"@id": S.BASE_URL + "/#site"},
             "author": {"@type": "Person", "name": "Quentin Closset", "url": "https://oraclemarin.fr/apropos/"}}]
    S.ecrire("presse/index.html", S.page(titre, desc, "presse/", corps, graph, "presse/"))
    return S.BASE_URL + "/presse/"
