# RAPPORT TESTS CI STRICT — FeedFormula AI

## Objectif

Mettre en place une suite **CI stricte** stable et reproductible pour valider les endpoints critiques de FeedFormula AI sans dépendre des APIs externes.

## Fichiers ajoutés

- `tests/test_ci_strict.py`
- `.github/workflows/tests.yml`

## Portée couverte (CI stricte)

- Santé plateforme: `/sante`
- Données de base: `/langues`, `/marche/prix`
- NutriCore: `/generer-ration`
- VetScan: `/vetscan/diagnostiquer`
- ReproTrack: `/reprotrack/evenement`
- PastureMap: `/pasturemap/analyser`
- FarmManager: `/farmmanager/evenement`
- FarmAcademy: `/academy/formations`, `/academy/formation/{code}`, `/academy/lecon/{formation}/{n}`, `/academy/quiz/soumettre`
- Community: `/community/posts`
- Gamification: `/gamification/action`, `/gamification/defi/completer`
- Paiement: `/paiement/creer`
- Notifications: `/notifications/du-jour/{user_id}`
- Audio: `/audio/synthese`
- Auth (flow complet): inscription + OTP + token

## Stratégie technique

- Utilisation de `fastapi.testclient.TestClient`.
- Isolation des appels externes via monkeypatch (client IA et VetScan).
- Assertions strictes sur:
  - codes HTTP,
  - présence des clés contractuelles,
  - types/présence des données critiques.
- Tolérance explicite pour le défi gamification (`200` ou `409` si déjà complété).

## Exécution locale

```feedformula-ai/docs/RAPPORT_TESTS_CI_STRICT.md#L1-3
pytest -q tests/test_ci_strict.py --maxfail=1 --disable-warnings
```

## Exécution GitHub Actions

Le workflow `.github/workflows/tests.yml` exécute automatiquement la suite sur `push`, `pull_request` et `workflow_dispatch`, puis publie un artefact JUnit:

- `docs/junit-test-ci-strict.xml`

## Critère de validation CI

La CI est verte si:

- tous les tests de `tests/test_ci_strict.py` passent,
- aucun endpoint critique ne régresse sur son contrat principal.
