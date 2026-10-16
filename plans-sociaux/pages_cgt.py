"""Page « Liste noire CGT » : les lignes du recensement de la CGT (PDF « Liste noire des plans de licenciement »), rangées par rubrique du PDF, avec pour chacune
la page du PDF d'origine, l'entreprise rapprochée (fiche du site) et le chiffre annoncé. Le PDF n'est pas republié : lien vers l'original sur cgt.fr.
Ancres : /cgt/#l<numéro de puce>. Données : cgt/index.json (cgt_pdf.py) et cgt_ligne portée par les événements."""
import json, os, re, sys
H = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, H)
import commun as S
from commun import esc

def coupe(t, n=380):
    t = re.split(r";?\s*[«\"“]", t, 1)[0] if len(t) > n else t           # on ne reprend pas les citations qui suivent la ligne
    return t if len(t) <= n else t[:n].rsplit(" ", 1)[0] + "…"

def p_cgt(EV, FICHES=None):
    I = json.load(open(os.path.join(H, "cgt", "index.json"), encoding="utf-8"))
    par = {}
    for e in EV:
        if e.get("cgt_ligne") is not None: par.setdefault(e["cgt_ligne"], e)
        for s in e.get("sources") or []:
            if s.get("cgt_ligne") is not None: par.setdefault(s["cgt_ligne"], e)
    pdf = I["pdf"]
    try: NOTES = json.load(open(os.path.join(H, "notes_cas.json"), encoding="utf-8"))
    except Exception: NOTES = {}
    secteurs, corps_l = [], []
    cur, n_ok = None, 0
    for l in I["lignes"]:
        sec = l["secteur"] or "Autres"
        if sec != cur:
            if cur is not None: corps_l.append("</ul>")
            secteurs.append(sec); corps_l.append(f'<h2 id="s{len(secteurs)}">{esc(sec.title())}</h2><ul class="cgt-l">'); cur = sec
        e = par.get(l["n"])
        ent = ""
        if e and e.get("siren"):
            nom = e.get("entreprise") or ""
            url = f"{S.BASE}/entreprise/{e['siren']}-{S.slug(nom)[:60].strip('-')}/"
            if FICHES is None or e["siren"] in FICHES: ent = f' <a class="cgt-f" href="{esc(url)}">Fiche : {esc(nom[:40])}</a>'; n_ok += 1
        emp = e.get("emplois_min") if e else None
        nt = NOTES.get(e.get("id")) if e else None
        if e and e.get("note_cas"): nt = ((nt + " ") if nt else "") + ("Estimation à la main : " if e.get("emplois_estime") else "") + e["note_cas"]
        corps_l.append(f'<li id="l{l["n"]}" data-t="{esc((l["texte"] + " " + sec).lower())}"><span>{esc(coupe(l["texte"]))}</span>'
                       f'<div class="cgt-m"><a href="{esc(pdf)}#page={l["page"]}" rel="noopener">dans le PDF, page {l["page"]}</a>'
                       + (f' · {S.fr(emp)} emplois retenus' + (f' (la ligne CGT annonce {S.fr(e["emplois_source_brut"])} : écart relevé d’après la presse)' if e and e.get("emplois_source_brut") and e["emplois_source_brut"] != emp else '') if emp else "") + ent + f' <a class="cgt-ancre" href="#l{l["n"]}" title="Lien vers cette ligne" aria-label="Lien vers cette ligne">#</a></div>' + (f'<div class="cgt-m"><b>Note :</b> {esc(nt)}</div>' if nt else "") + '</li>')
    corps_l.append("</ul>")
    titre = "Liste noire CGT : état des lieux de la vérification, carte et toutes les lignes"
    desc = (f"Les {len(I['lignes'])} lignes du recensement de la CGT (septembre 2023 à mars 2026), rangées par secteur, avec la page du PDF d'origine, "
            "l'entreprise rapprochée et le chiffre annoncé.")
    css = ("<style>.cgt-l{list-style:none;padding:0;margin:0 0 10px}.cgt-l li{padding:9px 0;border-bottom:1px solid #D9D5CC}.cgt-l li:target{background:#FFF4D6;outline:2px solid #C98A00;outline-offset:2px}"
           ".cgt-m{font-size:13px;color:#5A6371;margin-top:3px}.cgt-m a{color:#17202E}.cgt-f{font-weight:600}.cgt-m .cgt-ancre{color:#8A93A0;margin-left:6px;text-decoration:none}.cgt-m .cgt-ancre:hover{color:#B8361E}#cgt-q{font:16px inherit;padding:8px 10px;border:1px solid #D9D5CC;width:100%;max-width:460px}"
           "#cgt-nav{display:flex;flex-wrap:wrap;gap:6px 14px;margin:10px 0;font-size:14px}</style>")
    nav = '<div id="cgt-nav">' + "".join(f'<a href="#s{i + 1}">{esc(s.title())}</a>' for i, s in enumerate(secteurs)) + "</div>"
    js = ("<script>(function(){var q=document.getElementById('cgt-q'),L=[].slice.call(document.querySelectorAll('.cgt-l li')),c=document.getElementById('cgt-c');"
          "function f(){var v=q.value.trim().toLowerCase(),n=0;L.forEach(function(li){var ok=!v||li.dataset.t.indexOf(v)>-1;li.style.display=ok?'':'none';if(ok)n++});c.textContent=n+' ligne'+(n>1?'s':'')+(v?' pour « '+q.value.trim()+' »':'')}"
          "q.addEventListener('input',f);f()})()</script>")
    try:
        import pages_cgt_etat; etat = pages_cgt_etat.bloc(EV, I, FICHES)
    except Exception as ex:
        print("liste noire CGT (état des lieux) :", ex, file=sys.stderr); etat = ""
    corps = (css + f"<h1>Liste noire CGT des plans de licenciement : état des lieux</h1>"
             f'<p class="chapo">Le recensement de la CGT « de septembre 2023 à mars 2026 » ({I["pages"] - 1} pages) reprend les plans de licenciement connus de ses unions et fédérations. '
             f'Chaque ligne ci-dessous renvoie à <b>sa page dans le PDF d\'origine</b> sur cgt.fr ; quand le site a rapproché l\'entreprise, un lien mène à sa fiche. '
             f'Les lignes sont reprises en quelques mots (entreprise, lieu, effectif annoncé) ; les commentaires et citations du PDF ne sont pas reproduits.</p>'
             f'<p class="meta">Source : <a href="{esc(pdf)}" rel="noopener">le PDF complet sur cgt.fr</a>. Recensement indicatif, non exhaustif, établi par la CGT : un plan peut avoir été modifié ou abandonné depuis. '
             f'Les chiffres « retenus » sont ceux que le site a gardés après lecture de la ligne (effectif visé en France).</p>'
             f'<p><a href="liste-cgt-sourcee.pdf" download><b>Télécharger la liste sourcée (PDF)</b></a> : chaque ligne avec le chiffre de la CGT, le chiffre retenu, le statut de recoupement et les liens vers les sources.</p>'
             f'<p><input id="cgt-q" type="search" placeholder="Chercher une entreprise, un département, un mot…" aria-label="Chercher dans la liste noire"> <span id="cgt-c" class="meta"></span></p>'
             + etat + nav + "".join(corps_l) + js)
    graph = [S.site_ld(), {"@type": "WebPage", "name": titre, "url": S.BASE_URL + "/cgt/", "inLanguage": "fr-FR", "isPartOf": {"@id": S.BASE_URL + "/#site"}}]
    S.ecrire("cgt/index.html", S.page(titre, desc, "cgt/", corps, graph, "cgt/"))
    print(f"liste noire CGT : {len(I['lignes'])} lignes, {n_ok} avec fiche", file=sys.stderr)
    return S.BASE_URL + "/cgt/"
