"""Carte des liens entre sociétés, côté site public : page /liens/, encart du hub, mini-graphe des fiches.
Données : graphe_liens.donnees() (liens de societes_liees.csv, avec preuve). Aucun lien n'est un constat d'appartenance à un groupe."""
import json, os, shutil, sys
H = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, H)
import commun as S
from commun import esc

_D = {"d": None}
def donnees():
    if _D["d"] is None:
        import graphe_liens
        d = graphe_liens.donnees()
        idx = {n["id"]: n for n in d["noeuds"]}
        adj = {}
        for l in d["liens"]:
            if l["force"] == "indice": continue
            adj.setdefault(l["s"], []).append(l); adj.setdefault(l["t"], []).append(l)
        _D["d"] = (d, idx, adj)
    return _D["d"]

def _noeud(n, centre=False):
    return {"id": n["id"], "nom": (n.get("cite") or n["nom"] or n["id"])[:48], "eff": n.get("eff"), "a": n.get("annonces", 0), "p": bool(n.get("proc")), "u": n.get("url"), "c": 1 if centre else 0}

def widget_fiche(siren):
    """Mini-graphe d'une fiche : la société, ses liens forts ou probables (12 au plus) et les liens entre eux."""
    d, idx, adj = donnees()
    L = adj.get(siren)
    if not L or siren not in idx: return ""
    ordre = {"fort": 0, "probable": 1}
    vois = []
    for l in sorted(L, key=lambda l: ordre[l["force"]]):
        o = l["t"] if l["s"] == siren else l["s"]
        if o not in vois: vois.append(o)
    vois = vois[:12]; ids = {siren, *vois}
    liens, vus = [], set()
    for s in ids:
        for l in adj.get(s, []):
            if l["s"] in ids and l["t"] in ids and (l["s"], l["t"], l["force"]) not in vus:
                vus.add((l["s"], l["t"], l["force"])); liens.append({"s": l["s"], "t": l["t"], "f": l["force"][0], "p": l["preuve"][:120]})
    data = {"n": [_noeud(idx[i], i == siren) for i in [siren] + vois if i in idx], "l": liens}
    return (f'<style>{CSS_COMMUN}</style><section class="fiche-liens"><h2>Groupe et sociétés liées</h2>'
            f'<div class="mini-liens" data-h="270"></div><script type="application/json" class="mini-data">{json.dumps(data, ensure_ascii=False).replace("</", "<\\/")}</script>'
            f'<p class="meta">Déplace les blocs, clique sur une société pour ouvrir sa fiche. La taille suit l\'effectif ; plein : lien fort, pointillé : probable. '
            f'Les preuves sont dans « Sociétés liées » ci-dessus. <a href="{S.BASE}/groupes/#{siren}">Voir sur la carte des groupes</a>. '
            'Un lien n\'est pas un constat d\'appartenance à un groupe.</p></section>'
            f'<script src="{S.BASE}/miniliens.js" defer></script>')

def encart_hub():
    """Encart du hub : aperçu animé d'un groupe d'une dizaine de sociétés qui ont des événements, et bouton vers la page dédiée."""
    d, idx, adj = donnees()
    par, noeuds = {}, [n["id"] for n in d["noeuds"]]
    def trouve(x):
        while par[x] != x: par[x] = par[par[x]]; x = par[x]
        return x
    for i in noeuds: par[i] = i
    for s, L in adj.items():
        for l in L:
            a, b = trouve(l["s"]), trouve(l["t"])
            if a != b: par[a] = b
    comp = {}
    for i in noeuds: comp.setdefault(trouve(i), []).append(i)
    def valeur(c):
        ev = sum(1 for i in c if idx[i].get("annonces") or idx[i].get("proc"))
        return (ev if 5 <= len(c) <= 12 else 0, len(c))
    best = max(comp.values(), key=valeur)
    if valeur(best)[0] == 0: return ""
    ids = set(best)
    liens = [{"s": l["s"], "t": l["t"], "f": l["force"][0], "p": l["preuve"][:100]} for s in ids for l in adj.get(s, []) if l["s"] == s and l["t"] in ids]
    data = {"n": [_noeud(idx[i]) for i in best], "l": liens}
    nb_g = sum(1 for c in comp.values() if len(c) >= 3)
    return (f'<style>{CSS_COMMUN}</style><section class="encart-liens" aria-label="Liens entre sociétés"><div><h2>Qui est lié à qui ?</h2>'
            f'<p>{S.fr(len(d["noeuds"]))} sociétés suivies ou liées, {S.fr(len(d["liens"]))} liens avec leur preuve (dirigeant commun, adresse, reprise publiée au BODACC), {nb_g} groupes de trois sociétés ou plus. Aperçu : un groupe du tracker.</p>'
                        f'<p><a class="bouton-liens" href="{S.BASE}/groupes/">Ouvrir la carte des groupes →</a></p></div>'
            f'<div class="mini-liens" data-h="230" data-statique="1"></div><script type="application/json" class="mini-data">{json.dumps(data, ensure_ascii=False).replace("</", "<\\/")}</script></section>'
            f'<script src="{S.BASE}/miniliens.js" defer></script>')

