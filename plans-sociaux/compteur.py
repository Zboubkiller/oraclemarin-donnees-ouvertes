"""Compteurs : public/compteur.json, recalculé toutes les 15 minutes (cron). Deux périodes : depuis le 1er janvier, et
depuis le début du suivi (DEPUIS).
- procedures.reel : jugements d'ouverture de procédure collective publiés au BODACC sur la période (décompte exact, tous
  effectifs). Le BODACC publie par paquets irréguliers : la page ajoute une extrapolation au rythme moyen des 8 dernières
  semaines depuis la dernière mise à jour, présentée comme une estimation.
- emplois_annonces : suppressions ou menaces d'emplois ANNONCÉES (presse, liste CGT), dédoublonnées par entreprise
  (même entreprise citée plusieurs fois à moins de 60 jours d'écart : on garde le chiffre le plus élevé). Borne basse.
- salaries_procedures : salariés des entreprises de 50 salariés et plus entrées en procédure collective (BODACC, bas de la
  tranche d'effectif INSEE, une fois par entreprise). Ce ne sont pas des licenciements : une entreprise en redressement
  peut garder tous ses salariés."""
import json, os, re, sys, time, unicodedata, urllib.parse, urllib.request, datetime as dt
from commun import nature_emplois
H = os.path.dirname(os.path.abspath(__file__))
DEPUIS = "2026-10-08"
B = "https://bodacc-datadila.opendatasoft.com/api/explore/v2.1/catalog/datasets/annonces-commerciales/records?"
W = 'familleavis="collective" and typeavis_lib="Avis initial" and jugement like "*Jugement d\'ouverture*"'

def get(p):
    for i in range(3):
        try: return json.load(urllib.request.urlopen(urllib.request.Request(B + urllib.parse.urlencode(p), headers={"User-Agent": "tracker-plans-sociaux/0.6"}), timeout=40))
        except Exception: time.sleep(2 + 3 * i)
    return None
def compte(where):
    r = get({"select": "count(*) as n", "where": where})
    return r["results"][0]["n"] if r else None
def cle(nom): return re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFD", (nom or "").lower()).encode("ascii", "ignore").decode())[:20]

def emplois_annonces(ev, depuis):
    import commun
    tous = [e for e in ev if e.get("source") != "BODACC" and (e.get("date") or "") >= depuis]
    nv = sorted([e for e in tous if not commun.exclu_totaux(e)], key=lambda e: e.get("date") or "")
    garde = []                                   # [clé, date, emplois, nature]
    for e in nv:
        k, d = cle(e.get("entreprise")), e["date"]
        g = next((x for x in garde if k and x[0] == k and (dt.date.fromisoformat(d) - dt.date.fromisoformat(x[1])).days <= 60), None)
        if g:
            if (e.get("emplois_min") or 0) > g[2]: g[2], g[3] = e["emplois_min"], nature_emplois(e)
        else: garde.append([k or e.get("id"), d, e.get("emplois_min") or 0, nature_emplois(e)])
    par_nature = {}
    for x in garde: par_nature[x[3]] = par_nature.get(x[3], 0) + x[2]
    top = sorted(garde, key=lambda x: -x[2])[:5]
    return {"min": sum(x[2] for x in garde), "plans": len(garde), "par_nature": par_nature,
            "part_5_plus_gros_pct": round(100 * sum(x[2] for x in top) / max(1, sum(x[2] for x in garde))), "sans_effectif": sum(1 for x in garde if not x[2]), "doublons_retires": len(nv) - len(garde), "exclus": len(tous) - len(nv)}

def salaries_procedures(ev, depuis, complet):
    vus = {}
    for e in ev:
        if e.get("source") == "BODACC" and (e.get("date_publication") or e.get("date") or "") >= depuis and e.get("siren"):
            vus[e["siren"]] = max(vus.get(e["siren"], 0), e.get("emplois_min") or 0)
    return {"min": sum(vus.values()), "entreprises": len(vus), "complet": complet}

def main():
    aujourd = dt.date.today()
    an0 = aujourd.replace(month=1, day=1).isoformat()
    hist = compte(W + f' and dateparution>="{(aujourd - dt.timedelta(days=56)).isoformat()}" and dateparution<"{aujourd.isoformat()}"')
    d30 = (aujourd - dt.timedelta(days=30)).isoformat()
    ra, rs = compte(W + f' and dateparution>="{an0}"'), compte(W + f' and dateparution>="{d30}"')
    if None in (hist, ra, rs):
        print("BODACC indisponible, compteur inchangé", file=sys.stderr); return
    try: ev = json.load(open(os.path.join(H, "public", "data.json")))["evenements"]
    except Exception: ev = []
    try:
        import commun
        cv = json.load(open(os.path.join(H, "public", "etat.json")))["couverture"]
        note = (f"Liste CGT (dernière édition publiée : {commun.mois_long(cv['cgt_edition'][:7])}) et presse (suivie depuis {commun.mois_long(cv['presse_depuis'][:7])}), "
                "accords d'entreprise sans effectif. Annonces hors de France ou sans entreprise précise exclues.")
    except Exception:
        note = "Liste CGT et presse. Annonces hors de France ou sans entreprise précise exclues."
    try: cov = json.load(open(os.path.join(H, "public", "tendance.json")))["plus_de_50_salaries"].get("couverture")
    except Exception: cov = None
    out = {"maj": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "rythme_par_jour": round(hist / 56, 1),
           "periodes": {
               "annee": {"depuis": an0, "reel": ra, "emplois_annonces": emplois_annonces(ev, an0),
                         "salaries_procedures": salaries_procedures(ev, an0, bool(cov and cov[0] <= an0)),
                         "note_emplois": note},
               "suivi": {"depuis": d30, "reel": rs, "emplois_annonces": emplois_annonces(ev, d30),      # 30 derniers jours (clé gardée pour la page)
                         "salaries_procedures": salaries_procedures(ev, d30, True),
                         "note_emplois": note}}}
    tmp = os.path.join(H, "public", "compteur.json.tmp")
    json.dump(out, open(tmp, "w"), ensure_ascii=False); os.replace(tmp, os.path.join(H, "public", "compteur.json"))
    print(json.dumps(out, ensure_ascii=False))

if __name__ == "__main__":
    main()
