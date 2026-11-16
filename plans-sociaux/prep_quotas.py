#!/usr/bin/env python3
"""Agrège le registre européen des quotas (EUTL, paquet Zenodo CC-BY 4.0) par société française (SIREN du titulaire de compte) :
quotas gratuits alloués et émissions vérifiées, par installation et par année. Sortie : quotas_co2.json (lu par pages_quotas.py).
À relancer quand un nouveau paquet est téléchargé dans /opt/donnees-externes/eutl/."""
import csv, collections, json, os, re
D = "/opt/donnees-externes/eutl/"; H = os.path.dirname(os.path.abspath(__file__))
inst = {r["id"]: r for r in csv.DictReader(open(D + "installations.csv", encoding="utf-8")) if r["registry_id"] == "FR"}
acc = collections.defaultdict(list)
for r in csv.DictReader(open(D + "link_installation_account.csv", encoding="utf-8")): acc[r["installation_id"]].append(r["account_id"])
lah = collections.defaultdict(list)
for r in csv.DictReader(open(D + "link_account_holder.csv", encoding="utf-8")): lah[r["account_id"]].append(r["holder_id"])
HD = {r["id"]: r for r in csv.DictReader(open(D + "account_holders.csv", encoding="utf-8")) if r["registry_id"] == "FR"}
comp = collections.defaultdict(dict)
for r in csv.DictReader(open(D + "compliance.csv", encoding="utf-8")):
    if r["registry_id"] == "FR" and r["year"] >= "2013": comp[r["installation_id"]][r["year"]] = (float(r["allocated_free"] or 0), float(r["verified"] or 0))
out = {}
for i, r in inst.items():
    sir = None; nom = None
    for a in acc.get(i, []):
        for h in lah.get(a, []):
            n = re.sub(r"\D", "", (HD.get(h, {}).get("company_registration_number") or ""))
            if len(n) == 9: sir, nom = n, HD[h]["name"]
    if not sir: continue
    o = out.setdefault(sir, {"titulaire": nom, "installations": []})
    o["installations"].append({"id": i, "nom": r["name"], "commune": r["city"], "activite": r["activity_name"], "derniere_emission": r["year_of_last_emissions"],
                               "gratuits": {y: v[0] for y, v in comp[i].items()}, "verifiees": {y: v[1] for y, v in comp[i].items()}})
json.dump(out, open(H + "/quotas_co2.json", "w", encoding="utf-8"), ensure_ascii=False)
print(len(out), "sociétés,", sum(len(v["installations"]) for v in out.values()), "installations")
