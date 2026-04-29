# Rapport des tests

## Statut
Tests automatisés préparés, mais non exécutés dans cette session.

## Périmètre couvert
- `GET /sante`
- génération de ration pour :
  - poulet
  - vache
  - tilapia
- test multilingue :
  - `fr`
  - `fon`
  - `en`
- gamification :
  - points
  - niveaux
- auth :
  - inscription
  - OTP
  - token JWT
- prix marché

## Résultats attendus
- Réponses HTTP `200` sur les endpoints principaux
- Présence des champs métier attendus dans les réponses JSON
- Authentification fonctionnelle via OTP
- Calculs de ration exploitables côté frontend

## Résultats observés
- En attente d’exécution de `pytest`

## Remarques
- Les tests ont été préparés pour fonctionner sans appel externe à l’IA, grâce au mocking des dépendances réseau.
- Un lancement de `pytest` est nécessaire pour remplir la section ci-dessous avec les vrais résultats.

## Résultat final après exécution
- À compléter après lancement des tests