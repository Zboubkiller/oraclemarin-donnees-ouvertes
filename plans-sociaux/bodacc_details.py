"""Détails des jugements BODACC : administrateur judiciaire, mandataire judiciaire ou liquidateur, date de cessation des
paiements (texte « complementJugement » de l'annonce), et repreneur dans les jugements arrêtant un plan de cession.
Extraction par expressions régulières sur le texte officiel ; le texte brut est gardé pour vérification."""
import json, re, sqlite3, sys, time, urllib.parse, os
import collect
H = os.path.dirname(os.path.abspath(__file__))
db = sqlite3.connect(os.path.join(H, "cache.db"), timeout=120)
db.execute("create table if not exists bodacc_det(id text primary key, js text)")
MOIS = {m: i + 1 for i, m in enumerate(["janvier", "fevrier", "mars", "avril", "mai", "juin", "juillet", "aout", "septembre", "octobre", "novembre", "decembre"])}
ROLES = [("administrateur", r"administrateurs?(?: judiciaires?)?"), ("mandataire", r"mandataires? judiciaires?"),
         ("liquidateur", r"liquidateurs?(?: judiciaires?)?"), ("commissaire", r"commissaires? (?:à|a) l.ex[ée]cution du plan")]
FIN = r"(?:Les d[ée]clarations|Les cr[ée]ances|et d[ée]signant|ayant pour|en remplacement|$)"

def sans_accent(s):
    import unicodedata
    return unicodedata.normalize("NFD", s or "").encode("ascii", "ignore").decode().lower()

def date_cp(t):
    m = re.search(r"cessation des paiements(?: fix[ée]e)?(?: le| au)?\s*:?\s*(\d{1,2})(?:er)?\s+([a-zéû]+)\s+(\d{4})", t, re.I)
    if m and sans_accent(m[2]) in MOIS: return f"{m[3]}-{MOIS[sans_accent(m[2])]:02d}-{int(m[1]):02d}"
    m = re.search(r"cessation des paiements[^0-9]{0,15}(\d{2})/(\d{2})/(\d{4})", t, re.I)
    return f"{m[3]}-{m[2]}-{m[1]}" if m else None

def personnes(seg):
    """« SELARL X (Me Prénom Nom) » : études et noms des mandataires dans un segment de texte."""
    etudes = [re.sub(r"\s+", " ", x).strip(" ,") for x in re.findall(
        r"\b((?:(?i:SELARL|SELAS|SELASU|SELAFA|SCP|SAS|SARL)\b(?:\s+d.administrateurs judiciaires)?|(?:AJRS|AJ UP|AJ Partenaires|AJ Associ[ée]s|BTSG|MJA)\b)[^,;:(]{0,60}?)(?=\s+(?:mission|en la personne|prise en|repr[ée]sent|prise|ayant|agissant|demeurant|sise|\d)|,|;|$)", seg)]
    noms = [re.sub(r"\s+", " ", x).strip() for x in re.findall(r"\b(?:Me|[Mm]a[iî]tre)\s+((?:[A-ZÉÈÀÂÎÔ][\w'’-]+|de|d'|du|le|la)(?:\s+(?:[A-ZÉÈÀÂÎÔ][\w'’-]+|de|d'|du|le|la)){0,4})", seg)]
    noms = [re.sub(r"\s+(?:de|d'|du|le|la)$", "", n) for n in noms]
    out = []
    for x in etudes + ["Me " + n for n in noms]:
        if x and x not in out and len(x) < 90 and not re.fullmatch(r"(?i)(?:SELARL|SELAS|SELASU|SELAFA|SCP|SAS|SARL)", x): out.append(x)
    return out[:4]

def acteurs(t):
    if not t: return {}
    pos = sorted((m.start(), m.end(), r) for r, rx in ROLES for m in re.finditer(r"\b" + rx + r"\b", t, re.I))
    res = {}
    for i, (a, b, r) in enumerate(pos):
        fin = pos[i + 1][0] if i + 1 < len(pos) else len(t)
        seg = re.split(FIN, t[b:fin], maxsplit=1)[0]
        p = personnes(seg)
        if p and r not in res: res[r] = p
    return res

def repreneur(t):
    m = re.search(r"au profit (?:de |d['’])\s*(?:la soci[ée]t[ée] |la SAS |la SARL |la SA |l['’]entreprise |M\. |Mme |Monsieur |Madame )?(.{3,90}?)(?=,| avec | moyennant| pour un | pour le prix| \(| ayant| sise| dont| RCS| immatricul|\.\s|$)", t or "", re.I)
    return m[1].strip(" ,.") if m else None

def details(ids):
    """{id: {...}} : cache, puis API BODACC par lots de 40 identifiants."""
    out, manq = {}, []
    for i in ids:
        r = db.execute("select js from bodacc_det where id=?", (i,)).fetchone()
        if r: out[i] = json.loads(r[0])
        else: manq.append(i)
    for k in range(0, len(manq), 40):
        lot = manq[k:k + 40]
        w = "id in (" + ",".join(f'"{x}"' for x in lot) + ")"
        d = collect.get(collect.BODACC + "?" + urllib.parse.urlencode({"select": "id,jugement", "where": w, "limit": 100}))
        if d is None: break
        vus = set()
        for x in d.get("results", []):
            j = json.loads(x.get("jugement") or "{}"); t = j.get("complementJugement") or ""
            v = {"texte": t[:1500], "cessation_paiements": date_cp(t), "acteurs": acteurs(t)}
            db.execute("replace into bodacc_det values(?,?)", (x["id"], json.dumps(v, ensure_ascii=False))); out[x["id"]] = v; vus.add(x["id"])
        for x in set(lot) - vus:
            db.execute("replace into bodacc_det values(?,?)", (x, json.dumps({}, ensure_ascii=False)))
        db.commit(); time.sleep(0.3)
    return out

def enrichir(evs):
    b = [e for e in evs if e.get("source") == "BODACC" and str(e.get("id", "")).startswith("bodacc-")]
    det = details([e["id"][7:] for e in b])
    n = 0
    for e in b:
        v = det.get(e["id"][7:]) or {}
        if v.get("acteurs"): e["acteurs"] = v["acteurs"]; n += 1
        if v.get("cessation_paiements"): e["cessation_paiements"] = v["cessation_paiements"]
        if v.get("texte"): e["jugement_texte"] = v["texte"]
    print(f"BODACC détails : {n}/{len(b)} procédures avec administrateur ou mandataire identifiés", file=sys.stderr)
