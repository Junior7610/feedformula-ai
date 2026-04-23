# ARCHITECTURE TECHNIQUE — FeedFormula AI

## 1) Vision d’ensemble

FeedFormula AI est une plateforme **web + mobile + IA** qui permet à un éleveur africain de gérer son élevage en langue locale, même avec une connexion 3G.  
L’architecture repose sur 3 couches principales :

1. **Couche Frontend**  
   - `frontend/` (React.js) pour web
   - `mobile/` (React Native) pour Android/iOS
2. **Couche Backend**  
   - `backend/` (FastAPI) : API métier, auth, orchestration IA, gamification, paiements, notifications
3. **Couche IA / Data**  
   - API Afri (`https://build.lewisnote.com/v1`) pour LLM/multilingue/voix
   - Services IA spécialisés (vision, RAG, scoring, recommandations)
   - PostgreSQL + Redis + stockage fichiers

---

## 2) Architecture logique (macro)

### 2.1 Composants principaux

- **Client Web/Mobile**
  - UI, capture audio/photo/texte
  - cache local minimal (mode réseau instable)
  - gestion offline partielle (file d’attente d’actions)

- **API Gateway FastAPI**
  - point d’entrée unique (`/api/v1`)
  - validation des requêtes
  - auth JWT + contrôle d’accès

- **Services métier (modulaires)**
  - `nutricore_service`
  - `vetscan_service`
  - `reprotrack_service`
  - `pasturemap_service`
  - `farmmanager_service`
  - `farmacademy_service`
  - `farmcast_service`
  - `farmcommunity_service`
  - `gamification_service` (Aya, points, ligues, énergie)

- **Orchestrateur IA**
  - routing des prompts
  - appel API Afri (langues, voix, LLM)
  - garde-fous (santé animale, toxicité, hallucination)
  - fallback quand API externe indisponible

- **Données**
  - PostgreSQL : données métier structurées
  - Redis : sessions, cache, files courtes, rate limit
  - Object storage (S3 compatible) : images, audio, vidéos, PDF

- **Workers asynchrones**
  - génération vidéo FarmCast
  - notifications push
  - traitements image/audio
  - tâches planifiées (marchés, météo, rappels reproduction)

---

## 3) Communication entre les 3 couches (Frontend / Backend / IA)

## 3.1 Frontend → Backend

- Protocole : HTTPS REST (JSON + multipart)
- Auth : Bearer JWT
- Endpoints exemples :
  - `POST /auth/login`
  - `POST /nutricore/ration`
  - `POST /vetscan/analyze` (photo + audio)
  - `GET /market/prices`
  - `POST /gamification/events`

## 3.2 Backend → IA (Afri API)

- Backend envoie :
  - prompt structuré (contexte ferme + langue + module)
  - paramètres modèle (ex: `gpt-5.4` pour raisonnement)
  - éventuels médias (audio/image selon pipeline)
- Backend reçoit :
  - réponse texte structurée
  - variantes langue/voix (si demandées)
  - métadonnées d’usage/token/latence

## 3.3 Backend → Frontend

- Retour standardisé :
  - `status`, `message_localized`, `data`, `actions`, `safety_flags`
- UX critique :
  - réponse claire + action concrète (“isoler l’animal”, “consulter vétérinaire sous 24h”)
  - niveau de confiance + avertissement si diagnostic incertain

---

## 4) Flux complet d’une demande éleveur (exemple VetScan)

1. L’éleveur parle en **fon** et envoie une photo.
2. L’app mobile compresse le média + ajoute contexte (espèce, âge, symptômes).
3. Le backend valide le format, authentifie l’utilisateur, crée un `case_id`.
4. Pipeline IA :
   - transcription audio (si nécessaire)
   - détection langue
   - analyse image (symptômes visuels)
   - prompt clinique encadré (règles vétérinaires)
5. Appel API Afri (LLM) pour synthèse en langue locale.
6. Backend applique les garde-fous :
   - si gravité élevée -> message urgence + escalade vétérinaire
   - si confiance faible -> demande infos complémentaires
7. Réponse renvoyée à l’app :
   - diagnostic de suspicion (pas diagnostic définitif)
   - protocole de premiers soins
   - suivi 24h + alerte communauté si activée
8. Événements gamification créés :
   - “action prévention”, “consultation module santé”
   - points + progression mission quotidienne
9. Données stockées pour historique, audit, amélioration modèle.

---

## 5) Gestion des 50 langues africaines via API Afri

## 5.1 Principe

- Le backend garde une clé `preferred_language` par utilisateur.
- Toute réponse passe par une couche de **localisation IA** :
  - compréhension entrée multilingue
  - génération sortie dans langue cible
  - option voix (TTS) avec style “assistant africain naturel”

## 5.2 Stratégie technique

- Normaliser les intentions en représentation interne (fr/en technique)
- Générer la réponse locale à la fin (langue utilisateur)
- Conserver une version pivot pour audit et support

## 5.3 Risques + solutions

- **Risque :** qualité inégale selon dialectes  
  **Solution :** glossaires métiers par langue + boucle feedback utilisateur.

- **Risque :** ambiguïté de termes zootechniques  
  **Solution :** lexique validé par experts + prompts contraints.

- **Risque :** latence réseau en zone 3G  
  **Solution :** réponses courtes en priorité + mode texte fallback + retry intelligent.

---

## 6) Schéma de base de données (PostgreSQL) pour les 8 modules

## 6.1 Tables transverses (socle)

