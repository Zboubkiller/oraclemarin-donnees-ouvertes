"""Archive mensuelle datée des fichiers de données (preuve d'antériorité en cas de copie) :
copie locale dans archives/AAAA-MM/ avec manifeste SHA-256, puis demande d'archivage du CSV à la Wayback Machine (Internet Archive).
Usage : archive_mensuelle.py (cron le 1er de chaque mois)."""
import gzip, hashlib, json, os, shutil, sys, time, urllib.request
H = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(H, "archives", time.strftime("%Y-%m")); os.makedirs(D, exist_ok=True)
man = {}
for f in ("evenements.csv", "restructurations.csv", "data.json", "compteur.json"):
    src = os.path.join(H, "public", f)
    if not os.path.exists(src): continue
    dst = os.path.join(D, f + (".gz" if f.endswith(".json") else ""))
    if dst.endswith(".gz"):
        with open(src, "rb") as a, gzip.open(dst, "wb") as b: shutil.copyfileobj(a, b)
    else: shutil.copy(src, dst)
    man[f] = hashlib.sha256(open(src, "rb").read()).hexdigest()
json.dump({"date": time.strftime("%Y-%m-%dT%H:%M:%S"), "sha256": man}, open(os.path.join(D, "manifeste.json"), "w"), indent=1)
for f in ("evenements.csv", "restructurations.csv"):
    u = "https://oraclemarin.fr/plans-sociaux/" + f
    try:
        r = urllib.request.urlopen(urllib.request.Request("https://web.archive.org/save/" + u, headers={"User-Agent": "plans-sociaux-archive (quentinclosset@gmail.com)"}), timeout=120)
        print("wayback", f, r.status, r.headers.get("Content-Location"))
    except Exception as ex:
        print("wayback", f, "échec :", ex, file=sys.stderr)
    time.sleep(5)
print("archive", D, man)
