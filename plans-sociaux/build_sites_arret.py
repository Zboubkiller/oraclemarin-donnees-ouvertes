#!/usr/bin/env python3
"""Sites à quotas gratuits sans émissions (ou presque) : allocation gratuite qui continue alors que les émissions vérifiées sont nulles ou en chute.
Source : data.json de la carte (EUTL, Zenodo). Contrôles automatiques de l'arrêt : émissions, ICPE (Géorisques), annonces de fermeture, registre et BODACC (sociétés à site unique).
Sorties : /var/www/quotas-carbone/arret.json, arret.csv, arret.html. Formulation neutre : « alloué alors que… », jamais « revendu »."""
import csv, html, json, os, re, sys, time, urllib.parse, urllib.request
W = "/var/www/quotas-carbone/"
CACHE = "./work/arret_cache.json"
UA = {"User-Agent": "tracker-plans-sociaux/0.9 (+https://oraclemarin.fr/quotas-carbone/)"}
PRIX = (65, 80)
d = json.load(open(W + "data.json", encoding="utf-8")); AN = d["meta"]["annees"]; INST = d["inst"]
try: cache = json.load(open(CACHE, encoding="utf-8"))
except Exception: cache = {}
WEB = {   # constats de la recherche sur le web (sources citées), par installation
 "FR_689": [("Rapport d’inspection Géorisques : four sous cocon depuis 2021, démantèlement du four évoqué ; le site fabrique désormais du ciment à partir de clinker apporté par la route (centre de broyage, activité hors quotas). Le site n’est donc pas à l’arrêt complet.", "https://georisques.gouv.fr/webappReport/ws/installations/inspection/TdiGJsWOaJnAIhyW4Xa9oyqomy3JMrCa"),
            ("Global Energy Monitor : transformation en centre de broyage en 2022 (carrière de Guitrancourt épuisée).", "https://www.gem.wiki/Gargenville_Cement_Plant")],
 "FR_204211": [("L’atelier d’ammoniac est à l’arrêt depuis début 2025 selon la presse ; en mars 2026 LAT Nitrogen a annoncé la fin de la production d’ammonitrate, d’urée et d’AdBlue, avec cessation définitive en août et reconversion en plateforme logistique (115 salariés). Écart non expliqué : les émissions vérifiées sont déjà tombées de 213 000 t (2022) à 33 000 t par an dès 2023, alors que l’allocation gratuite est restée à 275 020 quotas par an.", "https://www.terre-net.fr/engrais/article/897028/a-grandpuits-l-usine-lat-nitrogen-produisant-de-l-ammonitrate-et-de-l-uree-va-fe"),
            ("Le site, ex-Borealis, a changé de raison sociale en LAT Nitrogen (lettre préfectorale du 5 octobre 2023) ; l’usine a aussi marqué un arrêt d’environ deux mois pendant la crise énergétique de 2022 (Argus, cité par Terre-net).", "https://www.terre-net.fr/marche-agricole/actualite-marche-agricole/article/plus-de-la-moitie-des-lignes-de-production-d-ammoniac-en-europe-sont-a-l-arret-1395-220740.html")],
 "FR_597": [("Smurfit Kappa a présenté fin 2023 un plan de fermeture de la papeterie Alfa d’Avignon (Le Pontet, environ 60 salariés, 75 000 t/an de papier recyclé) ; un rapport d’inspection de décembre 2023 mentionne le projet de fermeture. Émissions vérifiées nulles en 2024 et 2025, allocation maintenue à 15 846 quotas par an.", "https://www.paper-world.com/en/newsdetail/smurfit-kappa-plans-to-close-a-french-paper-mill")],
 "FR_77": [("Papeterie de Bègles (Etex) : arrêtée depuis fin mars 2021, fermeture décidée en janvier 2021 faute de repreneur ; site repris ensuite par Global Hygiène. L’allocation a été ramenée à 85 quotas par an (ajustement visible), après 6 278 en 2022.", "https://www.euwid-paper.com/news/markets/papeterie-de-begles-in-france-will-be-closed/")],
 "FR_232": [("Tereos a annoncé le 29 août 2023 la fermeture de la féculerie d’Haussimont (62 salariés), faute de repreneur. Émissions vérifiées de 322 t en 2024 et zéro en 2025 ; allocation de 6 461 quotas en 2024 et 2025.", "https://www.pleinchamp.com/actualite/tereos-annonce-la-fermeture-de-sa-feculerie-d-haussimont")],
 "FR_1016": [("Conversion de la centrale de Bois-Rouge du charbon à la biomasse (bagasse, bois), annoncée comme une baisse d’environ 84 % des émissions directes ; la biomasse n’est pas comptée comme émission au registre. Il s’agit d’un changement de combustible, pas d’un arrêt.", "https://echanges.dila.gouv.fr/OPENDATA/AMF/MKW/2020/12/FCMKW134661_20201208.pdf")],
 "FR_204218": [("Prodeva (groupe Cristal Union) a remplacé le lignite par deux foyers biomasse bois sur son site de Vatry : la baisse des émissions comptées vient d’un changement de combustible, pas d’un arrêt.", "https://www.reussir.fr/prodeva-passe-au-100-biomasse-et-plaide-pour-le-developpement-des-surfaces-de-luzerne")],
 "FR_205636": [("Luzéal Recy : deux lignes de séchage toujours en activité (inspection du 17 septembre 2024) ; le site est raccordé depuis 2023 au réseau de chaleur de Châlons-en-Champagne, ce qui explique la chute des émissions comptées.", "")],
 "FR_204861": [("UCDV Saussay-la-Campagne : site en activité (déshydratation de luzerne de mai à octobre, pulpe de betterave de septembre à janvier) ; inspection de novembre 2025 (DREAL Normandie). Les émissions nulles ne signifient pas un arrêt ; origine à établir (combustible biomasse ?).", "")],
 "FR_211": [("Papeteries de Giroux : site actif (environ 45 salariés, papier pour carton ondulé, inspection de janvier 2025) ; chaufferie biomasse bois depuis 2007. Baisse des émissions comptées non liée à un arrêt.", "")],
 "FR_1062": [("Papeteries Palm : l’usine de Descartes dispose d’une cogénération au gaz exploitée par Descartes Biomasse Industrie (arrêté préfectoral du 2 juin 2017) ; aucun arrêt trouvé.", "https://www.indre-et-loire.gouv.fr/index.php/contenu/telechargement/14079/104055/file/descartes-papeteries-palm.pdf")],
 "FR_902": [("Norpaper a racheté la cogénération au gaz de Blendecques à Boralex en 2021 et voulait maintenir son exploitation ; site classé en exploitation avec titre. Aucun arrêt trouvé.", "https://www.euwid-paper.com/news/companies/news-in-brief-norpaper-acquires-cogeneration-plant-in-blendecques-120521/")],
 "FR_1091": [("Fermeture de Beffes et de Villiers-au-Bouin annoncée en avril 2024 pour octobre 2025 (environ 170 emplois pour les deux sites).", "https://cemnet.com/News/story/176747/heidelberg-materials-france-to-close-two-plants.html"),
             ("Rapports d’inspection des installations classées (Géorisques) : four arrêté le 23 août 2024 ; visite du 15 décembre 2025 : four à l’arrêt, n’ayant fonctionné que quelques semaines selon l’exploitant. L’allocation 2025 est pourtant restée à 270 381 quotas.", "")],
 "FR_936": [("Fours float de Boussois : la ligne B1 est à l’arrêt depuis 2020 (redémarrage possible d’ici 2030 selon AGC) et la ligne B2 a été arrêtée à partir du 10 octobre 2022 à cause de la crise énergétique. Les émissions vérifiées sont de 816 t (2023), 129 t (2024) et 138 t (2025), contre 98 177 quotas gratuits alloués chaque année.", "https://www.glass-international.com/news/energy-crisis-forces-french-glass-furnace-to-close"),
            ("Le redémarrage possible de la ligne B1 pourrait expliquer que l’allocation soit maintenue : question à poser à la DGEC (statut d’arrêt temporaire ou définitif).", "")],
 "FR_46": [("Le site d’Amiens (ex-Metex Nøøvistago), seul producteur européen de lysine, a été menacé de liquidation puis repris par Avril avec le fonds SPI/Bpifrance (315 emplois préservés) ; la presse ne décrit pas d’arrêt définitif. La chute des émissions vérifiées (21 700 t en 2018 à 146 t en 2025) n’est pas expliquée par les sources trouvées.", "https://www.agtechnavigator.com/Article/2024/07/17/avril-group-takes-over-metex-noovistago")],
}
NIV = {"FR_1091": "confirme", "FR_936": "confirme", "FR_204211": "probable", "FR_46": "actif", "FR_597": "confirme", "FR_77": "confirme", "FR_232": "confirme", "FR_1016": "actif", "FR_204218": "actif", "FR_205636": "actif", "FR_204861": "actif", "FR_211": "actif", "FR_1062": "non_etabli", "FR_902": "non_etabli"}   # verdicts établis après recherche web (sources dans WEB)
def get(u):
    for k in range(3):
        try: return json.loads(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60).read())
        except Exception: time.sleep(2 + 2 * k)
