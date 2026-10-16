"""Chiffres de l'état des lieux de la liste noire CGT : ce que dit la CGT, ce que le site a rapproché, confirmé, corroboré. Aucune interprétation : des comptes."""
import collections, json, os, re, sys
H = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, H)
import commun

def est_cgt(e): return str(e.get("source", "")).startswith("CGT")
def src_indep(e):
    """Sources autres que la CGT et que les accords d'entreprise (qui ne confirment pas le plan) : presse, BODACC, etc."""
    L = [s for s in e.get("sources") or [] if not str(s.get("source", "")).startswith("CGT") and s.get("source") != "Accords d'entreprise"]
    return [s for s in L if dans_fenetre(e, s)]

FENETRE = (-120, 540)     # jours entre l'annonce et l'article : un article d'historique (reprise, ancienne procédure) s'affiche sur la fiche mais ne « recoupe » pas ce plan
def dans_fenetre(e, s):
    import datetime as dt
    try: da, ds = dt.date.fromisoformat((e.get("date") or "")[:10]), dt.date.fromisoformat((s.get("date") or "")[:10])
    except ValueError: return True          # une des deux dates manque : on garde l'article
    return FENETRE[0] <= (ds - da).days <= FENETRE[1]

def site_ferme(e):
    """L'établissement de la commune citée est fermé au répertoire Sirene, à une date compatible avec une annonce de fermeture ou de liquidation."""
    import datetime as dt
    f = (e.get("verif_site") or {}).get("ferme")
    if not f or not re.search(r"ferm|liquidation|cessation|arr[êe]t d.activit", (e.get("detail") or "") + " " + (e.get("titre") or ""), re.I) or not e.get("date"): return False
    try: d, j = dt.date.fromisoformat(f[:10]), dt.date.fromisoformat(e["date"][:10])
    except Exception: return False
    return -270 <= (d - j).days <= 900

def recoupe(e):
    return bool(src_indep(e) or e.get("procedure_bodacc") or e.get("etablissements_fermes") or e.get("fermeture_confirmee") or (e.get("preuve_comptes") or {}).get("recoupe", True) and e.get("preuve_comptes") or site_ferme(e))

def calcul(EV, nb_lignes, nb_pages):
    C = [e for e in EV if est_cgt(e)]
    P = [e for e in C if not commun.exclu_totaux(e)]                         # périmètre : hors employeurs publics, hors France, hors sous-lignes de groupes
    hors = collections.Counter()
    for e in C:
        if commun.exclu_totaux(e):
            hors["employeur public" if e.get("employeur_public") else "hors France" if e.get("hors_france") else "sans entreprise" if e.get("sans_entreprise") else "détail d'un plan de groupe" if e.get("partie_de") else "autre"] += 1
    ident = [e for e in P if e.get("siren")]
    confirme = [e for e in ident if (e.get("verif_ident") or "").startswith(("confirmé", "vérifié")) or e.get("valide_humain") or e.get("ident_humain")]
    presse = [e for e in P if src_indep(e)]
    proc = [e for e in P if e.get("procedure_bodacc")]
    ferme = [e for e in P if e.get("etablissements_fermes") or e.get("fermeture_confirmee")]
    corr = [e for e in P if recoupe(e)]
    lieu = collections.Counter((e.get("verif_site") or {}).get("niveau", "inconnu") for e in ident)
    ferme_sirene = [e for e in P if site_ferme(e)]
    emp = lambda L: sum(e.get("emplois_min") or 0 for e in L)
    try: dec = json.load(open(os.path.join(H, "validations.json"), encoding="utf-8")).get("identification", {})
    except Exception: dec = {}
    nonc = [e for e in P if e not in corr]
    detail = collections.Counter()
    for e in nonc:
        d = (dec.get(e["id"]) or {}).get("choix")
        detail["a_traiter" if (d is None and not e.get("siren")) else "doute" if d == "passer" else "auto" if (e.get("siren") and d is None) else "main"] += 1
    sect = collections.defaultdict(lambda: [0, 0, 0])
    for e in P:
        s = e.get("cgt_secteur") or "Autres"; sect[s][0] += 1; sect[s][1] += e.get("emplois_min") or 0; sect[s][2] += 1 if e in corr else 0
    mois = collections.Counter((e.get("date") or "")[:7] for e in P if e.get("date"))
    dep = collections.defaultdict(lambda: [0, 0])
    pts = []
    for e in P:
        if e.get("lat") and e.get("lon"):
            pts.append({"n": commun.esc(e.get("entreprise") or ""), "lat": float(e["lat"]), "lon": float(e["lon"]), "e": e.get("emplois_min") or 0, "d": e.get("dep"),
                        "c": 1 if e in corr else 0, "l": int(e["cgt_ligne"]) if str(e.get("cgt_ligne", "")).isdigit() else None})
        if e.get("dep"): dep[e["dep"]][0] += 1; dep[e["dep"]][1] += e.get("emplois_min") or 0
    # recoupement avec le reste du site : plans sociaux de la presse sur la même période
    debut = min((e.get("date") for e in C if e.get("date")), default="2023-09")
    seuil = lambda e: (e.get("emplois_min") or 0) >= 50
    presse_seule = [e for e in EV if not est_cgt(e) and e.get("type") == "plan social" and (e.get("date") or "") >= "2023-09" and seuil(e) and not commun.exclu_totaux(e)]
    taille = collections.Counter()
    for e in P:
        n = e.get("emplois_min") or 0
        taille["moins de 50" if n < 50 else "50 à 99" if n < 100 else "100 à 199" if n < 200 else "200 à 499" if n < 500 else "500 et plus"] += 1
    tc = collections.defaultdict(lambda: [0, 0])
    for e in P:
        n = e.get("emplois_min") or 0
        k = "moins de 50" if n < 50 else "50 à 99" if n < 100 else "100 à 199" if n < 200 else "200 à 499" if n < 500 else "500 et plus"
        tc[k][0] += 1; tc[k][1] += 1 if e in corr else 0
    return {
        "lignes_pdf": nb_lignes, "pages": nb_pages, "evenements": len(C), "perimetre": len(P), "hors": dict(hors),
        "emplois_cgt": emp(C), "emplois_perimetre": emp(P),
        "identifiees": len(ident), "confirmees": len(confirme), "emplois_identifiees": emp(ident),
        "presse": len(presse), "procedure_bodacc": len(proc), "fermetures": len(ferme), "corroborees": len(corr), "emplois_corroborees": emp(corr),
        "lieu": dict(lieu), "fermetures_sirene": len(ferme_sirene), "non_verifiees": len(P) - len(corr), "non_detail": dict(detail), "emplois_non_verifiees": emp(P) - emp(corr),
        "secteurs": sorted(([k, *v] for k, v in sect.items()), key=lambda x: -x[2]),
        "mois": sorted(mois.items()), "deps": {k: v for k, v in dep.items()}, "points": pts, "taille": dict(taille),
        "taille_corr": {k: v for k, v in tc.items()},
        "presse_hors_cgt": len(presse_seule), "emplois_presse_hors_cgt": emp(presse_seule),
        "sources_noms": collections.Counter(s.get("source") for e in P for s in src_indep(e)).most_common(10),
    }

if __name__ == "__main__":
    EV = json.load(open(os.path.join(H, "public", "data.json"), encoding="utf-8"))["evenements"]
    I = json.load(open(os.path.join(H, "cgt", "index.json"), encoding="utf-8"))
    d = calcul(EV, len(I["lignes"]), I["pages"])
    d.pop("points")
    print(json.dumps(d, ensure_ascii=False, indent=1))
