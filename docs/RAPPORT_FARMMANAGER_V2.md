# RAPPORT FARMMANAGER V2 — Deuxième cerveau de ferme

## Résumé exécutif

FarmManager V2 transforme le module FarmManager en système de gestion technico-économique complet pour une ferme africaine. L’objectif implémenté est clair : le propriétaire ne doit plus être surpris par les événements de sa ferme. Le module centralise la mémoire opérationnelle, les alertes, les registres animaux, les lots, la santé, l’alimentation, les finances, le planning, les ressources humaines et l’intelligence prédictive.

Le backend expose désormais une API FarmManager complète via le routeur `/farmmanager`, déjà inclus dans `backend/main.py`. Le frontend `frontend/farmmanager.html` a été refondu en interface à 6 onglets avec zone vocale persistante. Le prompt système dédié a été réécrit pour positionner FarmManager AI comme deuxième cerveau de l’éleveur.

## Fichiers modifiés ou créés

- `prompts/system_prompt_farmmanager.txt`
- `backend/farmmanager_service.py`
- `frontend/farmmanager.html`
- `tests/test_farmmanager_complet.py`
- `docs/RAPPORT_FARMMANAGER_V2.md`

## 1. Refonte du prompt système FarmManager

Le fichier `prompts/system_prompt_farmmanager.txt` définit maintenant FarmManager AI comme deuxième cerveau du propriétaire de ferme africain avec 4 expertises simultanées :

1. Expert zootechnicien
2. Assistant personnel agricole
3. Analyste financier agricole
4. Planificateur stratégique

Le prompt couvre aussi :

- catégorisation automatique des événements vocaux ;
- extraction de données même approximatives ;
- analyse et conseil après enregistrement ;
- mises à jour en cascade ;
- règles de fiabilité et de sécurité sanitaire ;
- format JSON strict attendu par l’API ;
- format de briefing quotidien.

## 2. Refonte backend complète

Le fichier `backend/farmmanager_service.py` a été réécrit pour structurer FarmManager en 8 catégories fonctionnelles.

### Catégorie 1 — Registre animal complet

Classe : `RegistreAnimal`

Fonctions implémentées :

- `ajouter_animal`
- `modifier_animal`
- `supprimer_animal`
- `get_animal`
- `get_tous_animaux`
- `get_animaux_par_lot`
- `get_animaux_par_statut`
- `enregistrer_pesee`
- `transferer_lot`

Fonctionnalités :

- fiche animal complète ;
- âge calculé automatiquement ;
- historique de pesées ;
- calcul GMQ depuis dernière pesée ;
- calcul GMQ cumulé ;
- comparaison à un objectif de production ;
- recommandation si croissance insuffisante ;
- transfert entre lots avec historique et notification.

### Catégorie 2 — Gestion lots et bâtiments

Classe : `GestionLots`

Fonctions implémentées :

- `creer_lot`
- `get_tableau_bord_lot`
- `projeter_vente_lot`
- `alertes_lot`

Fonctionnalités :

- fiche lot complète ;
- effectif actuel calculé ;
- mortalité cumulée et taux de mortalité ;
- âge moyen ;
- poids moyen ;
- consommation alimentaire journalière estimée ;
- indice de consommation ;
- stade de production ;
- projection de vente ;
- alertes lot : mortalité, indice de consommation, vente approchante.

### Catégorie 3 — Gestion sanitaire complète

Classe : `GestionSanitaire`

Fonctions implémentées :

- `generer_programme_sanitaire`
- `enregistrer_traitement`
- `verifier_delai_attente`
- `rapport_sanitaire_mensuel`

Fonctionnalités :

- programme vaccinal automatique ;
- exemple poulet de chair : Marek, Newcastle, Bronchite, Gumboro ;
- enregistrement traitement ;
- coût sanitaire ;
- rappels de suivi ;
- délai d’attente ;
- alerte si vente interdite ;
- rapport sanitaire mensuel.

### Catégorie 4 — Gestion alimentaire intelligente

Classe : `GestionAlimentaire`

Fonctions implémentées :

- `enregistrer_entree_stock`
- `enregistrer_consommation`
- `get_stock_critique`
- `commander_automatiquement`
- `optimiser_cout_alimentaire`

Fonctionnalités :

- suivi stock par ingrédient ;
- valeur stock FCFA ;
- seuil d’alerte ;
- jours restants ;
- date d’épuisement estimée ;
- bon de commande automatique ;
- estimation quantité optimale ;
- suggestions d’optimisation alimentaire.

### Catégorie 5 — Analyse financière complète

