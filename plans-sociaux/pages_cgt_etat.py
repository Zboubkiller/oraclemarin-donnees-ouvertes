"""État des lieux de la liste noire CGT : bloc placé en tête de /cgt/. Que des comptes, avec la définition de chaque compte.
Leurs chiffres (lignes du PDF, emplois annoncés) et les nôtres (lignes rapprochées d'une société, identité confirmée, plan recoupé par une autre source)."""
import json, os, sys
H = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, H)
import commun as S
from commun import esc
import cgt_stats

ROUGE = "#B8361E"; ENCRE = "#17202E"; GRIS = "#98A2B3"

def pct(a, b): return f"{round(100 * a / b)} %" if b else "—"
def barre(lib, val, tot, couleur=ROUGE, note="", fond="#E3E6EA"):
    l = max(1.5, 100 * val / tot) if tot else 0
    return (f'<div class="eb"><div class="eb-l">{lib}</div><div class="eb-p" style="background:{fond}"><i style="width:{l:.1f}%;background:{couleur}"></i></div>'
            f'<div class="eb-v">{note}</div></div>')
def barre2(lib, tot, part, tmax, note):
    t = 100 * tot / tmax if tmax else 0; p = 100 * part / tmax if tmax else 0
    return (f'<div class="eb"><div class="eb-l">{lib}</div><div class="eb-p" style="background:#fff"><i style="width:{t:.1f}%;background:#E8B7AB"></i>'
            f'<i style="width:{p:.1f}%;background:{ROUGE};margin-top:-14px"></i></div><div class="eb-v">{note}</div></div>')

CSS = f"""<style>.ek{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px;margin:16px 0}}
.ek>div{{background:#fff;border:1px solid #D9D5CC;border-top:4px solid {ROUGE};padding:10px 14px}}.ek b{{display:block;font:700 2.1rem/1 "Barlow Condensed",sans-serif;color:{ROUGE}}}.ek span{{font-size:14px;color:#5A6371}}
.ek .nous{{border-top-color:{ENCRE}}}.ek .nous b{{color:{ENCRE}}}
.eb{{display:grid;grid-template-columns:minmax(150px,26%) 1fr minmax(110px,22%);gap:10px;align-items:center;margin:5px 0;font-size:14px}}.eb-p{{height:14px;border:1px solid #D9D5CC;overflow:hidden}}
.eb-p i{{display:block;height:14px}}.eb-l{{text-align:right}}.eb-v{{color:#5A6371;font-variant-numeric:tabular-nums}}
@media(max-width:700px){{.eb{{grid-template-columns:1fr}}.eb-l{{text-align:left}}}}
.ep{{border:1px solid #D9D5CC;background:#fff;padding:6px 16px 12px;margin:14px 0}}.ep h3{{margin:12px 0 4px}}.ep p.meta{{margin:4px 0}}
#cgt-carte{{height:520px;border:1px solid #D9D5CC;margin:8px 0}}.cgt-lege i{{display:inline-block;width:12px;height:12px;border-radius:50%;margin:0 5px 0 12px;vertical-align:-1px}}
.ecomp td:nth-child(n+2),.ecomp th:nth-child(n+2){{text-align:right;font-variant-numeric:tabular-nums}}.ecomp .r{{color:{ROUGE};font-weight:600}}
.chantier{{border:2px solid {ROUGE};background:#FFF1EE;color:#17202E;padding:10px 14px;margin:12px 0;font-size:15px}}.chantier b:first-child{{color:{ROUGE};text-transform:uppercase;letter-spacing:.03em}}
.parti{{border-left:5px solid {ENCRE};background:#fff;padding:10px 14px;margin:12px 0;font-size:15px;max-width:80ch}}\n.etat-nav{{display:flex;flex-wrap:wrap;gap:6px 14px;font-size:14px;margin:8px 0 14px}}.etat-nav a{{color:{ROUGE};font-weight:600}}</style>"""

