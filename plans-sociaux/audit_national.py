#!/usr/bin/env python3
"""Audit automatique national : aides de collectivités à objectif d'emplois (toutes régions, départements, métropoles lus par build_subventions.py),
puis suppressions d'emplois sur la même société. Quatre contrôles (même site, entité, emplois, ordres de grandeur) avec preuve,
recommandation, et validation automatique UNIQUEMENT quand les preuves sont solides. Les cas bretons déjà audités à la main gardent leur verdict.
Sorties : dossier_pilote.json (cas « nat|SIREN » ajoutés), validations.json["dossier"] (décisions auto, champ auto=true), rapport audit-national.md."""
import json, os, re, sqlite3, sys, time, unicodedata, urllib.parse, urllib.request, fcntl
H = "/opt/plans-sociaux/"
CACHE = "./work/audit_cache.json"
UA = {"User-Agent": "tracker-plans-sociaux/0.9 (+https://oraclemarin.fr/plans-sociaux/)"}
POS = re.compile(r"\bCDI\b|cr[ée]ation[^.;]{0,50}emploi|maintien[^.;]{0,40}emploi|\d+\s*emplois?", re.I)
NEG = re.compile(r"demandeurs? d.emploi|QUALIF|formation|stagiaires|PREPA|insertion", re.I)
CUT = ("plan social", "fermeture", "départs volontaires", "liquidation", "redressement", "sauvegarde")
PROC = re.compile(r"liquidation|plan de cession|redressement|sauvegarde", re.I)

def norm(s):
    s = unicodedata.normalize("NFD", (s or "").lower()); s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", s).strip()
def get(u):
    for k in range(3):
        try: return json.loads(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60).read())
        except Exception: time.sleep(2 + 2 * k)
def cible_emplois(objet):
    m = re.search(r"cr[ée]ation (?:pr[ée]visionnelle )?de (\d+)\s*(?:emplois?|CDI)", objet or "", re.I) or re.search(r"maintien des ([\d,\.]+) emplois", objet or "", re.I) or re.search(r"(\d+)\s*(?:emplois?|CDI)", objet or "", re.I)
    if not m: return None
    try: return float(m.group(1).replace(",", "."))
    except ValueError: return None
def eu(n): return ("%.1f M€" % (n / 1e6)).replace(".", ",") if n >= 1e6 else "%d k€" % round(n / 1e3)

lock = open("/tmp/audit-national.lock", "w")
try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
except OSError: sys.exit("déjà en cours")
EV = json.load(open(H + "public/data.json", encoding="utf-8"))["evenements"]
J = json.load(open(H + "subventions_locales_auto.json", encoding="utf-8"))["par_siren"]
VAL = json.load(open(H + "validations.json", encoding="utf-8"))
NB = VAL.get("nombre", {})
D = json.load(open(H + "dossier_pilote.json", encoding="utf-8")) if os.path.exists(H + "dossier_pilote.json") else []
manuels = {x["cle"]: x for x in D if not x["cle"].startswith("nat|")}
try: cache = json.load(open(CACHE, encoding="utf-8"))
except Exception: cache = {}
S = sqlite3.connect(H + "sirene.db")

# --- 1) candidats : dernière annonce de suppression depuis 2023 + au moins une aide avec objectif d'emplois
best = {}
for e in EV:
    if not e.get("siren") or e.get("exclu_totaux") or e.get("doublon_de") or e.get("sans_entreprise") or e.get("source") == "Sirene" or not e.get("date") or e["type"] not in CUT or e["date"] < "2023-01-01": continue
    if e["siren"] not in best or e["date"] > best[e["siren"]]["date"]: best[e["siren"]] = e
cands = []
for s, e in best.items():
    if "bzh|" + s in manuels: continue
    L = [l for l in J.get(s, []) if POS.search(l.get("objet") or "") and not NEG.search(l.get("objet") or "") and (cible_emplois(l["objet"]) or 0) > 0 and l["date"] and l["date"] < e["date"]]
    if L: cands.append((s, e, L))
