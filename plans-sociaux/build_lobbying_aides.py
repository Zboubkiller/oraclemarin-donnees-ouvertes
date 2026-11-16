#!/usr/bin/env python3
"""Piste « lobbying, puis soutien public » : pour les sociétés du radar des quotas dont les déclarations HATVP évoquent les quotas (SEQE) ou les aides publiques,
chronologie rapprochée des déclarations (année), des aides ADEME et contrats de soutien à la décarbonation (date), des quotas gratuits et des annonces de suppressions.
Formulation neutre : une succession dans le temps n'établit aucun lien de cause ; la HATVP ne publie que l'année de l'exercice, pas la date de l'action.
Sorties : /var/www/quotas-carbone/lobbying.html, lobbying.csv, lobbying.json."""
import csv, html, json, time
W = "/var/www/quotas-carbone/"
E = html.escape
D = json.load(open(W + "radar_full.json", encoding="utf-8"))["lignes"]
def m(x): return ("%.1f M€" % (x / 1e6)).replace(".", ",") if x >= 1e5 else ("%d k€" % round(x / 1e3) if x else "0 €")
def mois(d): return d[:7]
rows = []
for l in D:
    if not (l.get("lob_ets") or l.get("lob_aide")): continue
    ya = sorted({int(x["a"]) for x in l.get("lob_aide", [])}); ye = sorted({int(x["a"]) for x in l.get("lob_ets", [])})
    ref = min(ya) if ya else None
    aides = [{"d": t["d"], "m": t["m"], "o": t["o"], "type": "ADEME"} for t in l.get("top", [])] + [{"d": g["d"], "m": g["m"], "o": g["o"], "type": "contrat de soutien (appel d’offres décarbonation)"} for g in l.get("gpid", [])]
    apres = [a for a in aides if ref and int(a["d"][:4]) >= ref]; avant = [a for a in aides if ref and int(a["d"][:4]) < ref]
    ev = [{"d": "%s" % p["d"], "t": p["t"], "n": p.get("n"), "c": p.get("c"), "s": p.get("s")} for p in (l.get("ps") or [])]
    rows.append({"siren": l["siren"], "nom": l["nom"], "decl_aides": ya, "decl_quotas": ye, "depenses": l.get("lob_dep"), "lob_ets": l.get("lob_ets", []), "lob_aide": l.get("lob_aide", []),
                 "ademe_total": l.get("ademe") or 0, "ademe_n": l.get("ademe_n") or 0, "aides": sorted(aides, key=lambda a: a["d"]), "apres": sum(a["m"] for a in apres), "avant": sum(a["m"] for a in avant),
                 "ref": ref, "quotas": l["g"], "ps": ev})
