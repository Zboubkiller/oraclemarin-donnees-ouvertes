# VERSION_PUBLIQUE : page référencée (menu pied de page, plan du site)
"""Page de travail « Recoupements » : trois lectures croisées de la base à partir des SIREN identifiés.
1. Dirigeants personnes morales communs : holdings qui dirigent plusieurs sociétés touchées (plan social, fermeture, procédure collective).
2. Aides publiques dans les 24 mois précédant une suppression d'emplois (ADEME et autres sources de la fiche).
3. Lobbying déclaré à la HATVP et suppressions d'emplois.
Page référencée (plan du site, pied de page).
Un dirigeant personne morale n'est pas un actionnaire ; une aide proche d'une suppression ne prouve aucun lien de cause."""
import csv, datetime as dt, json, os, re, sys
H = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, H)
import commun as S
esc, fr = S.esc, S.fr
MOIS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]
SUPPR = ("plan social", "fermeture", "départs volontaires")
PROC = SUPPR + ("liquidation", "redressement", "sauvegarde")
INVESTISSEURS_PUBLICS = ("BPIFRANCE", "CAISSE DES DEPOTS")

def mois(d): return f"{MOIS[int(d[5:7]) - 1]} {d[:4]}"
def n_emp(e): return e.get("emplois_max") or e.get("emplois_min") or 0
def meur(x): return (f"{x / 1e6:.1f}".replace(".", ",") + " M€") if x >= 1e5 else (f"{round(x / 1e3)} k€" if x else "—")

def retenus(EV):
    return [e for e in EV if e.get("siren") and not e.get("sans_entreprise") and not e.get("doublon_de") and not e.get("exclu_totaux")
            and e.get("source") != "Sirene" and e.get("date")]

def lien(nom, sir, FICHES):
    f = FICHES.get(sir)
    return f'<a href="{S.BASE}/entreprise/{esc(f)}/">{esc(nom)}</a>' if f else esc(nom)

def holdings(EV, FICHES):
    H_ = {}
    for e in retenus(EV):
        if e["type"] not in PROC or e["date"] < "2024-01-01": continue
        for d in (e.get("direction") or {}).get("dirigeants_pm") or []:
            if not d.get("siren") or d["siren"] == e["siren"]: continue
            h = H_.setdefault(d["siren"], {"nom": d["nom"], "s": {}})
            s = h["s"].setdefault(e["siren"], {"nom": e["entreprise"], "ev": []})
            s["ev"].append((e["date"][:10], e["type"], n_emp(e)))
    out = []
    for sir, h in H_.items():
        if len(h["s"]) < 2: continue
        tot = 0
        for s in h["s"].values():
            s["ev"].sort(reverse=True)
            s["emp"] = max((x[2] for x in s["ev"]), default=0); tot += s["emp"]
        out.append({"siren": sir, "nom": h["nom"], "s": h["s"], "tot": tot})
    out.sort(key=lambda h: (-len(h["s"]), -h["tot"]))
    return out

def aidees(EV):
    best = {}
    for e in retenus(EV):
        p = e.get("proximite") or {}
        if e["type"] not in SUPPR or not p.get("montant") or p["montant"] < 100000 or n_emp(e) < 30 or e["date"] < "2023-01-01": continue
        k = e["siren"]
        if k not in best or e["date"] > best[k]["date"]: best[k] = e
    return sorted(best.values(), key=lambda e: -e["proximite"]["montant"])

def lobbyistes(EV):
    best = {}
    for e in retenus(EV):
        if e["type"] not in SUPPR or not e.get("lobbying") or n_emp(e) < 50 or e["date"] < "2024-01-01": continue
        k = e["siren"]
        if k not in best or n_emp(e) > n_emp(best[k]): best[k] = e
    return sorted(best.values(), key=lambda e: -n_emp(e))


POS_EMPLOI = re.compile(r"\bCDI\b|cr[ée]ation[^.;]{0,50}emploi|maintien[^.;]{0,40}emploi|\d+\s*emplois?", re.I)
NEG_EMPLOI = re.compile(r"demandeurs? d.emploi|QUALIF|formation|stagiaires|PREPA|insertion", re.I)

