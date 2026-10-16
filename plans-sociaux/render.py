"""Pré-rend index.html depuis data.json : la liste et les chiffres sont lisibles sans JavaScript (robots, LLM)."""
import json, os, html, datetime as dt
import commun as C
H = os.path.dirname(os.path.abspath(__file__))
d = json.load(open(os.path.join(H, "public", "data.json")))
ev = d["evenements"]
lim = (dt.date.today() - dt.timedelta(days=30)).isoformat()
_b30 = {}
for e in ev:      # publications BODACC des 30 derniers jours, une fois par entreprise (même règle que compteur.py)
    if e["source"] == "BODACC" and e.get("siren") and (e.get("date_publication") or e.get("date") or "")[:10] >= lim:
        _b30[e["siren"]] = max(_b30.get(e["siren"], 0), e.get("emplois_min") or 0)
b30 = list(_b30)
emp = sum(_b30.values())
fr = lambda n: f"{n:,}".replace(",", "\u202f")
def emplois(e):
    if e.get("emplois_min") is None: return "effectif inconnu"
    if e.get("emplois_precision") == "annoncé": return f"{fr(e['emplois_min'])} emplois annoncés"
    return f"{fr(e['emplois_min'])} à {fr(e['emplois_max'])} salariés"
def eu(n):
    s, v = ("−" if n < 0 else ""), abs(n)
    return s + (f"{v/1e9:.1f} Md€".replace(".", ",") if v >= 1e9 else f"{v/1e6:.1f} M€".replace(".", ",") if v >= 1e6 else fr(int(v)) + " €")
