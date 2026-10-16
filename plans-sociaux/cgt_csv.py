import csv, json, os, sqlite3, sys
H = "/opt/plans-sociaux"; sys.path.insert(0, H)
import commun, cgt_stats
EV = json.load(open(H + "/public/data.json", encoding="utf-8"))["evenements"]
I = json.load(open(H + "/cgt/index.json", encoding="utf-8"))
FICHES = json.load(open(H + "/public/fiches.json"))
S = sqlite3.connect(H + "/sirene.db")
def nom(s):
    r = S.execute("select nom from ul where siren=?", (s,)).fetchone(); return r[0] if r else ""
NON = len(sys.argv) > 2 and sys.argv[2] == "non"      # « non » : les plans sans source indépendante, à compléter
try: NOTES = json.load(open(H + "/notes_cas.json", encoding="utf-8"))
except Exception: NOTES = {}
lignes = {l["n"]: l for l in I["lignes"]}
rows = []
for e in EV:
    if not cgt_stats.est_cgt(e) or commun.exclu_totaux(e): continue
    src = cgt_stats.src_indep(e); proc = e.get("procedure_bodacc"); ferme = e.get("etablissements_fermes") or e.get("fermeture_confirmee") or cgt_stats.site_ferme(e)
    if cgt_stats.recoupe(e) == NON: continue
    kinds = []
    if src: kinds.append("presse")
    if proc: kinds.append("BODACC")
    if ferme: kinds.append("fermeture Sirene")
    n = int(e["cgt_ligne"]) if str(e.get("cgt_ligne", "")).isdigit() else None
    pdf = f'{I["pdf"]}#page={e.get("cgt_page")}' if e.get("cgt_page") else I["pdf"]
    fiche = f'{commun.BASE_URL}/entreprise/{FICHES[e["siren"]]}/' if e.get("siren") in FICHES else ""
    liens = " ; ".join(f'{s.get("source")} ({(s.get("date") or "")[:10]}) {s.get("url")}' for s in src if s.get("url"))
    rows.append({
        "ligne_cgt": n, "page_pdf": e.get("cgt_page"), "secteur_cgt": e.get("cgt_secteur"), "entreprise": e.get("entreprise"),
        "texte_cgt": (e.get("detail") or "")[:300], "siren": e.get("siren"), "nom_sirene": nom(e.get("siren") or ""),
        "departement": e.get("dep"), "commune": e.get("commune"), "date_annonce": (e.get("date") or "")[:10],
        "emplois_cgt": e.get("emplois_cgt_brut") or e.get("emplois_source_brut") or e.get("emplois_min"),
        "emplois_retenus": e.get("emplois_min"), "emplois_corriges_a_la_main": "oui" if e.get("emplois_corrige_a_la_main") else "",
        "identite": e.get("verif_ident") or "", "type_recoupement": " + ".join(kinds), "nb_sources_presse": len(src),
        "lieu_verifie": (e.get("verif_site") or {}).get("niveau", ""), "etablissements_lieu": " ; ".join((e.get("verif_site") or {}).get("communes", [])),
        "etablissement_ferme_le": (e.get("verif_site") or {}).get("ferme", ""), "procedure_bodacc": (proc or {}).get("type", ""), "date_procedure": (proc or {}).get("date", ""),
        "liens_sources": liens, "note": NOTES.get(e.get("id"), ""), "fiche_site": fiche, "pdf_cgt": pdf})
rows.sort(key=lambda r: -(r["emplois_retenus"] or 0))
if NON:
    for r in rows:
        for k in ("type_recoupement", "nb_sources_presse", "etablissement_ferme_le", "procedure_bodacc", "date_procedure", "liens_sources", "emplois_corriges_a_la_main"): r.pop(k, None)
        r["source_a_fournir"] = ""
out = sys.argv[1]
with open(out, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0]), delimiter=";"); w.writeheader(); w.writerows(rows)
print(len(rows), "lignes ;", sum(r["emplois_retenus"] or 0 for r in rows), "emplois retenus")
