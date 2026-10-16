"""Une fiche par entreprise (SIREN) : chronologie des procédures et des annonces, procédure en cours (tribunal, administrateur,
mandataire), groupe, comptes, argent public, lobbying, mobilisations, sources. Plus un flux RSS par entreprise.
Seuls les rattachements sûrs ou probables ouvrent une fiche (jamais un rapprochement « indicatif » par le nom seul)."""
import datetime as dt
from email.utils import format_datetime
import commun as S
from commun import esc, fr, eu, mois_court, date_long

import re
PERSO = re.compile(r"(?i)faillite personnelle|interdiction de g[ée]rer|interdiction d.exercer")
LIEN = {"siren_source": "sûr", "siret_commune": "sûr", "nom+dep": "probable"}
CSS = """.fc .det ul{margin:4px 0 0;padding-left:16px}.fc .det li{margin:3px 0}.fiche-grille{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:10px;margin:14px 0}
.fc{background:#fff;border:1px solid #DDE1E6;border-left:5px solid #5B6573;padding:8px 12px}.fc .lab{font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:.04em;color:#5B6573}
.fc .val{font:700 1.3rem/1.2 "Barlow Condensed",sans-serif;margin:3px 0}.fc .det{font-size:13px;color:#3D4654}
.chrono{list-style:none;padding:0;margin:10px 0;border-left:3px solid #C9CFD6}.chrono li{position:relative;padding:4px 0 10px 18px}
.chrono li:before{content:"";position:absolute;left:-7px;top:9px;width:11px;height:11px;border-radius:50%;background:#5B6573}
.chrono li.bodacc:before{background:#17202E}.chrono li.annonce:before{background:#B8361E}.chrono li.mob:before{background:#C2185B}.chrono li.accord:before{background:#00695C}
.chrono .d{font-weight:600;font-variant-numeric:tabular-nums;margin-right:6px}details.jt{font-size:13px;color:#3D4654;max-width:110ch}
.ident{color:#3D4654;margin:-4px 0 8px}
.leg-box{background:#fff;border:1px solid #DDE1E6;border-radius:3px;margin:16px 0;padding:14px 16px;box-shadow:0 1px 3px rgba(0,0,0,0.03)}
.leg-box.rouge{border-left:5px solid #B8361E;background:#FFFBFB}
.leg-box.orange{border-left:5px solid #D97706;background:#FFFDF7}
.leg-box.gris{border-left:5px solid #5B6573;background:#FAFBFD}
.leg-head{display:flex;align-items:baseline;flex-wrap:wrap;gap:8px;margin-bottom:8px}
.leg-tag{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.05em;padding:2px 7px;border-radius:2px;color:#fff}
.leg-box.rouge .leg-tag{background:#B8361E}
.leg-box.orange .leg-tag{background:#D97706}
.leg-box.gris .leg-tag{background:#5B6573}
.leg-tit{font:700 1.15rem/1.3 "Barlow Condensed",sans-serif;color:#17202E}
.leg-syn{font-size:13.5px;line-height:1.45;color:#2D3748;margin:6px 0 10px}
.leg-sigs{margin:0 0 8px;padding-left:18px;font-size:13px;color:#3D4654;line-height:1.45}
.leg-sigs li{margin-bottom:3px}
.leg-pts{font-size:12.5px;color:#4B5563;background:rgba(0,0,0,0.03);padding:6px 10px;border-radius:2px;margin-top:8px}
.leg-foot{font-size:11px;color:#718096;margin-top:8px}"""

def tranche_hatvp(t):
    """« > = 600 000 euros et < 700 000 euros » -> « entre 600 000 et 700 000 € » ; « < 10 000 euros » -> « moins de 10 000 € »."""
    m = re.match(r"\s*>\s*=\s*([\d\s]+?)\s*euros?\s*et\s*<\s*([\d\s]+?)\s*euros?", t or "")
    if m: return f"entre {m.group(1).strip()} et {m.group(2).strip()} €"
    m = re.match(r"\s*<\s*([\d\s]+?)\s*euros?", t or "")
    if m: return f"moins de {m.group(1).strip()} €"
    m = re.match(r"\s*>\s*=\s*([\d\s]+?)\s*euros?", t or "")
    return f"au moins {m.group(1).strip()} €" if m else (t or "")