def subv_emploi(EV):
    """Subventions de collectivités dont l'objet vise des créations ou maintiens d'emplois, suivies d'une annonce de suppression."""
    try: J = json.load(open(os.path.join(H, "subventions_locales_auto.json"), encoding="utf-8")).get("par_siren", {})
    except Exception: return []
    best = {}
    for e in retenus(EV):
        if e["type"] not in PROC or e["date"] < "2024-01-01": continue
        if e["siren"] not in best or e["date"] > best[e["siren"]]["date"]: best[e["siren"]] = e
    out = []
    for sir, e in best.items():
        L = [l for l in J.get(sir, []) if l.get("date") and l["date"][:10] <= e["date"][:10] and POS_EMPLOI.search(l.get("objet") or "") and not NEG_EMPLOI.search(l.get("objet") or "")]
        if L:
            out.append({"e": e, "L": sorted(L, key=lambda l: -l["montant"]), "tot": sum(l["montant"] for l in L)})
    out.sort(key=lambda r: -r["tot"])
    return out

def p_recoupements(EV, FICHES):
    HO, AI, LO, SE = holdings(EV, FICHES), aidees(EV), lobbyistes(EV), subv_emploi(EV)
    def bloc_h(h):
        pub = any(x in h["nom"].upper() for x in INVESTISSEURS_PUBLICS)
        lignes = "".join(
            f'<tr><td>{lien(s["nom"], sir, FICHES)}</td><td>{" · ".join(esc(t) + " " + esc(mois(d)) for d, t, _ in s["ev"][:2])}</td><td class="n">{fr(s["emp"]) if s["emp"] else "—"}</td></tr>'
            for sir, s in sorted(h["s"].items(), key=lambda kv: -kv[1]["emp"]))
        return (f'<details class="rc"><summary><b>{lien(h["nom"], h["siren"], FICHES)}</b> : {len(h["s"])} sociétés touchées, {fr(h["tot"])} emplois'
                f'{" <span class=pub>investisseur public</span>" if pub else ""}</summary>'
                f'<table><thead><tr><th>Société dirigée</th><th>Annonces depuis 2024</th><th class="n">Emplois</th></tr></thead><tbody>{lignes}</tbody></table></details>')
    corps_h = "".join(bloc_h(h) for h in HO[:40])
    def lig_a(e):
        p, r, c = e["proximite"], e.get("ratios") or {}, e.get("comptes") or {}
        ren = {True: "oui", False: "non"}.get(c.get("profitable"), "—")
        return (f'<tr><td>{lien(e["entreprise"], e["siren"], FICHES)}</td><td>{esc(e["type"])} {esc(mois(e["date"][:10]))}<br><small>{fr(n_emp(e))} emplois</small></td>'
                f'<td class="n">{meur(p["montant"])}<br><small>{p["n"]} aide{"s" if p["n"] > 1 else ""}</small></td>'
                f'<td class="n">{fr(r["aide_par_emploi"]) + " €" if r.get("aide_par_emploi") else "—"}</td><td class="n">{ren}</td>'
                f'<td><small>{esc((p.get("plus_grosse") or {}).get("source") or "")} {esc(((p.get("plus_grosse") or {}).get("date") or "")[:7])} : {esc(((p.get("plus_grosse") or {}).get("libelle") or "")[:110])}</small></td></tr>')
    corps_a = "".join(lig_a(e) for e in AI[:60])
    def lig_l(e):
        l = e["lobbying"]
        obj = (l.get("objets") or [""])[0][:170]
        return (f'<tr><td>{lien(e["entreprise"], e["siren"], FICHES)}</td><td>{esc(e["type"])} {esc(mois(e["date"][:10]))}<br><small>{fr(n_emp(e))} emplois</small></td>'
                f'<td class="n">{esc(str(l.get("annee") or ""))}<br><small>{esc(str(l.get("depenses") or ""))}</small></td><td><small>{esc(obj)}</small></td></tr>')
    corps_l = "".join(lig_l(e) for e in LO[:60])
    def lig_s(r):
        e, L = r["e"], r["L"]
        sub = "<br>".join('%s : %s <small>(%s)</small><br><small>« %s »</small>' % (esc(l["financeur"]), meur(l["montant"]), esc(l["date"][:7]), esc(l["objet"][:150])) for l in L[:2])
        return ('<tr><td>%s</td><td>%s %s<br><small>%s</small></td><td class="n">%s<br><small>%d subvention%s</small></td><td><small>%s</small></td></tr>'
                % (lien(e["entreprise"], e["siren"], FICHES), esc(e["type"]), esc(mois(e["date"][:10])), (fr(n_emp(e)) + " emplois") if n_emp(e) else "emplois non précisés",
                   meur(r["tot"]), len(L), "s" if len(L) > 1 else "", sub))
    corps_s = "".join(lig_s(r) for r in SE[:60])
    with open(os.path.join(S.PUB, "recoupements-aidees.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";"); w.writerow(["siren", "societe", "annonce", "date", "emplois", "aides_24_mois_eur", "nb_aides", "aide_par_emploi_eur", "rentable_dernier_exercice"])
        for e in AI:
            p, r, c = e["proximite"], e.get("ratios") or {}, e.get("comptes") or {}
            w.writerow([e["siren"], e["entreprise"], e["type"], e["date"][:10], n_emp(e), p["montant"], p["n"], r.get("aide_par_emploi") or "", c.get("profitable") if c else ""])
    with open(os.path.join(S.PUB, "recoupements-holdings.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";"); w.writerow(["siren_dirigeant", "dirigeant_personne_morale", "siren_societe", "societe", "annonce", "date", "emplois"])
        for h in HO:
            for sir, s in h["s"].items():
                for d, t, n in s["ev"][:1]: w.writerow([h["siren"], h["nom"], sir, s["nom"], t, d, n])
    css = ("<style>.bandeau{background:#FFF4D6;border:1px solid #C98A00;padding:10px 14px;margin:10px 0;font-size:14px}.tq{overflow-x:auto;margin:12px 0}.tq table,.rc table{border-collapse:collapse;width:100%;font-size:14px;background:#fff}"
           ".tq th,.tq td,.rc th,.rc td{border-bottom:1px solid #E3E6EA;padding:7px 9px;text-align:left;vertical-align:top}.tq th,.rc th{background:#F2F3F5;font-size:12.5px}"
           ".tq td.n,.tq th.n,.rc td.n,.rc th.n{text-align:right;white-space:nowrap}.rc{border:1px solid #D6DBE0;margin:6px 0;background:#fff;padding:6px 10px}.rc summary{cursor:pointer;padding:4px 0}"
           ".pub{background:#455A64;color:#fff;border-radius:4px;padding:1px 6px;font-size:12px;margin-left:6px}small{color:#5A6371}</style>")
    corps = (css + "<h1>Recoupements : holdings, aides et lobbying</h1>"
             "<p class=\"chapo\">Trois lectures croisées de la base, rendues possibles par l'identification des sociétés (SIREN). Elles rapprochent des faits publics ; elles n'établissent aucun lien de cause.</p>"
             '<p class="meta">Sommaire : <a href="#holdings">holdings</a> · <a href="#aides">aides puis suppressions</a> · <a href="#emploi">subventions liées à l\'emploi</a> · <a href="#lobbying">lobbying et suppressions</a> · '
             '<a href="../recoupements-aidees.csv">CSV des aides</a> · <a href="../recoupements-holdings.csv">CSV des holdings</a></p>'
             f'<h2 id="holdings">Holdings qui dirigent plusieurs sociétés touchées</h2><p>{len(HO)} dirigeants personnes morales apparaissent au registre à la tête d\'au moins deux sociétés de la base '
             'ayant annoncé un plan social, une fermeture ou une procédure collective depuis 2024. Les 40 premiers sont listés (dépliez une ligne).</p>' + corps_h +
             f'<h2 id="aides">Aides publiques dans les 24 mois, puis suppressions d\'emplois</h2><p>{len(AI)} sociétés ont annoncé 30 emplois supprimés ou plus depuis 2023 après avoir reçu au moins 100 000 € d\'aides '
             'rapprochées dans les 24 mois précédents. Les 60 premières sont listées, par montant d\'aides.</p><div class="tq"><table><thead><tr><th>Société</th><th>Annonce</th><th class="n">Aides (24 mois)</th>'
             '<th class="n">Aide par emploi</th><th class="n">Rentable</th><th>Plus grosse aide</th></tr></thead><tbody>' + corps_a + '</tbody></table></div>'
             f'<h2 id="emploi">Subventions liées à l\'emploi, puis suppressions</h2><p>{len(SE)} sociétés ont annoncé un plan social, une fermeture ou une procédure collective depuis 2024 après avoir reçu '
             'une subvention d\'une collectivité dont l\'objet vise des créations ou des maintiens d\'emplois (jeux ouverts de conventions de subvention). '
             'Un objectif d\'emplois dans l\'intitulé n\'est pas forcément un engagement contractuel : durée, suivi et contrôle ne sont pas publiés. La subvention peut aussi concerner un autre site que celui qui ferme (exemple : une aide pour Fougères, une fermeture à Mantes-la-Ville) : lisez l\'objet affiché.</p><div class="tq"><table><thead><tr><th>Société</th><th>Annonce</th>'
             '<th class="n">Subventions</th><th>Objet et financeur</th></tr></thead><tbody>' + corps_s + '</tbody></table></div>'
             f'<h2 id="lobbying">Lobbying déclaré et suppressions d\'emplois</h2><p>{len(LO)} sociétés ayant un lobbying déclaré à la HATVP ont annoncé 50 suppressions d\'emplois ou plus depuis 2024. '
             'Les 60 premières sont listées, par nombre d\'emplois ; l\'objet affiché est celui de la dernière déclaration retrouvée.</p><div class="tq"><table><thead><tr><th>Société</th><th>Annonce</th>'
             '<th class="n">Déclaration</th><th>Objet déclaré</th></tr></thead><tbody>' + corps_l + '</tbody></table></div>'
             '<h2>Méthode et limites</h2><ul>'
             '<li><b>Holdings</b> : « dirigeant personne morale » au registre des entreprises (par exemple président d\'une SAS). Ce n\'est pas un actionnaire ni une preuve d\'appartenance au même groupe. '
             'Bpifrance et la Caisse des dépôts sont signalées comme investisseurs publics : être dirigeant ne dit rien d\'une décision de suppression.</li>'
             '<li><b>Aides</b> : aides rapprochées par SIREN (ADEME et autres sources de la fiche) datées des 24 mois précédant l\'annonce. Elles ne sont pas forcément liées à l\'activité supprimée ; '
             'les contrats pluriannuels sont des plafonds, pas des sommes versées.</li>'
             '<li><b>Lobbying</b> : déclarations au registre de la HATVP rapprochées par SIREN. L\'absence de déclaration ne signifie pas l\'absence de lobbying (groupe, fédération).</li>'
             '<li><b>Emplois</b> : nombres annoncés par la presse ou les sources officielles, parfois pour un groupe entier ; une société n\'est comptée qu\'une fois (annonce la plus récente ou la plus forte).</li>'
             '<li>Aucun de ces tableaux n\'établit de lien de cause : ils mettent des faits publics côte à côte.</li></ul>'
             f'<p class="meta">Données arrêtées au {dt.date.today().strftime("%d/%m/%Y")}. Édité par Quentin Closset, Perros-Guirec.</p>')
    S.ecrire("recoupements/index.html", S.page("Recoupements : holdings, aides et lobbying autour des plans sociaux",
             "Holdings à la tête de plusieurs sociétés touchées, aides publiques avant suppressions d'emplois, lobbying déclaré : rapprochements de la base Plans sociaux et faillites.",
             "recoupements/", corps, None, "", robots="index,follow"))
    print(f"recoupements : {len(SE)} subventions emploi, {len(HO)} holdings, {len(AI)} aidées puis licenciantes, {len(LO)} lobbyistes avec suppressions")
    return S.BASE_URL + "/recoupements/"
