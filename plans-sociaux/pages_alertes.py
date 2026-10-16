"""Alertes et lettre hebdomadaire : flux RSS par département et par secteur, page /alertes/, page /cette-semaine/,
archives /semaine/<année>-s<nn>/ et flux lettre.xml (une entrée par semaine, contenu complet, utilisable par un service
d'envoi de lettre par e-mail à partir d'un flux RSS)."""
import datetime as dt
from email.utils import format_datetime
import commun as S
from commun import esc, fr, date_long
import pages_fiche as PF

def titre_ev(e):
    emp = (f", {fr(e['emplois_min'])} emplois annoncés" if e.get("emplois_precision") == "annoncé" and e.get("emplois_min")
           else f", {fr(e['emplois_min'])} à {fr(e['emplois_max'])} salariés" if e.get("emplois_min") else "")
    return f"{e['type'].capitalize()} : {e.get('entreprise') or ''}" + (f" ({e['commune']})" if e.get("commune") and not e.get("approx") else "") + emp

def lisible(e):
    return not e.get("sans_entreprise") and e.get("entreprise") != e.get("titre")

def items_ev(evs, FU):
    out = []
    for e in sorted([e for e in evs if e.get("date") and lisible(e)], key=lambda e: (e.get("date_publication") or e["date"]), reverse=True)[:60]:
        d = (e.get("date_publication") or e["date"])[:10]
        out.append((d, titre_ev(e), FU.get(e.get("siren")) and S.BASE_URL + FU[e["siren"]][len(S.BASE):] or e.get("url"), e.get("id")))
    return out

def flux(EV, FU):
    n = 0
    for code, nom in S.DEPS.items():
        evd = [e for e in EV if e.get("dep") == code]
        u = S.dep_url(code, True)
        S.ecrire(u[len(S.BASE_URL) + 1:] + "rss.xml", PF.rss(f"{nom} ({code}) : faillites et plans sociaux — {S.NOM}", u, u + "rss.xml",
                 f"Procédures collectives des entreprises de 50 salariés et plus, plans sociaux et fermetures dans le département {nom}.", items_ev(evd, FU))); n += 1
    secteurs = sorted({S.secteur(e.get("naf")) for e in EV if S.secteur(e.get("naf"))})
    for s in secteurs:
        u = f"{S.BASE_URL}/flux/secteur-{S.slug(s)}.xml"
        S.ecrire(f"flux/secteur-{S.slug(s)}.xml", PF.rss(f"{s} : faillites et plans sociaux — {S.NOM}", S.BASE_URL + "/explorer/#sec=" + s, u,
                 f"Procédures collectives et plans sociaux, secteur {s}.", items_ev([e for e in EV if S.secteur(e.get("naf")) == s], FU))); n += 1
    return secteurs

def p_alertes(secteurs):
    deps = "".join(f'<option value="{S.dep_url(c)}rss.xml">{esc(n)} ({esc(c)})</option>' for c, n in S.DEPS.items())
    secs = "".join(f'<li><a href="{S.BASE}/flux/secteur-{S.slug(s)}.xml">{esc(s)}</a></li>' for s in secteurs)
    titre = "Alertes : suivre les faillites et plans sociaux par département, secteur ou entreprise"
    desc = "Flux RSS gratuits pour être prévenu d'une procédure collective ou d'un plan social dans votre département, votre secteur, ou pour une entreprise précise. Lettre hebdomadaire."
    corps = (f"<h1>Alertes</h1><p class=\"chapo\">Soyez prévenu dès qu'une procédure collective (entreprise de 50 salariés et plus), un plan social ou une fermeture est recensé, "
             "sur le territoire, le secteur ou l'entreprise que vous suivez. Les flux sont mis à jour plusieurs fois par jour.</p>"
             f'<h2>La lettre de la semaine</h2><p>Chaque lundi, ce qui a bougé la semaine précédente : <a href="{S.BASE}/cette-semaine/">voir la semaine en cours</a> · '
             f'<a href="{S.BASE}/lettre.xml">flux de la lettre</a> (une entrée complète par semaine).</p>'
             f'<h2>Par département</h2><p><label for="fd">Choisissez un département</label> <select id="fd"><option value="">—</option>{deps}</select> '
             '<a id="fdl" href="#" hidden>ouvrir le flux</a></p>'
             "<script>const s=document.getElementById('fd'),a=document.getElementById('fdl');s.addEventListener('change',()=>{a.href=s.value;a.textContent=s.value?'Flux : '+s.options[s.selectedIndex].text:'';a.hidden=!s.value})</script>"
             f"<h2>Par secteur</h2><ul>{secs}</ul>"
             "<h2>Par entreprise</h2><p>Chaque fiche entreprise a son propre flux (lien « suivre cette entreprise ») : nouveaux jugements, annonces, mobilisations. "
             f'Cherchez l\'entreprise dans <a href="{S.BASE}/explorer/">l\'explorateur</a> puis ouvrez sa fiche.</p>'
             f'<h2>Tout</h2><p><a href="{S.BASE}/rss.xml">Flux général</a> : les 60 derniers événements.</p>'
             "<h2>Recevoir les alertes par e-mail</h2><p>Copiez l'adresse d'un flux dans un lecteur de flux (Thunderbird, Feedly, Inoreader, NetNewsWire…) "
             "ou dans un service qui envoie les nouveautés d'un flux RSS par e-mail. Une lettre par e-mail directement depuis ce site est en préparation.</p>")
    S.ecrire("alertes/index.html", S.page(titre, desc, "alertes/", corps, [S.site_ld()], "alertes/"))
    return S.BASE_URL + "/alertes/"

