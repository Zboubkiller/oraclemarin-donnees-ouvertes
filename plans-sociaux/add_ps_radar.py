import json
F="/var/www/quotas-carbone/radar_full.json"
J=json.load(open(F,encoding="utf-8"));EV=json.load(open("public/data.json",encoding="utf-8"))["evenements"]
par={}
for e in EV:
    if e.get("siren"): par.setdefault(e["siren"],[]).append(e)
for r in J["lignes"]:
    L=sorted(par.get(r["siren"],[]),key=lambda e:e.get("date") or "",reverse=True)
    r["ps"]=[{"d":e.get("date"),"c":e.get("commune"),"t":e.get("type"),"n":e.get("emplois_max"),"s":e.get("source"),"x":(e.get("titre") or "")[:140]} for e in L[:6]]
    r["ps_n"]=len(L)
json.dump(J,open(F,"w",encoding="utf-8"),ensure_ascii=False,separators=(",",":"))
print(sum(1 for r in J["lignes"] if r["ps_n"]),"sociétés avec annonces")
