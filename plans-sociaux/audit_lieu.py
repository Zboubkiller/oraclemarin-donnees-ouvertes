"""Audit du lieu sur toute la base : annonces dont la société rattachée n'a aucun établissement dans le département cité. Sortie : audit/lieu.csv (aucune donnée modifiée)."""
import collections, csv, json, os, sys
H = os.path.dirname(os.path.abspath(__file__))
E = json.load(open(os.path.join(H, "public", "data.json"), encoding="utf-8"))["evenements"]
os.makedirs(os.path.join(H, "audit"), exist_ok=True)
rows, tot = [], collections.Counter()
for e in E:
    v = (e.get("verif_site") or {}).get("niveau")
    if not v: continue
    g = "CGT" if str(e.get("source", "")).startswith("CGT") else "autres"
    tot[(g, v)] += 1
    if v == "aucun":
        rows.append({"id": e["id"], "source": e.get("source"), "entreprise": e.get("entreprise"), "siren": e.get("siren"), "dep": e.get("dep"), "commune": e.get("commune"),
                     "date": (e.get("date") or "")[:10], "emplois": e.get("emplois_min"), "verifie_a_la_main": "oui" if (e.get("valide_humain") or e.get("ident_humain")) else "", "url": e.get("url")})
rows.sort(key=lambda r: -(r["emplois"] or 0))
with open(os.path.join(H, "audit", "lieu.csv"), "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, list(rows[0]) if rows else ["id"], delimiter=";"); w.writeheader(); w.writerows(rows)
print("audit du lieu :", dict(tot), file=sys.stderr)
