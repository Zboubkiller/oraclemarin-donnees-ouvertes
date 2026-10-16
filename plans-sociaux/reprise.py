"""« Reprise ou fusion récente » : pour chaque annonce rattachée à une société, dernière opération publiée au BODACC (achat ou vente d'un
fonds de commerce, d'une branche d'activité, fusion) visant cette société dans les 24 mois AVANT l'annonce. On ne pose aucun lien de cause :
on donne la date de l'opération, son rôle (a repris / a cédé), la contrepartie, le délai en mois et le lien vers l'annonce BODACC.
« À creuser » si le nom de la contrepartie (activité reprise ou repreneur) est cité dans l'annonce, ou si l'opération a moins de 12 mois alors qu'elle est rare pour la société (3 opérations ou moins en 60 mois : pas un groupe qui achète en continu).
Limite : les cessions de titres (rachat d'actions, LBO) ne sont pas publiées au BODACC et n'apparaissent donc pas ici.
Écrit e["reprise_recente"] ; opérations lues dans la table bodacc_ops (operations.py)."""
import datetime as dt, re, sys, unicodedata
NATURES = ("achat ou vente d'un fonds de commerce", "achat ou vente d'une branche d'activité", "fusion")
GENERIQUES = {"france", "groupe", "group", "societe", "sas", "sarl", "sa", "ste", "et", "des", "les", "de", "du", "la", "le", "industrie", "industries", "services", "service", "holding",
              "international", "distribution", "commerce", "media", "medias", "retail", "europe", "gestion", "participations", "finances", "invest", "immobilier"}
FENETRE_MOIS = 24
DELAI_COURT = 12      # mois
OPS_RARES = 3         # au plus 3 opérations de ce type dans la fenêtre : au-delà, une société qui achète ou vend sans cesse (grande distribution, groupes)

def _norm(x):
    return re.sub(r"[^a-z0-9 ]", " ", unicodedata.normalize("NFD", (x or "").lower()).encode("ascii", "ignore").decode())

def mois_entre(a, b):
    """Nombre de mois entiers entre les dates a (avant) et b (après)."""
    return (b.year - a.year) * 12 + (b.month - a.month) - (1 if b.day < a.day else 0)

def cite(contre, texte, nom_societe=""):
    """Un mot distinctif (4 lettres et plus, non générique) du nom de la contrepartie figure dans le texte de l'annonce, sans faire partie
    du nom de la société elle-même (« Suez » pour Suez Eau de France, « monde » pour Maisons du Monde)."""
    t = " " + _norm(texte) + " "
    propre = set(_norm(nom_societe).split())
    return any(" " + w + " " in t for w in _norm(contre).split() if len(w) >= 4 and w not in GENERIQUES and w not in propre)

def enrichir(evs):
    try:
        import operations; OPS = operations.par_siren()
    except Exception as ex:
        print("reprise :", ex, file=sys.stderr); return
    n = a = 0
    for e in evs:
        s = e.get("siren")
        if not s or e.get("source") == "BODACC" or not e.get("date") or e.get("partie_de"): continue
        try: d = dt.date.fromisoformat(e["date"][:10])
        except ValueError: continue
        best = None; nb = 0
        for o in OPS.get(s) or []:
            if o.get("nature") not in NATURES: continue
            try: od = dt.date.fromisoformat(o["date"][:10])
            except (KeyError, ValueError): continue
            m = mois_entre(od, d)
            if od > d or m > FENETRE_MOIS: continue
            nb += 1
            if best is None or od > best[0]: best = (od, m, o)
        e.pop("reprise_recente", None)
        if not best: continue
        od, m, o = best
        texte = (e.get("titre") or "") + " " + (e.get("detail") or "")
        motifs = []
        if m < DELAI_COURT and nb <= OPS_RARES and o.get("contrepartie"): motifs.append("opération rare pour la société, publiée moins de 12 mois avant l'annonce")
        if o.get("contrepartie") and cite(o["contrepartie"], texte, e.get("entreprise")): motifs.append("la contrepartie est citée dans l'annonce")
        e["reprise_recente"] = {"date": od.isoformat(), "delai_mois": m, "role": "a cédé" if o.get("role") == "vendeur" else "a repris ou absorbé" if o.get("nature") != "fusion" else "est la société absorbante ou bénéficiaire",
                                "nature": o.get("nature"), "contrepartie": o.get("contrepartie"), "url": o.get("url"), "nb_operations": nb, "a_creuser": bool(motifs), "motifs": motifs}
        n += 1; a += bool(motifs)
    print(f"reprise récente (BODACC, {FENETRE_MOIS} mois) : {n} annonces concernées, dont {a} « à creuser »", file=sys.stderr)