def externe(s):
    c = cache.get(s)
    if c and c.get("maj") == time.strftime("%Y-%m-%d"): return c
    o = {"maj": time.strftime("%Y-%m-%d"), "registre": {}, "bodacc": []}
    r = ((get("https://recherche-entreprises.api.gouv.fr/search?q=%s&per_page=1" % s) or {}).get("results") or [{}])[0]
    if r.get("siren") == s: o["registre"] = {"nom": r.get("nom_complet"), "etat": r.get("etat_administratif"), "cessation": r.get("date_fermeture")}
    b = get("https://bodacc-datadila.opendatasoft.com/api/explore/v2.1/catalog/datasets/annonces-commerciales/records?" + urllib.parse.urlencode(
        {"where": 'registre like "%s"' % s, "limit": 50, "order_by": "dateparution desc", "select": "dateparution,familleavis_lib,jugement"})) or {}
    for x in b.get("results", []):
        j = x.get("jugement")
        try: j = json.loads(j) if isinstance(j, str) else j
        except Exception: j = {}
        n = (j or {}).get("nature")
        if n and re.search(r"liquidation|cession|redressement|sauvegarde", n, re.I) or x.get("familleavis_lib") == "Radiations": o["bodacc"].append({"paru": x["dateparution"], "nature": n or x["familleavis_lib"], "date": (j or {}).get("date")})
    cache[s] = o; time.sleep(0.4)
    return o
