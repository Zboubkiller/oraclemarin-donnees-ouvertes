"""Infographie à défilement (« Un an de faillites, carré par carré ») et explorateur de données filtrable.
Appelé par pages.py ; produit en-un-an/index.html, explorer/index.html et explorer.json."""
import json, os, re, sqlite3, unicodedata, datetime as dt
import commun as S
from commun import esc, fr, pct, mois_long, date_long

def types_aide(e):
    """Types d'aide publique avec une aide datée dans les 24 mois avant l'annonce (ADEME, France Relance), un marché public notifié l'année de l'annonce ou la précédente (DECP : année seulement), ou une aide de minimis (non datée dans la source)."""
    mois = lambda d: int(d[:4]) * 12 + int(d[5:7]) if d and re.match(r"\d{4}-\d{2}", d) else None
    ap, me, out = e.get("argent_public") or {}, mois(e.get("date")), []
    if me is not None:
        if any(mi is not None and 0 <= me - mi <= 24 for mi in (mois(d[0]) for d in (ap.get("ademe") or {}).get("dates", []))): out.append("ADEME")
        if any(mi is not None and 0 <= me - mi <= 24 for mi in (mois(r.get("date")) for r in e.get("relance") or [])): out.append("France Relance")
        an = e["date"][:4]
        if any(str(y) in (ap.get("marches") or {}).get("par_annee", {}) for y in (int(an) - 1, int(an))): out.append("Marchés publics")
    if (e.get("programmes_etat") or {}).get("proximite"): out.append("PIA / France 2030 (ADEME)")
    if ap.get("minimis"): out.append("Aide de minimis (sans date)")
    return out

def _cle(nom): return re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFD", (nom or "").lower()).encode("ascii", "ignore").decode())[:20]

def periode(m0, m1):
    """« entre juillet et septembre 2026 », « entre novembre 2025 et janvier 2026 »."""
    if m0[:4] == m1[:4]: return f"entre {S.MOIS[int(m0[5:7]) - 1]} et {mois_long(m1)}"
    return f"entre {mois_long(m0)} et {mois_long(m1)}"

def part_50(D, TD):
    """Part des entreprises de 50 salariés et plus parmi les jugements d'ouverture, sur les mois entiers couverts par l'historique."""
    cov = (D["tendance"].get("plus_de_50_salaries") or {}).get("couverture")
    if not cov: return None
    try:
        db = sqlite3.connect(os.path.join(S.H, "cache.db"), timeout=60)
        ev = [json.loads(r[0]) for r in db.execute("select js from ev")]
    except sqlite3.OperationalError:
        return None
    d0, d1 = dt.date.fromisoformat(cov[0]), dt.date.fromisoformat(cov[1])
    mois = []
    m = (d0.replace(day=1) + dt.timedelta(days=32)).replace(day=1) if d0.day > 1 else d0.replace(day=1)
    while (m + dt.timedelta(days=32)).replace(day=1) <= d1:
        mois.append(m.strftime("%Y-%m")); m = (m + dt.timedelta(days=32)).replace(day=1)
    if not mois: return None
    par_siren = {}                               # une entreprise compte une fois, même si elle a plusieurs annonces
    for e in ev:
        if e.get("source") == "BODACC" and (e.get("date_publication") or "")[:7] in mois:
            k = e.get("siren") or e.get("id"); par_siren[k] = max(par_siren.get(k, 0), e.get("emplois_min") or 0)
    n50, sal = len(par_siren), sum(par_siren.values())
    ntot = sum(n for (mm, d), n in TD.items() if mm in mois)
    if not ntot or not n50: return None
    return {"mois": mois, "n50": n50, "ntot": ntot, "pour_mille": round(1000 * n50 / ntot, 1), "salaries": sal}

def emplois_par_entreprise(plans):
    """Une ligne par entreprise (même dédoublonnage que le compteur : 60 jours), effectif le plus élevé annoncé."""
    garde = []
    for e in sorted(plans, key=lambda e: e.get("date") or ""):
        if not e.get("emplois_min"): continue
        k = _cle(e.get("entreprise"))
        g = next((x for x in garde if k and x["k"] == k and (dt.date.fromisoformat(e["date"]) - dt.date.fromisoformat(x["date"])).days <= 60), None)
        if g:
            if e["emplois_min"] > g["n"]: g.update(n=e["emplois_min"], nature=S.nature_emplois(e), src=e["source"])
        else:
            garde.append({"k": k or e.get("id"), "nom": e.get("entreprise"), "n": e["emplois_min"], "date": e["date"], "nature": S.nature_emplois(e), "src": e["source"]})
    return sorted(garde, key=lambda x: -x["n"])

COUL_NAT = {"suppressions annoncées": "#B8361E", "départs volontaires": "#3E7CB1", "emplois menacés": "#D9822B"}

IG_CSS = """
main{max-width:980px}.ig p{font-size:19px;line-height:1.55;max-width:62ch}.ig h2{font-size:2.1rem;margin-top:70px}
.ig-intro h1{font-size:clamp(2.4rem,8vw,4.6rem)}.ig-intro .chapo{font-size:21px}
.ig-wrap{position:relative;margin:26px 0}.ig-grille{position:relative;width:100%}
.ig-b{position:absolute;--fond:#E9ECEF;background:linear-gradient(90deg,var(--fond) 1px,transparent 1px) 0 0/var(--c) var(--c),linear-gradient(var(--fond) 1px,transparent 1px) 0 0/var(--c) var(--c),var(--col)}
.ig-lab{position:absolute;left:0;transform:translateY(-100%);background:#F7F8F9;border:1px solid #C9CFD6;border-left:4px solid var(--col,#17202E);padding:2px 8px;font-size:14px;font-weight:600;white-space:nowrap;max-width:100%;overflow:hidden;text-overflow:ellipsis;z-index:1}
.ig-compteur{position:sticky;top:0;z-index:3;background:#17202E;color:#fff;padding:8px 14px;font:600 16px Barlow,sans-serif;display:flex;gap:14px;flex-wrap:wrap;align-items:baseline}
.ig-compteur b{font:700 1.7rem "Barlow Condensed",sans-serif;color:#E8B21E;font-variant-numeric:tabular-nums}
.ig-leg{display:flex;flex-wrap:wrap;gap:6px 18px;font-size:15px;margin:8px 0}.ig-leg i{display:inline-block;width:13px;height:13px;margin-right:6px;vertical-align:-2px}
.ig-barres div{height:30px;margin:6px 0;background:#17202E;color:#fff;font-size:14px;padding:5px 8px;white-space:nowrap;overflow:visible}
.ig-cta{display:inline-block;background:#17202E;color:#fff;padding:12px 18px;text-decoration:none;font-weight:600;margin:6px 8px 6px 0}
"""

