"""Contexte économique (séries mensuelles, sources ouvertes sans clé) : public/macro.json, une fois par jour.
- INSEE : climat des affaires et climat de l'emploi (tous secteurs), production industrielle (industrie manufacturière, CVS-CJO),
  prix de production de l'électricité (marché français).
- BCE : taux d'intérêt des nouveaux crédits aux sociétés non financières en France ; taux de change euro-dollar.
- Banque mondiale (« Pink Sheet ») : prix du Brent en dollars, converti en euros avec le taux BCE du mois.
Ces séries sont présentées EN REGARD des défaillances, jamais comme une explication."""
import csv, io, json, os, re, sys, time, urllib.request, zipfile, xml.etree.ElementTree as ET, datetime as dt
H = os.path.dirname(os.path.abspath(__file__))
UA = {"User-Agent": "tracker-plans-sociaux/0.7"}
INSEE = {"climat_affaires": ("001565530", "Climat des affaires (tous secteurs)", "indice, moyenne 100"),
         "climat_emploi": ("001796629", "Climat de l'emploi (tous secteurs)", "indice, moyenne 100"),
         "production_industrielle": ("010768307", "Production de l'industrie manufacturière", "indice CVS-CJO, base 100 en 2021"),
         "prix_electricite": ("010763990", "Prix de production de l'électricité (marché français)", "indice, base 100 en 2021")}
BCE_TAUX = "https://data-api.ecb.europa.eu/service/data/MIR/M.FR.B.A2A.A.R.A.2240.EUR.N?format=csvdata&startPeriod={}"
BCE_CHANGE = "https://data-api.ecb.europa.eu/service/data/EXR/M.USD.EUR.SP00.A?format=csvdata&startPeriod={}"
BM_XLSX = "https://thedocs.worldbank.org/en/doc/18675f1d1639c7a34d463f59263ba0a2-0050012025/related/CMO-Historical-Data-Monthly.xlsx"

def get(u, accept=None, timeout=90):
    for i in range(3):
        try:
            h = dict(UA, **({"Accept": accept} if accept else {}))
            return urllib.request.urlopen(urllib.request.Request(u, headers=h), timeout=timeout).read()
        except Exception:
            time.sleep(3 + 4 * i)
    return None

def insee(ids, n=40):
    x = get("https://bdm.insee.fr/series/sdmx/data/SERIES_BDM/" + "+".join(ids) + f"?lastNObservations={n}", "application/xml")
    out = {}
    if not x: return out
    for a, body in re.findall(r"<Series ([^>]*)>(.*?)</Series>", x.decode("utf-8", "replace"), re.S):
        d = dict(re.findall(r'(\w+)="([^"]*)"', a))
        out[d.get("IDBANK")] = {p: float(v) for p, v in re.findall(r'<Obs TIME_PERIOD="([^"]+)" OBS_VALUE="([^"]+)"', body) if v not in ("", "NaN")}
    return out

def bce(url):
    t = get(url, "text/csv")
    if not t: return {}
    return {r["TIME_PERIOD"]: float(r["OBS_VALUE"]) for r in csv.DictReader(io.StringIO(t.decode("utf-8"))) if r.get("OBS_VALUE")}

def brent_usd():
    """Lit la feuille « Monthly Prices » du classeur de la Banque mondiale sans bibliothèque externe (xlsx = zip de XML)."""
    # le lien du classeur change à chaque édition : on le relit sur la page de la Banque mondiale, l'ancien sert de repli
    page = get("https://www.worldbank.org/en/research/commodity-markets") or b""
    liens = re.findall(rb"https://thedocs\.worldbank\.org[^\"']*CMO-Historical-Data-Monthly\.xlsx", page)
    b = get(liens[0].decode() if liens else BM_XLSX, timeout=180)
    if not b: return {}
    z = zipfile.ZipFile(io.BytesIO(b)); ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    ss = [("".join(t.itertext())) for t in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", ns)]
    wb = ET.fromstring(z.read("xl/workbook.xml")); rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    rid = next(s.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id") for s in wb.find("m:sheets", ns) if s.get("name") == "Monthly Prices")
    cible = next(r.get("Target") for r in rels if r.get("Id") == rid).lstrip("/")
    sh = ET.fromstring(z.read(cible if cible.startswith("xl/") else "xl/" + cible))
    def val(c):
        v = c.find("m:v", ns)
        if v is None: return None
        return ss[int(v.text)] if c.get("t") == "s" else v.text
    col_brent, out = None, {}
    for row in sh.iter("{%s}row" % ns["m"]):
        cells = {re.sub(r"\d", "", c.get("r")): val(c) for c in row.findall("m:c", ns)}
        if col_brent is None:
            col_brent = next((k for k, v in cells.items() if v and "brent" in str(v).lower()), None)
            continue
        m = re.fullmatch(r"(\d{4})M(\d{2})", str(cells.get("A") or ""))
        if m and cells.get(col_brent) not in (None, "", "…"):
            try: out[f"{m.group(1)}-{m.group(2)}"] = float(cells[col_brent])
            except ValueError: pass
    return out

def serie(d, n=36): return [{"mois": k, "v": round(v, 2)} for k, v in sorted(d.items())[-n:]]
def glissement(d):
    if not d: return None
    m = max(d); y = f"{int(m[:4]) - 1}{m[4:]}"
    return {"mois": m, "valeur": round(d[m], 2), "an_avant": round(d[y], 2) if y in d else None,
            "variation_pct": round(100 * (d[m] - d[y]) / d[y], 1) if y in d and d[y] else None}

def main():
    debut = f"{dt.date.today().year - 4}-01"
    out = {"maj": dt.datetime.now(dt.timezone.utc).isoformat(timespec="minutes"), "series": {}}
    s = insee([v[0] for v in INSEE.values()])
    for k, (i, nom, unite) in INSEE.items():
        if s.get(i): out["series"][k] = {"nom": nom, "unite": unite, "source": f"INSEE, série {i}", "url": f"https://www.insee.fr/fr/statistiques/serie/{i}",
                                         "serie": serie(s[i]), "dernier": glissement(s[i])}
    t = bce(BCE_TAUX.format(debut))
    if t: out["series"]["taux_credit"] = {"nom": "Taux des nouveaux crédits aux entreprises (France)", "unite": "%", "source": "BCE, MIR",
                                          "url": "https://data.ecb.europa.eu/data/datasets/MIR", "serie": serie(t), "dernier": glissement(t)}
    try: b = brent_usd()
    except Exception as ex:
        print("brent :", ex, file=sys.stderr); b = {}
    fx = bce(BCE_CHANGE.format(debut))
    be = {m: v / fx[m] for m, v in b.items() if m in fx and fx[m]}
    if be: out["series"]["brent_eur"] = {"nom": "Prix du Brent", "unite": "€ par baril", "source": "Banque mondiale (Pink Sheet), converti au taux BCE",
                                         "url": "https://www.worldbank.org/en/research/commodity-markets", "serie": serie(be), "dernier": glissement(be)}
    if not out["series"]: print("aucune série, macro.json inchangé", file=sys.stderr); return
    tmp = os.path.join(H, "public", "macro.json.tmp")
    json.dump(out, open(tmp, "w"), ensure_ascii=False, separators=(",", ":")); os.replace(tmp, os.path.join(H, "public", "macro.json"))
    print("macro.json :", {k: (v["dernier"] or {}).get("mois") for k, v in out["series"].items()}, file=sys.stderr)

if __name__ == "__main__":
    main()
