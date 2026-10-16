"""Vérification des rattachements par le nom (« probable » : nom + établissement dans le département ; « indicatif » : nom seul).
1. Cohérence de taille : une entreprise ne peut pas supprimer nettement plus de postes que son effectif total -> rejet.
2. Relecture : Gemini compare le texte de la source à la fiche du registre de l'entreprise proposée (nom légal, activité, commune
   du siège, taille) et répond même entreprise / autre entreprise / impossible à dire. Il ne propose jamais de SIREN.
Conséquences : « autre entreprise » ou taille incohérente -> rattachement retiré ; « même entreprise » -> rattachement confirmé
(compte comme fiable) ; sinon -> reste probable ou indicatif mais n'entre pas dans les chiffres (bénéfices, aides).
Cache : table verif_ident (clé : identifiant de l'événement + SIREN)."""
import json, os, sqlite3, sys, time, urllib.request, urllib.parse
import aides, collect, commun
H = os.path.dirname(os.path.abspath(__file__))
db = sqlite3.connect(os.path.join(H, "cache.db"), timeout=120)
db.execute("create table if not exists verif_ident(k text primary key, js text, ts real)")
db.execute("create table if not exists ident_siege(siren text primary key, js text, ts real)")
CHAMPS_SIREN = ("siren", "lien", "siren_rapproche", "siret", "comptes", "argent_public", "proximite", "ratios", "dependance_publique",
                "fiable", "naf", "categorie", "groupe", "lobbying", "lobbying_groupe", "sanction_delais", "bonne_boite", "verif_urssaf", "accords", "ident_ia")

def siege(siren):
    """Nom légal, activité, commune du siège, tranche d'effectif (API Recherche d'entreprises, cache 30 jours)."""
    r = db.execute("select js, ts from ident_siege where siren=?", (siren,)).fetchone()
    if r and time.time() - r[1] < 30 * 86400: return json.loads(r[0])
    d = collect.get(collect.RE_API + "?" + urllib.parse.urlencode({"q": siren, "per_page": 1}))
    if d is None: return None
    e = (d.get("results") or [{}])[0]
    s = e.get("siege") or {}
    out = {"nom": e.get("nom_complet"), "naf": e.get("activite_principale"), "tranche": e.get("tranche_effectif_salarie"),
           "commune": s.get("libelle_commune"), "dep": s.get("departement"), "etablissements": e.get("nombre_etablissements_ouverts")} if e.get("siren") == siren else {}
    db.execute("replace into ident_siege values(?,?,?)", (siren, json.dumps(out, ensure_ascii=False), time.time())); db.commit(); time.sleep(0.15)
    return out

def demander(lot, k):
    prompt = ("Pour chaque ligne ci-dessous : un texte (annonce de suppressions d'emplois, de fermeture ou de procédure) et une entreprise du registre "
              "des entreprises proposée pour ce texte. Réponds en JSON : liste d'objets {i, meme}. meme = true si le texte parle bien de cette entreprise "
              "(ou d'un de ses sites), false si c'est manifestement une autre entreprise (homonyme, activité sans rapport, autre pays), null si impossible à dire. "
              "Sois strict : un simple nom commun ne suffit pas.\n\n"
              + "\n".join(f"[{j}] TEXTE : {x['texte'][:300]} || ENTREPRISE PROPOSÉE : {x['cand']}" for j, x in enumerate(lot)))
    body = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"responseMimeType": "application/json", "temperature": 0}}
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-lite-latest:generateContent?key=" + k
    for essai in range(3):
        try:
            r = json.load(urllib.request.urlopen(urllib.request.Request(url, json.dumps(body).encode(), {"Content-Type": "application/json"}), timeout=120))
            return {int(x["i"]): x.get("meme") for x in json.loads(r["candidates"][0]["content"]["parts"][0]["text"])}
        except Exception as ex:
            print("verif_ident :", ex, file=sys.stderr); time.sleep(5 + 10 * essai)
    return None