def url_fiche(siren, nom, absolu=False):
    return f"{S.BASE_URL if absolu else S.BASE}/entreprise/{siren}-{S.slug(nom or '')[:60].strip('-')}/"

def groupes(EV):
    G = {}
    for e in EV:
        if e.get("siren") and (e.get("source") == "BODACC" or e.get("lien") in LIEN):
            G.setdefault(e["siren"], []).append(e)
    return G

def nom_de(evs):
    b = [e for e in evs if e.get("source") == "BODACC"]
    n = (b[0] if b else evs[0]).get("entreprise") or ""
    return n.split(" (")[0] if n.count("(") == 1 and n.endswith(")") else n

def case(lab, val, det=""):
    return f'<div class="fc"><div class="lab">{esc(lab)}</div><div class="val">{val}</div><div class="det">{det}</div></div>'

def src_nom(e):
    return "BODACC" if e.get("source") == "BODACC" else ("liste CGT" if str(e.get("source", "")).startswith("CGT") else e.get("source") or "presse")

def chronologie(evs):
    L = []
    vus = set()
    for e in evs:
        for t in e.get("chronologie") or []:
            if PERSO.search(t["nature"]): continue      # sanction visant le dirigeant (personne physique) : pas publiée ici
            k = (t["date"], t["nature"])
            if k in vus: continue
            vus.add(k)
            d = t.get("date_jugement") or t["date"]
            L.append((d, "bodacc", f"{esc(t['nature'])} <span class=meta>(jugement du {esc(d)}, publié au BODACC le {esc(t['date'])})</span>"))
        if e.get("source") == "Accords d'entreprise":
            continue
        if e.get("source") == "BODACC":
            if not e.get("chronologie"):
                L.append((e.get("date") or "", "bodacc", f'{esc(e.get("detail") or e["type"])} <span class=meta>(<a href="{esc(e.get("url"))}" rel="noopener">annonce BODACC</a>)</span>'))
        else:
            d = e.get("date") or ""
            dd = mois_court(d) if e.get("date_precision") == "mois" and d else d
            emp = f", {fr(e['emplois_min'])} emplois" if e.get("emplois_min") else ""
            srcs = [f'<a href="{esc(e.get("url"))}" rel="noopener">{esc(src_nom(e))}</a>'] + [f'<a href="{esc(x.get("url"))}" rel="noopener">{esc(x.get("source") or "source")}</a>' for x in e.get("sources") or []]
            txt = f"{esc(e['type'].capitalize())} annoncé{emp} ({esc(S.nature_emplois(e))})" + (f" à {esc(e['commune'])}" if e.get("commune") and not e.get("approx") else "")
            prob = " · rapprochement vérifié à la main" if e.get("valide_humain") else (" · rapprochement probable" + (", confirmé à la relecture" if e.get("verif_ident") == "confirmé" else "")) if e.get("lien") == "nom+dep" else ""
            L.append((d, "annonce", f'{txt} <span class=meta>— {" · ".join(srcs)}{prob}</span>' + (f'<br><span class=meta>{esc((e.get("detail") or "")[:240])}</span>' if e.get("detail") else "") + (f'<br><span class=meta><b>Note :</b> {"Estimation à la main : " if e.get("emplois_estime") else ""}{esc(e["note_cas"])}</span>' if e.get("note_cas") else ""), dd))
        for a in e.get("accords") or []:
            k = ("a", a["url"])
            if k in vus: continue
            vus.add(k)
            L.append((a["date"], "accord", f'{"Avenant : " if a.get("avenant") else ""}{esc(a["libelle"].capitalize())} : <a href="{esc(a["url"])}" rel="noopener">« {esc(a["titre"][:180])} »</a> <span class=meta>(accord d\u2019entreprise, Légifrance' + (f' ; signé par {esc(", ".join(a["syndicats"]))}' if a.get("syndicats") else "") + ")</span>"))
        for a in e.get("mobilisations") or []:
            k = ("m", a.get("url"))
            if k in vus: continue
            vus.add(k)
            L.append((a["date"], "mob", f'Mobilisation : <a href="{esc(a.get("url"))}" rel="noopener">{esc(a["titre"])}</a> <span class=meta>({esc(a.get("source") or "")}, via ça brûle)</span>'))
    L.sort(key=lambda x: x[0] or "", reverse=True)
    return "<ul class=chrono>" + "".join(f'<li class="{c}"><span class="d">{esc(x[3] if len(x) > 3 else x[0])}</span>{x[2]}</li>' for x in L for c in [x[1]]) + "</ul>"