def ap(e):
    a, c = e.get("argent_public") or {}, e.get("comptes")
    if not a and not c and not e.get("suite") and not e.get("emplois_note") and not e.get("groupe") and not e.get("lobbying") and not e.get("sanction_delais"): return ""
    p, h = [], ""
    m = a.get("marches")
    if m and m.get("n"): p.append(f'<a href="{html.escape(m["url"])}">{m["n"]} marché(s) public(s)</a> (titulaire unique), {eu(m["total"])} notifiés ({m["de"]}–{m["a"]})')
    if m and m.get("accords_cadres"): p.append(f'{m["accords_cadres"]["n"]} accord(s)-cadre non comptés (plafonds de {eu(m["accords_cadres"]["plafond"])}, pas des sommes versées)')
    if a.get("ademe"): p.append(f'<a href="{html.escape(a["ademe"]["url"])}">{a["ademe"]["n"]} aide(s) ADEME</a> pour {eu(a["ademe"]["total"])}')
    if a.get("minimis"): p.append(f'<a href="{html.escape(a["minimis"]["url"])}">{a["minimis"]["n"]} aide(s) de minimis</a> pour {eu(a["minimis"]["total"])}')
    av = a.get("avant_annonce")
    if av and av["total"] > 0: h += f'<div>Avant {av["annee"]} (année de l&#39;annonce) : <b>{eu(av["total"])}</b> de marchés et d&#39;aides ADEME.</div>'
    if p: h += "<div>Argent public : " + " ; ".join(p) + "</div>"
    if c and c.get("derniere_annee"):
        h += f'<div>Comptes {c["derniere_annee"]} : résultat net <b>{eu(c["resultat_net"])}</b>' + (f' pour {eu(c["ca"])} de CA' if c.get("ca") else "") + f' ; bénéfice {c["annees_benefice"]} année(s) sur {c["annees"]}. <a href="{html.escape(c["url"])}">Annuaire (État)</a></div>'
        if c.get("profitable") and (not c.get("ca") or c["resultat_net"] / c["ca"] >= 0.03) and e["type"] in ("plan social", "fermeture"): h += '<div class="alerte">Annonce un plan alors que les derniers comptes sont bénéficiaires (marge d\'au moins 3 %).</div>'
    dp = e.get("dependance_publique")
    if dp: h += f'<div>Commande publique : au moins environ <b>{dp["part_pct"]:.0f} %</b> du chiffre d\'affaires {dp["annee"]} (estimation par défaut, à partir de {dp["n_marches"]} marchés, étalés sur leur durée).</div>'
    l = {"nom_seul": "Identifiée par son nom seul : il peut s'agir de la maison mère ou d'un homonyme, montants indicatifs.",
         "nom+dep": "Entreprise rapprochée par son nom (établissement présent dans le département) : à vérifier.",
         "siret_commune": "Établissement de l'entreprise trouvé dans la commune de l'annonce (SIRET " + str(e.get("siret") or "") + ")."}.get(e.get("lien"))
    lb, vu = e.get("lobbying"), e.get("verif_urssaf")
    if lb: h += f'<div>Lobbying déclaré à la HATVP : <b>{html.escape(lb["depenses"])}</b> en {html.escape(lb["annee"])}' + (f', notamment « {html.escape(lb["objets"][0][:120])} »' if lb.get("objets") else "") + f'. <a href="{html.escape(lb["url"])}">Fiche HATVP</a></div>'
    for sd in e.get("sanction_delais") or []:
        h += f'<div>Amende de la DGCCRF pour retards de paiement aux fournisseurs : <b>{eu(sd["montant"])}</b> ({html.escape(sd["date"])}{", " + html.escape(sd["nom"]) + ", même groupe" if sd["niveau"] == "groupe" else ""}). <a href="{html.escape(sd["url"])}">Décision</a></div>'
    if (e.get("bonne_boite") or {}).get("fort"): h += '<div>France Travail estime, par algorithme, que cet établissement a un fort potentiel d’embauche (La Bonne Boîte).</div>'
    if vu: h += f'<div>Vérification URSSAF : emploi salarié du secteur à {html.escape(vu["commune"] or "")} : {fr(vu["avant"])} ({vu["annee_avant"]}) → <b>{fr(vu["apres"])}</b> ({vu["annee_apres"]}).</div>'
    g = e.get("groupe")
    if g and g["nom"].lower()[:6] != (e.get("entreprise") or "").lower()[:6]: h += f'<div>Groupe : <b>{html.escape(g["nom"])}</b>' + (f' ({html.escape(g["pays"])})' if g.get("pays") else "") + f' <span class="statut">[{html.escape(g["source"])}]</span></div>'
    if e.get("emplois_note"): h += f'<div class="statut">Nombre d’emplois relevé dans l’article : {html.escape(e["emplois_note"])}.</div>'
    su = e.get("suite")
    if su: h += '<div>Suite de la procédure : <b>' + {"liquidation": "liquidation", "cession": "plan de cession", "plan": "plan de redressement ou de sauvegarde", "en cours": "aucune décision publiée à ce jour"}[su["issue"]] + '</b>' + (f' ({html.escape(su["date"])})' if su.get("date") else "") + '.</div>'
    if l: h += f'<div class="statut">{l}</div>'
    return f'<details class="ap"><summary>Détails : comptes, argent public…</summary>{h}</details>' if h else ""