def graphe_liens(P):
    import pages_liens
    d, idx, adj = pages_liens.donnees()
    seeds = {e["siren"] for e in P if e.get("siren") and e["siren"] in idx}
    par = {}
    def tr(x):
        while par.setdefault(x, x) != x: par[x] = par[par[x]]; x = par[x]
        return x
    nodes = set()
    for s in seeds:
        for l in adj.get(s, []):
            nodes.update((l["s"], l["t"]))
    for n in nodes: tr(n)
    for s in nodes:
        for l in adj.get(s, []):
            if l["s"] in nodes and l["t"] in nodes:
                a, b = tr(l["s"]), tr(l["t"])
                if a != b: par[a] = b
    comp = {}
    for n in nodes: comp.setdefault(tr(n), []).append(n)
    bons = sorted((c for c in comp.values() if sum(1 for n in c if n in seeds) >= 2), key=lambda c: -sum(1 for n in c if n in seeds))
    choisis, total = [], 0
    for c in bons:
        if total + len(c) > 110: continue
        choisis.append(c); total += len(c)
    ids = {n for c in choisis for n in c}
    noeuds = [{"id": n, "nom": (idx[n].get("cite") or idx[n]["nom"] or n)[:48], "eff": idx[n].get("eff"), "a": idx[n].get("annonces", 0), "p": bool(idx[n].get("proc")),
               "u": idx[n].get("url"), "c": 1 if n in seeds else 0} for n in ids]
    liens, vus = [], set()
    for n in ids:
        for l in adj.get(n, []):
            k = (l["s"], l["t"], l["force"])
            if l["s"] in ids and l["t"] in ids and k not in vus:
                vus.add(k); liens.append({"s": l["s"], "t": l["t"], "f": l["force"][0], "p": l["preuve"][:120]})
    return {"n": noeuds, "l": liens}, len(choisis), len(seeds)

def preuves_comptes(P):
    L = [e for e in P if e.get("preuve_comptes")]
    if not L: return ""
    fr = S.fr
    out = ('<h2 id="e-comptes">Preuve par les comptes sociaux</h2><p class="chapo"><b>La démarche.</b> Quand aucun article ni aucune procédure collective ne confirme un plan, '
           'on regarde les comptes annuels que l’entreprise dépose au greffe (publics, gratuits sur Pappers ou l’Annuaire des entreprises) : ligne « Salaires et traitements » et ligne « Charges sociales » du compte de résultat, sur plusieurs exercices. '
           'Une masse salariale stable puis en baisse nette est cohérente avec une réduction d’effectif ; une masse salariale qui ne bouge pas ne la confirme pas. '
           '<b>Limites :</b> les comptes donnent un ordre de grandeur annuel, pas le nombre de postes ni la cause de la baisse, et ils arrivent avec un an de retard sur un plan en cours. '
           'Ils ne remplacent pas une source qui nomme le plan ; ils permettent de voir si les chiffres de la CGT sont compatibles avec la réalité économique de l’entreprise. Chaque cas est saisi à la main avec ses liens.</p>')
    for e in L:
        c = e["preuve_comptes"]; an = c["annees"]
        sal, cs = c["salaires"], c["charges_sociales"]
        ev = lambda v: f'{(v[-1] / v[-2] - 1) * 100:+.0f} %'.replace("-", "−")
        ligne = lambda nom, v: "<tr><th>" + nom + "</th>" + "".join(f"<td>{fr(round(x / 1000))} k€</td>" for x in v) + f"<td><b>{ev(v)}</b></td></tr>"
        out += (f'<div class="ep"><h3>{c["nom"]} : {fr(e.get("emplois_min") or 0)} emplois retenus (liste CGT)</h3>'
                '<div class="tablo"><table class="ecomp"><tr><th></th>' + "".join(f"<th>{a}</th>" for a in an) + f"<th>{an[-1]} / {an[-2]}</th></tr>"
                + ligne("Salaires et traitements", sal) + ligne("Charges sociales", cs) + "</table></div>" +
                (f'<p class="chantier"><b>En attente.</b> {c["attente"]}</p>' if c.get("attente") else "") + f'<p class="meta">{c["lecture"]} Source : {c["source"]} : '
                + " · ".join(f'<a href="{u}" rel="noopener">{u.split("/")[2]}</a>' for u in c["liens"]) + ".</p></div>")
    return out

