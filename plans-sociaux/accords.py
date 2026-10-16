"""Accords d'entreprise (ACCO, voir acco.py) dans le tracker :
1. creer() : un événement par accord de PSE, rupture conventionnelle collective ou plan de départs volontaires signé depuis 2024
   dans une entreprise de 50 salariés et plus (source « Accords d'entreprise », rattachement sûr par le SIRET). Ce sont les
   suppressions de postes qui passent souvent sous les radars (pas de BODACC, peu de presse).
2. enrichir() : pour chaque événement du tracker, les accords de l'entreprise liés à l'emploi (y compris activité partielle et
   performance collective) signés de 24 mois avant à 12 mois après."""
import datetime as dt, sys
import acco, collect

SOURCE = "Accords d'entreprise"
TYPE = {"pse": "plan social", "rcc": "départs volontaires", "pdv": "départs volontaires"}
DEBUT = "2024-01-01"

def jour(a): return a.get("date_texte") or a.get("date_depot") or ""

def creer(evs):
    P = acco.par_siren()
    out = []
    for siren, L in P.items():
        L = sorted([a for a in L if a["cat"] in TYPE and not a["avenant"] and jour(a) >= DEBUT], key=jour)
        groupes = []
        for a in L:   # un événement par entreprise et par période de 180 jours (accord de méthode puis accord final = un seul plan)
            if groupes and (dt.date.fromisoformat(jour(a)) - dt.date.fromisoformat(jour(groupes[-1][0]))).days <= 180: groupes[-1].append(a)
            else: groupes.append([a])
        if not groupes: continue
        ent = collect.entreprise(siren)
        lo, hi = collect.TR.get(ent.get("tranche") or "", (None, None))
        if lo is None or lo < collect.SEUIL: continue
        for g in groupes:
            princ = next((a for a in g if a["cat"] in ("rcc", "pdv") and "méthode" not in a["titre"].lower()), None) or \
                    next((a for a in g if "méthode" not in a["titre"].lower()), g[0])
            cat = princ["cat"]
            out.append({"id": "acco-" + princ["id"], "source": SOURCE, "type": TYPE[cat], "entreprise": ent.get("nom") or princ["raison_sociale"],
                        "siren": siren, "siret": princ["siret"], "lien": "siren_source", "naf": ent.get("naf"),
                        "commune": ent.get("commune"), "dep": ent.get("dep"), "insee": ent.get("insee"), "lat": ent.get("lat"), "lon": ent.get("lon"),
                        "emplois_min": None, "emplois_max": None, "emplois_precision": None, "effectif_entreprise": [lo, hi],
                        "date": jour(g[0]), "date_publication": princ.get("date_diffusion"),
                        "detail": f"{acco.LIB[cat].capitalize()} : « {princ['titre'][:200]} »" + (f" ({len(g)} accords)" if len(g) > 1 else ""),
                        "titre_accord": princ["titre"], "url": princ["url"], "accords": [resume(a) for a in g]})
    print(f"accords d'entreprise : {len(out)} événements (PSE, RCC, départs volontaires) depuis {DEBUT}", file=sys.stderr)
    return out

def resume(a):
    return {"cat": a["cat"], "libelle": acco.LIB[a["cat"]], "titre": a["titre"], "date": jour(a), "url": a["url"], "avenant": a["avenant"],
            "syndicats": a.get("syndicats") or []}

def enrichir(evs):
    P = acco.par_siren(); n = 0
    for e in evs:
        if e.get("source") == SOURCE or not e.get("siren") or not e.get("date"): continue
        L = P.get(e["siren"])
        if not L: continue
        j = dt.date.fromisoformat(e["date"][:10])
        lo, hi = (j - dt.timedelta(days=730)).isoformat(), (j + dt.timedelta(days=365)).isoformat()
        m = sorted([resume(a) for a in L if lo <= jour(a) <= hi], key=lambda a: a["date"])
        if m: e["accords"] = m[-8:]; n += 1
    print(f"accords d'entreprise : {n} événements du tracker avec un accord lié à l'emploi", file=sys.stderr)