Classe : `AnalyseFinanciere`

Fonctions implémentées :

- `tableau_bord_financier`
- `cout_de_revient_par_animal`
- `seuil_de_rentabilite`
- `analyse_par_espece`
- `projection_annuelle`
- `identifier_pertes_cachees`

Fonctionnalités :

- revenus par catégorie ;
- dépenses par catégorie ;
- total revenus ;
- total dépenses ;
- marge brute ;
- marge nette ;
- taux de rentabilité ;
- coût de revient par animal ;
- seuil de rentabilité ;
- projection annuelle pessimiste/réaliste/optimiste ;
- pertes cachées chiffrées.

### Catégorie 6 — Planification et agenda intelligent

Classe : `PlanificationIntellligente`

Fonctions implémentées :

- `generer_planning_semaine`
- `planifier_cycle_production`
- `optimiser_planning_multi_lots`

Fonctionnalités :

- planning semaine sur 7 jours ;
- tâches matin, contrôle, collecte ;
- tâches sanitaires incluses ;
- plan de cycle de production ;
- budget prévisionnel ;
- projection de rentabilité ;
- risques et mitigations ;
- optimisation multi-lots.

### Catégorie 7 — Gestion RH

Classe : `GestionRH`

Fonctions implémentées :

- `assigner_tache`
- `tableau_bord_technicien`
- `rapport_performance_equipe`

Fonctionnalités :

- assignation de tâches ;
- priorités ;
- ressources nécessaires ;
- critères de validation ;
- vue technicien ;
- rapport performance équipe.

### Catégorie 8 — IA prédictive

Classe : `IAPredicitve`

Fonctions implémentées :

- `predire_mortalite`
- `predire_performance_lot`
- `detecter_anomalies`
- `conseil_quotidien_ia`

Fonctionnalités :

- risque de mortalité ;
- facteurs de risque ;
- actions préventives ;
- prédiction de performance lot ;
- anomalies quotidiennes ;
- conseil/briefing quotidien IA.

## 3. Intelligence événement vocal

Endpoint principal : `POST /farmmanager/evenement`

Le body attendu est :

- `texte`
- `user_id`
- `langue`

Le traitement inclut :

1. catégorisation automatique ;
2. extraction animal, lot, espèce, quantité, prix, montant ;
3. calcul coût/revenu ;
4. génération d’alertes ;
5. génération de rappels ;
6. mise à jour logique des registres ;
7. retour confirmation + conseil + points.

Catégories reconnues :

- `sanitaire`
- `financier`
- `alimentaire_stock`
- `registre_animal`
- `planning`
- `ressources_humaines`
- `ia_predictive`
- `autre`

Le service utilise GPT 5.5 si disponible et bascule automatiquement vers un moteur local déterministe si l’API IA est absente ou indisponible. En environnement `test`, le fallback local est forcé pour garantir des tests rapides et reproductibles.

## 4. Endpoints API FarmManager V2

### Registre animal

- `POST /farmmanager/animaux/ajouter`
- `PUT /farmmanager/animaux/{id}/modifier`
- `DELETE /farmmanager/animaux/{id}/supprimer`
- `GET /farmmanager/animaux/{user_id}/tous`
- `GET /farmmanager/animaux/{user_id}/lot/{lot}`
- `POST /farmmanager/animaux/{id}/pesee`
- `POST /farmmanager/animaux/{id}/transferer`

### Gestion lots

- `POST /farmmanager/lots/creer`
- `GET /farmmanager/lots/{user_id}/tous`
- `GET /farmmanager/lots/{id}/tableau-bord`
- `GET /farmmanager/lots/{id}/projection-vente`
- `GET /farmmanager/lots/{id}/alertes`

### Sanitaire

- `POST /farmmanager/sanitaire/programme`
- `POST /farmmanager/sanitaire/traitement`
- `GET /farmmanager/sanitaire/delais-attente/{user_id}`
- `GET /farmmanager/sanitaire/rapport/{user_id}`

### Alimentaire / stocks

- `POST /farmmanager/stocks/entree`
- `POST /farmmanager/stocks/consommation`
- `GET /farmmanager/stocks/critiques/{user_id}`
- `GET /farmmanager/stocks/optimisation/{user_id}`
- `GET /farmmanager/stocks/commander/{user_id}/{ingredient}`

### Financier

- `GET /farmmanager/finances/tableau-bord/{user_id}`
- `GET /farmmanager/finances/cout-revient/{lot_id}`
- `GET /farmmanager/finances/seuil-rentabilite/{lot_id}`
- `GET /farmmanager/finances/analyse-espece/{user_id}`
- `GET /farmmanager/finances/projection-annuelle/{user_id}`
- `GET /farmmanager/finances/pertes-cachees/{user_id}`

