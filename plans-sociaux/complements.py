"""Compléments pour les annonces rattachées à une entreprise (après identification) :
- effectif de l'entreprise (tranche INSEE, base Sirene locale) ;
- commune du site : celle de l'établissement trouvé (SIRET), ou, si l'entreprise n'a qu'un établissement dans le département de
  l'annonce, celle-ci (marquée « déduite ») ;
- procédure collective de la même entreprise au BODACC (type, date du jugement, date de publication, lien), la plus proche ;
- dernier exercice publié (résultat net, année), même postérieur à l'annonce, pour information (« bénéficiaire avant le plan »
  reste réservé aux comptes antérieurs)."""
import json, os, re, sqlite3, sys, unicodedata
import collect
H = os.path.dirname(os.path.abspath(__file__))

def _sans(x):
    return re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFD", (x or "").lower().replace("saint", "st")).encode("ascii", "ignore").decode())

PUBLIC = re.compile(r"^(ville|commune|mairie|conseil (d[ée]partemental|r[ée]gional|g[ée]n[ée]ral)|d[ée]partement|r[ée]gion|m[ée]tropole|communaut[ée]|agglom[ée]ration|minist[èe]re|acad[ée]mie|rectorat|"
                    r"pr[ée]fecture|chu\b|chr\b|centre hospitalier|h[ôo]pital|assistance publique|ap-hp|[ée]ducation nationale|finances publiques|france travail|dgfip|insee|cnrs|inserm|ehpad public|sdis)", re.I)
PRIVE = re.compile(r"priv[ée]|association|fondation|clinique|catholique|libre|mutuelle", re.I)

def public_par_le_nom(e):
    """Annonce sans SIREN dont le nom est manifestement celui d'un employeur public (Ville de Toulouse, Conseil départemental, Finances publiques, hôpital public)."""
    n = (e.get("entreprise") or "").strip()
    return bool(n and n != e.get("titre") and PUBLIC.search(n) and not PRIVE.search(n) and not e.get("siren") and not e.get("valide_humain"))

