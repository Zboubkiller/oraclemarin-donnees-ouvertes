#!/usr/bin/env python3
"""Recherche des SIREN manquants (annonces de presse et lignes CGT sans SIREN) dans le répertoire Sirene (API recherche-entreprises).
Règle sûre : nom identique (tous les mots distinctifs, et rien de plus), société active unique (avec département si l'annonce en a un),
ni association/employeur public, taille compatible avec le nombre d'emplois. Sinon : aucune proposition, la raison du doute est gardée.
Sortie : siren_prop.json ; avec --appliquer, les propositions sûres sont écrites dans validations.json (identification, marque « auto »)."""
import json, os, re, sys, time
H = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, H)
import auto_ident as A, commun

E = json.load(open(os.path.join(H, "public", "data.json"), encoding="utf-8"))["evenements"]
cibles = [e for e in E if not e.get("siren") and e.get("source") != "BODACC" and (e.get("entreprise") or "").strip()
          and e.get("entreprise") != e.get("titre") and not e.get("partie_de")]

def nettoyer(n):
    n = re.sub(r"\(.*?\)", " ", n or "")
    n = re.sub(r"^(la |le |les |l[’'])", "", n.strip(), flags=re.I)
    n = re.sub(r"\b(groupe|société|ste|entreprise|usine|site|enseigne|magasin|magasins|clinique|établissements?|ets)\b", " ", n, flags=re.I)
    return re.sub(r"\s+", " ", n).strip(" -–·,.")

def proposer(e):
    nom = nettoyer(e["entreprise"])
    if len(nom) < 3 or "·" in nom or " et " in nom.lower() or "/" in nom: return {"doute": "nom composite ou trop court"}
    if A.NON_SOCIETE.search(A.norm(nom)): return {"doute": "association, CSE ou employeur public"}
    need = set(A.toks(nom))
    if not need: return {"doute": "nom trop générique"}
    dep = e.get("dep")
    res = A.appel(nom, dep) if dep else A.appel(nom)
    trouves = {}
    for r in res:
        nj = (r.get("nature_juridique") or "")[:1]
        if nj in ("1", "7", "8", "9") or A.NON_SOCIETE.search(A.norm(r.get("nom_complet") or "")): continue
        noms = [re.sub(r"\(.*?\)", " ", r.get("nom_complet") or "")] + re.findall(r"\((.*?)\)", r.get("nom_complet") or "")
        if any(set(A.toks(x)) == need for x in noms if x.strip()): trouves[r["siren"]] = r
    if not trouves: return {"doute": "aucune société de ce nom" + (" dans le " + dep if dep else "")}
    L = list(trouves.values())
    if len(L) > 1:
        act = [r for r in L if r.get("etat_administratif") == "A"]
        if len(act) == 1: L = act
        else: return {"doute": "%d sociétés possibles : %s" % (len(L), ", ".join(r["nom_complet"][:30] + " " + r["siren"] for r in L[:4]))}
    r = L[0]; tr = r.get("tranche_effectif_salarie") or "NN"; n = e.get("emplois_min") or 0
    if not dep and len(need) < 2 and tr in ("NN", "00", "01", "02", "03"): return {"doute": "nom court, sans département, société de petite taille : trop ambigu"}
    if r.get("etat_administratif") == "C" and (r.get("date_fermeture") or "9999")[:4] < (e.get("date") or "0000")[:4]:
        return {"doute": "société cessée en %s avant l'annonce : %s %s" % ((r.get("date_fermeture") or "")[:4], r["nom_complet"], r["siren"])}
    mx = A.TRMAX.get(tr)
    if mx is not None and n and mx < n * 0.25: return {"doute": "société trop petite (%s) pour %d emplois : %s %s" % (tr, n, r["nom_complet"], r["siren"])}
    return {"siren": r["siren"], "nom": r["nom_complet"], "etat": r.get("etat_administratif"), "effectif": tr, "siege": r["siege"].get("commune"),
            "raison": "nom identique" + (" et établissement dans le " + dep if dep else ", société unique en France")}

def main():
    out = {}
    for e in cibles:
        try: out[e["id"]] = proposer(e)
        except Exception as ex: out[e["id"]] = {"doute": "erreur : %s" % ex}
    json.dump(out, open(os.path.join(H, "siren_prop.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    ok = {k: v for k, v in out.items() if v.get("siren")}
    print(len(cibles), "annonces sans SIREN ;", len(ok), "propositions sûres")
    if "--appliquer" in sys.argv:
        fp = os.path.join(H, "validations.json"); V = json.load(open(fp, encoding="utf-8")); I = V.setdefault("identification", {}); n = 0
        for k, v in ok.items():
            if k in I: continue
            I[k] = {"choix": "siren:" + v["siren"], "date": time.strftime("%Y-%m-%d %H:%M"), "auto": True, "raison": v["raison"]}; n += 1
        json.dump(V, open(fp, "w", encoding="utf-8"), ensure_ascii=False, indent=1); print(n, "écrites dans validations.json (auto)")
    for k, v in out.items():
        e = next(x for x in cibles if x["id"] == k)
        print(("OK  " if v.get("siren") else "--  ") + e["entreprise"][:32].ljust(32), (v["siren"] + " " + v["nom"][:34] + " [" + v["raison"] + "]") if v.get("siren") else v["doute"][:100])

if __name__ == "__main__":
    main()
