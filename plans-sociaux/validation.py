"""Applique les décisions humaines (validations.json, page privée de validation) aux rattachements."""
import json, os, sys
H = os.path.dirname(os.path.abspath(__file__))

def analogies(evs, S, R, I):
    """Reprend sur les annonces non identifiées le choix manuel déjà fait pour le MÊME nom cité : une seule société choisie pour ce nom,
    nom d'au moins 5 caractères, annonce à moins de 18 mois de l'annonce validée, la société a un établissement actif dans le département
    de l'annonce (ou l'annonce n'en a pas). Exclut les plans multi-sociétés et les annonces déjà décidées."""
    import datetime as dt, re, unicodedata, collections
    cle = lambda n: re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFD", (n or "").lower()).encode("ascii", "ignore").decode())
    par_id = {e.get("id"): e for e in evs}
    alias = collections.defaultdict(list)           # nom -> [(siren, date de l'annonce validée)]
    def noter(e, sr):
        for nom in (e.get("entreprise_ia"), e.get("entreprise")):
            if nom and nom != e.get("titre") and len(cle(nom)) >= 5 and e.get("date"): alias[cle(nom)].append((sr, e["date"][:10]))
    for k, v in R.items():
        if v.get("choix") == "oui" and k.split("|")[0] in par_id: noter(par_id[k.split("|")[0]], k.split("|")[1])
    for k, v in I.items():
        if str(v.get("choix", "")).startswith("siren:") and "," not in v["choix"] and k in par_id: noter(par_id[k], v["choix"][6:])
    n = 0
    decides = {k.split("|")[0] for k, v in R.items() if v.get("choix") != "passer"} | {k for k, v in I.items() if v.get("choix") != "passer"}   # « je ne sais pas » : l'annonce reste à traiter
    for e in evs:
        if e.get("siren") or e.get("source") == "BODACC" or e.get("sans_entreprise") or e.get("hors_france") or e.get("partie_de") or e.get("id") in decides or not e.get("date"): continue
        nom = e.get("entreprise_ia") or e.get("entreprise")
        if not nom or (nom == e.get("titre") and not e.get("entreprise_ia")): continue
        try: d = dt.date.fromisoformat(e["date"][:10])
        except ValueError: continue
        k0 = cle(nom)
        # même nom, ou un nom contenu dans l'autre (« Stade Malherbe » / « Stade Malherbe Caen », « Coccinelle » / « Supérette Coccinelle » ; 8 caractères au moins)
        L = [(sr, dd) for k1, lst in alias.items() if k1 == k0 or (min(len(k0), len(k1)) >= 8 and (k0 in k1 or k1 in k0))
             for sr, dd in lst if abs((d - dt.date.fromisoformat(dd)).days) <= 548]
        if len({sr for sr, _ in L}) != 1: continue
        sr = L[0][0]; dep = e.get("dep")
        if dep and not S.execute("select 1 from etab where siren=? and dep=? and etat='A' limit 1", (sr, dep)).fetchone(): continue
        e.update(siren=sr, lien="nom+dep", siren_rapproche=True, valide_humain=True, ident_humain=True, ident_analogie=True,
                 verif_ident="vérifié à la main (d'après une validation manuelle précédente)")
        e.pop("rattachement_retire", None); nom_ul(e, S, sr); n += 1
    return n

def source_lien(u):
    """Source ajoutée par un lien saisi à la main : un avis BODACC n'est pas un article de presse."""
    import re
    if re.match(r"https?://([a-z0-9-]+\.)*bodacc(-datadila)?\.(fr|opendatasoft\.com)/", u or "", re.I):
        return {"source": "BODACC", "url": u, "date": None, "titre": "avis BODACC (vérification)"}
    import fermetures
    return {"source": fermetures.presse_nom(u), "url": u, "date": None, "titre": "article de presse (vérification)"}

def complements(e, d):
    """Lien presse et nombre réel d'emplois saisis avec une identification : l'article devient une source, le nombre remplace celui de la source d'origine
    (conservé dans emplois_source_brut)."""
    u = (d.get("url") or "").strip()
    if u and u not in [x.get("url") for x in e.get("sources") or []] + [e.get("url")]:
        e.setdefault("sources", []).append(source_lien(u))
    n = d.get("emplois")
    if isinstance(n, int) and n > 0 and n != e.get("emplois_min"):
        e["emplois_source_brut"] = e.get("emplois_min")
        e.update(emplois_min=n, emplois_max=n, emplois_precision="annoncé", emplois_corrige_a_la_main=True)

def nom_ul(e, S, siren, force=False):
    """Annonce sans employeur nommé (entreprise == titre) : le nom de la société choisie devient l’entreprise (sinon la ligne resterait hors totaux)."""
    if force or e.get("entreprise") == e.get("titre"):
        u = S.execute("select nom from ul where siren=?", (siren,)).fetchone()
        if u: e["entreprise"] = u[0]

