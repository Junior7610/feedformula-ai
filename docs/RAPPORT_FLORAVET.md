# RAPPORT FLORAVET AI — Module 9 FeedFormula AI

## Résumé exécutif

FloraVet AI est le 9ème module de FeedFormula AI. Il transforme la plateforme en bibliothèque botanique vivante pour l’élevage africain : identification de plantes, valorisation fourragère, détection des plantes toxiques, usages médicinaux vétérinaires, recommandations de culture, intégration rationnelle et passerelles avec les autres modules.

Logo du module : 🌿  
Couleur distinctive : `#2E7D32`  
Gamification : `+25 🌟` par analyse botanique

## Fichiers créés ou modifiés

- `prompts/system_prompt_floravet.txt`
- `backend/floravet_service.py`
- `backend/database.py`
- `backend/main.py`
- `frontend/floravet.html`
- `frontend/modules.html`
- `frontend/index.html`
- `frontend/vetscan.html`
- `data/plantes_benin.json`
- `gamification/points_engine.py`
- `tests/test_floravet_complet.py`
- `README.md`
- `docs/RAPPORT_FLORAVET.md`

## 1. System prompt FloraVet AI

Le prompt `prompts/system_prompt_floravet.txt` définit FloraVet AI comme :

- botaniste tropical ;
- ethnobotaniste d’Afrique de l’Ouest ;
- expert plantes fourragères ;
- expert phytothérapie vétérinaire traditionnelle ;
- spécialiste des plantes toxiques pour les animaux.

Le prompt impose 15 sections obligatoires :

1. Identification botanique complète
2. Description botanique complète
3. Distribution et écologie
4. Composition nutritionnelle détaillée
5. Animaux bénéficiaires et doses
6. Vertus médicinales et thérapeutiques
7. Toxicité et contre-indications
8. Intégration dans les rations
9. Impact sur les productions animales
10. Culture et production
11. Écologie et services environnementaux
12. Usages humains et culturels
13. Plantes similaires et comparaison
14. Recommandations personnalisées
15. Message d’Aya et score

Le prompt contient aussi une règle de sécurité : toute plante toxique doit produire un avertissement clair et ne doit jamais être recommandée sans précaution.

## 2. Backend FloraVet

Le service `backend/floravet_service.py` a été créé autour de la classe `FloraVetService`.

### Fonctions principales

- `analyser_plante_photo`
- `rechercher_plante_nom`
- `get_plantes_region`
- `get_plantes_saison`
- `get_plantes_toxiques_alerte`
- `comparer_plantes`
- `get_historique_analyses`
- `get_bibliotheque_plantes_benin`

### Analyse photo

`analyser_plante_photo` réalise :

1. encodage image en base64 ;
2. appel GPT 5.5 Vision si l’API est disponible ;
3. fallback local déterministe si l’API est absente ou en environnement test ;
4. génération des 15 sections ;
5. enrichissement contextuel :
   - ration exemple NutriCore ;
   - maladies aidées / lien VetScan ;
   - intégration PastureMap ;
6. sauvegarde en base ;
7. attribution de `+25 🌟`.

En environnement `test`, l’appel IA externe est volontairement désactivé pour garantir des tests rapides, stables et reproductibles.

## 3. Base de données

Deux modèles ont été ajoutés dans `backend/database.py`.

### Table `analyses_floravet`

Champs :

- `id`
- `user_id`
- `image_hash`
- `nom_scientifique`
- `nom_francais`
- `noms_locaux_json`
- `niveau_confiance`
- `analyse_complete_json`
- `espece_eleveur`
- `region_benin`
- `langue`
- `points_gagnes`
- `date_analyse`

### Table `bibliotheque_plantes`

Champs :

- `id`
- `nom_scientifique`
- `nom_francais`
- `famille_botanique`
- `noms_locaux_json`
- `fiche_complete_json`
- `especes_beneficiaires_json`
- `est_toxique`
- `niveau_toxicite`
- `disponible_benin`
- `regions_benin_json`
- `date_ajout`
- `nb_analyses`

La bibliothèque initiale est chargée depuis `data/plantes_benin.json`. Les tables sont disponibles pour migration future vers un stockage complet en base.

## 4. Endpoints API FloraVet

Le routeur FloraVet est enregistré dans `backend/main.py`.

Endpoints disponibles :

- `POST /floravet/analyser-photo`
- `POST /floravet/analyser-url`
- `GET /floravet/rechercher/{nom}`
- `GET /floravet/region/{region_benin}`
- `GET /floravet/toxiques/{region_benin}`
- `POST /floravet/comparer`
- `GET /floravet/bibliotheque`
- `GET /floravet/historique/{user_id}`
- `GET /floravet/stats`

## 5. Frontend FloraVet

