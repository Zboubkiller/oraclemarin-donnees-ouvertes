import os
os.chdir('/opt/plans-sociaux')
import commun as S, pages_fiche

D = S.charge()
EV = D['data'].get('evenements', [])
G = pages_fiche.groupes(EV)

def a_signal_atypique(evs):
    # Aide recente
    if any(e.get('proximite') for e in evs): return 'Aide publique recente'
    if any(e.get('programmes_etat') for e in evs): return 'Programme Etat / PIA'
    # Holding / fonds
    if any(any(p.get('holding') for p in (e.get('direction') or {}).get('dirigeants_pm') or []) for e in evs): return 'Holding / Fonds'
    # Comptes positifs avec suppression annoncee (non-BODACC)
    has_pse = any(e.get('source') != 'BODACC' for e in evs)
    rn = next(((e.get('comptes') or {}).get('resultat_net') for e in evs if (e.get('comptes') or {}).get('resultat_net') is not None), None)
    if has_pse and rn is not None and rn > 100000: return f'Benefice net ({rn}€) avec PSE'
    # Reprise recente
    if any(e.get('reprise_recente') for e in evs): return 'Reprise / Fusion recente'
    # Sanctions DGCCRF
    if any(e.get('sanction_delais') for e in evs): return 'Sanction DGCCRF'
    # Lobbying important
    if any(e.get('lobbying') for e in evs): return 'Lobbying HATVP'
    return None

candidats = []
for siren, evs in G.items():
    motif = a_signal_atypique(evs)
    if motif:
        candidats.append((siren, pages_fiche.nom_de(evs), motif))

print(f'Total fiches: {len(G)}')
print(f'Total prioritaires avec signaux atypiques: {len(candidats)}')
from collections import Counter
c = Counter(m.split(' (')[0] for _, _, m in candidats)
for k, v in c.most_common():
    print(f'  - {k}: {v}')