print(len(cands), "candidats nationaux (aide à objectif d'emplois antérieure à l'annonce)", flush=True)

def collecte(s):
    c = cache.get(s)
    if c and c.get("maj") == time.strftime("%Y-%m-%d"): return c
    out = {"maj": time.strftime("%Y-%m-%d"), "bodacc": [], "registre": {}}
    d = get("https://bodacc-datadila.opendatasoft.com/api/explore/v2.1/catalog/datasets/annonces-commerciales/records?" + urllib.parse.urlencode(
        {"where": 'registre like "%s"' % s, "limit": 100, "order_by": "dateparution desc", "select": "dateparution,familleavis_lib,tribunal,jugement"})) or {}
    for r in d.get("results", []):
        j = r.get("jugement")
        try: j = json.loads(j) if isinstance(j, str) else j
        except Exception: j = {}
        j = j or {}
        if j.get("nature"): out["bodacc"].append({"paru": r["dateparution"], "nature": j.get("nature"), "date": j.get("date")})
    d = get("https://recherche-entreprises.api.gouv.fr/search?q=%s&per_page=1" % s) or {}
    r = (d.get("results") or [{}])[0]
    if r.get("siren") == s:
        out["registre"] = {"nom": r.get("nom_complet"), "etat": r.get("etat_administratif"), "cessation": r.get("date_fermeture"), "tranche": r.get("tranche_effectif_salarie"), "siege": (r.get("siege") or {}).get("libelle_commune")}
    cache[s] = out; time.sleep(0.4)
    return out

def jours(a, b):
    try:
        import datetime as dt
        return abs((dt.date.fromisoformat(a[:10]) - dt.date.fromisoformat(b[:10])).days)
    except Exception: return 99999

