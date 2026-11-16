# VERSION_PUBLIQUE : page référencée (page « Pistes à explorer », plan du site)
"""Page « Fermetures et sites classés » : sociétés en liquidation ou en fermeture (depuis 2024) qui exploitent ou exploitaient une installation classée (ICPE) soumise à autorisation ou Seveso,
avec ce que le registre des installations classées (Géorisques) dit du site : état administratif, mises en demeure, mesures d'urgence ou conservatoires, servitudes, dernière inspection.
Question posée : qui assure la remise en état quand l'exploitant disparaît ? Aucun constat de pollution n'est affirmé : la page signale des dossiers à demander à la DREAL."""
import csv, datetime as dt, gzip, json, os, re, sys, unicodedata
H = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, H)
import commun as S
esc, fr = S.esc, S.fr
TYPES = ("liquidation", "fermeture")
MOIS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]
def norm(s):
    s = unicodedata.normalize("NFD", (s or "").lower()); s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", s).strip()
def mois(d): return f"{MOIS[int(d[5:7]) - 1]} {d[:4]}"
def n_emp(e): return e.get("emplois_max") or e.get("emplois_min") or 0
def docs(x, *types):
    L = [d for d in x.get("documents") or [] if d[0] in types]
    return len(L), (max(d[1] for d in L if d[1]) if any(d[1] for d in L) else "")

def candidats(EV):
    ICPE = json.load(gzip.open("/opt/donnees-externes/georisques/icpe_national.json.gz", "rt", encoding="utf-8"))
    par = {}
    for x in ICPE:
        if x.get("siret"): par.setdefault(x["siret"][:9], []).append(x)
    best = {}
    for e in EV:
        if (e["type"] not in TYPES or not e.get("siren") or (e.get("date") or "") < "2024-01-01" or e.get("doublon_de") or e.get("sans_entreprise") or e.get("exclu_totaux") or e.get("source") == "Sirene"): continue
        if e["siren"] not in best or e["date"] > best[e["siren"]]["date"]: best[e["siren"]] = e
    out = []
    for sir, e in best.items():
        sites = []
        for x in par.get(sir, []):
            risque = x["seveso"] != "Non Seveso" and x["seveso"] or ""
            if not (x["regime"] == "Autorisation" or risque or x.get("ied")): continue
            md, md_d = docs(x, "Arrêté de mise en demeure", "AP mise en demeure")
            ur, ur_d = docs(x, "AP mesures d'urgence", "AP mesures conservatoires", "AP de mesures d'évaluations et/ou remèdes")
            su, _ = docs(x, "AP servitude d'utilité publique")
            ins = sorted(x.get("inspections") or [])
            meme = norm(x["commune"]) == norm(e.get("commune")) and bool(x["commune"])
            sites.append({"nom": x["nom"], "commune": x["commune"], "dep": (x["insee"] or "")[:2], "regime": x["regime"], "seveso": risque, "ied": bool(x.get("ied")), "etat": x["etat"] or "non renseigné",
                          "md": md, "md_d": md_d, "ur": ur, "ur_d": ur_d, "su": su, "insp_n": len(ins), "insp_d": ins[-1] if ins else "", "aiot": x.get("aiot"), "meme": meme})
        if not sites: continue
        sites.sort(key=lambda s: (-s["meme"], {"Seveso seuil haut": 0, "Seveso seuil bas": 1}.get(s["seveso"], 2), -s["ur"], -s["md"]))
        pri = (3 if any(s["seveso"] == "Seveso seuil haut" for s in sites if s["meme"]) else 0) + (2 if any(s["seveso"] for s in sites if s["meme"]) else 0) + (2 if any(s["ur"] for s in sites if s["meme"]) else 0) \
              + (1 if any(s["md"] for s in sites if s["meme"]) else 0) + (1 if any(s["su"] for s in sites if s["meme"]) else 0) + (1 if e["type"] == "liquidation" else 0) + (2 if any(s["meme"] for s in sites) else 0)
        out.append({"e": e, "sites": sites, "pri": pri})
    out.sort(key=lambda c: (-c["pri"], -n_emp(c["e"])))
    return out

