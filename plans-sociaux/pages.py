"""Pages rendues côté serveur pour le référencement (moteurs et assistants IA), régénérées après chaque collecte :
faillites-entreprises/, liste/, departements/, departement/<code>-<nom>/, methode/, donnees/ (+ evenements.csv),
rss.xml, sitemap.xml, llms.txt, og.png, favicon.png.
Usage : python3 pages.py [--indexnow]   (--indexnow : signale aux moteurs IndexNow les pages qui changent chaque jour)"""
import csv, io, json, os, sys, datetime as dt, urllib.request
from email.utils import format_datetime
import commun as S
from commun import esc, fr, pct, eu, mois_long, mois_court, date_long

D = S.charge(); F = S.faits(D); TD = S.tend_dep()
EV = D["data"].get("evenements", [])
AUJ = dt.date.today(); AN = AUJ.year; AN0 = f"{AN}-01-01"
FICHES = {}
INDEXNOW_KEY = "cd6be145f5c44dec205bfa1d8c0d6968"

def mois_complets(n):
    t = AUJ.replace(day=1); out = []
    for _ in range(n):
        t = (t - dt.timedelta(days=1)).replace(day=1); out.append(t.strftime("%Y-%m"))
    return out[::-1]
def an_avant(m): return f"{int(m[:4]) - 1}{m[4:]}"
def var(a, b): return None if not b else round(100 * (a - b) / b, 1)

