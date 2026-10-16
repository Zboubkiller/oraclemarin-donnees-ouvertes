"""Opérations publiées au BODACC (« ventes et cessions ») pour les entreprises suivies : achats et ventes de fonds de commerce ou de
branches d'activité, apports, fusions, avec la contrepartie et le montant quand l'annonce l'indique. Les cessions d'actions (rachat
d'une société par un fonds, LBO) ne sont pas publiées au BODACC : elles n'apparaissent pas ici.
Cache : table bodacc_ops (rafraîchie tous les 30 jours)."""
import json, os, re, sqlite3, sys, time, urllib.parse
import collect
H = os.path.dirname(os.path.abspath(__file__))
db = sqlite3.connect(os.path.join(H, "cache.db"), timeout=120)
db.execute("create table if not exists bodacc_ops(siren text primary key, js text, ts real)")

def montant(t):
    m = re.search(r"(?:prix|montant|moyennant(?: le prix de)?|pour la somme de)\s*(?:de|global de|principal de|:)?\s*([\d][\d\s.  ]*(?:,\d+)?)\s*(?:€|euros?|EUR)", t or "", re.I)
    if not m: return None
    v = re.sub(r"[\s.  ]", "", m.group(1)).replace(",", ".")
    try:
        x = float(v)
        return x if 100 <= x <= 5e10 else None
    except ValueError:
        return None

def nature(cat, t):
    c, t = (cat or "").lower(), (t or "").lower()
    if "fusion" in t or "absorb" in t: return "fusion"
    if "apport" in t and "fonds" not in c: return "apport"
    if "location-gérance" in c or "location-gérance" in t: return "location-gérance"
    if "branche" in t: return "achat ou vente d'une branche d'activité"
    if "fonds" in c or "fonds" in t: return "achat ou vente d'un fonds de commerce"
    return "autre opération"

def lire(siren):
    r = db.execute("select js, ts from bodacc_ops where siren=?", (siren,)).fetchone()
    if r and time.time() - r[1] < 30 * 86400: return json.loads(r[0])
    sp = f"{siren[:3]} {siren[3:6]} {siren[6:]}"
    d = collect.get(collect.BODACC + "?" + urllib.parse.urlencode({"where": f'familleavis="vente" and registre like "*{sp}*"', "limit": 30,
                    "order_by": "dateparution desc", "select": "id,dateparution,commercant,registre,acte,listeprecedentproprietaire,listeprecedentexploitant,url_complete"}))
    if d is None: return None
    ops = []
    for x in d.get("results", []):
        try: a = json.loads(x.get("acte") or "{}")
        except ValueError: a = {}
        if not isinstance(a, dict): a = {}
        v = a.get("vente") or {}
        if not isinstance(v, dict): v = {"categorieVente": str(v)}
        prec = (x.get("listeprecedentproprietaire") or "") + (x.get("listeprecedentexploitant") or "")
        vendeur = sp in prec or siren in prec
        t = str(a.get("descriptif") or "")
        contre = None
        if vendeur: contre = (x.get("commercant") or "").split(",")[0].strip() or None
        else:
            m = re.search(r'"denomination":\s*"([^"]+)"', prec); contre = m.group(1) if m else None
        ops.append({"date": x["dateparution"], "role": "vendeur" if vendeur else "acheteur ou bénéficiaire", "nature": nature(v.get("categorieVente"), t),
                    "contrepartie": contre, "montant": montant(t), "extrait": re.sub(r"\s+", " ", t)[:300], "url": x.get("url_complete")})
    db.execute("replace into bodacc_ops values(?,?,?)", (siren, json.dumps(ops, ensure_ascii=False), time.time())); db.commit()
    time.sleep(0.15)
    return ops

def par_siren():
    return {s: json.loads(js) for s, js in db.execute("select siren, js from bodacc_ops")}

def enrichir(evs, limite=400):
    LIEN = ("siren_source", "siret_commune", "nom+dep")
    sirens = sorted({e["siren"] for e in evs if e.get("siren") and (e.get("source") == "BODACC" or e.get("lien") in LIEN)})
    n = nouveaux = 0
    for s in sirens:
        neuf = not db.execute("select 1 from bodacc_ops where siren=?", (s,)).fetchone()
        if neuf and nouveaux >= limite: continue
        ops = lire(s)
        if neuf: nouveaux += 1
        if ops: n += 1
    print(f"opérations BODACC : {n} entreprises avec au moins une opération ({nouveaux} interrogées)", file=sys.stderr)
