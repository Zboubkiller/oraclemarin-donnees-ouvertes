"""« Un an de faillites, à l'échelle » : page à défilement horizontal sur le principe de « Wealth shown to scale ».
Chapitre 1 : 1 carré = 1 entreprise en défaillance (cumul Banque de France sur 12 mois), avec des repères familiers.
Chapitre 2 : 1 carré = 1 emploi (annonces de l'année, une entreprise par bloc), avec des repères d'échelle (seuil légal du PSE,
emploi privé d'une petite commune). Le texte des cartes est dans le HTML (lisible sans JavaScript) ; le JavaScript ne fait que
placer les éléments à leur abscisse exacte."""
import json, datetime as dt
import commun as S
from commun import esc, fr, pct, mois_long

CSS = """
:root{--papier:#F5F3EE;--encre:#17202E;--gris:#5B6573;--trait:#C9CFD6;--jaune:#E8B21E;--sup:#B8361E;--dep:#3E7CB1;--men:#D9822B}
*{box-sizing:border-box}html,body{margin:0;height:100%}body{background:var(--papier);color:var(--encre);font:16px/1.5 Barlow,system-ui,sans-serif;overflow-x:auto;overflow-y:hidden}
a{color:inherit}a:focus-visible,.piste:focus-visible{outline:3px solid var(--jaune);outline-offset:2px}
.barre-haut{position:fixed;top:0;left:0;right:0;z-index:10;display:flex;gap:16px;flex-wrap:wrap;align-items:baseline;padding:10px 18px;background:rgba(245,243,238,.94);border-bottom:1px solid var(--trait);font-size:15px}
.barre-haut .marque{font:700 1.05rem "Barlow Condensed",sans-serif;text-transform:uppercase;letter-spacing:.03em;text-decoration:none;margin-right:auto}
.piste{position:relative;height:100vh}
.bar{position:absolute;top:46vh;height:var(--bh,240px)}
.bar canvas{position:absolute;top:0}
.inlab{position:absolute;top:calc(46vh + var(--bh,240px) / 2 - 13px);background:rgba(245,243,238,.94);color:var(--encre);font:600 15px Barlow,sans-serif;padding:2px 8px;white-space:nowrap;pointer-events:none;border-left:3px solid var(--encre)}
@media(max-width:700px){.inlab{top:calc(48vh + var(--bh,200px) / 2 - 12px);font-size:13px}}
.lab{position:absolute;top:calc(46vh - 46px);font-size:14px;white-space:nowrap;border-left:2px solid var(--encre);padding-left:6px;line-height:1.2}
.lab b{display:block;font:700 1.15rem "Barlow Condensed",sans-serif}
.carte{position:absolute;width:min(330px,80vw);background:#fff;border:1px solid var(--trait);border-top:4px solid var(--encre);padding:12px 16px;font-size:17px;line-height:1.45;box-shadow:0 2px 0 rgba(0,0,0,.04)}
.carte.haut{bottom:calc(54vh + 56px)}.carte.bas{top:calc(46vh + var(--bh,240px) + 22px)}
.carte::after{content:"";position:absolute;left:-1px;width:2px;background:var(--encre)}
.carte.haut::after{top:100%;height:56px}.carte.bas::after{bottom:100%;height:22px}
.carte b.n{font:700 1.6rem "Barlow Condensed",sans-serif}
.intro{position:absolute;left:0;top:0;height:100vh;width:var(--w);display:flex;flex-direction:column;justify-content:center;padding:70px 6vw 40px}
.intro h1{font:700 clamp(2.6rem,7vw,5.4rem)/.95 "Barlow Condensed",sans-serif;margin:0 0 18px;max-width:14ch}
.intro p{font-size:clamp(17px,2.2vw,21px);max-width:44ch;margin:0 0 12px}.fleche{font:700 1.4rem "Barlow Condensed",sans-serif;margin-top:14px}
.chap{position:absolute;top:0;height:100vh;width:var(--w);display:flex;flex-direction:column;justify-content:center;padding:70px 4vw 40px}
.chap h2{font:700 clamp(2.2rem,6vw,4.4rem)/1 "Barlow Condensed",sans-serif;margin:0 0 12px;max-width:16ch}.chap p{font-size:19px;max-width:42ch}
.compteur{position:fixed;left:18px;bottom:22px;z-index:10;background:var(--encre);color:#fff;padding:8px 14px;font-size:15px;max-width:calc(100vw - 36px)}
.compteur b{font:700 1.8rem "Barlow Condensed",sans-serif;color:var(--jaune);font-variant-numeric:tabular-nums;margin-right:6px}
.progres{position:fixed;left:0;bottom:0;height:5px;background:var(--jaune);z-index:11;width:0}
.leg{display:flex;flex-wrap:wrap;gap:4px 14px;font-size:15px;margin-top:8px}.leg i{display:inline-block;width:12px;height:12px;margin-right:5px;vertical-align:-1px}
.raye{background:repeating-linear-gradient(45deg,var(--men) 0 6px,#F0C38E 6px 12px)}
.fin{position:absolute;top:0;height:100vh;width:var(--w);display:flex;flex-direction:column;justify-content:center;padding:70px 4vw 40px}
.fin p{max-width:56ch;font-size:17px}.fin .cta{display:inline-block;background:var(--encre);color:#fff;padding:10px 16px;text-decoration:none;font-weight:600;margin:6px 8px 0 0}
@media(max-width:700px){.bar{top:48vh}.carte{font-size:15px;padding:10px 12px}.carte.haut{bottom:calc(52vh + 46px)}.carte.haut::after{height:46px}.carte.bas{top:calc(48vh + var(--bh,200px) + 18px)}.lab{top:calc(48vh - 42px);font-size:13px}}
"""