rows.sort(key=lambda r: -(r["ademe_total"] + sum(a["m"] for a in r["aides"] if a["type"] != "ADEME")))
json.dump({"genere": time.strftime("%Y-%m-%d"), "lignes": rows}, open(W + "lobbying.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
with open(W + "lobbying.csv", "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f, delimiter=";"); w.writerow(["siren", "societe", "annees_declarations_aides", "annees_declarations_quotas", "depenses_lobbying_derniere_annee", "ademe_total_eur", "ademe_nb", "aides_datees_avant_1re_declaration_eur", "aides_datees_annee_declaration_ou_apres_eur", "quotas_gratuits_2021_2025"])
    for r in rows: w.writerow([r["siren"], r["nom"], " ".join(map(str, r["decl_aides"])), " ".join(map(str, r["decl_quotas"])), r["depenses"], r["ademe_total"], r["ademe_n"], r["avant"], r["apres"], r["quotas"]])

def carte(r):
    ev = []   # chronologie : (clé de tri, texte)
    for x in r["lob_aide"]: ev.append((x["a"] + "-00", "Déclaration HATVP %s, aides publiques : « %s »" % (x["a"], x["t"]), "lob"))
    for x in r["lob_ets"]: ev.append((x["a"] + "-00", "Déclaration HATVP %s, quotas (SEQE) : « %s »" % (x["a"], x["t"]), "lob"))
    for a in r["aides"]: ev.append((a["d"], "%s : %s, %s" % (mois(a["d"]), m(a["m"]), a["o"][:130]) + (" (%s)" % a["type"] if a["type"] != "ADEME" else " (ADEME)"), "aide"))
    for p in r["ps"]: ev.append((p["d"], "%s : %s%s%s (%s)" % (mois(p["d"]), p["t"], (", " + str(p["n"]) + " emplois") if p.get("n") else "", (", " + p["c"]) if p.get("c") else "", p.get("s")), "ps"))
    ev.sort(key=lambda t: t[0])
    li = "".join('<li class="%s"><small>%s</small></li>' % (c, E(t)) if False else '<li class="%s">%s</li>' % (c, E(t)) for k, t, c in ev)
    ordre = ""
    if r["ref"]:
        ordre = "<p><small>Rapprochement : %s d’aides datées avant l’année de la première déclaration évoquant des aides (%d), %s d’aides datées de cette année ou après (sur les aides listées).</small></p>" % (m(r["avant"]), r["ref"], m(r["apres"]))
    return ('<div class="l"><h2>%s <small>· SIREN %s</small></h2><p><small>Dépenses de lobbying déclarées (dernière année) : %s. ADEME : %d aides pour %s au total. Quotas gratuits 2021-2025 : %s.</small></p>%s<ul class="tl">%s</ul></div>'
            % (E(r["nom"]), r["siren"], E(r["depenses"] or "non renseignées"), r["ademe_n"], m(r["ademe_total"]), "{:,}".format(r["quotas"]).replace(",", " "), ordre, li))
cartes = "".join(carte(r) for r in rows)
H = '''<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Lobbying puis soutien public · Radar des quotas</title><link rel="icon" href="favicon.svg" type="image/svg+xml">
<meta name="robots" content="index,follow,max-image-preview:large"><link rel="canonical" href="https://oraclemarin.fr/quotas-carbone/lobbying.html">
<meta name="description" content="Industriels qui déclarent du lobbying sur les quotas de CO₂ ou les aides publiques, puis bénéficient d’aides de l’ADEME ou de contrats de décarbonation : chronologie sourcée, sans lien de cause affirmé.">
<style>:root{--encre:#14202B;--gris:#5C6772;--trait:#D6DBE0;--fond:#F4F6F8}*{box-sizing:border-box}body{margin:0;font:15px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;color:var(--encre);background:var(--fond)}a{color:inherit;text-underline-offset:3px}
header{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:10px 18px;background:#fff;border-bottom:1px solid var(--trait)}.btn{border:1px solid var(--encre);background:#fff;padding:6px 12px;border-radius:6px;font-weight:600;font-size:13.5px;text-decoration:none}
main{max-width:900px;margin:0 auto;padding:18px}h1{font-size:26px;line-height:1.15;margin:6px 0 8px}.intro{color:var(--gris)}.l{background:#fff;border:1px solid var(--trait);border-radius:8px;padding:12px 14px;margin:10px 0}.l h2{font-size:17px;margin:0 0 4px}.l p{margin:4px 0}small{color:var(--gris)}
.tl{list-style:none;margin:8px 0 0;padding:0 0 0 12px;border-left:3px solid var(--trait)}.tl li{margin:6px 0;padding-left:8px;font-size:14px}.tl .lob{border-left:3px solid #E8710A;margin-left:-15px;padding-left:12px}.tl .aide{border-left:3px solid #2E7D32;margin-left:-15px;padding-left:12px}.tl .ps{border-left:3px solid #B3261E;margin-left:-15px;padding-left:12px}
.leg span{display:inline-block;margin-right:14px;font-size:13px}.leg i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:4px}</style><script src="/om-bar.js?v=2" defer></script></head><body>
<header><a href="radar.html" class="btn">← Radar</a><span><a href="./" class="btn">La carte</a> <a href="arret.html" class="btn">Sites à l’arrêt</a></span></header><main>
<h1>Lobbying déclaré, puis soutien public</h1>
<p class="intro">%d industriels du radar des quotas déclarent à la HATVP des actions de lobbying portant sur les quotas de CO₂ (SEQE) ou sur les aides publiques. Leur chronologie est mise en regard des aides de l’ADEME, des contrats de soutien à la décarbonation et des annonces de suppressions. Mise à jour le %s.</p>
<div class="l"><h2>Comment lire</h2><p><small>La HATVP publie l’<b>année</b> de l’exercice et une fourchette de dépenses, pas la date ni le destinataire de chaque action. Une aide attribuée après une déclaration n’est pas la conséquence de cette déclaration : les aides résultent d’appels à projets ouverts à tous, instruits sur dossier. Cette page met des faits publics dans l’ordre du temps. Les aides listées sont les plus importantes retrouvées (jusqu’à trois par société), les montants totaux ADEME sont donnés à part ; les contrats de soutien sont des plafonds pluriannuels, pas des sommes versées.</small></p>
<p class="leg"><span><i style="background:#E8710A"></i>déclaration de lobbying</span><span><i style="background:#2E7D32"></i>aide ou contrat</span><span><i style="background:#B3261E"></i>annonce de suppressions</span></p></div>
%s
<p><small>Données : <a href="lobbying.json">lobbying.json</a> · <a href="lobbying.csv">lobbying.csv</a>. Sources : registre de la HATVP, aides de l’ADEME en données ouvertes, appel d’offres « Grands projets industriels de décarbonation », EUTL, base Plans sociaux et faillites.</small></p></main></body></html>''' % (len(rows), time.strftime("%d/%m/%Y"), cartes)
open(W + "lobbying.html", "w", encoding="utf-8").write(H)
print(len(rows), "sociétés")