def enrichir(evs):
    try: S = sqlite3.connect(os.path.join(H, "sirene.db"))
    except Exception as ex:
        print("compléments :", ex, file=sys.stderr); return
    B = {}
    for e in evs:
        if e.get("source") == "BODACC" and e.get("siren"): B.setdefault(e["siren"], []).append(e)
    n = {"effectif": 0, "commune": 0, "bodacc": 0}
    CB = {}                                                      # procédures collectives trouvées SIREN par SIREN (bodacc_cible.py), y compris pour les petites sociétés
    try:
        import json as _jb
        _c = sqlite3.connect(os.path.join(H, "cache.db"), timeout=60)
        for _s, _j, _t in _c.execute("select siren, js, ts from audit_bodacc"): CB[_s] = _jb.loads(_j)
    except Exception: pass
    for e in evs:
        if e.get("source") != "BODACC" and not e.get("siren"):
            e.pop("employeur_public_nom", None)
            if public_par_le_nom(e): e["employeur_public"] = True; e["employeur_public_nom"] = True; n["public"] = n.get("public", 0) + 1
    for e in evs:
        s = e.get("siren")
        if not s or e.get("source") == "BODACC": continue
        u = S.execute("select tranche, cj from ul where siren=?", (s,)).fetchone()
        e.pop("employeur_public", None)
        if u and (u[1] or "").startswith("7"): e["employeur_public"] = True; n["public"] = n.get("public", 0) + 1
        if u and not e.get("effectif_entreprise"):
            lo, hi = collect.TR.get(u[0] or "", (None, None))
            if lo is not None: e["effectif_entreprise"] = [lo, hi]; n["effectif"] += 1
        if not e.get("commune") or e.get("approx"):
            r = None
            if e.get("siret"): r = S.execute("select commune, insee, dep from etab where siret=?", (e["siret"],)).fetchone()
            elif e.get("dep") and e.get("lien") in ("siren_source", "siret_commune", "nom+dep"):
                L = S.execute("select commune, insee, dep from etab where siren=? and dep=? and etat='A'", (s, e["dep"])).fetchall()
                if len(L) == 1: r = L[0]; e["commune_deduite"] = True
            if r and r[0]:
                e.update(commune=r[0].title(), insee=r[1], dep=r[2], approx=False); n["commune"] += 1
        # département faux par homonymie de communes (Nozay 91 / 44, Saint-Léonard 88 / 62) ou « Pays de la Loire » lu comme la Loire (42) :
        # la commune de l'annonce porte le nom d'une commune où la société a un établissement actif, dans un autre département -> celui de l'établissement
        if e.get("dep") and not e.get("plan_multi_societes"):
            deps_soc = {r[0] for r in S.execute("select dep from etab where siren=? and etat='A'", (s,))}
            if deps_soc and e["dep"] not in deps_soc:
                nc = _sans(e.get("commune"))
                autre = [r for r in S.execute("select commune, insee, dep from etab where siren=? and etat='A'", (s,)) if nc and _sans(r[0]) == nc]
                if autre:
                    e.update(dep=autre[0][2], insee=autre[0][1], lat=None, lon=None, dep_corrige_par_etablissement=True)
                    try:
                        import json as _j
                        c = next(x for x in _j.load(open("/opt/ca-brule/communes.json")) if x["code"] == autre[0][1])["centre"]["coordinates"]; e["lon"], e["lat"] = c[0], c[1]
                    except Exception: pass
                    n["dep"] = n.get("dep", 0) + 1
                elif e["dep"] == "42" and re.search(r"pays de (la )?loire", (e.get("titre") or "") + " " + (e.get("detail") or "") + " " + (e.get("entreprise") or ""), re.I):
                    e.update(dep=None, commune=None, insee=None, lat=None, lon=None, dep_corrige_region=True); n["dep"] = n.get("dep", 0) + 1
        if s in B and e.get("date"):
            import datetime as dt
            j = dt.date.fromisoformat(e["date"][:10])
            b = min(B[s], key=lambda b: abs((dt.date.fromisoformat(b["date"][:10]) - j).days))
            e["procedure_bodacc"] = {"type": b["type"], "date": b["date"], "date_publication": (b.get("date_publication") or "")[:10], "url": b.get("url"),
                                     "suite": (b.get("suite") or {}).get("issue")}
            n["bodacc"] += 1
        elif s in CB and e.get("date"):
            import datetime as dt
            j = dt.date.fromisoformat(e["date"][:10])
            cand = [x for x in CB[s] if re.search(r"ouverture|liquidation|redressement|sauvegarde|plan", x.get("nature") or "", re.I) and not re.search(r"cl[ôo]ture|[ée]tat des cr[ée]ances", x.get("nature") or "", re.I)]
            def dj(x):
                for v in (x.get("date_jugement"), x.get("date")):                       # date_jugement est parfois en toutes lettres (« 24 novembre 2023 ») : on se rabat sur la date de parution
                    if v and re.match(r"\d{4}-\d{2}-\d{2}", v): return dt.date.fromisoformat(v[:10])
                return dt.date.fromisoformat(x["date"][:10])
            cand = [x for x in cand if abs((dj(x) - j).days) <= 730]
            if cand:
                b = min(cand, key=lambda x: abs((dj(x) - j).days))
                e["procedure_bodacc"] = {"type": b["nature"], "date": dj(b).isoformat(), "date_publication": b["date"][:10], "url": None, "suite": None, "recherche": "par SIREN"}
                n["bodacc"] += 1
    try:
        PC = json.load(open(os.path.join(H, "comptes_preuves.json"), encoding="utf-8"))
        for e in evs:
            if e.get("siren") in PC: e["preuve_comptes"] = PC[e["siren"]]
    except Exception as ex:
        print("preuves par les comptes :", ex, file=sys.stderr)
    try:
        import verif_site; vs = verif_site.verifier(evs)
        print("lieu vérifié (commune / département / aucun / inconnu) :", vs["commune"], vs["departement"], vs["aucun"], vs["inconnu"], file=sys.stderr)
    except Exception as ex:
        print("vérification du lieu :", ex, file=sys.stderr)
    print(f"compléments : effectif {n['effectif']}, commune {n['commune']}, département corrigé {n.get('dep', 0)}, employeurs publics {n.get('public', 0)}, procédure BODACC liée {n['bodacc']}", file=sys.stderr)
