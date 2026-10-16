"""Audit des identifications faites à la main : pour chaque annonce rattachée par une validation humaine, contrôle automatique de la société retenue.
Contrôles : existence du SIREN, état (cessée avant l'annonce), établissement dans le département, taille, procédure collective au BODACC,
ressemblance du nom, même SIREN pour des noms sans rapport. Sortie : audit/audit_ident.json et .csv (alertes seulement, par gravité) ; aucune
donnée du site n'est modifiée. Usage : audit_ident.py"""
import csv, datetime as dt, json, os, re, sqlite3, sys, time, unicodedata, urllib.parse, urllib.request
H = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, H)
import collect
S = sqlite3.connect(os.path.join(H, "sirene.db"))
C = sqlite3.connect(os.path.join(H, "cache.db"), timeout=120)
C.execute("create table if not exists audit_api(siren text primary key, js text, ts real)")
C.execute("create table if not exists audit_bodacc(siren text primary key, js text, ts real)")
TR = collect.TR
norm = lambda x: re.sub(r"[^a-z0-9 ]", " ", unicodedata.normalize("NFD", (x or "").lower().replace("’", "'")).encode("ascii", "ignore").decode())
GEN = {"france", "groupe", "group", "societe", "sas", "sarl", "sa", "ste", "des", "les", "de", "du", "la", "le", "industrie", "industries", "services", "service", "holding", "international",
       "usine", "site", "entreprise", "magasin", "ets", "etablissements", "centre", "association", "fabrication", "plan", "social"}
jetons = lambda x: {w for w in norm(x).split() if len(w) >= 4 and w not in GEN}

def api(siren):
    r = C.execute("select js, ts from audit_api where siren=?", (siren,)).fetchone()
    if r and time.time() - r[1] < 7 * 86400: return json.loads(r[0])
    try:
        d = json.load(urllib.request.urlopen(urllib.request.Request("https://recherche-entreprises.api.gouv.fr/search?q=" + siren + "&per_page=1", headers={"User-Agent": "plans-sociaux-audit (quentinclosset@gmail.com)"}), timeout=30))
        x = next((x for x in d.get("results", []) if x.get("siren") == siren), None)
        out = None if not x else {"nom": x.get("nom_complet"), "sigle": x.get("sigle"), "naf": x.get("activite_principale"), "etat": x.get("etat_administratif"), "tranche": x.get("tranche_effectif_salarie"),
                                  "dep_siege": (x.get("siege") or {}).get("departement"), "creation": x.get("date_creation")}
        C.execute("replace into audit_api values(?,?,?)", (siren, json.dumps(out), time.time())); C.commit(); time.sleep(0.25)
        return out
    except Exception:
        return False                                    # indisponible : pas d'alerte « inexistant »

def bodacc(siren):
    r = C.execute("select js, ts from audit_bodacc where siren=?", (siren,)).fetchone()
    if r and time.time() - r[1] < 7 * 86400: return json.loads(r[0])
    sp = f"{siren[:3]} {siren[3:6]} {siren[6:]}"
    d = collect.get(collect.BODACC + "?" + urllib.parse.urlencode({"where": f'registre like "*{sp}*" and familleavis="collective"', "limit": 30, "order_by": "dateparution desc", "select": "dateparution,jugement"}))
    if d is None: return None
    out = []
    for x in d.get("results", []):
        try: j = json.loads(x.get("jugement") or "{}")
        except Exception: j = {}
        out.append({"date": x["dateparution"], "nature": (j.get("nature") or "")[:60], "date_jugement": j.get("date")})
    C.execute("replace into audit_bodacc values(?,?,?)", (siren, json.dumps(out), time.time())); C.commit(); time.sleep(0.15)
    return out