MOIS_FR = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]
def mois_fr(m): return MOIS_FR[int(m[5:7]) - 1] + " " + m[:4]
def signe(v): return "—" if v is None else ("+" if v > 0 else "−" if v < 0 else "") + str(abs(v)) + " %"
def graphe(serie):
    if not serie: return ""
    W, Hh, base = 720, 150, 130
    mx = max(max(s["n"], s["n_an_avant"]) for s in serie) or 1
    bw = W / len(serie)
    parts = []
    for i, s in enumerate(serie):
        h = base * s["n"] / mx; x = i * bw
        parts.append(f'<rect x="{x + 3:.1f}" y="{base - h:.1f}" width="{bw - 6:.1f}" height="{h:.1f}" fill="#17202E"><title>{mois_fr(s["mois"])} : {fr(s["n"])} (an dernier : {fr(s["n_an_avant"])})</title></rect>')
        yy = base - base * s["n_an_avant"] / mx
        parts.append(f'<line x1="{x + 1:.1f}" x2="{x + bw - 1:.1f}" y1="{yy:.1f}" y2="{yy:.1f}" stroke="#E8B21E" stroke-width="3"/>')
        if i % 3 == 0: parts.append(f'<text x="{x + bw / 2:.1f}" y="{Hh - 2}" font-size="11" text-anchor="middle" fill="#5B6573">{MOIS_FR[int(s["mois"][5:7]) - 1]} {s["mois"][2:4]}</text>')
    return (f'<svg viewBox="0 0 {W} {Hh}" role="img" aria-label="Ouvertures de procédures collectives par mois sur 24 mois, avec le niveau du même mois un an plus tôt" '
            f'style="width:100%;height:auto;max-width:720px">{"".join(parts)}</svg>')

def decisions_html(n=14):
    """Derniers jugements (hors ouvertures et formalités) publiés pour des entreprises suivies, avec lien vers leur fiche."""
    try:
        import pages_fiche as PF
        G = PF.groupes(d.get("evenements", []))
    except Exception:
        return ""
    vus, L = set(), []
    for s, evs in G.items():
        for e in evs:
            for t in e.get("chronologie") or []:
                nat = t["nature"]; k = (s, nat, t["date"])
                if k in vus or any(x in nat.lower() for x in ("ouverture", "dépôt", "état des créances", "rectificatif", "modifiant", "faillite personnelle", "interdiction de gérer")): continue
                vus.add(k); L.append((t["date"], s, PF.nom_de(evs), nat, PF.url_fiche(s, PF.nom_de(evs))))
    L.sort(reverse=True)
    if not L: return ""
    court = lambda n: (n.replace("Jugement de conversion en liquidation judiciaire", "conversion en liquidation").replace("Jugement arrêtant un plan de cession", "plan de cession")
                       .replace("Jugement arrêtant le plan de cession", "plan de cession").replace("Jugement arrêtant le plan de redressement", "plan de redressement")
                       .replace("Jugement arrêtant le plan de sauvegarde", "plan de sauvegarde").replace("Jugement de clôture", "clôture").replace("Jugement prononçant", "").strip())
    return ('<h3>Dernières décisions publiées</h3><ul class="cas">' + "".join(
        f'<li><b><a href="{u}">{html.escape(nom)}</a></b> : {html.escape(court(nat))} <span class="meta">({html.escape(dte)})</span></li>' for dte, s, nom, nat, u in L[:n])
        + f'</ul><p class="meta"><a href="{C.BASE}/cette-semaine/">Tout ce qui a bougé cette semaine</a>.</p>')

