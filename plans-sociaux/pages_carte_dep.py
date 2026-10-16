"""Page « Carte par département » : carte interactive (Leaflet, aplats par département), indicateur et période au choix, panneau de chiffres concrets par département
(plans et fermetures annoncés, emplois, procédures collectives, plus gros plans, dernières annonces), classement et accès à l'outre-mer.
Les agrégats sont calculés dans le navigateur à partir des lignes embarquées (même dédoublonnage que le reste du site : un plan = un evenement_id, emplois = maximum annoncé)."""
import datetime as dt, json, os, shutil, sys
H = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, H)
import commun as S
esc, fr = S.esc, S.fr

GEO_SRC = "/var/www/boamp-service/services-publics/departements.geojson"
POP_SRC = "/var/www/boamp-service/services-publics/departements_stats.json"

def p_carte(EV, FICHES):
    out = os.path.join(H, "public", "carte-departements"); os.makedirs(out, exist_ok=True)
    geo = os.path.join(out, "departements.geojson")
    if not os.path.exists(geo) and os.path.exists(GEO_SRC): shutil.copy(GEO_SRC, geo)
    json.dump(S.DEPS, open(os.path.join(H, "public", "departements-noms.json"), "w", encoding="utf-8"), ensure_ascii=False)
    try: POP = json.load(open(POP_SRC, encoding="utf-8"))
    except Exception: POP = {}
    deps = {c: {"n": n, "pop": (POP.get(c) or {}).get("pop_2026"), "u": S.dep_url(c)} for c, n in S.DEPS.items()}
    sûr = ("siren_source", "siret_commune", "nom+dep")
    rows = []
    for e in EV:
        if e.get("sans_entreprise") or S.exclu_totaux(e) or e.get("entreprise") == e.get("titre") or not e.get("dep") or e["dep"] not in deps or not e.get("date"): continue
        if e.get("type") not in ("plan social", "fermeture", "liquidation", "redressement", "sauvegarde"): continue
        bod = e.get("source") == "BODACC"
        c = e.get("comptes") or {}
        benef = int(bool(c.get("profitable") and (not c.get("ca") or c["resultat_net"] / c["ca"] >= 0.03) and e["type"] in ("plan social", "fermeture")))
        aide = int(bool((e.get("proximite") or {}).get("n")))
        fu = FICHES.get(e.get("siren")) if (bod or e.get("lien") in sûr) else None
        rows.append([e["dep"], e["date"][:10], "b" if bod else "p", e["type"], e.get("entreprise") or "", e.get("emplois_min") if (bod or e.get("emplois_precision") == "annoncé") else None,
                     e.get("evenement_id") or e["id"], fu or "", ("" if fu or len(e.get("url") or "") > 140 else e.get("url")), benef, aide])
    annee = dt.date.today().year
    data = json.dumps({"rows": rows, "deps": deps, "annee": annee}, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    corps = (CSS + "<h1>Carte par département</h1>"
             '<p class="chapo">Où tombent les plans sociaux et les procédures collectives ? Choisissez un indicateur et une période, puis cliquez sur un département : les chiffres, les plus gros plans et les dernières annonces s\'affichent à côté de la carte.</p>'
             '<div class="cd-ctl" role="group" aria-label="Indicateur"><span class="cd-l">Indicateur</span><span id="cd-met"></span></div>'
             '<div class="cd-ctl" role="group" aria-label="Période"><span class="cd-l">Période</span><span id="cd-per"></span></div>'
             '<div class="cd-grille"><div><div id="cdmap" role="img" aria-label="Carte des départements de France métropolitaine, colorés selon l\'indicateur choisi"></div>'
             '<div id="cd-leg" class="cd-leg"></div><p id="cd-om" class="cd-om"></p></div>'
             '<aside id="cd-panel" aria-live="polite"></aside></div>'
             '<h2>Classement des départements</h2><p class="meta" id="cd-rtxt"></p><div class="tablo"><table id="cd-tab"><thead><tr><th>Département</th><th class="n">Plans</th><th class="n">Emplois annoncés</th><th class="n">Procédures</th><th class="n">Emplois / 100 000 hab.</th></tr></thead><tbody></tbody></table></div>'
             '<p><button type="button" id="cd-plus" class="cd-b">Voir tous les départements</button></p>'
             '<h2>Ce que mesurent ces chiffres</h2><ul class="cd-notes">'
             '<li><b>Plans sociaux et fermetures</b> : annonces relevées dans la liste noire de la CGT et dans la presse, rattachées au département du site concerné quand la source le précise (sinon au siège). Un même plan cité par plusieurs sources n\'est compté qu\'une fois.</li>'
             '<li><b>Emplois annoncés</b> : emplois supprimés ou menacés selon la source (nombre le plus élevé annoncé pour le plan). Un nombre n\'est pas toujours connu : un département peut compter des plans sans emplois renseignés.</li>'
             '<li><b>Procédures collectives</b> : liquidations, redressements et sauvegardes publiés au BODACC pour des entreprises de 50 salariés et plus ; les salariés indiqués sont l\'effectif de ces entreprises, pas des suppressions.</li>'
             '<li><b>Pour 100 000 habitants</b> : population estimée de 2026, pas un chiffre officiel. Les périodes ne couvrent pas les mêmes sources (BODACC depuis mars 2025, presse depuis janvier 2025, liste CGT depuis 2023).</li>'
             '<li>Ce site met des faits publics en regard et n\'établit aucun lien de cause. <a href="' + S.BASE + '/methode/">Méthode et limites</a>.</li></ul>'
             + "<script>" + JS.replace("__DATA__", data).replace("__BASE__", S.BASE) + "</script>")
    titre = "Carte par département : plans sociaux, fermetures et faillites en France"
    desc = "Carte interactive des départements : nombre de plans sociaux et de fermetures, emplois annoncés et procédures collectives, avec les plus gros plans et les dernières annonces de chaque département."
    graph = [S.site_ld(), {"@type": "WebPage", "name": titre, "url": S.BASE_URL + "/carte-departements/", "inLanguage": "fr-FR", "isPartOf": {"@id": S.BASE_URL + "/#site"}}]
    S.ecrire("carte-departements/index.html", S.page(titre, desc, "carte-departements/", corps, graph, "carte-departements/"))
    print(f"carte départements : {len(rows)} lignes embarquées", file=sys.stderr)
    return S.BASE_URL + "/carte-departements/"

CSS = """<link rel="stylesheet" href="../lib/leaflet.css"><style>
.cd-ctl{display:flex;flex-wrap:wrap;gap:8px 10px;align-items:center;margin:8px 0}.cd-l{font-weight:600;min-width:84px;font-size:15px}
.cd-b{font:600 15px Barlow,system-ui,sans-serif;padding:7px 13px;border:1px solid #C9CFD6;background:#F7F8F9;color:#17202E;cursor:pointer}
.cd-b[aria-pressed=true]{background:#17202E;color:#fff;border-color:#17202E}.cd-b:focus-visible{outline:3px solid #E8B21E;outline-offset:2px}
.cd-grille{display:grid;grid-template-columns:minmax(0,1.25fr) minmax(280px,1fr);gap:18px;margin:14px 0}@media(max-width:860px){.cd-grille{grid-template-columns:1fr}}
#cdmap{height:560px;background:#F3F5F7;border:1px solid #C9CFD6}@media(max-width:860px){#cdmap{height:420px}}
.cd-leg{display:flex;flex-wrap:wrap;gap:4px 12px;font-size:14px;margin:8px 0}.cd-leg i{display:inline-block;width:14px;height:14px;margin-right:5px;vertical-align:-2px;border:1px solid #C9CFD6}
.cd-om{font-size:15px;margin:6px 0}.cd-om .cd-b{padding:4px 9px;font-size:14px;margin:2px 4px 2px 0}
#cd-panel{background:#F7F8F9;border:1px solid #C9CFD6;border-top:3px solid #B8361E;padding:14px 18px 16px;font-size:16px}#cd-panel h2{margin:0 0 6px;font-size:1.5rem;border:0;padding:0}
#cd-panel h3{font-size:1rem;margin:14px 0 4px}#cd-panel ol,#cd-panel ul{margin:4px 0 6px;padding-left:20px}#cd-panel li{margin:4px 0;font-size:15.5px}
.cd-n{display:flex;flex-wrap:wrap;gap:10px 22px;margin:10px 0}.cd-n div{min-width:92px}.cd-n b{display:block;font:700 1.9rem/1 "Barlow Condensed",sans-serif}.cd-n small{font-size:14px;color:#4A5361}
.cd-notes{max-width:90ch;font-size:15.5px}.cd-notes li{margin:6px 0}#cd-tab tbody tr{cursor:pointer}#cd-tab tbody tr:hover{background:#FFF4D6}
</style><script src="../lib/leaflet.js"></script>"""

JS = r"""(function(){
const D=__DATA__,BASE='__BASE__';
const R=D.rows.map(r=>({dep:r[0],date:r[1],kind:r[2],type:r[3],nom:r[4],emp:r[5],eid:r[6],fu:r[7],url:r[8],benef:r[9],aide:r[10]}));
const iso=d=>d.toISOString().slice(0,10),fmt=n=>(n==null?'?':Math.round(n).toLocaleString('fr-FR'));
const PER={ytd:{l:'Depuis le 1er janvier '+D.annee,from:D.annee+'-01-01'},m12:{l:'12 derniers mois',from:iso(new Date(Date.now()-365*864e5))},all:{l:'Depuis 2023',from:'0000-00-00'}};
const MET={plans:{l:'Plans sociaux et fermetures',u:'plans'},emplois:{l:'Emplois annoncés',u:'emplois annoncés'},proc:{l:'Procédures collectives',u:'procédures'},hab:{l:'Emplois pour 100 000 hab.',u:'emplois / 100 000 hab.'}};
const TYPES={'plan social':'plan social',fermeture:'fermeture',liquidation:'liquidation',redressement:'redressement',sauvegarde:'sauvegarde'};
const COUL=['#FBEAE4','#F2C3B4','#E08E78','#C45A40','#8F2411'],VIDE='#EEF0F2';
let met='plans',per='ytd',sel=null,A={},geoCodes=new Set(),couches={};
const esc=s=>String(s==null?'':s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
function btns(id,obj,cur,fn){const z=document.getElementById(id);z.innerHTML='';Object.keys(obj).forEach(k=>{const b=document.createElement('button');b.type='button';b.className='cd-b';b.textContent=obj[k].l;b.setAttribute('aria-pressed',String(k===cur));b.onclick=()=>fn(k);z.appendChild(b)})}
function agreger(){const X={};Object.keys(D.deps).forEach(c=>X[c]={plans:0,emplois:0,proc:0,salproc:0,benef:0,aide:0,ent:new Set(),eids:{},recent:[]});
 R.forEach(r=>{if(r.date<PER[per].from)return;const a=X[r.dep];if(!a)return;a.recent.push(r);a.ent.add(r.nom.toLowerCase());
  if(r.kind==='b'){a.proc++;a.salproc+=r.emp||0}
  else if(r.eid in a.eids){if((r.emp||0)>a.eids[r.eid].emp)a.eids[r.eid].emp=r.emp||0}
  else{a.eids[r.eid]={emp:r.emp||0,r:r};a.plans++;if(r.benef)a.benef++;if(r.aide)a.aide++}});
 Object.keys(X).forEach(c=>{const a=X[c];const L=Object.values(a.eids);a.emplois=L.reduce((s,k)=>s+k.emp,0);a.top=L.sort((x,y)=>y.emp-x.emp).slice(0,5).map(k=>Object.assign({},k.r,{emp:k.emp}));a.recent.sort((x,y)=>y.date.localeCompare(x.date));a.recent=a.recent.slice(0,6);
  const p=D.deps[c].pop;a.hab=p?a.emplois/p*100000:0});
 return X}
const val=c=>{const a=A[c];return a?a[met]:0};
function seuils(){const v=Object.keys(A).filter(c=>geoCodes.has(c)).map(val).filter(x=>x>0).sort((a,b)=>a-b);if(!v.length)return[];return[0.2,0.4,0.6,0.8].map(q=>v[Math.min(v.length-1,Math.floor(q*v.length))])}
function coul(x,S){if(!(x>0))return VIDE;let i=0;while(i<S.length&&x>S[i])i++;return COUL[Math.min(i,4)]}
function legende(S){const z=document.getElementById('cd-leg');const u=MET[met].u;const b=[0].concat(S);let h='<span><i style="background:'+VIDE+'"></i>aucun</span>';
 COUL.forEach((c,i)=>{const lo=i===0?1:Math.floor(S[i-1])+1,hi=S[i]!=null?Math.floor(S[i]):null;h+='<span><i style="background:'+c+'"></i>'+(hi==null?'plus de '+fmt(lo-1):(lo>=hi?fmt(hi):fmt(lo)+' à '+fmt(hi)))+'</span>'});
 z.innerHTML=h+'<span class="meta">('+esc(u)+', '+esc(PER[per].l.toLowerCase())+')</span>'}
function style(c){const S=seuils();return{fillColor:coul(val(c),S),fillOpacity:.95,color:c===sel?'#17202E':'#fff',weight:c===sel?3:.8}}
function panneau(){const z=document.getElementById('cd-panel');
 if(!sel){const t=Object.values(A).reduce((s,a)=>({plans:s.plans+a.plans,emplois:s.emplois+a.emplois,proc:s.proc+a.proc}),{plans:0,emplois:0,proc:0});
  const top=Object.keys(A).filter(c=>val(c)>0).sort((x,y)=>val(y)-val(x)).slice(0,5);
  z.innerHTML='<h2>France entière</h2><p class="meta">'+esc(PER[per].l)+'</p><div class="cd-n"><div><b>'+fmt(t.plans)+'</b><small>plans et fermetures annoncés</small></div><div><b>'+fmt(t.emplois)+'</b><small>emplois annoncés</small></div><div><b>'+fmt(t.proc)+'</b><small>procédures collectives</small></div></div>'
   +'<h3>Les 5 départements les plus touchés ('+esc(MET[met].l.toLowerCase())+')</h3><ol>'+top.map(c=>'<li><button type="button" class="cd-b" data-c="'+c+'">'+esc(D.deps[c].n)+' ('+c+')</button> '+fmt(val(c))+' '+esc(MET[met].u)+'</li>').join('')+'</ol><p class="meta">Cliquez sur un département de la carte pour voir le détail.</p>';return}
 const a=A[sel],d=D.deps[sel];
 const li=r=>'<li>'+(r.fu?'<a href="'+esc(r.fu)+'">'+esc(r.nom)+'</a>':(r.url?'<a href="'+esc(r.url)+'" rel="noopener">'+esc(r.nom)+'</a>':esc(r.nom)))+' <span class="meta">('+esc(TYPES[r.type]||r.type)+', '+esc(r.date)+(r.emp?', '+fmt(r.emp)+(r.kind==='b'?' salariés':' emplois'):'')+')</span></li>';
 z.innerHTML='<h2>'+esc(d.n)+' ('+sel+')</h2><p class="meta">'+esc(PER[per].l)+'</p><div class="cd-n"><div><b>'+fmt(a.plans)+'</b><small>plans et fermetures annoncés</small></div><div><b>'+fmt(a.emplois)+'</b><small>emplois annoncés</small></div><div><b>'+fmt(a.proc)+'</b><small>procédures collectives</small></div></div>'
  +'<p style="font-size:15.5px;margin:6px 0">'+fmt(a.ent.size)+' entreprise'+(a.ent.size>1?'s':'')+' concernée'+(a.ent.size>1?'s':'')+(a.proc?'  ; les procédures touchent des entreprises de '+fmt(a.salproc)+' salariés au total':'')+'.'
  +(a.plans?' Parmi les plans : '+fmt(a.benef)+' avec des derniers comptes bénéficiaires (marge d\'au moins 3 %), '+fmt(a.aide)+' avec une aide publique dans les 24 mois précédents.':'')+'</p>'
  +(a.top.length?'<h3>Les plus gros plans annoncés</h3><ol>'+a.top.map(li).join('')+'</ol>':'<p>Aucun plan annoncé sur cette période.</p>')
  +(a.recent.length?'<h3>Dernières annonces et procédures</h3><ul>'+a.recent.map(li).join('')+'</ul>':'')
  +'<p><a href="'+esc(d.u)+'">Voir la page du département</a> · <button type="button" class="cd-b" data-c="">Revenir à la France entière</button></p>'}
function tableau(tout){const cs=Object.keys(A).sort((x,y)=>val(y)-val(x)||D.deps[x].n.localeCompare(D.deps[y].n,'fr'));const L=tout?cs:cs.slice(0,15);
 document.getElementById('cd-rtxt').textContent='Classé selon : '+MET[met].l.toLowerCase()+', '+PER[per].l.toLowerCase()+'. Cliquez sur une ligne pour afficher le département.';
 document.querySelector('#cd-tab tbody').innerHTML=L.map(c=>{const a=A[c];return'<tr data-c="'+c+'"><td><strong>'+c+' · '+esc(D.deps[c].n)+'</strong></td><td class="n">'+fmt(a.plans)+'</td><td class="n">'+fmt(a.emplois)+'</td><td class="n">'+fmt(a.proc)+'</td><td class="n">'+fmt(a.hab)+'</td></tr>'}).join('');
 document.getElementById('cd-plus').style.display=tout?'none':''}
function maj(){A=agreger();btns('cd-met',MET,met,k=>{met=k;maj()});btns('cd-per',PER,per,k=>{per=k;maj()});
 const S=seuils();legende(S);Object.keys(couches).forEach(c=>{couches[c].setStyle(style(c));couches[c].setTooltipContent(D.deps[c].n+' ('+c+') : '+fmt(val(c))+' '+MET[met].u)});panneau();tableau(tout);
 try{history.replaceState(null,'','#'+['m='+met,'p='+per].concat(sel?['d='+sel]:[]).join('&'))}catch(e){}}
let tout=false;
function choisir(c){sel=c||null;Object.keys(couches).forEach(k=>couches[k].setStyle(style(k)));panneau();try{history.replaceState(null,'','#'+['m='+met,'p='+per].concat(sel?['d='+sel]:[]).join('&'))}catch(e){}if(sel&&couches[sel])couches[sel].bringToFront()}
document.addEventListener('click',e=>{const b=e.target.closest('[data-c]');if(b&&b.closest('#cd-panel,#cd-om')){choisir(b.dataset.c)}const tr=e.target.closest('#cd-tab tr[data-c]');if(tr)choisir(tr.dataset.c)});
document.getElementById('cd-plus').onclick=()=>{tout=true;tableau(true)};
const h=new URLSearchParams(location.hash.slice(1));if(MET[h.get('m')])met=h.get('m');if(PER[h.get('p')])per=h.get('p');if(D.deps[h.get('d')])sel=h.get('d');
const carte=L.map('cdmap',{scrollWheelZoom:false,zoomSnap:.25,attributionControl:false}).setView([46.6,2.4],5.4);
fetch('departements.geojson').then(r=>r.json()).then(g=>{A=agreger();
 L.geoJSON(g,{style:f=>({fillColor:VIDE,fillOpacity:.95,color:'#fff',weight:.8}),onEachFeature:(f,l)=>{const c=f.properties.code;geoCodes.add(c);couches[c]=l;l.bindTooltip(D.deps[c]?D.deps[c].n:c,{sticky:true});l.on('click',()=>choisir(c))}}).addTo(carte);
 const om=Object.keys(D.deps).filter(c=>!geoCodes.has(c)&&(c.startsWith('97')));document.getElementById('cd-om').innerHTML=om.length?'Outre-mer : '+om.map(c=>'<button type="button" class="cd-b" data-c="'+c+'">'+esc(D.deps[c].n)+'</button>').join(' '):'';
 maj()}).catch(()=>{document.getElementById('cdmap').innerHTML='<p class="meta" style="padding:20px">La carte n\'a pas pu se charger : le classement ci-dessous reste disponible.</p>';A=agreger();maj()});
})();"""
