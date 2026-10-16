"""Règles automatiques tirées des validations humaines, appliquées aux rattachements par le nom (probables ou indicatifs) qui
n'ont pas été validés à la main :
1. entreprise créée après l'annonce (société du repreneur) -> retrait ;
2. entreprise déjà cessée plus d'un mois avant l'annonce -> retrait ;
3. filiale nommée dans le texte (« Orange Bank », « sa filiale Engie Home Services ») alors que l'entreprise proposée est une autre
   société (souvent la maison mère) -> retrait ;
4. redressement ou liquidation d'un magasin ou d'une concession de chaîne rattaché à la société nationale (1 000 salariés et plus,
   grande distribution, automobile, restauration) -> retrait (c'est la société du franchisé ou du locataire-gérant) ;
5. plus de postes supprimés que de salariés dans l'entreprise proposée -> plan sur plusieurs sociétés : ni validé ni proposé ;
6. holding proposée (70.10Z) alors qu'une société active du même nom a une activité réelle et plus de salariés (Fleury Michon ->
   Fleury Michon LS) -> bascule sur la société opérationnelle (rattachement par le nom, à confirmer)."""
import os, re, sqlite3, sys
import collect, sirene_rag
H = os.path.dirname(os.path.abspath(__file__))
GENERIQUES = {"france", "groupe", "group", "usine", "site", "sites", "magasin", "magasins", "hypermarche", "supermarche", "agence", "centre", "sas", "sa",
              "sarl", "entreprise", "societe", "industries", "industrie", "international", "holding", "services", "service"}
FRANCHISE = ("47.11", "47.19", "45.11", "45.19", "45.20", "56.10", "47.30", "47.52")

def operationnelle(S, siren, nom_legal, lo):
    """Société active dont le nom commence par celui de la holding, avec une activité réelle et plus de salariés (la plus grosse)."""
    q = " ".join('"%s"' % j for j in sirene_rag.jetons(nom_legal))
    meilleur = None
    if not q: return None
    for (s2,) in S.execute("select distinct siren from noms where noms match ? and siren <> ? limit 30", (q, siren)):
        v = S.execute("select nom, naf, tranche, etat from ul where siren=?", (s2,)).fetchone()
        if not v or v[3] != "A" or (v[1] or "").startswith(("70.10", "64.")) or not (v[0] or "").upper().startswith((nom_legal or "").upper()): continue
        lo2 = collect.TR.get(v[2] or "", (None, None))[0]
        if lo2 and lo2 > (lo or 0) and (not meilleur or lo2 > meilleur[1]): meilleur = (s2, lo2, v[1])
    return meilleur

def appliquer(evs):
    import verif_ident
    S = sqlite3.connect(os.path.join(H, "sirene.db"))
    n = {}; bascules = []
    def marque(e, motif, retrait=True):
        n[motif] = n.get(motif, 0) + 1
        if retrait: verif_ident.retirer(e, "règle automatique : " + motif)
        else: e["fiable"] = False; e["verif_ident"] = motif; e["regle_auto"] = motif
    for e in evs:
        r = e.get("rattachement_retire") or {}
        if not e.get("siren") and r.get("siren") and "humaine" in (r.get("motif") or "") and e.get("source") != "BODACC":
            v = S.execute("select nom, naf, tranche from ul where siren=?", (r["siren"],)).fetchone()
            if v and (v[1] or "").startswith("70.10") and (collect.TR.get(v[2] or "", (0, 0))[0] or 0) < 250:
                m = operationnelle(S, r["siren"], v[0], collect.TR.get(v[2] or "", (0, 0))[0])
                if m:
                    e.update(siren=m[0], naf=m[2], siren_holding=r["siren"], fiable=False, lien="nom_seul"); bascules.append(e)
                    n["holding refusée : société opérationnelle proposée"] = n.get("holding refusée : société opérationnelle proposée", 0) + 1
            continue
        if e.get("source") == "BODACC" or not e.get("siren") or e.get("valide_humain") or e.get("ident_recherche") or e.get("lien") not in ("nom+dep", "nom_seul"): continue
        u = S.execute("select nom, naf, tranche, etat, date_etat, creation from ul where siren=?", (e["siren"],)).fetchone()
        if not u: continue
        d = (e.get("date") or "")[:10]
        nom_legal, naf, tranche, etat, date_etat, creation = u
        lo, hi = collect.TR.get(tranche or "", (None, None))
        if (naf or "").startswith("70.10") and (lo or 0) < 250:
            meilleur = operationnelle(S, e["siren"], nom_legal, lo)
            if meilleur:
                ancien = e["siren"]
                for k in ("siret", "comptes", "argent_public", "proximite", "categorie", "tranche", "effectif_entreprise", "verif_ident"): e.pop(k, None)
                e.update(siren=meilleur[0], naf=meilleur[2], siren_holding=ancien, fiable=False, lien="nom_seul" if e.get("lien") == "nom_seul" else "nom+dep")
                bascules.append(e); n["holding remplacée par la société opérationnelle"] = n.get("holding remplacée par la société opérationnelle", 0) + 1
                continue
        if d and creation and creation[:10] > d and creation[:7] != d[:7]:
            marque(e, "entreprise créée après l'annonce (société du repreneur)"); continue
        if d and etat == "C" and date_etat and date_etat[:10] < d and date_etat[:7] != d[:7]:
            marque(e, "entreprise déjà cessée au moment de l'annonce"); continue
        cite = set(sirene_rag.jetons(e.get("entreprise"))) - GENERIQUES
        legal = set(sirene_rag.jetons(nom_legal)) - GENERIQUES
        communes = set(sirene_rag.jetons(e.get("commune"))) if e.get("commune") else set()
        en_plus = cite - legal - communes
        if legal and legal < cite and en_plus:
            marque(e, "filiale ou entité nommée dans le texte, autre que l'entreprise proposée"); continue
        texte = f"{e.get('titre') or ''} {e.get('detail') or ''}"
        m = re.search(r"(?:sa |la |une )?filiale ([A-ZÉ][\w'’-]*(?: [A-ZÉ&][\w'’-]*){0,3})", texte)
        if m:
            fil = set(sirene_rag.jetons(m.group(1))) - GENERIQUES
            if fil and not fil <= set(sirene_rag.jetons(nom_legal)):
                marque(e, "filiale ou entité nommée dans le texte, autre que l'entreprise proposée"); continue
        if e.get("type") in ("redressement", "liquidation") and lo and lo >= 1000 and (naf or "").startswith(FRANCHISE):
            marque(e, "magasin ou concession de chaîne : procédure du franchisé, pas de la société nationale"); continue
        if e.get("emplois_precision") == "annoncé" and hi and (e.get("emplois_min") or 0) > hi:
            marque(e, "plus de postes que de salariés : plan sur plusieurs sociétés du groupe", retrait=False)
    if bascules:
        try:
            import aides; aides.enrichir(bascules)
        except Exception as ex: print("règles automatiques (aides) :", ex, file=sys.stderr)
    print("règles automatiques :", ", ".join(f"{k} : {v}" for k, v in n.items()) or "aucun cas", file=sys.stderr)