def synthese_html():
    out = []
    try: tj = json.load(open(os.path.join(H, "public", "tendance.json")))
    except Exception: tj = None
    of = C.lire("officiel.json", {}) or {}
    if tj:
        a = tj["toutes_tailles"]; r6 = a.get("recent_6_mois_hors_ruptures") or a["recent_6_mois"]
        dfl = of.get("defaillances")
        tete = ""
        if dfl:
            m = dfl["dernier_mois"]
            tete = (f'<p class="gros"><b>{fr(dfl["cumul_12_mois"])}</b> défaillances d\'entreprises sur les douze mois à fin {C.mois_long(m)}, '
                    f'soit <b>{C.pct(dfl["variation_pct"])}</b> sur un an, selon la Banque de France (chiffre officiel, environ deux mois de recul).</p>')
        out.append(f'<div class="bloc"><h2>Les défaillances d\'entreprises : où en est-on ?</h2>{tete}'
                   f'<p>Signal plus récent, le BODACC : {fr(r6["n"])} jugements d\'ouverture publiés entre {mois_fr(r6["periode"][0])} et {mois_fr(r6["periode"][1])}, '
                   f'{signe(r6["variation_pct"])} par rapport aux mêmes mois un an plus tôt (hors Alsace-Moselle). Ce décompte est irrégulier : la tendance de fond est celle de la Banque de France.</p>'
                   f'{graphe(a["serie"])}<p class="meta">Barres : jugements publiés au BODACC par mois. Trait jaune : même mois un an plus tôt. Toutes tailles d\'entreprise. '
                   f'<a href="{C.BASE}/faillites-entreprises/">Tous les chiffres : secteurs, départements, créations</a>.</p>')
        hs = [x for x in a["departements"] if not x["alerte"]][:5]
        al = [x for x in a["departements"] if x["alerte"]]
        out.append('<h3>Départements où ça monte</h3><ul class="cas">' + "".join(
            f'<li><b><a href="{C.dep_url(x["dep"])}">{html.escape(C.DEPS.get(x["dep"], x["dep"]))} ({html.escape(x["dep"])})</a></b> : {signe(x["variation_pct"])} ({fr(x["precedent"])} → {fr(x["recent"])} procédures sur 6 mois)</li>' for x in hs) + '</ul>')
        notes = []
        for x in al:
            if x["variation_pct"] <= -50: notes.append(f'{x["dep"]} ({signe(x["variation_pct"])})')
        if notes:
            out.append('<p class="meta">Non comparables : ' + ", ".join(notes) + ' (Moselle, Bas-Rhin, Haut-Rhin) affichent un effondrement brutal à partir de fin 2025 qui ressemble à un changement de publication dans la source, pas à une amélioration. '
                       'Les départements dont la hausse repose sur un seul mois sont écartés du classement.</p>')
        g = tj.get("plus_de_50_salaries") or {}
        if g.get("comparable") and g.get("recent_6_mois"):
            gr = g["recent_6_mois"]
            out.append(f'<h3>Entreprises de 50 salariés et plus</h3><p class="gros"><b>{fr(gr["n"])}</b> procédures sur {mois_fr(gr["periode"][0])} – {mois_fr(gr["periode"][1])}, <b>{signe(gr["variation_pct"])}</b> '
                       f'sur un an, pour au moins {fr(gr["emplois_min"])} salariés (contre {fr(gr["emplois_min_an_avant"])}). Effectif par tranche INSEE : ordre de grandeur.</p>')
            sec = [s for s in g.get("secteurs", []) if s["variation_pct"] is not None and s["precedent"] >= 6][:5]
            if sec: out.append('<ul class="cas">' + "".join(f'<li>{html.escape(s["nom"])} : {signe(s["variation_pct"])} ({s["precedent"]} → {s["recent"]})</li>'
                                                       for s in sorted(sec, key=lambda s: -s["variation_pct"])) + '</ul>')
        elif g.get("couverture"):
            out.append(f'<p class="meta">Version « 50 salariés et plus » en cours de constitution : historique BODACC couvert du {g["couverture"][0]} au {g["couverture"][1]}.</p>')
        out.append('</div>')
    sj = (tj or {}).get("suites")
    if sj and any(v["n"] for v in sj["types"].values()):
        lib = {"redressement": "redressement judiciaire", "sauvegarde": "sauvegarde"}
        li = "".join(f'<li><b>{lib[k]}</b> ({v["n"]} entreprises) : liquidation {v["liquidation"]} ({round(100 * v["liquidation"] / v["n"])} %), plan de cession {v["cession"]}, '
                     f'plan de redressement ou de sauvegarde {v["plan"]}, aucune décision publiée {v["en cours"]}</li>' for k, v in sj["types"].items() if v["n"])
        out.append(f'<div class="bloc"><h2>Que deviennent les entreprises en procédure ?</h2><p class="gros">Entreprises de 50 salariés et plus dont la procédure a été ouverte entre le {sj["periode_ouverture"][0]} et le {sj["periode_ouverture"][1]} :</p>'
                   f'<ul class="cas">{li}</ul><p class="meta">État à ce jour d\'après les jugements publiés au BODACC, qui publie avec retard : « aucune décision publiée » n\'est pas une survie. Les liquidations ouvertes d\'emblée ne sont pas comptées ici.</p>'
                   + decisions_html() + '</div>')
    sy = d.get("synthese")
    if sy and sy.get("plans_avec_comptes_fiables"):
        cb = "".join(f'<li><b>{html.escape(c["entreprise"] or "")}</b>, {c["emplois"] and fr(c["emplois"]) + " emplois, " or ""}annonce {html.escape(c["date"] or "")} : '
                     f'résultat net {eu(c["resultat_net"])} ({c["annee_comptes"]})</li>' for c in sy["cas_benefice"][:5])
        cp = "".join(f'<li><b>{html.escape(c["entreprise"] or "")}</b>, annonce {html.escape(c["date"] or "")} : '
                     + (f'{c["n"]} aide(s) dans les 24 mois, dont la plus récente {c["plus_recente"]["delai_mois"]} mois avant ({html.escape(c["plus_recente"]["source"])}'
                        + (f', {eu(c["plus_recente"]["montant"])}' if c["plus_recente"]["montant"] else ", montant non publié") + ")")
                     + (f', total ADEME {eu(c["montant"])}' if c["montant"] else "") + '</li>' for c in sy["cas_proximite"][:3])
        cd = "".join(f'<li><b>{html.escape(c["entreprise"] or "")}</b>, annonce {html.escape(c["date"] or "")} : au moins environ {c["part_pct"]:.0f} % du CA {c["annee"]} venait de marchés publics (estimation par défaut)</li>' for c in sy.get("cas_dependance", [])[:2])
        out.append(f'<div class="bloc"><h2>Licencier malgré les bénéfices, après des aides ?</h2>'
                   f'<p class="gros"><b>{sy["dont_benefice"]}</b> des {sy["plans_avec_comptes_fiables"]} entreprises annonçant un plan social ou une fermeture (entreprise identifiée de façon sûre ou probable, comptes récents) '
                   f'avaient un résultat net positif sur leur dernier exercice publié. <b>{sy["proximite_aide_24_mois"]}</b> avaient reçu une aide de l\'ADEME ou été lauréates de France Relance dans les 24 mois précédant l\'annonce.</p>'
                   + (f'<h3>Dernier exercice bénéficiaire</h3><ul class="cas">{cb}</ul><p class="meta"><a href="{C.BASE}/explorer/#ben=1&tri=nr-">Les {sy["dont_benefice"]} cas dans l\'explorateur</a></p>' if cb else "")
                   + (f'<h3>Aide puis annonce</h3><ul class="cas">{cp}</ul><p class="meta"><a href="{C.BASE}/explorer/#aide=1&tri=nr-">Dans l\'explorateur : toutes les entreprises aidées dans les 24 mois avant un événement, y compris les procédures collectives</a></p>' if cp else "")
                   + (f'<h3>Forte dépendance à la commande publique</h3><ul class="cas">{cd}</ul>' if cd else "")
                   + f'<p class="meta">{html.escape(sy["definition"])} Une corrélation n\'est pas un lien de cause à effet : une aide à un projet ne finance pas le plan social. Dates de l\'annonce au mois près.</p></div>')
    return "".join(out)