def appliquer_nombres(evs):
    """Nombres d'emplois confirmés à la main d'après un article (onglet Nombres) : ils remplacent l'absence de chiffre."""
    try: N = json.load(open(os.path.join(H, "validations.json"), encoding="utf-8")).get("nombre", {})
    except Exception: return
    n = 0
    for e in evs:
        d = N.get(e.get("id"))
        if d and d.get("note"): e["note_cas"] = d["note"]
        if d and d.get("estime") and d.get("choix") == "oui": e["emplois_estime"] = True
        if d and d.get("choix") == "hors":
            e["sans_entreprise"] = True; e["hors_perimetre_motif"] = "pas une suppression d'emplois (relevé à la main)"; continue
        if not d or d.get("choix") != "oui" or not isinstance(d.get("emplois"), int) or d["emplois"] < 0: continue
        for u in (d.get("urls") or ([d["url"]] if d.get("url") else [])):
            if u not in [x.get("url") for x in e.get("sources") or []] + [e.get("url")]: e.setdefault("sources", []).append(source_lien(u))
        if e.get("emplois_min") == d["emplois"]: continue
        e.update(emplois_min=d["emplois"], emplois_max=d["emplois"], emplois_precision="annoncé", emplois_corrige_a_la_main=True, emplois_note="confirmé à la main"); n += 1
    print(f"nombres d'emplois confirmés à la main d'après un article : {n}", file=sys.stderr)

def appliquer_presse(evs):
    """Articles de presse confirmés à la main (onglet Presse) : ils deviennent des sources de l'annonce."""
    try: P = json.load(open(os.path.join(H, "validations.json"), encoding="utf-8")).get("presse", {})
    except Exception: return
    n = 0
    for e in evs:
        d = P.get(e.get("id"))
        if not d or d.get("choix") != "oui": continue
        deja = [x.get("url") for x in e.get("sources") or []] + [e.get("url")]
        for a in d.get("articles") or []:
            if a["url"] in deja: continue
            e.setdefault("sources", []).append({"source": a.get("source") or "presse", "url": a["url"], "date": a.get("date") or None, "titre": a.get("titre") or "article de presse (vérification)"}); n += 1
    print(f"articles de presse confirmés à la main : {n} sources ajoutées", file=sys.stderr)

def appliquer_lieux(evs):
    """Lieux corrigés à la main (annonce rattachée au siège alors que le site concerné est ailleurs) : lieux_corriges.json {id: {commune, dep, lat, lon, note}}."""
    try: L = json.load(open(os.path.join(H, "lieux_corriges.json"), encoding="utf-8"))
    except Exception: return
    for e in evs:
        o = L.get(e.get("id"))
        if o: e.update(commune=o["commune"], dep=o["dep"], lat=o["lat"], lon=o["lon"], approx=False, lieu_corrige_a_la_main=True, lieu_note=o.get("note"))

