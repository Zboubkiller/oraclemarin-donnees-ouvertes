"""Vérification du LIEU : l'établissement cité par l'annonce existe-t-il chez la société rattachée ?
Compare la commune (écrite dans l'annonce, jamais déduite de la société elle-même) et le département aux établissements de la société (principal et secondaires,
ouverts et fermés) du répertoire Sirene (table etab_tous de sirene_cible.db, repli sur sirene.db). Écrit e["verif_site"] :
  niveau : "commune" (un établissement dans la commune citée), "departement" (dans le département, pas dans la commune), "aucun" (aucun dans le département), "inconnu"
  communes : établissements du département (commune, état, date de fermeture), ferme : date de fermeture de l'établissement de la commune si fermé."""
import os, re, sqlite3, unicodedata
H = os.path.dirname(os.path.abspath(__file__))

def norm(c):
    c = unicodedata.normalize("NFD", (c or "").lower()).encode("ascii", "ignore").decode()
    c = re.sub(r"\b(arrondissement|cedex)\b|\b\d+(er|e|eme)\b|\d+", " ", c)
    c = re.sub(r"\bsaint(e?)\b", lambda m: "st" + m.group(1), c)
    return re.sub(r"[^a-z]+", "", c)

def dep_de(insee, cp=None):
    i = insee or ""
    if i.startswith(("97", "98")): return i[:3]
    if i[:2] in ("2A", "2B"): return i[:2]
    return i[:2] if len(i) >= 2 else (cp or "")[:2]

def meme_commune(a, b):
    a, b = norm(a), norm(b)
    return bool(a and b and (a == b or (a in ("paris", "lyon", "marseille") and b.startswith(a)) or (b in ("paris", "lyon", "marseille") and a.startswith(b))))

def verifier(evs):
    base = os.path.join(H, "sirene_cible.db")
    Sc = sqlite3.connect(base) if os.path.exists(base) else None
    Sl = sqlite3.connect(os.path.join(H, "sirene.db"))
    cache, n = {}, {"commune": 0, "departement": 0, "aucun": 0, "inconnu": 0}
    def etabs(s):
        if s in cache: return cache[s]
        L = []
        if Sc:
            try: L = [(r[0], r[1], r[2], r[3], r[4]) for r in Sc.execute("select commune, insee, cp, etat, date_etat from etab_tous where siren=?", (s,))]
            except sqlite3.OperationalError: L = []
        if not L:
            L = [(r[0], r[1], r[2], r[3], r[4]) for r in Sl.execute("select commune, insee, cp, etat, date_etat from etab where siren=?", (s,))]
        cache[s] = L; return L
    for e in evs:
        s = e.get("siren")
        if not s or e.get("source") == "BODACC": continue
        e.pop("verif_site", None)
        L = etabs(s)
        dep = e.get("dep"); com = None if (e.get("commune_deduite") or e.get("approx")) else e.get("commune")
        if not L or not (dep or com):
            e["verif_site"] = {"niveau": "inconnu"}; n["inconnu"] += 1; continue
        if e.get("plan_multi_societes"):
            e["verif_site"] = {"niveau": "inconnu"}; n["inconnu"] += 1; continue
        ds = [x for x in L if dep and dep_de(x[1], x[2]) == dep]
        dc = [x for x in L if com and meme_commune(x[0], com)]
        if dc: niv = "commune"
        elif ds: niv = "departement"
        elif dep or com: niv = "aucun"
        else: niv = "inconnu"
        n[niv] += 1
        v = {"niveau": niv, "communes": sorted({(x[0] or "").title() + (" (fermé)" if x[3] == "F" else "") for x in (dc or ds)})[:6]}
        fermes = [x[4] for x in dc if x[3] == "F" and x[4]]
        if fermes and not [x for x in dc if x[3] == "A"]: v["ferme"] = max(fermes)[:10]                 # tous les établissements de la commune sont fermés : date de la dernière fermeture
        e["verif_site"] = v
    return n