def cpt_vars():
    vide = {k: "" for k in ("CPT_N", "CPT_E", "CPT_S", "CPT_DEPUIS", "CPT_NOTE", "CPT_E_NOTE", "CPT_S_NOTE")}
    try: c = json.load(open(os.path.join(H, "public", "compteur.json")))
    except Exception: return vide
    p = c["periodes"]["annee"]; ea, sp = p.get("emplois_annonces") or {}, p.get("salaries_procedures") or {}
    return {"CPT_N": fr(p["reel"]), "CPT_E": fr(ea.get("min", 0)), "CPT_S": fr(sp.get("min", 0)), "CPT_DEPUIS": C.date_long(p["depuis"]),
            "CPT_NOTE": f'Décompte exact au BODACC ({c["maj"][:16].replace("T", " ")} UTC) : {fr(p["reel"])}.',
            "CPT_E_NOTE": f'{fr(ea.get("plans", 0))} plans ou fermetures. ' + p.get("note_emplois", ""),
            "CPT_S_NOTE": f'{fr(sp.get("entreprises", 0))} entreprises. Ce ne sont pas des licenciements.'}

def encart_liens():
    try:
        import pages_liens; return pages_liens.encart_hub()
    except Exception as ex:
        print("liens (hub) :", ex); return ""