- `users` (profil, langue, rôle, plan)
- `farms` (exploitations)
- `animals` (lot/individu)
- `subscriptions` (FREE/STANDARD/PREMIUM/VIP/GOLD)
- `media_assets` (photos, audio, vidéos)
- `ai_requests` (traçabilité prompts/réponses)
- `notifications` (push/SMS/in-app)
- `audit_logs` (sécurité et conformité)

## 6.2 NutriCore

- `feed_ingredients` (valeurs nutritionnelles)
- `market_prices` (prix journaliers par marché)
- `ration_requests`
- `ration_results`
- `stock_items` (stock ferme)

## 6.3 VetScan

- `health_cases`
- `symptom_reports`
- `diagnosis_suspicions`
- `treatment_protocols`
- `vet_referrals`

## 6.4 ReproTrack

- `breeding_cycles`
- `inseminations`
- `pregnancy_checks`
- `birth_events`
- `fertility_metrics`

## 6.5 PastureMap

- `pasture_zones`
- `satellite_observations` (Sentinel-2 dérivés)
- `biomass_estimates`
- `grazing_recommendations`

## 6.6 FarmManager

- `farm_journal_entries` (voix/texte)
- `expenses`
- `revenues`
- `cashflow_snapshots`
- `documents` (PDF rapports)

## 6.7 FarmAcademy

- `courses`
- `lessons`
- `lesson_progress`
- `quiz_attempts`
- `certificates`

## 6.8 FarmCast

- `content_topics`
- `generated_scripts`
- `generated_videos`
- `publishing_channels`
- `content_metrics`

## 6.9 FarmCommunity

- `communities`
- `community_members`
- `posts`
- `comments`
- `marketplace_listings`
- `transactions`

---

## 7) Intégration d’Aya et de la gamification dans le backend

## 7.1 Service gamification

`gamification_service` écoute des événements métier :

- ration créée
- cas santé traité
- cours terminé
- défi quotidien validé
- interaction communautaire utile

## 7.2 Mécanismes stockés

- `xp_events`
- `user_levels`
- `trophies`
- `user_trophies`
- `leagues`
- `league_rankings`
- `golden_seeds_wallet`
- `solar_energy_state`
- `missions` / `mission_completions`

## 7.3 Aya (mascotte)

Aya est pilotée par un moteur d’états :

- **états** : neutre, contente, encourage, alerte, félicite
- **déclencheurs** : streak, échec répété, montée de niveau, mission réussie
- **canal** : message texte + voix + animation UI

## 7.4 Règles backend importantes

- anti-fraude points (idempotence des événements)
- plafonds journaliers
- recalcul périodique des classements
- contrôle d’équité inter-ligues

---

## 8) Sécurité : points critiques à respecter

## 8.1 Identité & accès

- JWT court + refresh token sécurisé
- rôles (`farmer`, `vet`, `admin`, `coach`)
- RBAC strict sur toutes les routes

## 8.2 Protection des données

- TLS partout (client↔backend, backend↔APIs externes)
- chiffrement au repos (DB + stockage médias)
- secrets dans variables d’environnement (`.env`), jamais dans le code
- rotation régulière des clés API (dont `AFRI_API_KEY`)

## 8.3 Sécurité applicative

- validation stricte entrée (Pydantic)
- antivirus/scan basique fichiers uploadés
- limitation taille audio/image
- rate limiting par IP + utilisateur (Redis)
- journalisation sécurité (tentatives login, accès refusés)

## 8.4 Sécurité IA

- filtrage prompts (prompt injection)
- règles de sortie pour santé animale (ne pas donner d’acte vétérinaire invasif)
- mention claire “aide à la décision” quand nécessaire
- escalade humaine en cas critique

## 8.5 Conformité & gouvernance

- politique de conservation des données
- consentement explicite pour audio/photo
- anonymisation pour analytics
- audit trail complet des décisions automatiques sensibles

---

## 9) Résilience, performance, observabilité

## 9.1 Résilience

- retries exponentiels sur API externes
- circuit breaker pour Afri API
- files de reprise pour tâches asynchrones
- mode dégradé : réponse locale minimale si IA indisponible

## 9.2 Performance

- cache Redis pour prix marchés/météo/contenus fréquents
- pagination systématique (posts, historique)
- compression média côté mobile avant upload
- index DB sur tables volumineuses

## 9.3 Observabilité

- logs structurés (JSON)
- métriques : latence, taux erreur, coût token IA
- traces distribuées (requête end-to-end)
- alertes temps réel sur erreurs critiques

---

## 10) Problèmes potentiels anticipés + solutions

1. **Connexion instable en zone rurale**  
   Solution : mode offline partiel + synchronisation différée + payload léger.

2. **Coût IA élevé à grande échelle**  
   Solution : cache des réponses fréquentes, modèles adaptés par cas d’usage, quotas par offre commerciale.

3. **Qualité variable des images (téléphones entrée de gamme)**  
   Solution : guide visuel de prise photo + prétraitement + seuil de confiance.

4. **Risque médical/vétérinaire mal interprété**  
   Solution : protocoles validés experts, wording prudent, bouton “contacter vétérinaire”.

5. **Fraude gamification**  
   Solution : détection d’anomalies, règles anti-spam, vérification croisée d’événements.

6. **Montée en charge communautaire**  
   Solution : séparation lecture/écriture progressive, cache agressif, workers dédiés.

---

## 11) Conclusion

Cette architecture est conçue pour être :

- **pratique** pour l’éleveur (mobile, voix, langue locale),
- **robuste** techniquement (FastAPI + PostgreSQL + Redis + workers),
- **évolutive** pour couvrir les 8 modules,
- **responsable** sur la sécurité et l’aide à la décision IA.

Elle permet de livrer rapidement une V1 utile, puis d’industrialiser progressivement vers une plateforme panafricaine fiable et multilingue.