def bloc(EV, I, FICHES=None):
    st = cgt_stats.calcul(EV, len(I["lignes"]), I["pages"])
    P = [e for e in EV if cgt_stats.est_cgt(e) and not cgt_stats.commun.exclu_totaux(e)]
    corr = cgt_stats.recoupe
    n, ep = st["perimetre"], st["emplois_perimetre"]
    # plans d'au moins 50 emplois : combien recoupés, et combien de plans de la presse ne figurent pas dans la liste CGT
    gros = [e for e in P if (e.get("emplois_min") or 0) >= 50]; gros_c = [e for e in gros if corr(e)]
    fr = S.fr
    kpi = ('<div class="ek">'
           f'<div><b>{fr(st["lignes_pdf"])}</b><span>lignes dans le PDF de la CGT ({st["pages"] - 1} pages), soit {fr(st["perimetre"])} plans en France retenus après exclusion des employeurs publics et des doublons de groupes</span></div>'
           f'<div><b>{fr(st["emplois_cgt"])}</b><span>emplois annoncés par la CGT ({fr(st["emplois_perimetre"])} dans le périmètre)</span></div>'
           f'<div class="nous"><b>{pct(st["identifiees"], n)}</b><span>des plans rattachés à une société ({fr(st["identifiees"])} sur {fr(n)}), {fr(st["emplois_identifiees"])} emplois</span></div>'
           f'<div class="nous"><b>{pct(st["confirmees"], n)}</b><span>avec identité confirmée (nom, lieu, taille compatibles, ou vérifiée à la main) : {fr(st["confirmees"])} plans</span></div>'
           f'<div class="nous"><b>{pct(st["corroborees"], n)}</b><span>recoupés par une autre source ({fr(st["corroborees"])} plans) : {pct(st["emplois_corroborees"], ep)} des emplois, {fr(st["emplois_corroborees"])}</span></div>'
           f'<div class="nous"><b>{pct(len(gros_c), len(gros))}</b><span>des plans d\'au moins 50 emplois sont recoupés ({fr(len(gros_c))} sur {fr(len(gros))})</span></div></div>')
    comp = ('<div class="tablo"><table class="ecomp"><thead><tr><th></th><th>Plans</th><th>%</th><th>Emplois</th><th>%</th></tr></thead><tbody>'
            f'<tr><td><b>Selon la CGT</b> (lignes du PDF, périmètre France)</td><td>{fr(n)}</td><td>100 %</td><td>{fr(ep)}</td><td>100 %</td></tr>'
            f'<tr><td>… rattachés à une société (SIREN)</td><td>{fr(st["identifiees"])}</td><td>{pct(st["identifiees"], n)}</td><td>{fr(st["emplois_identifiees"])}</td><td>{pct(st["emplois_identifiees"], ep)}</td></tr>'
            f'<tr><td>… dont identité confirmée</td><td>{fr(st["confirmees"])}</td><td>{pct(st["confirmees"], n)}</td><td></td><td></td></tr>'
            f'<tr><td>&nbsp;&nbsp;↳ lieu vérifié : un établissement de la société existe dans la commune citée (principal ou secondaire, ouvert ou fermé)</td><td>{fr(st["lieu"].get("commune", 0))}</td><td>{pct(st["lieu"].get("commune", 0), st["identifiees"])} des rattachés</td><td></td><td></td></tr>'
            f'<tr><td>&nbsp;&nbsp;↳ lieu vérifié au département seulement (commune non citée ou différente)</td><td>{fr(st["lieu"].get("departement", 0))}</td><td>{pct(st["lieu"].get("departement", 0), st["identifiees"])} des rattachés</td><td></td><td></td></tr>'
            f'<tr><td>&nbsp;&nbsp;↳ aucun établissement dans le département cité (à vérifier : siège ou holding, ou rattachement douteux)</td><td>{fr(st["lieu"].get("aucun", 0))}</td><td>{pct(st["lieu"].get("aucun", 0), st["identifiees"])} des rattachés</td><td></td><td></td></tr>'
            f'<tr class="r"><td class="r">… <b>recoupés par une autre source</b> (presse, BODACC, fermeture au répertoire Sirene)</td><td class="r">{fr(st["corroborees"])}</td><td class="r">{pct(st["corroborees"], n)}</td><td class="r">{fr(st["emplois_corroborees"])}</td><td class="r">{pct(st["emplois_corroborees"], ep)}</td></tr>'
            f'<tr><td>… dont article de presse</td><td>{fr(st["presse"])}</td><td>{pct(st["presse"], n)}</td><td></td><td></td></tr>'
            f'<tr><td>… dont procédure collective publiée au BODACC</td><td>{fr(st["procedure_bodacc"])}</td><td>{pct(st["procedure_bodacc"], n)}</td><td></td><td></td></tr>'
            f'<tr><td>Pas encore recoupés (non vérifié ne veut pas dire faux)</td><td>{fr(st["non_verifiees"])}</td><td>{pct(st["non_verifiees"], n)}</td><td>{fr(st["emplois_non_verifiees"])}</td><td>{pct(st["emplois_non_verifiees"], ep)}</td></tr>'
            f'<tr><td>&nbsp;&nbsp;↳ pas encore traités : la ligne n\'a pas encore été examinée (en cours)</td><td>{fr(st["non_detail"].get("a_traiter", 0))}</td><td>{pct(st["non_detail"].get("a_traiter", 0), n)}</td><td></td><td></td></tr>'
            f'<tr><td>&nbsp;&nbsp;↳ rattachés à une société, source indépendante pas encore cherchée</td><td>{fr(st["non_detail"].get("auto", 0))}</td><td>{pct(st["non_detail"].get("auto", 0), n)}</td><td></td><td></td></tr>'
            f'<tr><td>&nbsp;&nbsp;↳ examinés sans rien trouver de fiable pour l\'instant</td><td>{fr(st["non_detail"].get("doute", 0) + st["non_detail"].get("main", 0))}</td><td>{pct(st["non_detail"].get("doute", 0) + st["non_detail"].get("main", 0), n)}</td><td></td><td></td></tr>'

            f'<tr><td>Plans de la presse, en France, d\'au moins 50 emplois, <b>absents</b> de la liste CGT (même période)</td><td>{fr(st["presse_hors_cgt"])}</td><td></td><td>{fr(st["emplois_presse_hors_cgt"])}</td><td></td></tr>'
            '</tbody></table></div>')
    ent = "".join([
        barre("Lignes du PDF", st["lignes_pdf"], st["lignes_pdf"], GRIS, f'{fr(st["lignes_pdf"])} (100 %)'),
        barre("En France, hors employeurs publics", n, st["lignes_pdf"], "#5A6371", f'{fr(n)} ({pct(n, st["lignes_pdf"])})'),
        barre("Rattachés à une société", st["identifiees"], st["lignes_pdf"], "#E07B28", f'{fr(st["identifiees"])} ({pct(st["identifiees"], st["lignes_pdf"])})'),
        barre("Identité confirmée", st["confirmees"], st["lignes_pdf"], "#B8361E", f'{fr(st["confirmees"])} ({pct(st["confirmees"], st["lignes_pdf"])})'),
        barre("Recoupés par une autre source", st["corroborees"], st["lignes_pdf"], "#7A1B12", f'{fr(st["corroborees"])} ({pct(st["corroborees"], st["lignes_pdf"])})'),
        barre("… dont procédure collective (BODACC)", st["procedure_bodacc"], st["lignes_pdf"], ENCRE, f'{fr(st["procedure_bodacc"])} ({pct(st["procedure_bodacc"], st["lignes_pdf"])})')])
    ordre = ["moins de 50", "50 à 99", "100 à 199", "200 à 499", "500 et plus"]
    tail = "".join(barre(f"{k} emplois", st["taille_corr"].get(k, [0, 0])[1], st["taille_corr"].get(k, [0, 0])[0] or 1, "#7A1B12", f'{st["taille_corr"].get(k, [0, 0])[1]} sur {st["taille_corr"].get(k, [0, 0])[0]} ({pct(st["taille_corr"].get(k, [0, 0])[1], st["taille_corr"].get(k, [0, 0])[0])})') for k in ordre)
    tmax = max((s[2] for s in st["secteurs"]), default=1)
    sect = "".join(barre2(esc(s[0].title()[:46]), s[2], sum(e.get("emplois_min") or 0 for e in P if (e.get("cgt_secteur") or "Autres") == s[0] and corr(e)), tmax,
                          f'{fr(s[1])} plans · {fr(s[2])} emplois') for s in st["secteurs"])
    mois = dict(st["mois"]); ms = [m for m in sorted(mois) if "2023-09" <= m <= "2026-03"]
    mx = max((mois[m] for m in ms), default=1); w = 880; bw = w / max(1, len(ms))
    svg = [f'<svg viewBox="0 0 {w} 190" role="img" aria-label="Nombre de plans par mois d\'annonce" style="width:100%;height:auto;background:#fff;border:1px solid #D9D5CC">']
    for i, m in enumerate(ms):
        h = 130 * mois[m] / mx; x = i * bw
        svg.append(f'<rect x="{x + 2:.1f}" y="{150 - h:.1f}" width="{bw - 4:.1f}" height="{h:.1f}" fill="{ROUGE}"><title>{m} : {mois[m]} plans</title></rect>')
        if m.endswith("-01") or m.endswith("-07") or i == 0:
            svg.append(f'<text x="{x:.1f}" y="170" font-size="12" fill="#5A6371">{m[5:]}/{m[2:4]}</text>')
    svg.append(f'<text x="4" y="14" font-size="12" fill="#5A6371">max {mx} plans par mois</text></svg>')
    pts = [dict(p) for p in st["points"]]
    pj = json.dumps(pts, ensure_ascii=False).replace("</", "<\\/")
    carte = (f'<link rel="stylesheet" href="{S.BASE}/lib/leaflet.css"><div id="cgt-carte" role="img" aria-label="Carte des plans de la liste noire CGT"></div>'
             f'<p class="meta cgt-lege"><i style="background:{ROUGE}"></i>plan recoupé par une autre source<i style="background:#fff;border:2px solid {ROUGE}"></i>pas encore recoupé · la surface suit le nombre d\'emplois · {fr(len(pts))} plans localisés sur {fr(n)}</p>'
             f'<script src="{S.BASE}/lib/leaflet.js"></script><script>(function(){{var P={pj},m=L.map("cgt-carte",{{scrollWheelZoom:false}}).setView([46.6,2.4],6);'
             "L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}',{attribution:'Fond © Esri',maxZoom:16}).addTo(m);"
             "P.sort(function(a,b){return b.e-a.e}).forEach(function(p){var r=Math.max(3,Math.min(16,1.5+.45*Math.sqrt(p.e||1)));"
             f"var c=L.circleMarker([p.lat,p.lon],{{radius:r,color:'{ROUGE}',weight:2,fillColor:p.c?'{ROUGE}':'#fff',fillOpacity:p.c?.55:.4}}).addTo(m);"
             "c.bindPopup('<b>'+p.n+'</b><br>'+(p.e||'?')+' emplois'+(p.c?' · recoupé':' · pas encore recoupé')+(p.l!=null?'<br><a href=\"#l'+p.l+'\">voir la ligne</a>':''))})})()</script>")
    try:
        data, ncomp, nseeds = graphe_liens(P)
    except Exception as ex:
        print("cgt : graphe de liens :", ex, file=sys.stderr); data = None
    if data and data["n"]:
        graph = (f'<style>{__import__("pages_liens").CSS_COMMUN}</style><div class="mini-liens" data-h="560"></div><script type="application/json" class="mini-data">{json.dumps(data, ensure_ascii=False).replace("</", "<\\/")}</script>'
                 f'<p class="meta">{fr(len(data["n"]))} sociétés en {ncomp} groupes qui contiennent <b>au moins deux entreprises de la liste noire</b> (contour sombre). Taille : effectif ; orange : plan social, rouge : procédure collective ; trait plein : lien fort, pointillé : probable. '
                 f'Déplace un bloc, clique pour ouvrir la fiche. <a href="{S.BASE}/groupes/">Carte complète des groupes</a>. Un lien n\'est pas un constat d\'appartenance à un groupe.</p>'
                 f'<script src="{S.BASE}/miniliens.js" defer></script>')
    else:
        graph = '<p class="meta">Pas assez de liens entre entreprises de la liste pour dessiner un graphe.</p>'
    nav = ('<div class="etat-nav"><a href="#e-chiffres">Chiffres</a><a href="#e-entonnoir">Entonnoir</a><a href="#e-taille">Par taille</a><a href="#e-secteurs">Par secteur</a>'
           '<a href="#e-temps">Dans le temps</a><a href="#e-carte">Carte</a><a href="#e-liens">Liens entre sociétés</a><a href="#e-comptes">Preuve par les comptes</a><a href="#e-lignes">Toutes les lignes</a></div>')
    import datetime as dt
    chantier = (f'<div class="parti"><b>Relecture terminée.</b> La relecture manuelle des rapprochements douteux de la liste noire est terminée (mise à jour du {dt.datetime.now().strftime("%d/%m/%Y à %Hh%M")}). '
                'Les chiffres restent recalculés à chaque collecte, à mesure que de nouvelles sources (presse, BODACC) paraissent : <b>« pas recoupé » ne veut pas dire « faux »</b>, cela veut dire qu’aucune source indépendante n’a encore été trouvée.</div>')
    parti = ('<div class="parti"><b>Un parti pris assumé.</b> Ce travail a un objectif : <b>sourcer le déclaratif de la CGT</b>. La liste noire est un recensement syndical, repris tel quel ; '
             'le site cherche, ligne par ligne, des éléments vérifiables (articles de presse, procédures collectives publiées au BODACC, répertoire Sirene) pour que '
             '<b>toute personne qui voudrait contester ces chiffres ait des preuves sous les yeux</b>, avec leurs liens. '
             'Ce n\'est pas une démonstration que la liste est exacte : quand une ligne ne se recoupe pas, quand une entreprise n\'est pas retrouvée ou quand le nombre d\'emplois diffère de celui de la presse, '
             'cela est dit et non masqué. Une erreur ou une source à ajouter ? <a href="mailto:' + S.CONTACT + '?subject=Liste%20noire%20CGT">Écris-moi</a>.</div>')
    return (CSS + chantier + parti + nav
            + f'<h2 id="e-chiffres">Ce que dit la CGT, ce que le site a pu vérifier</h2>' + kpi + comp
            + '<p class="meta"><b>Recoupé</b> : une source indépendante de la CGT et des accords d\'entreprise confirme le plan dans la base du site (article de presse, procédure collective au BODACC, fermeture au répertoire Sirene). '
              '<b>Pas encore recoupé</b> ne signifie pas que la ligne est fausse : la recherche est en cours, ligne par ligne, et ces comptes sont recalculés à chaque collecte. '
              'L\'identification d\'une entreprise est faite par recoupement automatique (nom, lieu, taille) puis, pour une partie, vérifiée à la main.</p>'
            + f'<div class="ep"><h3 id="e-entonnoir">De la ligne du PDF au plan recoupé</h3>{ent}</div>'
            + f'<div class="ep"><h3 id="e-taille">Part des plans recoupés, selon leur taille</h3>{tail}<p class="meta">Les plans les plus gros sont aussi les plus souvent couverts par la presse ; les petits plans, par nature moins médiatisés, le sont moins.</p></div>'
            + f'<div class="ep"><h3 id="e-secteurs">Les secteurs de la liste (emplois annoncés, part recoupée en rouge foncé)</h3>{sect}</div>'
            + f'<div class="ep"><h3 id="e-temps">Plans par mois d\'annonce</h3>{"".join(svg)}</div>'
            + f'<h2 id="e-carte">Où sont les plans de la liste noire</h2>{carte}'
            + f'<h2 id="e-liens">Les sociétés liées entre elles</h2><p class="chapo">Beaucoup de plans touchent plusieurs sociétés d\'un même groupe (dirigeant personne morale commun, société mère, même adresse). Voici les groupes qui regroupent plusieurs entreprises de la liste.</p>{graph}'
            + preuves_comptes(P) + '<h2 id="e-lignes">Toutes les lignes, avec la page du PDF</h2>')