def p_sols(EV, FICHES):
    C = candidats(EV)
    def lien(e):
        f = FICHES.get(e["siren"])
        return f'<a href="{esc(f) if f.startswith("/") else S.BASE + "/entreprise/" + esc(f) + "/"}">{esc(e["entreprise"])}</a>' if f else esc(e["entreprise"])
    def sit(s):
        tags = []
        if s["seveso"]: tags.append(f'<span class="r">{esc(s["seveso"])}</span>')
        tags.append(esc(s["regime"] + (", directive IED" if s["ied"] else "")))
        faits = []
        if s["md"]: faits.append(f'{s["md"]} mise{"s" if s["md"] > 1 else ""} en demeure (dernière : {esc(s["md_d"][:7])})')
        if s["ur"]: faits.append(f'{s["ur"]} arrêté{"s" if s["ur"] > 1 else ""} de mesures d’urgence, conservatoires ou d’évaluation (dernier : {esc(s["ur_d"][:7])})')
        if s["su"]: faits.append(f'{s["su"]} servitude{"s" if s["su"] > 1 else ""} d’utilité publique')
        faits.append(f'{s["insp_n"]} inspection{"s" if s["insp_n"] > 1 else ""} publiée{"s" if s["insp_n"] > 1 else ""}' + (f' (dernière : {esc(s["insp_d"][:7])})' if s["insp_d"] else ""))
        lien_g = f'https://www.georisques.gouv.fr/risques/installations/donnees/details/{esc(s["aiot"])}' if s.get("aiot") else ""
        return (f'<li>{"<b>" if s["meme"] else ""}{esc(s["nom"])}, {esc((s["commune"] or "").title())}{"</b>" if s["meme"] else ""} · {" · ".join(tags)} · état : {esc(s["etat"])}'
                f'<br><small>{" ; ".join(faits)}' + (f' · <a href="{lien_g}" rel="noopener">fiche Géorisques</a>' if lien_g else "") + "</small></li>")
    def lig(c):
        e = c["e"]; meme = [s for s in c["sites"] if s["meme"]]
        sites = c["sites"][:4]
        return (f'<tr><td>{lien(e)}</td><td>{esc(e["type"])} {esc(mois(e["date"][:10]))}<br><small>{esc((e.get("commune") or "").title())} ({esc(e.get("dep") or "")}) · '
                f'{(fr(n_emp(e)) + " emplois") if n_emp(e) else "emplois non précisés"}</small></td>'
                f'<td><ul class="si">{"".join(sit(s) for s in sites)}</ul>' + (f'<small>+ {len(c["sites"]) - 4} autre(s) site(s) classé(s)</small>' if len(c["sites"]) > 4 else "") + '</td>'
                f'<td class="n">{"site de l’annonce" if meme else "autre site"}</td></tr>')
    with open(os.path.join(S.PUB, "fermetures-sites-classes.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";"); w.writerow(["siren", "societe", "annonce", "date", "emplois", "site_icpe", "commune_site", "site_de_l_annonce", "regime", "seveso", "etat", "mises_en_demeure", "mesures_urgence_ou_remedes", "servitudes", "inspections", "derniere_inspection", "priorite"])
        for c in C:
            for s in c["sites"]:
                w.writerow([c["e"]["siren"], c["e"]["entreprise"], c["e"]["type"], c["e"]["date"][:10], n_emp(c["e"]), s["nom"], s["commune"], "oui" if s["meme"] else "non", s["regime"], s["seveso"], s["etat"], s["md"], s["ur"], s["su"], s["insp_n"], s["insp_d"], c["pri"]])
    nm = sum(1 for c in C if any(s["meme"] for s in c["sites"])); nsev = sum(1 for c in C if any(s["seveso"] for s in c["sites"]))
    css = ("<style>.tq{overflow-x:auto;margin:12px 0}.tq table{border-collapse:collapse;width:100%;font-size:14px;background:#fff}.tq th,.tq td{border-bottom:1px solid #E3E6EA;padding:7px 9px;text-align:left;vertical-align:top}"
           ".tq th{background:#F2F3F5;font-size:12.5px}.tq td.n{white-space:nowrap}.si{margin:0;padding-left:16px}.si li{margin:3px 0}.r{background:#B3261E;color:#fff;border-radius:4px;padding:0 6px;font-size:12px}small{color:#5A6371}</style>")
    corps = (css + "<h1>Fermetures et sites classés</h1><p class=\"chapo\">Quand une société qui exploite une installation classée pour la protection de l’environnement (ICPE) ferme ou est liquidée, qui assure la remise en état du site ? "
             "Cette page liste les sociétés en liquidation ou en fermeture depuis 2024 qui ont un site classé soumis à autorisation ou Seveso, avec ce que le registre officiel dit de ce site. Elle ne constate aucune pollution : elle signale des dossiers à demander à la DREAL.</p>"
             f'<p class="meta">{len(C)} sociétés ; {nm} avec un site classé dans la commune de l’annonce ; {nsev} avec au moins un site Seveso. Les 80 premières sont affichées, par priorité ; '
             '<a href="../fermetures-sites-classes.csv">CSV complet</a>.</p>'
             '<div class="tq"><table><thead><tr><th>Société</th><th>Annonce</th><th>Sites classés (registre Géorisques)</th><th>Rapprochement</th></tr></thead><tbody>' + "".join(lig(c) for c in C[:80]) + "</tbody></table></div>"
             "<h2>Lire et vérifier</h2><ul><li><b>Priorité</b> : site dans la commune de l’annonce, classement Seveso, arrêtés de mesures d’urgence ou conservatoires, mises en demeure, servitudes, puis liquidation. Ce n’est pas une mesure de pollution.</li>"
             "<li><b>État administratif</b> : « en exploitation avec titre » après une fermeture peut signifier que la cessation d’activité n’a pas encore été notifiée ou enregistrée ; le registre peut aussi avoir du retard.</li>"
             "<li><b>Mises en demeure et mesures</b> : elles sont comptées d’après les documents publiés au registre, sans en lire le contenu. Elles peuvent concerner des manquements sans rapport avec le sol.</li>"
             "<li><b>Questions à poser</b> : à la DREAL (dossier de cessation d’activité, état des sols, garanties financières), à la préfecture (arrêtés), au mandataire liquidateur (devenir du site), à l’ADEME et à la collectivité (financement d’une éventuelle remise en état si l’exploitant a disparu).</li>"
             "<li><b>Sources</b> : registre des installations classées (Géorisques), base Plans sociaux et faillites pour les annonces. Les sites pollués (BASOL, secteurs d’information sur les sols) ne sont pas recoupés ici faute de jeu national ouvert accessible : consultez Géorisques pour la commune.</li></ul>"
             f'<p class="meta">Données arrêtées au {dt.date.today().strftime("%d/%m/%Y")}. Édité par Quentin Closset, Perros-Guirec.</p>')
    S.ecrire("sites-classes/index.html", S.page("Fermetures et sites classés : qui assure la remise en état quand l'exploitant disparaît ?",
             "Sociétés en liquidation ou en fermeture qui exploitent une installation classée soumise à autorisation ou Seveso : état, mises en demeure, mesures d'urgence, inspections, questions à poser à la DREAL.",
             "sites-classes/", corps, None, "", robots="index,follow"))
    print(f"sites classés : {len(C)} sociétés, {nm} sur la commune de l'annonce, {nsev} Seveso")
    return S.BASE_URL + "/sites-classes/"
