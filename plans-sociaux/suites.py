"""Suites des procédures collectives (BODACC) : que devient une entreprise de 50 salariés ou plus après un redressement
judiciaire ou une sauvegarde ? Chronologie des jugements par SIREN, classée en : liquidation, cession, plan (continuation),
en cours. « En cours » = aucune décision publiée à ce jour (le BODACC publie avec retard : lecture prudente).
Cohorte comparable : procédures ouvertes entre 9 et 19 mois avant aujourd'hui."""
import json, sys, time, urllib.parse, datetime as dt
import collect

db = collect.db
db.execute("create table if not exists suites(siren text primary key, js text, ts real)")

def fetch(siren):
    r = db.execute("select js, ts from suites where siren=?", (siren,)).fetchone()
    if r and time.time() - r[1] < 7 * 86400:
        tl = json.loads(r[0])
        if all("texte" in t for t in tl): return tl          # anciens caches sans le texte du jugement : on recharge
    sp = f"{siren[:3]} {siren[3:6]} {siren[6:]}"
    d = collect.get(collect.BODACC + "?" + urllib.parse.urlencode({
        "select": "dateparution,typeavis_lib,jugement", "where": f'familleavis="collective" and registre="{sp}"', "order_by": "dateparution", "limit": 60}))
    if d is None: return None
    tl = []
    for x in d.get("results", []):
        if x.get("typeavis_lib") != "Avis initial": continue
        j = json.loads(x.get("jugement") or "{}")
        tl.append({"date": x["dateparution"], "nature": j.get("nature") or "", "date_jugement": j.get("date"), "texte": (j.get("complementJugement") or "")[:700]})
    db.execute("replace into suites values(?,?,?)", (siren, json.dumps(tl, ensure_ascii=False), time.time())); db.commit()
    time.sleep(0.15)
    return tl

def etape(nature):
    n = (nature or "").lower()
    if "ouverture" in n:
        return "liquidation" if "liquidation" in n else "sauvegarde" if "sauvegarde" in n else "redressement" if "redressement" in n else None
    if "plan de cession" in n: return "cession"
    if "conversion en liquidation" in n or ("résolution" in n and "liquidation" in n) or "reprise de la procédure de liquidation" in n: return "liquidation"
    if "conversion en redressement" in n or ("résolution" in n and "redressement" in n): return "redressement"
    if "plan de redressement" in n or "plan de sauvegarde" in n:
        return None if "modifiant" in n else "plan"
    if "clôture" in n: return "cloture"
    return None

def issue(tl, depuis):
    """État à ce jour d'une procédure ouverte à la date `depuis` : la dernière décision parmi liquidation / cession / plan."""
    etat, date = "en cours", None
    for t in tl:
        if t["date"] < depuis: continue
        e = etape(t["nature"])
        if e in ("liquidation", "cession", "plan"): etat, date = e, t["date"]
        elif e == "cloture" and etat == "en cours": etat, date = "liquidation", t["date"]
    return etat, date

def enrichir(evs, limite=400):
    """Ajoute e['suite'] aux procédures BODACC de redressement/sauvegarde. Réseau limité à `limite` SIREN nouveaux par appel."""
    n = 0
    for e in evs:
        if e.get("source") != "BODACC" or e.get("type") not in ("redressement", "sauvegarde") or not e.get("siren"): continue
        if n >= limite and not db.execute("select 1 from suites where siren=?", (e["siren"],)).fetchone(): continue
        if not db.execute("select 1 from suites where siren=?", (e["siren"],)).fetchone(): n += 1
        tl = fetch(e["siren"])
        if tl is None: continue
        etat, date = issue(tl, e.get("date_publication") or "")
        e["suite"] = {"issue": etat, "date": date}
        if etat == "cession":
            import bodacc_details
            t = next((t for t in reversed(tl) if etape(t["nature"]) == "cession"), None)
            r = bodacc_details.repreneur(t.get("texte")) if t else None
            if r: e["suite"]["repreneur"] = r
    # chronologie complète des jugements (toutes procédures BODACC), pour les fiches entreprise
    for e in evs:
        if e.get("source") != "BODACC" or not e.get("siren"): continue
        r = db.execute("select js from suites where siren=?", (e["siren"],)).fetchone()
        tl = json.loads(r[0]) if r else (fetch(e["siren"]) if n < limite else None)
        if not r and tl is not None: n += 1
        if tl: e["chronologie"] = [{"date": t["date"], "date_jugement": t.get("date_jugement"), "nature": t["nature"]} for t in tl if t["nature"]][-12:]

def cohortes():
    ajd = dt.date.today()
    lo = (ajd - dt.timedelta(days=19 * 30)).isoformat(); hi = (ajd - dt.timedelta(days=9 * 30)).isoformat()
    evs = [json.loads(r[0]) for r in db.execute("select js from ev")]
    out = {"periode_ouverture": [lo, hi], "types": {}}
    manque = 0
    for typ in ("redressement", "sauvegarde"):
        cohorte = [e for e in evs if e.get("source") == "BODACC" and e.get("type") == typ and lo <= (e.get("date_publication") or "") <= hi and e.get("siren")]
        c = {"liquidation": 0, "cession": 0, "plan": 0, "en cours": 0}
        for e in cohorte:
            tl = fetch(e["siren"])
            if tl is None: manque += 1; continue
            c[issue(tl, e["date_publication"])[0]] += 1
        n = sum(c.values())
        out["types"][typ] = {"n": n, **c}
    out["indisponibles"] = manque
    return out

if __name__ == "__main__":
    print(json.dumps(cohortes(), ensure_ascii=False))