JS = r"""
(function(){
const D=JSON.parse(document.getElementById('donnees').textContent);const P=document.querySelector('.piste');const nf=n=>Math.round(n).toLocaleString('fr-FR');
const vw=()=>document.documentElement.clientWidth;let L={};
function el(cls,css,html,titre){const d=document.createElement('div');d.className=cls;Object.assign(d.style,css);if(html!=null)d.innerHTML=html;if(titre)d.title=titre;d.dataset.gen='1';P.appendChild(d);return d}
// géométrie : un carré de 6 px, 2 px d'écart ; les unités remplissent la bande colonne par colonne, de haut en bas
const U=6,PAS=8;let R=25;
const X=i=>Math.floor(i/R)*PAS, LARG=n=>Math.ceil(n/R)*PAS;
const COUL={sup:['#B8361E','#D0654F'],dep:['#3E7CB1','#6E9CCB'],men:['#D9822B','#E8A866']};
function grille(x0,total,couleur,titre){
 const larg=LARG(total),bar=el('bar',{left:x0+'px',width:larg+'px'},null,titre);
 const dpr=Math.min(2,window.devicePixelRatio||1),TW=Math.floor(3200/PAS)*PAS;   // tuiles : un canvas trop large ne se peint pas partout
 for(let ox=0;ox<larg;ox+=TW){const w=Math.min(TW,larg-ox),cv=document.createElement('canvas');cv.width=Math.round(w*dpr);cv.height=Math.round(R*PAS*dpr);
  cv.style.cssText=`left:${ox}px;width:${w}px;height:${R*PAS}px`;const g=cv.getContext('2d');g.scale(dpr,dpr);let prev='';
  const c0=ox/PAS,c1=c0+w/PAS;
  for(let c=c0;c<c1;c++)for(let r=0;r<R;r++){const i=c*R+r;if(i>=total)break;const k=couleur(i);if(k!==prev){g.fillStyle=k;prev=k}g.fillRect((c-c0)*PAS,r*PAS,U,U)}
  bar.appendChild(cv)}
 return bar}
function runs(liste){const fins=[];let c=0;liste.forEach(s=>{c+=s.n;fins.push(c)});
 return i=>{let lo=0,hi=fins.length-1;while(lo<hi){const m=(lo+hi)>>1;if(fins[m]>i)hi=m;else lo=m+1}return lo}}
function rappels(x0,larg,txt){for(let o=900;o<larg-500;o+=1500)el('inlab',{left:(x0+o)+'px'},txt)}
function construire(){
 P.querySelectorAll('[data-gen]').forEach(n=>n.remove());const w=vw(),h=innerHeight,etroit=w<700,ecran=etroit?w:Math.max(w,640),lintro=etroit?w:Math.max(w,720);
 R=Math.max(12,Math.floor((etroit?.26:.32)*h/PAS));P.style.setProperty('--bh',(R*PAS)+'px');let x=0;L={};
 L.intro=0;x=lintro+(etroit?40:0);
 L.c1=x;x+=LARG(D.c1.total);L.c1fin=x;x+=440;                 // la carte de fin (330 px) ne doit pas recouvrir le titre du chapitre 2
 L.chap2=x;x+=ecran;
 L.pse=x;x+=LARG(D.c2.pse)+Math.max(420,w*.45);
 if(D.c2.local){L.local=x;x+=LARG(D.c2.local.eff)+Math.max(420,w*.45)}
 L.blocs=x;x+=LARG(D.c2.total);L.blocsfin=x;x+=300;
 if(D.c2.bodacc){L.bodacc=x;x+=LARG(D.c2.bodacc);x+=300}
 L.fin=x;x+=Math.max(w,760);L.total=x;P.style.width=x+'px';
 document.querySelectorAll('.intro,.chap,.fin').forEach(n=>n.style.setProperty('--w',(n.classList.contains('intro')?lintro:ecran)+'px'));
 document.querySelector('.chap').style.left=L.chap2+'px';document.querySelector('.fin').style.left=L.fin+'px';
 // chapitre 1 : un carré = une entreprise ; secteurs en deux tons ; un carré jaune sur T (50 salariés et plus) ; la hausse en rouge
 const sec=runs(D.c1.secteurs),T=D.c1.tous_les||0,av=D.c1.n_avant&&D.c1.n_avant<D.c1.total?D.c1.n_avant:Infinity;
 grille(L.c1,D.c1.total,i=>T&&(i+1)%T===0?'#E8B21E':i>=av?'#B8361E':(sec(i)%2?'#3A4A66':'#17202E'),'Une entreprise par carré');
 let c=0;D.c1.secteurs.forEach(s=>{el('lab',{left:(L.c1+X(c))+'px'},`<b>${nf(s.n)}</b>${s.label}`);if(s.n>3000)rappels(L.c1+X(c),LARG(s.n),s.label);c+=s.n});
 // chapitre 2 : un carré = un emploi
 grille(L.pse,D.c2.pse,()=>'#B8361E','10 emplois');
 if(D.c2.local)grille(L.local,D.c2.local.eff,i=>i<D.c2.local.n?'#B8361E':'#B9C0C9','Salariés du privé de '+D.c2.local.commune);
 const bl=runs(D.c2.blocs);grille(L.blocs,D.c2.total,i=>{const k=bl(i);return COUL[D.c2.blocs[k].k][k%2]},'Un emploi par carré');
 c=0;let derniere=-999;D.c2.blocs.forEach(s=>{const xs=X(c);if(LARG(s.n)>=48&&xs-derniere>=150){el('lab',{left:(L.blocs+xs)+'px'},`<b>${nf(s.n)}</b>${s.nom}`);derniere=xs}
  if(LARG(s.n)>1400)rappels(L.blocs+xs,LARG(s.n),s.nom+' · '+nf(s.n)+' '+s.nature);c+=s.n});
 if(D.c2.bodacc){grille(L.bodacc,D.c2.bodacc,i=>i%2?'#E3A15E':'#D9822B','Salariés des entreprises de 50 salariés et plus entrées en procédure');
  rappels(L.bodacc,LARG(D.c2.bodacc),'salariés d\'entreprises en procédure, pas forcément licenciés')}
 // cartes : data-at est un rang d'unité, converti en abscisse
 document.querySelectorAll('.carte').forEach(k=>{const base={c1:L.c1,pse:L.pse,local:L.local,blocs:L.blocs,bodacc:L.bodacc}[k.dataset.ref];
  if(base==null){k.style.display='none';return}k.style.display='';k.style.left=(base+X(+k.dataset.at||0))+'px'});
 maj()}
function rang(x,x0,total){return Math.min(total,Math.max(0,(Math.floor((x-x0)/PAS)+1)*R))}
function maj(){const w=vw(),x=scrollX+w*.5;let txt='Faites défiler vers la droite →',n=null,u='';
 if(x>=L.c1&&x<=L.c1fin+150){n=rang(x,L.c1,D.c1.total);u='entreprises';let c=0;for(const s of D.c1.secteurs){if(n<=c+s.n){txt=s.label;break}c+=s.n}if(n>=D.c1.total)txt='une année de défaillances'}
 else if(x>=L.blocs&&x<=L.blocsfin+150){n=rang(x,L.blocs,D.c2.total);u='emplois annoncés';let c=0;for(const s of D.c2.blocs){if(n<=c+s.n){txt=s.nom+' · '+s.nature;break}c+=s.n}if(n>=D.c2.total)txt='depuis le 1er janvier'}
 else if(L.bodacc&&x>=L.bodacc&&x<=L.bodacc+LARG(D.c2.bodacc)+150){n=rang(x,L.bodacc,D.c2.bodacc);u='salariés en procédure';txt='entreprises de 50 salariés et plus'}
 else if(x>L.c1fin)txt=x<L.fin?'1 carré = 1 emploi':'Fin';
 document.getElementById('cpt').innerHTML=(n!=null?`<b>${nf(n)}</b>${u} · `:'')+txt;
 document.querySelector('.progres').style.width=(100*scrollX/Math.max(1,L.total-w))+'%'}
// molette verticale -> défilement horizontal lissé : on vise une cible et on s'en rapproche à chaque image (sauf « réduire les animations »)
const doux=!matchMedia('(prefers-reduced-motion: reduce)').matches;let cible=null,anim=0;
function glisse(){const d=cible-scrollX;if(Math.abs(d)<0.5){scrollTo(cible,0);cible=null;anim=0;return}scrollTo(scrollX+d*0.14,0);anim=requestAnimationFrame(glisse)}
addEventListener('wheel',e=>{if(Math.abs(e.deltaY)>Math.abs(e.deltaX)&&!e.ctrlKey){e.preventDefault();const pas=e.deltaY*(e.deltaMode===1?40:1.4);
 if(!doux){scrollBy(pas,0);return}const max=document.documentElement.scrollWidth-innerWidth;
 cible=Math.max(0,Math.min(max,(cible==null?scrollX:cible)+pas));if(!anim)anim=requestAnimationFrame(glisse)}},{passive:false});
addEventListener('pointerdown',()=>{cible=null;cancelAnimationFrame(anim);anim=0});
addEventListener('keydown',e=>{if(e.key==='Home'){scrollTo(0,0)}if(e.key==='End'){scrollTo(L.total,0)}});
addEventListener('scroll',maj,{passive:true});let t;addEventListener('resize',()=>{clearTimeout(t);t=setTimeout(construire,200)});construire()})();
"""

