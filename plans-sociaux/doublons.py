"""Doublons d'annonces : un même plan présent deux fois (articles à des dates différentes, ligne CGT et article, deux accords...).
Compare, pour chaque entreprise (SIREN, sinon nom), les annonces non BODACC deux à deux : dates proches, mêmes emplois, textes qui se recoupent.
Niveau A (sûr) : fusionné automatiquement : l'annonce secondaire sort des totaux (doublon_de) et ses sources passent à l'annonce principale. Niveau B : proposé dans l'onglet Doublons de la validation.
Les décisions humaines (validations.json, « doublon ») priment : « oui » = fusion, « non » = deux plans distincts (la paire n'est plus proposée). Écrit doublons_candidats.json."""
import datetime as dt, itertools, json, os, re, sys, unicodedata
H = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, H)
STOP = {"dans", "avec", "pour", "plan", "social", "emplois", "emploi", "postes", "poste", "licenciements", "licenciement", "suppression", "suppressions", "annonce", "entreprise", "groupe", "société", "usine", "site", "salariés", "france", "selon", "après", "leurs", "cette", "entre", "sont", "plus", "mois", "dont", "vers", "chez", "pse"}
def norm(s): return re.sub(r"[^a-z0-9 ]", " ", unicodedata.normalize("NFD", (s or "").lower()).encode("ascii", "ignore").decode())
def jetons(e):
    nom = set(norm(e.get("entreprise")).split())
    return {w for w in norm((e.get("titre") or "") + " " + (e.get("detail") or "")).split() if len(w) >= 4 and w not in STOP and w not in nom}
def jour(e):
    try: return dt.date.fromisoformat((e.get("date") or "")[:10])
    except ValueError: return None

def eligible(e):
    so = str(e.get("source", ""))
    return not (so == "BODACC" or so.startswith(("Sirene", "Accords")) or e.get("partie_de") or e.get("sans_entreprise") or e.get("hors_france") or e.get("doublon_de") or not e.get("entreprise") or e.get("entreprise") == e.get("titre"))

def score(a, b):
    s, why = 0, []
    if a.get("url") and a.get("url") == b.get("url"): return 6, ["même lien"]
    da, db = jour(a), jour(b)
    if da and db:
        d = abs((da - db).days)
        if d <= 45: s += 2; why.append(f"{d} jours d'écart")
        elif d <= 120: s += 1; why.append(f"{d} jours d'écart")
        elif d > 180:
            # plan repris plus tard par une autre source (ligne CGT puis article un an après) : même nombre, ou nombres presque identiques
            ea, eb = a.get("emplois_min"), b.get("emplois_min")
            if d > 900 or not (ea and eb): return -9, []
            ecart = abs(ea - eb) / max(ea, eb)
            if ea >= 30 and ecart == 0: return 5, [f"même nombre ({ea}), {round(d / 30)} mois d'écart : même plan repris par une autre source"]
            if max(ea, eb) >= 100 and ecart <= 0.02: return 5, [f"nombres presque identiques ({ea} / {eb}), {round(d / 30)} mois d'écart"]
            if max(ea, eb) >= 100 and ecart <= 0.15: return 3, [f"nombres proches ({ea} / {eb}), {round(d / 30)} mois d'écart"]
            return -9, []
    ea, eb = a.get("emplois_min"), b.get("emplois_min")
    if ea and eb:
        if ea == eb: s += 3; why.append(f"même nombre ({ea})")
        elif abs(ea - eb) / max(ea, eb) <= 0.1: s += 2; why.append(f"nombres proches ({ea} / {eb})")
        elif abs(ea - eb) / max(ea, eb) > 0.25: s -= 3; why.append(f"nombres différents ({ea} / {eb})")
    elif ea or eb: s += 1
    if not (da and db) and ea and eb and ea == eb and ea >= 30: return 5, [f"même nombre ({ea}), date manquante sur l'une des lignes"]
    ja, jb = jetons(a), jetons(b)
    if ja and jb:
        j = len(ja & jb) / len(ja | jb)
        if j >= 0.3: s += 1; why.append("textes proches")
    return s, why

def paires(evs):
    G = {}
    for e in evs:
        if not eligible(e): continue
        G.setdefault(e.get("siren") or "n:" + norm(e.get("entreprise")), []).append(e)
    out = []
    for k, L in G.items():
        for a, b in itertools.combinations(L, 2):
            if str(a.get("source", "")).startswith("CGT") and str(b.get("source", "")).startswith("CGT") and a.get("cgt_ligne") != b.get("cgt_ligne") and a.get("emplois_min") != b.get("emplois_min"): continue
            s, why = score(a, b)
            if s >= 3: out.append((s, a, b, why))
    return out

