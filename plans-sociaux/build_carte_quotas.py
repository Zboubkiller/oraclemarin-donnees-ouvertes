#!/usr/bin/env python3
"""Construit data.json du site « carte des quotas de CO₂ gratuits » : une ligne par installation du marché européen du carbone en France,
avec coordonnées, quotas gratuits et émissions vérifiées 2013-2025, annonces récentes de la société (plans sociaux, fermetures, procédures),
aides ADEME de la société et installation classée voisine (Géorisques). Sortie : /var/www/quotas-carbone/data.json"""
import csv, gzip, json, math, os, re, sqlite3, sys, unicodedata, datetime as dt
H = "/opt/plans-sociaux"; sys.path.insert(0, H)
import commun
D = "/opt/donnees-externes/eutl/"; OUT = "/var/www/quotas-carbone/"; os.makedirs(OUT, exist_ok=True)
ANNEES = list(range(2013, 2026))
Q = json.load(open(H + "/quotas_co2.json", encoding="utf-8"))
EV = json.load(open(H + "/public/data.json", encoding="utf-8"))["evenements"]
ICPE = json.load(gzip.open("/opt/donnees-externes/georisques/icpe_national.json.gz", "rt", encoding="utf-8"))
SQ = sqlite3.connect(H + "/sirene.db")
loc = {r["installation_id"]: (float(r["latitude"]), float(r["longitude"])) for r in csv.DictReader(open(D + "installation_locations.csv", encoding="utf-8")) if r["latitude"]}
meta = {r["id"]: r for r in csv.DictReader(open(D + "installations.csv", encoding="utf-8")) if r["registry_id"] == "FR"}
def norm(s): return re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFD", (s or "").lower()).encode("ascii", "ignore").decode())
def titre(s): return " ".join(w if (len(w) <= 3 and w.isupper() and w in ("SA", "SAS", "SNC", "EDF", "BP")) else w.capitalize() for w in re.split(r"\s+", (s or "").strip().lower()))
def sect(a):
    a = (a or "").lower()
    if "cement" in a or "lime" in a or "gypsum" in a: return "ciment"
    if "refining" in a: return "raffinage"
    if "non-ferrous" in a or "aluminium" in a: return "metaux"
    if "pig iron" in a or "steel" in a or "ferrous" in a or "coke" in a or "ore" in a: return "acier"
    if "glass" in a or "ceramic" in a or "mineral wool" in a: return "verre"
    if "pulp" in a or "paper" in a: return "papier"
    if any(k in a for k in ("chemical", "nitric", "ammonia", "hydrogen", "carbon black", "soda", "adipic", "glyoxal", "acid", "synthesis")): return "chimie"
    if "combustion" in a or "power" in a: return "energie"
    return "autre"
def hav(a, b, c, d):
    p = math.pi / 180; x = math.sin((c - a) * p / 2) ** 2 + math.cos(a * p) * math.cos(c * p) * math.sin((d - b) * p / 2) ** 2
    return 12742 * math.asin(math.sqrt(x))
par = {}
for e in EV:
    if e.get("siren"): par.setdefault(e["siren"], []).append(e)
icpe_par = {}
for x in ICPE:
    if x["siret"] and x["lat"] is not None: icpe_par.setdefault(x["siret"][:9], []).append(x)
TYPES = ("plan social", "fermeture", "liquidation", "redressement", "sauvegarde")
out = []
for sir, q in Q.items():
    evs = par.get(sir, [])
    nom = (SQ.execute("select nom from ul where siren=?", (sir,)).fetchone() or [q["titulaire"]])[0]
    recents = []
    for e in evs:
        if e["type"] in TYPES and (e.get("date") or "") >= "2024-01-01" and not commun.exclu_totaux(e) and e.get("source") != "Sirene":
            recents.append({"t": e["type"], "d": e["date"][:10], "n": e.get("emplois_min"), "c": e.get("commune") or "", "dep": e.get("dep") or "", "u": e.get("url") or "", "s": e.get("source") or ""})
    recents.sort(key=lambda r: r["d"], reverse=True)
    ademe = max((((e.get("argent_public") or {}).get("ademe") or {}).get("total") or 0 for e in evs), default=0)
    ademe_n = max((((e.get("argent_public") or {}).get("ademe") or {}).get("n") or 0 for e in evs), default=0)
    for ins in q["installations"]:
        if ins["id"] not in loc: continue
        g = [round(ins["gratuits"].get(str(y), 0)) for y in ANNEES]; v = [round(ins["verifiees"].get(str(y), 0)) for y in ANNEES]
        if not any(g[-5:]) and not any(v[-5:]): continue
        la, lo = loc[ins["id"]]; cp = (meta.get(ins["id"], {}).get("postal_code") or "")
        dep = cp[:3] if cp[:2] in ("97", "98") else cp[:2]
        c_n = norm(ins["commune"])
        site = [r for r in recents if r["dep"] == dep and (norm(r["c"]) in c_n or c_n in norm(r["c"]) or not r["c"] and False) and r["c"]]
        autres = [r for r in recents if r not in site]
        ic = None
        best = min(((hav(la, lo, x["lat"], x["lon"]), x) for x in icpe_par.get(sir, [])), key=lambda t: t[0], default=None)
        if best and best[0] <= 3:
            x = best[1]; ic = {"etat": x["etat"], "regime": x["regime"], "seveso": x["seveso"], "insp": (x["inspections"] or [None])[-1], "ninsp": len(x["inspections"] or []), "km": round(best[0], 1)}
        out.append({"id": ins["id"], "n": ins["nom"], "s": titre(nom), "siren": sir, "c": titre(ins["commune"]), "d": dep, "la": round(la, 5), "lo": round(lo, 5),
                    "k": sect(ins["activite"]), "al": ins["activite"], "g": g, "v": v, "fin": ins["derniere_emission"] or "", "se": site[:3], "ce": autres[:3],
                    "ad": round(ademe), "adn": ademe_n, "ic": ic})
meta_out = {"annees": ANNEES, "genere": dt.date.today().isoformat(), "n": len(out), "paquet": "EUTL, paquet Zenodo du 21/07/2026 (CC-BY 4.0)"}
json.dump({"meta": meta_out, "inst": out}, open(OUT + "data.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
print(len(out), "installations,", sum(1 for o in out if o["se"]), "avec annonce sur le site,", sum(1 for o in out if o["ce"] and not o["se"]), "avec annonce ailleurs dans la société,", sum(1 for o in out if o["ic"]), "avec installation classée voisine")
print(os.path.getsize(OUT + "data.json") // 1024, "Ko")