IG_JS = r"""
(function(){
const DATA=JSON.parse(document.getElementById('ig-data').textContent);
const nf=n=>Math.round(n).toLocaleString('fr-FR');
function grille(el,segs,c){
  const W=el.clientWidth,cols=Math.max(8,Math.floor(W/c));el.innerHTML='';el.style.setProperty('--c',c+'px');
  let i=0;const marks=[];
  for(const s of segs){if(!s.n)continue;const a=i,b=i+s.n,r0=Math.floor(a/cols),c0=a%cols,r1=Math.floor((b-1)/cols),c1=(b-1)%cols;
    const add=(r,x0,x1,rows)=>{const d=document.createElement('div');d.className='ig-b';d.style.cssText=`top:${r*c}px;left:${x0*c}px;width:${(x1-x0)*c}px;height:${rows*c}px;--col:${s.col};--c:${c}px`;if(s.titre)d.title=s.titre;el.appendChild(d)};
    if(r0===r1)add(r0,c0,c1+1,1);else{add(r0,c0,cols,1);if(r1-r0>1)add(r0+1,0,cols,r1-r0-1);add(r1,0,c1+1,1)}
    if(s.label&&(s.n>=cols*2||s.force))marks.push({top:r0*c,a,s});
    i=b}
  el.style.height=Math.ceil(i/cols)*c+'px';
  let last=-99;for(const m of marks){if(m.top-last<30)continue;last=m.top;const l=document.createElement('div');l.className='ig-lab';l.style.top=(m.top+c)+'px';l.style.setProperty('--col',m.s.col);l.textContent=m.s.label;el.appendChild(l)}
  return{cols,total:i,marks}}
const G={};
function tout(){
  const larg=document.querySelector('main').clientWidth;
  G.f=grille(document.getElementById('g-faillites'),DATA.faillites,larg>700?7:5);
  if(DATA.p50)grille(document.getElementById('g-50'),[{n:1000-Math.round(DATA.p50),col:'#17202E'},{n:Math.round(DATA.p50),col:'#E8B21E'}],larg>700?16:12);
  G.e=grille(document.getElementById('g-emplois'),DATA.emplois,larg>700?10:7);
  DATA.local.forEach((x,k)=>grille(document.getElementById('g-local-'+k),[{n:x.n,col:'#B8361E',titre:x.nom+' : '+nf(x.n)+' emplois annoncés'},{n:Math.max(0,x.eff-x.n),col:'#9AA3AE',titre:'autres salariés du privé de la commune'}],larg>700?14:10));
  maj()}
function maj(){const g=document.getElementById('g-faillites');if(!G.f)return;const r=g.getBoundingClientRect();const c=parseFloat(g.style.getPropertyValue('--c'))||7;
  const y=innerHeight*0.55-r.top;const n=Math.max(0,Math.min(G.f.total,Math.floor(y/c)*G.f.cols));
  document.getElementById('ig-n').textContent=nf(n);let sec='';for(const m of G.f.marks)if(m.a<=n)sec=m.s.label;document.getElementById('ig-sec').textContent=sec}
let t;addEventListener('resize',()=>{clearTimeout(t);t=setTimeout(tout,200)});addEventListener('scroll',maj,{passive:true});tout()})();
"""

def p_infographie(D, F, TD, AN):
    b, a, cr = F.get("bdf"), F.get("annee") or {}, F.get("creations")
    if not b: return None
    secs = [s for s in F.get("secteurs", [])]
    reste = b["n"] - sum(s["cumul_12_mois"] for s in secs)
    tons = ["#17202E", "#46536A"]
    seg_f = [{"n": s["cumul_12_mois"], "col": tons[i % 2], "label": f'{s["secteur"]} : {fr(s["cumul_12_mois"])}'} for i, s in enumerate(secs)]
    if reste > 0: seg_f.append({"n": reste, "col": tons[len(secs) % 2], "label": f"Autres secteurs : {fr(reste)}"})
    p50 = part_50(D, TD)
    an0 = f"{AN}-01-01"
    plans = [e for e in D["data"].get("evenements", []) if e.get("source") != "BODACC" and (e.get("date") or "") >= an0]
    ents = emplois_par_entreprise(plans)
    tot_e = sum(x["n"] for x in ents)
    par_nat = {}
    for x in ents: par_nat[x["nature"]] = par_nat.get(x["nature"], 0) + x["n"]
    seg_e = [{"n": x["n"], "col": COUL_NAT[x["nature"]], "label": f'{x["nom"]} : {fr(x["n"])}', "titre": f'{x["nom"]} : {fr(x["n"])} ({x["nature"]}, {x["src"]}, {mois_long(x["date"])})'} for x in ents]
    top5 = sum(x["n"] for x in ents[:5])
    import echelle                                  # version « à l'échelle » (défilement horizontal, 1 pixel = 1 unité)
    return echelle.page(D, F, AN, ents, p50, par_nat, round(100 * top5 / max(1, tot_e)))
    loc, vus = [], set()
    for e in sorted([e for e in plans if (e.get("poids_local") or {}).get("part_commune_pct", 0) >= 10 and e["poids_local"]["effectif_commune"] <= 2500
                     and e["poids_local"]["part_commune_pct"] <= 100], key=lambda e: -e["poids_local"]["part_commune_pct"]):
        p = e["poids_local"]
        if p["insee"] in vus: continue
        vus.add(p["insee"])
        loc.append({"nom": e["entreprise"], "commune": p["commune"], "dep": e.get("dep"), "n": e["emplois_min"], "eff": p["effectif_commune"],
                    "pct": p["part_commune_pct"], "annee": p["annee"], "src": e["source"], "date": e["date"]})
        if len(loc) == 4: break
    data = {"faillites": seg_f, "p50": p50["pour_mille"] if p50 else None, "emplois": seg_e,
            "local": [{"nom": x["nom"], "n": x["n"], "eff": x["eff"]} for x in loc]}
    titre = f"Un an de faillites en France, carré par carré"
    desc = (f"{fr(b['n'])} entreprises ont fait défaillance en un an : une infographie à faire défiler, un carré par entreprise, puis un carré par emploi "
            f"dont la suppression est annoncée en {AN}.")
    ratio_crea = round(cr["cumul_12_mois"] / b["n"]) if cr else None
    corps = (f"<style>{IG_CSS}</style><div class=\"ig\"><section class=\"ig-intro\"><h1>Un an de faillites, carré par carré</h1>"
             f'<p class="chapo">{S.de_mois(b["debut"]).capitalize().replace("D’", "D’")} à {mois_long(b["mois"])}, <b>{fr(b["n"])} entreprises</b> ont fait défaillance en France '
             f'({pct(b["var"])} en un an, selon la Banque de France). Chaque carré ci-dessous est l\'une d\'elles. Faites défiler.</p></section>'
             '<div class="ig-wrap"><div class="ig-compteur" aria-hidden="true"><span><b id="ig-n">0</b> entreprises</span><span id="ig-sec"></span></div>'
             f'<div class="ig-grille" id="g-faillites" role="img" aria-label="{fr(b["n"])} carrés, un par défaillance d\'entreprise, regroupés par secteur d\'activité"></div></div>'
             f'<p>Voilà {fr(b["n"])} entreprises. Les plus touchées : la construction et le commerce, puis l\'hébergement et la restauration. '
             "La plupart sont de très petites structures : un artisan, un commerce, un restaurant.</p>")
    if p50:
        corps += (f"<h2>Une sur {round(1000 / p50['pour_mille'])} avait 50 salariés ou plus</h2>"
                  f'<p>Sur 1 000 jugements d\'ouverture de procédure collective publiés au BODACC, environ <b>{str(p50["pour_mille"]).replace(".", ",")}</b> concernent une entreprise '
                  f'de 50 salariés ou plus (en jaune). Peu nombreuses, elles pèsent lourd : {periode(p50["mois"][0], p50["mois"][-1])}, '
                  f'{fr(p50["n50"])} entreprises de cette taille sont entrées en procédure, avec au moins {fr(p50["salaries"])} salariés.</p>'
                  '<div class="ig-wrap"><div class="ig-grille" id="g-50" role="img" aria-label="1 000 carrés, dont ceux en jaune représentent les entreprises de 50 salariés et plus"></div></div>')
    corps += (f"<h2>{fr(tot_e)} emplois annoncés en {AN}</h2>"
              f"<p>Depuis le 1er janvier, au moins <b>{fr(tot_e)} emplois</b> ont été annoncés comme supprimés ou menacés, dans {fr(len(ents))} entreprises "
              f"(liste CGT, presse ; chiffres annoncés). Un carré = un emploi. Les cinq plus gros plans en font {round(100 * top5 / max(1, tot_e))} %.</p>"
              '<div class="ig-leg">' + "".join(f'<span><i style="background:{COUL_NAT[n]}"></i>{n} : {fr(par_nat.get(n, 0))}</span>' for n in S.NATURES) + "</div>"
              '<div class="ig-wrap"><div class="ig-grille" id="g-emplois" role="img" aria-label="Un carré par emploi annoncé comme supprimé ou menacé, regroupés par entreprise"></div></div>'
              "<p>Tous ces emplois ne disparaîtront pas : les départs volontaires ne sont pas des licenciements, et une entreprise en redressement peut être reprise. "
              "Mais chaque bloc est une annonce publique, avec sa source.</p>")
    if loc:
        corps += "<h2>Vu depuis la commune</h2><p>Un plan de 150 postes passe inaperçu à l'échelle du pays. Pas dans une petite commune.</p>"
        for k, x in enumerate(loc):
            corps += (f'<h3>{esc(x["commune"])}{" (" + esc(x["dep"]) + ")" if x.get("dep") else ""} : {str(x["pct"]).replace(".", ",")} % de l\'emploi privé</h3>'
                      f'<p>{fr(x["eff"])} salariés travaillent dans le secteur privé à {esc(x["commune"])} (URSSAF, {x["annee"]}). '
                      f'Chez {esc(x["nom"])}, <b>{fr(x["n"])} emplois</b> sont annoncés comme supprimés ou menacés (en rouge ; source : {esc(x["src"])}, {mois_long(x["date"])}).</p>'
                      f'<div class="ig-wrap"><div class="ig-grille" id="g-local-{k}" role="img" aria-label="{fr(x["eff"])} carrés pour les salariés du privé de {esc(x["commune"])}, dont {fr(x["n"])} en rouge"></div></div>')
    if cr:
        w = max(2, round(100 * b["n"] / cr["cumul_12_mois"], 1))
        corps += (f"<h2>Et pendant ce temps, {fr(cr['cumul_12_mois'])} créations</h2>"
                  f"<p>Sur les douze mois à fin {mois_long(cr['dernier_mois'])}, il s'est créé environ <b>{ratio_crea} fois plus</b> d'entreprises qu'il n'en a fait défaillance. "
                  f"Les dessiner toutes demanderait de faire défiler {ratio_crea} fois plus longtemps. Mais {str(cr['dont_micro_pct']).replace('.', ',')} % sont des micro-entreprises, "
                  "pour la plupart sans salarié : une création ne compense pas un plan social, et ce site ne calcule pas de « solde » d'emplois.</p>"
                  f'<div class="ig-barres" role="img" aria-label="Comparaison des créations et des défaillances sur douze mois"><div style="width:100%">Créations : {fr(cr["cumul_12_mois"])}</div>'
                  f'<div style="width:{w}%">Défaillances : {fr(b["n"])}</div></div>')
    corps += (f"<h2>Les sources</h2><p>Défaillances : Banque de France (série INSEE {esc(D['officiel']['defaillances']['idbank'])}), cumul sur douze mois à fin {mois_long(b['mois'])}, "
              "réparties par secteur. Entreprises de 50 salariés et plus : jugements publiés au BODACC rapprochés des tranches d'effectif INSEE. "
              "Emplois : liste CGT des plans de licenciement et presse, chiffres annoncés, dédoublonnés par entreprise. Emploi local : URSSAF. Créations : INSEE.</p>"
              f'<p><a class="ig-cta" href="{S.BASE}/explorer/">Explorer et filtrer les données</a><a class="ig-cta" href="{S.BASE}/methode/">Méthode et limites</a></p></div>'
              f'<script type="application/json" id="ig-data">{json.dumps(data, ensure_ascii=False).replace("</", "<\\/")}</script><script>{IG_JS}</script>')
    graph = [S.site_ld(), {"@type": "WebPage", "name": titre, "url": S.BASE_URL + "/en-un-an/", "inLanguage": "fr-FR", "dateModified": dt.date.today().isoformat(),
                           "isPartOf": {"@id": S.BASE_URL + "/#site"}, "description": desc}]
    S.ecrire("en-un-an/index.html", S.page(titre, desc, "en-un-an/", corps, graph, "en-un-an/"))
    return S.BASE_URL + "/en-un-an/"

