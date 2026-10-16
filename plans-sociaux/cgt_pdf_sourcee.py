#!/usr/bin/env python3
"""PDF « Liste noire CGT, version sourcée » : chaque ligne du recensement de la CGT avec le chiffre de la CGT, le chiffre retenu, le statut de recoupement
(presse, BODACC, fermeture d'établissement) et ses sources cliquables. Les lignes sont reprises en quelques mots, comme sur la page /cgt/ (pas les commentaires du PDF).
Sortie : public/cgt/liste-cgt-sourcee.pdf (Chromium sans interface)."""
import html, json, os, re, sqlite3, sys, time, datetime as dt
H = "/opt/plans-sociaux"; sys.path.insert(0, H)
import commun, cgt_stats
from pages_cgt import coupe
E = json.load(open(H + "/public/data.json", encoding="utf-8"))["evenements"]
I = json.load(open(H + "/cgt/index.json", encoding="utf-8"))
FICHES = json.load(open(H + "/public/fiches.json"))
try: NOTES = json.load(open(H + "/notes_cas.json", encoding="utf-8"))
except Exception: NOTES = {}
esc = html.escape
MOIS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]
def fr(n): return f"{int(n):,}".replace(",", " ") if n is not None else "?"
def date_fr(d): return f"{MOIS[int(d[5:7]) - 1]} {d[:4]}" if d and len(d) >= 7 else "date inconnue"
def dom(u): return re.sub(r"^https?://(www\.)?", "", u or "").split("/")[0]

par = {}
for e in E:
    if cgt_stats.est_cgt(e) and e.get("cgt_ligne") is not None and "#" not in e["id"]: par.setdefault(e["cgt_ligne"], e)
    for s in e.get("sources") or []:
        if s.get("cgt_ligne") is not None: par.setdefault(s["cgt_ligne"], e)

n_ok = n_tot = emp_ok = 0; secteurs = {}
for l in I["lignes"]:
    e = par.get(l["n"]); n_tot += 1
    stat, src, extra = "Non recoupé à ce jour", [], []
    emp_cgt = emp_ret = None; ent = ""; lieu = ""; date = ""; fiche = ""
    if e:
        src = [s for s in cgt_stats.src_indep(e) if s.get("url")]
        proc = e.get("procedure_bodacc"); ferme = e.get("etablissements_fermes") or e.get("fermeture_confirmee") or cgt_stats.site_ferme(e)
        kinds = (["presse"] if src else []) + (["BODACC"] if proc else []) + (["fermeture d'établissement (Sirene)"] if ferme else [])
        if cgt_stats.recoupe(e): stat = "Recoupé : " + " + ".join(kinds or ["source indépendante"]); n_ok += 1; emp_ok += e.get("emplois_min") or 0
        if proc: extra.append(f"BODACC : {esc(str(proc.get('type', '')))} {esc(str(proc.get('date', ''))[:10])}")
        emp_ret = e.get("emplois_min"); emp_cgt = e.get("emplois_cgt_brut") or e.get("emplois_source_brut") or emp_ret
        ent = e.get("entreprise") or ""; lieu = " ".join(x for x in (e.get("commune"), f"({e['dep']})" if e.get("dep") else "") if x)
        date = date_fr((e.get("date") or "")[:10]) + (f" ; fin de PSE {date_fr(e['date_fin_pse'][:10])}" if e.get("date_fin_pse") else "")
        if e.get("siren") in FICHES: fiche = f"{commun.BASE_URL}/entreprise/{FICHES[e['siren']]}/"
        nt = NOTES.get(e.get("id")) or ""
        if e.get("note_cas"): nt = (nt + " " if nt else "") + ("Estimation à la main : " if e.get("emplois_estime") else "") + e["note_cas"]
        if nt: extra.append("Note : " + esc(nt))
        if e.get("siren"): extra.append(f"SIREN {esc(e['siren'])}" + (f" · {esc(e['verif_ident'])}" if e.get("verif_ident") else ""))
    ecart = (emp_ret is not None and emp_cgt is not None and emp_cgt != emp_ret)
    ligne_emp = (f"CGT : {fr(emp_cgt)} · retenu : <b>{fr(emp_ret)}</b>" if ecart else (f"<b>{fr(emp_ret)}</b> emplois" if emp_ret else "effectif non retenu"))
    liens = "".join(f'<li><a href="{esc(s["url"])}">{esc((s.get("source") or dom(s["url"]))[:34])}</a> <span>{esc((s.get("date") or "")[:10])}</span></li>' for s in src[:5])
    cls = "ok" if stat.startswith("Recoup") else "non"
    row = (f'<div class="l {cls}"><div class="h"><span class="n">ligne {l["n"]} · p. {l["page"]}</span><span class="st">{esc(stat)}</span></div>'
           f'<div class="t">{esc(coupe(l["texte"], 300))}</div>'
           f'<div class="m">{esc(ent[:50])}{" · " + esc(lieu) if lieu else ""} · {esc(date)} · {ligne_emp}'
           + (f' · <a href="{esc(fiche)}">fiche</a>' if fiche else "") + '</div>'
           + (f'<ul class="s">{liens}</ul>' if liens else "") + (f'<div class="x">{" · ".join(extra)}</div>' if extra else "") + '</div>')
    secteurs.setdefault(l["secteur"] or "Autres", []).append(row)

