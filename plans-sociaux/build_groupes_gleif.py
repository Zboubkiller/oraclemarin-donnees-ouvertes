#!/usr/bin/env python3
"""Rapproche chaque titulaire de quotas (SIREN) de sa maison mère ultime via GLEIF (LEI, relations de niveau 2).
Sortie : /var/www/quotas-carbone/groupes.json {siren: {lei, mere, mere_lei, mere_pays}} ; absence = aucun LEI ou aucune mère déclarée."""
import json, time, urllib.parse, urllib.request
OUT = "/var/www/quotas-carbone/"
R = json.load(open(OUT + "radar.json", encoding="utf-8"))["lignes"]
def get(u):
    for _ in range(3):
        try:
            return json.load(urllib.request.urlopen(urllib.request.Request(u, headers={"Accept": "application/vnd.api+json"}), timeout=25))
        except urllib.error.HTTPError as e:
            if e.code == 404: return None
            time.sleep(2)
        except Exception: time.sleep(2)
    return None
B = "https://api.gleif.org/api/v1/lei-records"
res = {}
for r in R:
    s = r["siren"]; f = "%s %s %s" % (s[:3], s[3:6], s[6:])
    d = get(B + "?" + urllib.parse.urlencode({"filter[entity.registeredAs]": f, "filter[entity.legalAddress.country]": "FR"}))
    if not d or not d.get("data"): res[s] = {"lei": None}; continue
    x = d["data"][0]; lei = x["id"]; o = {"lei": lei, "nom_gleif": x["attributes"]["entity"]["legalName"]["name"]}
    u = get(B + "/" + lei + "/ultimate-parent")
    if u and u.get("data"):
        p = u["data"]; p = p[0] if isinstance(p, list) else p
        o.update({"mere": p["attributes"]["entity"]["legalName"]["name"], "mere_lei": p["id"], "mere_pays": p["attributes"]["entity"]["legalAddress"]["country"]})
    else:
        e = (x.get("attributes", {}).get("entity", {}).get("")) if False else None
        rep = x.get("attributes", {}).get("registration", {})
        o["sans_mere"] = True
    res[s] = o; time.sleep(.2)
json.dump(res, open(OUT + "groupes.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(len(res), "avec LEI:", sum(1 for v in res.values() if v.get("lei")), "avec mère:", sum(1 for v in res.values() if v.get("mere")))
for r in R[:40]:
    v = res[r["siren"]]; print(r["rang"], r["nom"][:30], "|", v.get("lei") and "LEI", "|", v.get("mere", "-"), v.get("mere_pays", ""))