def main():
    E = json.load(open(os.path.join(H, "public", "data.json")))["evenements"]
    bod = {}
    for e in E:
        if e.get("source") == "BODACC" and e.get("siren") and e.get("date"): bod.setdefault(e["siren"], []).append((e["date"][:10], e.get("type")))
    cibles = [e for e in E if e.get("source") != "BODACC" and e.get("siren") and e.get("date")
              and (e.get("valide_humain") or e.get("ident_humain") or "vérifié à la main" in (e.get("verif_ident") or ""))]
    print(len(cibles), "identifications à contrôler", file=sys.stderr)
    alertes = []; noms_par_siren = {}
    def al(e, niveau, controle, motif):
        alertes.append({"niveau": niveau, "controle": controle, "id": e["id"], "siren": e["siren"], "entreprise": (e.get("entreprise") or "")[:60], "source": (e.get("source") or "")[:20],
                        "date": e["date"][:10], "dep": e.get("dep"), "emplois": e.get("emplois_min"), "motif": motif, "url": e.get("url")})
    for e in cibles:
        s = e["siren"]; d = dt.date.fromisoformat(e["date"][:10])
        u = S.execute("select nom, sigle, usuels, naf, tranche, etat, date_etat, creation from ul where siren=?", (s,)).fetchone()
        loc = u is not None
        if not loc:
            a = api(s)
            if a is False: continue
            if a is None: al(e, "HAUTE", "existence", "SIREN introuvable dans Sirene ni dans l'API"); continue
            u = (a["nom"], a.get("sigle"), "", a.get("naf"), a.get("tranche"), a.get("etat"), None, a.get("creation"))
        nom, sigle, usuels, naf, tranche, etat, date_etat, creation = u
        lo, hi = TR.get(tranche or "", (None, None))
        # 2. état et dates
        if creation and creation[:10] > e["date"][:10] and creation[:7] != e["date"][:7]: al(e, "HAUTE", "état", f"société créée le {creation[:10]}, après l'annonce")
        if etat == "C" and date_etat and date_etat[:10] < (d - dt.timedelta(days=45)).isoformat():
            al(e, "HAUTE", "état", f"société cessée le {date_etat[:10]}, avant l'annonce")
        # 3. département
        if loc and e.get("dep") and not e.get("plan_multi_societes"):
            if not S.execute("select 1 from etab where siren=? and dep=? limit 1", (s, e["dep"])).fetchone():
                al(e, "MOYENNE", "département", f"aucun établissement de la société dans le département {e['dep']} (siège ailleurs ou holding)")
        # 4. taille
        n = e.get("emplois_min") or 0
        if n and e.get("emplois_precision") == "annoncé" and not e.get("partie_de") and hi and n > max(1.5 * hi, hi + 20):
            al(e, "MOYENNE", "taille", f"{n} emplois annoncés pour une société de {lo}–{hi} salariés")
        # 6. nom
        cite = e.get("entreprise_ia") or e.get("entreprise") or ""
        if cite and cite != e.get("titre") and not e.get("ident_analogie"):
            cj = jetons(cite); nj = jetons(" ".join(filter(None, [nom, sigle, usuels])))
            enseignes = {w for (en,) in S.execute("select enseigne from etab where siren=?", (s,)) for w in jetons(en or "")} if loc else set()
            if cj and not (cj & nj) and not (cj & enseignes):
                al(e, "BASSE", "nom", f"nom cité « {cite[:40]} » sans rapport avec « {(nom or '')[:40]} » (normal pour un changement de nom, une marque ou un repreneur)")
        noms_par_siren.setdefault(s, []).append((cite, e))
        # 5. procédure collective
        txt = ((e.get("titre") or "") + " " + (e.get("detail") or "")).lower()
        if e.get("type") in ("redressement", "liquidation", "sauvegarde") or re.search(r"redressement judiciaire|liquidation judiciaire|placé en liquidation|procédure de sauvegarde", txt):
            ok = any(abs((dt.date.fromisoformat(dd) - d).days) <= 400 for dd, _ in bod.get(s, []))
            if not ok:
                b = bodacc(s)
                if b is not None: ok = any(abs((dt.date.fromisoformat(x["date"][:10]) - d).days) <= 400 for x in b)
                if b is not None and not ok: al(e, "MOYENNE", "BODACC", "l'annonce parle d'une procédure collective, aucune annonce BODACC pour cette société autour de la date")
    # 7. même SIREN, noms sans rapport
    for s, L in noms_par_siren.items():
        noms = {c for c, _ in L if c}
        if len(noms) >= 2:
            tj = [jetons(c) for c in noms]
            if all(not (a & b) for i, a in enumerate(tj) for b in tj[i + 1:]) and all(tj):
                e = L[0][1]; al(e, "BASSE", "doublon", "même SIREN pour des noms cités sans rapport : " + " / ".join(sorted(n[:30] for n in noms)[:3]))
    ordre = {"HAUTE": 0, "MOYENNE": 1, "BASSE": 2}
    alertes.sort(key=lambda a: (ordre[a["niveau"]], -(a["emplois"] or 0)))
    os.makedirs(os.path.join(H, "audit"), exist_ok=True)
    json.dump({"date": time.strftime("%Y-%m-%d %H:%M"), "controlees": len(cibles), "alertes": alertes}, open(os.path.join(H, "audit", "audit_ident.json"), "w"), ensure_ascii=False, indent=1)
    with open(os.path.join(H, "audit", "audit_ident.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, list(alertes[0].keys()) if alertes else ["niveau"]); w.writeheader(); w.writerows(alertes)
    import collections
    print(len(cibles), "contrôlées ;", len({a["id"] for a in alertes}), "annonces avec au moins une alerte ;", dict(collections.Counter((a["niveau"], a["controle"]) for a in alertes)), file=sys.stderr)

if __name__ == "__main__":
    main()
