# VERSION_PUBLIQUE : page référencée (page « Pistes à explorer », plan du site)
"""Page « Reprises et rechutes » : faits du BODACC et du registre des entreprises, sans nom de personne physique.
1. Rechutes : une société dont le tribunal a arrêté un plan (redressement, sauvegarde ou cession), puis qui rouvre une procédure ou est liquidée au moins six mois plus tard.
2. Chaînes : une société créée après la cession ou la liquidation d'une autre société de la base, qui partage avec elle au moins un dirigeant (personne morale, ou personne physique non nommée), et qui est à son tour en procédure.
Une reprise par un dirigeant ou un proche est encadrée par la loi et peut être autorisée par le tribunal : la page rapproche des faits, elle ne qualifie aucune intention."""
import csv, datetime as dt, json, os, sys
H = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, H)
import commun as S
esc, fr = S.esc, S.fr
MOIS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]
def mois(d):
    try: return f"{MOIS[int(d[5:7]) - 1]} {d[:4]}"
    except Exception: return d or "—"

def p_reprises(EV, FICHES):
    try: R = json.load(open(os.path.join(H, "reprises.json"), encoding="utf-8"))
    except Exception: return None
    def lien(s, nom):
        f = FICHES.get(s)
        return f'<a href="{esc(f) if f.startswith("/") else S.BASE + "/entreprise/" + esc(f) + "/"}">{esc(nom)}</a>' if f else esc(nom)
    rech = R["rechutes"]; cha = R["chaines"]
    lr = "".join(f'<tr><td>{lien(r["siren"], r["nom"])}</td><td>{esc(r["type"])}<br><small>{esc(mois(r["plan"]))}</small></td><td>{esc(mois(r["puis"]))}'
                 + (f'<br><small>liquidation {esc(mois(r["liq"]))}</small>' if r.get("liq") and r["liq"] >= r["puis"] else "") + f'</td><td class="n">{fr(r["emplois"]) if r["emplois"] else "—"}</td><td>{"actif" if r["actif"] else "cessé"}</td></tr>' for r in rech[:50])
    lc = "".join(f'<tr><td>{lien(c["a"], c["nom_a"])}<br><small>{esc(c["nature_a"])} {esc(mois(c["date_a"]))}</small></td><td>{lien(c["b"], c["nom_b"])}<br><small>créée le {esc(c["creation_b"][:10])}</small></td>'
                 f'<td>{esc(c["type_b"])} {esc(mois(c["date_b"]))}<br><small>{(fr(c["emplois_b"]) + " emplois") if c["emplois_b"] else "emplois non précisés"}</small></td><td>{esc(c["dirigeant_commun"])}<br><small>{c["n_communs"]} dirigeant(s) en commun</small></td></tr>' for c in cha[:50])
    with open(os.path.join(S.PUB, "reprises-rechutes.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";"); w.writerow(["siren", "societe", "plan_ou_cession_date", "type", "nouvelle_procedure_date", "liquidation_date", "emplois", "en_activite"])
        for r in rech: w.writerow([r["siren"], r["nom"], r["plan"], r["type"], r["puis"], r.get("liq") or "", r["emplois"], "oui" if r["actif"] else "non"])
    with open(os.path.join(S.PUB, "reprises-chaines.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";"); w.writerow(["siren_a", "societe_a", "evenement_a", "date_a", "siren_b", "societe_b", "creation_b", "evenement_b", "date_b", "emplois_b", "dirigeant_commun", "nb_dirigeants_communs"])
        for c in cha: w.writerow([c["a"], c["nom_a"], c["nature_a"], c["date_a"][:10], c["b"], c["nom_b"], c["creation_b"], c["type_b"], c["date_b"][:10], c["emplois_b"], c["dirigeant_commun"], c["n_communs"]])
    if cha:
        bloc_ch = '<div class="tq"><table><thead><tr><th>Société A</th><th>Société B</th><th>Situation de B</th><th>Dirigeant commun</th></tr></thead><tbody>' + lc + '</tbody></table></div>'
    else:
        bloc_ch = ("<p><b>Aucune chaîne de ce type n’a été détectée dans la base.</b> Sur " + fr(R["n_societes"]) + " sociétés examinées, aucune société créée après l’ouverture de la procédure d’une autre société de la base "
                   "ne partage un dirigeant avec elle tout en étant elle-même en procédure ou en plan social. Ce résultat ne dit rien des sociétés hors base, ni des reprises par des proches non inscrits comme dirigeants : "
                   "il montre seulement que, dans ce périmètre, le schéma n’apparaît pas.</p>")
    css = ("<style>.tq{overflow-x:auto;margin:12px 0}.tq table{border-collapse:collapse;width:100%;font-size:14px;background:#fff}.tq th,.tq td{border-bottom:1px solid #E3E6EA;padding:7px 9px;text-align:left;vertical-align:top}"
           ".tq th{background:#F2F3F5;font-size:12.5px}.tq td.n,.tq th.n{text-align:right}small{color:#5A6371}.bandeau{background:#FFF4D6;border:1px solid #C98A00;padding:10px 14px;margin:10px 0;font-size:14px}</style>")
    corps = (css + "<h1>Reprises et rechutes</h1><p class=\"chapo\">Que deviennent les sociétés dont le tribunal a arrêté un plan ? Et quand une société disparaît, en retrouve-t-on le ou les dirigeants à la tête d’une société plus récente, elle-même en difficulté ? "
             "Cette page rapproche des faits du BODACC et du registre des entreprises. Elle ne qualifie aucune intention.</p>"
             '<div class="bandeau"><b>À lire avant de citer.</b> Une reprise par un dirigeant ou un proche est encadrée par la loi (le tribunal peut l’autoriser) ; un dirigeant commun à deux sociétés est fréquent et n’a rien d’anormal en soi. '
             'Les personnes physiques ne sont pas nommées ici : la correspondance se fait sur le nom, le prénom et l’année de naissance du registre, et les homonymes sont possibles. Chaque rapprochement est à vérifier dans les annonces du BODACC avant publication.</div>'
             f'<p class="meta">{fr(R["n_societes"])} sociétés examinées (procédure collective, fermeture ou plan social depuis 2023) : {len(rech)} rechutes, {len(cha)} chaînes. Sommaire : <a href="#rechutes">rechutes</a> · <a href="#chaines">chaînes</a> · '
             '<a href="../reprises-rechutes.csv">CSV des rechutes</a> · <a href="../reprises-chaines.csv">CSV des chaînes</a></p>'
             '<h2 id="rechutes">Rechutes : un plan, puis une nouvelle procédure</h2><p>Sociétés dont le BODACC publie un plan de redressement, de sauvegarde ou de cession, puis une nouvelle ouverture de procédure ou une liquidation au moins six mois plus tard. Les 50 premières, par nombre d’emplois.</p>'
             '<div class="tq"><table><thead><tr><th>Société</th><th>Plan ou cession</th><th>Nouvelle procédure</th><th class="n">Emplois</th><th>Registre (retard possible)</th></tr></thead><tbody>' + lr + '</tbody></table></div>'
             '<h2 id="chaines">Chaînes : une société, puis une plus récente avec un dirigeant commun</h2><p>Société A cédée ou liquidée ; société B créée après cette date, avec au moins un dirigeant en commun, en procédure ou en plan social depuis moins de cinq ans après sa création. '
             'Les dirigeants présents dans plus de huit sociétés de la base (holdings, investisseurs, mandataires) sont écartés. Les 50 premières, par nombre d’emplois de la société B.</p>'
             + bloc_ch +
             "<h2>Méthode et limites</h2><ul><li><b>Sources</b> : BODACC (nature des jugements et dates) et registre des entreprises (dates de création, dirigeants). Seules les sociétés de la base sont examinées : un chaînon hors base est invisible.</li>"
             "<li><b>Rechute</b> : plan arrêté (redressement, sauvegarde ou cession) puis nouvelle ouverture ou liquidation à six mois d’écart ou plus. Une rechute n’est pas une faute : beaucoup de plans échouent pour des raisons de marché.</li>"
             "<li><b>Chaîne</b> : correspondance de dirigeants personnes morales (SIREN) ou personnes physiques (nom, premier prénom, année de naissance). Elle ne prouve ni contrôle capitalistique ni reprise de l’activité de A par B.</li>"
             "<li>Aucun de ces tableaux n’affirme une fraude ni un montage : ce sont des pistes à vérifier auprès du greffe, du mandataire judiciaire et des salariés.</li></ul>"
             f'<p class="meta">Données arrêtées au {dt.date.today().strftime("%d/%m/%Y")}. Édité par Quentin Closset, Perros-Guirec.</p>')
    S.ecrire("reprises/index.html", S.page("Reprises et rechutes : plans arrêtés puis nouvelle procédure, chaînes de sociétés",
             "Sociétés dont le tribunal a arrêté un plan puis qui rouvrent une procédure, et sociétés créées après une cession ou liquidation avec un dirigeant commun : faits du BODACC et du registre, sans qualifier d'intention.",
             "reprises/", corps, None, "", robots="index,follow"))
    print(f"reprises : {len(rech)} rechutes, {len(cha)} chaînes")
    return S.BASE_URL + "/reprises/"
