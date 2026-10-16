"""Après la génération des pages :
1. liens vers les fiches entreprises : un lien /entreprise/<siren>-<nom>/ dont le nom ne correspond pas au dossier réel (« aci-d-n-rabourdin » au lieu de « aci-d-n ») est ramené au dossier existant ;
2. fiches.json : correspondance siren -> dossier, pour que la page 404 rattrape les anciens liens ;
3. 404.html aux couleurs du site (servie sous /plans-sociaux/)."""
import json, os, re, sys
H = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, H)
import commun as S
from commun import esc
PUB = os.path.join(H, "public")

def dossiers():
    d = {}
    base = os.path.join(PUB, "entreprise")
    for n in os.listdir(base):
        m = re.match(r"(\d{9})-", n)
        if m and os.path.isfile(os.path.join(base, n, "index.html")): d.setdefault(m.group(1), n)
    return d

RX = re.compile(r"(/entreprise/)(\d{9})-([a-z0-9-]*)(/)")
def corrige(texte, D, vus):
    def r(m):
        s, slug = m.group(2), m.group(3)
        ok = D.get(s)
        if not ok or ok == f"{s}-{slug}": return m.group(0)
        vus[0] += 1
        return m.group(1) + ok + m.group(4)
    return RX.sub(r, texte)

def liens():
    D = dossiers(); vus = [0]; fichiers = 0
    for racine, _, noms in os.walk(PUB):
        if os.sep + "entreprise" + os.sep in racine + os.sep and racine != os.path.join(PUB, "entreprise") and False: pass
        for nm in noms:
            if not nm.endswith((".html", ".json")) or nm in ("data.json", "explorer.json"): continue
            p = os.path.join(racine, nm)
            try: t = open(p, encoding="utf-8").read()
            except Exception: continue
            if "/entreprise/" not in t: continue
            avant = vus[0]; n = corrige(t, D, vus)
            if vus[0] != avant:
                tmp = p + ".tmp"; open(tmp, "w", encoding="utf-8").write(n); os.replace(tmp, p); fichiers += 1
    S.ecrire("fiches.json", json.dumps(D, separators=(",", ":")))
    print(f"liens fiches : {vus[0]} liens corrigés dans {fichiers} fichiers, {len(D)} fiches", file=sys.stderr)

def p404():
    corps = f"""<style>.e404{{max-width:62ch;margin:24px 0 10px}}.e404 .n{{font:700 clamp(4rem,16vw,9rem)/.9 "Barlow Condensed",sans-serif;color:var(--liq);letter-spacing:-.02em;margin:0}}
.e404 h1{{margin-top:6px}}.e404 ul{{list-style:none;padding:0;margin:14px 0;display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:8px}}
.e404 li{{margin:0}}.e404 li a{{display:block;border:1px solid var(--trait);background:var(--papier);border-top:3px solid var(--encre);padding:9px 12px;text-decoration:none;font-weight:600}}
.e404 li a span{{display:block;font-weight:400;color:var(--gris);font-size:14px}}#e404-msg{{display:none}}</style>
<div class="e404"><p class="n">404</p><h1>Cette page n'existe pas</h1>
<p class="chapo" id="e404-t">L'adresse est peut-être ancienne, ou la fiche n'a jamais été créée : seules les entreprises qui ont eu une annonce de licenciement ou une procédure collective en ont une.</p>
<p id="e404-msg" class="alerte"></p>
<ul><li><a href="{S.BASE}/">Carte et liste<span>les annonces de l'année sur la carte</span></a></li>
<li><a href="{S.BASE}/explorer/">Explorer<span>chercher une entreprise, un département</span></a></li>
<li><a href="{S.BASE}/cgt/">Liste noire CGT<span>état des lieux de la vérification</span></a></li>
<li><a href="{S.BASE}/faillites-entreprises/">Chiffres<span>faillites et plans sociaux</span></a></li></ul>
<p class="meta">Un lien qui devrait marcher ? <a href="mailto:{S.CONTACT}?subject=Lien%20cass%C3%A9">Dis-le-moi</a>, avec l'adresse de la page.</p></div>
<script>(function(){{var m=location.pathname.match(/\\/entreprise\\/(\\d{{9}})-/);if(!m)return;
fetch('{S.BASE}/fiches.json').then(function(r){{return r.json()}}).then(function(D){{var d=D[m[1]];if(d){{document.getElementById('e404-msg').style.display='block';document.getElementById('e404-msg').textContent='La fiche a changé d\\'adresse : redirection…';location.replace('{S.BASE}/entreprise/'+d+'/')}}}}).catch(function(){{}})}})()</script>"""
    html = S.page("Page introuvable", "Cette page n'existe pas.", "404.html", corps, None, "", robots="noindex")
    S.ecrire("404.html", html)

if __name__ == "__main__":
    liens(); p404()