# --------------------------------------------------------------------------------------------------------- explorateur
def explorer_json(D):
    lien = {"siren_source": "sûr", "siret_commune": "sûr", "nom+dep": "probable", "nom_seul": "indicatif"}
    src = lambda e: "BODACC" if e["source"] == "BODACC" else "CGT" if str(e["source"]).startswith("CGT") else "Accords" if e["source"] == "Accords d'entreprise" else "Presse"
    rows = []
    import pages_fiche
    FU = {s: pages_fiche.url_fiche(s, pages_fiche.nom_de(v)) for s, v in pages_fiche.groupes(D["data"].get("evenements", [])).items()}
    for e in D["data"].get("evenements", []):
        c, pl, dp, pr = e.get("comptes") or {}, e.get("poids_local") or {}, e.get("dependance_publique") or {}, e.get("proximite") or {}
        fi = bool(e.get("fiable"))
        rows.append({"id": e.get("id"), "d": e.get("date"), "t": e.get("type"), "s": src(e), "sl": e.get("source"), "e": e.get("entreprise"), "siren": e.get("siren"),
                     "f": ("sûr (vérifié à la main)" if e.get("valide_humain") else ", ".join(x for x in (lien.get(e.get("lien"), ""), "confirmé à la relecture" if e.get("verif_ident") == "confirmé" else "") if x)), "c": e.get("commune"), "dep": e.get("dep"), "reg": S.REGIONS.get(e.get("dep") or "", ""),
                     "sec": S.secteur(e.get("naf")) or "", "cat": e.get("categorie") or "", "em": e.get("emplois_min"), "ex": e.get("emplois_max"),
                     "p": "annoncé" if e.get("emplois_precision") == "annoncé" else ("tranche" if e.get("emplois_min") is not None else ""),
                     "nat": S.nature_emplois(e), "u": e.get("url"),
                     "rnd": c.get("resultat_net") if c and e.get("lien") != "nom_seul" else None, "acd": c.get("derniere_annee") if c and e.get("lien") != "nom_seul" else None,
                     "pbt": (e.get("procedure_bodacc") or {}).get("type"), "pbd": (e.get("procedure_bodacc") or {}).get("date"),
                     "pbp": (e.get("procedure_bodacc") or {}).get("date_publication"), "pbu": (e.get("procedure_bodacc") or {}).get("url"), "cd": e.get("commune_deduite") or None, "fp": S.empreinte(e.get("id")), "ev": e.get("evenement_id"), "dn": S.DEPS.get(e.get("dep") or "", ""),
                     "pa": e.get("emplois_min") if e.get("emplois_precision") == "annoncé" else None,
                     "efm": (e.get("emplois_min") if e.get("source") == "BODACC" else (e.get("effectif_entreprise") or [None, None])[0]),
                     "efx": (e.get("emplois_max") if e.get("source") == "BODACC" else (e.get("effectif_entreprise") or [None, None])[1]), "xt": S.exclu_totaux(e) or None,
                     "acc": [[a["date"], a["libelle"], a["titre"][:160], a["url"], a["cat"]] for a in (e.get("accords") or []) if not (e.get("source") == "Accords d'entreprise" and a["url"] == e.get("url"))] or None, "v1": e.get("vu_le"),
                     "fu": FU.get(e.get("siren")) if (e.get("source") == "BODACC" or e.get("lien") in ("siren_source", "siret_commune", "nom+dep")) else None,
                     "mob": [[a["date"], a["titre"], a.get("source"), a.get("url"), a.get("commune")] for a in e.get("mobilisations") or []] or None,
                     "dc": [[x["date"], x["texte"], x.get("url")] for x in e.get("deces_travail") or []] or None, "ns": 1 + len(e.get("sources") or []),
                     "src": [[x.get("source"), x.get("url"), x.get("date")] for x in (e.get("sources") or [])] or None,
                     "accu": " | ".join(a["date"] + " " + a["libelle"] + " " + a["url"] for a in e.get("accords") or []) or None,
                     "mobu": " | ".join(a["date"] + " " + (a.get("url") or "") for a in e.get("mobilisations") or []) or None,
                     "srcu": " | ".join(x.get("url") or "" for x in (e.get("sources") or [])) or None, "det": (e.get("detail") or "")[:220],
                     "rn": c.get("resultat_net") if fi else None, "ac": c.get("derniere_annee") if fi else None,
                     "ben": (bool(c.get("profitable") and e.get("type") in ("plan social", "fermeture")) if fi and c.get("profitable") is not None else None),
                     "aide": pr.get("montant") if fi and pr else None, "aide_n": pr.get("n") if fi and pr else None,
                     "at": types_aide(e),
                     "cp": dp.get("part_pct"), "pl": pl.get("part_commune_pct"), "en": e.get("emplois_note"), "dpub": e.get("date_publication") if e.get("source") == "BODACC" else None,
                     "se": bool(e.get("sans_entreprise") or (e.get("entreprise") and e.get("entreprise") == e.get("titre")) or S.exclu_totaux(e)), "ia": bool(e.get("ident_ia") or e.get("commune_ia")), "dp": e.get("date_precision"), "g": (e.get("groupe") or {}).get("nom"), "gp": (e.get("groupe") or {}).get("pays"),
                     "gs": (e.get("groupe") or {}).get("source"),
                     "sd": "; ".join(f"{x['montant']:,} € ({x['date'][:7]}{', ' + x['nom'] if x['niveau'] == 'groupe' else ''})".replace(",", " ") for x in e.get("sanction_delais") or []) or None,
                     "bb": (bool(e["bonne_boite"].get("fort")) if e.get("bonne_boite") else None),
                     "sdm": sum(x["montant"] for x in e.get("sanction_delais") or []) or None,
                     "lbmin": (lambda l: int(re.sub(r"\D", "", (re.search(r">\s*=\s*([\d\s]+)", l["depenses"]) or re.search(r"()", ""))[1] or "0") or 0) if l else None)(e.get("lobbying")),
                     "lbt": (lambda l: l["depenses"].replace("> = ", "").replace(" euros", " €").replace(" et < ", " – ").replace("< ", "moins de ") if l else None)(e.get("lobbying")),
                     "lb": (lambda l: f"{l['depenses']} en {l['annee']}" + (f" — « {l['objets'][0][:100]} »" if l.get("objets") else "") if l else None)(e.get("lobbying")),
                     "lbg": (lambda l: f"{l['nom']} : {l['depenses']} en {l['annee']}" if l else None)(e.get("lobbying_groupe")),
                     "vu": (lambda v: f"{v['commune']} : {v['avant']:.0f} ({v['annee_avant']}) → {v['apres']:.0f} ({v['annee_apres']})" if v else None)(e.get("verif_urssaf")), "siret": e.get("siret"), "dl": (S.delocalisation(e) or {}).get("pays", "") if S.delocalisation(e) else None, "plc": pl.get("commune"), "su": (e.get("suite") or {}).get("issue")})
    S.ecrire("explorer.json", json.dumps({"maj": D["data"].get("maj"), "n": len(rows), "lignes": rows}, ensure_ascii=False, separators=(",", ":")))
    return rows

