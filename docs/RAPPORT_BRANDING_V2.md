# Rapport Branding V2

Date : 17/05/2026 19:38

Sortie : `assets/branding_v2`

Images disponibles : **20/20**

## Correction demandée appliquée

Le script `assets/generer_branding_v2_premium.py` a été mis à jour selon la documentation officielle fournie :

- Endpoint strict : `POST https://build.lewisnote.com/v1/images/generations`
- Modèle : `gpt-image-2`
- Qualité : `high`
- Body JSON strict :

```json
{
  "model": "gpt-image-2",
  "prompt": "...",
  "size": "...",
  "quality": "high"
}
```

## Tailles corrigées

- `1792x1024` → `1536x1024`
- `1024x1792` → `1024x1536`
- `1792x512` → `1280x720`

## Résultat d'exécution

L'exécution du script avec l'endpoint officiel a encore retourné `404 Not Found` pour chaque appel API image dans cet environnement.

Pour éviter de bloquer le workflow et garder les fichiers disponibles, le script a utilisé son fallback local Pillow. Les fichiers ci-dessous sont donc **présents**, aux **tailles corrigées**, mais ils ne sont pas des images GPT Image 2 réelles tant que l'endpoint image distant retourne `404`.

Pour forcer un échec strict sans fallback :

```bash
FEEDFORMULA_BRANDING_LOCAL_FALLBACK=0 python assets/generer_branding_v2_premium.py
```

Pour forcer le fallback local :

```bash
FEEDFORMULA_FORCE_LOCAL_BRANDING=1 python assets/generer_branding_v2_premium.py
```

## Fichiers disponibles

- ✅ `logo_feedformula_v2.png` — 1024x1024 — fallback local
- ✅ `aya_officielle_v2.png` — 1024x1024 — fallback local
- ✅ `aya_celebration_v2.png` — 1024x1024 — fallback local
- ✅ `aya_triste_v2.png` — 1024x1024 — fallback local
- ✅ `aya_urgence_v2.png` — 1024x1024 — fallback local
- ✅ `hero_aviculture_premium.png` — 1536x1024 — fallback local
- ✅ `hero_elevage_bovin_premium.png` — 1536x1024 — fallback local
- ✅ `hero_petits_ruminants_premium.png` — 1536x1024 — fallback local
- ✅ `hero_aquaculture_premium.png` — 1536x1024 — fallback local
- ✅ `hero_porciculture_premium.png` — 1536x1024 — fallback local
- ✅ `hero_cuniculture_premium.png` — 1536x1024 — fallback local
- ✅ `hero_pintades_premium.png` — 1536x1024 — fallback local
- ✅ `hero_multispecies_benin.png` — 1536x1024 — fallback local
- ✅ `splash_screen_v2.png` — 1024x1536 — fallback local
- ✅ `icones_animaux_production.png` — 1024x1024 — fallback local
- ✅ `infographie_nutrition_animale.png` — 1536x1024 — fallback local
- ✅ `carte_impact_benin_v2.png` — 1024x1024 — fallback local
- ✅ `banniere_presentation_investisseurs.png` — 1536x1024 — fallback local
- ✅ `progression_niveaux_eleveur.png` — 1280x720 — fallback local
- ✅ `background_pattern_africain.png` — 1024x1024 — fallback local
