"""Déconstruction du PDF « Liste noire des plans de licenciement » de la CGT : chaque puce du PDF devient une ligne {page, secteur, sous-rubrique, texte},
rattachée à la ligne correspondante du fichier d'extraction (/opt/ca-brule/licenciements.json, id « cgt-N »). Permet de renvoyer vers la PAGE du PDF
(#page=N) et de construire la page « Liste noire CGT » du site. Le PDF n'est pas republié : on garde un lien vers l'original sur cgt.fr.
Sortie : cgt/index.json. Usage : cgt_pdf.py (téléchargement du PDF si absent, puis analyse)"""
import hashlib, json, os, re, subprocess, sys, unicodedata, urllib.request
H = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(H, "cgt"); os.makedirs(D, exist_ok=True)
SRC = "/opt/ca-brule/licenciements.json"
norm = lambda x: re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFD", (x or "").lower().replace("’", "'")).encode("ascii", "ignore").decode())

def items():
    d = json.load(open(SRC)); return d if isinstance(d, list) else next(v for v in d.values() if isinstance(v, list))

def telecharger(url):
    p = os.path.join(D, "liste_noire.pdf")
    if not os.path.exists(p) or os.path.getmtime(p) < __import__("time").time() - 86400:
        req = urllib.request.Request(url, headers={"User-Agent": "plans-sociaux (quentinclosset@gmail.com)"})
        open(p, "wb").write(urllib.request.urlopen(req, timeout=90).read())
    return p

def puces(pdf):
    txt = subprocess.run(["pdftotext", "-layout", pdf, "-"], capture_output=True, text=True, check=True).stdout
    sect, sous, out, cur = "", "", [], None
    for page, ptxt in enumerate(txt.split("\f"), 1):
        L = ptxt.split("\n"); haut = []
        for l in L:
            s = l.strip()
            if not s or re.fullmatch(r"\d{1,2}", s): cur = cur if not s else cur; continue
            if s.startswith("•"):
                if haut: sect = " ".join(haut); haut = []; sous = ""
                if cur: out.append(cur)
                cur = {"page": page, "secteur": sect, "sous": sous, "texte": s.lstrip("• ").strip()}
            elif s.isupper() and len(s) > 4 and not re.search(r"\d|\[", s):          # titre de secteur (peut tenir sur plusieurs lignes)
                if cur: out.append(cur); cur = None
                haut.append(s)
            elif cur and (len(l) - len(l.lstrip())) >= 4 and not s.isupper():           # suite d'une puce sur la ligne suivante
                cur["texte"] += " " + s
            else:                                                                        # texte d'introduction ou sous-titre
                if cur: out.append(cur); cur = None
                if haut: sect = " ".join(haut); haut = []; sous = ""
                if len(s) < 70 and not s.endswith(".") and not s.endswith(",") and not s.startswith("Recensement"): sous = s
        if haut: sect = " ".join(haut)
    if cur: out.append(cur)
    return out

def analyser():
    its = items()
    pdf = telecharger(its[0]["url"])
    P = puces(pdf)
    for i, p in enumerate(P): p["n"] = i; p["cle"] = norm(p["texte"])
    par_cle = {}
    for p in P: par_cle.setdefault(p["cle"][:70], []).append(p)
    lien, manque = {}, []
    for i, it in enumerate(its):
        k = norm(it.get("text"))
        c = par_cle.get(k[:70]) or [p for p in P if k and (k in p["cle"] or (len(p["cle"]) > 30 and p["cle"] in k))]
        if c: lien["cgt-%d" % i] = c[0]["n"]
        else: manque.append((i, (it.get("text") or "")[:80]))
    h = hashlib.sha256(open(pdf, "rb").read()).hexdigest()
    json.dump({"pdf": its[0]["url"], "sha256": h, "pages": max(p["page"] for p in P), "lignes": [{k: p[k] for k in ("n", "page", "secteur", "sous", "texte")} for p in P], "items": lien},
              open(os.path.join(D, "index.json"), "w", encoding="utf-8"), ensure_ascii=False)
    print(len(its), "lignes extraites ;", len(P), "puces dans le PDF ;", len(lien), "rattachées ;", len(manque), "non retrouvées", file=sys.stderr)
    return manque

if __name__ == "__main__":
    m = analyser()
    for x in m[:12]: print("  non retrouvée :", x)
    I = json.load(open(os.path.join(D, "index.json")))
    import collections
    print(collections.Counter(l["secteur"][:38] for l in I["lignes"]).most_common(14))
    for i in ("cgt-285", "cgt-29", "cgt-94"):
        l = I["lignes"][I["items"][i]] if i in I["items"] else None
        print(i, "→", l and (l["page"], l["secteur"][:30], l["sous"][:30], l["texte"][:90]))