def barres(serie, titre, ref=True, h=150):
    """Histogramme SVG accessible : serie = [(mois, n, n_an_avant)]."""
    if not serie: return ""
    W, base = 720, h - 22
    mx = max(max(n, r or 0) for _, n, r in serie) or 1
    bw = W / len(serie); p = []
    for i, (m, n, r) in enumerate(serie):
        hh = base * n / mx; x = i * bw
        p.append(f'<rect x="{x + 2:.1f}" y="{base - hh:.1f}" width="{bw - 4:.1f}" height="{hh:.1f}" fill="#17202E"><title>{mois_court(m)} : {fr(n)}'
                 + (f" (un an plus tôt : {fr(r)})" if ref and r is not None else "") + "</title></rect>")
        if ref and r is not None:
            yy = base - base * r / mx
            p.append(f'<line x1="{x + 1:.1f}" x2="{x + bw - 1:.1f}" y1="{yy:.1f}" y2="{yy:.1f}" stroke="#E8B21E" stroke-width="3"/>')
        if i % max(1, len(serie) // 8) == 0:
            p.append(f'<text x="{x + bw / 2:.1f}" y="{h - 4}" font-size="11" text-anchor="middle" fill="#5B6573">{mois_court(m)}</text>')
    return f'<svg viewBox="0 0 {W} {h}" role="img" aria-label="{esc(titre)}" style="width:100%;height:auto;max-width:720px">{"".join(p)}</svg>'

def mini(points, titre, fmt=lambda v: fr(v), coul="#17202E", h=120):
    """Petite courbe pour le contexte économique : [(mois, valeur)], min et max annotés."""
    if len(points) < 3: return ""
    W, g, d = 340, 4, 4
    vals = [v for _, v in points]; lo, hi = min(vals), max(vals); pad = (hi - lo) * 0.12 or 1; lo, hi = lo - pad, hi + pad
    X = lambda i: g + i * (W - g - d) / (len(points) - 1); Y = lambda v: 8 + (h - 30) * (hi - v) / (hi - lo)
    pts = " ".join(f"{X(i):.1f},{Y(v):.1f}" for i, (_, v) in enumerate(points))
    return (f'<svg viewBox="0 0 {W} {h}" role="img" aria-label="{esc(titre)}" style="width:100%;height:auto">'
            f'<polyline points="{pts}" fill="none" stroke="{coul}" stroke-width="2.5"/>'
            f'<circle cx="{X(len(points) - 1):.1f}" cy="{Y(vals[-1]):.1f}" r="4" fill="{coul}"/>'
            f'<text x="{g}" y="{h - 6}" font-size="11" fill="#5B6573">{mois_court(points[0][0])}</text>'
            f'<text x="{W - d}" y="{h - 6}" font-size="11" fill="#5B6573" text-anchor="end">{mois_court(points[-1][0])} : {fmt(vals[-1])}</text></svg>')

def dares_html():
    da = S.lire("dares.json")
    dr = F.get("dares")
    if not (da and dr): return ""
    L, V = da["licenciements_eco"], da["pse_valides"]
    trim = lambda t: f"{t[-1]}{'er' if t[-1] == '1' else 'e'} trim. {t[:4]}"
    pts_l = [(x["t"][:4] + "-" + ("%02d" % (int(x["t"][-1]) * 3)), x["inscriptions"]) for x in L]
    pts_v = [(x["t"][:4] + "-" + ("%02d" % (int(x["t"][-1]) * 3)), x["ruptures"]) for x in V]
    # couverture : emplois annoncés recensés sur le site (liste CGT) face aux ruptures prévues dans les PSE validés, par année complète
    cgt = {}
    for e in EV:
        if str(e.get("source", "")).startswith("CGT") and e.get("emplois_min") and e.get("date"):
            cgt[e["date"][:4]] = cgt.get(e["date"][:4], 0) + e["emplois_min"]
    lignes = "".join(f"<tr><td>{y}</td><td class=n>{fr(n)}</td><td class=n>{fr(cgt.get(y, 0))}</td><td class=n>{round(100 * cgt.get(y, 0) / n)} %</td></tr>"
                     for y, n in sorted(dr["ruptures_annee"].items()) if y >= "2023")
    return (f'<h2>Les licenciements économiques : les chiffres officiels</h2>'
            f'<p class="gros">Au {trim(dr["t"])}, <b>{fr(dr["inscriptions"])}</b> personnes se sont inscrites à France Travail après un licenciement économique, '
            f'<b>{pct(dr["var_an"])}</b> sur un an{" (données provisoires)" if dr["provisoire"] else ""}. Sur le même trimestre, <b>{dr["pse"]}</b> plans de sauvegarde de l\'emploi '
            f'ont été validés ou homologués, pour <b>{fr(dr["ruptures"])}</b> ruptures de contrat prévues.</p>'
            '<div class="ctxg">'
            f'<div class="ctx"><h3>Inscriptions à France Travail après un licenciement économique</h3><p class="meta">par trimestre, CVS-CJO</p>{mini(pts_l, "Inscriptions après licenciement économique", coul="#B8361E")}</div>'
            f'<div class="ctx"><h3>Ruptures de contrat prévues dans les PSE validés ou homologués</h3><p class="meta">par trimestre, CVS-CJO</p>{mini(pts_v, "Ruptures prévues dans les PSE")}</div></div>'
            f'<p class="meta">Source : <a href="{esc(da["url"])}">Dares</a>, publication du {date_long(da.get("publication") or "")}. Le site de la Dares bloque les téléchargements automatiques : '
            "ces séries sont relevées à la main à chaque publication trimestrielle. L'effet de la loi pour le plein emploi (inscription automatique depuis janvier 2025) "
            "invite à la prudence sur l'évolution des inscriptions.</p>"
            + (f'<h3>Quelle part des plans la liste CGT capte-t-elle ?</h3><div class="tablo"><table><thead><tr><th>Année</th><th class=n>Ruptures prévues dans les PSE (Dares)</th>'
               f'<th class=n>Emplois annoncés dans la liste CGT</th><th class=n>Rapport</th></tr></thead><tbody>{lignes}</tbody></table></div>'
               "<p class=\"meta\">Comparaison indicative : la liste CGT compte aussi des emplois menacés hors PSE (redressements, départs volontaires) et ne recense pas tous les PSE, "
               "notamment les petits. Les deux chiffres ne mesurent pas exactement la même chose.</p>" if lignes else ""))

def contexte_html():
    """Chaque secteur de défaillances face à un indicateur qui le concerne. Mis en regard, pas une explication."""
    M = (S.lire("macro.json", {}) or {}).get("series", {})
    sec = {s["secteur"]: s for s in (D["officiel"].get("defaillances") or {}).get("secteurs", []) if s.get("serie")}
    tot = (D["officiel"].get("defaillances") or {}).get("serie_cumul", [])
    def carte_def(titre, serie, var):
        if not serie: return ""
        return (f'<div class="ctx"><h3>{esc(titre)}</h3><p class="meta">Défaillances sur 12 mois glissants (Banque de France) · {pct(var)} sur un an</p>'
                + mini([(x["mois"], x["n"]) for x in serie], titre, coul="#B8361E") + "</div>")
    def carte_ind(k, fmt):
        s = M.get(k)
        if not s: return ""
        dn = s.get("dernier") or {}
        return (f'<div class="ctx"><h3>{esc(s["nom"])}</h3><p class="meta">{esc(s["unite"])} · {pct(dn.get("variation_pct"))} sur un an · '
                f'<a href="{esc(s["url"])}">{esc(s["source"])}</a></p>' + mini([(x["mois"], x["v"]) for x in s["serie"]], s["nom"], fmt) + "</div>")
    f1 = lambda v: f"{v:.1f}".replace(".", ","); f2 = lambda v: f"{v:.2f}".replace(".", ",") + " %"; fe = lambda v: f"{v:.0f} €"
    paires = [("Toutes les entreprises et le coût du crédit", carte_def("Défaillances, tous secteurs", tot[-36:], (D["officiel"]["defaillances"] or {}).get("variation_pct")), carte_ind("taux_credit", f2)),
              ("Transports et prix du pétrole", carte_def("Défaillances, transports et entreposage", (sec.get("Transports et entreposage") or {}).get("serie"), (sec.get("Transports et entreposage") or {}).get("variation_pct")), carte_ind("brent_eur", fe)),
              ("Industrie, énergie et production", carte_def("Défaillances, industrie", (sec.get("Industrie") or {}).get("serie"), (sec.get("Industrie") or {}).get("variation_pct")),
               carte_ind("prix_electricite", f1) + carte_ind("production_industrielle", f1)),
              ("Le moral des entreprises", carte_ind("climat_affaires", f1), carte_ind("climat_emploi", f1))]
    blocs = "".join(f'<h3 class="paire">{esc(t)}</h3><div class="ctxg">{a}{b}</div>' for t, a, b in paires if a or b)
    if not blocs: return ""
    return ('<h2>Contexte économique</h2><p>Chaque secteur est placé à côté d\'un indicateur qui le concerne directement. Ces courbes sont <b>mises en regard, '
            "pas proposées comme une explication</b> : sur deux ou trois ans, deux séries peuvent évoluer ensemble sans lien de cause à effet, et une défaillance "
            "a presque toujours plusieurs causes.</p>"
            '<style>.ctxg{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px}.ctx{background:var(--papier);border:1px solid var(--trait);padding:6px 12px 8px}'
            '.ctx h3{margin:6px 0 0;font-size:1rem}.ctx .meta{margin:2px 0 4px}h3.paire{font:700 1.25rem "Barlow Condensed",sans-serif;margin:22px 0 6px}</style>' + blocs)

def courbe(serie, titre, h=170):
    """Courbe SVG pour une série lente (cumul sur 12 mois) : axe vertical resserré, signalé sous le graphique."""
    if len(serie) < 2: return ""
    W, g, d, hb = 720, 64, 16, h - 26
    vals = [n for _, n in serie]; lo, hi = min(vals), max(vals)
    pad = max((hi - lo) * 0.15, hi * 0.01); lo, hi = lo - pad, hi + pad
    X = lambda i: g + i * (W - g - d) / (len(serie) - 1)
    Y = lambda v: 10 + (hb - 10) * (hi - v) / (hi - lo)
    pts = " ".join(f"{X(i):.1f},{Y(n):.1f}" for i, (_, n) in enumerate(serie))
    p = [f'<line x1="{g}" x2="{W - d}" y1="{Y(v):.1f}" y2="{Y(v):.1f}" stroke="#C9CFD6"/><text x="{g - 6}" y="{Y(v) + 4:.1f}" font-size="11" text-anchor="end" fill="#5B6573">{fr(v)}</text>'
         for v in (lo + (hi - lo) * k / 3 for k in range(4))]
    p.append(f'<polyline points="{pts}" fill="none" stroke="#17202E" stroke-width="3"/>')
    for i, (m, n) in enumerate(serie):
        p.append(f'<circle cx="{X(i):.1f}" cy="{Y(n):.1f}" r="3.5" fill="#E8B21E"><title>{mois_court(m)} : {fr(n)}</title></circle>')
        if i % max(1, len(serie) // 6) == 0 or i == len(serie) - 1:
            p.append(f'<text x="{X(i):.1f}" y="{h - 6}" font-size="11" text-anchor="middle" fill="#5B6573">{mois_court(m)}</text>')
    return f'<svg viewBox="0 0 {W} {h}" role="img" aria-label="{esc(titre)}" style="width:100%;height:auto;max-width:720px">{"".join(p)}</svg>'

def ligne_ev(e, dep_lien=True):
    lieu = esc(e.get("commune") or "")
    if e.get("dep"):
        d = e["dep"]; lieu += (" " if lieu else "") + (f'(<a href="{S.dep_url(d)}">{esc(d)}</a>)' if dep_lien and d in S.DEPS else f"({esc(d)})")
    if e.get("emplois_min") is None: emp = "effectif inconnu"
    elif e.get("emplois_precision") == "annoncé": emp = f"{fr(e['emplois_min'])} emplois annoncés"
    else: emp = (f"{fr(e['emplois_min'])} salariés" if e['emplois_min'] == e['emplois_max'] else f"{fr(e['emplois_min'])} à {fr(e['emplois_max'])} salariés")
    notes = []
    if e.get("emplois_note"): notes.append("effectif relu : " + esc(e["emplois_note"]))
    g = e.get("groupe")
    if g and S.cle_nom(g["nom"]) != S.cle_nom(e.get("entreprise")): notes.append(f"groupe : {esc(g['nom'])}" + (f" ({esc(g['pays'])})" if g.get("pays") else "") + f" [{esc(g['source'])}]")
    lb = e.get("lobbying")
    if lb: notes.append(f"lobbying déclaré (HATVP) : {esc(lb['depenses'])} en {esc(lb['annee'])}" + (f", notamment : « {esc(lb['objets'][0][:110])} »" if lb.get("objets") else ""))
    for sd in e.get("sanction_delais") or []:
        notes.append(f"amende DGCCRF pour retards de paiement : {eu(sd['montant'])} ({esc(sd['date'][:7])}{', ' + esc(sd['nom']) if sd['niveau'] == 'groupe' else ''})")
    if (e.get("bonne_boite") or {}).get("fort"): notes.append("classé « fort potentiel d'embauche » par France Travail (La Bonne Boîte, estimation algorithmique)")
    vu = e.get("verif_urssaf")
    if vu: notes.append(f"URSSAF, emploi du secteur à {esc(vu['commune'])} : {fr(vu['avant'])} ({vu['annee_avant']}) → {fr(vu['apres'])} ({vu['annee_apres']})")
    dl = S.delocalisation(e)
    if dl: notes.append("délocalisation" + (f" ({esc(dl['pays'])})" if dl["pays"] else ""))
    pl = e.get("poids_local")
    if pl and pl.get("part_commune_pct", 0) >= 1 and pl["part_commune_pct"] <= 100:
        notes.append(f"{str(pl['part_commune_pct']).replace('.', ',')} % de l'emploi salarié privé de {esc(pl['commune'])}")
    c = e.get("comptes")
    if e.get("fiable") and c and c.get("profitable") and e["type"] in ("plan social", "fermeture"):
        notes.append(f"dernier exercice bénéficiaire ({eu(c['resultat_net'])} en {c['derniere_annee']})")
    su = e.get("suite")
    if su and su["issue"] != "en cours": notes.append({"liquidation": "puis liquidation", "cession": "puis plan de cession", "plan": "puis plan de continuation"}[su["issue"]])
    dte = mois_court(e["date"]) if e.get("date_precision") == "mois" and e.get("date") else (e.get("date") or "")
    if e.get("sources"): dte += f" · {1 + len(e['sources'])} sources"
    acs = [a for a in e.get("accords") or [] if a["url"] != e.get("url")]
    if acs: notes.append("accord d'entreprise : " + "; ".join(f"{esc(a['libelle'])} ({esc(a['date'][:7])})" for a in acs[-3:]))
    if e.get("mobilisations"): dte += f" · mobilisation signalée ({len(e['mobilisations'])} article{'s' if len(e['mobilisations']) > 1 else ''})"
    if e.get("source") == "BODACC" and e.get("date_publication") and e["date_publication"][:10] != e.get("date"): dte += f" (publié le {e['date_publication'][:10]})"
    fu = FICHES.get(e.get("siren")) if (e.get("source") == "BODACC" or e.get("lien") in ("siren_source", "siret_commune", "nom+dep")) else None
    return (f'<tr><td class="n">{esc(dte)}</td><td><a href="{esc(fu) if fu else esc(e.get("url") or "")}" rel="noopener">{esc(e.get("entreprise") or "")}</a>'
            f'{f" · <a href={chr(34)}{esc(e.get('url') or '')}{chr(34)} rel=noopener>annonce</a>" if fu and e.get("url") else ""}'
            f'{"<br><span class=meta>" + "; ".join(notes) + "</span>" if notes else ""}</td><td>{esc(e["type"])}</td><td>{lieu}</td><td class="n">{emp}</td>'
            f'<td class="meta">{esc(e["source"])}</td></tr>')
TABLE_EV = '<div class="tablo"><table><thead><tr><th>Date</th><th>Entreprise</th><th>Type</th><th>Lieu</th><th class="n">Effectif</th><th>Source</th></tr></thead><tbody>{}</tbody></table></div>'

def citer(titre, chemin):
    return (f'<h2>Citer cette page</h2><p>« {esc(titre)} », {esc(S.NOM)}, {S.BASE_URL}/{chemin}, consulté le {date_long(AUJ.isoformat())}. '
            "Les chiffres changent chaque jour : indiquez la date de consultation et, pour un chiffre officiel, la source d'origine (Banque de France, INSEE, BODACC).</p>")

# ----------------------------------------------------------------------------------------------------------------- pages
def p_faillites():
    b, a, t = F.get("bdf"), F.get("annee"), D["tendance"].get("toutes_tailles") or {}
    titre = f"Faillites d'entreprises en France en {AN} : chiffres à jour"
    desc = (f"{fr(b['n'])} défaillances d'entreprises sur 12 mois à fin {mois_long(b['mois'])} ({pct(b['var'])}, Banque de France)" if b else "Défaillances d'entreprises en France")
    if a: desc += f", {fr(a['procedures'])} procédures publiées au BODACC depuis janvier : par secteur, par département, mis à jour chaque jour."
    q = S.faq(F)
    corps = f"<h1>Faillites d'entreprises en France en {AN}</h1>"
    if b:
        corps += (f'<p class="chapo"><b>{fr(b["n"])} défaillances d\'entreprises</b> ont été prononcées en France sur les douze mois {S.de_mois(b["debut"])} à '
                  f'{mois_long(b["mois"])}, soit <b>{pct(b["var"])}</b> sur un an, selon la Banque de France.'
                  + (f' Depuis le 1er janvier {AN}, le BODACC a publié <b>{fr(a["procedures"])}</b> jugements d\'ouverture de procédure collective.' if a else "")
                  + f'</p><p class="meta">Mis à jour le {date_long(AUJ.isoformat())}. Chiffre officiel : série INSEE <a href="{esc(b["url"])}">{esc(D["officiel"]["defaillances"]["idbank"])}</a> '
                  "(source Banque de France, défaillances comptées à la date du jugement, publiées avec environ deux mois de recul).</p>")
        sc = D["officiel"]["defaillances"].get("serie_cumul", [])
        corps += ('<div class="bloc"><h2>Le chiffre officiel : cumul sur douze mois</h2>'
                  + courbe([(x["mois"], x["n"]) for x in sc], "Défaillances d'entreprises, cumul sur 12 mois glissants, Banque de France")
                  + '<p class="meta">Chaque point : nombre de défaillances des douze mois qui précèdent. L\'axe vertical ne part pas de zéro, pour rendre visible '
                  'une évolution de quelques pour cent. Source : Banque de France, via l\'INSEE.</p></div>')
    if t.get("serie"):
        r6 = t.get("recent_6_mois_hors_ruptures") or t["recent_6_mois"]
        corps += ('<div class="bloc"><h2>Le signal quotidien : jugements publiés au BODACC</h2>'
                  f'<p class="gros">Entre {mois_long(r6["periode"][0])} et {mois_long(r6["periode"][1])} : <b>{fr(r6["n"])}</b> jugements d\'ouverture publiés, '
                  f'<b>{pct(r6["variation_pct"])}</b> par rapport aux mêmes mois un an plus tôt (hors Alsace-Moselle, voir plus bas).</p>'
                  + barres([(x["mois"], x["n"], x["n_an_avant"]) for x in t["serie"]], "Jugements d'ouverture publiés au BODACC par mois, avec le même mois un an plus tôt")
                  + '<p class="meta">Barres : mois de publication. Trait jaune : même mois un an plus tôt. Le BODACC publie par paquets irréguliers : '
                  "une variation sur un ou deux mois n'est pas significative.</p></div>")
    sec = F.get("secteurs") or []
    if sec:
        corps += ('<h2>Par secteur</h2><div class="tablo"><table><thead><tr><th>Secteur</th><th class="n">Défaillances sur 12 mois</th><th class="n">Sur un an</th></tr></thead><tbody>'
                  + "".join(f'<tr><td>{esc(s["secteur"])}</td><td class="n">{fr(s["cumul_12_mois"])}</td><td class="n">{pct(s["variation_pct"])}</td></tr>' for s in sec)
                  + f'</tbody></table></div><p class="meta">Banque de France, cumul sur douze mois à fin {mois_long(sec[0]["mois"])}.</p>')
    deps = [x for x in t.get("departements", []) if not x.get("alerte")]
    if deps:
        corps += ('<h2>Par département</h2><p>Départements où les jugements publiés augmentent le plus (six derniers mois complets, contre les mêmes mois un an plus tôt) :</p>'
                  '<div class="tablo"><table><thead><tr><th>Département</th><th class="n">6 derniers mois</th><th class="n">Un an plus tôt</th><th class="n">Évolution</th></tr></thead><tbody>'
                  + "".join(f'<tr><td><a href="{S.dep_url(x["dep"])}">{esc(S.DEPS.get(x["dep"], x["dep"]))} ({esc(x["dep"])})</a></td><td class="n">{fr(x["recent"])}</td>'
                            f'<td class="n">{fr(x["precedent"])}</td><td class="n">{pct(x["variation_pct"])}</td></tr>' for x in deps[:15])
                  + f'</tbody></table></div><p><a href="{S.BASE}/departements/">Tous les départements</a>. Moselle, Bas-Rhin et Haut-Rhin sont exclus : '
                  "leurs publications s'effondrent brutalement fin 2025, ce qui ressemble à un changement dans la source et non à une amélioration.</p>")
    g = D["tendance"].get("plus_de_50_salaries") or {}
    corps += "<h2>Entreprises de 50 salariés et plus</h2>"
    if g.get("comparable") and g.get("recent_6_mois"):
        gr = g["recent_6_mois"]
        corps += (f'<p>{fr(gr["n"])} procédures entre {mois_long(gr["periode"][0])} et {mois_long(gr["periode"][1])}, {pct(gr["variation_pct"])} sur un an, '
                  f'dans des entreprises qui comptent au moins {fr(gr["emplois_min"])} salariés au total (tranches d\'effectif INSEE).</p>')
    else:
        cov = g.get("couverture")
        corps += ("<p>L'historique des entreprises de 50 salariés et plus est en cours de constitution (chaque procédure doit être rapprochée de l'effectif "
                  "de l'entreprise)" + (f" : il couvre aujourd'hui du {date_long(cov[0])} au {date_long(cov[1])}" if cov else "") + ". La comparaison sur un an apparaîtra ici dès qu'elle sera possible.</p>")
    sj = D["tendance"].get("suites")
    if sj and any(v["n"] for v in sj["types"].values()):
        corps += ("<h2>Que deviennent les entreprises en redressement ?</h2><ul>" + "".join(
            f'<li><b>{"Redressement judiciaire" if k == "redressement" else "Sauvegarde"}</b>, {v["n"]} entreprises de 50 salariés et plus : '
            f'{v["liquidation"]} liquidées ({round(100 * v["liquidation"] / v["n"])} %), {v["cession"]} cédées, {v["plan"]} avec un plan de continuation, '
            f'{v["en cours"]} sans décision publiée.</li>' for k, v in sj["types"].items() if v["n"])
            + f'</ul><p class="meta">Procédures ouvertes entre le {date_long(sj["periode_ouverture"][0])} et le {date_long(sj["periode_ouverture"][1])}, état à ce jour d\'après le BODACC.</p>')
    cr = F.get("creations")
    if cr:
        corps += (f'<h2>Et les créations d\'entreprises ?</h2><p>{fr(cr["cumul_12_mois"])} entreprises créées sur les douze mois à fin {mois_long(cr["dernier_mois"])} '
                  f'({pct(cr["variation_pct"])} sur un an, INSEE), dont {str(cr["dont_micro_pct"]).replace(".", ",")} % de micro-entrepreneurs. '
                  "Il y a donc bien plus de créations que de faillites, mais les deux ne se compensent pas en emplois : la plupart des créations n'ont aucun salarié, "
                  "alors qu'une défaillance peut toucher des centaines de salariés. Ce site ne calcule donc pas de « solde » d'emplois.</p>")
    corps += dares_html() + contexte_html()
    cp = F.get("comparaison")
    if cp:
        corps += (f'<h2>Pourquoi le BODACC et la Banque de France ne donnent pas le même chiffre</h2><p>Sur la même période ({mois_long(cp["periode"][0])} à {mois_long(cp["periode"][1])}), '
                  f'la Banque de France compte {fr(cp["banque_de_france"])} défaillances, le BODACC {fr(cp["bodacc_site"])} jugements d\'ouverture, soit {str(abs(cp["ecart_pct"])).replace(".", ",")} % {"de plus" if cp["ecart_pct"] >= 0 else "de moins"}. '
                  f'{esc(cp["explication"])} Le chiffre de référence est celui de la Banque de France ; le BODACC sert de signal avancé et de détail local.</p>')
    corps += "<h2>Questions fréquentes</h2>" + "".join(f"<h3>{esc(a)}</h3><p>{esc(r)}</p>" for a, r in q[:2] + q[-2:]) + citer(titre, "faillites-entreprises/")
    graph = [S.site_ld(), S.dataset_ld(D, S.BASE_URL + "/faillites-entreprises/", f"Faillites d'entreprises en France en {AN}", desc), S.faq_ld(q[:2] + q[-2:])]
    S.ecrire("faillites-entreprises/index.html", S.page(titre, desc, "faillites-entreprises/", corps, graph, "faillites-entreprises/"))

def poids_html(plans):
    """Annonces qui pèsent le plus dans l'emploi salarié privé de leur commune (URSSAF)."""
    vus, lignes = set(), []
    for e in sorted([e for e in plans if (e.get("poids_local") or {}).get("part_commune_pct", 0) >= 5],
                    key=lambda e: -e["poids_local"]["part_commune_pct"]):
        k = (e.get("entreprise"), e["poids_local"]["insee"])
        if k in vus: continue
        vus.add(k); p = e["poids_local"]
        part = "plus que l'emploi salarié privé recensé dans la commune" if p["part_commune_pct"] > 100 else f"{str(p['part_commune_pct']).replace('.', ',')} % de l'emploi salarié privé de la commune"
        lignes.append(f'<li><b>{esc(e["entreprise"])}</b> à {esc(p["commune"])} : {fr(e["emplois_min"])} emplois annoncés, soit {part} '
                      f'({fr(p["effectif_commune"])} salariés en {p["annee"]})' + (f', {str(p["part_zone_pct"]).replace(".", ",")} % de la zone d\'emploi {esc(S.de_nom(p["zone_emploi"]))}' if p.get("part_zone_pct") is not None else "")
                      + f'. <span class="meta">{esc(e.get("date") or "")}, source : {esc(e["source"])}</span></li>')
    if not lignes: return ""
    return ("<h2>Les annonces qui pèsent le plus localement</h2><p>Emplois annoncés rapportés à l'emploi salarié privé de la commune du site (URSSAF, effectifs au 31 décembre). "
            "Le site peut employer des salariés venus d'autres communes : c'est un ordre de grandeur du choc local, pas une part de la population active.</p><ul>" + "".join(lignes[:15]) + "</ul>")

def groupes_html(evs):
    """Groupes dont plusieurs filiales ou sites sont concernés (plans, fermetures, procédures)."""
    par = {}
    for e in evs:
        g = e.get("groupe")
        if not g: continue
        x = par.setdefault(g["nom"], {"pays": g.get("pays"), "ent": set(), "n": 0, "emplois": 0, "src": set()})
        x["ent"].add(e.get("entreprise")); x["n"] += 1; x["emplois"] += e.get("emplois_min") or 0; x["src"].add(g["source"])
    multi = sorted([(k, v) for k, v in par.items() if len(v["ent"]) >= 2], key=lambda kv: -kv[1]["emplois"])
    if not multi: return ""
    return ("<h2>Groupes dont plusieurs entités sont concernées</h2><p>Rattachement au groupe d'après GLEIF (registre mondial des entités légales), Wikidata "
            "ou une vérification manuelle ; la source est indiquée. Les effectifs additionnent des annonces d'années différentes.</p><ul>"
            + "".join(f"<li><b>{esc(k)}</b>{' (' + esc(v['pays']) + ')' if v.get('pays') else ''} : {', '.join(esc(x) for x in sorted(v['ent']) if x)} "
                      f"— {v['n']} annonces, au moins {fr(v['emplois'])} emplois <span class=meta>[{', '.join(sorted(v['src']))}]</span></li>" for k, v in multi[:20]) + "</ul>")

def p_liste():
    a = F.get("annee") or {}; p = a.get("plans") or {}
    plans = sorted([e for e in F["plans_annee"] if not e.get("sans_entreprise") and not e.get("exclu_totaux") and e.get("entreprise") != e.get("titre")], key=lambda e: e.get("date") or "", reverse=True)
    titre = f"Liste des plans sociaux en France en {AN}"
    desc = (f"{fr(p.get('plans', len(plans)))} plans sociaux, suppressions de postes et fermetures annoncés depuis le 1er janvier {AN}, au moins "
            f"{fr(p.get('min', 0))} emplois : entreprise, lieu, effectif et source, mis à jour chaque jour.")
    b50 = sorted([e for e in EV if e.get("source") == "BODACC" and (e.get("date") or "") >= AN0], key=lambda e: e.get("date") or "", reverse=True)
    g = D["tendance"].get("plus_de_50_salaries") or {}
    corps = (f"<h1>Plans sociaux en France en {AN}</h1>"
             f'<p class="chapo"><b>{fr(p.get("plans", len(plans)))}</b> plans de licenciement, suppressions de postes ou fermetures annoncés depuis le 1er janvier {AN}, '
             f'pour au moins <b>{fr(p.get("min", 0))} emplois</b> (chiffres annoncés, une même entreprise citée plusieurs fois n\'est comptée qu\'une fois).</p>'
             f'<p class="meta">Sources : « liste noire » des plans de licenciement publiée par la CGT (source syndicale) et, depuis octobre {AN}, presse nationale et régionale. '
             f"Ce n'est pas un décompte officiel des plans de sauvegarde de l'emploi. Mis à jour le {date_long(AUJ.isoformat())}.</p>"
             + poids_html(plans) + groupes_html([e for e in EV if e.get("groupe")]) +
             "<h2>Plans annoncés</h2>" + TABLE_EV.format("".join(ligne_ev(e) for e in plans))
             + f"<h2>Entreprises de 50 salariés et plus en procédure collective en {AN}</h2>"
             f"<p>{fr(len(b50))} jugements d'ouverture (liquidation, redressement, sauvegarde) publiés au BODACC concernent des entreprises de 50 salariés et plus"
             + (f" (historique complet depuis le {date_long(g['couverture'][0])})" if g.get("couverture") and g["couverture"][0] <= AN0 else
                " ; l'historique avant octobre est en cours de rattrapage, la liste est donc incomplète pour le début de l'année") + ".</p>"
             + TABLE_EV.format("".join(ligne_ev(e) for e in b50[:400])) + citer(titre, "liste/"))
    graph = [S.site_ld(), S.dataset_ld(D, S.BASE_URL + "/liste/", titre, desc)]
    S.ecrire("liste/index.html", S.page(titre, desc, "liste/", corps, graph, "liste/"))

def stats_dep(code):
    r6 = mois_complets(6); p6 = [an_avant(m) for m in r6]
    n6 = sum(TD.get((m, code), 0) for m in r6); n6p = sum(TD.get((m, code), 0) for m in p6)
    ytd = sum(n for (m, d), n in TD.items() if d == code and m >= f"{AN}-01")
    serie = [(m, TD.get((m, code), 0), TD.get((an_avant(m), code), 0)) for m in mois_complets(18)]
    return {"n6": n6, "n6p": n6p, "var": var(n6, n6p), "ytd": ytd, "serie": serie, "periode": (r6[0], r6[-1])}

def p_departements():
    lignes, urls = [], []
    for code, nom in S.DEPS.items():
        st = stats_dep(code)
        evd = sorted([e for e in EV if e.get("dep") == code and (e.get("date") or "") >= (AUJ - dt.timedelta(days=365)).isoformat()],
                     key=lambda e: e.get("date") or "", reverse=True)
        titre = f"{nom} ({code}) : faillites et plans sociaux en {AN}"
        desc = (f"{fr(st['n6'])} procédures collectives en six mois ({pct(st['var'])} sur un an), {fr(st['ytd'])} depuis janvier, et les plans sociaux "
                f"et fermetures annoncés dans le département {nom}. Mis à jour chaque jour.")
        corps = (f"<h1>{esc(nom)} ({esc(code)}) : faillites et plans sociaux</h1>"
                 f'<p class="chapo">Entre {mois_long(st["periode"][0])} et {mois_long(st["periode"][1])}, <b>{fr(st["n6"])}</b> jugements d\'ouverture de procédure collective '
                 f'(liquidations, redressements, sauvegardes) ont été publiés au BODACC pour des entreprises du département {esc(nom)}, '
                 f'contre {fr(st["n6p"])} un an plus tôt ({pct(st["var"])}). Depuis le 1er janvier {AN} : <b>{fr(st["ytd"])}</b>.</p>')
        if code in S.RUPTURES:
            corps += ('<p class="alerte">Attention : les publications BODACC de ce département s\'effondrent brutalement à partir de fin 2025. '
                      "Cela ressemble à un changement dans la source (régime local d'Alsace-Moselle), pas à une baisse réelle : ces chiffres ne sont pas comparables d'une année sur l'autre.</p>")
        corps += f'<p class="meta"><a href="rss.xml">Être alerté pour ce département (flux RSS)</a> · <a href="{S.BASE}/alertes/">toutes les alertes</a></p>'
        corps += barres(st["serie"], f"Jugements d'ouverture publiés au BODACC par mois, {nom}")
        corps += '<p class="meta">Toutes tailles d\'entreprise, par mois de publication. Trait jaune : même mois un an plus tôt.</p>'
        corps += f"<h2>Entreprises de 50 salariés et plus, plans sociaux et fermetures (12 derniers mois)</h2>"
        corps += (TABLE_EV.format("".join(ligne_ev(e, False) for e in evd)) if evd else
                  "<p>Aucun événement recensé dans ce département sur les douze derniers mois (procédure d'une entreprise de 50 salariés et plus, plan de licenciement ou fermeture annoncés).</p>")
        corps += (f'<p class="meta">Les procédures sont rattachées au département du siège de l\'entreprise ; les plans sociaux au site concerné quand la source le précise. '
                  f'<a href="{S.BASE}/departements/">Tous les départements</a> · <a href="{S.BASE}/faillites-entreprises/">Les chiffres nationaux</a>.</p>')
        url = S.dep_url(code, True)
        graph = [S.site_ld(), {"@type": "WebPage", "name": titre, "url": url, "inLanguage": "fr-FR", "dateModified": AUJ.isoformat(),
                               "isPartOf": {"@id": S.BASE_URL + "/#site"}, "about": {"@type": "AdministrativeArea", "name": nom}}]
        chemin = url[len(S.BASE_URL) + 1:]
        S.ecrire(chemin + "index.html", S.page(titre, desc, chemin, corps, graph, "departements/"))
        urls.append(url)
        lignes.append(f'<tr><td><a href="{S.dep_url(code)}">{esc(nom)}</a></td><td>{esc(code)}</td><td class="n">{fr(st["n6"])}</td>'
                      f'<td class="n">{"n.c." if code in S.RUPTURES else pct(st["var"])}</td><td class="n">{fr(st["ytd"])}</td><td class="n">{len(evd)}</td></tr>')
    titre = f"Faillites et plans sociaux par département en {AN}"
    desc = "Procédures collectives publiées au BODACC, évolution sur un an et plans sociaux annoncés, pour chacun des 101 départements français. Mis à jour chaque jour."
    corps = (f"<h1>Faillites et plans sociaux par département</h1><p class=\"chapo\">Pour chaque département : jugements d'ouverture de procédure collective publiés au BODACC "
             f"sur les six derniers mois complets, évolution sur un an, total depuis le 1er janvier {AN} et nombre d'événements recensés (entreprises de 50 salariés et plus, plans sociaux, fermetures).</p>"
             '<div class="tablo"><table><thead><tr><th>Département</th><th>Code</th><th class="n">6 derniers mois</th><th class="n">Sur un an</th>'
             f'<th class="n">Depuis janvier</th><th class="n">Événements (12 mois)</th></tr></thead><tbody>{"".join(lignes)}</tbody></table></div>'
             '<p class="meta">n.c. : non comparable (rupture de série dans la source, voir la page Méthode).</p>' + citer(titre, "departements/"))
    S.ecrire("departements/index.html", S.page(titre, desc, "departements/", corps, [S.site_ld()], "departements/"))
    return urls

CORRECTIONS_INITIALES = [
    ["2026-10-08", "Marchés publics : le jeu de données utilisé (DECP « marchés valides ») s'arrêtait au 8 février 2024. Ajout du DECP consolidé de data.gouv.fr, jusqu'en octobre 2026."],
    ["2026-10-08", "Accords-cadres retirés des montants de marchés publics : ce sont des plafonds pluriannuels, souvent partagés entre plusieurs entreprises. Exemple : Orange passe de 11,5 Md€ à 104 M€ de marchés fermes."],
    ["2026-10-08", "Comptes : un exercice postérieur à l'annonce d'un plan n'est plus utilisé pour dire que l'entreprise était bénéficiaire au moment de l'annonce."],
    ["2026-10-08", "« Bénéficiaire trois années de suite » remplacé par « dernier exercice bénéficiaire » : la source ne fournit qu'un exercice par entreprise."],
    ["2026-10-08", "Compteur d'emplois scindé : emplois dont la suppression est annoncée (presse, CGT, dédoublonnés par entreprise) d'un côté, salariés des entreprises entrées en procédure (BODACC) de l'autre, qui ne sont pas des licenciements."],
    ["2026-10-08", "Tendance : le chiffre de référence devient la série officielle de la Banque de France. Le décompte BODACC (irrégulier, affecté par une rupture en Alsace-Moselle) passe au rang de signal avancé. Il indiquait −1 % sur 12 mois quand la Banque de France mesure +4,6 %."],
]

def rapprochements_html():
    try: r = json.load(open(os.path.join(S.H, "rapprochements.json"), encoding="utf-8"))
    except Exception: return ""
    li = [f"<li><b>{esc(x['cite'])}</b> n'est pas rattaché au SIREN {esc(x['siren'])} : {esc(x['motif'])}.</li>" for x in r.get("refus", [])]
    li += [f"<li>Le lien de groupe de <b>{esc(x['nom'])}</b> (SIREN {esc(x['siren'])}) n'est pas repris : {esc(x['motif'])}.</li>" for x in r.get("groupes_refus", [])]
    li += [f"<li>Événement retiré ({esc(x['id'][:40])}…) : {esc(x['motif'])}.</li>" for x in r.get("exclure", [])]
    return ("<h2>Rapprochements corrigés à la main</h2><p>Après audit, ces rapprochements automatiques ont été refusés ou ces articles retirés. "
            "Les sigles de quatre lettres ou moins (ACC, SMP…) ne sont rattachés qu'à une entreprise au nom identique, jamais au seul niveau national.</p><ul>" + "".join(li) + "</ul>") if li else ""

def p_methode():
    fc = os.path.join(S.H, "corrections.json")
    if not os.path.exists(fc): json.dump(CORRECTIONS_INITIALES, open(fc, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    corr = sorted(json.load(open(fc, encoding="utf-8")), key=lambda x: x[0], reverse=True)
    cp = F.get("comparaison")
    titre = "Méthode, sources et corrections"
    desc = "Comment le site compte les faillites et les plans sociaux : sources publiques, recoupements et leur fiabilité, écarts connus avec les chiffres officiels, journal des corrections."
    src = [("BODACC (DILA)", "Jugements d'ouverture de liquidation, de redressement et de sauvegarde ; suites des procédures", "Compteur toutes les 15 min, liste 2 fois par jour", "Officiel. Compté à la date de publication."),
           ("Banque de France, via l'INSEE", "Défaillances d'entreprises (date de jugement), cumul sur 12 mois, par secteur", "Mensuel, environ 2 mois de recul", "Chiffre de référence."),
           ("INSEE", "Créations d'entreprises mensuelles", "Mensuel", "Officiel."),
           ("API Recherche d'entreprises", "Tranche d'effectif, siège, chiffre d'affaires et résultat net (un exercice)", "Cache de 30 jours", "Tranche d'effectif parfois ancienne de 1 à 2 ans."),
           ("URSSAF", "Emploi salarié privé par commune et par zone d'emploi (2025)", "Annuel", "Officiel."),
           ("DECP", "Marchés publics : data.economie.gouv.fr jusqu'en février 2024, puis DECP consolidé de data.gouv.fr", "Quotidien", "Déclaratif : erreurs de saisie possibles."),
           ("ADEME", "Aides financières, datées, par SIRET", "Hebdomadaire", "Officiel."),
           ("France Relance", "Lauréats des projets industriels (sans montant par entreprise)", "Hebdomadaire", "Officiel."),
           ("Registre européen des aides d’État (TAM)", "Aides individuelles de plus de 100 000 € déclarées à la Commission européenne depuis 2016, rapprochées par SIREN ou SIRET ; les aides de l’ADEME sont écartées pour ne pas les compter deux fois", "Mensuel", "Officiel, déclaré par les autorités qui octroient l’aide. Les aides fiscales sont publiées par tranche de montant : on affiche le bas et le haut de la fourchette."),
           ("Registre des aides de minimis", "Aides octroyées depuis 2026", "Hebdomadaire", "Officiel, couverture récente."),
           ("Dares", "Inscriptions à France Travail après un licenciement économique, PSE engagés et validés", "Hebdomadaire (publication trimestrielle)", "Officiel."),
           ("BODACC, ventes et cessions", "Achats et ventes de fonds de commerce ou de branches d’activité, apports et fusions de chaque entreprise suivie, avec la contrepartie et le montant quand l’annonce l’indique. Les cessions d’actions (rachat d’une société par un fonds) ne sont pas publiées au BODACC", "Mensuel", "Officiel. Montant extrait automatiquement du texte : à vérifier sur l’annonce."),
           ("Accords d’entreprise (DILA, Légifrance)", "Accords déposés par les entreprises, avec leur SIRET : accords de méthode et accords de PSE, ruptures conventionnelles collectives, plans de départs volontaires, accords de performance collective, activité partielle de longue durée. Classement d’après le titre de l’accord (les thèmes déclarés sont peu fiables) ; le nombre de postes n’est pas extrait", "Hebdomadaire", "Officiel, rattachement sûr. Une entreprise peut demander à occulter certains passages ; tous les accords ne sont pas publiés."),
           ("HATVP", "Lobbying déclaré : tranche de dépenses, actions, par entreprise ou groupe", "Hebdomadaire", "Déclaratif, officiel."),
           ("DGCCRF", "Amendes pour retards de paiement aux fournisseurs (décisions publiées, avec SIRET)", "Relevé manuel", "Officiel ; publication limitée à un an."),
           ("GLEIF, Wikidata", "Groupe d'appartenance (société mère)", "Mensuel", "GLEIF : déclaré par l'entité ; Wikidata : collaboratif, sommet unique seulement."),
           ("France Travail (La Bonne Boîte)", "Établissements jugés à fort potentiel d'embauche", "Hebdomadaire", "Estimation algorithmique, pas des offres publiées."),
           ("Banque mondiale, BCE, INSEE", "Contexte : Brent, taux des crédits, climat des affaires, production, prix de l'électricité", "Quotidien", "Officiel ; mis en regard, pas une explication."),
           ("Liste CGT des plans de licenciement", "Plans annoncés, effectifs annoncés", "À chaque mise à jour du document", "Source syndicale. Dates au mois près."),
           ("Presse (environ 200 flux)", "Annonces de suppressions de postes, fermetures, procédures", "2 fois par jour", "Extraction automatique (titre et chapô) : à vérifier dans l'article.")]
    liens = [("SIREN fourni par la source (BODACC)", "Sûr"),
             ("Nom correspondant et établissement actif de l'entreprise dans la commune de l'annonce (SIRET)", "Sûr"),
             ("Nom exact et établissement dans le département de l'événement", "Probable : vérifier la filiale concernée"),
             ("Nom exact seulement", "Indicatif : peut désigner la maison mère ou un homonyme ; exclu des synthèses"),
             ("Commune du site et effectif annoncé → emploi local (URSSAF)", "Calculé seulement si la commune est connue ; jamais pour le siège d'une entreprise en procédure"),
             ("Marchés publics → part du chiffre d'affaires", "Plancher : marchés fermes à titulaire unique, hors accords-cadres et co-traitance, étalés sur leur durée"),
             ("Aide → annonce (24 mois)", "Rapprochement chronologique au mois près, pas un lien de cause à effet")]
    corps = (f"<h1>Méthode, sources et corrections</h1>"
             "<p class=\"chapo\">Le site agrège chaque jour des sources publiques pour suivre trois choses : les défaillances d'entreprises (chiffre officiel et décompte quotidien), "
             "les procédures collectives des entreprises de 50 salariés et plus, et les plans de licenciement ou fermetures annoncés. Chaque chiffre renvoie à sa source.</p>"
             "<h2>Les sources</h2><div class=\"tablo\"><table><thead><tr><th>Source</th><th>Ce que le site en tire</th><th>Fréquence</th><th>Fiabilité</th></tr></thead><tbody>"
             + "".join(f"<tr><td>{esc(a)}</td><td>{esc(b)}</td><td>{esc(c)}</td><td>{esc(d)}</td></tr>" for a, b, c, d in src) + "</tbody></table></div>"
             "<h2>Comment les sources sont reliées</h2><div class=\"tablo\"><table><thead><tr><th>Rapprochement</th><th>Fiabilité</th></tr></thead><tbody>"
             + "".join(f"<tr><td>{esc(a)}</td><td>{esc(b)}</td></tr>" for a, b in liens) + "</tbody></table></div>"
             "<h2>Les indicateurs</h2><ul>"
             "<li><b>Procédures collectives depuis le 1er janvier</b> : décompte exact des jugements d'ouverture publiés au BODACC, toutes tailles d'entreprise, sauvegardes comprises. "
             "Entre deux relevés, le compteur de la page d'accueil avance au rythme moyen des huit dernières semaines : cette partie est une estimation, signalée comme telle.</li>"
             "<li><b>Emplois dont la suppression est annoncée</b> : somme des effectifs annoncés (liste CGT, presse), une entreprise citée plusieurs fois à moins de 60 jours d'écart n'étant comptée qu'une fois. "
             "Borne basse : un effectif inconnu compte pour zéro.</li>"
             "<li><b>Salariés des entreprises entrées en procédure</b> : bas de la tranche d'effectif INSEE des entreprises de 50 salariés et plus. Ce ne sont pas des licenciements : "
             "une entreprise en redressement peut garder ses salariés, une liquidation les perd en général tous.</li>"
             "<li><b>Tendance</b> : la référence est le cumul sur douze mois de la Banque de France. Le décompte BODACC sert de signal avancé, hors Alsace-Moselle.</li>"
             "<li><b>Suites des procédures</b> : pour les entreprises de 50 salariés et plus en redressement ou en sauvegarde, dernière décision publiée (liquidation, cession, plan). "
             "« Aucune décision publiée » ne veut pas dire que l'entreprise a survécu : le BODACC publie avec retard.</li></ul>"
             "<h2>Écarts connus et limites</h2><ul>"
             + (f"<li><b>BODACC et Banque de France</b> : sur {mois_long(cp['periode'][0])} à {mois_long(cp['periode'][1])}, {fr(cp['bodacc_site'])} jugements d'ouverture au BODACC contre "
                f"{fr(cp['banque_de_france'])} défaillances selon la Banque de France ({pct(cp['ecart_pct'])}). {esc(cp['explication'])}</li>" if cp else "")
             + "<li><b>Alsace-Moselle</b> : les publications BODACC de la Moselle, du Bas-Rhin et du Haut-Rhin chutent de 60 à 95 % à partir de fin 2025, ce qui ressemble à un changement dans la source. "
             "Ces départements sont exclus des comparaisons.</li>"
             "<li><b>Effectifs</b> : tranches INSEE (par exemple 50 à 99 salariés), parfois anciennes ; ce sont des ordres de grandeur.</li>"
             "<li><b>Comptes</b> : un seul exercice disponible par entreprise ; il n'est utilisé que s'il est antérieur ou égal à l'année de l'annonce.</li>"
             "<li><b>Presse</b> : l'entreprise, la commune et l'effectif sont extraits automatiquement du titre et du chapô ; l'article d'origine fait foi.</li>"
             "<li><b>Non couvert</b> : crédit d'impôt recherche, exonérations de cotisations, aides de Bpifrance et de France 2030, aides d'État de moins de 100 000 €, "
             "dividendes, installations classées (Géorisques n'est pas joignable depuis le serveur du site).</li></ul>"
             + rapprochements_html() +
             "<h2>Journal des corrections</h2><p>Les erreurs signalées ou trouvées sont corrigées et listées ici, avec leur date. Pour en signaler une : "
             f'<a href="mailto:{S.CONTACT}">{S.CONTACT}</a>.</p><ul>' + "".join(f"<li><b>{esc(d)}</b> : {esc(t)}</li>" for d, t in corr) + "</ul>"
             f"<h2>Qui édite ce site</h2><p>{S.EDITEUR}, développeur indépendant à Perros-Guirec. Projet sans financement ni publicité. "
             '<a href="https://oraclemarin.fr/apropos/">À propos</a>. Le code de collecte et les données sont décrits sur la page '
             f'<a href="{S.BASE}/donnees/">Données ouvertes</a>.</p>' + citer(titre, "methode/"))
    graph = [S.site_ld(), {"@type": "WebPage", "name": titre, "url": S.BASE_URL + "/methode/", "inLanguage": "fr-FR", "dateModified": max(c[0] for c in corr),
                           "isPartOf": {"@id": S.BASE_URL + "/#site"}}]
    S.ecrire("methode/index.html", S.page(titre, desc, "methode/", corps, graph, "methode/"))

def completude_html():
    """Taux de remplissage des champs clés, séparément pour les annonces (liste CGT, presse, accords) et pour les procédures collectives du BODACC."""
    import cgt_stats
    A = [e for e in EV if e.get("source") != "BODACC"]; B = [e for e in EV if e.get("source") == "BODACC"]
    CG = [e for e in A if str(e.get("source", "")).startswith("CGT")]
    pc = lambda n, d: f"{round(100 * n / d)} %" if d else "—"
    def ligne(nom, fa, fb=None, note="", pop=None):
        a = [e for e in (pop if pop is not None else A)]
        na = sum(1 for e in a if fa(e))
        cb = (f"{pc(sum(1 for e in B if fb(e)), len(B))}" if fb else "—")
        return f"<tr><td>{nom}</td><td class=\"n\">{pc(na, len(a))}</td><td class=\"n\">{cb}</td><td>{note}</td></tr>"
    eff = lambda e: tuple(e.get("effectif_entreprise") or (None, None))[0] is not None
    sur = lambda e: e.get("lien") in ("siren_source", "siret_commune") or e.get("valide_humain") or e.get("verif_ident") == "confirmé"
    R = [ligne("SIREN identifié", lambda e: bool(e.get("siren")), lambda e: bool(e.get("siren")), "Sans SIREN, une annonce n’a pas de fiche entreprise."),
         ligne("Rapprochement sûr ou confirmé (parmi les annonces avec SIREN)", sur, None, "Les autres sont « probables » ou « indicatifs ».", [e for e in A if e.get("siren")]),
         ligne("Date", lambda e: bool(e.get("date")), lambda e: bool(e.get("date"))),
         ligne("Département", lambda e: bool(e.get("dep")), lambda e: bool(e.get("dep"))),
         ligne("Commune précise", lambda e: bool(e.get("commune")) and not e.get("approx"), lambda e: bool(e.get("commune"))),
         ligne("Nombre d’emplois annoncé", lambda e: e.get("emplois_precision") == "annoncé" and e.get("emplois_min") is not None, None, "Plusieurs sources donnent « emplois menacés » ou aucun chiffre."),
         ligne("Taille de l’entreprise (tranche d’effectif)", eff, lambda e: bool(e.get("emplois_min")), "Répertoire Sirene ; seules les unités de 10 salariés et plus y figurent."),
         ligne("Dernier résultat net publié", lambda e: bool((e.get("comptes") or {}).get("resultat_net") is not None and e.get("fiable")), lambda e: bool((e.get("comptes") or {}).get("resultat_net") is not None and e.get("fiable")), "Comptes déposés, avec l’année."),
         ligne("Lieu vérifié (établissement dans la commune ou le département)", lambda e: (e.get("verif_site") or {}).get("niveau") in ("commune", "departement"), None, "Parmi les annonces avec SIREN.", [e for e in A if e.get("siren")]),
         ligne("Au moins une source indépendante de la CGT (lignes de la liste CGT)", cgt_stats.recoupe, None, "Presse, BODACC, fermeture au répertoire Sirene ou comptes.", CG)]
    return ("<h2 id=\"completude\">Complétude des données</h2><p>Part des lignes dont le champ est renseigné, au moment de la génération du fichier ("
            f"{fr(len(A))} annonces, {fr(len(B))} procédures collectives du BODACC). <b>Une case vide veut dire « inconnu »</b>, pas « non ». Un tiret : champ sans objet pour ce type de ligne.</p>"
            "<div class=\"tablo\"><table><thead><tr><th>Champ</th><th class=\"n\">Annonces</th><th class=\"n\">Procédures BODACC</th><th>Remarque</th></tr></thead><tbody>" + "".join(R) + "</tbody></table></div>")

CHAMPS = ["id", "evenement_id", "date", "date_publication", "type", "source", "entreprise", "siren", "fiabilite_rapprochement", "commune", "departement",
          "postes_annonces", "effectif_entreprise_min", "effectif_entreprise_max", "exclu_des_totaux", "url_source", "resultat_net", "annee_comptes", "chiffre_affaires",
          "part_commande_publique_pct", "part_emploi_commune_pct", "suite_procedure", "resultat_net_dernier_exercice", "annee_dernier_exercice",
          "procedure_bodacc_liee", "operation_bodacc_recente", "date_operation_bodacc", "delai_operation_mois", "a_creuser_reprise", "lieu_verifie", "empreinte", "credit"]
def p_donnees():
    buf = io.StringIO(); w = csv.writer(buf)
    w.writerow(CHAMPS)
    lien = {"siren_source": "sur", "siret_commune": "sur", "nom+dep": "probable", "nom_seul": "indicatif"}
    for e in EV:
        c = e.get("comptes") or {}
        ann = e.get("emplois_precision") == "annoncé"
        eff = (e.get("emplois_min"), e.get("emplois_max")) if e.get("source") == "BODACC" else tuple(e.get("effectif_entreprise") or (None, None))
        w.writerow([e.get("id"), e.get("evenement_id"), e.get("date"), e.get("date_publication"), e.get("type"), e.get("source"), e.get("entreprise"), e.get("siren"),
                    lien.get(e.get("lien"), ""), e.get("commune"), e.get("dep"), e.get("emplois_min") if ann else "", eff[0], eff[1], "oui" if e.get("exclu_totaux") else "",
                    e.get("url"), c.get("resultat_net") if e.get("fiable") else "", c.get("derniere_annee") if e.get("fiable") else "",
                    c.get("ca") if e.get("fiable") else "", (e.get("dependance_publique") or {}).get("part_pct", ""),
                    (e.get("poids_local") or {}).get("part_commune_pct", ""), (e.get("suite") or {}).get("issue", ""),
                    c.get("resultat_net", "") if c and e.get("lien") != "nom_seul" else "", c.get("derniere_annee", "") if c and e.get("lien") != "nom_seul" else "",
                    (lambda pb: f"{pb['type']} jugé le {pb['date']}, publié le {pb['date_publication']}" if pb else "")(e.get("procedure_bodacc")),
                    (lambda r: f"{r['role']} ({r['nature']}) : {r.get('contrepartie') or '?'}" if r else "")(e.get("reprise_recente")),
                    (e.get("reprise_recente") or {}).get("date", ""), (e.get("reprise_recente") or {}).get("delai_mois", ""),
                    "oui" if (e.get("reprise_recente") or {}).get("a_creuser") else "",
                    ((e.get("verif_site") or {}).get("niveau") if (e.get("verif_site") or {}).get("niveau") in ("commune", "departement", "aucun") else ""),
                    S.empreinte(e.get("id")), S.CREDIT])
    # lignes de contrôle (voir « Licence et réutilisation ») : fictives, exclues des totaux, empreinte comme les autres lignes
    try:
        rows = list(csv.reader(io.StringIO(buf.getvalue()))); entete, corps_ = rows[0], rows[1:]
        for t in json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".pieges.json"), encoding="utf-8")):
            ligne = [""] * len(entete)
            val = {"id": t["id"], "evenement_id": t["id"], "date": t["date"], "date_publication": t["date"], "type": t["type"], "source": "presse", "entreprise": t["entreprise"],
                   "commune": t["commune"], "departement": t["dep"], "postes_annonces": t["emplois"], "exclu_des_totaux": "oui",
                   "url_source": S.BASE + "/donnees/#controle", "empreinte": S.empreinte(t["id"]), "credit": S.CREDIT}
            for k, v in val.items(): ligne[entete.index(k)] = v
            corps_.insert(int(t["pos"] * len(corps_)), ligne)
        b2 = io.StringIO(); w2 = csv.writer(b2); w2.writerow(entete); w2.writerows(corps_); buf = b2
    except Exception as ex:
        print("lignes de contrôle :", ex, file=__import__("sys").stderr)
    _csv = chr(0xfeff) + buf.getvalue()
    S.ecrire("evenements.csv", _csv)
    import hashlib
    EMPREINTE_FICHIER = hashlib.sha256(_csv.encode("utf-8")).hexdigest()
    titre = "Données ouvertes : plans sociaux et faillites"
    desc = "Téléchargez les données du site en CSV et JSON : événements (procédures, plans sociaux, fermetures), tendance BODACC, séries officielles, compteurs. Mises à jour chaque jour."
    fich = [("evenements.csv", "Un événement par ligne : procédure collective (entreprise de 50 salariés et plus), plan de licenciement ou fermeture annoncés, avec rapprochements.", "CSV, UTF-8, séparateur virgule"),
            ("data.json", "Les mêmes événements avec tous les champs (argent public, comptes, proximité des aides, poids local), et la synthèse.", "JSON"),
            ("tendance.json", "Jugements d'ouverture BODACC par mois et par département, entreprises de 50 salariés et plus, suites des procédures.", "JSON"),
            ("officiel.json", "Séries officielles : défaillances (Banque de France) et créations d'entreprises (INSEE), comparaison avec le BODACC.", "JSON"),
            ("compteur.json", "Compteurs depuis le 1er janvier et sur les 30 derniers jours.", "JSON, toutes les 15 minutes"),
            ("societes_liees.csv", "Sociétés liées aux sociétés suivies, avec la preuve de chaque lien : dirigeant personne morale commun, adresse de siège commune, cession de fonds publiée au BODACC. Les commissaires aux comptes et mandataires judiciaires sont exclus. Un lien n'est pas un constat d'appartenance à un groupe ; la force (fort, probable, indice) dit le poids de la preuve.", "CSV, UTF-8"),
            ("restructurations.csv", "Fermetures d'établissements qui sont des mouvements juridiques et non des pertes d'emplois immédiates : sites transférés à une société du groupe (vérifiés à la main), sociétés absorbées ou fusionnées (BODACC). Alerte si la société qui a reçu le site entre ensuite en procédure collective. Hors des totaux d'emplois.", "CSV, UTF-8")]
    corps = ("<h1>Données ouvertes</h1><p class=\"chapo\">Toutes les données affichées sur le site sont téléchargeables, réutilisables par la presse, la recherche, les syndicats et les associations, et mises à jour chaque jour.</p>"
             "<div class=\"tablo\"><table><thead><tr><th>Fichier</th><th>Contenu</th><th>Format</th></tr></thead><tbody>"
             + "".join(f'<tr><td><a href="{S.BASE}/{f}">{f}</a></td><td>{esc(c)}</td><td>{esc(t)}</td></tr>' for f, c, t in fich) + "</tbody></table></div>"
             f"<h2>Source et signature</h2><p>Merci de citer : « {esc(S.CREDIT)} ». {esc(S.LICENCE)}. "
             "Chaque ligne porte une <b>empreinte</b> (colonne empreinte), calculée à partir de son identifiant avec une clé que seul l'éditeur connaît : "
             "elle permet de retrouver l'origine d'une ligne republiée ailleurs, sans modifier les données. "
             f"Empreinte SHA-256 du fichier evenements.csv du jour : <code>{EMPREINTE_FICHIER}</code>.</p>"
             "<h2>Avant de compter : les règles</h2><ul>"
             "<li><b>Une ligne n'est pas toujours un événement distinct.</b> Les mentions d'une même entreprise à moins de 180 jours d'écart partagent le même <b>evenement_id</b> : comptez les evenement_id distincts, pas les lignes.</li>"
             "<li><b>Ne mélangez pas effectif et postes.</b> <b>postes_annonces</b> est un nombre de postes supprimés annoncé par la source (liste CGT, presse) ; <b>effectif_entreprise_min / max</b> est la taille de toute l'entreprise (tranche INSEE), ce ne sont pas des suppressions.</li>"
             "<li><b>Une case vide veut dire « inconnu »</b>, pas « non ».</li>"
             "<li><b>Les sources ne couvrent pas les mêmes périodes</b> (tableau ci-dessous) : une courbe mensuelle tirée du fichier montre l'arrivée des sources autant que la conjoncture. Pour une tendance, utilisez les séries officielles (Banque de France) ou tendance.json.</li>"
             "<li><b>Fiabilité</b> : ne publiez que les lignes au rattachement <i>sûr</i> ou, après vérification, <i>probable</i>. La liste CGT est une source syndicale (« liste noire ») : citez-la comme telle. Les lignes <b>exclu_des_totaux</b> (pas d'entreprise précise, chiffre invérifiable) ne sont pas comptées sur le site.</li></ul>"
             "<h2>Période couverte par source</h2><div class=\"tablo\"><table><thead><tr><th>Source</th><th>Période</th><th>Remarque</th></tr></thead><tbody>"
             "<tr><td>BODACC (procédures collectives, entreprises de 50 salariés et plus)</td><td>Depuis janvier 2025</td><td>Date du jugement et date de publication</td></tr>"
             "<tr><td>Liste CGT (« liste noire »)</td><td>Août 2023 à mars 2026 (dernière édition publiée par la CGT)</td><td>Dates au mois près (le 15 du mois) ; 12 lignes sans date</td></tr>"
             "<tr><td>Accords d'entreprise (Légifrance)</td><td>Accords signés depuis janvier 2024 (historique complet de la base Légifrance)</td><td>Pas de nombre de postes</td></tr>"
             "<tr><td>Presse</td><td>Depuis janvier 2025 (rattrapé par recherche d'actualités semaine par semaine jusqu'à septembre 2026, puis en continu)</td><td>Titres et liens ; articles hors de France ou sans suppression collective retirés ; couverture moins complète pour les petits titres régionaux</td></tr></tbody></table></div>"
             + completude_html() + "<h2>Champs</h2><ul>"
             "<li><b>evenement_id</b> : identifiant commun aux lignes d'un même événement (même SIREN, moins de 180 jours d'écart).</li>"
             "<li><b>fiabilite_rapprochement</b> : <i>sur</i> (SIREN fourni par la source, ou établissement de l'entreprise trouvé dans la commune), <i>probable</i> (nom exact et établissement dans le département), <i>indicatif</i> (nom seul).</li>"
             "<li><b>commune</b> : celle de la source, ou de l'établissement de l'entreprise trouvé dans le registre ; vide quand seul le département est connu.</li>"
             "<li><b>resultat_net_dernier_exercice, annee_dernier_exercice</b> : dernier exercice publié, pour information, même postérieur à l'annonce (resultat_net, lui, ne retient que des comptes antérieurs ou de l'année de l'annonce).</li>"
             "<li><b>procedure_bodacc_liee</b> : procédure collective de la même entreprise au BODACC, la plus proche de l'annonce.</li>"
             "<li><b>postes_annonces</b> ; <b>effectif_entreprise_min / max</b> : voir ci-dessus.</li>"
             "<li><b>resultat_net, annee_comptes, chiffre_affaires</b> : renseignés seulement quand le rapprochement est sûr ou probable et l'exercice antérieur ou égal à l'année de l'annonce (un seul exercice disponible).</li>"
             "<li><b>part_commande_publique_pct</b> : estimation par défaut de la part du chiffre d'affaires venant de marchés publics.</li>"
             "<li><b>part_emploi_commune_pct</b> : postes annoncés rapportés à l'emploi salarié privé de la commune du site (URSSAF).</li>"
             "<li><b>suite_procedure</b> : liquidation, cession, plan, ou « en cours » (aucune décision publiée).</li><li><b>operation_bodacc_recente</b>, <b>date_operation_bodacc</b>, <b>delai_operation_mois</b> : dernière vente de fonds de commerce, cession de branche d'activité ou fusion publiée au BODACC visant la société dans les 60 mois précédant l'annonce, avec le délai en mois. Les cessions de titres (rachats d'actions) ne sont pas publiées au BODACC et n'y figurent pas. Aucun lien de cause n'est posé.</li><li><b>a_creuser_reprise</b> : « oui » si le nom de la contrepartie est cité dans l'annonce, ou si cette opération, rare pour la société (trois ou moins en 60 mois), a eu lieu moins de 12 mois avant l'annonce. C'est un signal à vérifier, pas une conclusion.</li><li><b>lieu_verifie</b> : « commune » si la société rattachée a un établissement (principal ou secondaire, ouvert ou fermé, au répertoire Sirene) dans la commune citée par l'annonce, « departement » s'il y en a un dans le département seulement, « aucun » si elle n'en a aucun dans le département cité (rattachement à vérifier : siège ou holding, erreur de lieu dans la source, ou mauvaise société), vide si le lieu ne peut pas être vérifié.</li></ul>"
             "<p>L'export de l'<a href=\"" + S.BASE + "/explorer/\">explorateur</a> suit les mêmes règles, avec en plus les recoupements (groupe, lobbying, aides, accords, mobilisations).</p>"
             "<h2>Licence et réutilisation</h2><p>Les données compilées par ce site (rapprochements avec les entreprises, vérifications, recoupements, classement) sont publiées sous licence "
             "<a href=\"https://creativecommons.org/licenses/by-nc-sa/4.0/deed.fr\" rel=\"license noopener\">CC BY-NC-SA 4.0</a> : mention de la source, pas d'usage commercial, partage dans les mêmes conditions. "
             "La presse, la recherche, les syndicats et les associations peuvent les réutiliser librement, y compris dans un article ou une infographie. Pour un usage commercial (revente, "
             "intégration à un produit payant), écrire à " + S.CONTACT + ". L'extraction systématique ou la reprise d'une partie substantielle de la base à des fins commerciales est interdite "
             "(droit des producteurs de bases de données). <span id=\"controle\">Les fichiers téléchargeables contiennent quelques lignes de contrôle, exclues des totaux "
             "(<code>exclu_des_totaux</code> = oui), qui ne correspondent à aucun événement réel et servent à détecter les copies.</span></p>"
             "<p>Les données issues de sources publiques (BODACC, INSEE, Banque de France, URSSAF, DECP, ADEME, API Recherche d'entreprises) "
             "sont réutilisables selon la Licence Ouverte d'Etalab, en citant la source d'origine et ce site. La liste de la CGT reste la propriété de la CGT : le site en reprend les lignes en quelques mots (entreprise, lieu, effectif annoncé), les rattache à la page du PDF d'origine et renvoie vers l'original sur cgt.fr. Les articles de presse restent la propriété de leurs auteurs : "
             "le site n'en reprend que le titre, la date, l'effectif annoncé et le lien.</p>" + citer(titre, "donnees/"))
    S.ecrire("donnees/index.html", S.page(titre, desc, "donnees/", corps, [S.site_ld(), S.dataset_ld(D)], "donnees/"))

def p_rss():
    items = sorted([e for e in EV if e.get("date") and e["date"] <= AUJ.isoformat()], key=lambda e: (e["date"], e.get("id", "")), reverse=True)[:60]
    def it(e):
        when = dt.datetime.fromisoformat(e["date"] + "T12:00:00+00:00")
        emp = (f", {fr(e['emplois_min'])} emplois annoncés" if e.get("emplois_precision") == "annoncé" and e.get("emplois_min")
               else f", {fr(e['emplois_min'])} salariés ou plus" if e.get("emplois_min") else "")
        t = f"{e['type'].capitalize()} : {e.get('entreprise') or ''}" + (f" ({e['commune']})" if e.get("commune") else "") + emp
        return (f"<item><title>{esc(t)}</title><link>{esc(e.get('url') or S.BASE_URL + '/')}</link><guid isPermaLink=\"false\">{esc(e.get('id'))}</guid>"
                f"<pubDate>{format_datetime(when)}</pubDate><description>{esc((e.get('detail') or '') + ' Source : ' + e['source'] + '.')}</description></item>")
    S.ecrire("rss.xml", '<?xml version="1.0" encoding="UTF-8"?><rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom"><channel>'
             f"<title>{esc(S.NOM)}</title><link>{S.BASE_URL}/</link><atom:link href=\"{S.BASE_URL}/rss.xml\" rel=\"self\" type=\"application/rss+xml\"/>"
             "<description>Procédures collectives des entreprises de 50 salariés et plus, plans de licenciement et fermetures annoncés en France.</description>"
             f"<language>fr-fr</language><lastBuildDate>{format_datetime(dt.datetime.now(dt.timezone.utc))}</lastBuildDate>{''.join(it(e) for e in items)}</channel></rss>")

def p_llms():
    b, a, cr = F.get("bdf"), F.get("annee"), F.get("creations")
    chiffres = []
    if b: chiffres.append(f"- Défaillances d'entreprises (Banque de France, cumul sur 12 mois à fin {mois_long(b['mois'])}) : {fr(b['n'])}, {pct(b['var'])} sur un an.")
    if a:
        chiffres.append(f"- Jugements d'ouverture de procédure collective publiés au BODACC depuis le 1er janvier {AN} : {fr(a['procedures'])} (sauvegardes comprises, décompte du site).")
        p = a.get("plans") or {}
        if p: chiffres.append(f"- Plans sociaux, suppressions de postes ou fermetures annoncés depuis le 1er janvier {AN} : {fr(p['plans'])}, au moins {fr(p['min'])} emplois (liste CGT et presse, dédoublonné ; pas un décompte officiel).")
    dr = F.get("dares")
    if dr: chiffres.append(f"- Inscriptions à France Travail après un licenciement économique (Dares, {dr['t']}) : {fr(dr['inscriptions'])}, {pct(dr['var_an'])} sur un an ; {dr['pse']} PSE validés ou homologués, {fr(dr['ruptures'])} ruptures prévues.")
    if cr: chiffres.append(f"- Créations d'entreprises (INSEE, 12 mois à fin {mois_long(cr['dernier_mois'])}) : {fr(cr['cumul_12_mois'])}, dont {str(cr['dont_micro_pct']).replace('.', ',')} % de micro-entrepreneurs.")
    txt = f"""# {S.NOM}

> Suivi quotidien et sourcé des faillites d'entreprises (défaillances, procédures collectives publiées au BODACC), des entreprises de 50 salariés et plus en liquidation, redressement ou sauvegarde, et des plans sociaux et fermetures annoncés en France. Recoupé avec les séries officielles (Banque de France, INSEE), l'emploi local (URSSAF), les comptes, les marchés publics et les aides. Gratuit, sans compte.

Langue : français. Périmètre : France (métropole et outre-mer). Mise à jour : chaque jour ; compteur BODACC toutes les 15 minutes.

## Chiffres du jour (au {date_long(AUJ.isoformat())})

{chr(10).join(chiffres)}

## Pages principales

- [Carte et liste des événements]({S.BASE_URL}/) : carte, compteurs depuis le 1er janvier, derniers événements avec leurs sources.
- [Un an de faillites, carré par carré]({S.BASE_URL}/en-un-an/) : infographie à faire défiler (un carré par défaillance, puis par emploi annoncé, poids local, créations).
- [Explorer les données]({S.BASE_URL}/explorer/) : filtres (région, département, secteur, taille, période, nature des emplois, aides, bénéfices), tri, export CSV, lien partageable.
- [Faillites d'entreprises en France, chiffres à jour]({S.BASE_URL}/faillites-entreprises/) : chiffre officiel de la Banque de France, décompte BODACC, secteurs, départements, créations.
- [Liste des plans sociaux en {AN}]({S.BASE_URL}/liste/) : plans de licenciement et fermetures annoncés, entreprises de 50 salariés et plus en procédure.
- [Par département]({S.BASE_URL}/departements/) : une page par département (adresse : /plans-sociaux/departement/<code>-<nom>/).
- [Méthode, sources et corrections]({S.BASE_URL}/methode/) : sources, fiabilité des recoupements, écarts connus, journal des corrections.
- [Données ouvertes]({S.BASE_URL}/donnees/) : CSV et JSON ; [flux RSS]({S.BASE_URL}/rss.xml).

## Limites à citer

- Le chiffre officiel des défaillances est celui de la Banque de France (publié avec environ deux mois de recul). Le décompte BODACC du site est plus récent mais irrégulier, et compte aussi les sauvegardes.
- Les effectifs sont des tranches INSEE ou des chiffres annoncés : ce sont des ordres de grandeur. Les salariés d'une entreprise en redressement ne sont pas des licenciés.
- La liste des plans sociaux vient surtout de la CGT (source syndicale) et de la presse : ce n'est pas un décompte officiel des plans de sauvegarde de l'emploi.
- Ne pas présenter la comparaison entre créations et faillites comme un solde d'emplois.

## Citer ce site

Nom : « {S.NOM} » — {S.BASE_URL}/ . Indiquer la date de consultation ; pour un chiffre officiel, citer aussi la source d'origine (Banque de France, INSEE, BODACC). Éditeur : {S.EDITEUR}.
"""
    S.ecrire("llms.txt", txt)

def p_sitemap(urls_dep, extra=(), fiches=()):
    j = AUJ.isoformat()
    u = [(S.BASE_URL + "/", "daily", "1.0"), (S.BASE_URL + "/faillites-entreprises/", "daily", "0.9"), (S.BASE_URL + "/liste/", "daily", "0.9"),
         (S.BASE_URL + "/departements/", "daily", "0.7"), (S.BASE_URL + "/methode/", "weekly", "0.6"), (S.BASE_URL + "/donnees/", "weekly", "0.5")]
    u += [(x, "daily", "0.9") for x in extra if x]
    u += [(x, "daily", "0.6") for x in urls_dep]
    u += [(x, "weekly", "0.5") for x in fiches]
    S.ecrire("sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
             + "".join(f"<url><loc>{esc(a)}</loc><lastmod>{j}</lastmod><changefreq>{c}</changefreq><priority>{p}</priority></url>" for a, c, p in u) + "</urlset>")
    return [a for a, _, _ in u]

def images():
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return
    def font(noms, t):
        for n in noms:
            try: return ImageFont.truetype(n, t)
            except OSError: continue
        return ImageFont.load_default()
    titre_f = ["/usr/share/fonts/truetype/custom/BebasNeue-Regular.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
    gras = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"]
    norm = ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"]
    im = Image.new("RGB", (1200, 630), "#17202E"); d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 1200, 10], fill="#E8B21E")
    d.text((60, 50), "PLANS SOCIAUX ET FAILLITES EN FRANCE", font=font(titre_f, 64), fill="#FFFFFF")
    b, a = F.get("bdf"), F.get("annee")
    y = 160
    if b:
        d.text((60, y), fr(b["n"]).replace(" ", " "), font=font(titre_f, 150), fill="#E8B21E")
        d.text((60, y + 150), f"défaillances d'entreprises sur 12 mois ({pct(b['var'])})".replace(" ", " "), font=font(gras, 34), fill="#FFFFFF")
        d.text((60, y + 195), f"Banque de France, à fin {mois_long(b['mois'])}", font=font(norm, 26), fill="#C9CFD6")
    if a:
        d.text((60, y + 260), f"{fr(a['procedures']).replace(chr(8239), ' ')} procédures publiées au BODACC depuis le 1er janvier {AN}", font=font(gras, 30), fill="#FFFFFF")
    d.text((60, 570), f"oraclemarin.fr/plans-sociaux · mis à jour le {date_long(AUJ.isoformat())}", font=font(norm, 24), fill="#C9CFD6")
    im.save(os.path.join(S.PUB, "og.png"), optimize=True)
    ic = Image.new("RGB", (64, 64), "#17202E"); di = ImageDraw.Draw(ic)
    for i, hgt in enumerate((40, 30, 22, 12)):
        di.rectangle([8 + i * 13, 56 - hgt, 17 + i * 13, 56], fill="#E8B21E")
    ic.save(os.path.join(S.PUB, "favicon.png"))