LEGITIMITE = {}

def _charge_legitimite():
    global LEGITIMITE
    import sqlite3, json, os
    db_path = os.path.join(S.H, "cache.db")
    try:
        with sqlite3.connect(db_path, timeout=30) as db:
            for siren, niv, tit, js in db.execute("SELECT siren, niveau, titre, js FROM gemini_legitimite"):
                try: LEGITIMITE[siren] = (niv, tit, json.loads(js))
                except Exception: pass
    except Exception as ex:
        print("legitimite (chargement cache) :", ex)

AFFICHER_LEGITIMITE = False      # masqué le 2026-10-15 en attendant décision : synthèse générée par une IA, sans mention ni relecture (voir detecteur_legitimite.py)

def _legitimite_widget(siren):
    if not AFFICHER_LEGITIMITE: return ""
    if not LEGITIMITE:
        _charge_legitimite()
    data = LEGITIMITE.get(siren)
    if not data: return ""
    niv, tit, d = data
    if niv == "DONNEES_INSUFFISANTES": return ""
    
    cfg = {
        "PISTE_A_CREUSER": {"cls": "rouge", "tag": "Piste à creuser"},
        "ELEMENTS_ATTENTION": {"cls": "orange", "tag": "Éléments d'attention"},
        "DIFFICULTES_DOCUMENTEES": {"cls": "gris", "tag": "Difficultés documentées"}
    }.get(niv, {"cls": "gris", "tag": "Analyse factuelle"})
    
    titre = esc(d.get("titre_court") or tit or "")
    synthese = esc(d.get("synthese") or "")
    sigs = "".join(f"<li>{esc(s)}</li>" for s in d.get("signaux_releves") or [])
    pts = d.get("points_a_eclaircir") or []
    pts_html = f'<div class="leg-pts"><b>Points à éclaircir :</b> {esc(" · ".join(pts))}</div>' if pts else ""
    
    return (f'<div class="leg-box {cfg["cls"]}">'
            f'<div class="leg-head"><span class="leg-tag">{cfg["tag"]}</span><span class="leg-tit">{titre}</span></div>'
            f'<div class="leg-syn">{synthese}</div>'
            f'<ul class="leg-sigs">{sigs}</ul>'
            f'{pts_html}'
            f'</div>')

def _liens_widget(siren):
    try:
        import pages_liens
        return pages_liens.widget_fiche(siren)
    except Exception as ex:
        print("liens (fiche) :", ex)
        return ""

def presse_html(evs):
    """Tous les articles de presse qui concernent l'entreprise, quelle que soit l'annonce à laquelle ils sont rattachés (BODACC, liste CGT, presse)."""
    vus, L = set(), []
    def ajoute(u, titre, src, d):
        if not u or u in vus: return
        vus.add(u); L.append((d or "", u, titre, src))
    for e in evs:
        so = str(e.get("source") or "")
        if so not in ("BODACC", "Accords d'entreprise") and not so.startswith(("CGT", "Sirene")): ajoute(e.get("url"), e.get("titre") or e.get("detail") or "article", so, e.get("date"))
        for x in e.get("sources") or []:
            sx = str(x.get("source") or "")
            if sx in ("BODACC", "Accords d'entreprise") or sx.startswith("CGT"): continue
            ajoute(x.get("url"), x.get("titre") or "", sx, x.get("date") or e.get("date"))
    if not L: return ""
    L.sort(key=lambda t: t[0], reverse=True)
    li = "".join(f'<li><a href="{esc(u)}" rel="noopener">{esc((t if t and t != "article de presse (vérification)" else s_)[:170])}</a> <span class="meta">({esc(s_)}{", " + esc(d[:10]) if d else ""})</span></li>' for d, u, t, s_ in L[:15])
    return f'<h2>Articles de presse</h2><ul>{li}</ul>'