EX_CSS = """
main{max-width:1240px}.fx{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:10px 14px;background:#F7F8F9;border:1px solid #C9CFD6;padding:14px;margin:14px 0}
.fx label{display:block;font-size:14px;font-weight:600}.fx input[type=text],.fx input[type=number],.fx input[type=date],.fx select{width:100%;font:15px Barlow,sans-serif;padding:6px 8px;border:1px solid #C9CFD6;background:#fff;color:#17202E;border-radius:3px;margin-top:3px}
.fx fieldset{border:0;padding:0;margin:0}.fx legend{font-size:14px;font-weight:600;padding:0}.fx .cases label{font-weight:400;display:inline-flex;gap:5px;align-items:center;margin:3px 10px 0 0}
.fx .larges{grid-column:1/-1;display:flex;flex-wrap:wrap;gap:8px 18px;align-items:center}details.larges{display:block}details.larges[open]{display:flex}details.larges summary{cursor:pointer;font-weight:600;width:100%}details.larges label{margin-right:18px}@media (max-width:640px){table thead th:nth-child(5),table thead th:nth-child(7),table thead th:nth-child(8),#corps tr.lig>td:nth-child(5),#corps tr.lig>td:nth-child(7),#corps tr.lig>td:nth-child(8){display:none}}
.btn{font:600 15px Barlow,sans-serif;padding:8px 14px;border:1px solid #17202E;background:#17202E;color:#fff;cursor:pointer;border-radius:3px}.btn.sec{background:#fff;color:#17202E}
.resume{font-size:17px;margin:10px 0}.resume b{font:700 1.4rem "Barlow Condensed",sans-serif}
th button{all:unset;cursor:pointer;font-weight:600}th button:focus-visible{outline:3px solid #E8B21E}th[aria-sort=ascending] button::after{content:" ▲"}th[aria-sort=descending] button::after{content:" ▼"}
td .meta{display:block}.tag{display:inline-block;font-size:12px;font-weight:600;padding:0 6px;border-radius:3px;color:#fff;background:#5B6573;margin:2px 4px 0 0}
#hist{margin:6px 0 2px}
.chip{display:inline-block;font-size:12px;font-weight:600;line-height:1.5;padding:0 7px;border-radius:10px;margin:2px 3px 0 0;color:#fff;white-space:nowrap}
.c-fin{background:#9A2B1A}.c-pub{background:#2F6FA8}.c-lob{background:#6B4C9A}.c-amd{background:#C26A12}.c-ter{background:#2E7D4F}.c-soc{background:#B8361E}.c-emb{background:#13757A}
.c-mob{background:#C2185B}.c-acc{background:#00695C}.k-acc{border-left-color:#00695C}.k-mob{border-left-color:#C2185B}.c-grp{background:#5B6573}.c-inf{background:#E9ECEF;color:#17202E;border:1px solid #C9CFD6}
tr.fort>td:first-child{box-shadow:inset 5px 0 0 #E8B21E}
.neuf{display:block;width:max-content;margin-left:auto;background:#E8B21E;color:#17202E;font:700 11px Barlow,sans-serif;text-transform:uppercase;border-radius:3px;padding:0 5px}#memo{background:#EDEFF2;padding:6px 10px;font-size:14px}#memo button{font:600 13px Barlow,sans-serif;background:none;border:0;text-decoration:underline;cursor:pointer;padding:0 4px}.vf{font-size:12px;font-weight:600;margin-left:6px}.nsrc{display:inline-block;margin-left:6px;font-size:12px;font-weight:600;padding:0 6px;border:1px solid #17202E;border-radius:10px;white-space:nowrap}tr.ouvrable{cursor:pointer}tr.ouvrable:hover>td{background:#F4F6F8}tr.fort.ouvrable:hover>td{background:#FFF6D6}
tr.ouvrable:focus-visible{outline:3px solid #E8B21E;outline-offset:-3px}.fleche{display:inline-block;margin-left:4px;color:#5B6573;transition:transform .15s}tr.ouvert .fleche{transform:rotate(180deg)}
tr.detail>td{background:#F7F8F9;padding:12px 14px 14px}
.fiche{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:10px}
.case{background:#fff;border:1px solid #DDE1E6;border-left:5px solid #5B6573;padding:8px 12px}.case .lab{font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:.04em;color:#5B6573}
.case .val{font:700 1.35rem/1.15 "Barlow Condensed",sans-serif;margin:3px 0 4px;word-break:break-word}.case .det{font-size:13px;color:#3D4654;line-height:1.4}
.k-fin{border-left-color:#9A2B1A}.k-pub{border-left-color:#2F6FA8}.k-lob{border-left-color:#6B4C9A}.k-amd{border-left-color:#C26A12}.k-ter{border-left-color:#2E7D4F}
.k-soc{border-left-color:#B8361E}.k-emb{border-left-color:#13757A}.k-grp{border-left-color:#5B6573}.k-inf{border-left-color:#C9CFD6;background:#FBFBFC}
.src{font-size:13px;color:#3D4654;margin:10px 0 0;max-width:110ch}.btn-fiche{display:inline-block;background:#17202E;color:#fff;font:600 15px Barlow,sans-serif;padding:9px 16px;margin:2px 0 10px;text-decoration:none;border-bottom:3px solid #B8361E}.btn-fiche:hover,.btn-fiche:focus-visible{background:#B8361E;color:#fff}
@media (prefers-reduced-motion:reduce){.fleche{transition:none}}
td.v{font-weight:600;font-size:14px}.v-fin,.v-pub,.v-amd,.v-ter,.v-soc,.v-emb{white-space:nowrap!important}td.vide{background:transparent}
.v-fin{background:#F6E1DD;color:#7A2214}.v-pub{background:#DCE8F4;color:#1F4E79}.v-lob{background:#E9E1F3;color:#4B2E78}.v-amd{background:#F7E4CF;color:#8A4A0B}
.v-ter{background:#DDEFE3;color:#1E5C38}.v-soc{background:#F6DCD7;color:#8F2716}.v-emb{background:#D7EEEE;color:#0E5559}.v-grp{background:#EDEFF2;color:#17202E;font-weight:400}
th.h-fin{box-shadow:inset 0 -3px 0 #9A2B1A}th.h-pub{box-shadow:inset 0 -3px 0 #2F6FA8}th.h-lob{box-shadow:inset 0 -3px 0 #6B4C9A}th.h-amd{box-shadow:inset 0 -3px 0 #C26A12}
th.h-ter{box-shadow:inset 0 -3px 0 #2E7D4F}th.h-soc{box-shadow:inset 0 -3px 0 #B8361E}th.h-emb{box-shadow:inset 0 -3px 0 #13757A}th.h-grp{box-shadow:inset 0 -3px 0 #5B6573}
tr.detail td{background:#F7F8F9;font-size:14px}tr.detail ul{margin:4px 0;padding-left:18px}
.voir{font:600 12px Barlow,sans-serif;background:none;border:1px solid #C9CFD6;border-radius:3px;padding:0 6px;cursor:pointer;color:#17202E}
.legende-rec{display:flex;flex-wrap:wrap;gap:4px 10px;font-size:13px;margin:6px 0}
button.chip{border:2px solid transparent;cursor:pointer;font-family:inherit;font-size:13px;padding:2px 9px;line-height:1.4}button.chip .nb{font-weight:400;opacity:.85}.c-deux{background:#E8B21E;color:#17202E}.filtres-rec.actif button.chip[aria-pressed=false]{opacity:.45}button.chip[aria-pressed=true]{border-color:#17202E;box-shadow:0 0 0 2px #fff inset}button.chip:focus-visible{outline:3px solid #E8B21E;outline-offset:1px}button.chip:hover{filter:brightness(1.12)}
"""

