"""Relecture de l'effectif des lignes de la liste CGT. Le chiffre extrait automatiquement du PDF est souvent le plus grand nombre
de la ligne : effectif total du groupe, suppressions au niveau mondial ou européen, effectif d'une usine dont seule une part est visée.
On relit le texte pour garder le nombre d'emplois visés EN FRANCE :
- « dont N en France » l'emporte toujours ;
- si la ligne parle du monde, de l'Europe ou de l'effectif d'un groupe, on cherche « N … en France » ;
- sinon on garde les nombres liés à une suppression (« suppression de N », « N emplois supprimés », « PSE sur N »…), en écartant
  ceux qui décrivent un effectif ou un périmètre étranger ; si la ligne annonce plusieurs plans successifs, on les additionne ;
- si le seul nombre disponible est un effectif ou un périmètre hors France, la ligne n'est pas comptée (effectif inconnu), avec une note."""
import re

NB = r"(\d{1,3}(?:[  .]\d{3})+|\d+)"
VISE = re.compile(r"suppression|supprim|licenci|\bpse\b|plan |menac|départs?|ruptures?|délocalis|fermeture|ferme |risque|sellette|reclass|concern|impact", re.I)
HORS = re.compile(r"mondial|dans le monde|monde entier|europ|pays\b|à l.international|groupe de|effectifs? (?:de |du )(?:l.usine|du site|du groupe|groupe)"
                  r"|emploie|compte \d|personnes et|chiffre d.affaires|représentant", re.I)
LIGNE_HORS = re.compile(r"mondial|dans le monde|europ|\d+ pays|groupe de \d", re.I)
DONT_FR = re.compile(r"dont\s*" + NB + r"\s*(?:emplois|postes|personnes|salariés)?\s*en France", re.I)
N_FR = re.compile(NB + r"\s*(?:emplois|postes|personnes|salariés|licenciements|suppressions)[^.;()]{0,25}?\ben France\b", re.I)
PLUSIEURS = re.compile(r"supplémentaire|nouveau plan|nouvelle (?:annonce|vague|fermeture)|second plan|deuxième plan", re.I)
NON_ENTREPRISES = {"fonction publique"}

def val(s): return int(re.sub(r"\D", "", s))

def relire(texte, jobs, nom=""):
    """(emplois retenus ou None, note ou None)."""
    t = texte or ""
    if nom: t = t.replace(nom, "")                 # « Maisons du Monde » ne doit pas déclencher « monde »
    if (nom or "").strip().lower() in NON_ENTREPRISES:
        return None, "pas une entreprise (suppressions de postes publics)"
    m = DONT_FR.search(t) or (LIGNE_HORS.search(t) and N_FR.search(t))
    if m:
        n = val(m.group(1))
        if 5 <= n < 100000:
            return n, (None if n == jobs else f"chiffre France retenu ({n}) au lieu de {jobs}")
    cands = []
    for m in re.finditer(NB, t):
        n = val(m.group(1))
        if not (5 <= n < 100000): continue
        avant, apres = t[max(0, m.start() - 45):m.start()], t[m.end():m.end() + 60]
        # le nombre doit être suivi de son unité : écarte les dates (« 05.25 ») et les années (« en 2025 »)
        if not re.match(r"\s*(?:emplois?|postes|licenciements|suppressions|salariés|personnes|départs|CDI)", apres, re.I):
            continue
        prop = re.split(r"[;(]| dans le cadre", apres)[0]   # le contexte s'arrête à la fin de la proposition
        ctx = avant[-16:] + " " + prop                 # « 10 000 emplois en Europe ; PSE sur 110 » garde 110
        autres = bool(re.search(r"prestataires?|sous-traitants", apres[:50], re.I))   # emplois d'autres entreprises
        cands.append((n, bool(VISE.search(avant + apres)), bool(HORS.search(ctx)) or autres))
    bons = list(dict.fromkeys(n for n, v, h in cands if v and not h))
    if len(bons) >= 2 and PLUSIEURS.search(t):
        s = sum(bons)
        return s, (None if s == jobs else f"plusieurs plans dans la même ligne : {' + '.join(map(str, bons))} = {s} (au lieu de {jobs})")
    if jobs in bons: return jobs, None
    if bons: return max(bons), f"chiffre relu dans le texte ({max(bons)}) au lieu de {jobs}"
    if jobs and any(n == jobs and h for n, v, h in cands):
        return None, f"{jobs} : effectif du groupe ou périmètre hors France, non compté"
    return jobs, None