import sqlite3, unicodedata, zipfile
EU = "/opt/donnees-externes/eutl/"
def norm(x):
    x = unicodedata.normalize("NFD", (x or "").lower()); x = "".join(c for c in x if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", x).strip()
def transferts(ids):
    """Transactions publiques du registre de l'Union (transactions.csv, publiées avec un délai de plusieurs années) pour les comptes des installations donnees."""
    f = "./work/transactions.csv"
    if not os.path.exists(f):
        try: zipfile.ZipFile(EU + "eutl_data_package.zip").extract("transactions.csv", "./work/")
        except Exception: return {}, ""
    acc = {}
    for r in csv.DictReader(open(EU + "link_installation_account.csv", encoding="utf-8")):
        if r["installation_id"] in ids: acc.setdefault(r["account_id"], r["installation_id"])
    A = {r["id"]: r for r in csv.DictReader(open(EU + "accounts.csv", encoding="utf-8"))}
    out = {i: [] for i in ids}; mx = ""
    for r in csv.DictReader(open(f, encoding="utf-8")):
        if r["date"] > mx: mx = r["date"]
        o = r["transferring_account_id"]
        if o in acc and r["transaction_type"] not in ("10-2", "10-36") and r["date"] >= "2021-01-01":
            a2 = A.get(r["acquiring_account_id"], {})
            out[acc[o]].append({"date": r["date"][:10], "type": r["transaction_type"], "unites": r["unit_type_description"], "n": int(float(r["amount"] or 0)),
                                "vers": a2.get("name") or r["acquiring_account_id"], "compte": a2.get("account_type") or "", "pays": r["acquiring_registry_id"]})
    return out, mx[:10]
S = sqlite3.connect("/opt/plans-sociaux/sirene.db")
def etab_ferme(siren, commune):
    cn = norm(commune)
    L = [(c, et, de, sg) for c, et, de, sg in S.execute("select commune, etat, date_etat, siege from etab where siren=?", (siren,)) if norm(c) and (norm(c) == cn or cn.startswith(norm(c)) or norm(c).startswith(cn))]
    return L
nsites = {}
for x in INST: nsites[x["siren"]] = nsites.get(x["siren"], 0) + 1
def moy(l): l = [a for a in l if a is not None]; return sum(l) / len(l) if l else 0
def t(n): return f"{round(n):,}".replace(",", " ")
ref = [i for i, a in enumerate(AN) if 2015 <= a <= 2019]
res, zero = [], []
for x in INST:
    g, v = x["g"], x["v"]
    g_ref, v_ref = moy([g[i] for i in ref]), moy([v[i] for i in ref])
    g2, v2 = sum(g[-2:]), sum(v[-2:])
    if g[-1] > 0 and g2 > 0 and (v2 <= 0.01 * g2 or (v_ref > 0 and moy(v[-2:]) <= 0.2 * v_ref and g[-1] >= 0.5 * g_ref)):
        nul = v2 <= 0.01 * g2
        surplus = sum(max(0, g[i] - v[i]) for i in range(len(AN)) if AN[i] >= 2022)
        # contrôles
        ic = x.get("ic") or {}; etat = (ic.get("etat") or "")
        ce = [c for c in (x.get("ce") or []) if c["t"] in ("fermeture", "liquidation", "plan social") and c.get("c") and c["c"].lower() == (x["c"] or "").lower()]
        ex = externe(x["siren"]) if x.get("siren") and nsites.get(x["siren"]) == 1 else {}
        preuves = []
        emi = ("ok", "Émissions vérifiées nulles ou quasi nulles en 2024-2025 (%s t) pour %s quotas gratuits ; moyenne 2015-2019 : %s t." % (t(v2), t(g2), t(v_ref))) if nul and v_ref > 1000 else \
              ("incertain", "Émissions très faibles mais le site n'a jamais beaucoup émis (moyenne 2015-2019 : %s t) : arrêt non démontré par les chiffres." % t(v_ref)) if nul else \
              ("incertain", "Émissions en forte baisse (moyenne 2024-2025 : %s t contre %s t en 2015-2019) : baisse, pas arrêt." % (t(moy(v[-2:])), t(v_ref)))
        if re.search(r"fin d.exploitation|cessation|arr[êe]t", etat, re.I): preuves.append("ICPE : « %s »" % etat)
        if ce: preuves.append("annonce de fermeture ou de suppressions à %s (%s)" % (x["c"], ce[0]["d"]))
        if ex.get("registre", {}).get("etat") == "C": preuves.append("société cessée au registre (%s)" % (ex["registre"].get("cessation") or "date inconnue"))
        for c, et, de, sg in etab_ferme(x["siren"], x["c"]):
            if et == "F": preuves.append("Sirene : établissement de %s fermé le %s" % (x["c"], de))
        web = WEB.get(x["id"], []); preuves += [w[0][:140] + ("…" if len(w[0]) > 140 else "") for w in web]
        liq = [b for b in ex.get("bodacc", []) if re.search(r"liquidation|radiation", b["nature"] or "", re.I)]
        if liq: preuves.append("BODACC : %s (%s)" % (liq[0]["nature"], liq[0]["paru"]))
        niveau = "confirme" if emi[0] == "ok" and len(preuves) >= 2 else "probable" if emi[0] == "ok" and preuves else "non_etabli"
        niveau = NIV.get(x["id"], niveau)
        if x["id"] in NIV: emi = (emi[0], "Émissions vérifiées en 2024-2025 : %s t pour %s quotas gratuits ; moyenne 2015-2019 : %s t." % (t(v2), t(g2), t(v_ref)))
        if etat and not re.search(r"fin d.exploitation|cessation|arr[êe]t", etat, re.I): preuves_contre = "ICPE : « %s » (toujours sous titre d'exploitation)" % etat
        else: preuves_contre = ""
        res.append({"id": x["id"], "site": x["n"], "societe": x["s"], "siren": x["siren"], "commune": x["c"], "dep": x["d"], "secteur": x["k"], "activite": x["al"], "niveau": niveau,
                    "alloc_2024_2025": g2, "emis_2024_2025": v2, "emis_ref_2015_2019": round(v_ref), "alloc_2022_2025": sum(g[i] for i in range(len(AN)) if AN[i] >= 2022), "emis_2022_2025": sum(v[i] for i in range(len(AN)) if AN[i] >= 2022),
                    "surplus_2022_2025": round(surplus), "valeur_basse_Meur": round(surplus * PRIX[0] / 1e6, 2), "valeur_haute_Meur": round(surplus * PRIX[1] / 1e6, 2), "emissions_nulles": nul,
                    "web": web, "controle_emissions": emi, "preuves": preuves, "contre": preuves_contre, "g": g, "v": v, "lat": x.get("la"), "lon": x.get("lo")})
    elif g[-1] == 0 and g_ref > 0 and v_ref > 10000 and v[-2:] and moy(v[-2:]) <= 0.1 * v_ref:
        zero.append({"id": x["id"], "site": x["n"], "commune": x["c"], "dep": x["d"], "secteur": x["k"], "emis_ref_2015_2019": round(v_ref), "emis_2024_2025": sum(v[-2:]), "g_ref": round(g_ref)})
TX, TXMAX = transferts({r["id"] for r in res})
for r in res:
    L = TX.get(r["id"], []); r["tx_jusqua"] = TXMAX
    ext = [t for t in L if t["type"] in ("10-0", "3-2") or True]
    r["tx"] = ext[:12]; r["tx_total"] = sum(t["n"] for t in ext if "ERU" not in t["unites"] and "CER" not in t["unites"])
json.dump(cache, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False)
ordre = {"confirme": 0, "probable": 1, "non_etabli": 2, "actif": 3}
res.sort(key=lambda r: (ordre[r["niveau"]], -r["surplus_2022_2025"])); zero.sort(key=lambda r: -r["emis_ref_2015_2019"])
meta = {"genere": time.strftime("%Y-%m-%d"), "prix": PRIX, "source": d["meta"]["paquet"], "n": len(res), "par_niveau": {k: sum(1 for r in res if r["niveau"] == k) for k in ordre}}
json.dump({"meta": meta, "sites": res, "allocation_tombee_a_zero": zero}, open(W + "arret.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
with open(W + "arret.csv", "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f, delimiter=";"); w.writerow(["niveau", "site", "societe", "siren", "commune", "dep", "quotas_gratuits_2022_2025", "emissions_verifiees_2022_2025", "surplus_2022_2025", "valeur_indicative_basse_Meur", "valeur_indicative_haute_Meur", "emissions_2015_2019_moyenne", "preuves"])
    for r in res: w.writerow([r["niveau"], r["site"], r["societe"], r["siren"], r["commune"], r["dep"], r["alloc_2022_2025"], r["emis_2022_2025"], r["surplus_2022_2025"], r["valeur_basse_Meur"], r["valeur_haute_Meur"], r["emis_ref_2015_2019"], " ; ".join(r["preuves"])])
# ---------- page
E = html.escape
LIB = {"confirme": ("Arrêt corroboré", "ok"), "probable": ("Arrêt probable", "chk"), "non_etabli": ("Arrêt non établi", "non"), "actif": ("Site actif", "apx")}
def tx_html(r):
    if not r.get("tx_jusqua"): return ""
    L = [t for t in r["tx"] if "ERU" not in t["unites"] and "CER" not in t["unites"]]
    if not L: return "Transferts de quotas depuis le compte du site : aucun trouvé entre le 01/01/2021 et le %s (le registre ne publie qu’avec un délai de plusieurs années ; rien n’est visible après cette date)." % r["tx_jusqua"][8:10] + "/" + r["tx_jusqua"][5:7] + "/" + r["tx_jusqua"][:4]
    det = " ; ".join("%s : %s quotas vers %s (%s)" % (t["date"], t2(t["n"]), E(t["vers"]), E(t["compte"] or "compte inconnu")) for t in L[:5])
    return "Transferts de quotas depuis le compte du site entre 2021 et le %s (limite de publication) : %s. %s" % (r["tx_jusqua"], t2(sum(t["n"] for t in L)), det)
def t2(n): return f"{round(n):,}".replace(",", " ")
def carte(r):
    lib, cl = LIB[r["niveau"]]
    return f'''<div class="l"><h2><span class="t {cl}">{lib}</span>{E(r["site"])} · {E(r["commune"] or "?")} ({E(r["dep"] or "")})</h2>
<p><b>{t(r["alloc_2022_2025"])}</b> quotas gratuits alloués en 2022-2025 pour <b>{t(r["emis_2022_2025"])} t</b> d’émissions vérifiées ; différence : {t(r["surplus_2022_2025"])} quotas, soit {r["valeur_basse_Meur"]:.1f} à {r["valeur_haute_Meur"]:.1f} M€ en valeur indicative ({PRIX[0]} à {PRIX[1]} €/t).</p>
<p><small>{E(r["controle_emissions"][1])}</small></p>
<p><small>{"".join("<br>Source : " + E(w[0]) + " <a href=\"" + E(w[1]) + "\" target=\"_blank\" rel=\"noopener\">lien</a>" for w in r["web"])}</small></p><p><small>{tx_html(r)}</small></p><p><small>Corroborations : {E(" ; ".join(r["preuves"]) or "aucune trouvée")}.{(" Contre : " + E(r["contre"]) + ".") if r["contre"] else ""}</small></p></div>'''
Z = "".join(f'<li>{E(z["site"])} · {E(z["commune"] or "?")} ({E(z["dep"] or "")}) : {t(z["emis_ref_2015_2019"])} t/an en 2015-2019, {t(z["emis_2024_2025"])} t en 2024-2025, allocation gratuite nulle en 2025.</li>' for z in zero[:25])
H = f'''<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Quotas gratuits et sites à l’arrêt · Radar des quotas</title><link rel="icon" href="favicon.svg" type="image/svg+xml">
<meta name="robots" content="index,follow,max-image-preview:large"><link rel="canonical" href="https://oraclemarin.fr/quotas-carbone/arret.html">
<meta name="description" content="Sites européens à quotas de CO₂ gratuits dont les émissions vérifiées sont nulles ou en chute : liste, contrôles automatiques de l’arrêt, limites et questions à poser.">
<style>:root{{--encre:#14202B;--gris:#5C6772;--trait:#D6DBE0;--fond:#F4F6F8}}*{{box-sizing:border-box}}body{{margin:0;font:15px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;color:var(--encre);background:var(--fond)}}a{{color:inherit;text-underline-offset:3px}}
header{{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:10px 18px;background:#fff;border-bottom:1px solid var(--trait)}}.btn{{border:1px solid var(--encre);background:#fff;padding:6px 12px;border-radius:6px;font-weight:600;font-size:13.5px;text-decoration:none}}
main{{max-width:900px;margin:0 auto;padding:18px}}h1{{font-size:26px;line-height:1.15;margin:6px 0 8px}}.intro{{color:var(--gris)}}.l{{background:#fff;border:1px solid var(--trait);border-radius:8px;padding:12px 14px;margin:10px 0}}.l h2{{font-size:16px;margin:0 0 4px}}.l p{{margin:4px 0}}small{{color:var(--gris)}}
.t{{display:inline-block;font-size:11.5px;font-weight:700;border-radius:4px;padding:1px 7px;margin-right:6px;color:#fff;vertical-align:1px}}.ok{{background:#2E7D32}}.chk{{background:#E8710A}}.non{{background:#B3261E}}.apx{{background:#1A5FB4}}</style><script src="/om-bar.js?v=2" defer></script></head><body>
<header><a href="./" class="btn">← Carte des quotas</a><a href="radar.html" class="btn">Radar</a><a href="lobbying.html" class="btn">Lobbying et aides</a></header><main>
<h1>Quotas gratuits, émissions nulles ou en chute</h1>
<p class="intro">{meta["n"]} sites de la carte reçoivent encore des quotas gratuits en 2024-2025 alors que leurs émissions vérifiées sont nulles ou très inférieures à celles de 2015-2019. Mise à jour automatique le {time.strftime("%d/%m/%Y")}. Source : EUTL (registre européen), paquet Zenodo du 21/07/2026. {meta["par_niveau"]["confirme"]} arrêts corroborés, {meta["par_niveau"]["probable"]} probables, {meta["par_niveau"]["non_etabli"]} non établis et {meta["par_niveau"]["actif"]} sites actifs dont la baisse vient d’un changement de combustible ou d’une cause autre qu’un arrêt.</p>
<div class="l"><h2>Comment lire</h2><p><small>Un quota gratuit est négociable : un site qui n’émet plus peut en théorie les vendre. Nous ne savons pas si c’est le cas : les données montrent ce qui est <b>alloué</b>, pas ce qui est vendu. Les règles européennes prévoient que l’allocation soit ajustée après une cessation, avec un délai ; un décalage peut expliquer une partie des écarts. Des émissions nulles peuvent aussi venir de la biomasse (non comptée) ou d’un site qui n’a jamais beaucoup émis : c’est pourquoi seul l’arrêt corroboré par au moins deux sources (émissions, ICPE, annonce de fermeture, registre, BODACC) est classé « corroboré ». Les valeurs sont indicatives ({PRIX[0]} à {PRIX[1]} €/t).</small></p></div>
{"".join(carte(r) for r in res)}
<div class="l"><h2>Contre-exemples : l’allocation est tombée à zéro</h2><p><small>Sites dont les émissions ont chuté et dont l’allocation gratuite 2025 est nulle : le mécanisme d’ajustement a fonctionné.</small></p><ul>{Z}</ul></div>
<div class="l"><h2>Questions à poser</h2><p><small>À la DGEC : l’allocation du site est-elle ajustée après la cessation, et à quelle date ? Les quotas alloués après l’arrêt ont-ils été restitués ou mis en réserve ? À l’exploitant : le site a-t-il cessé son activité, et depuis quand ?</small></p></div>
<p><small>Données : <a href="arret.json">arret.json</a> · <a href="arret.csv">arret.csv</a> (CC-BY 4.0, source EUTL).</small></p></main></body></html>'''
open(W + "arret.html", "w", encoding="utf-8").write(H)
print(meta, "; allocation tombée à zéro :", len(zero))
for r in res[:12]: print(r["niveau"], r["site"][:35], r["commune"], r["surplus_2022_2025"], r["preuves"])