def appliquer(evs):
    appliquer_lieux(evs)
    appliquer_presse(evs)
    appliquer_nombres(evs)
    try: HP = json.load(open(os.path.join(H, "hors_perimetre.json"), encoding="utf-8"))
    except Exception: HP = {}
    for e in evs:
        h = HP.get(e.get("id"))
        if not h: continue
        e["sans_entreprise"] = True; e["hors_perimetre_motif"] = h.get("motif")
        for u in h.get("sources", []):
            if u not in [x.get("url") for x in e.get("sources") or []] + [e.get("url")]: e.setdefault("sources", []).append(source_lien(u))
    # annonces écartées à la main (« pas une suppression d'emplois », organismes publics, interviews…) : retirées de la base, pas seulement des totaux.
    # Les lignes de la liste CGT restent : la page CGT reprend la liste telle quelle.
    try: NH = json.load(open(os.path.join(H, "validations.json"), encoding="utf-8")).get("nombre", {})
    except Exception: NH = {}
    avant = len(evs)
    evs[:] = [e for e in evs if str(e.get("id", "")).startswith("cgt-") or not ((NH.get(e.get("id")) or {}).get("choix") == "hors" or (HP.get(e.get("id")) or {}).get("retirer"))]
    if len(evs) != avant: print(f"validation humaine : {avant - len(evs)} annonces écartées retirées de la base", file=sys.stderr)
    try: R = json.load(open(os.path.join(H, "validations.json"), encoding="utf-8")).get("rattachement", {})
    except Exception: return
    import verif_ident
    n = {"oui": 0, "non": 0}
    for e in evs:
        if not e.get("siren") or e.get("source") == "BODACC": continue
        d = R.get(f"{e.get('id')}|{e['siren']}")
        if not d: continue
        if d["choix"] == "oui":
            e["verif_ident"] = "vérifié à la main"; e["valide_humain"] = True
            if e.get("lien") == "nom_seul": e["lien"] = "nom+dep"
            c = e.get("comptes") or {}; da, ya = c.get("derniere_annee"), int((e.get("date") or "0")[:4] or 0)
            e["fiable"] = bool(da and ya and 0 <= ya - int(da) <= 2); n["oui"] += 1
            if d.get("url") and d["url"] not in [x.get("url") for x in e.get("sources") or []] + [e.get("url")]:
                e.setdefault("sources", []).append(source_lien(d["url"]))
        elif d["choix"] == "non":
            verif_ident.retirer(e, "vérification humaine : autre entreprise"); n["non"] += 1
    print(f"validation humaine : {n['oui']} rattachements confirmés, {n['non']} retirés", file=sys.stderr)
    # identifications faites à la main (annonce sans SIREN, entreprise(s) choisie(s)) : une société = rattachement direct ;
    # plusieurs = plan multi-sociétés : l'annonce garde le total, chaque société reçoit une ligne « partie_de » (hors totaux) avec
    # sa part d'emplois quand une composante du texte (département) la désigne sans ambiguïté
    try: I = json.load(open(os.path.join(H, "validations.json"), encoding="utf-8")).get("identification", {})
    except Exception: I = {}
    nouv, ids = [], {e.get("id") for e in evs}
    import sqlite3
    S = sqlite3.connect(os.path.join(H, "sirene.db"))
    for e in list(evs):
        d = I.get(e.get("id"))
        if not d or (e.get("siren") and not d.get("force")) or e.get("source") == "BODACC" or not str(d.get("choix", "")).startswith("siren:"): continue
        sirens = [x for x in d["choix"][6:].split(",") if len(x) == 9]
        if len(sirens) == 1:
            if d.get("auto"): e.update(siren=sirens[0], lien="nom+dep", siren_rapproche=True, ident_recherche=True, verif_ident="rapprochement automatique : " + (d.get("raison") or "nom identique"))
            else: e.update(siren=sirens[0], lien="nom+dep", siren_rapproche=True, valide_humain=True, ident_humain=True, verif_ident="vérifié à la main")
            nom_ul(e, S, sirens[0])
            complements(e, d)
            e.pop("rattachement_retire", None); nouv.append(e)
        elif len(sirens) > 1:
            e.update(plan_multi_societes=sirens, valide_humain=not d.get("auto"), verif_ident=("rapprochement automatique (plusieurs sociétés)" if d.get("auto") else "vérifié à la main (plusieurs sociétés)"))
            complements(e, d)
            if e.get("entreprise") == e.get("titre"):
                noms = []
                for x in sirens[:3]:
                    r = S.execute("select nom from ul where siren=?", (x,)).fetchone()
                    if r: noms.append(r[0])
                e["entreprise"] = " · ".join(noms)[:120] or e["entreprise"]
            comps = e.get("composantes") or []
            deps = {sr: {r[0] for r in S.execute("select dep from etab where siren=? and etat='A'", (sr,))} for sr in sirens}
            for sr in sirens:
                cid = f"{e['id']}#{sr}"
                if cid in ids: continue
                ok = [c for c in comps if set(c.get("departements") or []) & deps[sr]]
                autres = [c for c in comps if c not in ok]
                part = ok[0]["emplois"] if len(ok) == 1 and not any(set(c.get("departements") or []) & deps[sr] for c in autres) else None
                f = {k: v for k, v in e.items() if k in ("source", "type", "entreprise", "titre", "date", "date_precision", "url", "detail", "sources", "en_france", "extraction")}
                nom_ul(f, S, sr, force=True)
                f.update(id=cid, siren=sr, lien="nom+dep", siren_rapproche=True, valide_humain=True, ident_humain=True, verif_ident=("rapprochement automatique (plusieurs sociétés)" if d.get("auto") else "vérifié à la main (plusieurs sociétés)"),
                         partie_de=e["id"], emplois_min=part, emplois_max=part, emplois_precision="part du plan, selon le texte de la source" if part else None,
                         emplois_total_plan=e.get("emplois_min"))
                evs.append(f); ids.add(cid); nouv.append(f)
    if nouv:
        try:
            import aides; aides.enrichir(nouv)
        except Exception as ex: print("validation (aides) :", ex, file=sys.stderr)
        for e in nouv:
            c = e.get("comptes") or {}; da, ya = c.get("derniere_annee"), int((e.get("date") or "0")[:4] or 0)
            e["fiable"] = bool(da and ya and 0 <= ya - int(da) <= 2)
    try:
        R2 = json.load(open(os.path.join(H, "validations.json"), encoding="utf-8")).get("rattachement", {})
        na = analogies(evs, S, R2, I)
        if na:
            import aides
            aides.enrichir([e for e in evs if e.get("ident_analogie") and not e.get("comptes")])
            for e in evs:
                if e.get("ident_analogie"):
                    c = e.get("comptes") or {}; da, ya = c.get("derniere_annee"), int((e.get("date") or "0")[:4] or 0)
                    e["fiable"] = bool(da and ya and 0 <= ya - int(da) <= 2)
        print(f"validation humaine : {na} annonces identifiées d'après une validation précédente", file=sys.stderr)
    except Exception as ex:
        print("analogies :", ex, file=sys.stderr)
    print(f"validation humaine : {len(nouv)} entreprises identifiées à la main", file=sys.stderr)
