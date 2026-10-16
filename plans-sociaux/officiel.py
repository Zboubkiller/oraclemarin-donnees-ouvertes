"""Séries officielles (INSEE, Banque de données macroéconomiques, API SDMX ouverte sans clé) : public/officiel.json.
- Défaillances d'entreprises (source Banque de France, comptées par DATE DE JUGEMENT) : cumul sur 12 mois glissants,
  total et par secteur, et série mensuelle CVS-CJO.
- Créations d'entreprises (méthode 2022) : mensuelles brutes, dont micro-entrepreneurs.
- Comparaison avec le décompte BODACC du site (jugements d'ouverture, comptés par DATE DE PUBLICATION) : les deux ne
  mesurent pas exactement la même chose (sauvegardes incluses côté BODACC, décalage de publication), l'écart est publié.
Une fois par jour suffit : les séries sont mensuelles, publiées avec environ deux mois de recul."""
import json, os, re, sqlite3, sys, time, urllib.request, datetime as dt
H = os.path.dirname(os.path.abspath(__file__))
API = "https://bdm.insee.fr/series/sdmx/data/SERIES_BDM/"
DEF_TOTAL, DEF_CVS = "001656101", "001656092"
DEF_SECTEURS = ["001656093", "001656094", "001656095", "001656096", "001656097", "001656098", "001656099", "001656100",
                "001656102", "001656103", "001656104"]
CREA = {"total": "010755537", "micro": "010755410", "classiques": "011811818", "ei_hors_micro": "011811817"}

def series(ids, n=40):
    url = API + "+".join(ids) + f"?lastNObservations={n}"
    for i in range(3):
        try:
            x = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "tracker-plans-sociaux/0.6", "Accept": "application/xml"}),
                                       timeout=90).read().decode("utf-8", "replace")
            break
        except Exception:
            time.sleep(3 + 5 * i)
    else:
        return None
    out = {}
    for a, body in re.findall(r"<Series ([^>]*)>(.*?)</Series>", x, re.S):
        d = dict(re.findall(r'(\w+)="([^"]*)"', a))
        obs = {p: float(v) for p, v in re.findall(r'<Obs TIME_PERIOD="([^"]+)" OBS_VALUE="([^"]+)"', body) if v not in ("", "NaN")}
        out[d.get("IDBANK")] = {"titre": d.get("TITLE_FR", ""), "obs": dict(sorted(obs.items()))}
    return out

def mois_avant(m, k):
    y, mo = int(m[:4]), int(m[5:7]) - k
    while mo <= 0: y, mo = y - 1, mo + 12
    return f"{y}-{mo:02d}"
def var(a, b): return None if not b else round(100 * (a - b) / b, 1)

def main():
    s = series([DEF_TOTAL, DEF_CVS] + DEF_SECTEURS + list(CREA.values()))
    if not s or DEF_TOTAL not in s:
        print("INSEE indisponible, officiel.json inchangé", file=sys.stderr); return
    tot = s[DEF_TOTAL]["obs"]; m = max(tot)
    out = {"maj": dt.datetime.now(dt.timezone.utc).isoformat(timespec="minutes"),
           "source": "INSEE, Banque de données macroéconomiques (séries Banque de France pour les défaillances)",
           "defaillances": {"dernier_mois": m, "cumul_12_mois": round(tot[m]), "cumul_12_mois_an_avant": round(tot.get(mois_avant(m, 12), 0)) or None,
                            "variation_pct": var(tot[m], tot.get(mois_avant(m, 12))),
                            "serie_cumul": [{"mois": k, "n": round(v)} for k, v in tot.items()][-25:],
                            "serie_cvs": [{"mois": k, "n": round(v)} for k, v in s.get(DEF_CVS, {}).get("obs", {}).items()][-25:],
                            "idbank": DEF_TOTAL, "url": "https://www.insee.fr/fr/statistiques/serie/" + DEF_TOTAL, "secteurs": []}}
    for i in DEF_SECTEURS:
        if i not in s: continue
        o = s[i]["obs"]; mm = max(o)
        out["defaillances"]["secteurs"].append({"secteur": s[i]["titre"].split(" - France - ")[-1].strip(), "cumul_12_mois": round(o[mm]),
                                                "variation_pct": var(o[mm], o.get(mois_avant(mm, 12))), "mois": mm,
                                                "serie": [{"mois": k, "n": round(v)} for k, v in sorted(o.items())][-36:]})
    out["defaillances"]["secteurs"].sort(key=lambda x: -x["cumul_12_mois"])
    ct = s.get(CREA["total"], {}).get("obs", {})
    if ct:
        mc = max(ct); r12 = [mois_avant(mc, k) for k in range(12)]; p12 = [mois_avant(mc, k + 12) for k in range(12)]
        S = lambda sid, L: sum(s.get(sid, {}).get("obs", {}).get(x, 0) for x in L)
        out["creations"] = {"dernier_mois": mc, "cumul_12_mois": round(S(CREA["total"], r12)), "cumul_12_mois_an_avant": round(S(CREA["total"], p12)),
                            "variation_pct": var(S(CREA["total"], r12), S(CREA["total"], p12)),
                            "dont_micro_pct": round(100 * S(CREA["micro"], r12) / S(CREA["total"], r12), 1) if S(CREA["total"], r12) else None,
                            "dont_classiques": round(S(CREA["classiques"], r12)),
                            "idbank": CREA["total"], "url": "https://www.insee.fr/fr/statistiques/serie/" + CREA["total"]}
    # comparaison avec le décompte BODACC du site (même fenêtre de 12 mois, mais par date de publication)
    try:
        db = sqlite3.connect(os.path.join(H, "cache.db"), timeout=60)
        fen = [mois_avant(m, k) for k in range(12)]
        b = sum(db.execute("select coalesce(sum(n),0) from tend_dep where m=?", (x,)).fetchone()[0] for x in fen)
        if b:
            out["comparaison"] = {"periode": [fen[-1], fen[0]], "banque_de_france": round(tot[m]), "bodacc_site": b,
                                  "ecart_pct": var(b, tot[m]),
                                  "explication": "Le BODACC compte les jugements d'ouverture à leur date de publication, sauvegardes comprises ; "
                                                 "la Banque de France compte les défaillances (redressements et liquidations) à leur date de jugement."}
    except sqlite3.OperationalError:
        pass
    tmp = os.path.join(H, "public", "officiel.json.tmp")
    json.dump(out, open(tmp, "w"), ensure_ascii=False, separators=(",", ":")); os.replace(tmp, os.path.join(H, "public", "officiel.json"))
    d = out["defaillances"]; print("officiel.json :", d["dernier_mois"], d["cumul_12_mois"], d["variation_pct"], "%", out.get("comparaison", {}).get("ecart_pct"), file=sys.stderr)

if __name__ == "__main__":
    main()
