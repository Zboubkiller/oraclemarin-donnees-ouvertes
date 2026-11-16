#!/usr/bin/env python3
"""Radar « Qui défend ses quotas, qui est soutenu par l'argent public ? » : pour les premiers titulaires de quotas gratuits, rapproche
quotas (registre européen), aides ADEME, contrats de soutien à la décarbonation, comptes et déclarations de lobbying (HATVP) évoquant le marché du carbone ou les aides.
Sorties : /var/www/quotas-carbone/radar.json et radar.csv"""
import csv, datetime as dt, json, re, sqlite3, os, sys, urllib.parse
H = "/opt/plans-sociaux"; OUT = "/var/www/quotas-carbone/"
sys.path.insert(0, H)
import aides
def ademe_direct(sir):
    """Aides de l'ADEME rapprochées par SIREN du bénéficiaire (tous établissements), hors contrats pluriannuels de l'appel d'offres de décarbonation, présentés à part."""
    d = aides.get(aides.ADEME + "?" + urllib.parse.urlencode({"size": 300, "sort": "-montant", "qs": "idBeneficiaire:%s*" % sir,
                  "select": "dateConvention,montant,dispositifAide,objet,conditionsVersement,datesPeriodeVersement"})) or {}
    aid, gp = [], []
    for x in d.get("results", []):
        m = x.get("montant") or 0
        if "Grands Projets Industriels" in (x.get("dispositifAide") or ""):
            gp.append({"d": x.get("dateConvention"), "m": round(m), "o": (x.get("objet") or "")[:140], "c": (x.get("conditionsVersement") or "")[:300], "p": (x.get("datesPeriodeVersement") or "")[:120]})
        else: aid.append((x.get("dateConvention") or "", m, (x.get("objet") or "")[:100]))
    return round(sum(a[1] for a in aid)), len(aid), round(sum(a[1] for a in aid if a[0] >= "2021")), [{"d": a[0], "m": round(a[1]), "o": a[2]} for a in aid[:3]], gp
Q = json.load(open(H + "/quotas_co2.json", encoding="utf-8"))
EV = json.load(open(H + "/public/data.json", encoding="utf-8"))["evenements"]
HV = json.load(open(H + "/hatvp_index.json", encoding="utf-8"))
SQ = sqlite3.connect(H + "/sirene.db")
RE_ETS = re.compile(r"quota|seqe|\bets\b|ajustement carbone|fuite de carbone|march[ée] (europ[ée]en )?(du )?carbone|benchmark|cbam", re.I)
RE_AIDE = re.compile(r"aides? publiques?|soutien financier|subvention|financement public|contrats? carbone|contrats? pour diff|france 2030|soutien (de l.[ée]tat|public)", re.I)
PRIX = (65, 80); ANNEES = [str(y) for y in range(2021, 2026)]
def titre(s): return " ".join(w.capitalize() for w in re.split(r"\s+", (s or "").strip().lower()))
par = {}
for e in EV:
    if e.get("siren"): par.setdefault(e["siren"], []).append(e)
rows = []
for sir, q in Q.items():
    g = sum(v for i in q["installations"] for y, v in i["gratuits"].items() if y in ANNEES); v_ = sum(v for i in q["installations"] for y, v in i["verifiees"].items() if y in ANNEES)
    if g <= 0: continue
    evs = par.get(sir, [])
    nom = (SQ.execute("select nom from ul where siren=?", (sir,)).fetchone() or [q["titulaire"]])[0]
    ademe, ademe_n, ademe21, top3, gpid = ademe_direct(sir)
    comptes = max((e.get("comptes") for e in evs if e.get("comptes")), key=lambda c: c.get("derniere_annee") or "", default=None)
    lob = HV.get(sir); ets, aid, last = [], [], None
    for ex in sorted((lob or {}).get("exercices", []), key=lambda x: x["annee"], reverse=True):
        last = last or ex
        for o in ex.get("objets") or []:
            t = re.sub(r"\s+", " ", o).strip()
            if RE_ETS.search(t) and not any(t[:60] == x["t"][:60] for x in ets): ets.append({"a": ex["annee"], "t": t[:260]})
            elif RE_AIDE.search(t) and not any(t[:60] == x["t"][:60] for x in aid): aid.append({"a": ex["annee"], "t": t[:260]})
    rows.append({"siren": sir, "nom": titre(nom), "sites": len(q["installations"]), "g": round(g), "v": round(v_), "bas": round(g * PRIX[0] / 1e6, 1), "haut": round(g * PRIX[1] / 1e6, 1),
                 "ademe": round(ademe), "ademe_n": ademe_n, "ademe21": ademe21, "top": top3, "gpid": gpid, "net": (comptes or {}).get("resultat_net"), "ca": (comptes or {}).get("ca"), "an": (comptes or {}).get("derniere_annee"),
                 "lob_an": (last or {}).get("annee"), "lob_dep": (last or {}).get("depenses"), "lob_ets": ets[:4], "lob_aide": aid[:3], "lob": bool(lob)})
rows.sort(key=lambda r: -r["g"]); rows = rows[:100]
for k, r in enumerate(rows, 1): r["rang"] = k
top40 = rows[:40]
res = {"n40_lob_ets": sum(1 for r in top40 if r["lob_ets"]), "n40_lob_aide": sum(1 for r in top40 if r["lob_aide"]), "n40_ademe": sum(1 for r in top40 if r["ademe"]), "n40_gpid": sum(1 for r in top40 if r["gpid"]),
       "n40_lob": sum(1 for r in top40 if r["lob"])}
json.dump({"meta": {"genere": dt.date.today().isoformat(), "prix": PRIX, "resume": res}, "lignes": rows}, open(OUT + "radar.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
with open(OUT + "radar.csv", "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f, delimiter=";"); w.writerow(["rang", "siren", "societe", "sites", "quotas_gratuits_2021_2025", "emissions_verifiees_2021_2025", "valeur_indicative_basse_Meur", "valeur_indicative_haute_Meur", "aides_ademe_eur", "nb_aides_ademe", "contrats_soutien_decarbonation_eur", "resultat_net_eur", "annee_comptes", "lobbying_derniere_annee", "lobbying_depenses", "lobbying_marche_carbone", "lobbying_aides"])
    for r in rows: w.writerow([r["rang"], r["siren"], r["nom"], r["sites"], r["g"], r["v"], r["bas"], r["haut"], r["ademe"], r["ademe_n"], sum(c["m"] or 0 for c in r["gpid"]), r["net"] or "", r["an"] or "", r["lob_an"] or "", r["lob_dep"] or "", " || ".join(x["a"] + " : " + x["t"] for x in r["lob_ets"]), " || ".join(x["a"] + " : " + x["t"] for x in r["lob_aide"])])
print(len(rows), "sociétés ;", res)
for r in rows:
    for c in r["gpid"]: print("  contrat", r["nom"][:24], c["d"], c["m"], "| conditions:", c["c"] or "—", "| versement:", c["p"] or "—")
for r in rows[:12]: print(r["rang"], r["nom"][:28], "| lob ETS", len(r["lob_ets"]), "| aides", len(r["lob_aide"]), "| ADEME", r["ademe"], "| GPID", sum(c["m"] or 0 for c in r["gpid"]), "| lob enregistré", r["lob"])
