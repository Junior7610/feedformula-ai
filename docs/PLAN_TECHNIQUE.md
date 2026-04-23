# PLAN TECHNIQUE — FeedFormula AI (30 jours)

## 1) Objectif du plan
Construire une première version opérationnelle (MVP+) de FeedFormula AI en 30 jours, avec :
- 8 modules connectés
- backend API sécurisé
- front web + mobile utilisables en 3G
- support multilingue via API Afri
- base gamification (Aya, points, niveaux, défis, notifications)

---

## 2) Architecture technique retenue (résumé exécutable)

- **Frontend Web** : React.js + Vite + TypeScript + Tailwind CSS
- **Mobile** : React Native (Expo) + TypeScript
- **Backend** : FastAPI (Python 3.11)
- **Base de données** : PostgreSQL
- **Cache / files d’attente légères** : Redis
- **Stockage fichiers** : Cloudflare R2 (images/audio/documents)
- **Auth** : JWT (access + refresh), hash `bcrypt`
- **IA & agents** : API Afri (`https://build.lewisnote.com/v1`) + orchestration LangChain
- **Observabilité** : Sentry (erreurs), logs structurés JSON
- **Déploiement** :
  - Web: Vercel
  - API: Cloudflare + conteneur (ou VM)
  - DB/Redis: service managé

---

## 3) Technologies exactes par module

## 3.1 Modules métier (8)

### 1) NutriCore — ration optimale
- **Entrées** : espèce, âge, poids, objectif (croissance/ponte), ingrédients disponibles, prix locaux
- **Tech** :
  - FastAPI endpoints (`/nutrition/*`)
  - Moteur calcul Python (pandas + règles métier)
  - Optimisation linéaire (SciPy `linprog` ou OR-Tools)
  - PostgreSQL pour formules/historiques
- **Sorties** : ration journalière, coût, alternatives d’ingrédients

### 2) VetScan — santé photo + voix
- **Entrées** : photo, audio, symptômes texte/voix
- **Tech** :
  - Upload multipart (`python-multipart`, `aiofiles`)
  - Pré-traitement image (`Pillow`)
  - Analyse multimodale via API Afri
  - Règles de triage (urgence / non urgence)
- **Sorties** : suspicion, niveau de risque, protocole premier niveau, recommandation vétérinaire

### 3) ReproTrack — reproduction intelligente
- **Tech** :
  - Calendrier cycles, chaleurs, saillies/inséminations
  - Moteur alertes (J+21/J+45/etc.)
  - Cron jobs (`schedule`) + queue Redis
- **Sorties** : notifications de suivi, prédictions dates clés

### 4) PastureMap — satellite Sentinel-2
- **Tech** :
  - APIs géospatiales (Copernicus/EO Browser/Sentinel Hub selon disponibilité)
  - Indices NDVI/NDWI
  - Cache tuiles/résultats Redis
- **Sorties** : carte pâturage, score biomasse, alertes sécheresse

### 5) FarmManager — registre vocal + finance
- **Tech** :
  - Saisie vocale -> transcription via API Afri
  - Ledger simplifié (dépenses, ventes, mortalité, stock)
  - Génération rapports PDF (`reportlab`)
- **Sorties** : tableaux de bord, marge brute, flux de trésorerie simplifié

### 6) FarmAcademy — micro-formation
- **Tech** :
  - CMS léger (leçons, quiz, niveau)
  - Recommandation leçons (règles + IA)
  - Contenu multilingue via API Afri
- **Sorties** : parcours personnalisé, score d’apprentissage

### 7) FarmCast — vidéo automatique
- **Tech** :
  - Génération scripts (IA)
  - Synthèse voix locale (API Afri voix)
  - Pipeline publication (stockage + métadonnées)
- **Sorties** : capsules 60–120 sec publiées par thème/langue

### 8) FarmCommunity — réseau + marketplace
- **Tech** :
  - Fil d’actualité, commentaires, likes
  - Annonces achat/vente
  - Modération semi-automatique (règles + IA)
- **Sorties** : interactions locales, visibilité marché

## 3.2 Système transversal gamification
- Service dédié `gamification` (points, niveaux, trophées, ligues)
- Événements backend (`event_bus` interne) : `lesson_completed`, `ration_generated`, `daily_login`, etc.
- Récompenses : XP + Graines d’Or + progression Aya

---

## 4) Ordre de développement (30 jours)

## Phase 0 — Préparation (Jour 1 à 3)
- **J1**
  - Initialisation mono-repo, conventions, CI basique
  - Setup FastAPI + React + React Native (Expo)
- **J2**
  - Setup PostgreSQL + Redis + Alembic
  - Modèle utilisateur, auth JWT, rôles
- **J3**
  - Connexion API Afri (wrapper unique), gestion erreurs + timeouts + retries
  - Environnements `.env` (dev/staging/prod)

## Phase 1 — Socle produit (Jour 4 à 10)
- **J4–J5** : NutriCore v1 (calcul ration + coût)
- **J6–J7** : FarmManager v1 (registre + dashboard simple)
- **J8** : Gamification v1 (XP, niveaux, streak)
- **J9** : API notifications (push queue, limite 1/jour)
- **J10** : Intégration front web + mobile (écrans principaux)

## Phase 2 — Santé & Reproduction (Jour 11 à 17)
- **J11–J13** : VetScan v1 (photo + voix + protocole premier niveau)
- **J14–J15** : ReproTrack v1 (calendrier + alertes)
- **J16** : Traduction/réponse vocale multilingue via Afri
- **J17** : Tests E2E parcours “Kofi” (symptômes -> photo -> réponse locale)

