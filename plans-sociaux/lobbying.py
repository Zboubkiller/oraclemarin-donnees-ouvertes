"""Lobbying déclaré à la HATVP (répertoire des représentants d'intérêts, données ouvertes, mise à jour quotidienne).
Le fichier complet (~140 Mo) est téléchargé au plus une fois par semaine et réduit à un index par SIREN (hatvp_index.json).
Écrit e["lobbying"] = {nom, annee, depenses (tranche déclarée), activites, salaries, objets, url} pour l'entreprise ou,
à défaut, pour son groupe quand celui-ci est un déclarant identifié par son nom exact."""
import json, os, re, sys, time, unicodedata, urllib.request
H = os.path.dirname(os.path.abspath(__file__))
URL = "https://www.hatvp.fr/agora/opendata/agora_repertoire_opendata.json"
IDX = os.path.join(H, "hatvp_index.json")

def norm(s): return re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFD", (s or "").lower()).encode("ascii", "ignore").decode())

def construire_index():
    tmp = "/tmp/hatvp_opendata.json"
    with urllib.request.urlopen(urllib.request.Request(URL, headers={"User-Agent": "tracker-plans-sociaux/0.9"}), timeout=600) as r, open(tmp, "wb") as f:
        while True:
            b = r.read(1 << 20)
            if not b: break
            f.write(b)
    pub = json.load(open(tmp, encoding="utf-8"))["publications"]; os.remove(tmp)
    idx = {}
    for p in pub:
        ex = []
        for e in p.get("exercices") or []:
            pc = e.get("publicationCourante") or {}
            if not pc.get("montantDepense"): continue
            objets = [a.get("publicationCourante", {}).get("objet") for a in pc.get("activites") or [] if a.get("publicationCourante", {}).get("objet")]
            ex.append({"annee": (pc.get("dateFin") or "")[-4:], "depenses": pc["montantDepense"], "salaries": pc.get("nombreSalaries"),
                       "activites": pc.get("nombreActivite") or len(objets), "objets": objets[:3]})
        if not ex: continue
        ex.sort(key=lambda x: x["annee"])
        idx[p.get("identifiantNational")] = {"nom": p.get("denomination"), "type": p.get("typeIdentifiantNational"), "exercices": ex[-4:]}
    json.dump(idx, open(IDX + ".tmp", "w", encoding="utf-8"), ensure_ascii=False); os.replace(IDX + ".tmp", IDX)
    print("hatvp : index de", len(idx), "déclarants", file=sys.stderr)

def charger():
    if not os.path.exists(IDX) or time.time() - os.path.getmtime(IDX) > 7 * 86400:
        try: construire_index()
        except Exception as ex: print("hatvp :", ex, file=sys.stderr)
    try: return json.load(open(IDX, encoding="utf-8"))
    except Exception: return {}

def resume(i, ident):
    x = i["exercices"][-1]
    return {"nom": i["nom"], "annee": x["annee"], "depenses": x["depenses"], "activites": x["activites"], "salaries": x["salaries"],
            "objets": x["objets"], "exercices": [{"annee": e["annee"], "depenses": e["depenses"]} for e in i["exercices"]],
            "url": f"https://www.hatvp.fr/fiche-organisation/?organisation={ident}"}

def enrichir(evs):
    idx = charger()
    if not idx: return evs
    par_nom = {norm(v["nom"]): (k, v) for k, v in idx.items()}
    n = 0
    for e in evs:
        s = e.get("siren")
        if s and s in idx:
            e["lobbying"] = dict(resume(idx[s], s), niveau="entreprise"); n += 1
        elif e.get("groupe") and norm(e["groupe"]["nom"]) in par_nom:
            # le lobbying d'un groupe actionnaire porte souvent sur tout autre chose (Eurazeo : fiscalité de l'investissement ;
            # CMA CGM : taxe au tonnage, rattaché à La Provence) : gardé à part, jamais attribué à la filiale
            k, v = par_nom[norm(e["groupe"]["nom"])]
            e["lobbying_groupe"] = dict(resume(v, k), niveau="groupe")
    print("lobbying :", n, "événements", file=sys.stderr)
    return evs