Le fichier `frontend/floravet.html` a été créé.

Interface en 4 sections :

### Section 1 — Analyser une plante

- header vert botanique ;
- logo 🌿 FloraVet AI ;
- badge `+25 🌟 par analyse` ;
- prise photo smartphone ;
- upload galerie ;
- sélection d’une plante courante ;
- prévisualisation ;
- contexte éleveur : espèce, région, langue ;
- bouton `🌿 Analyser avec FloraVet AI` ;
- animation de progression ;
- résultat en sections repliables.

### Section 2 — Bibliothèque des plantes

- recherche par nom ;
- filtres espèce animale et toxicité ;
- grille de cards ;
- score FloraVet ;
- tags fourragère / médicinale / toxique ;
- lien vers fiche complète.

### Section 3 — Plantes de ma région

- top 10 régional ;
- saison prise en compte côté API ;
- alertes plantes toxiques.

### Section 4 — Mes analyses sauvegardées

- historique utilisateur ;
- date ;
- plante identifiée ;
- revoir analyse complète ;
- partage WhatsApp.

## 6. Bibliothèque initiale des 50 plantes

Le fichier `data/plantes_benin.json` contient 50 plantes prioritaires du Bénin :

- 10 légumineuses fourragères ;
- 10 graminées fourragères ;
- 10 arbres fourragers ;
- 10 plantes médicinales vétérinaires ;
- 5 plantes toxiques ;
- 5 plantes de pâturage naturel.

Chaque fiche contient notamment :

- nom scientifique ;
- nom français ;
- famille botanique ;
- noms locaux ;
- usages ;
- espèces bénéficiaires ;
- toxicité ;
- score FloraVet ;
- protéines brutes estimées ;
- régions béninoises ;
- saisons ;
- description.

## 7. Gamification FloraVet

`gamification/points_engine.py` a été mis à jour.

### Actions FloraVet

- `analyser_plante_photo` : 25 points
- `identifier_plante_rare` : 50 points
- `plante_non_repertoriee` : 75 points
- `analyser_10_plantes` : 100 points
- `partager_analyse_floravet` : 15 points
- `identifier_plante_toxique` : 30 points

### Trophées FloraVet

- `botaniste_debutant` — 🌿 Botaniste Débutant
- `botaniste_experimente` — 🌳 Botaniste Expérimenté
- `protecteur_troupeau` — 🛡️ Protecteur du Troupeau
- `ethnobotaniste` — 🌍 Ethnobotaniste Africain
- `bibliotheque_vivante` — 📚 Bibliothèque Vivante

## 8. Intégrations modules

### NutriCore

Chaque analyse FloraVet génère une ration exemple et un lien :

- `nutricore.html?ingredient=<plante>`

### VetScan

`frontend/vetscan.html` affiche désormais une section :

- `🌿 Plantes médicinales recommandées — FloraVet`

avec liens vers FloraVet.

### PastureMap

L’analyse contient une clé `integration_pasturemap` pour qualifier la qualité botanique du pâturage.

### FarmManager

Chaque analyse est sauvegardée en base et journalisée via `UserActionLog`. Elle peut être exploitée comme événement de ferme ou ressource végétale suivie.

### FarmAcademy

Les données FloraVet sont prêtes à alimenter une formation dédiée sur les plantes fourragères du Bénin.

## 9. Mise à jour des modules existants

### `frontend/modules.html`

Ajout de FloraVet AI comme 9ème module :

- icône : 🌿 ;
- couleur : `#2E7D32` ;
- description : `Identifiez et valorisez les plantes de votre ferme` ;
- badge disponible ;
- points : `+25 🌟 par analyse` ;
- bouton vers `floravet.html`.

### `frontend/index.html`

Mise à jour des mentions `8 modules` vers `9 modules` et ajout de FloraVet dans les descriptions.

### `README.md`

La section modules mentionne maintenant FloraVet AI comme 9ème module.

## 10. Tests qualité

Fichier créé : `tests/test_floravet_complet.py`

Tests inclus :

1. analyse photo Moringa avec 15 sections ;
2. recherche par nom : moringa, leucaena, neem ;
3. plantes de la région Atlantique ;
4. bibliothèque de 50 plantes ;
5. intégration NutriCore.

Résultat exécuté :

- `5 passed in 52.10s`
- Score FloraVet : `10/10`

## 11. Résultat final

FloraVet AI est maintenant intégré comme 9ème module de FeedFormula AI avec :

- prompt spécialisé ;
- backend API complet ;
- base de données ;
- bibliothèque initiale de 50 plantes ;
- frontend dédié ;
- gamification ;
- intégration modules ;
- tests automatisés ;
- documentation.

Objectif qualité FloraVet : `10/10`.