def fiche(siren, evs):
    nom = nom_de(evs)
    b = sorted([e for e in evs if e.get("source") == "BODACC"], key=lambda e: e.get("date") or "", reverse=True)
    a = sorted([e for e in evs if e.get("source") != "BODACC"], key=lambda e: e.get("date") or "", reverse=True)
    ref = (b or a)[0]
    naf = next((e.get("naf") for e in evs if e.get("naf")), None)
    sect = S.secteur(naf) or ""
    commune = next((e.get("commune") for e in b if e.get("commune")), None) or next((e.get("commune") for e in a if e.get("commune") and not e.get("approx")), None)
    dep = ref.get("dep")
    cat = next((e.get("categorie") for e in evs if e.get("categorie")), None)
    trn = next(((e["emplois_min"], e["emplois_max"]) for e in b if e.get("emplois_min") is not None), None)
    # résumé factuel (cité tel quel par les moteurs et assistants)
    phr = []
    for e in b[:2]:
        phr.append(f"{e['type']} judiciaire ouvert le {date_long(e['date'])}" + (f" ({esc(e['tribunal'].replace('Greffe du ', ''))})" if e.get("tribunal") else "")
                   if e["type"] != "sauvegarde" else f"procédure de sauvegarde ouverte le {date_long(e['date'])}")
    for e in a[:2]:
        d = e.get("date") or ""
        quand = ("en " + S.mois_long(d[:7])) if e.get("date_precision") == "mois" and d else (f"le {date_long(d)}" if d else "")
        phr.append(f"{e['type']} annoncé {quand}" + (f" ({fr(e['emplois_min'])} emplois, selon {src_nom(e)})" if e.get("emplois_min") else f" (selon {src_nom(e)})"))
    su = next((e["suite"] for e in b if e.get("suite") and e["suite"]["issue"] != "en cours"), None)
    if su: phr.append({"liquidation": "puis liquidation", "cession": "puis plan de cession", "plan": "puis plan de continuation"}[su["issue"]] + f" le {date_long(su['date'])}")
    chapo = f"<b>{esc(nom)}</b>" + (f", {esc(sect.lower())}" if sect else "") + (f", {esc(commune)} ({esc(dep)})" if commune and dep else "") + " : " + " ; ".join(phr) + "."
    # cases
    cs = []; ai = []     # ai : lignes de la carte « Argent public »
    if trn: cs.append(case("Effectif", f"{fr(trn[0])} à {fr(trn[1])}", "salariés (tranche INSEE)" + (f", {esc(cat)}" if cat else "")))
    g = next((e["groupe"] for e in evs if e.get("groupe")), None)
    if g and S.cle_nom(g["nom"]) != S.cle_nom(nom): cs.append(case("Groupe", esc(g["nom"]), (esc(g.get("pays") or "") + " · " if g.get("pays") else "") + "source : " + esc(g.get("source") or "")))
    c = next((e["comptes"] for e in evs if (e.get("comptes") or {}).get("resultat_net") is not None), None)
    if c: cs.append(case(f"Résultat net {c['derniere_annee']}", eu(c["resultat_net"]), ("chiffre d'affaires : " + eu(c["ca"])) if c.get("ca") else "dernier exercice publié"))
    ap = next((e["argent_public"] for e in evs if e.get("argent_public")), None)
    if ap and (ap.get("marches") or {}).get("total"):
        m = ap["marches"]; ai.append(("Marchés publics", eu(m["total"]), f"{m['n']} marché{'s' if m['n'] > 1 else ''} publics ({esc(m.get('de') or '')}–{esc(m.get('a') or '')}), hors accords-cadres"))
    if ap and (ap.get("ademe") or {}).get("total"):
        m = ap["ademe"]; ai.append(("Aides ADEME", eu(m["total"]), f"{m.get('n', '')} aide(s)"))
    dr = next((e["direction"] for e in evs if e.get("direction")), None)
    ho = [p for p in (dr or {}).get("dirigeants_pm") or [] if p.get("holding")]
    if ho:    # seuls les dirigeants holdings ou fonds sont montrés : les changements d'administration du BODACC sont trop fréquents (sans noms) pour être informatifs
        cs.append(case("Direction", "Holding ou fonds", "Dirigée par " + ", ".join(f"{esc(p['nom'])} ({esc(p.get('qualite') or 'dirigeant')})" for p in ho[:3]) + ". Aucun lien de cause n’est établi ; les cessions de titres ne sont pas publiées."))
    pe = next((e["programmes_etat"] for e in evs if e.get("programmes_etat")), None)
    if pe:
        j = pe["projets"][0]; pp = next((e["programmes_etat"]["proximite"] for e in evs if (e.get("programmes_etat") or {}).get("proximite")), None)
        ai.append(("Programmes d’État (PIA, France 2030)", eu(pe["total"]), f"{pe['n']} projet(s) financé(s) via l’ADEME (déjà compris, pour la plupart, dans « Aides ADEME » ci-dessus) ; le plus récent : {esc((j.get('projet') or j.get('objet') or '')[:90])} ({esc(j.get('programme') or '')}, {esc((j.get('date') or '')[:7])})"
                    + (f". <b>{pp['n']} dans les 24 mois avant l’annonce</b> ({eu(pp['montant'])})" if pp else "") + f" · <a href=\"{esc(pe['url'])}\" rel=\"noopener\">source</a>"))
    ct = (ap or {}).get("contrats_soutien")
    if ct:
        ai.append(("Contrat de soutien (appel d’offres ADEME)", eu(sum(c["montant"] for c in ct)),
                       f"{len(ct)} contrat(s) attribué(s) le {esc(ct[0]['date'][:10])} par appel d’offres « Grands projets industriels de décarbonation » : <b>montant d’un contrat de soutien pluriannuel</b> (la presse parle de quinze ans pour ce type de contrat), versé progressivement et non en une fois ; ce n’est pas une aide déjà reçue. {esc((ct[0].get('objet') or '')[:110])}"))
    pr = next((e["proximite"] for e in evs if (e.get("proximite") or {}).get("n")), None)
    if pr:
        g = pr.get("plus_grosse") or {}
        ai.append(("Aide avant l'annonce", eu(pr["montant"]), f"{pr['n']} aide(s) dans les {pr['fenetre_mois']} mois précédant l'annonce"
                       + (f". La plus importante : « {esc((g.get('libelle') or '')[:120])} » ({eu(g['montant'])}, {esc((g.get('date') or '')[:10])}{', le même mois que l’annonce' if g.get('delai_mois') == 0 else ''}). L’aide peut concerner un autre site de la même société que celui de l’annonce." if g.get("montant") else "")))
    lb = next((e["lobbying"] for e in evs if e.get("lobbying")), None)
    if ai:
        tete = next((v for t, v, d in ai if t.startswith("Aide avant")), None) or next((v for t, v, d in ai if t.startswith("Aides ADEME")), None) or ai[0][1]
        cs.append(case("Argent public" + (" : 24 mois avant l’annonce" if any(t.startswith("Aide avant") for t, v, d in ai) else ""), tete, "<ul>" + "".join(f"<li><b>{esc(t)}</b> : {v} — {d}</li>" for t, v, d in ai) + "</ul>"))
    if lb: cs.append(case("Lobbying (HATVP)", esc(tranche_hatvp(lb["depenses"])), f"en {esc(lb['annee'])}" + (f" : « {esc(lb['objets'][0][:120])} »" if lb.get("objets") else "")))
    for sd in next((e["sanction_delais"] for e in evs if e.get("sanction_delais")), []) or []:
        cs.append(case("Amende retards de paiement", eu(sd["montant"]), f"DGCCRF, {esc(sd['date'][:7])}"))
    pl = next((e["poids_local"] for e in evs if (e.get("poids_local") or {}).get("part_commune_pct", 0) >= 1), None)
    if pl: cs.append(case("Poids local", f"{str(pl['part_commune_pct']).replace('.', ',')} %", f"de l'emploi salarié privé de {esc(pl['commune'])} (URSSAF {pl['annee']})"))
    acs = {a["url"]: a for e in evs for a in e.get("accords") or []}
    if acs:
        cats = sorted({a["libelle"] for a in acs.values()})
        cs.append(case("Accords d'entreprise", fr(len(acs)), "liés à l'emploi : " + esc(", ".join(cats))))
    ef = {x["siret"]: x for e in evs for x in e.get("etablissements_fermes") or []}
    if ef:
        x = sorted(ef.values(), key=lambda x: x["date"])[-1]
        cs.append(case("Établissements fermés (Sirene)", fr(len(ef)), f"dont {esc(x['commune'])} le {esc(x['date'])} ({x['effectif'][0]}–{x['effectif'][1]} salariés) ; registre, à vérifier"))
    rs = {x["siret"]: x for e in evs for x in e.get("restructurations") or []}
    if rs:
        x = next((x for x in rs.values() if x.get("alerte")), sorted(rs.values(), key=lambda x: x["date"])[-1])
        det = f"{esc(x['commune'])}, {esc(x['date'])} : {esc(x['nature'])}" + (f" vers {esc(', '.join(x['vers']))}" if x.get("vers") else "")
        if x.get("alerte"): det += f" ; <b>à creuser</b> : {esc(x['alerte'])}"
        cs.append(case("Restructurations (hors totaux)", fr(len(rs)), det))
    SL = {}
    for e in evs:
        for l in e.get("societes_liees") or []:
            if l["force"] in ("fort", "probable") and l.get("nom") and l["siren"] not in SL: SL[l["siren"]] = l
    if SL:
        L = sorted(SL.values(), key=lambda l: (l["force"] != "fort", l["nom"]))[:5]
        det = " ; ".join(f"{esc(l['nom'])} ({esc(l['preuves'][0])})" for l in L)
        cs.append(case("Sociétés liées (avec la preuve)", fr(len(SL)), det + ". Liens établis par les dirigeants, l'adresse ou le BODACC ; ce ne sont pas des constats d'appartenance à un groupe."))
    rr = [e for e in evs if e.get("reprise_recente")]
    if rr:
        e0 = next((e for e in rr if e["reprise_recente"].get("a_creuser")), rr[0]); r = e0["reprise_recente"]
        ct = f" : {esc(r['contrepartie'])}" if r.get("contrepartie") else ""
        det = (f"{esc(r['role'])}{ct} ; opération publiée au <a href=\"{esc(r['url'])}\" rel=\"noopener\">BODACC</a> le {esc(r['date'])}, soit {r['delai_mois']} mois avant l'annonce du {esc((e0.get('date') or '')[:10])}. "
               "Aucun lien de cause n'est établi ; les cessions de titres ne sont pas publiées.")
        if r.get("a_creuser"): det += " <b>À creuser</b> : " + esc(" ; ".join(r["motifs"])) + "."
        cs.append(case("Reprise ou fusion récente (BODACC)", fr(r["delai_mois"]) + " mois", det))
    nm = sum(len(e.get("mobilisations") or []) for e in evs)
    if nm: cs.append(case("Mobilisations", fr(nm), "article(s) relevés par ça brûle"))
    # procédure
    proc = ""
    if b:
        e = b[0]; ac = e.get("acteurs") or {}
        lignes = [f"<li><b>Tribunal</b> : {esc((e.get('tribunal') or '').replace('Greffe du ', ''))}</li>" if e.get("tribunal") else ""]
        if e.get("cessation_paiements"): lignes.append(f"<li><b>Date de cessation des paiements</b> : {date_long(e['cessation_paiements'])}</li>")
        for r, lab in (("administrateur", "Administrateur judiciaire"), ("mandataire", "Mandataire judiciaire"), ("liquidateur", "Liquidateur"), ("commissaire", "Commissaire à l'exécution du plan")):
            if ac.get(r): lignes.append(f"<li><b>{lab}</b> : {esc(', '.join(ac[r]))}</li>")
        proc = (f"<h2>Procédure collective</h2><ul>{''.join(lignes)}</ul>"
                + (f'<details class="jt"><summary>Texte du jugement (BODACC)</summary><p>{esc(e["jugement_texte"])}</p></details>' if e.get("jugement_texte") else "")
                + f'<p class="meta">Les administrateurs et mandataires sont extraits automatiquement du texte publié au BODACC : vérifiez sur <a href="{esc(e.get("url"))}" rel="noopener">l\'annonce officielle</a>.</p>')
    ops = OPS.get(siren) or []
    ops_html = ""
    if ops:
        def li_op(o):
            m = f" — montant indiqué : <b>{eu(o['montant'])}</b>" if o.get("montant") else ""
            role = ("cédant" if o["role"] == "vendeur" else "acquéreur") if o["nature"].startswith("achat") else ""
            c = (", " if role else "") + f"avec {esc(o['contrepartie'])}" if o.get("contrepartie") else ""
            par = f" ({role}{c})" if role or c else ""
            return (f'<li><span class="d">{esc(o["date"])}</span> {esc(o["nature"])}{par}{m} '
                    f'<a href="{esc(o.get("url") or "")}" rel="noopener">annonce</a><br><span class="meta">{esc(o["extrait"][:220])}</span></li>')
        ops_html = ("<h2>Opérations publiées au BODACC</h2><p class=\"meta\">Achats et ventes de fonds de commerce ou de branches d'activité, apports, fusions, "
                    "avec le montant quand l'annonce l'indique. Les rachats de la société elle-même (cessions d'actions, LBO) ne sont pas publiés au BODACC.</p>"
                    "<ul class=\"chrono\">" + "".join(li_op(o) for o in ops[:12]) + "</ul>")
        nm = sum(1 for o in ops if o.get("montant"))
        cs.append(case("Opérations BODACC", fr(len(ops)), "achats, ventes, fusions" + (f", dont {nm} avec montant" if nm else "")))
    liens = (f'<h2>Documents et registres</h2><ul><li><a href="https://annuaire-entreprises.data.gouv.fr/entreprise/{siren}" rel="noopener">Annuaire des entreprises (État)</a> : identité, dirigeants, annonces BODACC</li>'
             f'<li><a href="https://data.inpi.fr/entreprises/{siren}" rel="noopener">INPI</a> : comptes annuels déposés, actes</li>'
             + "".join(f'<li><a href="{esc(e.get("url"))}" rel="noopener">Annonce BODACC du {esc(e.get("date_publication") or e.get("date"))}</a></li>' for e in b[:3]) + "</ul>")
    titre = f"{nom} : " + ", ".join(dict.fromkeys(("procédure collective" if e.get("source") == "BODACC" else e["type"]) for e in evs)) + " (chronologie)"
    desc = (f"{nom} (SIREN {siren}) : " + " ; ".join(phr))[:300]
    chemin = url_fiche(siren, nom, True)[len(S.BASE_URL) + 1:]
    corps = (f"<style>{CSS}</style><p class=meta><a href=\"{S.BASE}/explorer/\">Explorer</a> › entreprise</p><h1>{esc(nom)}</h1>"
             f'<p class="ident">SIREN {siren[:3]} {siren[3:6]} {siren[6:]}' + (f" · {esc(naf)}" if naf else "") + (f' · <a href="{S.dep_url(dep)}">{esc(S.DEPS.get(dep, dep))}</a>' if dep in S.DEPS else "")
             + f' · <a href="rss.xml">suivre cette entreprise (RSS)</a></p><p class="chapo">{chapo}</p>'
             + _legitimite_widget(siren)
             + "<h2>Chronologie</h2>" + chronologie(evs) + presse_html(evs)
             + (f'<h2>Contexte financier et public</h2><div class="fiche-grille">{"".join(cs)}</div>' if cs else "")
             + _liens_widget(siren) + proc + ops_html + liens
             + f'<p class="meta">Fiche générée automatiquement à partir de sources publiques (BODACC, liste CGT, presse, accords d’entreprise publiés sur Légifrance, INSEE, URSSAF, DECP, ADEME, HATVP, DGCCRF, ça brûle), mise à jour plusieurs fois par jour. '
             f'Une erreur ? <a href="mailto:quentinclosset@gmail.com?subject=Fiche%20{siren}">Signalez-la</a>. <a href="{S.BASE}/methode/">Méthode et limites</a>.</p>'
             f'<p><b>Vous suivez ce dossier ?</b> Article, section syndicale, enquête : l’outil est gratuit et fait par une seule personne. '
             f'<a href="mailto:quentinclosset@gmail.com?subject=Fiche%20{siren}%20%E2%80%93%20j%27utilise%20l%27outil">Dites-moi à quoi il vous sert</a>, ça m’aide à l’améliorer.</p>')
    url = S.BASE_URL + "/" + chemin
    graph = [S.site_ld(), {"@type": "WebPage", "name": titre, "url": url, "inLanguage": "fr-FR", "dateModified": dt.date.today().isoformat(), "isPartOf": {"@id": S.BASE_URL + "/#site"},
             "about": {"@type": "Organization", "name": nom, "identifier": {"@type": "PropertyValue", "propertyID": "SIREN", "value": siren},
                       "sameAs": [f"https://annuaire-entreprises.data.gouv.fr/entreprise/{siren}"]}},
             {"@type": "BreadcrumbList", "itemListElement": [{"@type": "ListItem", "position": 1, "name": S.NOM, "item": S.BASE_URL + "/"},
                                                             {"@type": "ListItem", "position": 2, "name": nom, "item": url}]}]
    S.ecrire(chemin + "index.html", S.page(titre, desc, chemin, corps, graph, "explorer/"))
    # flux RSS de l'entreprise
    items = []
    for e in evs:
        for t in e.get("chronologie") or []:
            if PERSO.search(t["nature"]): continue
            items.append((t["date"], f"{nom} : {t['nature']}", e.get("url"), f"bodacc-{siren}-{t['date']}-{S.slug(t['nature'])[:40]}"))
        if e.get("source") != "BODACC" and e.get("date"):
            items.append((e["date"], f"{nom} : {e['type']} annoncé" + (f", {fr(e['emplois_min'])} emplois" if e.get("emplois_min") else ""), e.get("url"), e.get("id")))
        for m in e.get("mobilisations") or []:
            items.append((m["date"], f"{nom} : mobilisation — {m['titre']}", m.get("url"), "mob-" + S.slug(m["titre"])[:60]))
    items = sorted({i[3]: i for i in items}.values(), key=lambda i: i[0], reverse=True)[:40]
    S.ecrire(chemin + "rss.xml", rss(f"{nom} — {S.NOM}", url, url + "rss.xml", f"Procédures, annonces et mobilisations concernant {nom} (SIREN {siren}).", items))
    return url

