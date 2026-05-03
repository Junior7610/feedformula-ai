# Rapport modules Jour 7 — FeedFormula AI

## Statut global
- Module 1 FarmAcademy : en place, API connectée, catalogue 5 formations / 18 leçons, quiz, progression et certificat PDF.
- Module 2 FarmCast : en place, génération script/audio/images/PDF, historique et partage.
- Module 3 FarmCommunity : en place, posts, commentaires, marketplace et statistiques de base.
- Module 4 Paiement Mobile Money : en place, offres, abonnement, webhook, historique et vérification d'activation.

## Points techniques vérifiés
- `backend/main.py` inclut bien les 4 routers : academy, farmcast, community, paiement.
- `database.py` inclut les nouveaux modèles : `Post`, `Commentaire`, `AnnonceMarche`, `FarmCastContenu`, `TransactionPaiement`.
- `init_db()` est appelé au démarrage.
- CORS est configuré de façon permissive pour le développement.
- Les frontends utilisent désormais `API_BASE` avec fallback sur `http://127.0.0.1:8000`.

## Endpoints attendus

### FarmAcademy
- `GET /academy/formations`
- `GET /academy/formation/{code}`
- `GET /academy/lecon/{code}/{numero}`
- `POST /academy/quiz/soumettre`
- `GET /academy/progression/{user_id}`
- `POST /academy/certification/generer`

### FarmCast
- `POST /farmcast/creer`
- `GET /farmcast/contenus/{user_id}`
- `GET /farmcast/partager/{contenu_id}`

### FarmCommunity
- `GET /community/posts`
- `POST /community/posts`
- `POST /community/posts/{id}/like`
- `POST /community/posts/{id}/commentaire`
- `GET /community/marche`
- `POST /community/marche`
- `PUT /community/marche/{id}/statut`
- `GET /community/marche/{id}`
- `GET /community/stats`

### Paiement
- `POST /paiement/creer`
- `POST /paiement/webhook`
- `GET /paiement/statut/{transaction_id}`
- `GET /paiement/abonnement/{user_id}`
- `GET /paiement/historique/{user_id}`

## Vérification runtime
- Une première validation a révélé un décalage de schéma SQLite sur la base existante (`users.departement` manquant).
- Un helper de migration légère a été ajouté dans `database.py` pour compléter automatiquement les colonnes manquantes sur SQLite existant.
- Les validations runtime doivent être relancées après rechargement complet du backend pour confirmer la migration.

## Remarques
- Les clés API externes ne doivent pas être codées en dur.
- Les secrets doivent rester dans l'environnement (`.env`, variables de déploiement).
- Les frontends sont prêts pour un backend local sur `127.0.0.1:8000` et une URL de production à remplacer au déploiement.
