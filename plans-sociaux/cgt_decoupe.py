"""Découpage des lignes de la liste noire CGT qui décrivent plusieurs plans (sites, départements, sociétés) en composantes :
{emplois, extrait, departements, lieux, societe}. Gemini lit le texte ; chaque composante doit être vérifiable : l'extrait cité figure
dans la ligne et le nombre d'emplois figure dans l'extrait, sinon elle est rejetée. La somme des composantes est comparée au total
retenu (e["composantes_somme_ok"]). Les composantes ne remplacent rien : elles aident l'identification (onglet Identifier) et
répartissent les emplois entre les sociétés choisies. Cache : table cgt_decoupe (par texte)."""
import hashlib, json, os, re, sqlite3, sys, time, unicodedata, urllib.request
H = os.path.dirname(os.path.abspath(__file__))
db = sqlite3.connect(os.path.join(H, "cache.db"), timeout=120)
db.execute("create table if not exists cgt_decoupe(h text primary key, js text, ts real)")
norm = lambda x: re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFD", (x or "").lower()).encode("ascii", "ignore").decode())

def nombres(t):
    t = re.sub(r"\(\d{2}\.\d{2}\)", " ", t or "")                       # dates de la liste : (10.24)
    t = re.sub(r"\b(?:19|20)\d\d\b", " ", t)                           # années
    return [int(re.sub(r"\D", "", m)) for m in re.findall(r"\d[\d  ]*", t) if re.sub(r"\D", "", m) and int(re.sub(r"\D", "", m)) >= 10]

def candidat(e):
    t = e.get("detail") or ""
    return str(e.get("source", "")).startswith("CGT") and len(set(nombres(t))) >= 2

def demander(lot, k):
    prompt = ("Chaque ligne ci-dessous vient de la liste noire des plans de licenciement de la CGT. Certaines décrivent PLUSIEURS plans : plusieurs sites, "
              "départements, sociétés ou dates, chacun avec son nombre d'emplois. Pour chaque ligne, réponds en JSON : liste d'objets {i, composantes}. "
              "composantes : liste de {emplois (entier), extrait (fragment EXACT copié dans la ligne qui contient ce nombre), departements (codes à 2 chiffres, "
              "vide si non cités ; déduis-les des noms de départements cités), lieux (communes ou sites cités), societe (nom de la société si elle est nommée, sinon null)}. "
              "Ne découpe que si la ligne décrit au moins deux plans ou sites avec chacun son nombre d'emplois ; sinon composantes = []. "
              "N'invente aucun chiffre : « en plus de ceux listés ci-dessous » ou un total global ne sont pas des composantes.\n\n"
              + "\n".join(f"[{i}] {x.get('entreprise')} — {x['detail'][:700]}" for i, x in enumerate(lot)))
    body = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"responseMimeType": "application/json", "temperature": 0}}
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-lite-latest:generateContent?key=" + k
    for essai in range(3):
        try:
            r = json.load(urllib.request.urlopen(urllib.request.Request(url, json.dumps(body).encode(), {"Content-Type": "application/json"}), timeout=180))
            u = r.get("usageMetadata", {})
            with open(os.path.join(H, "gemini_usage.log"), "a") as f:
                f.write(f"{time.strftime('%Y-%m-%dT%H:%M')} cgt_decoupe={len(lot)} in={u.get('promptTokenCount')} out={u.get('candidatesTokenCount')}\n")
            return {int(x["i"]): x.get("composantes") or [] for x in json.loads(r["candidates"][0]["content"]["parts"][0]["text"])}
        except Exception as ex:
            print("cgt_decoupe :", ex, file=sys.stderr); time.sleep(5 + 10 * essai)
    return None

def valider(comps, texte):
    out = []
    for c in comps if isinstance(comps, list) else []:
        try: n = int(c.get("emplois"))
        except (TypeError, ValueError): continue
        ex = str(c.get("extrait") or "")
        if len(ex) < 8 or norm(ex) not in norm(texte) or str(n) not in re.sub(r"[\s  ]", "", ex): continue
        deps = [str(d).zfill(2) for d in (c.get("departements") or []) if re.fullmatch(r"\d{1,3}|2[AB]", str(d))]
        out.append({"emplois": n, "extrait": ex, "departements": deps, "lieux": [str(x) for x in (c.get("lieux") or [])][:6], "societe": c.get("societe") or None})
    return out if len(out) >= 2 else []

def enrichir(evs):
    from gemini_ident import cle
    k = cle(); C = [e for e in evs if candidat(e)]
    a_faire = []
    for e in C:
        h = hashlib.sha1((e.get("detail") or "").encode()).hexdigest()
        r = db.execute("select js from cgt_decoupe where h=?", (h,)).fetchone()
        if r: e["composantes"] = json.loads(r[0])
        else: a_faire.append((h, e))
    for i in range(0, len(a_faire) if k else 0, 20):
        lot = a_faire[i:i + 20]
        rep = demander([e for _, e in lot], k)
        if rep is None: break
        for j, (h, e) in enumerate(lot):
            comps = valider(rep.get(j), e.get("detail") or "")
            db.execute("replace into cgt_decoupe values(?,?,?)", (h, json.dumps(comps, ensure_ascii=False), time.time())); e["composantes"] = comps
        db.commit(); time.sleep(3)
    n = 0
    for e in C:
        c = e.get("composantes") or []
        if not c: e.pop("composantes", None); continue
        n += 1; e["composantes_somme_ok"] = sum(x["emplois"] for x in c) == (e.get("emplois_min") or -1)
    print(f"découpage CGT : {len(C)} lignes à plusieurs nombres, {n} découpées en composantes", file=sys.stderr)

if __name__ == "__main__":
    import collect
    evs = collect.cgt(); enrichir(evs)
    for e in evs:
        if e.get("composantes"):
            print(e["entreprise"], e.get("emplois_min"), "| somme ok:", e["composantes_somme_ok"])
            for c in e["composantes"]: print("    ", c["emplois"], c["departements"], c["lieux"], c["societe"], "|", c["extrait"][:70])