nouveaux, rap = [], []
for s, e, L in cands:
    v = collecte(s); r = v["registre"]; nom = e["entreprise"]
    L = sorted(L, key=lambda l: -(cible_emplois(l["objet"]) or 0) * 1e6 - l["montant"])
    # --- contrôle 1 : même site (SIRET de l'aide → commune de l'établissement dans Sirene, sinon commune de projet publiée)
    coms = set()
    for l in L:
        if l.get("siret"):
            row = S.execute("select commune from etab where siret=?", (l["siret"],)).fetchone()
            if row and row[0]: coms.add(norm(row[0]))
        if l.get("commune_projet") and norm(l["commune_projet"]) not in ("non disponible", ""): coms.add(norm(l["commune_projet"]))
    ev_com = norm(e.get("commune") or "")
    fiable_lieu = bool(ev_com) and not e.get("approx") and (e.get("verif_site") or {}).get("niveau") != "departement" or e.get("lieu_corrige_a_la_main")
    if not coms: site = ("incertain", "Commune du projet aidé non publiée.")
    elif not ev_com: site = ("incertain", "Commune de l'annonce inconnue ; projet aidé à %s." % ", ".join(sorted(coms)))
    elif any(c == ev_com or c in ev_com or ev_com in c for c in coms): site = ("ok" if fiable_lieu else "incertain", "Commune du projet aidé (%s) = commune de l'annonce (%s)%s." % (", ".join(sorted(coms)), e["commune"], "" if fiable_lieu else ", mais lieu de l'annonce approximatif"))
    elif fiable_lieu: site = ("non", "Commune du projet aidé : %s ; commune de l'annonce : %s." % (", ".join(sorted(coms)), e["commune"]))
    else: site = ("incertain", "Commune du projet aidé : %s ; commune de l'annonce approximative (%s)." % (", ".join(sorted(coms)), e.get("commune")))
    # --- contrôle 2 : entité
    entite = ("ok", "Même SIREN pour l'aide (SIRET %s) et l'annonce ; registre : %s, %s." % (L[0].get("siret") or "non publié", r.get("nom") or nom, "en activité" if r.get("etat") == "A" else "cessée %s" % (r.get("cessation") or ""))) if r else ("incertain", "Registre indisponible.")
    if e.get("verif_ident") not in (None, "confirmé") and not e.get("siren_valide_a_la_main"): entite = ("incertain", "Rapprochement SIREN automatique non confirmé (%s)." % e.get("verif_ident"))
    # --- contrôle 3 : emplois et procédure
    proc = [b for b in v["bodacc"] if PROC.search(b["nature"] or "") and jours(b["date"] or b["paru"], e["date"]) < 550]
    domaines = {re.sub(r"^www\.", "", (x.get("url") or "").split("/")[2]) for x in (e.get("sources") or []) if x.get("url")} | ({re.sub(r"^www\.", "", e["url"].split("/")[2])} if e.get("url") and e["url"].startswith("http") else set())
    nbr = n_emp = (e.get("emplois_max") or e.get("emplois_min") or 0)
    valide_main = e.get("id") in NB and NB[e["id"]].get("choix") == "oui"
    if n_emp and (valide_main or len(domaines) >= 2) and proc: emplois = ("ok", "%d emplois cités par %s ; procédure au BODACC : %s (%s)." % (n_emp, "validation manuelle" if valide_main else "%d sources distinctes" % len(domaines), proc[0]["nature"][:50], proc[0]["date"]))
    elif n_emp: emplois = ("incertain", "%d emplois cités par %d source(s)%s." % (n_emp, len(domaines), "" if proc else ", aucune procédure au BODACC dans la période"))
    else: emplois = ("incertain", "Nombre d'emplois non établi.")
    # --- contrôle 4 : ordres de grandeur
    cible = cible_emplois(L[0]["objet"]); coupes = n_emp
    if not cible: ordre = ("incertain", "Objectif d'emplois non chiffré.")
    elif not coupes: ordre = ("incertain", "Nombre de suppressions inconnu.")
    elif cible <= 3 or cible < 0.15 * coupes or cible > 6 * coupes: ordre = ("non", "Objectif de %g emploi(s) contre %d emplois concernés : non comparable." % (cible, coupes))
    else: ordre = ("ok", "Objectif de %g emplois, %d emplois concernés : même ordre de grandeur." % (cible, coupes))
    etats = [site[0], entite[0], emplois[0], ordre[0]]
    reco = "ecarter" if "non" in (site[0], ordre[0]) else "retenir" if etats == ["ok"] * 4 else "creuser"
    statut = []
    if r: statut.append("Registre : %s ; tranche d'effectif %s ; siège %s." % ("en activité" if r.get("etat") == "A" else "cessée le %s" % r.get("cessation"), r.get("tranche"), r.get("siege")))
    for b in v["bodacc"][:6]:
        if PROC.search(b["nature"] or ""): statut.append("BODACC %s : %s (jugement du %s)." % (b["paru"], b["nature"], b["date"]))
    tot = sum(l["montant"] for l in L)
    motif = {"retenir": "Quatre contrôles concordants : site, entité, emplois (source multiple ou validée) et ordres de grandeur.", "ecarter": "Contrôle négatif : " + (site[1] if site[0] == "non" else ordre[1]), "creuser": "Contrôles non concluants : " + "; ".join(k for k, st in zip(("site", "entité", "emplois", "ordres de grandeur"), etats) if st != "ok") + "."}[reco]
    x = {"cle": "nat|" + s, "siren": s, "tier": {"retenir": "A", "creuser": "B", "ecarter": "C"}[reco], "titre": "%s : %s (%s)" % (nom, eu(tot) + " d'aides locales à objectif d'emplois puis " + e["type"], L[0]["financeur"]),
         "annonce": {"type": e["type"], "date": e["date"][:10], "emplois": n_emp or None, "commune": e.get("commune"), "dep": e.get("dep"), "source": e.get("source"), "url": e.get("url")},
         "aides": [{"f": l["financeur"], "d": l["date"][:10], "m": l["montant"], "o": l["objet"][:170], "emp": True} for l in L[:6]],
         "comptes": {"ca": (e.get("comptes") or {}).get("ca"), "net": (e.get("comptes") or {}).get("resultat_net"), "rentable": (e.get("comptes") or {}).get("profitable")},
         "faits": [], "questions": ["Les aides ont-elles été versées en totalité ? Les engagements d'emplois ont-ils été tenus (demander le bilan à la collectivité) ?"],
         "fiche": "/plans-sociaux/entreprise/%s/" % (e.get("slug") or ""), "tot_emploi": tot,
         "audit": {"maj": time.strftime("%Y-%m-%d"), "statut": statut, "controles": {"site": {"etat": site[0], "preuve": site[1]}, "entite": {"etat": entite[0], "preuve": entite[1]}, "emplois": {"etat": emplois[0], "preuve": emplois[1]}, "ordre": {"etat": ordre[0], "preuve": ordre[1]}},
                   "reco": reco, "motif": motif, "web": [], "auto": True}}
    nouveaux.append(x)