def retirer(e, motif):
    e["rattachement_retire"] = {"siren": e.get("siren"), "motif": motif}
    for c in CHAMPS_SIREN: e.pop(c, None)

def verifier(evs):
    cibles = [e for e in evs if e.get("source") != "BODACC" and e.get("siren") and e.get("lien") in ("nom+dep", "nom_seul")]
    k = dict(l.strip().split("=", 1) for l in open(os.path.join(H, ".env")) if "=" in l).get("GEMINI_API_KEY")
    a_demander, n_inc = [], 0
    for e in cibles:
        s = siege(e["siren"]) or {}
        lo, hi = collect.TR.get(s.get("tranche") or "", (None, None))
        if e.get("emplois_precision") == "annoncé" and hi and (e.get("emplois_min") or 0) > max(1.5 * hi, hi + 20):
            retirer(e, f"taille incohérente : {e['emplois_min']} postes annoncés pour une entreprise de {lo} à {hi} salariés"); n_inc += 1; continue
        cle = f"{e.get('id')}|{e['siren']}"
        r = db.execute("select js from verif_ident where k=?", (cle,)).fetchone()
        if r: e["_v"] = json.loads(r[0]); continue
        cand = (f"{s.get('nom') or e['entreprise']}, activité {commun.secteur(s.get('naf')) or s.get('naf') or '?'} ({s.get('naf') or '?'}), siège à {s.get('commune') or '?'} "
                f"({s.get('dep') or '?'}), {s.get('etablissements') or '?'} établissement(s), effectif {lo if lo is not None else '?'}–{hi if hi is not None else '?'} salariés")
        texte = f"{e.get('entreprise')} — {(e.get('titre') or e.get('detail') or '')}" + (f" (lieu cité : {e['commune']})" if e.get("commune") and not e.get("approx") else "")
        a_demander.append((e, cle, {"texte": texte, "cand": cand}))
    for i in range(0, len(a_demander) if k else 0, 25):
        lot = a_demander[i:i + 25]
        rep = demander([x[2] for x in lot], k)
        if rep is None: break
        for j, (e, cle, _) in enumerate(lot):
            v = rep.get(j)
            db.execute("replace into verif_ident values(?,?,?)", (cle, json.dumps(v), time.time())); e["_v"] = v
        db.commit(); time.sleep(3)
    n = {"confirme": 0, "rejete": 0, "incertain": 0}
    for e in cibles:
        if "_v" not in e: continue
        v = e.pop("_v")
        if v is False: retirer(e, "relecture : autre entreprise que celle du texte"); n["rejete"] += 1
        elif v is True and e.get("lien") == "nom_seul" and not ((siege(e["siren"]) or {}).get("dep") and (siege(e["siren"]) or {}).get("dep") == e.get("dep")):
            n["incertain"] += 1; e["fiable"] = False; e["verif_ident"] = "nom seul, sans indice géographique"   # la relecture seule ne suffit pas
        elif v is True:
            e["verif_ident"] = "confirmé"; n["confirme"] += 1
            if e.get("lien") == "nom_seul": e["lien"] = "nom+dep"          # siège dans le département de l'annonce et relecture : niveau « probable »
            c = e.get("comptes") or {}
            da, ya = c.get("derniere_annee"), int((e.get("date") or "0")[:4] or 0)
            e["fiable"] = bool(da and ya and 0 <= ya - int(da) <= 2)
        else:
            n["incertain"] += 1; e["fiable"] = False                        # non confirmé : pas dans les chiffres
    for e in cibles:
        if e.get("lien") == "nom+dep" and e.get("verif_ident") != "confirmé": e["fiable"] = False
    print(f"verif_ident : {len(cibles)} rattachements par le nom ; {n_inc} retirés (taille incohérente), {n['rejete']} retirés à la relecture, "
          f"{n['confirme']} confirmés, {n['incertain']} incertains", file=sys.stderr)
