# Données ouvertes d'oraclemarin.fr

Code de deux projets de données publiques, par Quentin Closset (Perros-Guirec). Site de l'observatoire : [oraclemarin.fr](https://oraclemarin.fr/) · Méthode : [oraclemarin.fr/methode](https://oraclemarin.fr/methode/) · Autre dépôt : [ca-brule](https://github.com/Zboubkiller/ca-brule).

- **`plans-sociaux/`** : suivi des plans sociaux et fermetures (presse, BODACC, liste CGT, Sirene), rapprochement par SIREN, aides publiques, comptes, lobbying. Site : https://oraclemarin.fr/plans-sociaux/
- **`quotas-carbone/`** : carte et radar des quotas de CO₂ gratuits de 1 055 sites industriels français (registre européen des quotas), croisés avec les aides de l'ADEME, les déclarations de lobbying (HATVP), les annonces d'emplois et les dossiers de sols pollués (Géorisques). Site : https://oraclemarin.fr/quotas-carbone/

Mise à jour de novembre 2026 : ajout des scripts de recoupement avec les aides et subventions (`build_subventions*.py`, `build_lobbying_aides.py`), des sites industriels à l'arrêt (`build_sites_arret.py`), des reprises (`build_reprises.py`), des pages d'audit, de pistes et de territoires (`pages_*.py`), du modèle de page (`template.html`) et d'un [modèle de demande CADA](modele-demande-cada-aides-regionales.md) pour obtenir les aides régionales aux entreprises. L'adresse de contact, les chemins du serveur et les identifiants sont retirés de cette copie (`ADRESSE_DE_CONTACT`, fichier `.env` à créer).

## Principes
- Chaque chiffre vient d'une source publique citée. Les rapprochements automatiques (société ↔ SIREN, classement du lobbying par mots-clés) sont signalés comme tels.
- Aucun lien de cause n'est affirmé : les jeux de données sont mis côte à côte.
- La page `quotas-carbone/site/verif.html` liste ce qui est contrôlé, à vérifier ou non établi. Une erreur ? Ouvrez une issue ou écrivez à quentinclosset@gmail.com : elle sera corrigée et datée.

## Sources
Registre de l'Union européenne des quotas (EU Transaction Log, paquet Zenodo, CC-BY 4.0) · données ouvertes de l'ADEME · registre HATVP · BODACC · Sirene / API Recherche d'entreprises · Géorisques · GLEIF · Direction générale des Entreprises.

## Ce dépôt ne contient pas
Les données collectées, les bases locales, les identifiants et clés d'API (lus depuis un fichier `.env` non versionné), ni les pages d'administration privées. Les scripts supposent l'arborescence du serveur d'origine (`/opt/plans-sociaux`) et ne sont pas prêts à lancer tels quels ailleurs.

## Licence
Code : MIT. Données et pages produites : à citer avec leur source ; les données du registre des quotas restent sous CC-BY 4.0.