EX_JS = r"""
(function(){
const CREDIT='Plans sociaux et faillites en France, oraclemarin.fr/plans-sociaux, Quentin Closset (quentinclosset@gmail.com)';let L=[],F=[],tri={k:'d',dir:-1},lim=100;const $=id=>document.getElementById(id);
const nf=n=>n==null?'':Math.round(n).toLocaleString('fr-FR');const esc=s=>String(s==null?'':s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const eu=n=>{const v=Math.abs(n),s=n<0?'−':'';return s+(v>=1e9?(v/1e9).toLocaleString('fr-FR',{maximumFractionDigits:1})+' Md€':v>=1e6?(v/1e6).toLocaleString('fr-FR',{maximumFractionDigits:1})+' M€':nf(v)+' €')};
const CHAMPS=['q','t','s','nat','reg','dep','sec','cat','f','d0','d1','emin','dl','lb','sd','bb','se','ben','aide','at','pl','cp','n2','mb','ae'];
function lire(){const o={};CHAMPS.forEach(k=>{const el=$('x-'+k);if(!el)return;if(el.dataset.multi){o[k]=[...el.querySelectorAll('input:checked')].map(i=>i.value)}else if(el.type==='checkbox')o[k]=el.checked;else o[k]=el.value});return o}
function ecrire(o){CHAMPS.forEach(k=>{const el=$('x-'+k);if(!el||o[k]==null)return;if(el.dataset.multi){el.querySelectorAll('input').forEach(i=>i.checked=o[k].includes(i.value))}else if(el.type==='checkbox')el.checked=!!o[k];else el.value=o[k]})}
function versHash(o){const p=new URLSearchParams();for(const[k,v]of Object.entries(o)){if(Array.isArray(v)){if(v.length)p.set(k,v.join('|'))}else if(v===true)p.set(k,'1');else if(v&&v!==false)p.set(k,v)}p.set('tri',tri.k+(tri.dir<0?'-':'+'));return p.toString()}
const LS={get(k){try{return localStorage.getItem(k)}catch(e){return null}},set(k,v){try{localStorage.setItem(k,v)}catch(e){}}};
let derniere=null;try{derniere=sessionStorage.getItem('explorer_avant');if(derniere===null){derniere=LS.get('explorer_vu')||'';sessionStorage.setItem('explorer_avant',derniere)}}catch(e){derniere=''}
addEventListener('pagehide',()=>LS.set('explorer_vu',new Date().toISOString()));
function depuisHash(h){const p=new URLSearchParams(h==null?location.hash.slice(1):h);const o={};p.forEach((v,k)=>{const el=$('x-'+k);if(k==='tri'){tri={k:v.slice(0,-1),dir:v.endsWith('-')?-1:1};return}if(!el)return;o[k]=el.dataset.multi?v.split('|'):el.type==='checkbox'?v==='1':v});return o}
const norm=s=>(s||'').normalize('NFD').replace(/[̀-ͯ]/g,'').toLowerCase();
function filtrer(){const o=lire();const q=norm(o.q);
 F=L.filter(r=>(!q||norm(r.e+' '+r.c+' '+r.det+' '+(r.g||'')).includes(q))&&(!o.t.length||o.t.includes(r.t))&&(!o.s.length||o.s.includes(r.s))&&(!o.nat||r.nat===o.nat)&&(!o.reg||r.reg===o.reg)
  &&(!o.dep||r.dep===o.dep)&&(!o.sec||r.sec===o.sec)&&(!o.cat||r.cat===o.cat)&&(!o.f||r.f===o.f)&&(!o.d0||(r.d&&r.d>=o.d0))&&(!o.d1||(r.d&&r.d<=o.d1))&&(!o.emin||(r.em||0)>=+o.emin)
  &&(!o.dl||r.dl!=null)&&(!o.lb||r.lb)&&(!o.sd||r.sd)&&(!o.bb||r.bb)&&(o.se||!r.se)&&(!o.ben||r.ben)&&(!o.aide||r.aide_n)&&(!o.at||(r.at||[]).includes(o.at))&&(!o.pl||(r.pl||0)>=5)&&(!o.cp||(r.cp||0)>=20)&&(!o.n2||r.nr>=2)&&(!o.mb||r.mob)&&(!o.ae||r.acc||r.s==='Accords'));
 const k=tri.k,d=tri.dir;F.sort((a,b)=>{const x=a[k],y=b[k];if(x==null&&y==null)return 0;if(x==null)return 1;if(y==null)return -1;return(x<y?-1:x>y?1:0)*d});
 history.replaceState(null,'','#'+versHash(o));LS.set('explorer_filtres',versHash(o));lim=100;afficher();pastilles(o)}
const TEST={ben:r=>r.ben,aide:r=>r.aide_n,cp:r=>(r.cp||0)>=20,lb:r=>r.lb,sd:r=>r.sd,pl:r=>(r.pl||0)>=5,dl:r=>r.dl!=null,bb:r=>r.bb,mb:r=>r.mob,ae:r=>r.acc||r.s==='Accords',n2:r=>r.nr>=2};
function pastilles(o){const z=$('pastilles');let actif=0;z.querySelectorAll('button').forEach(b=>{const k=b.dataset.f;b.setAttribute('aria-pressed',String(!!o[k]));if(o[k])actif++;b.querySelector('.nb').textContent=o[k]?'✕':nf(F.filter(TEST[k]).length)});z.classList.toggle('actif',actif>0)}
function resume(){const ann=F.filter(r=>r.p==='annoncé'&&!r.xt),proc=F.filter(r=>r.s==='BODACC');const ents=new Set(F.map(r=>r.siren||norm(r.e)));
 const parN={};const vus={};ann.forEach(r=>{const k=norm(r.e);if(!vus[k]||vus[k].em<r.em)vus[k]=r});Object.values(vus).forEach(r=>parN[r.nat]=(parN[r.nat]||0)+(r.em||0));
 const totA=Object.values(parN).reduce((a,b)=>a+b,0);const sal={};proc.forEach(r=>{if(r.siren)sal[r.siren]=Math.max(sal[r.siren]||0,r.em||0)});
 $('resume').innerHTML=`<b>${nf(F.length)}</b> événements · <b>${nf(ents.size)}</b> entreprises · au moins <b>${nf(totA)}</b> emplois annoncés`+(totA?` (${Object.entries(parN).map(([n,v])=>esc(n)+' : '+nf(v)).join(', ')})`:'')+(proc.length?` · <b>${nf(Object.values(sal).reduce((a,b)=>a+b,0))}</b> salariés d'entreprises entrées en procédure`:'')+((!$('x-d0').value&&!$('x-d1').value)?' <span class="meta">(toutes périodes : liste CGT depuis août 2023, presse depuis janvier 2025, procédures collectives (BODACC) complètes depuis mars 2025 ; choisissez des dates pour comparer avec l\u2019accueil)</span>':'');
 const m={};F.forEach(r=>{if(r.d)m[r.d.slice(0,7)]=(m[r.d.slice(0,7)]||0)+1});const ks=Object.keys(m).sort().slice(-24);
 if(!ks.length){$('hist').innerHTML='';return}const mx=Math.max(...ks.map(k=>m[k]));const W=720,H=70,bw=W/ks.length;
 $('hist').innerHTML=`<svg viewBox="0 0 ${W} ${H+16}" role="img" aria-label="Événements sélectionnés par mois" style="width:100%;max-width:720px;height:auto">`+ks.map((k,i)=>{const h=H*m[k]/mx;return`<rect x="${i*bw+1}" y="${H-h}" width="${bw-2}" height="${h}" fill="#17202E"><title>${k} : ${m[k]}</title></rect>`+(i%3===0?`<text x="${i*bw+bw/2}" y="${H+13}" font-size="10" text-anchor="middle" fill="#5B6573">${k}</text>`:'')}).join('')+'</svg>'}
// recoupements : une pastille par type, couleur par famille ; les « forts » comptent dans le tri et la mise en avant
function recoupements(r){const R=[];const add=(fam,lab,val,det,fort)=>R.push({fam,lab,val,det,fort});
 if(r.ben)add('fin','Bénéficiaire',eu(r.rn),`Dernier exercice publié (${r.ac}) : résultat net positif.`,1);
 if(r.aide_n)add('pub','Aide publique',r.aide?eu(r.aide):`${r.aide_n} aide${r.aide_n>1?'s':''}`,`${r.aide_n} aide${r.aide_n>1?'s':''} (ADEME, France Relance) dans les 24 mois avant l'annonce.`,1);
 if(r.cp>=1)add('pub','Commande publique',`${Math.round(r.cp)} % du CA`,`Part estimée (minimum) du chiffre d'affaires venant de marchés publics.`,r.cp>=20?1:0);
 if(r.lb)add('lob','Lobbying',esc(r.lbt||''),`Déclaré à la HATVP : ${r.lb}`,1);
 if(r.sd)add('amd','Amende fournisseurs',eu(r.sdm),`Amende de la DGCCRF pour retards de paiement : ${r.sd}`,1);
 if(r.pl>=1)add('ter','Poids local',`${String(r.pl).replace('.',',')} %`,`des emplois salariés privés de ${r.plc} (URSSAF).`,r.pl>=5?1:0);
 if(r.vu)add('ter','Vérifié URSSAF',(r.vu.split(' : ')[1]||''),`Emploi du secteur dans la commune : ${r.vu}.`,1);
 if(r.dl!=null)add('soc','Délocalisation',r.dl||'oui','Délocalisation annoncée'+(r.dl?` vers : ${r.dl}.`:'.'),1);
 if(r.mob)add('mob','Mobilisation',`${r.mob.length} article${r.mob.length>1?'s':''}`,'Grève, rassemblement ou débrayage signalé par la presse (via ça brûle) : '+r.mob.map(a=>a[0]+' — '+a[1]).join(' · '),1);
 if(r.dc)add('soc','Décès au travail',r.dc[0][0]||'','Accident mortel du travail signalé par la presse (via ça brûle) : '+r.dc.map(x=>x[1]).join(' · '),1);
 if(r.acc)add('acc','Accord d\u2019entreprise',r.acc.length>1?r.acc.length+' accords':r.acc[0][1],'Accord(s) lié(s) à l\u2019emploi déposé(s) par l\u2019entreprise (Légifrance) : '+r.acc.map(a=>a[0]+' — '+a[1]+' : « '+a[2]+' »').join(' · '),1);
 if(r.pbt)add('fin','Procédure collective',r.pbt,`Même entreprise au BODACC : ${r.pbt}, jugement du ${r.pbd}`+(r.pbp?`, publié le ${r.pbp}`:'')+'.',1);
 if(!r.ben&&r.rnd!=null)add('inf','Dernier exercice publié',eu(r.rnd),`Résultat net ${r.acd} (comptes publiés, éventuellement postérieurs à l\u2019annonce).`,0);
 if(r.bb)add('emb','Recrute ?','oui',"France Travail estime, par algorithme, que l'établissement a un fort potentiel d'embauche (La Bonne Boîte).",1);
 if(r.g&&norm(r.g).slice(0,8)!==norm(r.e).slice(0,8))add('grp','Groupe',esc(r.g),`Société mère${r.gp?' ('+r.gp+')':''}, source ${r.gs}.`,0);
 if(r.lbg)add('inf','Lobbying du groupe','—',`${r.lbg} — sans lien établi avec cette société.`,0);
 if(r.su&&r.su!=='en cours')add('inf','Suite de la procédure',r.su,'Dernière décision publiée au BODACC.',0);
 if(r.en)add('inf','Effectif relu','—','Effectif relu dans le texte de la source : '+r.en,0);
 return R}
function ligne(r,i){const R=recoupements(r);
 const emp=r.em==null?'':r.p==='annoncé'?nf(r.em):nf(r.em)+'–'+nf(r.ex);
 const MO=['janv.','févr.','mars','avr.','mai','juin','juil.','août','sept.','oct.','nov.','déc.'];const neuf=derniere&&r.v1&&r.v1>derniere?'<span class="neuf">nouveau</span>':'';const dte=r.dp==='mois'&&r.d?MO[+r.d.slice(5,7)-1]+' '+r.d.slice(0,4):(r.d||'');const pub=r.dpub&&r.dpub.slice(0,10)!==r.d?`<span class="meta">jugé ; publié le ${esc(r.dpub.slice(0,10))}</span>`:'';
 const chips=R.filter(x=>x.fam!=='inf').map(x=>`<span class="chip c-${x.fam}">${esc(x.lab)}</span>`).join('');
 const ouvrable=R.length||r.det||r.src;
 return`<tr class="lig${r.nr>=2?' fort':''}${ouvrable?' ouvrable':''}" data-i="${i}"${ouvrable?` tabindex="0" aria-expanded="false" aria-controls="d${i}"`:''}><td class="n">${neuf}${esc(dte)}${pub}</td><td><a href="${esc(r.u)}" rel="noopener" target="_blank">${esc(r.e)}</a>${r.fu?` <a class="vf" href="${esc(r.fu)}">fiche</a>`:''}${r.ns>1?`<span class="nsrc">${r.ns} sources</span>`:''}${r.f?`<span class="meta">rapprochement ${esc(r.f)}${r.ia?' (nom ou commune lus par IA)':''}</span>`:''}</td><td>${esc(r.t)}</td><td>${esc(r.c||r.dn||'')} ${r.dep?'('+esc(r.dep)+')':''}</td><td>${esc(r.sec)}</td><td class="n">${emp}</td><td>${esc(r.p==='annoncé'||r.s!=='BODACC'?r.nat:'')}</td><td class="meta">${esc(r.s)}</td><td>${chips}${ouvrable?'<span class="fleche" aria-hidden="true">▾</span>':''}</td></tr>`
  +(ouvrable?`<tr class="detail" id="d${i}" hidden><td colspan="9">${r.fu?`<a class="btn-fiche" href="${esc(r.fu)}">Voir la fiche de ${esc(r.e)} →</a>`:''}<div class="fiche">${R.map(x=>`<div class="case k-${x.fam}"><div class="lab">${esc(x.lab)}</div><div class="val">${x.val}</div><div class="det">${esc(x.det)}</div></div>`).join('')}</div>`
    +`${r.det?`<p class="src"><b>Source</b> (${esc(r.sl||r.s)}) : ${esc(r.det)} <a href="${esc(r.u)}" target="_blank" rel="noopener">lire</a></p>`:''}${r.acc?`<p class="src"><b>Accords d\u2019entreprise</b> (Légifrance) : ${r.acc.map(a=>`<a href="${esc(a[3])}" target="_blank" rel="noopener">${esc(a[0])} · ${esc(a[1])}</a>`).join(' — ')}</p>`:''}${r.mob?`<p class="src"><b>Mobilisations</b> (via <a href="/cabrule/">ça brûle</a>) : ${r.mob.map(a=>`<a href="${esc(a[3])}" target="_blank" rel="noopener">${esc(a[0])} · ${esc(a[1])}</a>`).join(' — ')}</p>`:''}${r.src?`<p class="src"><b>Autres sources</b> : ${r.src.map(x=>`<a href="${esc(x[1])}" target="_blank" rel="noopener">${esc(x[0])}${x[2]?' ('+esc(String(x[2]).slice(0,10))+')':''}</a>`).join(' · ')}</p>`:''}</td></tr>`:'')}
function basculer(tr){const d=document.getElementById(tr.getAttribute('aria-controls'));if(!d)return;const o=d.hidden;d.hidden=!o;tr.setAttribute('aria-expanded',String(o));tr.classList.toggle('ouvert',o)}
function afficher(){resume();$('corps').innerHTML=F.slice(0,lim).map((r,i)=>ligne(r,i)).join('')||'<tr><td colspan="9">Aucun événement pour ces filtres.</td></tr>';
 $('plus').hidden=F.length<=lim;$('plus').textContent=`Afficher 100 de plus (${nf(F.length-lim)} restants)`;
 document.querySelectorAll('th[data-k]').forEach(th=>th.setAttribute('aria-sort',th.dataset.k===tri.k?(tri.dir<0?'descending':'ascending'):'none'))}
function csv(){const cols=['ev','d','dpub','dp','t','s','sl','e','siren','siret','g','gp','dl','lb','lbg','sd','bb','vu','f','c','dep','reg','sec','cat','pa','efm','efx','nat','rn','ac','ben','aide','cp','pl','su','u','srcu','mobu','accu','rnd','acd','pbt','pbd','pbp','fp','cr'];
 const ent=['evenement_id','date','date_publication_bodacc','precision_date','type','source','source_detail','entreprise','siren','siret_etablissement','groupe','pays_groupe','delocalisation_pays','lobbying_hatvp','lobbying_groupe','amende_retards_paiement','fort_potentiel_embauche','verification_urssaf','fiabilite_rapprochement','commune','departement','region','secteur','categorie','postes_annonces','effectif_entreprise_min','effectif_entreprise_max','nature_emplois','resultat_net','annee_comptes','benefice_et_plan','aides_24_mois','part_commande_publique_pct','part_emploi_commune_pct','suite','url','autres_sources','mobilisations','accords_entreprise','resultat_net_dernier_exercice','annee_dernier_exercice','procedure_bodacc_type','procedure_bodacc_date_jugement','procedure_bodacc_date_publication','empreinte','credit'];
 F.forEach(r=>r.cr=CREDIT);const q=v=>{v=v==null?'':String(v);return/[",\n]/.test(v)?'"'+v.replace(/"/g,'""')+'"':v};
 const t='﻿'+ent.join(',')+'\n'+F.map(r=>cols.map(c=>q(r[c])).join(',')).join('\n');const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([t],{type:'text/csv'}));a.download='selection-plans-sociaux.csv';a.click()}
function remplir(id,vals){const s=$(id);[...new Set(vals.filter(Boolean))].sort((a,b)=>a.localeCompare(b,'fr')).forEach(v=>{const o=document.createElement('option');o.value=o.textContent=v;s.appendChild(o)})}
fetch('../explorer.json?v='+Date.now()).then(r=>r.json()).then(d=>{L=d.lignes;L.forEach(r=>{r.nr=recoupements(r).filter(x=>x.fort).length});remplir('x-reg',L.map(r=>r.reg));remplir('x-dep',L.map(r=>r.dep));fetch('../departements-noms.json').then(r=>r.json()).then(N=>{document.querySelectorAll('#x-dep option').forEach(o=>{if(o.value&&N[o.value])o.textContent=o.value+' · '+N[o.value]})}).catch(()=>{});remplir('x-sec',L.map(r=>r.sec));remplir('x-cat',L.map(r=>r.cat));
 const memo=!location.hash.slice(1)&&LS.get('explorer_filtres');ecrire(depuisHash(memo||null));if(memo&&memo.replace(/(^|&)tri=[^&]*/,'')){$('memo').hidden=false}if([...document.querySelectorAll('#plus-filtres input')].some(i=>i.checked))$('plus-filtres').open=true;$('maj').textContent=new Date(d.maj).toLocaleString('fr-FR',{dateStyle:'long',timeStyle:'short'});
 document.querySelector('.fx').addEventListener('input',filtrer);document.querySelector('.fx').addEventListener('change',filtrer);filtrer()});
document.querySelectorAll('th[data-k] button').forEach(b=>b.addEventListener('click',()=>{const k=b.parentNode.dataset.k;tri=tri.k===k?{k,dir:-tri.dir}:{k,dir:k==='d'||k==='em'||k==='nr'?-1:1};filtrer()}));
$('plus').addEventListener('click',()=>{lim+=100;afficher()});
addEventListener('hashchange',()=>{if(!L||!L.length)return;const h=location.hash.slice(1);if(h===versHash(lire()))return;   // lien ouvert ou modifié dans un onglet déjà chargé
 CHAMPS.forEach(k=>{const el=$('x-'+k);if(!el)return;if(el.dataset.multi)el.querySelectorAll('input').forEach(i=>i.checked=false);else if(el.type==='checkbox')el.checked=false;else el.value=''});
 ecrire(depuisHash(h));filtrer()});
$('pastilles').addEventListener('click',ev=>{const b=ev.target.closest('button[data-f]');if(!b)return;const c=$('x-'+b.dataset.f);c.checked=!c.checked;filtrer()});
$('corps').addEventListener('click',ev=>{if(ev.target.closest('a'))return;const tr=ev.target.closest('tr.ouvrable');if(tr)basculer(tr)});
$('corps').addEventListener('keydown',ev=>{if((ev.key==='Enter'||ev.key===' ')&&ev.target.matches('tr.ouvrable')){ev.preventDefault();basculer(ev.target)}});
$('dl').addEventListener('click',csv);
fetch('../etat.json?v='+Date.now()).then(r=>r.json()).then(e=>{const c=e.couverture||{};$('couv').innerHTML=`<b>Couverture</b> : procédures collectives (BODACC, entreprises de 50 salariés et plus) depuis le ${esc(c.bodacc_historique_depuis)} ; presse en continu depuis le ${esc(c.presse_depuis)} ; liste CGT : dernière édition publiée par la CGT le ${esc(c.cgt_edition)}.`}).catch(()=>{});
$('memo-raz').addEventListener('click',()=>$('raz').click());
$('raz').addEventListener('click',()=>{history.replaceState(null,'',location.pathname);$('memo').hidden=true;document.querySelector('.fx').reset();filtrer()});
$('lien').addEventListener('click',()=>{navigator.clipboard&&navigator.clipboard.writeText(location.href).then(()=>{$('lien').textContent='Lien copié'})});
})();
"""

