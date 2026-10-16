"""Aide à l'identification des entreprises citées sans SIREN (liste CGT, presse) : Gemini lit le texte de la source et en
extrait le nom de la société, la commune et le département du site concerné, ou indique qu'aucune entreprise n'est en cause
(article de contexte, administration). Il ne choisit JAMAIS un SIREN : ses réponses repassent par le rapprochement strict
d'aides.identifier (établissement dans la commune, nom identique ou contenu, sigles exclus). Résultats en cache par événement."""
import json, os, re, sqlite3, sys, time, urllib.request
H = os.path.dirname(os.path.abspath(__file__))
db = sqlite3.connect(os.path.join(H, "cache.db"), timeout=120)
db.execute("create table if not exists gemini_ident2(id text primary key, js text, ts real)")
db.execute("create table if not exists gemini_presse(id text primary key, js text, ts real)")
MODELE = "gemini-flash-lite-latest"

def cle():
    env = dict(l.strip().split("=", 1) for l in open(os.path.join(H, ".env")) if "=" in l)
    return env.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY")

def demander(lots, k):
    prompt = ("Pour chaque ligne ci-dessous (une annonce de suppression d'emplois, fermeture ou procédure collective, en principe en France mais pas toujours), réponds en JSON : "
              "une liste d'objets {i, entreprise : nom de la société concernée tel qu'écrit dans le texte (sans « usine », « site », « groupe » si ce n'est pas "
              "dans son nom), commune : commune du site concerné si elle est écrite, departement : numéro ou nom du département s'il est écrit, "
              "est_entreprise : false si le texte ne concerne pas une entreprise précise (administration, secteur entier, article de contexte), "
              "en_france : false si les emplois ou le site concernés sont hors de France (usine allemande, plan mondial sans site français cité), null si on ne sait pas}. "
              "N'invente rien : null si l'information n'est pas dans le texte.\n\n"
              + "\n".join(f"[{i}] {x['nom']} — {x['texte'][:350]}" for i, x in enumerate(lots)))
    body = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"responseMimeType": "application/json", "temperature": 0}}
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODELE}:generateContent?key=" + k
    for essai in range(3):
        try:
            r = json.load(urllib.request.urlopen(urllib.request.Request(url, json.dumps(body).encode(), {"Content-Type": "application/json"}), timeout=120))
            u = r.get("usageMetadata", {})
            with open(os.path.join(H, "gemini_usage.log"), "a") as f:
                f.write(f"{time.strftime('%Y-%m-%dT%H:%M')} ident={len(lots)} in={u.get('promptTokenCount')} out={u.get('candidatesTokenCount')}\n")
            return {int(x["i"]): x for x in json.loads(r["candidates"][0]["content"]["parts"][0]["text"])}
        except Exception as ex:
            print("gemini_ident :", ex, file=sys.stderr); time.sleep(5 + 10 * essai)
    return None

def extraire(evs):
    """{id: {entreprise, commune, departement, est_entreprise}} pour les événements sans SIREN (cache, puis Gemini par lots de 30)."""
    k = cle()
    cibles = [e for e in evs if e.get("source") != "BODACC" and not e.get("siren") and e.get("id")]
    out, a_faire = {}, []
    for e in cibles:
        r = db.execute("select js from gemini_ident2 where id=?", (e["id"],)).fetchone()
        if r: out[e["id"]] = json.loads(r[0])
        else: a_faire.append(e)
    if a_faire and k:
        for i in range(0, len(a_faire), 30):
            lot = a_faire[i:i + 30]
            rep = demander([{"nom": e.get("entreprise") or "", "texte": (e.get("detail") or "") + " " + (e.get("titre") or "")} for e in lot], k)
            if rep is None: break
            for j, e in enumerate(lot):
                x = rep.get(j) or {}
                v = {"entreprise": x.get("entreprise"), "commune": x.get("commune"), "departement": x.get("departement"), "est_entreprise": x.get("est_entreprise", True), "en_france": x.get("en_france")}
                db.execute("replace into gemini_ident2 values(?,?,?)", (e["id"], json.dumps(v, ensure_ascii=False), time.time())); out[e["id"]] = v
            db.commit(); time.sleep(4)
    print("gemini_ident :", len(out), "lignes relues,", len(a_faire), "nouvelles", file=sys.stderr)
    return out


def verifier_presse(arts):
    """{id: {en_france, collectif}} pour chaque article de presse (cache, puis Gemini par lots de 40). Sert à retirer les articles
    sur des emplois hors de France et ceux qui ne parlent pas de suppressions collectives (licenciement individuel, grève salariale)."""
    k = cle(); out, a_faire = {}, []
    for e in arts:
        r = db.execute("select js from gemini_presse where id=?", (e["id"],)).fetchone()
        if r: out[e["id"]] = json.loads(r[0])
        else: a_faire.append(e)
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODELE}:generateContent?key=" + (k or "")
    for i in range(0, len(a_faire) if k else 0, 40):
        lot = a_faire[i:i + 40]
        prompt = ("Pour chaque article de presse ci-dessous (média, titre), réponds en JSON : liste d'objets {i, en_france, collectif}. "
                  "en_france : false si les emplois ou le site concernés sont hors de France (Suisse, Belgique, Luxembourg, Canada, Afrique, Allemagne...), "
                  "true s'ils sont en France (y compris outre-mer), null si on ne peut pas savoir. "
                  "collectif : true si l'article porte sur des suppressions d'emplois collectives, une fermeture de site, un plan social, des départs volontaires "
                  "ou une procédure collective (redressement, liquidation, sauvegarde) d'une entreprise ou d'un employeur ; false pour un licenciement individuel, "
                  "une grève ou un conflit sans suppression de postes, ou un article de contexte général.\n\n"
                  + "\n".join(f"[{j}] ({x.get('source') or ''}) {x.get('titre') or x.get('detail') or ''}"[:330] for j, x in enumerate(lot)))
        body = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"responseMimeType": "application/json", "temperature": 0}}
        rep = None
        for essai in range(3):
            try:
                r = json.load(urllib.request.urlopen(urllib.request.Request(url, json.dumps(body).encode(), {"Content-Type": "application/json"}), timeout=120))
                rep = {int(x["i"]): x for x in json.loads(r["candidates"][0]["content"]["parts"][0]["text"])}; break
            except Exception as ex:
                print("verifier_presse :", ex, file=sys.stderr); time.sleep(5 + 10 * essai)
        if rep is None: break
        for j, e in enumerate(lot):
            x = rep.get(j) or {}
            v = {"en_france": x.get("en_france"), "collectif": x.get("collectif", True)}
            db.execute("replace into gemini_presse values(?,?,?)", (e["id"], json.dumps(v), time.time())); out[e["id"]] = v
        db.commit(); time.sleep(3)
    print(f"verifier_presse : {len(out)} articles, {len(a_faire)} nouveaux", file=sys.stderr)
    return out