MINI_JS = r"""(function(){
function eff(n){var m=n.eff&&n.eff[0]!=null?(n.eff[0]+(n.eff[1]||n.eff[0]))/2:null;return m==null?5:Math.min(22,4+.45*Math.sqrt(m))}
function col(n){var a=n.a>0,p=n.p;return a&&p?'#7A1B12':p?'#B8361E':a?'#E07B28':'#98A2B3'}
function init(box){var sc=box.parentNode.querySelector('script.mini-data');if(!sc||box.dataset.pret)return;box.dataset.pret=1;
 var D=JSON.parse(sc.textContent),stat=!!box.dataset.statique,Hh=+box.dataset.h||260,cv=document.createElement('canvas'),ctx=cv.getContext('2d'),dpr=window.devicePixelRatio||1,W=0;
 cv.style.cssText='display:block;width:100%;height:'+Hh+'px;'+(stat?'':'touch-action:none;cursor:grab');box.appendChild(cv);
 var N=D.n.map(function(n,i){var a=i*6.2832/D.n.length;return Object.assign({},n,{r:eff(n),x:0,y:0,vx:0,vy:0,a:a,fx:null,fy:null})}),idx={};N.forEach(function(n){idx[n.id]=n});
 var L=D.l.map(function(l){return{s:idx[l.s],t:idx[l.t],f:l.f,p:l.p}}).filter(function(l){return l.s&&l.t});
 function dim(){W=box.clientWidth||300;cv.width=W*dpr;cv.height=Hh*dpr;ctx.setTransform(dpr,0,0,dpr,0,0);N.forEach(function(n){if(!n.x){n.x=W/2+Math.cos(n.a)*Math.min(W,Hh)*.3;n.y=Hh/2+Math.sin(n.a)*Hh*.3}})}
 dim();addEventListener('resize',dim);
 var sel=null,moved=0;
 function pas(){var cx=W/2,cy=Hh/2,i,j,n,m,dx,dy,d2,d,f;
  for(i=0;i<N.length;i++){n=N[i];n.vx*=.86;n.vy*=.86;n.vx+=(cx-n.x)*.004;n.vy+=(cy-n.y)*.004;n.vx+=(Math.random()-.5)*.07;n.vy+=(Math.random()-.5)*.07;
   for(j=i+1;j<N.length;j++){m=N[j];dx=n.x-m.x;dy=n.y-m.y;d2=dx*dx+dy*dy+.01;d=Math.sqrt(d2);f=Math.min(2.2,(900+(n.r+m.r)*30)/d2);n.vx+=dx/d*f;n.vy+=dy/d*f;m.vx-=dx/d*f;m.vy-=dy/d*f}}
  L.forEach(function(l){var dx=l.t.x-l.s.x,dy=l.t.y-l.s.y,d=Math.sqrt(dx*dx+dy*dy)||1,want=(l.f==='f'?70:100)+(l.s.r+l.t.r),f=(d-want)*.012;l.s.vx+=dx/d*f;l.s.vy+=dy/d*f;l.t.vx-=dx/d*f;l.t.vy-=dy/d*f});
  N.forEach(function(n){if(n.fx!=null){n.x=n.fx;n.y=n.fy;n.vx=n.vy=0}else{n.x=Math.max(n.r+6,Math.min(W-n.r-6,n.x+n.vx));n.y=Math.max(n.r+6,Math.min(Hh-n.r-14,n.y+n.vy))}})}
 function dessiner(){ctx.clearRect(0,0,W,Hh);
  L.forEach(function(l){var a=!sel||l.s===sel||l.t===sel;ctx.globalAlpha=a?1:.15;ctx.beginPath();ctx.moveTo(l.s.x,l.s.y);ctx.lineTo(l.t.x,l.t.y);ctx.strokeStyle='#4A5361';ctx.lineWidth=l.f==='f'?1.8:1.2;ctx.setLineDash(l.f==='f'?[]:[5,4]);ctx.stroke()});
  ctx.setLineDash([]);
  N.forEach(function(n){var a=!sel||n===sel||L.some(function(l){return(l.s===sel&&l.t===n)||(l.t===sel&&l.s===n)});ctx.globalAlpha=a?1:.25;ctx.beginPath();ctx.arc(n.x,n.y,n.r,0,6.2832);ctx.fillStyle=col(n);ctx.fill();ctx.lineWidth=n.c?3:1.4;ctx.strokeStyle=n.c?'#17202E':'#fff';ctx.stroke()});
  ctx.globalAlpha=1;ctx.textAlign='center';ctx.font='12px system-ui,sans-serif';
  N.forEach(function(n){var t=n.nom.length>24?n.nom.slice(0,23)+'…':n.nom;ctx.lineWidth=3;ctx.strokeStyle='rgba(255,255,255,.92)';ctx.strokeText(t,n.x,n.y+n.r+12);ctx.fillStyle='#17202E';ctx.font=(n.c?'600 ':'')+'12px system-ui,sans-serif';ctx.fillText(t,n.x,n.y+n.r+12)})}
 var vis=true;if('IntersectionObserver' in window)new IntersectionObserver(function(e){vis=e[0].isIntersecting}).observe(box);
 (function boucle(){if(vis){pas();dessiner()}requestAnimationFrame(boucle)})();
 for(var k=0;k<160;k++)pas();
 if(stat)return;
 function pos(e){var r=cv.getBoundingClientRect();return[e.clientX-r.left,e.clientY-r.top]}
 function sous(p){var b=null,dd=1e9;N.forEach(function(n){var d=(n.x-p[0])*(n.x-p[0])+(n.y-p[1])*(n.y-p[1]);if(d<=(n.r+6)*(n.r+6)&&d<dd){dd=d;b=n}});return b}
 cv.addEventListener('pointerdown',function(e){var n=sous(pos(e));if(!n)return;sel=n;moved=0;n.fx=n.x;n.fy=n.y;cv.setPointerCapture(e.pointerId);cv.style.cursor='grabbing';cv._d=n});
 cv.addEventListener('pointermove',function(e){var p=pos(e),n=cv._d;if(n){moved+=Math.abs(e.movementX||0)+Math.abs(e.movementY||0);n.fx=Math.max(n.r,Math.min(W-n.r,p[0]));n.fy=Math.max(n.r,Math.min(Hh-n.r,p[1]))}else cv.style.cursor=sous(p)?'pointer':'grab'});
 function fin(e){var n=cv._d;if(!n)return;cv._d=null;cv.style.cursor='grab';n.fx=null;n.fy=null;if(moved<5&&n.u)location.href=n.u;sel=null}
 cv.addEventListener('pointerup',fin);cv.addEventListener('pointercancel',fin)}
function tout(){document.querySelectorAll('.mini-liens').forEach(init)}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',tout);else tout()})();
"""

