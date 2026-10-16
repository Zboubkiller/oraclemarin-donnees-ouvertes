"""Récupération ciblée au BODACC des procédures collectives des entreprises de la liste noire CGT (et des annonces identifiées à la main).
La collecte générale ne garde que les procédures d'entreprises de plus de 10 salariés : les petites sociétés liquidées échappaient au rapprochement.
Ici, interrogation du BODACC SIREN par SIREN (cache de 7 jours, table audit_bodacc de cache.db) ; complements.py lit ce cache. Usage : bodacc_cible.py"""
import json, os, sys, time
H = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, H)
import audit_ident as A

def cibles():
    E = json.load(open(os.path.join(H, "public", "data.json"), encoding="utf-8"))["evenements"]
    out = set()
    for e in E:
        cgt = str(e.get("source", "")).startswith("CGT") or any(str(s.get("source", "")).startswith("CGT") for s in e.get("sources") or [])
        if (cgt or e.get("valide_humain") or e.get("ident_humain")) and e.get("siren") and e.get("source") != "BODACC": out.add(e["siren"])
    return sorted(out)

def main():
    L = cibles(); ok = proc = 0
    for i, s in enumerate(L):
        r = A.bodacc(s)
        if r is None: continue
        ok += 1; proc += 1 if r else 0
    print(f"BODACC ciblé : {ok}/{len(L)} sociétés interrogées, {proc} avec au moins une procédure collective", file=sys.stderr)

if __name__ == "__main__":
    main()
