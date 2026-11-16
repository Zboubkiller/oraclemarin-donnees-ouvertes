"""Page de travail « Quotas de CO₂ gratuits » : pour les sociétés de la base qui exploitent des installations du marché européen du carbone (SEQE-UE),
quotas gratuits alloués et émissions vérifiées sur 2021-2025, valeur indicative et annonces récentes (plan social, fermeture, procédure collective).
Page non référencée (noindex), absente du menu et du plan du site : version de travail à valider. Données : quotas_co2.json (prep_quotas.py)."""
import csv, datetime as dt, json, os, sqlite3, sys
H = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, H)
import commun as S
esc, fr = S.esc, S.fr
ANNEES = ("2021", "2022", "2023", "2024", "2025")
PRIX = (65, 80)       # euros par tonne : fourchette indicative (voir « méthode »)
MOIS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]
TYPES = {"plan social": "plan social", "fermeture": "fermeture", "liquidation": "liquidation", "redressement": "redressement", "sauvegarde": "sauvegarde"}

def mois(d): return f"{MOIS[int(d[5:7]) - 1]} {d[:4]}"
def mt(x): return f"{x / 1e6:.2f}".replace(".", ",") if x >= 1e5 else f"{x / 1e3:.0f}".replace(".", ",") + " k"

def p_quotas(EV, FICHES):
    try: Q = json.load(open(os.path.join(H, "quotas_co2.json"), encoding="utf-8"))
    except Exception as ex:
        print("quotas : données absentes", ex); return None
    try: SQ = sqlite3.connect(os.path.join(H, "sirene.db"))
    except Exception: SQ = None
    nom_ul = lambda s: ((SQ.execute("select nom from ul where siren=?", (s,)).fetchone() or [None])[0] if SQ else None)
    par = {}
    for e in EV:
        if e.get("siren"): par.setdefault(e["siren"], []).append(e)
    rows = []
    for sir, evs in par.items():
        q = Q.get(sir)
        if not q: continue
        gr = sum(v for ins in q["installations"] for y, v in ins["gratuits"].items() if y in ANNEES)
        ve = sum(v for ins in q["installations"] for y, v in ins["verifiees"].items() if y in ANNEES)
        if gr <= 0 and ve <= 0: continue
        recents = sorted({(e["date"][:10], e["type"], e.get("emplois_min")) for e in evs if e["type"] in TYPES and (e.get("date") or "") >= "2024-01-01"
                         and not e.get("sans_entreprise") and not e.get("doublon_de") and e.get("source") != "Sirene"}, reverse=True)[:2]
        ademe = max(((e.get("argent_public") or {}).get("ademe") or {}).get("total") or 0 for e in evs)
        acts = {}
        for ins in q["installations"]: acts[ins["activite"]] = acts.get(ins["activite"], 0) + 1
        nom = (nom_ul(sir) or q["titulaire"] or "").title()
        rows.append({"siren": sir, "nom": nom, "inst": len(q["installations"]), "activite": max(acts, key=acts.get), "gratuits": gr, "verifiees": ve,
                     "part": (gr / ve if ve else None), "bas": gr * PRIX[0] / 1e6, "haut": gr * PRIX[1] / 1e6, "ademe": ademe, "recents": recents,
                     "fiche": FICHES.get(sir)})
    rows.sort(key=lambda r: -r["gratuits"])
    def ligne(r):
        nom = f'<a href="{S.BASE}/entreprise/{esc(r["fiche"])}/">{esc(r["nom"])}</a>' if r["fiche"] else esc(r["nom"])
        ann = "<br>".join(f'{esc(TYPES[t])} {esc(mois(d))}' + (f' ({fr(n)} emplois)' if n else "") for d, t, n in r["recents"]) or "—"
        part = f'{r["part"] * 100:.0f} %' if r["part"] is not None else "—"
        return (f'<tr{" class=hl" if r["recents"] else ""}><td>{nom}<br><small>{esc(r["activite"])}</small></td><td class="n">{r["inst"]}</td><td class="n">{mt(r["gratuits"])}</td>'
                f'<td class="n">{mt(r["verifiees"])}</td><td class="n">{part}</td><td class="n">{fr(round(r["bas"]))} à {fr(round(r["haut"]))}</td>'
                f'<td class="n">{(str(round(r["ademe"] / 1e6, 1)).replace(".", ",") + " M€") if r["ademe"] else "—"}</td><td>{ann}</td></tr>')
    corps_l = "".join(ligne(r) for r in rows)
    with open(os.path.join(S.PUB, "quotas-co2.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";"); w.writerow(["siren", "societe", "installations", "quotas_gratuits_2021_2025", "emissions_verifiees_2021_2025", "valeur_indicative_basse_Meur", "valeur_indicative_haute_Meur", "aides_ademe_eur", "annonces_depuis_2024"])
        for r in rows: w.writerow([r["siren"], r["nom"], r["inst"], int(r["gratuits"]), int(r["verifiees"]), round(r["bas"], 1), round(r["haut"], 1), r["ademe"], " | ".join(f"{t} {d}" for d, t, n in r["recents"])])
    n_hl = sum(1 for r in rows if r["recents"])
    css = ("<style>.bandeau{background:#FFF4D6;border:1px solid #C98A00;padding:10px 14px;margin:10px 0;font-size:14px}.tq{overflow-x:auto;margin:12px 0}.tq table{border-collapse:collapse;width:100%;font-size:14px;background:#fff}"
           ".tq th,.tq td{border-bottom:1px solid #E3E6EA;padding:7px 9px;text-align:left;vertical-align:top}.tq th{background:#F2F3F5;font-size:12.5px;position:sticky;top:0}.tq td.n,.tq th.n{text-align:right;white-space:nowrap}"
           ".tq tr.hl td{background:#FFF8EC}.tq small{color:#5A6371}</style>")
    corps = (css + "<h1>Quotas de CO₂ gratuits : qui en reçoit, qui ferme</h1>"
             '<div class="bandeau"><b>Version de travail, non référencée.</b> Les chiffres sont à vérifier avant toute citation : relisez la méthode et les limites en bas de page.</div>'
             f'<p class="chapo">Les grands sites industriels européens reçoivent des quotas de CO₂ gratuits : le droit d\'émettre sans les acheter. Ce tableau rapproche, pour les sociétés de la base, '
             f'ces quotas, leurs émissions vérifiées et leurs annonces récentes de plans sociaux, fermetures ou procédures collectives. {len(rows)} sociétés, dont {n_hl} avec une annonce depuis 2024 (lignes colorées).</p>'
             '<p class="meta">Période : 2021-2025. Tri : quotas gratuits décroissants. <a href="../quotas-co2.csv">Télécharger le CSV</a>.</p>'
             '<div class="tq"><table><thead><tr><th>Société</th><th class="n">Installations</th><th class="n">Quotas gratuits (M t)</th><th class="n">Émissions vérifiées (M t)</th>'
             f'<th class="n">Part couverte gratuitement</th><th class="n">Valeur indicative (M€, {PRIX[0]} à {PRIX[1]} €/t)</th><th class="n">Aides ADEME (total)</th><th>Annonces depuis 2024</th></tr></thead>'
             f'<tbody>{corps_l}</tbody></table></div>'
             '<h2>Comment lire ce tableau</h2>'
             '<p>Un quota gratuit n\'est pas une somme versée : c\'est un droit d\'émettre une tonne de CO₂ que l\'entreprise n\'a pas à acheter. La « valeur indicative » est le nombre de quotas multiplié par une fourchette de prix de marché ; '
             'c\'est un ordre de grandeur de l\'avantage, pas un montant reçu. Une société peut avoir reçu moins de quotas que ses émissions (elle achète alors la différence) ou davantage (elle peut revendre le surplus).</p>'
             '<h2>Méthode et sources</h2>'
             '<ul><li><b>Quotas et émissions</b> : registre de l\'Union européenne (EU Transaction Log), reprise dans le paquet de données publié sur Zenodo le 21 juillet 2026 (licence CC-BY 4.0), champs « allocated_free » et « verified ». '
             'Les sociétés sont reliées par le numéro d\'immatriculation (SIREN) du titulaire du compte. Les données de la dernière année peuvent être provisoires.</li>'
             f'<li><b>Prix</b> : fourchette de {PRIX[0]} à {PRIX[1]} € la tonne. Repères : environ 65 € de moyenne en 2024 (Agence européenne pour l\'environnement), plus de 80 € en 2022 et 2023 (EASA), environ 73 € sur les onze premiers mois de 2025 (presse spécialisée). Ce ne sont pas des prix payés par chaque société.</li>'
             '<li><b>Annonces</b> : plans sociaux, fermetures et procédures collectives de la base « Plans sociaux et faillites en France », depuis le 1er janvier 2024.</li>'
             '<li><b>Aides ADEME</b> : total des aides financières de l\'ADEME rapprochées de la société (voir sa fiche).</li></ul>'
             '<h2>Limites</h2>'
             '<ul><li>Seules les sociétés présentes dans la base figurent ici. Le rapprochement par SIREN du titulaire de compte peut associer à une société les installations d\'une autre entité du groupe.</li>'
             '<li>Les règles d\'allocation changent à partir de 2026 (mécanisme d\'ajustement carbone aux frontières, réduction progressive des quotas gratuits) : ne pas extrapoler ces chiffres.</li>'
             '<li>Un lien entre quotas gratuits et fermeture n\'est pas établi : ce tableau rapproche des faits publics, il n\'en tire pas de cause.</li></ul>'
             f'<p class="meta">Données arrêtées au {dt.date.today().strftime("%d/%m/%Y")}. Édité par Quentin Closset, Perros-Guirec.</p>')
    S.ecrire("quotas-co2/index.html", S.page("Quotas de CO₂ gratuits : qui en reçoit, qui ferme (version de travail)", "Quotas de CO₂ gratuits des sites industriels français et annonces récentes de fermetures et de plans sociaux : version de travail.",
                                             "quotas-co2/", corps, None, "", robots="noindex,nofollow"))
    print(f"quotas CO₂ : {len(rows)} sociétés, {n_hl} avec annonce récente")
    return S.BASE_URL + "/quotas-co2/"
