(function(){
const $=id=>document.getElementById(id);
const esc=s=>String(s==null?'':s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const box=$('lg'),cv=document.createElement('canvas'),ctx=cv.getContext('2d');box.insertBefore(cv,box.firstChild);
let W=0,H=0,dpr=window.devicePixelRatio||1;
let D=null,noeuds=[],liens=[],sim=null,tr=d3.zoomIdentity,sel=null,vois=new Set(),corresp=new Set(),flotte=true;
function taille(n){const m=n.eff&&n.eff[0]!=null?(n.eff[0]+(n.eff[1]||n.eff[0]))/2:null;return m==null?4:Math.min(30,3+.55*Math.sqrt(m))}
function couleur(n){const a=n.annonces>0,p=!!n.proc;return a&&p?'#7A1B12':p?'#B8361E':a?'#E07B28':'#98A2B3'}
function dim(){W=box.clientWidth;H=box.clientHeight;cv.width=W*dpr;cv.height=H*dpr;ctx.setTransform(dpr,0,0,dpr,0,0);dessiner()}
addEventListener('resize',dim);
function actifs(){const ind=$('indice').checked,iso=$('isoles').checked;
 const L=D.liens.filter(l=>ind||l.force!=='indice');
 const deg=new Set();L.forEach(l=>{deg.add(l.s);deg.add(l.t)});
 const ev=id=>{const o=D.index[id]||{};return o.annonces>0||!!o.proc};
 const N=D.noeuds.filter(n=>deg.has(n.id)&&(iso||ev(n.id)||L.some(l=>(l.s===n.id&&ev(l.t))||(l.t===n.id&&ev(l.s)))));
 const ids=new Set(N.map(n=>n.id)),L2=L.filter(l=>ids.has(l.s)&&ids.has(l.t));
 const mini=+$('mini').value,par=new Map();const trouve=x=>{while(par.get(x)!==x){par.set(x,par.get(par.get(x)));x=par.get(x)}return x};
 N.forEach(n=>par.set(n.id,n.id));L2.forEach(l=>{const a=trouve(l.s),b=trouve(l.t);if(a!==b)par.set(a,b)});
 const tc=new Map();N.forEach(n=>{const r=trouve(n.id);tc.set(r,(tc.get(r)||0)+1)});
 const N3=N.filter(n=>tc.get(trouve(n.id))>=mini),ids3=new Set(N3.map(n=>n.id));
 return{N:N3,L:L2.filter(l=>ids3.has(l.s)&&ids3.has(l.t))}}
function construire(){const{N,L}=actifs();
 const anc=new Map(noeuds.map(n=>[n.id,n]));
 noeuds=N.map(n=>{const o=anc.get(n.id);return o?Object.assign(o,n):Object.assign({},n,{x:W/2+(Math.random()-.5)*W*.6,y:H/2+(Math.random()-.5)*H*.6})});
 const idx=new Map(noeuds.map(n=>[n.id,n]));
 liens=L.map(l=>({source:idx.get(l.s),target:idx.get(l.t),force:l.force,preuve:l.preuve}));
 noeuds.forEach(n=>n.r=taille(n));
 if(sim)sim.stop();
 sim=d3.forceSimulation(noeuds).force('lien',d3.forceLink(liens).distance(l=>l.force==='fort'?55:l.force==='probable'?85:120).strength(l=>l.force==='fort'?.5:.2))
  .force('charge',d3.forceManyBody().strength(n=>-40-n.r*3).distanceMax(300)).force('centre',d3.forceCenter(W/2,H/2).strength(.04))
  .force('x',d3.forceX(W/2).strength(.012)).force('y',d3.forceY(H/2).strength(.012)).force('collision',d3.forceCollide(n=>n.r+3))
  .force('flotte',()=>{if(!flotte)return;for(const n of noeuds){if(n.fx!=null)continue;n.vx+=(Math.random()-.5)*.09;n.vy+=(Math.random()-.5)*.09}})
  .alphaDecay(.02).alphaTarget(flotte?.04:0).on('tick',dessiner);
 $('nb').textContent=noeuds.length+' sociétés · '+liens.length+' liens';recherche();clearTimeout(window._cad);window._cad=setTimeout(cadrer,1800)}
function cadrer(){if(!noeuds.length)return;let x0=1e9,y0=1e9,x1=-1e9,y1=-1e9;noeuds.forEach(n=>{if(n.x==null)return;x0=Math.min(x0,n.x-n.r);y0=Math.min(y0,n.y-n.r);x1=Math.max(x1,n.x+n.r);y1=Math.max(y1,n.y+n.r)});
 const k=Math.min(2,.92*Math.min(W/(x1-x0||1),H/(y1-y0||1)));d3.select(cv).transition().duration(600).call(zoom.transform,d3.zoomIdentity.translate(W/2-k*(x0+x1)/2,H/2-k*(y0+y1)/2).scale(k))}
function dessiner(){ctx.save();ctx.clearRect(0,0,W,H);ctx.translate(tr.x,tr.y);ctx.scale(tr.k,tr.k);
 const fond=sel||corresp.size;
 for(const l of liens){const a=l.source,b=l.target;if(a.x==null||b.x==null)continue;
  const actif=!fond||(sel&&(a===sel||b===sel))||(corresp.size&&corresp.has(a.id)&&corresp.has(b.id));
  ctx.globalAlpha=actif?1:.08;ctx.beginPath();ctx.moveTo(a.x,a.y);ctx.lineTo(b.x,b.y);
  ctx.strokeStyle=l.force==='indice'?'#B9BEC7':'#4A5361';ctx.lineWidth=(l.force==='fort'?1.8:l.force==='probable'?1.2:.7)/tr.k**.3;
  ctx.setLineDash(l.force==='probable'?[5,4]:[]);ctx.stroke()}
 ctx.setLineDash([]);
 for(const n of noeuds){if(n.x==null)continue;const actif=!fond||n===sel||vois.has(n.id)||corresp.has(n.id);
  ctx.globalAlpha=actif?1:.12;ctx.beginPath();ctx.arc(n.x,n.y,n.r,0,6.2832);ctx.fillStyle=couleur(n);ctx.fill();
  ctx.lineWidth=n===sel?3:1.2;ctx.strokeStyle=n.cessee?'#17202E':'#fff';ctx.setLineDash(n.cessee?[2,2]:[]);ctx.stroke();ctx.setLineDash([])}
 ctx.globalAlpha=1;ctx.textAlign='center';
 for(const n of noeuds){if(n.x==null)continue;const gros=n.r>=17,actif=n===sel||vois.has(n.id)||corresp.has(n.id)||(!fond&&(gros||tr.k>2.6));
  if(!actif)continue;const t=(n.cite||n.nom||'').slice(0,26);ctx.font=(n===sel?'600 ':'')+Math.max(10,12/tr.k**.5)+'px system-ui';
  ctx.lineWidth=3;ctx.strokeStyle='rgba(255,255,255,.92)';ctx.strokeText(t,n.x,n.y+n.r+12);ctx.fillStyle='#17202E';ctx.fillText(t,n.x,n.y+n.r+12)}
 ctx.restore()}
function sous(x,y){const p=tr.invert([x,y]);let b=null,d=1e9;for(const n of noeuds){const dd=(n.x-p[0])**2+(n.y-p[1])**2;if(dd<=(n.r+4/tr.k)**2&&dd<d){d=dd;b=n}}return b}
function choisir(n){sel=n;vois=new Set();if(n)liens.forEach(l=>{if(l.source===n)vois.add(l.target.id);if(l.target===n)vois.add(l.source.id)});panneau();dessiner()}
function panneau(){const p=$('lg-info');if(!sel){p.style.display='none';return}
 const n=sel,L=liens.filter(l=>l.source===n||l.target===n).sort((a,b)=>['fort','probable','indice'].indexOf(a.force)-['fort','probable','indice'].indexOf(b.force));
 p.innerHTML=`<button type="button" id="lg-x" aria-label="Fermer">×</button><h2>${esc(n.nom)}</h2><div style="color:#5A6371;font-size:13px">SIREN ${esc(n.id)}${n.cessee?' · société cessée':''}${n.eff?' · '+(n.eff[0]||0)+'–'+(n.eff[1]||'?')+' salariés':' · effectif non connu'}</div>
 ${n.cite?'<p style="font-size:13px;color:#5A6371">Nom cité dans la presse : '+esc(n.cite)+'</p>':''}
 <p style="font-size:13px;margin:6px 0">${n.annonces?n.annonces+' annonce(s)'+(n.emplois?', '+n.emplois+' emplois annoncés':''):'aucune annonce dans le tracker'}${n.proc?' · dernière procédure : '+esc(n.proc):''}</p>
 <p style="font-size:13px;margin:6px 0">${n.url?'<a href="'+esc(n.url)+'">Voir la fiche</a> · ':''}<a href="https://annuaire-entreprises.data.gouv.fr/entreprise/${esc(n.id)}" target="_blank" rel="noopener">annuaire</a></p>
 <b style="font-size:13px">${L.length} lien(s)</b><ul>${L.map(l=>{const o=l.source===n?l.target:l.source;return `<li><a href="#${esc(o.id)}" data-g="${esc(o.id)}">${esc(o.nom)}</a> <span style="color:#5A6371">[${l.force}] ${esc(l.preuve)}</span></li>`}).join('')}</ul>`;
 p.style.display='block';$('lg-x').onclick=()=>choisir(null);
 p.querySelectorAll('a[data-g]').forEach(a=>a.onclick=e=>{e.preventDefault();const o=noeuds.find(x=>x.id===a.dataset.g);if(o){choisir(o);centrer(o)}})}
function centrer(n){const k=Math.max(tr.k,1.2);d3.select(cv).transition().duration(450).call(zoom.transform,d3.zoomIdentity.translate(W/2-n.x*k,H/2-n.y*k).scale(k))}
function recherche(){const q=$('q').value.trim().toLowerCase();corresp=new Set();if(q.length>=2)noeuds.forEach(n=>{if(((n.nom||'')+' '+(n.cite||'')+' '+n.id).toLowerCase().includes(q))corresp.add(n.id)});dessiner()}
$('q').addEventListener('input',recherche);$('q').addEventListener('keydown',e=>{if(e.key==='Enter'&&corresp.size){const n=noeuds.find(x=>corresp.has(x.id));if(n){choisir(n);centrer(n)}}});
['indice','isoles','mini'].forEach(i=>$(i).addEventListener('change',()=>{sel=null;panneau();construire()}));
$('flotte').addEventListener('change',e=>{flotte=e.target.checked;sim.alphaTarget(flotte?.04:0).alpha(.3).restart()});
$('cad').onclick=cadrer;
const zoom=d3.zoom().scaleExtent([.15,6]).filter(e=>!(e.type==='mousedown'&&sous(e.offsetX,e.offsetY))&&!(e.type==='touchstart'&&e.touches.length===1&&sous(e.touches[0].clientX-cv.getBoundingClientRect().left,e.touches[0].clientY-cv.getBoundingClientRect().top))&&(e.type!=='wheel'||e.ctrlKey||e.metaKey||true)).on('zoom',e=>{tr=e.transform;dessiner()});
d3.select(cv).call(zoom).on('dblclick.zoom',null);
const drag=d3.drag().subject(e=>{const n=sous(e.x,e.y);return n?{n,x:e.x,y:e.y}:null})
 .on('start',e=>{if(!e.active)sim.alphaTarget(.25).restart();e.subject.n.fx=e.subject.n.x;e.subject.n.fy=e.subject.n.y;choisir(e.subject.n)})
 .on('drag',e=>{const p=tr.invert([e.x,e.y]);e.subject.n.fx=p[0];e.subject.n.fy=p[1]})
 .on('end',e=>{if(!e.active)sim.alphaTarget(flotte?.04:0)});
d3.select(cv).call(drag);
cv.addEventListener('dblclick',e=>{const n=sous(e.offsetX,e.offsetY);if(n){n.fx=null;n.fy=null;sim.alpha(.3).restart()}});
cv.addEventListener('click',e=>{const n=sous(e.offsetX,e.offsetY);if(!n&&sel)choisir(null)});
function ouvrirHash(){const h=(location.hash||'').replace('#','');if(!/^\d{9}$/.test(h))return;
 let n=noeuds.find(x=>x.id===h);
 if(!n){$('mini').value='2';$('isoles').checked=true;$('indice').checked=true;construire();n=noeuds.find(x=>x.id===h)}
 if(n)setTimeout(()=>{choisir(n);centrer(n)},2200)}
fetch('@BASE@/liens.json').then(r=>r.json()).then(d=>{D=d;D.index={};d.noeuds.forEach(n=>D.index[n.id]=n);dim();construire();ouvrirHash()});
})();