CSS_COMMUN = (".mini-liens{border:1px solid #D9D5CC;background:#fff;position:relative;margin:8px 0}"
              ".fiche-liens h2{margin-top:22px}.encart-liens{max-width:1180px;margin:0 auto 10px;padding:0 20px;display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.2fr);gap:20px;align-items:center}"
              ".encart-liens h2{margin:0 0 6px}.encart-liens p{margin:6px 0}.bouton-liens{display:inline-block;background:#17202E;color:#fff;text-decoration:none;padding:9px 14px;font-weight:600}"
              "@media(max-width:860px){.encart-liens{grid-template-columns:1fr}}")

PAGE = r"""<style>#lg{position:relative;height:74vh;min-height:430px;border:1px solid #D9D5CC;background:#fff}#lg canvas{display:block;width:100%;height:100%;touch-action:none;cursor:grab}
#lg-ctl{display:flex;flex-wrap:wrap;gap:8px 14px;align-items:center;margin:10px 0}#lg-ctl label{font-size:14px;display:flex;align-items:center;gap:5px}#lg-ctl input[type=search]{font:15px inherit;padding:6px 9px;border:1px solid #D9D5CC;min-width:190px}
#lg-info{position:absolute;right:8px;bottom:8px;width:min(360px,calc(100% - 16px));max-height:60%;overflow:auto;background:#fff;border:1px solid #D9D5CC;padding:10px 12px;display:none;box-shadow:0 2px 12px rgba(0,0,0,.14);font-size:14px}
#lg-info h2{font-size:16px;margin:0 0 2px}#lg-info li{margin:3px 0 3px 16px;font-size:13px}#lg-info button{float:right;border:0;background:none;font-size:20px;cursor:pointer}
#lg-lege{font-size:13px;color:#5A6371;margin:8px 0}#lg-lege i{display:inline-block;width:11px;height:11px;border-radius:50%;margin:0 5px 0 12px;vertical-align:-1px}</style>
<h1>Carte des groupes et des sociétés liées</h1>
<p class="chapo">Chaque bloc est une société ; sa <b>taille</b> suit son effectif. Un trait relie deux sociétés quand une <b>preuve publique</b> les rapproche : dirigeant personne morale commun, société mère immédiate, reprise de fonds de commerce publiée au BODACC, ou adresse de siège commune. Un lien <b>n'est pas un constat d'appartenance à un groupe</b> : lis la preuve avant de conclure.</p>
<div id="lg-ctl"><input id="q" type="search" placeholder="Chercher une société ou un SIREN…" aria-label="Chercher une société"><label>groupes d'au moins <select id="mini"><option>2</option><option selected>3</option><option>4</option><option>6</option><option>10</option></select> sociétés</label>
<label><input type="checkbox" id="indice"> liens par simple adresse (faibles)</label><label><input type="checkbox" id="isoles"> sociétés sans événement</label><label><input type="checkbox" id="flotte" checked> flottement</label><button id="cad" type="button" style="font:inherit;padding:5px 10px">recadrer</button><span id="nb" style="color:#5A6371;font-size:13px"></span></div>
<div id="lg" role="img" aria-label="Carte interactive des groupes et des sociétés liées"><div id="lg-info"></div></div>
<p id="lg-lege"><b>Couleur</b><i style="background:#E07B28"></i>plan social ou fermeture<i style="background:#B8361E"></i>procédure collective<i style="background:#7A1B12"></i>les deux<i style="background:#98A2B3"></i>société liée sans événement · <b>Trait</b> plein : lien fort, pointillé : probable, fin : adresse seule · Glisse un bloc pour le déplacer, double-clic pour le relâcher, molette pour zoomer.</p>
<p class="meta">Données : <a href="@BASE@/societes_liees.csv">societes_liees.csv</a> (liens et preuves), mises à jour à chaque collecte. Dirigeants : API Recherche d'entreprises ; adresses : répertoire Sirene ; cessions : BODACC. Les commissaires aux comptes, administrateurs et mandataires judiciaires sont exclus des liens.</p>
<script src="@BASE@/vendor/d3.v7.8.5.min.js"></script><script src="@BASE@/liens-carte.js"></script>"""

