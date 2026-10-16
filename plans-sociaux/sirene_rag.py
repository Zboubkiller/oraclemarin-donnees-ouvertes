"""Rattachement par recherche dans la base locale Sirene (sirene.db) puis choix par Gemini parmi des entreprises réelles.
Pour chaque annonce encore sans entreprise : on cherche les candidats dont le nom, le sigle, le nom d'usage ou une enseigne
correspond (index plein texte), on les classe (établissement dans la commune ou le département, taille compatible avec le
nombre de postes), et Gemini choisit parmi les 8 premiers en lisant le texte de la source, ou répond « aucun ».
Niveau de rattachement : établissement dans la commune de l'annonce -> sûr ; établissement dans le département -> probable
(confirmé à la lecture) ; sinon -> indicatif (exclu des chiffres). Cache : table rag_ident (cache.db)."""
import json, os, re, sqlite3, sys, time, unicodedata, urllib.request
import collect, commun
H = os.path.dirname(os.path.abspath(__file__))
S = sqlite3.connect(os.path.join(H, "sirene.db"), check_same_thread=False)
C = sqlite3.connect(os.path.join(H, "cache.db"), timeout=120)
C.execute("create table if not exists rag_ident(id text primary key, js text, ts real)")
VIDES = {"groupe", "group", "societe", "ste", "sa", "sas", "sasu", "sarl", "eurl", "snc", "scop", "usine", "site", "magasin", "magasins", "entreprise",
         "les", "des", "de", "du", "la", "le", "l", "d", "et", "en", "au", "aux", "france", "sur", "chez", "the", "co", "cie", "compagnie", "etablissements", "ets"}

def sa(x): return unicodedata.normalize("NFD", (x or "").lower()).encode("ascii", "ignore").decode()
def jetons(nom): return [t for t in re.findall(r"[a-z0-9]+", sa(nom)) if t not in VIDES and len(t) >= 2]

def candidats(nom, dep=None, insee=None, emplois=None, n=8, date=None):
    j = jetons(nom)
    if not j: return []
    def chercher(tok):
        try: return S.execute("select siren, siret, genre, nom from noms where noms match ? limit 400", (" ".join(f'"{t}"' for t in tok),)).fetchall()
        except sqlite3.OperationalError: return []
    hits = chercher(j[:5])
    if not hits and len(j) > 1:          # « Verrerie d'Arc » : le nom légal ne contient pas tous les mots ; on retire un mot à la fois
        for i in range(min(len(j), 5)):
            reste = [t for k, t in enumerate(j[:5]) if k != i]
            if reste and len("".join(reste)) >= 3: hits += chercher(reste)
    par = {}
    for siren, siret, genre, nm in hits:
        p = par.setdefault(siren, {"siren": siren, "noms": set(), "exact": False})
        p["noms"].add(nm)
        if " ".join(jetons(nm)) == " ".join(j): p["exact"] = True
    out = []
    for siren, p in par.items():
        u = S.execute("select nom, sigle, naf, tranche, cat, etat, date_etat, cj from ul where siren=?", (siren,)).fetchone()
        if not u: continue
        if date and u[5] == "C" and (u[6] or "9999")[:10] < date[:10] and (u[6] or "")[:7] != date[:7]: continue   # entreprise déjà cessée au moment de l'annonce
        lo, hi = collect.TR.get(u[3] or "", (None, None))
        et = S.execute("select siret, insee, dep, commune, tranche, etat, enseigne, siege from etab where siren=?", (siren,)).fetchall()
        dans_com = [x for x in et if insee and x[1] == insee]
        dans_dep = [x for x in et if dep and x[2] == dep]
        taille_ok = not (emplois and hi and emplois > max(1.5 * hi, hi + 20))
        score = (4 if p["exact"] else 1) + (4 if dans_com else 2 if dans_dep else 0) + (1 if taille_ok else -5) + min(len(et), 50) / 100
        siege = next((x for x in et if x[7]), None)
        out.append({"siren": siren, "nom": u[0], "sigle": u[1], "naf": u[2], "tranche": (lo, hi), "cat": u[4], "etat": u[5], "score": score,
                    "siret_commune": dans_com[0][0] if dans_com else None, "dans_dep": [x[3] for x in dans_dep][:4], "nb_etab": len(et),
                    "siege": siege[3] if siege else None, "enseignes": sorted({x for x in p["noms"] if x != u[0]})[:3], "taille_ok": taille_ok, "public": (u[7] or "").startswith("7")})
    out.sort(key=lambda c: -c["score"])
    return [c for c in out if c["taille_ok"]][:n]

def decrire(c):
    t = f"{c['nom']}" + (f" (sigle {c['sigle']})" if c.get("sigle") else "") + (f", enseignes : {', '.join(c['enseignes'])}" if c["enseignes"] else "")
    t += f", activité {commun.secteur(c['naf']) or c['naf']} ({c['naf']}), {c['tranche'][0]}–{c['tranche'][1]} salariés, siège à {c['siege'] or '?'}, {c['nb_etab']} établissement(s)"
    if c["dans_dep"]: t += f", dont dans le département : {', '.join(c['dans_dep'])}"
    if c["etat"] == "C": t += ", entreprise cessée"
    return t