### Planning

- `GET /farmmanager/planning/semaine/{user_id}`
- `POST /farmmanager/planning/cycle-production`
- `GET /farmmanager/planning/optimisation/{user_id}`

### RH

- `POST /farmmanager/rh/assigner-tache`
- `GET /farmmanager/rh/tableau-bord/{technicien_id}`
- `GET /farmmanager/rh/rapport-performance/{user_id}`

### IA prédictive

- `GET /farmmanager/ia/briefing-quotidien/{user_id}`
- `GET /farmmanager/ia/prediction-mortalite/{lot_id}`
- `GET /farmmanager/ia/prediction-lot/{lot_id}`
- `GET /farmmanager/ia/anomalies/{user_id}`
- `GET /farmmanager/ia/conseil-quotidien/{user_id}`

### Compatibilité ancienne interface

- `POST /farmmanager/evenement-vocal`
- `GET /farmmanager/evenements/{user_id}`
- `GET /farmmanager/calendrier/{user_id}`
- `GET /farmmanager/stats/{user_id}`
- `GET /farmmanager/finances/{user_id}`
- `GET /farmmanager/rapport-mensuel/{user_id}`
- `POST /farmmanager/rapport-mensuel`

## 5. Refonte frontend FarmManager

Le fichier `frontend/farmmanager.html` a été complètement reconstruit en interface moderne à 6 onglets principaux.

### Onglet 1 — Tableau de bord

- briefing IA au chargement ;
- alertes critiques en rouge ;
- 5 métriques clés : animaux actifs, revenus, dépenses, marge nette, prochaine tâche urgente ;
- lots en cours ;
- priorités du jour.

### Onglet 2 — Mes animaux

- sous-onglets visuels ;
- filtres espèce, lot, bâtiment, statut, alerte ;
- cards animales avec statut vert/orange/rouge ;
- bouton détails ;
- bouton enregistrer événement.

### Onglet 3 — Finances

- résumé financier ;
- revenus ;
- dépenses ;
- analyse ;
- graphique Chart.js ;
- bouton transaction vocale.

### Onglet 4 — Planning

- vue semaine ;
- tâches urgentes et planifiées ;
- génération IA ;
- assignation technicien ;
- vue mois simplifiée.

### Onglet 5 — Stocks

- barres de niveau ;
- alertes rouges ;
- historique ;
- commande automatique ;
- livraison vocale.

### Onglet 6 — Rapports

- rapport mensuel ;
- rapport sanitaire ;
- rapport financier ;
- rapport performance lots ;
- rapport techniciens ;
- téléchargement PDF ;
- partage WhatsApp.

### Zone vocale persistante

Une zone micro reste visible en bas de l’écran sur tous les onglets :

- bouton micro ;
- textarea avec placeholder : « Dites ce qui s’est passé sur la ferme... » ;
- bouton enregistrer ;
- confirmation ;
- attribution de points.

## 6. Tests qualité FarmManager

Fichier créé : `tests/test_farmmanager_complet.py`

Tests implémentés :

1. briefing quotidien ;
2. 20 événements vocaux couvrant toutes les catégories principales ;
3. tableau de bord financier ;
4. planning semaine généré ;
5. détection anomalies IA + score FarmManager.

Résultat exécuté :

- `5 passed in 34.79s`
- Score affiché : `10/10`

## 7. Architecture de persistance

Pour éviter une migration lourde, la V2 utilise `UserActionLog` comme journal métier générique. Chaque domaine est persisté via un préfixe d’action :

- `farmmanager_event`
- `farmmanager_animal`
- `farmmanager_lot`
- `farmmanager_sanitaire`
- `farmmanager_stock`
- `farmmanager_consommation`
- `farmmanager_rh_task`

Ce choix permet :

- compatibilité avec la base existante ;
- déploiement rapide ;
- historisation complète ;
- extensibilité future vers des tables dédiées.

## 8. Résultat final

FarmManager V2 dispose maintenant des fondations d’un véritable deuxième cerveau de ferme :

- mémoire opérationnelle ;
- analyse financière ;
- alertes sanitaires ;
- suivi animal et lot ;
- gestion stock ;
- planning intelligent ;
- RH terrain ;
- prédiction et briefing quotidien ;
- interface vocale persistante ;
- tests automatisés validés.

Objectif qualité FarmManager : `10/10`.
