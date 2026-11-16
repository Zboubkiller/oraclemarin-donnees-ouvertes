"""La Bonne Boîte (France Travail, API v2) : l'établissement qui annonce un plan figure-t-il parmi les établissements que
France Travail juge à fort potentiel d'embauche ? Recherche par code NAF de l'entreprise et par commune de l'établissement, puis
comparaison du SIRET. Seulement pour les annonces dont l'établissement exact est connu (rapprochement « siret_commune »).
Écrit e["bonne_boite"] = {potentiel, fort, effectif}. Identifiants dans .env (FT_CLIENT_ID, FT_CLIENT_SECRET)."""
import json, os, sqlite3, sys, time, urllib.parse, urllib.request
H = os.path.dirname(os.path.abspath(__file__))
db = sqlite3.connect(os.path.join(H, "cache.db"), timeout=120)
db.execute("create table if not exists bonneboite(cle text primary key, js text, ts real)")
API = "https://api.francetravail.io/partenaire/labonneboite/v2/recherche?"

def jeton():
    env = dict(l.strip().split("=", 1) for l in open(os.path.join(H, ".env")) if "=" in l)
    p = {"grant_type": "client_credentials", "client_id": env["FT_CLIENT_ID"], "client_secret": env["FT_CLIENT_SECRET"], "scope": "api_labonneboitev2 search office"}
    r = urllib.request.urlopen(urllib.request.Request("https://entreprise.francetravail.fr/connexion/oauth2/access_token?realm=%2Fpartenaire",
                               urllib.parse.urlencode(p).encode(), {"Content-Type": "application/x-www-form-urlencoded"}), timeout=30)
    return json.load(r)["access_token"]

def chercher(t, naf, insee):
    cle = f"{naf}|{insee}"
    r = db.execute("select js, ts from bonneboite where cle=?", (cle,)).fetchone()
    if r and time.time() - r[1] < 7 * 86400: return json.loads(r[0])
    items = []
    for page in (1, 2, 3):
        q = {"naf": naf, "citycode": insee, "distance": 1, "page": page, "page_size": 100}
        for essai in range(3):
            try:
                rr = urllib.request.urlopen(urllib.request.Request(API + urllib.parse.urlencode(q), headers={"Authorization": "Bearer " + t, "Accept": "application/json"}), timeout=30)
                d = json.load(rr); break
            except urllib.error.HTTPError as e:
                if e.code == 429: time.sleep(2 + 2 * essai); continue
                d = None; break
            except Exception:
                d = None; time.sleep(2)
        else:
            d = None
        if d is None: return None
        items += [{"siret": x.get("siret"), "potentiel": x.get("hiring_potential"), "fort": x.get("is_high_potential"),
                   "effectif": [x.get("headcount_min"), x.get("headcount_max")]} for x in d.get("items", [])]
        time.sleep(0.6)                                     # 2 appels par seconde autorisés
        if len(d.get("items", [])) < 100: break
    db.execute("replace into bonneboite values(?,?,?)", (cle, json.dumps(items), time.time())); db.commit()
    return items

def enrichir(evs):
    cibles = [e for e in evs if e.get("siret") and e.get("naf") and e.get("lien") == "siret_commune"]
    if not cibles: return evs
    try: t = jeton()
    except Exception as ex:
        print("bonne boîte : authentification impossible :", ex, file=sys.stderr); return evs
    n = 0
    try:
        import territoire
    except Exception:
        territoire = None
    for e in cibles:
        insee = e.get("insee") or (territoire.insee_de(e) if territoire else None)
        if not insee: continue
        items = chercher(t, e["naf"].replace(".", ""), insee)
        if not items: continue
        x = next((i for i in items if i["siret"] == e["siret"]), None)
        if x:
            e["bonne_boite"] = {"potentiel": round(x["potentiel"] or 0, 1), "fort": bool(x["fort"]), "effectif": x["effectif"]}; n += 1
    print("bonne boîte :", n, "établissements trouvés sur", len(cibles), file=sys.stderr)
    return evs
