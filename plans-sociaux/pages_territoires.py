# VERSION_PUBLIQUE : page référencée (pied de page, plan du site)
"""Page « Territoires les plus exposés » : communes où une seule annonce de suppression d'emplois pèse plusieurs pour cent de l'emploi salarié privé
(poids local URSSAF), croisée avec l'argent public rapproché de la fiche (ADEME, aides d'État TAM, subventions de collectivités, commandes publiques).
Classement par région puis par département, avec un contrôle automatique de fiabilité par cas. Aucun lien de cause n'est affirmé."""
import csv, datetime as dt, json, os, sqlite3, sys
H = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, H)
import commun as S
esc, fr = S.esc, S.fr
SUPPR = ("plan social", "fermeture", "départs volontaires", "liquidation", "redressement")
MOIS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]
MIN_PART, MIN_EMP, DEPUIS = 2.0, 20, "2024-01-01"

_TR = {}
def _traj(insee):
    """Évolution 2006-2025 de l'emploi salarié privé de la commune (Urssaf), en % ; None si inconnue."""
    if not _TR:
        try: _TR.update(json.load(open(os.path.join(H, "emploi_communes_serie.json"), encoding="utf-8")))
        except Exception: _TR["_"] = None
    sr = _TR.get(insee)
    return round(100 * (sr[-1] / sr[0] - 1)) if isinstance(sr, list) and len(sr) == 20 and sr[0] and sr[-1] and min(sr[0], sr[-1]) >= 100 else None

def n_emp(e): return e.get("emplois_max") or e.get("emplois_min") or 0
def meur(x): return (f"{x / 1e6:.1f}".replace(".", ",") + " M€") if x >= 1e5 else (f"{round(x / 1e3)} k€" if x else "—")
def mois(d): return f"{MOIS[int(d[5:7]) - 1]} {d[:4]}"

def candidats(EV, VAL):
    NB = VAL.get("nombre", {})
    try: SUB = json.load(open(os.path.join(H, "subventions_locales_auto.json"), encoding="utf-8")).get("par_siren", {})
    except Exception: SUB = {}
    SQ = sqlite3.connect(os.path.join(H, "sirene.db"))
    best = {}
    for e in EV:
        pl = e.get("poids_local") or {}
        if (not e.get("siren") or e.get("sans_entreprise") or e.get("doublon_de") or e.get("exclu_totaux") or e.get("source") == "Sirene"
                or e["type"] not in SUPPR or (e.get("date") or "") < DEPUIS or n_emp(e) < MIN_EMP or (pl.get("part_commune_pct") or 0) < MIN_PART or not e.get("commune")): continue
        k = (e["siren"], pl.get("insee") or e["commune"])
        if k not in best or n_emp(e) > n_emp(best[k]): best[k] = e
    out = []
    for e in best.values():
        pl, ap = e["poids_local"], e.get("argent_public") or {}
        ademe = (ap.get("ademe") or {}).get("total") or 0
        tam = (ap.get("tam") or {}).get("total_min") or 0
        mar = (ap.get("marches") or {}).get("total") or 0
        sub = sum(l["montant"] for l in SUB.get(e["siren"], []))
        # contrôles automatiques de fiabilité
        etab = SQ.execute("select count(*) from etab where siren=? and insee=?", (e["siren"], pl.get("insee") or "")).fetchone()[0] if pl.get("insee") else 0   # établissement de la société dans cette commune (Sirene)
        manque = []
        if (e.get("approx") or (e.get("verif_site") or {}).get("niveau") not in ("commune", None)) and not e.get("lieu_corrige_a_la_main") and not etab: manque.append("lieu approximatif")
        if not (e.get("valide_humain") or e.get("verif_ident") == "confirmé" or e.get("lien") == "siren" or etab): manque.append("SIREN non confirmé")
        nb = NB.get(e.get("id"), {})
        doms = {x.replace("www.", "") for x in [(u.get("url") or "").split("/")[2] for u in (e.get("sources") or []) if "//" in (u.get("url") or "")] + [(e.get("url") or "").split("/")[2] if (e.get("url") or "").startswith("http") else "", e.get("source") or ""] if x and " " not in x and "." in x}
        if not (nb.get("choix") == "oui" or len(doms) >= 2): manque.append("emplois cités par une seule source")
        if n_emp(e) > (pl.get("effectif_commune") or 0) * 1.0: manque.append("emplois supérieurs à l'emploi salarié de la commune (groupe entier ?)")
        out.append({"e": e, "pl": pl, "ademe": ademe, "tam": tam, "marches": mar, "sub": sub, "manque": manque, "verifie": not manque})
    return out