def indexnow(urls):
    body = json.dumps({"host": "oraclemarin.fr", "key": INDEXNOW_KEY, "keyLocation": f"https://oraclemarin.fr/{INDEXNOW_KEY}.txt", "urlList": urls}).encode()
    try:
        r = urllib.request.urlopen(urllib.request.Request("https://api.indexnow.org/IndexNow", body, {"Content-Type": "application/json; charset=utf-8"}), timeout=30)
        print("IndexNow :", r.status, len(urls), "URL", file=sys.stderr)
    except Exception as ex:
        print("IndexNow :", ex, file=sys.stderr)

if __name__ == "__main__":
    import pages_ig, pages_fiche, pages_alertes
    urls_f, FICHES = pages_fiche.p_fiches(EV)
    urls_a = pages_alertes.tout(EV, FICHES)
    import pages_presse; urls_a.append(pages_presse.p_presse(D, EV, FICHES))
    try:
        import pages_cgt; urls_a.append(pages_cgt.p_cgt(EV, FICHES))
    except Exception as ex:
        print("liste noire CGT (page) :", ex)
    try:
        import pages_carte_dep; urls_a.append(pages_carte_dep.p_carte(EV, FICHES))
    except Exception as ex:
        print("carte par département (page) :", ex)
    # page « quotas-co2 » retirée le 18/10/2026 : remplacée par https://oraclemarin.fr/quotas-carbone/ (redirection 301 dans nginx)
    try:
        import pages_recoupements; urls_a.append(pages_recoupements.p_recoupements(EV, FICHES))     # page publique : dans le sitemap
    except Exception as ex:
        print("recoupements (page) :", ex)
    try:
        import pages_liens; urls_a.append(pages_liens.p_liens(EV, FICHES))
    except Exception as ex:
        print("liens (page) :", ex)
    p_faillites(); p_liste(); urls = p_departements(); p_methode(); p_donnees(); p_rss(); p_llms()
    extra = [pages_ig.p_infographie(D, F, TD, AN), pages_ig.p_explorer(D, AN)] + urls_a
    tout = p_sitemap(urls, extra, urls_f); images()
    print("pages.py :", len(tout), "URL dans le sitemap", file=sys.stderr)
    if "--indexnow" in sys.argv:
        indexnow([u for u in tout if "/departement/" not in u and "/entreprise/" not in u])
    if "--indexnow-tout" in sys.argv:
        indexnow(tout)
