#!/bin/sh
# Collecte quotidienne (cron 7h30 et 19h30) : presse, BODACC/CGT + recoupements, séries officielles, tendance, compteur, pages.
cd /opt/plans-sociaux || exit 1
P=/usr/bin/python3
$P presse.py >> presse.log 2>&1
$P sirene_cible.py >> collect.log 2>&1
$P bodacc_cible.py >> collect.log 2>&1
$P collect.py >> collect.log 2>&1 || exit 1
$P officiel.py >> collect.log 2>&1
$P macro.py >> collect.log 2>&1
$P tendance.py >> collect.log 2>&1
$P compteur.py >> compteur.log 2>&1
$P render.py >> collect.log 2>&1
# Analyse des signaux de légitimité économique via Gemini sur les nouvelles annonces
# MASQUÉ le 2026-10-15 en attendant décision (synthèses IA non affichées) : $P detecteur_legitimite.py --limite 50 >> collect.log 2>&1 || true
# IndexNow une fois par jour (passage du soir) pour les pages qui changent chaque jour
if [ "$(date +%H)" -ge 19 ]; then $P pages.py --indexnow >> collect.log 2>&1; else $P pages.py >> collect.log 2>&1; fi
$P post_pages.py >> collect.log 2>&1
$P cgt_pdf_sourcee.py >> collect.log 2>&1 || true
$P audit_lieu.py >> collect.log 2>&1
$P etat.py >> collect.log 2>&1
python3 auto_ident.py > /dev/null 2>&1 || true
