# Rapport Branding V2

Date : 17/05/2026 15:16

Sortie : `assets/branding_v2`

Images disponibles : **20/20**

## Diagnostic de génération

L'appel direct à l'API image Afri a retourné `404 Not Found` sur les routes testées :

- `https://build.lewisnote.com/v1/images/generations`
- `https://build.lewisnote.com/v1/image/generations`
- `https://build.lewisnote.com/v1/images/generate`
- `https://build.lewisnote.com/v1/image/generate`

Le SDK compatible OpenAI a également retourné `404 Not Found` sur la base URL actuelle.

## Correction appliquée

Le script `assets/generer_branding_v2_premium.py` a été rendu plus compatible avec cet environnement :

- lecture robuste de `.env`, même si `python-dotenv` ne parse pas une ligne locale ;
- support de `AFRI_BASE_URL`, `AFRI_API_BASE_URL`, `AFRI_IMAGE_BASE_URL`, `OPENAI_BASE_URL` ;
- support de `AFRI_IMAGE_ENDPOINT` si l'environnement Afri utilise une route spécifique ;
- essai de plusieurs chemins image compatibles ;
- fallback automatique via SDK OpenAI ;
- fallback local Pillow si l'API image est indisponible ;
- génération d'un rapport clair.

## Résultat actuel

Les 20 fichiers ont été créés avec le **fallback local Pillow**, car l'endpoint image distant disponible dans cet environnement retourne `404`.

> Pour obtenir les visuels GPT Image 2 réels, définir la bonne route image avec `AFRI_IMAGE_BASE_URL` ou `AFRI_IMAGE_ENDPOINT`, puis relancer : `python assets/generer_branding_v2_premium.py`.

## Fichiers générés

- ✅ `logo_feedformula_v2.png` — 1024x1024 — fallback local
- ✅ `aya_officielle_v2.png` — 1024x1024 — fallback local
- ✅ `aya_celebration_v2.png` — 1024x1024 — fallback local
- ✅ `aya_triste_v2.png` — 1024x1024 — fallback local
- ✅ `aya_urgence_v2.png` — 1024x1024 — fallback local
- ✅ `hero_aviculture_premium.png` — 1792x1024 — fallback local
- ✅ `hero_elevage_bovin_premium.png` — 1792x1024 — fallback local
- ✅ `hero_petits_ruminants_premium.png` — 1792x1024 — fallback local
- ✅ `hero_aquaculture_premium.png` — 1792x1024 — fallback local
- ✅ `hero_porciculture_premium.png` — 1792x1024 — fallback local
- ✅ `hero_cuniculture_premium.png` — 1792x1024 — fallback local
- ✅ `hero_pintades_premium.png` — 1792x1024 — fallback local
- ✅ `hero_multispecies_benin.png` — 1792x1024 — fallback local
- ✅ `splash_screen_v2.png` — 1024x1792 — fallback local
- ✅ `icones_animaux_production.png` — 1024x1024 — fallback local
- ✅ `infographie_nutrition_animale.png` — 1792x1024 — fallback local
- ✅ `carte_impact_benin_v2.png` — 1024x1024 — fallback local
- ✅ `banniere_presentation_investisseurs.png` — 1792x1024 — fallback local
- ✅ `progression_niveaux_eleveur.png` — 1792x512 — fallback local
- ✅ `background_pattern_africain.png` — 1024x1024 — fallback local
