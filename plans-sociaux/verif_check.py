import json,collections,random
D=json.load(open("/opt/plans-sociaux/public/data.json")); ev=D["evenements"]
ben=[e for e in ev if e.get("fiable") and (e.get("comptes") or {}).get("profitable") and e["type"] in ("plan social","fermeture")]
print("bénéficiaires",len(ben),collections.Counter((e.get("lien"),e.get("verif_ident")) for e in ben))
print("synthèse",{k:v for k,v in D["synthese"].items() if isinstance(v,int)})
print("liens",collections.Counter((e.get("lien"),e.get("verif_ident")) for e in ev if e["source"]!="BODACC" and e.get("siren")))
random.seed(5); c=[e for e in ben if e.get("verif_ident")=="confirmé"]
for e in random.sample(c,min(10,len(c))): print("  ",e["entreprise"][:28],e.get("dep"),"|",(e.get("titre") or e.get("detail") or "")[:70])
