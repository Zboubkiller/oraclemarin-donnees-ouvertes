"""Propositions automatiques de SIREN pour la file « CGT » (jamais enregistrées : l'humain valide d'un clic).
Règle : une seule société dont le nom contient tous les mots distinctifs du nom cité ET qui a un établissement (même fermé) dans un département cité,
ni employeur public, ni association/CSE, taille compatible avec le nombre d'emplois. Sinon : pas de proposition, la raison du doute est gardée.
Sortie : auto_prop.json  {id_carte: {siren, nom, raison, etat, effectif} | {doute: raison}}"""
import json, os, re, sys, time, unicodedata, urllib.parse, urllib.request
H = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, H)
import validation_server as V

API = "https://recherche-entreprises.api.gouv.fr/search?"
GENERIQUES = set("""sas sa sarl sasu snc eurl sci societe ste groupe group france francaise francais de du des la le les et d l en au aux sur sous
industrie industries usine usines site sites cimenterie verrerie fonderie equipementier magasin magasins enseigne holding international europe manufacturing
services service solutions systems system technologies technology automotive""".split())
TRMAX = {"NN": None, "00": 0, "01": 2, "02": 5, "03": 9, "11": 19, "12": 49, "21": 99, "22": 199, "31": 249, "32": 499, "41": 999, "42": 1999, "51": 4999, "52": 9999, "53": 10 ** 9}
TRMIN = {"NN": None, "00": 0, "01": 1, "02": 3, "03": 6, "11": 10, "12": 20, "21": 50, "22": 100, "31": 200, "32": 250, "41": 500, "42": 1000, "51": 2000, "52": 5000, "53": 10000}
NON_SOCIETE = re.compile(r"^(cse|ce |comite|comit|association|ass |amicale|sci |syndicat|gie |mairie|commune|departement|region)", re.I)

def norm(s):
    s = unicodedata.normalize("NFD", (s or "").lower()); s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", s).strip()

def toks(s, tout=False):
    t = norm(s).split()
    return [x for x in t if tout or (x not in GENERIQUES and len(x) > 1)]

def appel(q, dep=None):
    p = {"q": q, "per_page": 10}
    if dep: p["departement"] = dep
    for essai in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(API + urllib.parse.urlencode(p), headers={"User-Agent": "plans-sociaux/1.0 (contact: quentinclosset@gmail.com)"}), timeout=20) as r:
                time.sleep(0.2); return json.load(r).get("results", [])
        except Exception:
            time.sleep(1.5)
    return []

_BASE = None
def deja_en_base(x):
    """Autre événement (presse, BODACC…) de la base déjà identifié À LA MAIN sur la même entreprise, dans le même département : le SIREN est connu."""
    global _BASE
    if _BASE is None:
        E = json.load(open(os.path.join(H, "public", "data.json"), encoding="utf-8"))["evenements"]
        _BASE = [e for e in E if not str(e.get("source", "")).startswith("CGT") and e.get("siren") and (e.get("valide_humain") or e.get("ident_humain"))]
    need = set(toks(x["cite"]))
    if not need: return None
    deps = {x.get("dep")} | {d for c in x.get("composantes") or [] for d in c.get("departements") or []}
    trouves = {}
    for e in _BASE:
        tn = set(toks(e.get("entreprise"))) | set(toks(e.get("titre")))
        if need <= tn and ((e.get("dep") in deps) if len(need) == 1 else (not e.get("dep") or e["dep"] in deps)):
            trouves.setdefault(e["siren"], e)
    if len(trouves) != 1: return None
    sr, e = next(iter(trouves.items()))
    r = V.sqlite3.connect(os.path.join(H, "sirene.db")).execute("select nom, tranche from ul where siren=?", (sr,)).fetchone() if hasattr(V, "sqlite3") else None
    return {"siren": sr, "nom": r[0] if r else sr, "etat": "A", "effectif": r[1] if r else "NN", "siege": None,
            "raison": "déjà identifié à la main dans la base (%s, %s)" % (e.get("source"), e.get("date"))}

def proposer(x):
    b = deja_en_base(x)
    if b: return b
    cite = x["cite"] or ""
    deps = []
    for c in x.get("composantes") or []:
        for d in c.get("departements") or []:
            if d not in deps: deps.append(d)
    if x.get("dep") and x["dep"] not in deps: deps.insert(0, x["dep"])
    if not deps: return {"doute": "aucun département cité"}
    parts = [p.strip() for p in re.split(r"\s*/\s*|\s+et\s+", cite) if len(p.strip()) >= 3][:3] or [cite]
    if len(parts) > 1: return {"doute": "plusieurs entités citées (" + " / ".join(parts) + ")"}
    need = set(toks(parts[0]))
    if not need: return {"doute": "nom trop générique"}
    trouves = {}
    for d in deps[:4]:
        for r in appel(parts[0], d):
            nom = r.get("nom_complet") or ""
            if NON_SOCIETE.search(norm(nom)) or (r.get("nature_juridique") or "")[:1] in ("7", "8", "9"): continue
            nom0 = re.sub(r"\(.*?\)", " ", nom)
            if (r.get("nature_juridique") or "")[:1] == "1": continue          # entrepreneur individuel : jamais une entreprise de cette taille
            if need == set(toks(nom0)):
                trouves[r["siren"]] = r
    if not trouves: return {"doute": "aucune société de ce nom avec un établissement dans " + ", ".join(deps[:4])}
    L = list(trouves.values())
    if len(L) > 1:
        exact = [r for r in L if set(toks(r["nom_complet"])) == need]
        if len(exact) == 1: L = exact
        else:
            actifs = [r for r in L if r.get("etat_administratif") == "A"]
            if len(actifs) == 1: L = actifs
            else: return {"doute": "%d sociétés possibles : %s" % (len(L), ", ".join(r["nom_complet"] + " " + r["siren"] for r in L[:4]))}
    r = L[0]; tr = r.get("tranche_effectif_salarie") or "NN"; e = x.get("emplois") or 0
    if r.get("etat_administratif") == "C" and (r.get("date_fermeture") or "9999")[:4] < (x.get("date") or "0000")[:4]:
        return {"doute": "société cessée en %s, avant l'annonce : %s %s" % ((r.get("date_fermeture") or "")[:4], r["nom_complet"], r["siren"])}
    mx = TRMAX.get(tr)
    if mx is not None and e and r.get("etat_administratif") == "A" and mx < e * 0.25:
        return {"doute": "société trop petite (%s) pour %d emplois : %s %s" % (tr, e, r["nom_complet"], r["siren"])}
    return {"siren": r["siren"], "nom": r["nom_complet"], "etat": r.get("etat_administratif"), "effectif": tr, "siege": r["siege"].get("commune"),
            "raison": "nom identique et établissement dans le " + ", ".join(deps[:3])}

def main():
    out = {}
    cartes = V.cgt_liste()
    for i, x in enumerate(cartes):
        try: out[x["cle"]] = proposer(x)
        except Exception as ex: out[x["cle"]] = {"doute": "erreur : %s" % ex}
    json.dump(out, open(os.path.join(H, "auto_prop.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    ok = sum(1 for v in out.values() if v.get("siren"))
    print(f"{len(cartes)} cartes CGT : {ok} propositions, {len(cartes) - ok} laissées de côté")
    for x in cartes:
        v = out[x["cle"]]
        print(("OK  " if v.get("siren") else "--  ") + (x["cite"] or "")[:34].ljust(34), (v.get("siren", "") + " " + v.get("nom", "")) if v.get("siren") else v["doute"][:90])

if __name__ == "__main__":
    main()