def demander(lot, k):
    blocs = []
    for i, x in enumerate(lot):
        blocs.append(f"[{i}] TEXTE : {x['texte'][:320]}\n" + "\n".join(f"   ({j}) {decrire(c)}" for j, c in enumerate(x["cands"])))
    prompt = ("Pour chaque annonce (suppressions d'emplois, fermeture ou procédure collective en France), choisis dans la liste l'entreprise "
              "dont parle le texte. Réponds en JSON : liste d'objets {i, choix, raison}. choix = numéro du candidat, ou null si aucun ne correspond "
              "sûrement (homonyme, autre activité, autre région) ou si plusieurs sont aussi plausibles. raison : quelques mots (site cité, activité, taille). "
              "Ne choisis que si le texte le justifie.\n\n" + "\n\n".join(blocs))
    body = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"responseMimeType": "application/json", "temperature": 0}}
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-lite-latest:generateContent?key=" + k
    for essai in range(3):
        try:
            r = json.load(urllib.request.urlopen(urllib.request.Request(url, json.dumps(body).encode(), {"Content-Type": "application/json"}), timeout=150))
            return {int(x["i"]): x for x in json.loads(r["candidates"][0]["content"]["parts"][0]["text"])}
        except Exception as ex:
            print("sirene_rag :", ex, file=sys.stderr); time.sleep(5 + 10 * essai)
    return None

def completer(evs):
    """Rattache les annonces encore sans entreprise. Renvoie la liste des événements nouvellement rattachés (à enrichir)."""
    k = dict(l.strip().split("=", 1) for l in open(os.path.join(H, ".env")) if "=" in l).get("GEMINI_API_KEY")
    IA = {i: json.loads(js) for i, js in C.execute("select id, js from gemini_ident2")}
    cibles = [e for e in evs if e.get("source") != "BODACC" and not e.get("siren") and e.get("id") and not e.get("sans_entreprise")
              and not e.get("exclu_totaux") and e.get("entreprise") and e.get("entreprise") != e.get("titre") and not e.get("rattachement_retire")]
    a_faire, res = [], {}
    for e in cibles:
        r = C.execute("select js from rag_ident where id=?", (e["id"],)).fetchone()
        if r: res[e["id"]] = json.loads(r[0]); continue
        nom = (IA.get(e["id"]) or {}).get("entreprise") or e["entreprise"]
        insee = None
        if e.get("commune") and not e.get("approx"):
            try:
                import territoire; insee = territoire.insee_de(e)
            except Exception: insee = None
        cands = candidats(nom, e.get("dep"), insee, e.get("emplois_min") if e.get("emplois_precision") == "annoncé" else None, date=e.get("date"))
        if not cands:
            res[e["id"]] = None; C.execute("replace into rag_ident values(?,?,?)", (e["id"], "null", time.time())); continue
        texte = f"{e.get('entreprise')} — {e.get('titre') or e.get('detail') or ''}" + (f" (lieu : {e['commune']}, {e.get('dep')})" if e.get("commune") else (f" (département {e['dep']})" if e.get("dep") else ""))
        a_faire.append((e, {"texte": texte, "cands": cands}))
    C.commit()
    for i in range(0, len(a_faire) if k else 0, 12):
        lot = a_faire[i:i + 12]
        rep = demander([x[1] for x in lot], k)
        if rep is None: break
        for j, (e, x) in enumerate(lot):
            ch = (rep.get(j) or {}).get("choix")
            v = None
            if isinstance(ch, int) and 0 <= ch < len(x["cands"]):
                c = x["cands"][ch]
                v = {"siren": c["siren"], "siret": c["siret_commune"], "dep_ok": bool(c["dans_dep"]), "raison": (rep.get(j) or {}).get("raison"), "nom": c["nom"]}
            res[e["id"]] = v; C.execute("replace into rag_ident values(?,?,?)", (e["id"], json.dumps(v, ensure_ascii=False), time.time()))
        C.commit(); time.sleep(3)
    nouveaux, n = [], {"sur": 0, "probable": 0, "indicatif": 0}
    for e in cibles:
        v = res.get(e["id"])
        if not v: continue
        e["siren"] = v["siren"]; e["siren_rapproche"] = True; e["ident_base"] = v.get("raison") or True
        if v.get("siret"): e["lien"] = "siret_commune"; e["siret"] = v["siret"]; n["sur"] += 1
        elif v.get("dep_ok"): e["lien"] = "nom+dep"; e["verif_ident"] = "confirmé"; n["probable"] += 1
        else: e["lien"] = "nom_seul"; n["indicatif"] += 1
        nouveaux.append(e)
    print(f"sirene_rag : {len(cibles)} annonces sans entreprise, {len(nouveaux)} rattachées ({n['sur']} sûres, {n['probable']} probables confirmées, {n['indicatif']} indicatives)", file=sys.stderr)
    return nouveaux