def semaine(lundi):
    a, w, _ = lundi.isocalendar()
    return f"{a}-s{w:02d}"

def contenu_semaine(EV, FU, lundi, fin):
    """HTML de la semaine [lundi, fin] (fin incluse)."""
    l0, l1 = lundi.isoformat(), fin.isoformat()
    p0, p1 = (lundi - dt.timedelta(days=7)).isoformat(), (lundi - dt.timedelta(days=1)).isoformat()
    pub = lambda e: (e.get("date_publication") or "")[:10]
    proc = sorted([e for e in EV if e.get("source") == "BODACC" and l0 <= pub(e) <= l1], key=lambda e: -(e.get("emplois_min") or 0))
    proc_av = [e for e in EV if e.get("source") == "BODACC" and p0 <= pub(e) <= p1]
    ann = sorted([e for e in EV if e.get("source") != "BODACC" and lisible(e) and e.get("date_precision") != "mois" and l0 <= (e.get("date") or "") <= l1],
                 key=lambda e: -(e.get("emplois_min") or 0))
    vus, emp = set(), 0
    for e in ann:
        k = e.get("siren") or S.cle_nom(e.get("entreprise"))
        if k not in vus and e.get("emplois_precision") == "annoncé": vus.add(k); emp += e.get("emplois_min") or 0
    sal = sum(e.get("emplois_min") or 0 for e in proc)
    suites, vus2 = [], set()
    for e in EV:
        for t in e.get("chronologie") or []:
            if l0 <= t["date"] <= l1 and not any(x in t["nature"].lower() for x in ("ouverture", "dépôt", "depot", "état des créances", "rectificatif", "faillite personnelle", "interdiction de gérer")) and (e["siren"], t["nature"]) not in vus2:
                vus2.add((e["siren"], t["nature"])); suites.append((e, t))
    mobs, vus3 = [], set()
    for e in EV:
        for m in e.get("mobilisations") or []:
            if l0 <= m["date"] <= l1 and m.get("url") not in vus3: vus3.add(m.get("url")); mobs.append((e, m))
    def nomlien(e):
        fu = FU.get(e.get("siren")) if (e.get("source") == "BODACC" or e.get("lien") in PF.LIEN) else None
        return f'<a href="{S.BASE_URL + fu[len(S.BASE):] if fu else esc(e.get("url"))}">{esc(e.get("entreprise") or "")}</a>'
    def li(e):
        lieu = f" ({esc(e['commune'])}, {esc(e.get('dep') or '')})" if e.get("commune") and not e.get("approx") else (f" ({esc(e['dep'])})" if e.get("dep") else "")
        emp_ = (f" — {fr(e['emplois_min'])} emplois annoncés" if e.get("emplois_precision") == "annoncé" and e.get("emplois_min")
                else f" — {fr(e['emplois_min'])} emplois" if e.get("emplois_min") and e.get("emplois_min") == e.get("emplois_max")
                else f" — {fr(e['emplois_min'])} à {fr(e['emplois_max'])} salariés" if e.get("emplois_min") else "")
        return f"<li><b>{nomlien(e)}</b>{lieu} : {esc(e['type'])}{emp_} <span class=meta>[{esc(PF.src_nom(e))}]</span></li>"
    var = "" if not proc_av else f" (semaine précédente : {fr(len(proc_av))})"
    h = (f"<p class=\"chapo\">Du {date_long(l0)} au {date_long(l1)} : <b>{fr(len(proc))}</b> procédures collectives d'entreprises de 50 salariés et plus publiées au BODACC{var}, "
         f"concernant au moins <b>{fr(sal)}</b> salariés ; <b>{fr(len(ann))}</b> plans sociaux ou fermetures annoncés" + (f", au moins <b>{fr(emp)}</b> emplois" if emp else "") + ".</p>")
    if proc: h += "<h2>Procédures collectives (BODACC)</h2><ul>" + "".join(li(e) for e in proc[:40]) + "</ul>"
    if ann: h += "<h2>Plans sociaux et fermetures annoncés</h2><ul>" + "".join(li(e) for e in ann[:40]) + "</ul>"
    if suites: h += "<h2>Ce qui a été décidé</h2><p class=meta>Jugements publiés cette semaine pour des entreprises déjà suivies.</p><ul>" + "".join(
        f"<li><b>{nomlien(e)}</b> : {esc(t['nature'])} <span class=meta>(publié le {esc(t['date'])})</span></li>" for e, t in suites[:30]) + "</ul>"
    if mobs: h += "<h2>Mobilisations</h2><ul>" + "".join(f'<li><b>{nomlien(e)}</b> : <a href="{esc(m.get("url"))}">{esc(m["titre"])}</a></li>' for e, m in mobs[:20]) + "</ul>"
    return h, len(proc) + len(ann)