def p_liens(EV, FICHES=None):
    d, idx, adj = donnees()
    pub = os.path.join(S.PUB, "vendor"); os.makedirs(pub, exist_ok=True)
    shutil.copy(os.path.join(H, "vendor", "d3.v7.8.5.min.js"), os.path.join(pub, "d3.v7.8.5.min.js"))
    S.ecrire("liens.json", json.dumps({"noeuds": [{k: n[k] for k in ("id", "nom", "cite", "eff", "annonces", "emplois", "proc", "cessee", "url")} for n in d["noeuds"]], "liens": d["liens"]}, ensure_ascii=False, separators=(",", ":")))
    S.ecrire("miniliens.js", MINI_JS)
    carte = open(os.path.join(H, "liens-carte.js"), encoding="utf-8").read().replace("@BASE@", S.BASE)
    S.ecrire("liens-carte.js", carte)
    titre = "Carte des groupes : qui est lié à qui ?"
    desc = "Carte interactive des groupes et des sociétés liées aux entreprises suivies (dirigeant commun, société mère, reprise au BODACC, adresse), avec la preuve de chaque lien."
    corps = f"<style>{CSS_COMMUN}</style>" + PAGE.replace("@BASE@", S.BASE)
    graph = [S.site_ld(), {"@type": "WebPage", "name": titre, "url": S.BASE_URL + "/groupes/", "inLanguage": "fr-FR", "isPartOf": {"@id": S.BASE_URL + "/#site"}}]
    S.ecrire("groupes/index.html", S.page(titre, desc, "groupes/", corps, graph, "groupes/"))
    return S.BASE_URL + "/groupes/"