## Phase 3 — Contenu, communauté, géospatial (Jour 18 à 24)
- **J18–J19** : FarmAcademy v1 (leçons + quiz)
- **J20–J21** : FarmCommunity v1 (posts + annonces)
- **J22–J23** : PastureMap v1 (NDVI + alertes)
- **J24** : FarmCast v1 (génération script + audio + publication)

## Phase 4 — Durcissement & lancement (Jour 25 à 30)
- **J25** : Sécurité (audit permissions, rate limit, validation uploads)
- **J26** : Optimisation 3G (compression images, lazy loading, cache agressif)
- **J27** : Observabilité (Sentry, logs corrélés, dashboards)
- **J28** : Tests charge + résilience (API Afri indisponible, fallback)
- **J29** : QA final + correction bugs critiques
- **J30** : Déploiement production + checklist go-live + runbook support

---

## 5) Dépendances entre modules

## 5.1 Dépendances critiques
- **Auth** est prérequis pour tous les modules.
- **Service Afri** est prérequis pour :
  - VetScan (voix/texte multilingue)
  - FarmAcademy (contenu localisé)
  - FarmCast (script + voix)
  - Assistant conversationnel global
- **Gamification** dépend des événements émis par tous les modules.
- **FarmCommunity** dépend de la modération IA + règles de sécurité.
- **PastureMap** dépend d’une source satellite stable + cache.

## 5.2 Ordre conseillé de livraison
1. Auth + Socle DB/API  
2. NutriCore + FarmManager  
3. Gamification v1  
4. VetScan + ReproTrack  
5. FarmAcademy + FarmCommunity  
6. PastureMap + FarmCast  
7. Durcissement, optimisation 3G, production

---

## 6) APIs externes nécessaires

## 6.1 API Afri (principale)
- **Base URL** : `https://build.lewisnote.com/v1`
- **Clé** : `AFRI_API_KEY` dans `.env`
- **Usages** :
  - LLM conversationnel
  - Traduction multi-langues africaines
  - STT/TTS (voix locale)
  - Génération de contenus pédagogiques

## 6.2 Géospatial (PastureMap)
- Sentinel-2 via fournisseur API (Sentinel Hub/Copernicus)
- Endpoint NDVI/NDWI + tuiles cartographiques

## 6.3 Notifications push
- Firebase Cloud Messaging (Android prioritaire)
- Option APNs si iOS prioritaire ultérieurement

## 6.4 Stockage objet
- Cloudflare R2 pour médias (photos, audio, vidéos, PDF)

## 6.5 Paiement (offres commerciales)
- Intégrateur mobile money (MTN/Moov/Orange selon pays)
- Webhook de confirmation + anti-replay signature

---

## 7) Risques techniques anticipés et solutions

### Risque 1 — Latence élevée sur réseau 3G
- **Impact** : UX lente, abandon utilisateur
- **Solution** :
  - Payload minimal, compression image/audio
  - Cache local mobile + stratégie offline-first
  - Pagination stricte, timeout court + retry

### Risque 2 — Coût API IA trop élevé
- **Impact** : modèle économique fragile
- **Solution** :
  - Routage intelligent (petites tâches -> modèles moins coûteux)
  - Mise en cache des réponses fréquentes
  - Limites d’usage par offre commerciale

### Risque 3 — Diagnostics santé trop “affirmatifs”
- **Impact** : risque sanitaire/juridique
- **Solution** :
  - Formulation “suspicion” + niveau confiance
  - Message obligatoire “consulter vétérinaire si persistance”
  - Journal d’audit des recommandations

### Risque 4 — Qualité variable des langues locales
- **Impact** : incompréhension utilisateur
- **Solution** :
  - Boucle qualité avec retours utilisateurs
  - Prompts spécialisés par langue/dialecte
  - Glossaires métiers agricoles par langue

### Risque 5 — Sécurité et fuite de données
- **Impact** : perte de confiance, non-conformité
- **Solution** :
  - Chiffrement TLS, hash mot de passe, rotation secrets
  - Contrôle d’accès par rôle
  - Sauvegardes automatiques + PRA/PCA

### Risque 6 — Dépendance fournisseur API unique
- **Impact** : indisponibilité du service
- **Solution** :
  - Circuit breaker + file d’attente
  - Fallback règles locales pour fonctions critiques
  - Abstraction fournisseur dans `ai_provider_service`

### Risque 7 — Complexité de 8 modules en 30 jours
- **Impact** : retards, dette technique
- **Solution** :
  - Prioriser MVP par module (v1 puis v1.1)
  - “Definition of Done” stricte
  - Revue architecture tous les 5 jours

---

## 8) Definition of Done (DoD) par module
Un module est “livré” si :
1. API documentée (`/docs` FastAPI)  
2. Tests unitaires minimum + 1 test intégration  
3. Journalisation + gestion erreurs propre  
4. Écran web et mobile fonctionnel  
5. Événements gamification branchés  
6. Indicateurs de performance mesurés (latence, taux succès)

---

## 9) Indicateurs de succès (fin des 30 jours)
- Temps moyen réponse assistant < 3.5 s (texte), < 6 s (voix)
- Génération ration NutriCore < 2 s
- Taux erreur API global < 2%
- Au moins 1 parcours complet par module validé en QA
- Push `main` stable + déploiement production opérationnel

---

## 10) Prochaine étape immédiate (J+1)
1. Finaliser schéma DB de base (`users`, `farms`, `animals`, `events`, `subscriptions`)  
2. Créer wrapper unique API Afri avec gestion retries/timeouts  
3. Poser les contrats API des modules NutriCore et VetScan  
4. Mettre en place le bus d’événements pour gamification dès le début