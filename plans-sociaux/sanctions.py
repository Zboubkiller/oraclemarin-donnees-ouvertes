"""Sanctions de la DGCCRF pour retards de paiement aux fournisseurs (publication obligatoire, « Injonctions et sanctions »
sur economie.gouv.fr). Le site bloque les robots : la liste est relevée à la main via un navigateur et enregistrée dans
sanctions_dgccrf.json (nom, SIRET, montant, date, adresse de la décision). La publication ne reste en ligne qu'un an.
Écrit e["sanction_delais"] quand l'entreprise (même SIREN) a été sanctionnée."""
import json, os, sys
H = os.path.dirname(os.path.abspath(__file__))
BASE = "https://www.economie.gouv.fr/dgccrf/laction-de-la-dgccrf/injonctions-et-sanctions/"

def charger():
    try: return json.load(open(os.path.join(H, "sanctions_dgccrf.json"), encoding="utf-8"))
    except Exception: return {"sanctions": []}

def enrichir(evs):
    s = charger().get("sanctions", [])
    par = {}
    for x in s: par.setdefault(x["siret"][:9], []).append(x)
    # même groupe : vérifié par registre (GLEIF, Wikidata ou fichier manuel), jamais par le seul nom (« Condat » papeterie ≠ « Condat SA » lubrifiants)
    import groupes, re, unicodedata
    cle = lambda t: re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFD", (t or "").lower()).encode("ascii", "ignore").decode())
    groupes.remplir_cache(par.keys())
    grp = {}
    for sir in par:
        g = groupes.groupe_de(sir)
        if g: grp.setdefault(cle(g["nom"]), []).extend(par[sir])
    fiche = lambda x, niveau: {"montant": x["montant"], "date": x["date"], "nom": x["nom"], "url": BASE + x["page"], "niveau": niveau}
    n = 0
    for e in evs:
        if e.get("siren") in par:
            e["sanction_delais"] = [fiche(x, "entreprise") for x in par[e["siren"]]]; n += 1
        elif e.get("groupe") and cle(e["groupe"]["nom"]) in grp:
            e["sanction_delais"] = [fiche(x, "groupe") for x in grp[cle(e["groupe"]["nom"])]]; n += 1
    print("sanctions délais de paiement :", n, "événements", file=sys.stderr)
    return evs