def principale(a, b):
    """L'annonce conservée : la ligne CGT, sinon celle qui a un nombre, sinon la plus ancienne."""
    cg = lambda e: str(e.get("source", "")).startswith("CGT")
    ordre = lambda e: (not cg(e), not e.get("emplois_min"), e.get("date") or "9999", e["id"])
    return (a, b) if ordre(a) <= ordre(b) else (b, a)

def cle(a, b): return "|".join(sorted((a["id"], b["id"])))

def paires_croisees(evs):
    """Même plan sous deux noms ou deux SIREN (société et groupe, nom abrégé) : même nombre d'emplois, dates proches, un mot distinctif commun dans le nom (niveau B seulement)."""
    L = [e for e in evs if eligible(e) and (e.get("emplois_min") or 0) >= 20 and jour(e)]
    par_n = {}
    for e in L: par_n.setdefault(e["emplois_min"], []).append(e)
    deja = {(a["id"], b["id"]) for _, a, b, _ in paires(evs)}; out = []
    for n, G in par_n.items():
        for a, b in itertools.combinations(G, 2):
            if (a.get("siren") or "n:" + norm(a.get("entreprise"))) == (b.get("siren") or "n:" + norm(b.get("entreprise"))): continue
            if abs((jour(a) - jour(b)).days) > 60: continue
            ta = {w for w in norm(a["entreprise"]).split() if len(w) >= 5 and w not in STOP}; tb = {w for w in norm(b["entreprise"]).split() if len(w) >= 5 and w not in STOP}
            if ta & tb: out.append((3, a, b, [f"même nombre ({n})", f"nom commun : {sorted(ta & tb)[0]}", f"{abs((jour(a) - jour(b)).days)} jours d'écart"]))
    return out

def enrichir(evs):
    try: D = json.load(open(os.path.join(H, "validations.json"), encoding="utf-8")).get("doublon", {})
    except Exception: D = {}
    P = paires(evs) + paires_croisees(evs); cand = []; auto = hum = 0
    par_id = {e["id"]: e for e in evs}
    for s, a, b, why in sorted(P, key=lambda x: -x[0]):
        k = cle(a, b); d = D.get(k, {}).get("choix"); prin, sec = principale(a, b)
        if d == "non": continue
        if d == "oui" or (d is None and s >= 5):
            if sec.get("doublon_de") or prin.get("doublon_de") == sec["id"]: continue
            sec["doublon_de"] = prin["id"]; sec["doublon_niveau"] = "humain" if d == "oui" else "auto"
            deja = [x.get("url") for x in prin.get("sources") or []] + [prin.get("url")]
            if sec.get("url") and sec["url"] not in deja: prin.setdefault("sources", []).append({"source": sec.get("source"), "url": sec["url"], "date": sec.get("date"), "titre": sec.get("titre") or sec.get("detail") or sec.get("entreprise")})
            if sec.get("emplois_min") and not prin.get("emplois_min"): prin.update(emplois_min=sec["emplois_min"], emplois_max=sec.get("emplois_max"), emplois_precision=sec.get("emplois_precision"))
            hum += d == "oui"; auto += d is None
            if d is None: cand.append({"cle": k, "score": s, "pourquoi": why, "auto": True, "a": {x: prin.get(x) for x in ("id", "entreprise", "source", "date", "emplois_min", "url", "titre", "detail", "siren", "commune")},
                                       "b": {x: sec.get(x) for x in ("id", "entreprise", "source", "date", "emplois_min", "url", "titre", "detail", "siren", "commune")}})
        elif d is None:
            cand.append({"cle": k, "score": s, "pourquoi": why, "a": {x: prin.get(x) for x in ("id", "entreprise", "source", "date", "emplois_min", "url", "titre", "detail", "siren", "commune")},
                         "b": {x: sec.get(x) for x in ("id", "entreprise", "source", "date", "emplois_min", "url", "titre", "detail", "siren", "commune")}})
    json.dump(cand, open(os.path.join(H, "doublons_candidats.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"doublons : {auto} fusionnés automatiquement (niveau A), {hum} confirmés à la main, {len(cand)} paires à vérifier (niveau B)", file=sys.stderr)