def p_explorer(D, AN):
    rows = explorer_json(D)
    titre = "Explorer les plans sociaux et les faillites"
    desc = "Filtrez vous-même les procédures collectives, plans sociaux et fermetures : région, secteur, taille, période, nature des emplois, aides, bénéfices. Export CSV et lien partageable."
    types = ["liquidation", "redressement", "sauvegarde", "plan social", "départs volontaires", "fermeture"]
    corps = (f"<style>{EX_CSS}</style><h1>Explorer les données</h1>"
             f'<p class="chapo">{fr(len(rows))} événements : procédures collectives des entreprises de 50 salariés et plus (BODACC), plans de licenciement et fermetures annoncés '
             '(liste CGT, presse). Combinez les filtres, triez en cliquant sur les en-têtes, puis partagez le lien ou téléchargez la sélection.</p>'
             '<p class="meta">Données du <span id="maj"></span>. Les effectifs sont des chiffres annoncés ou des tranches INSEE ; la fiabilité du rapprochement de chaque entreprise est indiquée. '
             f'<a href="{S.BASE}/methode/">Méthode et limites</a>.</p>'
             '<p class="meta" id="couv" style="background:#FFF8E1;border-left:4px solid #E8B21E;padding:6px 10px"></p>'
             '<form class="fx" onsubmit="return false" aria-label="Filtres">'
             '<div><label for="x-q">Recherche</label><input type="text" id="x-q" placeholder="Entreprise, groupe, commune, mot"></div>'
             '<fieldset><legend>Type</legend><div class="cases" id="x-t" data-multi="1">' + "".join(f'<label><input type="checkbox" value="{t}">{t}</label>' for t in types) + '</div></fieldset>'
             '<fieldset><legend>Source</legend><div class="cases" id="x-s" data-multi="1">' + "".join(f'<label><input type="checkbox" value="{s}">{s}</label>' for s in ("BODACC", "CGT", "Presse", "Accords")) + '</div></fieldset>'
             '<div><label for="x-nat">Nature des emplois</label><select id="x-nat"><option value="">Toutes</option>' + "".join(f"<option>{n}</option>" for n in S.NATURES) + '</select></div>'
             '<div><label for="x-at">Aide publique (24 mois avant l’annonce)</label><select id="x-at"><option value="">Tous</option><option>ADEME</option><option>PIA / France 2030 (ADEME)</option><option>Marchés publics</option><option>Aide de minimis (sans date)</option></select></div>'
             '<div><label for="x-reg">Région</label><select id="x-reg"><option value="">Toutes</option></select></div>'
             '<div><label for="x-dep">Département</label><select id="x-dep"><option value="">Tous</option></select></div>'
             '<div><label for="x-sec">Secteur</label><select id="x-sec"><option value="">Tous</option></select></div>'
             '<div><label for="x-cat">Taille d\'entreprise</label><select id="x-cat"><option value="">Toutes</option></select></div>'
             '<div><label for="x-f">Fiabilité du rapprochement</label><select id="x-f"><option value="">Toutes</option><option value="sûr">sûr (SIREN fourni)</option>'
             '<option value="probable">probable</option><option value="indicatif">indicatif</option></select></div>'
             '<div><label for="x-d0">Du</label><input type="date" id="x-d0"></div><div><label for="x-d1">Au</label><input type="date" id="x-d1"></div>'
             '<div><label for="x-emin">Effectif minimum</label><input type="number" id="x-emin" min="0" step="10"></div>'
             '<div class="larges"><label><input type="checkbox" id="x-se"> Inclure les articles non retenus (sans entreprise précise, hors de France ou chiffre invérifiable)</label></div>'
             '<details class="larges" id="plus-filtres"><summary>Plus de filtres : recoupements (les mêmes que les pastilles sous le résumé)</summary><label><input type="checkbox" id="x-dl"> Délocalisation annoncée</label><label><input type="checkbox" id="x-lb"> Lobbying déclaré (HATVP)</label><label><input type="checkbox" id="x-sd"> Amende pour retards de paiement</label><label><input type="checkbox" id="x-bb"> « Fort potentiel d’embauche » (France Travail)</label><label><input type="checkbox" id="x-ben"> Dernier exercice bénéficiaire</label><label><input type="checkbox" id="x-aide"> Aide publique dans les 24 mois</label>'
             '<label><input type="checkbox" id="x-pl"> Au moins 5 % de l\'emploi privé de la commune</label><label><input type="checkbox" id="x-cp"> Au moins 20 % du CA en commande publique</label><label><input type="checkbox" id="x-ae"> Accord d\u2019entreprise lié à l\u2019emploi (Légifrance)</label><label><input type="checkbox" id="x-mb"> Mobilisation signalée (ça brûle)</label><label><input type="checkbox" id="x-n2"> Au moins deux recoupements</label></details>'
             '<div class="larges"><button type="button" class="btn" id="dl">Télécharger la sélection (CSV)</button><button type="button" class="btn sec" id="lien">Copier le lien de cette sélection</button>'
             '<button type="button" class="btn sec" id="raz">Réinitialiser</button></div></form>'
             '<p id="memo" hidden>Filtres de votre dernière visite restaurés.<button type="button" id="memo-raz">Réinitialiser</button></p><p class="resume" id="resume" aria-live="polite"></p><div id="hist"></div>'
             '<div class="legende-rec"><span class="filtres-rec" id="pastilles" role="group" aria-label="Filtrer par recoupement"><button type="button" class="chip c-fin" data-f="ben" aria-pressed="false">Bénéficiaire <span class="nb"></span></button><button type="button" class="chip c-pub" data-f="aide" aria-pressed="false">Aide publique <span class="nb"></span></button><button type="button" class="chip c-pub" data-f="cp" aria-pressed="false">Commande publique ≥ 20 % <span class="nb"></span></button><button type="button" class="chip c-lob" data-f="lb" aria-pressed="false">Lobbying <span class="nb"></span></button><button type="button" class="chip c-amd" data-f="sd" aria-pressed="false">Amende <span class="nb"></span></button><button type="button" class="chip c-ter" data-f="pl" aria-pressed="false">Poids local ≥ 5 % <span class="nb"></span></button><button type="button" class="chip c-soc" data-f="dl" aria-pressed="false">Délocalisation <span class="nb"></span></button><button type="button" class="chip c-acc" data-f="ae" aria-pressed="false">Accord d\u2019entreprise <span class="nb"></span></button><button type="button" class="chip c-mob" data-f="mb" aria-pressed="false">Mobilisation <span class="nb"></span></button><button type="button" class="chip c-emb" data-f="bb" aria-pressed="false">Embauche <span class="nb"></span></button><button type="button" class="chip c-deux" data-f="n2" aria-pressed="false">Au moins 2 recoupements <span class="nb"></span></button></span><span class="meta">Vos filtres sont mémorisés dans ce navigateur ; « nouveau » signale ce qui est apparu depuis votre dernière visite. Cliquez sur une pastille pour filtrer (plusieurs = toutes à la fois), à nouveau pour retirer le filtre. Cliquez sur une ligne pour afficher le détail de ses recoupements. Les lignes surlignées en cumulent au moins deux. Cliquez sur l\'en-tête d\'une colonne pour trier (« Nb » : nombre de recoupements) et voir d\'abord les cas les plus documentés.</span></div>'
             '<div class="tablo"><table><thead><tr>' + "".join(f'<th data-k="{k}"{" class=n" if k in ("d", "em") else ""}><button type="button">{l}</button></th>' for k, l in
                (("d", "Date"), ("e", "Entreprise"), ("t", "Type"), ("c", "Lieu"), ("sec", "Secteur"), ("em", "Effectif"), ("nat", "Nature"), ("s", "Source"), ("nr", "Recoupements")))
             + '</tr></thead><tbody id="corps"></tbody></table></div><p><button type="button" class="btn sec" id="plus" hidden></button></p>'
             f'<noscript><p>Cette page a besoin de JavaScript. Les mêmes données sont téléchargeables sur la page <a href="{S.BASE}/donnees/">Données ouvertes</a>.</p></noscript>'
             f"<script>{EX_JS}</script>")
    graph = [S.site_ld(), S.dataset_ld(D, S.BASE_URL + "/explorer/", titre, desc)]
    S.ecrire("explorer/index.html", S.page(titre, desc, "explorer/", corps, graph, "explorer/"))
    return S.BASE_URL + "/explorer/"