json.dump(cache, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False)

# --- 2) fichier des cas : manuels bretons + cas nationaux
cas = [x for x in D if not x["cle"].startswith("nat|")] + nouveaux
json.dump(cas, open(H + "dossier_pilote.json.tmp", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
os.replace(H + "dossier_pilote.json.tmp", H + "dossier_pilote.json")

# --- 3) validation automatique, seulement si solide : « retenu » = quatre contrôles ok ; « écarté » = contrôle négatif sur données fiables
#     (cas bretons audités à la main : leur recommandation « retenir » ou « écarter » est reprise). Les cas « creuser » restent à l'utilisateur. Jamais d'écrasement d'une décision humaine.
DEC = VAL.setdefault("dossier", {}); auto = {"retenu": [], "ecarte": []}
for x in cas:
    a = x.get("audit") or {}; k = x["cle"]
    if k in DEC and not DEC[k].get("auto"): continue
    ch = {"retenir": "retenu", "ecarter": "ecarte"}.get(a.get("reco"))
    if not ch: DEC.pop(k, None) if DEC.get(k, {}).get("auto") else None; continue
    cc = a["controles"]
    DEC[k] = {"choix": ch, "date": time.strftime("%Y-%m-%d %H:%M"), "auto": True, "note": "Validation automatique (audit du %s) : %s" % (a["maj"], a.get("motif", "")), "checks": {q: cc[q]["etat"] == "ok" for q in cc}}
    auto[ch].append(x["titre"])
tmp = H + "validations.json.tmp"
json.dump(VAL, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1); os.replace(tmp, H + "validations.json")

# --- 4) rapport
md = ["# Audit national : aides locales à objectif d'emplois puis suppressions", "", "*Généré le %s. Recoupement automatique ; aucun lien de cause n'est affirmé. Validation automatique seulement si les quatre contrôles concordent (retenu) ou si un contrôle négatif porte sur des données fiables (écarté). Le reste attend une décision.*" % time.strftime("%d/%m/%Y"), "",
      "%d cas ; retenus automatiquement : %d ; écartés automatiquement : %d ; à décider : %d." % (len(cas), len(auto["retenu"]), len(auto["ecarte"]), sum(1 for x in cas if x["cle"] not in DEC or DEC[x["cle"]].get("choix") == "passer")), ""]
for q in ("retenu", "ecarte"):
    md += ["## %s automatiquement" % ("Retenus" if q == "retenu" else "Écartés")] + ["- " + t for t in auto[q]] + [""]
open("./work/audit-national.md", "w", encoding="utf-8").write("\n".join(md))
print(len(nouveaux), "cas nationaux ;", {k: sum(1 for x in nouveaux if x["audit"]["reco"] == k) for k in ("retenir", "creuser", "ecarter")}, "; auto :", {k: len(v) for k, v in auto.items()})