R = cgt_stats.calcul(E, len(I['lignes']), I['pages'])
jour = dt.date.today().strftime("%d/%m/%Y")
css = """@page{size:A4;margin:16mm 13mm 16mm 13mm}body{font:10.5px/1.35 'Helvetica Neue',Arial,sans-serif;color:#17202E}
h1{font-size:22px;margin:0 0 4px}h2{font-size:14px;margin:16px 0 6px;padding:3px 0;border-bottom:2px solid #17202E;page-break-after:avoid}
.c{background:#F2F3F5;border-left:5px solid #B8361E;padding:8px 12px;margin:8px 0}.c b{font-size:13px}
.l{border:1px solid #C9CFD6;border-left:4px solid #8A93A0;padding:5px 8px;margin:0 0 5px;page-break-inside:avoid}.l.ok{border-left-color:#1B6E4A}.l.non{border-left-color:#B8361E}
.h{display:flex;justify-content:space-between;font-size:9px;color:#5A6371}.st{font-weight:700}.ok .st{color:#1B6E4A}.non .st{color:#B8361E}
.t{font-weight:600;margin:2px 0}.m{color:#2d3748}.s{margin:3px 0 0;padding-left:14px;font-size:9.5px}.s span{color:#5A6371}.x{font-size:9px;color:#5A6371;margin-top:2px}
a{color:#17202E}"""
doc = (f"<!doctype html><html lang='fr'><meta charset='utf-8'><style>{css}</style><body>"
       f"<h1>Liste noire CGT : version sourcée</h1><div>Recensement de la CGT « de septembre 2023 à mars 2026 », ligne par ligne, avec le recoupement par des sources indépendantes. Édition du {jour}.</div>"
       f"<div class='c'><b>{R['corroborees']} plans d'entreprises sur {R['perimetre']} ({round(100 * R['corroborees'] / R['perimetre'])} %) recoupés</b> par au moins une source indépendante (presse, BODACC, fermeture d'établissement), soit {fr(R['emplois_corroborees'])} emplois sur {fr(R['emplois_perimetre'])}. "
       f"Le périmètre exclut les employeurs publics, les plans hors de France, les lignes sans entreprise précise et le détail des plans de groupe ; ci-dessous, {n_ok} des {n_tot} lignes du PDF portent la mention « Recoupé ».<br>"
       "Chaque ligne indique la page du PDF d'origine de la CGT, le chiffre de la CGT et le chiffre retenu quand ils diffèrent (écart relevé d'après la presse), le statut de recoupement et les liens vers les sources. "
       "« Non recoupé » veut dire qu'aucune source indépendante n'a été retrouvée à ce jour, pas que la ligne est fausse.</div>"
       f"<p>Limites : liste indicative établie par la CGT, non exhaustive ; les dates sont au mois ; un plan a pu être modifié ou abandonné depuis. Les lignes sont reprises en quelques mots, sans les commentaires du PDF. "
       f"Original : <a href='{esc(I['pdf'])}'>{esc(dom(I['pdf']))}</a>. Méthode, sources et corrections : <a href='{commun.BASE_URL}/methode/'>{commun.BASE_URL}/methode/</a>. Données ouvertes (CSV) : <a href='{commun.BASE_URL}/donnees/'>{commun.BASE_URL}/donnees/</a>. Édité par Quentin Closset, Perros-Guirec.</p>"
       + "".join(f"<h2>{esc(s.title())} ({len(rows)})</h2>" + "".join(rows) for s, rows in secteurs.items()) + "</body></html>")
out = H + "/public/cgt/liste-cgt-sourcee.pdf"; tmp = "/tmp/liste-cgt-sourcee.html"
open(tmp, "w", encoding="utf-8").write(doc)
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(); pg.goto("file://" + tmp); pg.wait_for_timeout(500)
    pg.pdf(path=out, format="A4", print_background=True, display_header_footer=True,
           header_template="<span></span>",
           footer_template="<div style='font-size:8px;width:100%;text-align:center;color:#5A6371'>Liste noire CGT, version sourcée · oraclemarin.fr/plans-sociaux/cgt/ · page <span class='pageNumber'></span>/<span class='totalPages'></span></div>",
           margin={"top": "16mm", "bottom": "16mm", "left": "13mm", "right": "13mm"})
    b.close()
print(f"PDF : {n_tot} lignes, {n_ok} recoupées, {os.path.getsize(out) // 1024} Ko")