def geo_vars():
    D = C.charge(); F = C.faits(D); q = C.faq(F)
    titre = "Plans sociaux et faillites en France : suivi quotidien"
    desc = ("Suivi quotidien et sourcé des faillites d'entreprises, des procédures collectives (liquidations, redressements) des entreprises de 50 salariés "
            "et plus et des plans sociaux en France, recoupés avec les chiffres officiels.")
    return {"HEAD": C.head_meta(titre, desc, C.BASE_URL + "/") + C.ld_tag([C.site_ld(), C.dataset_ld(D), C.faq_ld(q)]),
            "NAV": C.nav_html(""), "PIED": C.PIED, "BASE": C.BASE, "ENCART_LIENS": encart_liens(),
            "FAQ": "<h2>Questions fréquentes</h2>" + "".join(f"<h3>{html.escape(a)}</h3><p>{html.escape(b)}</p>" for a, b in q)}
items = []
for e in [x for x in ev if (x.get("date") or "") >= lim and not x.get("sans_entreprise") and not x.get("exclu_totaux") and x.get("entreprise") != x.get("titre")][:150]:
    t = e["type"]; c = "t-plan" if t == "plan social" else "t-" + t.replace(" ", "-")
    items.append(f'<li><div><span class="tag {c}">{html.escape(t)}</span><span class="ent">{html.escape(e.get("entreprise") or "")}</span></div>'
                 f'<div class="meta">{", ".join(x for x in [(html.escape(e["commune"]) + (" (" + html.escape(e["dep"]) + ")" if e.get("dep") else "")) if e.get("commune") else "", (C.mois_court(e["date"]) if e.get("date_precision") == "mois" and e.get("date") else (("jugé le " + e["date"] + ", publié le " + e["date_publication"][:10]) if e.get("source") == "BODACC" and e.get("date_publication") and e["date_publication"][:10] != e.get("date") else e.get("date") or "")), emplois(e)] if x)}</div>'
                 f'<div class="meta">{html.escape(e.get("detail") or "")} <a href="{html.escape(e.get("url") or "")}">Source : {html.escape(e["source"])}</a>{(" (" + html.escape(e["statut"]) + ")") if e.get("statut") else ""}</div>{ap(e)}</li>')
maj = dt.datetime.fromisoformat(d["maj"]).astimezone().strftime("%d/%m %Hh%M")
t = open(os.path.join(H, "template.html")).read()
for k, v in {"N30": fr(len(b30)), "EMP30": fr(emp), "NPLANS": fr(sum(1 for e in ev if e["source"].startswith("CGT"))),
             "MAJ": maj, "VER": d["maj"].replace(":", "").replace("-", "")[:13], "LISTE": "".join(items), "SYNTHESE": synthese_html(), **cpt_vars(), **geo_vars()}.items():
    t = t.replace("{{%s}}" % k, v)
tmp = os.path.join(H, "public", "index.html.tmp"); open(tmp, "w").write(t); os.replace(tmp, os.path.join(H, "public", "index.html"))
print("index.html rendu :", len(b30), "procédures / 30 j,", emp, "salariés min")