def rss(titre, lien, soi, desc, items):
    def it(d, t, u, g):
        try: when = format_datetime(dt.datetime.fromisoformat(d[:10] + "T12:00:00+00:00"))
        except Exception: when = format_datetime(dt.datetime.now(dt.timezone.utc))
        return f"<item><title>{esc(t)}</title><link>{esc(u or lien)}</link><guid isPermaLink=\"false\">{esc(g)}</guid><pubDate>{when}</pubDate></item>"
    return ('<?xml version="1.0" encoding="UTF-8"?><rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom"><channel>'
            f'<title>{esc(titre)}</title><link>{esc(lien)}</link><atom:link href="{esc(soi)}" rel="self" type="application/rss+xml"/><description>{esc(desc)}</description>'
            f'<language>fr-fr</language><lastBuildDate>{format_datetime(dt.datetime.now(dt.timezone.utc))}</lastBuildDate>{"".join(it(*i) for i in items)}</channel></rss>')

OPS = {}

def p_fiches(EV):
    global OPS
    _charge_legitimite()
    try:
        import operations; OPS = operations.par_siren()
    except Exception as ex:
        print("opérations :", ex); OPS = {}
    G = groupes(EV)
    urls = [fiche(s, evs) for s, evs in G.items()]
    return urls, {s: url_fiche(s, nom_de(evs)) for s, evs in G.items()}
