"""Licenciements économiques et PSE (Dares, « Les dispositifs publics d'accompagnement des restructurations ») : public/dares.json.
Le site de la Dares bloque les téléchargements par script : on passe par un vrai navigateur sans interface (Playwright/Chromium)
pour ouvrir la page, trouver le classeur CVS-CJO du dernier trimestre et le télécharger. Une fois par semaine (cron).
En cas d'échec, le fichier précédent est conservé."""
import io, json, os, re, sys, zipfile, datetime as dt, xml.etree.ElementTree as ET
H = os.path.dirname(os.path.abspath(__file__))
PAGE = "https://dares.travail-emploi.gouv.fr/donnees/les-dispositifs-publics-daccompagnement-des-restructurations"
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}

def telecharger():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36", locale="fr-FR")
        pg = ctx.new_page(); pg.goto(PAGE, wait_until="networkidle", timeout=120000); pg.wait_for_timeout(3000)
        liens = pg.eval_on_selector_all("a", "els => els.map(a => a.href).filter(h => /restructurations_CVS-CJO.*\\.xlsx/i.test(h))")
        pub = pg.eval_on_selector("body", "b => (b.innerText.match(/(\\d{1,2})\\s+(janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)\\s+(20\\d\\d)/i) || [''])[0]")
        if not liens: b.close(); raise RuntimeError("lien du classeur CVS-CJO introuvable")
        r = ctx.request.get(liens[0]); body = r.body(); b.close()
        if r.status != 200 or body[:2] != b"PK": raise RuntimeError(f"téléchargement refusé ({r.status})")
        return body, liens[0], pub

def feuilles(xlsx):
    z = zipfile.ZipFile(io.BytesIO(xlsx))
    ss = ["".join(t.itertext()) for t in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", NS)]
    wb = ET.fromstring(z.read("xl/workbook.xml")); rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    cibles = {r.get("Id"): r.get("Target").lstrip("/") for r in rels}
    out = {}
    for s in wb.find("m:sheets", NS):
        rid = s.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
        cib = cibles[rid]; cib = cib if cib.startswith("xl/") else "xl/" + cib
        lignes = []
        for row in ET.fromstring(z.read(cib)).iter("{%s}row" % NS["m"]):
            d = {}
            for c in row.findall("m:c", NS):
                v = c.find("m:v", NS)
                if v is None: continue
                d[re.sub(r"\d", "", c.get("r"))] = ss[int(v.text)] if c.get("t") == "s" else v.text
            if d: lignes.append(d)
        out[s.get("name")] = lignes
    return out

def serie(lignes, cols, depuis="2019"):
    res = []
    for d in lignes:
        m = re.match(r"(\d{4}) T(\d)", str(d.get("A", "")))
        if not m or m.group(1) < depuis: continue
        x = {"t": f"{m.group(1)}-T{m.group(2)}", "provisoire": "(p)" in str(d.get("A"))}
        for k, c in cols:
            try: x[k] = round(float(d[c]))
            except (KeyError, ValueError): pass
        res.append(x)
    return res

MOIS = {m: i + 1 for i, m in enumerate(["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"])}
def main():
    try:
        xlsx, url, pub = telecharger()
        f = feuilles(xlsx)
        nom = lambda motif: next(k for k in f if re.search(motif, k, re.I))
        out = {"source": "Dares, « Les dispositifs publics d'accompagnement des restructurations » (données trimestrielles CVS-CJO, France)", "url": PAGE, "fichier": url,
               "releve": dt.date.today().isoformat(), "note": "Téléchargé automatiquement chaque semaine via un navigateur sans interface.",
               "licenciements_eco": serie(f[nom(r"licenci")], [("inscriptions", "B"), ("dont_csp", "C")]),
               "pse_valides": serie(f[nom(r"valid|homolog")], [("pse", "B"), ("ruptures", "C")]),
               "pse_inities": serie(f[nom(r"initi")], [("pse", "B")])}
        m = re.match(r"(\d{1,2})\s+(\w+)\s+(\d{4})", pub or "", re.I)
        if m and m.group(2).lower() in MOIS: out["publication"] = f"{m.group(3)}-{MOIS[m.group(2).lower()]:02d}-{int(m.group(1)):02d}"
        if len(out["licenciements_eco"]) < 8 or len(out["pse_valides"]) < 8: raise RuntimeError("séries incomplètes")
        tmp = os.path.join(H, "public", "dares.json.tmp")
        json.dump(out, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1); os.replace(tmp, os.path.join(H, "public", "dares.json"))
        print("dares.json :", out["licenciements_eco"][-1], out["pse_valides"][-1], file=sys.stderr)
    except Exception as ex:
        print("dares : échec, fichier précédent conservé :", ex, file=sys.stderr)

if __name__ == "__main__":
    main()