def p_territoires(EV, FICHES):
    try: VAL = json.load(open(os.path.join(H, "validations.json"), encoding="utf-8"))
    except Exception: VAL = {}
    C = candidats(EV, VAL)
    reg = {}
    for c in C: reg.setdefault(S.REGIONS.get(c["e"].get("dep") or "", "Autre"), []).append(c)
    def lien(c):
        e = c["e"]; f = FICHES.get(e["siren"])
        return f'<a href="{esc(f) if f.startswith("/") else S.BASE + "/entreprise/" + esc(f) + "/"}">{esc(e["entreprise"])}</a>' if f else esc(e["entreprise"])
    def lig(c):
        e, pl = c["e"], c["pl"]
        pub = " · ".join(x for x in (("ADEME %s" % meur(c["ademe"])) if c["ademe"] else "", ("aides d'État %s" % meur(c["tam"])) if c["tam"] else "",
                                       ("collectivités %s" % meur(c["sub"])) if c["sub"] else "", ("commandes publiques %s" % meur(c["marches"])) if c["marches"] else "") if x) or "aucune trouvée"
        badge = '<span class="ok">contrôles OK</span>' if c["verifie"] else '<span class="chk">à vérifier</span><br><small>' + esc("; ".join(c["manque"])) + "</small>"
        return (f'<tr><td>{esc(e["commune"].title() if e["commune"].isupper() else e["commune"])} ({esc(e.get("dep") or "")})</td><td>{lien(c)}</td><td>{esc(e["type"])} {esc(mois(e["date"][:10]))}<br><small>{fr(n_emp(e))} emplois</small></td>'
                f'<td class="n"><b>{str(pl["part_commune_pct"]).replace(".", ",")} %</b><br><small>emploi privé de la commune ({fr(pl.get("effectif_commune") or 0)}, URSSAF {pl["annee"]})</small>' + ((f'<br><small>depuis 2006 : {_traj(pl.get("insee")):+d} %'.replace('-', '−') + '</small>') if _traj(pl.get("insee")) is not None else '') + '</td>'
                f'<td class="n">{str(pl.get("part_zone_pct", "")).replace(".", ",")} %<br><small>{esc(pl.get("zone_emploi") or "")}</small></td><td><small>{esc(pub)}</small></td><td>{badge}</td></tr>')
    ent = '<thead><tr><th>Commune</th><th>Société</th><th>Annonce</th><th class="n">Poids dans la commune</th><th class="n">Zone d’emploi</th><th>Argent public rapproché</th><th>Contrôle</th></tr></thead>'
    corps_reg, sommaire = "", []
    for r in sorted(reg):
        L = sorted(reg[r], key=lambda c: (-c["verifie"], -c["pl"]["part_commune_pct"]))[:5]
        ident = S.slug(r)
        sommaire.append(f'<a href="#{ident}">{esc(r)}</a>')
        corps_reg += f'<h2 id="{ident}">{esc(r)}</h2><p><small>{len(reg[r])} cas depuis 2024 ; les 5 premiers (contrôles OK d’abord, puis par poids dans la commune).</small></p><div class="tq"><table>{ent}<tbody>' + "".join(lig(c) for c in L) + "</tbody></table></div>"
    # départements : 3 premiers, repliés
    dep = {}
    for c in C: dep.setdefault(c["e"].get("dep") or "?", []).append(c)
    det = ""
    for d in sorted(dep):
        L = sorted(dep[d], key=lambda c: -c["pl"]["part_commune_pct"])[:3]
        det += f'<details class="rc"><summary><b>{esc(S.DEPS.get(d, d) if hasattr(S, "DEPS") and isinstance(S.DEPS, dict) else d)}</b> ({esc(d)}) : {len(dep[d])} cas</summary><div class="tq"><table>{ent}<tbody>' + "".join(lig(c) for c in L) + "</tbody></table></div></details>"
    with open(os.path.join(S.PUB, "territoires-exposes.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";"); w.writerow(["region", "dep", "commune", "societe", "siren", "annonce", "date", "emplois", "effectif_salarie_prive_commune", "part_commune_pct", "part_zone_emploi_pct", "emploi_commune_evolution_2006_2025_pct", "ademe_eur", "aides_etat_eur", "collectivites_eur", "commandes_publiques_eur", "controle"])
        for c in sorted(C, key=lambda c: -c["pl"]["part_commune_pct"]):
            e, pl = c["e"], c["pl"]
            w.writerow([S.REGIONS.get(e.get("dep") or "", ""), e.get("dep"), e["commune"], e["entreprise"], e["siren"], e["type"], e["date"][:10], n_emp(e), pl.get("effectif_commune"), pl["part_commune_pct"], pl.get("part_zone_pct"), _traj(pl.get("insee")),
                        c["ademe"], c["tam"], c["sub"], c["marches"], "contrôles OK" if c["verifie"] else "; ".join(c["manque"])])
    nv = sum(1 for c in C if c["verifie"])
    css = ("<style>.tq{overflow-x:auto;margin:12px 0}.tq table{border-collapse:collapse;width:100%;font-size:14px;background:#fff}.tq th,.tq td{border-bottom:1px solid #E3E6EA;padding:7px 9px;text-align:left;vertical-align:top}"
           ".tq th{background:#F2F3F5;font-size:12.5px}.tq td.n,.tq th.n{text-align:right}.rc{border:1px solid #D6DBE0;margin:6px 0;background:#fff;padding:6px 10px}.rc summary{cursor:pointer;padding:4px 0}"
           ".ok{background:#2E7D32;color:#fff;border-radius:4px;padding:1px 7px;font-size:12px}.chk{background:#E8710A;color:#fff;border-radius:4px;padding:1px 7px;font-size:12px}small{color:#5A6371}</style>")
    corps = (css + "<h1>Territoires les plus exposés</h1><p class=\"chapo\">Communes où une seule annonce de suppression d’emplois pèse plusieurs pour cent de l’emploi salarié privé, rapprochées de l’argent public reçu par la société. "
             "Un classement par région que chaque rédaction locale peut reprendre et vérifier. Il rapproche des faits publics ; il n’établit aucun lien de cause.</p>"
             f'<p class="meta">{len(C)} cas depuis {DEPUIS[:4]} (au moins {MIN_EMP} emplois, au moins {str(MIN_PART).replace(".", ",")} % de l’emploi privé de la commune), dont {nv} passés par tous les contrôles automatiques. '
             f'Sommaire : {" · ".join(sommaire)} · <a href="#departements">départements</a> · <a href="../territoires-exposes.csv">CSV complet</a></p>' + corps_reg +
             f'<h2 id="departements">Par département</h2><p><small>Les trois cas les plus lourds de chaque département (dépliez).</small></p>' + det +
             "<h2>Méthode et limites</h2><ul><li><b>Poids local</b> : nombre d’emplois annoncés rapporté à l’emploi salarié privé de la commune (URSSAF, dernière année publiée). Les emplois annoncés sont parfois ceux d’un groupe entier : le cas est alors marqué « à vérifier ».</li>"
             "<li><b>Contrôles automatiques</b> : « contrôles OK » veut dire lieu précis, SIREN confirmé, emplois cités par au moins deux sources ou validés à la main, et nombre d’emplois inférieur à l’emploi de la commune. Ce n’est pas une garantie ; vérifiez avant de publier.</li>"
             "<li><b>Argent public</b> : aides rapprochées par SIREN (ADEME, aides d’État de la base TAM, subventions de collectivités en données ouvertes, commandes publiques). Elles ne concernent pas forcément le site qui ferme.</li>"
             "<li>Les zones d’emploi sont celles de l’Insee ; la part de la zone est toujours bien plus faible que celle de la commune.</li></ul>"
             f'<p class="meta">Données arrêtées au {dt.date.today().strftime("%d/%m/%Y")}. Édité par Quentin Closset, Perros-Guirec.</p>')
    S.ecrire("territoires/index.html", S.page("Territoires les plus exposés : communes où une annonce pèse sur l'emploi",
             "Classement par région et par département des communes où une suppression d'emplois annoncée pèse plusieurs pour cent de l'emploi privé, avec l'argent public rapproché et un contrôle de fiabilité.",
             "territoires/", corps, None, "", robots="index,follow"))
    print(f"territoires : {len(C)} cas, {nv} vérifiés, {len(reg)} régions")
    return S.BASE_URL + "/territoires/"