def nb_communes():
    """Communes de France métropolitaine et des départements d'outre-mer (hors collectivités d'outre-mer), d'après geo.api.gouv.fr."""
    try: c = json.load(open("/opt/ca-brule/communes.json"))
    except Exception: return None
    return sum(1 for x in c if not (x["code"].startswith("98") or x["code"][:3] in ("975", "977", "978")))

def page(D, F, AN, ents, p50, part_nat, top5):
    b, a, cr = F.get("bdf"), F.get("annee") or {}, F.get("creations")
    if not b: return None
    secs = list(F.get("secteurs", []))
    reste = b["n"] - sum(s["cumul_12_mois"] for s in secs)
    s1 = [{"n": s["cumul_12_mois"], "label": s["secteur"]} for s in secs] + ([{"n": reste, "label": "Autres"}] if reste > 0 else [])
    ncom = nb_communes()
    tous_les = round(1000 / p50["pour_mille"]) if p50 else None
    k = {"suppressions annoncées": "sup", "départs volontaires": "dep", "emplois menacés": "men"}
    blocs = sorted(ents, key=lambda x: (x["date"], -x["n"]))
    tot = sum(x["n"] for x in blocs)
    plans = [e for e in D["data"].get("evenements", []) if e.get("source") != "BODACC" and (e.get("date") or "") >= f"{AN}-01-01"]
    loc = None
    for e in sorted([e for e in plans if (e.get("poids_local") or {}).get("part_commune_pct", 0) >= 10 and e["poids_local"]["part_commune_pct"] <= 100
                     and e["poids_local"]["effectif_commune"] <= 1500], key=lambda e: -e["poids_local"]["part_commune_pct"]):
        p = e["poids_local"]; loc = {"commune": p["commune"], "dep": e.get("dep"), "eff": p["effectif_commune"], "n": e["emplois_min"], "nom": e["entreprise"],
                                     "pct": p["part_commune_pct"], "annee": p["annee"], "src": e["source"], "mois": mois_long(e["date"])}
        break
    sp = a.get("procedures_50") or {}
    bod = sp.get("min") or 0
    data = {"c1": {"total": b["n"], "secteurs": s1, "tous_les": tous_les, "n_avant": b.get("n_avant")},
            "c2": {"pse": 10, "local": loc, "total": tot, "bodacc": bod,
                   "blocs": [{"n": x["n"], "nom": x["nom"], "nature": x["nature"], "k": k[x["nature"]], "src": x["src"], "mois": mois_long(x["date"])} for x in blocs]}}
    jour, sem, mois = round(b["n"] / 365), round(b["n"] / 52), round(b["n"] / 12)
    cartes = [("c1", 0, "haut", "Ce petit carré, en haut à gauche de la bande, c'est <b>une entreprise</b> en défaillance. Les suivants s'empilent colonne par colonne."),
              ("c1", jour, "bas", f"<b class=n>{fr(jour)}</b><br>Une journée de défaillances, en moyenne."),
              ("c1", sem, "haut", f"<b class=n>{fr(sem)}</b><br>Une semaine."),
              ("c1", mois, "bas", f"<b class=n>{fr(mois)}</b><br>Un mois.")]
    if tous_les:
        cartes.append(("c1", 4200, "haut", f"Les carrés jaunes : <b>une entreprise sur {tous_les}</b> avait 50 salariés ou plus "
                                           f"(BODACC, {p50['mois'][0][:4]}). Peu nombreuses, ce sont elles qui emploient le plus."))
    if ncom and ncom < b["n"]:
        cartes.append(("c1", ncom, "bas", f"<b class=n>{fr(ncom)}</b><br>Le nombre de communes en France. En un an, il y a eu "
                                          f"<b>{str(round(b['n'] / ncom, 1)).replace('.', ',').replace(',0', '')} défaillances par commune</b>, en moyenne."))
    cum, pos = 0, ["bas", "haut", "haut"]
    for i, s in enumerate(secs[:3]):
        cum += s["cumul_12_mois"]
        part = round(100 * cum / b["n"])
        txt = (f"Fin de la construction : <b>une défaillance sur {round(b['n'] / s['cumul_12_mois'])}</b> vient du bâtiment ({fr(s['cumul_12_mois'])})." if i == 0 else
               f"Avec {s['secteur'].lower()}, on atteint <b>{part} %</b> des défaillances de l'année ({pct(s['variation_pct'])} en un an pour ce secteur).")
        if not (ncom and abs(cum - ncom) < 900): cartes.append(("c1", cum, pos[i], txt))
    if b.get("n_avant") and b["n_avant"] < b["n"]:
        cartes.append(("c1", b["n_avant"], "bas", f"<b class=n>{fr(b['n_avant'])}</b><br>Il y a un an, la barre s'arrêtait ici. "
                                                  f"Les <b>{fr(b['n'] - b['n_avant'])} carrés</b> rouges qui suivent : la hausse en un an."))
    cartes.append(("c1", b["n"], "haut", f"<b class=n>{fr(b['n'])}</b><br>Une année de défaillances, {S.de_mois(b['debut'])} à {mois_long(b['mois'])} "
                                         f"(Banque de France). <b>{pct(b['var'])}</b> en un an."))
    cartes.append(("pse", 0, "haut", "<b class=n>10</b><br>Ces 10 carrés : le seuil légal. À partir de 10 licenciements économiques en 30 jours, "
                                     "une entreprise de 50 salariés ou plus doit négocier un plan de sauvegarde de l'emploi."))
    if loc:
        cartes.append(("local", 0, "haut", f"<b class=n>{fr(loc['eff'])}</b><br>Tous les salariés du secteur privé de {esc(loc['commune'])}"
                                           f"{' (' + esc(loc['dep']) + ')' if loc.get('dep') else ''}, d'après l'URSSAF ({loc['annee']})."))
        cartes.append(("local", loc["n"], "bas", f"En rouge, <b>{fr(loc['n'])} emplois</b> annoncés comme supprimés ou menacés chez {esc(loc['nom'])} "
                                                 f"({esc(loc['src'])}, {loc['mois']}) : <b>{str(loc['pct']).replace('.', ',')} %</b> de l'emploi privé de la commune."))
    cartes.append(("blocs", 0, "haut", f"Toutes les annonces depuis le 1er janvier {AN}, dans l'ordre chronologique. Chaque bloc est une entreprise, à sa vraie longueur."
                                       '<span class="leg"><span><i style="background:var(--sup)"></i>suppressions annoncées</span>'
                                       '<span><i style="background:var(--dep)"></i>départs volontaires</span><span><i style="background:var(--men)"></i>emplois menacés</span></span>'))
    cartes.append(("blocs", tot, "haut", f"<b class=n>{fr(tot)}</b><br>emplois annoncés comme supprimés ou menacés en {AN}, dans {len(blocs)} entreprises : "
                                         + ", ".join(f"{fr(part_nat.get(n, 0))} {n}" for n in S.NATURES) + f". Les cinq plus gros plans en font {top5} %."))
    if bod:
        cartes.append(("bodacc", 0, "bas", f"<b class=n>{fr(bod)}</b><br>Et les salariés des {fr(sp.get('entreprises', 0))} entreprises de 50 salariés et plus entrées en procédure "
                                           "collective depuis janvier (BODACC, au minimum). Tous ne perdront pas leur emploi : une entreprise en redressement peut être reprise."
                                           + ("" if sp.get("complet") else " Chiffre provisoire : l'historique est en cours de rattrapage.")))
    html_cartes = "".join(f'<div class="carte {pos}" data-ref="{ref}" data-at="{at}">{t}</div>' for ref, at, pos, t in cartes)
    titre = "Un an de faillites, à l'échelle"
    desc = (f"{fr(b['n'])} défaillances d'entreprises en un an, à l'échelle : 1 carré = 1 entreprise, puis 1 carré = 1 emploi annoncé comme supprimé ou menacé en {AN}. "
            "Faites défiler.")
    url = S.BASE_URL + "/en-un-an/"
    graph = [S.site_ld(), {"@type": "WebPage", "name": titre, "url": url, "inLanguage": "fr-FR", "dateModified": dt.date.today().isoformat(),
                           "isPartOf": {"@id": S.BASE_URL + "/#site"}, "description": desc}]
    corps = (f'<header class="barre-haut"><a class="marque" href="{S.BASE}/">{esc(S.NOM)}</a><a href="{S.BASE}/faillites-entreprises/">Version texte</a>'
             f'<a href="{S.BASE}/explorer/">Explorer les données</a><a href="{S.BASE}/methode/">Méthode</a></header>'
             f'<main class="piste" tabindex="0" aria-label="Infographie à faire défiler horizontalement">'
             f'<section class="intro"><h1>Un an de faillites, à l\'échelle</h1>'
             f'<p>{S.de_mois(b["debut"]).capitalize()} à {mois_long(b["mois"])}, <b>{fr(b["n"])} entreprises</b> ont fait défaillance en France, selon la Banque de France.</p>'
             f'<p>Sur cette page, <b>1 carré = 1 entreprise</b>. La bande qui suit en compte {fr(b["n"])}, rangés en colonnes : zoomez, on peut les compter.</p>'
             '<p class="fleche">Faites défiler vers la droite →</p><p class="meta" style="font-size:15px;color:#5B6573">Molette, flèches du clavier ou glisser du doigt.</p></section>'
             f'{html_cartes}'
             f'<section class="chap"><h2>Changeons d\'unité : 1 carré = 1 emploi</h2><p>Une défaillance ne dit pas combien de personnes perdent leur travail. '
             f'Voici les emplois dont la suppression ou la menace a été annoncée publiquement en {AN}, avec, avant, deux repères pour juger de l\'échelle.</p></section>'
             f'<section class="fin"><h2 style="font:700 2.4rem \'Barlow Condensed\',sans-serif;margin:0 0 10px">D\'où viennent ces chiffres</h2>'
             f'<p>Défaillances : Banque de France, cumul sur douze mois à fin {mois_long(b["mois"])} (série INSEE {esc(D["officiel"]["defaillances"]["idbank"])}), réparties par secteur. '
             "Part des entreprises de 50 salariés et plus : jugements publiés au BODACC rapprochés des tranches d'effectif de l'INSEE. Communes : base officielle (geo.api.gouv.fr). "
             "Emplois : liste CGT des plans de licenciement et presse, chiffres annoncés, relus et dédoublonnés par entreprise. Emploi local : URSSAF. "
             "Seuil du plan de sauvegarde de l'emploi : article L1233-61 du Code du travail.</p>"
             f'<p><a class="cta" href="{S.BASE}/explorer/">Explorer et filtrer les données</a><a class="cta" href="{S.BASE}/faillites-entreprises/">Les chiffres en détail</a>'
             f'<a class="cta" href="{S.BASE}/methode/">Méthode et corrections</a></p></section></main>'
             '<div class="compteur" id="cpt" aria-hidden="true">Faites défiler vers la droite →</div><div class="progres" aria-hidden="true"></div>'
             f'<script type="application/json" id="donnees">{json.dumps(data, ensure_ascii=False).replace("</", "<\\/")}</script><script>{JS}</script>')
    html_page = ('<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
                 f'<title>{esc(titre)}</title><meta name="description" content="{esc(desc)}">{S.head_meta(titre, desc, url)}'
                 f'<link rel="stylesheet" href="{S.BASE}/fonts/fonts.css">'
                 f'<style>{CSS}</style>{S.ld_tag(graph)}</head><body>{corps}</body></html>')
    S.ecrire("en-un-an/index.html", html_page)
    return url