def p_semaines(EV, FU, n=12):
    auj = dt.date.today()
    lundi0 = auj - dt.timedelta(days=auj.weekday())
    urls, items = [], []
    for k in range(1, n + 1):
        lundi = lundi0 - dt.timedelta(days=7 * k); fin = lundi + dt.timedelta(days=6)
        h, nb = contenu_semaine(EV, FU, lundi, fin)
        sem = semaine(lundi); chemin = f"semaine/{sem}/"
        titre = f"Faillites et plans sociaux : la semaine du {date_long(lundi.isoformat())}"
        prec, suiv = semaine(lundi - dt.timedelta(days=7)), (semaine(lundi + dt.timedelta(days=7)) if k > 1 else None)
        nav = f'<p class=meta>{"<a href=" + chr(34) + S.BASE + "/semaine/" + prec + "/" + chr(34) + ">← semaine précédente</a>" if k < n else ""}' \
              f'{" · <a href=" + chr(34) + S.BASE + "/semaine/" + suiv + "/" + chr(34) + ">semaine suivante →</a>" if suiv else " · <a href=" + chr(34) + S.BASE + "/cette-semaine/" + chr(34) + ">semaine en cours →</a>"}</p>'
        S.ecrire(chemin + "index.html", S.page(titre, f"Procédures collectives, plans sociaux, décisions de justice et mobilisations de la semaine du {date_long(lundi.isoformat())}.", chemin,
                 f"<h1>{esc(titre)}</h1>{h}{nav}{abonner()}", [S.site_ld()], "alertes/"))
        urls.append(S.BASE_URL + "/" + chemin)
        items.append((lundi + dt.timedelta(days=7), titre, S.BASE_URL + "/" + chemin, sem, h))
    h, _ = contenu_semaine(EV, FU, lundi0, auj)
    titre = "Faillites et plans sociaux : cette semaine"
    S.ecrire("cette-semaine/index.html", S.page(titre, "Ce qui a bougé depuis lundi : procédures collectives, plans sociaux, décisions de justice et mobilisations. Mis à jour plusieurs fois par jour.",
             "cette-semaine/", f"<h1>Cette semaine</h1><p class=meta>Semaine en cours, mise à jour plusieurs fois par jour. "
             f'<a href="{S.BASE}/semaine/{semaine(lundi0 - dt.timedelta(days=7))}/">Semaine précédente</a>.</p>{h}{abonner()}', [S.site_ld()], "alertes/"))
    urls.insert(0, S.BASE_URL + "/cette-semaine/")
    def it(d, t, u, g, h):
        return (f"<item><title>{esc(t)}</title><link>{esc(u)}</link><guid isPermaLink=\"true\">{esc(u)}</guid>"
                f"<pubDate>{format_datetime(dt.datetime.combine(d, dt.time(6, 0), dt.timezone.utc))}</pubDate><description><![CDATA[{h.replace(']]>', '')}]]></description></item>")
    S.ecrire("lettre.xml", '<?xml version="1.0" encoding="UTF-8"?><rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom"><channel>'
             f'<title>La lettre de la semaine — {esc(S.NOM)}</title><link>{S.BASE_URL}/alertes/</link><atom:link href="{S.BASE_URL}/lettre.xml" rel="self" type="application/rss+xml"/>'
             "<description>Chaque lundi : procédures collectives, plans sociaux, décisions et mobilisations de la semaine écoulée.</description>"
             f"<language>fr-fr</language><lastBuildDate>{format_datetime(dt.datetime.now(dt.timezone.utc))}</lastBuildDate>{''.join(it(*i) for i in items)}</channel></rss>")
    return urls

def abonner():
    return f'<p class=meta>Recevoir chaque semaine : <a href="{S.BASE}/lettre.xml">flux de la lettre</a> · <a href="{S.BASE}/alertes/">toutes les alertes</a>.</p>'

def tout(EV, FU):
    secteurs = flux(EV, FU)
    return [p_alertes(secteurs)] + p_semaines(EV, FU)
