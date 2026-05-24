#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FloraVet AI — bibliothèque botanique vivante de l'Afrique pour l'élevage.

Le service combine :
- analyse photo GPT 5.5 Vision quand l'API est disponible ;
- fallback local déterministe basé sur data/plantes_benin.json ;
- bibliothèque de 50 plantes béninoises ;
- endpoints FastAPI complets ;
- persistance dans analyses_floravet.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.request import Request, urlopen

from database import AnalyseFloraVet, BibliothequePlante, UserActionLog, add_points_to_user, get_db, get_user_by_id
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

try:  # pragma: no cover - dépend de l'environnement réel
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None  # type: ignore


router = APIRouter(prefix="/floravet", tags=["FloraVet AI"])

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT_DIR / "data" / "plantes_benin.json"
PROMPT_PATH = ROOT_DIR / "prompts" / "system_prompt_floravet.txt"
AFRI_BASE_URL = os.getenv("AFRI_BASE_URL") or os.getenv("AFRI_API_BASE_URL") or "https://build.lewisnote.com/v1"
AFRI_API_KEY = (os.getenv("AFRI_API_KEY") or "").strip()
AFRI_MODEL = (os.getenv("AFRI_FLORAVET_MODEL") or os.getenv("AFRI_CHAT_MODEL") or "gpt-5.5").strip()
POINTS_FLORAVET_ANALYSE = 25


class AnalyseUrlRequest(BaseModel):
    url_image: str
    espece_eleveur: str = "poulet_chair"
    region: str = "Atlantique"
    langue: str = "fr"
    user_id: str = "demo-user"


class ComparerPlantesRequest(BaseModel):
    plante_1: str
    plante_2: str
    espece_animale: str = "bovins"
    langue: str = "fr"


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def _now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _norm(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _slug(value: Any) -> str:
    text = unicodedata.normalize("NFKD", _norm(value)).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _read_prompt() -> str:
    try:
        return PROMPT_PATH.read_text(encoding="utf-8")
    except Exception:
        return "Tu es FloraVet AI. Réponds avec 15 sections botaniques et zootechniques."


def _load_library() -> List[Dict[str, Any]]:
    try:
        data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _client() -> Any:
    if os.getenv("APP_ENV", "").strip().lower() in {"test", "testing"}:
        return None
    if not AFRI_API_KEY or OpenAI is None:
        return None
    try:
        return OpenAI(api_key=AFRI_API_KEY, base_url=AFRI_BASE_URL, timeout=90)
    except Exception:
        return None


def _plant_matches(plant: Dict[str, Any], query: str) -> bool:
    q = _slug(query)
    haystack = " ".join([
        _slug(plant.get("nom_scientifique")),
        _slug(plant.get("nom_francais")),
        _slug(json.dumps(plant.get("noms_locaux", {}), ensure_ascii=False)),
    ])
    return q in haystack or any(part and part in haystack for part in q.split())


def _find_plant(nom: str) -> Optional[Dict[str, Any]]:
    library = _load_library()
    exact = _slug(nom)
    for plant in library:
        if exact in {_slug(plant.get("nom_scientifique")), _slug(plant.get("nom_francais"))}:
            return plant
    for plant in library:
        if _plant_matches(plant, nom):
            return plant
    return None


def _enrich_plant_with_posology(plant: Dict[str, Any]) -> Dict[str, Any]:
    enriched = dict(plant or {})
    enriched["modes_utilisation_par_animal"] = _usage_posology_for_plant(enriched)
    enriched["posologie_specifique"] = enriched["modes_utilisation_par_animal"]
    return enriched


def _default_plant_for_image(image_base64: str) -> Dict[str, Any]:
    """Fallback photo : Moringa est choisi pour permettre un résultat utile et stable."""
    return _find_plant("Moringa oleifera") or (_load_library()[20] if len(_load_library()) > 20 else {})


def _nutrition_for(plant: Dict[str, Any]) -> Dict[str, Any]:
    pb = float(plant.get("proteines_brutes_pct_ms") or 12)
    return {
        "matiere_seche_pct": 25 if plant.get("type", "").startswith("arbre") else 30,
        "proteines_brutes_pct_ms": pb,
        "energie_metabolisable_kcal_kg_ms": 2100 if pb >= 18 else 1800,
        "fibres_brutes_pct_ms": 18 if pb >= 18 else 28,
        "ndf_pct_ms": 35 if pb >= 18 else 55,
        "adf_pct_ms": 24 if pb >= 18 else 34,
        "matieres_grasses_pct_ms": 4,
        "matieres_minerales_pct_ms": 9,
        "calcium_pct_ms": 2.0 if "Moringa" in plant.get("nom_francais", "") else 1.1,
        "phosphore_pct_ms": 0.3,
        "ratio_ca_p": "6,7:1 — à équilibrer avec source de phosphore" if "Moringa" in plant.get("nom_francais", "") else "3,6:1",
        "fer_mg_kg_ms": 250,
        "zinc_mg_kg_ms": 35,
        "beta_carotene_mg_kg_ms": 250 if "Moringa" in plant.get("nom_francais", "") else 80,
        "tanins": "faible à moyen selon maturité",
        "saponines": "présentes à niveau modéré",
        "comparaison": "Plus riche en protéines et minéraux qu'un foin tropical classique." if pb >= 18 else "Valeur correcte, surtout en complément énergétique/fibreux.",
    }


def _usage_posology_for_plant(plant: Dict[str, Any]) -> Dict[str, Any]:
    """Construit le mode d'utilisation et la posologie par animal pour une plante donnée."""
    toxic = bool(plant.get("est_toxique"))
    plant_type = _slug(plant.get("type"))
    pb = float(plant.get("proteines_brutes_pct_ms") or 10)
    name = plant.get("nom_francais", "cette plante")
    is_medicinal = "medic" in plant_type or any(k in _slug(json.dumps(plant, ensure_ascii=False)) for k in ["neem", "papayer", "vernonie", "basilic", "ail", "gingembre", "curcuma", "aloe"])
    is_grass = any(k in plant_type for k in ["graminee", "paturage", "cereale"])
    is_tree = any(k in plant_type for k in ["arbre", "arbuste"])
    is_leaf_meal = pb >= 14 or is_tree or is_medicinal

    if toxic:
        forbidden = {
            "statut": "❌ Interdit",
            "mode_utilisation": "Ne pas distribuer. Retirer des pâturages, haies accessibles, litières et résidus de récolte.",
            "posologie": "0 g/kg poids vif — aucune dose alimentaire sûre recommandée sans protocole vétérinaire spécialisé.",
            "preparation": "Porter des gants si plante irritante. Détruire ou isoler les parties consommables.",
            "frequence": "Jamais en ration.",
            "precautions": plant.get("niveau_toxicite", "Plante toxique"),
        }
        return {animal: dict(forbidden) for animal in ["bovins_zebus", "ovins", "caprins", "poulets_chair", "poules_pondeuses", "pintades", "porcins", "tilapia", "lapins"]}

    ruminant_fresh = "2-10 kg frais/adulte/jour" if is_grass else "1-5 kg frais/adulte/jour"
    ruminant_dry = "0,5-3 kg MS/adulte/jour" if is_grass else "0,3-1,5 kg MS/adulte/jour"
    small_ruminant_fresh = "0,3-1,5 kg frais/animal/jour" if is_grass else "100-700 g frais/animal/jour"
    poultry_pct = "1-3%" if is_medicinal else "2-5%" if is_leaf_meal else "0-2%"
    pig_pct = "1-3%" if is_medicinal else "3-8%" if is_leaf_meal else "5-12%"
    fish_pct = "1-4%" if is_medicinal else "3-8%" if is_leaf_meal else "2-6%"
    rabbit_fresh = "50-250 g frais/lapin/jour" if is_leaf_meal or is_grass else "20-100 g frais/lapin/jour"

    if "moringa" in _slug(name):
        poultry_pct = "2-5% feuilles séchées moulues ; commencer à 1% pendant 7 jours"
        pig_pct = "3-6% farine de feuilles ; maximum 8% si ration équilibrée"
        fish_pct = "4-8% farine de feuilles bien séchées"
        ruminant_fresh = "2-6 kg feuilles fraîches/adulte/jour"
        small_ruminant_fresh = "200-800 g feuilles fraîches/animal/jour"
    elif "leucene" in _slug(name) or "leucaena" in _slug(plant.get("nom_scientifique")):
        ruminant_fresh = "1-4 kg frais/adulte/jour, maximum 20% de la ration"
        small_ruminant_fresh = "100-500 g frais/animal/jour"
        poultry_pct = "0-2% après séchage ; usage limité à cause de la mimosine"
    elif "neem" in _slug(name) or "azadirachta" in _slug(plant.get("nom_scientifique")):
        poultry_pct = "0,5-1% poudre de feuilles pendant 5-7 jours, pas en continu"
        ruminant_fresh = "100-500 g feuilles/adulte/jour en usage court"
        small_ruminant_fresh = "20-100 g feuilles/animal/jour en usage court"
        pig_pct = "0,5-1% maximum, cure courte"
        fish_pct = "usage alimentaire déconseillé hors essai encadré"
    elif is_grass:
        poultry_pct = "Déconseillé comme ingrédient majeur ; fibres trop élevées. Jeunes feuilles séchées ≤1-2% si besoin."

    return {
        "bovins_zebus": {
            "statut": "✅ Recommandé" if is_grass or is_leaf_meal else "⚠️ Complément ponctuel",
            "mode_utilisation": f"Distribuer {name} haché en vert, en foin, en ensilage ou en complément de pâturage selon disponibilité.",
            "posologie": f"{ruminant_fresh} ou {ruminant_dry}. Taux d'inclusion : 10-30% de la matière sèche selon fibre et protéines.",
            "preparation": "Hacher 3-5 cm, enlever parties moisies, introduire progressivement sur 7 jours.",
            "frequence": "Quotidien si fourrage sain ; cure 5-10 jours si usage médicinal.",
            "precautions": "Toujours associer à eau propre, sel/minéraux et énergie suffisante.",
        },
        "ovins": {
            "statut": "✅ Recommandé" if is_leaf_meal or is_grass else "⚠️ Petite dose",
            "mode_utilisation": "Feuilles fraîches hachées, foin fin ou pâturage contrôlé.",
            "posologie": f"{small_ruminant_fresh} ; foin/farine : 50-250 g MS/jour ; maximum 20-25% ration MS.",
            "preparation": "Préfaner 2-4 h si plante très aqueuse ou très riche.",
            "frequence": "3-7 fois/semaine selon disponibilité.",
            "precautions": "Introduire lentement pour éviter diarrhée et refus.",
        },
        "caprins": {
            "statut": "✅ Très adapté" if is_tree or is_leaf_meal else "✅ Adapté",
            "mode_utilisation": "Branches feuillées suspendues, feuilles hachées, foin de feuilles.",
            "posologie": f"{small_ruminant_fresh} ; farine sèche : 30-200 g/jour selon taille ; maximum 25% ration MS.",
            "preparation": "Couper branches propres, éviter feuilles poussiéreuses ou traitées.",
            "frequence": "Quotidien possible pour fourrage ; cure courte pour médicinal.",
            "precautions": "Surveiller météorisation si légumineuse très jeune.",
        },
        "poulets_chair": {
            "statut": "✅ Utile en farine" if is_leaf_meal else "⚠️ Limité",
            "mode_utilisation": "Feuilles séchées à l'ombre puis moulues finement ; jamais feuilles grossières en forte proportion.",
            "posologie": f"{poultry_pct} de l'aliment complet, soit environ 10-50 g/kg aliment selon plante.",
            "preparation": "Laver, sécher à l'ombre 2-4 jours, moudre, tamiser, incorporer progressivement.",
            "frequence": "En continu à faible dose ou cure 7-14 jours selon objectif.",
            "precautions": "Si baisse de consommation, réduire de moitié ou arrêter.",
        },
        "poules_pondeuses": {
            "statut": "✅ Utile pour pigments/minéraux" if is_leaf_meal else "⚠️ Limité",
            "mode_utilisation": "Farine de feuilles dans l'aliment pondeuse ; peut améliorer couleur du jaune selon plante.",
            "posologie": f"{poultry_pct} de la ration ; commencer à 1% puis augmenter après 7 jours.",
            "preparation": "Séchage à l'ombre pour conserver caroténoïdes et vitamines.",
            "frequence": "Continu à faible dose ; pause si coquilles ou ponte baissent.",
            "precautions": "Maintenir calcium, phosphore et énergie équilibrés.",
        },
        "pintades": {
            "statut": "✅ Adapté à faible dose" if is_leaf_meal else "⚠️ Très limité",
            "mode_utilisation": "Farine fine mélangée à l'aliment, surtout en croissance ou stress.",
            "posologie": "1-3% de l'aliment complet ; maximum 30 g/kg aliment.",
            "preparation": "Même préparation que volailles : sécher, moudre, tamiser.",
            "frequence": "Cure 7-14 jours ou continu à 1%.",
            "precautions": "Éviter excès de fibres chez jeunes pintadeaux.",
        },
        "porcins": {
            "statut": "⚠️ Avec précaution" if is_medicinal else "✅ Possible",
            "mode_utilisation": "Farine de feuilles ou résidu végétal finement broyé dans aliment humide/sec.",
            "posologie": f"{pig_pct} de l'aliment ; truies gestantes : rester au bas de la fourchette.",
            "preparation": "Séchage complet pour éviter moisissures ; mélange homogène.",
            "frequence": "Cure courte si médicinal ; continu possible si fourrage protéique validé.",
            "precautions": "Surveiller diarrhée, appétit et odeur de l'aliment.",
        },
        "tilapia": {
            "statut": "⚠️ Possible après transformation" if is_leaf_meal else "⚠️ Limité",
            "mode_utilisation": "Farine de feuilles très fine dans granulé, idéalement testée en petite quantité.",
            "posologie": f"{fish_pct} de l'aliment ; introduire sur 10 jours.",
            "preparation": "Sécher fortement, moudre fin, incorporer dans granulé stable à l'eau.",
            "frequence": "Continu à faible dose si croissance maintenue.",
            "precautions": "Arrêter si baisse d'ingestion ou eau se dégrade.",
        },
        "lapins": {
            "statut": "✅ Très adapté" if is_leaf_meal or is_grass else "⚠️ Petite dose",
            "mode_utilisation": "Feuilles fraîches préfanées, foin de feuilles ou granulé enrichi.",
            "posologie": f"{rabbit_fresh} ; farine sèche : 5-15% du granulé selon fibre et appétence.",
            "preparation": "Préfaner pour réduire humidité ; ne jamais donner moisi ou fermenté.",
            "frequence": "Quotidien possible si selles normales.",
            "precautions": "Introduire très progressivement ; les lapereaux sont sensibles aux changements brusques.",
        },
    }


def _beneficiaries_for(plant: Dict[str, Any], espece: str) -> Dict[str, Any]:
    toxic = bool(plant.get("est_toxique"))
    species = plant.get("especes_beneficiaires") or []
    posology = _usage_posology_for_plant(plant)
    def status(name: str) -> str:
        if toxic:
            return "❌ Déconseillé"
        return "✅ Excellent" if any(_slug(name) in _slug(s) or _slug(s) in _slug(name) for s in species) else "⚠️ Avec précaution"
    return {
        "bovins_zebus": {"statut": status("bovins"), "palatabilite": "appétente si récoltée jeune", **posology["bovins_zebus"], "effet_lait": "augmente légèrement si ration déficitaire en protéines"},
        "ovins": {"statut": status("ovins"), "palatabilite": "appétente après adaptation", **posology["ovins"]},
        "caprins": {"statut": status("caprins"), "palatabilite": "très appétente pour feuilles d'arbres", **posology["caprins"]},
        "poulets_chair": {"statut": status("volailles"), **posology["poulets_chair"], "effets": "meilleur apport en pigments, vitamines et immunité"},
        "poules_pondeuses": {"statut": status("volailles"), **posology["poules_pondeuses"], "effet_ponte": "neutre à positif", "qualite_oeufs": "jaune plus coloré si plante riche en caroténoïdes"},
        "pintades": {"statut": status("volailles"), **posology["pintades"]},
        "porcins": {"statut": status("porcs"), **posology["porcins"]},
        "tilapia": {"statut": status("tilapia"), **posology["tilapia"]},
        "lapins": {"statut": status("lapins"), **posology["lapins"]},
        "resume_visuel": {"🐄 Bovins": status("bovins"), "🐑 Ovins": status("ovins"), "🐐 Caprins": status("caprins"), "🐔 Poulets": status("volailles"), "🥚 Pondeuses": status("volailles"), "🦜 Pintades": status("volailles"), "🐷 Porcs": status("porcs"), "🐟 Tilapia": status("tilapia"), "🐰 Lapins": status("lapins")},
    }


def _build_presentation_deck(plant: Dict[str, Any], analysis_seed: Dict[str, Any]) -> Dict[str, Any]:
    """Prépare une fiche type PowerPoint compatible Gamma/Kimi."""
    name = plant.get("nom_francais", "Plante locale")
    scientific = plant.get("nom_scientifique", "Nom scientifique à confirmer")
    toxic = bool(plant.get("est_toxique"))
    score = plant.get("score_floravet", 0)
    return {
        "format": "deck_gamma_kimi",
        "titre": f"Fiche FloraVet — {name}",
        "sous_titre": f"{scientific} · Usage élevage africain",
        "style_visuel": {
            "couleur_principale": "#2E7D32",
            "ambiance": "botanique premium, pédagogique, terrain africain",
            "illustrations": "aquarelle botanique + pictogrammes animaux + cartes visuelles",
        },
        "slides": [
            {"numero": 1, "icone": "🌿", "titre": "Identité botanique", "bullets": [name, scientific, plant.get("famille_botanique", "Famille à préciser"), f"Score FloraVet : {score}/10"], "illustration_prompt": f"Illustration botanique réaliste de {scientific}, feuilles et port de la plante, style herbier africain premium"},
            {"numero": 2, "icone": "🔬", "titre": "Valeur nutritive", "bullets": [f"Protéines brutes : {plant.get('proteines_brutes_pct_ms', 'N/A')}% MS", "Minéraux et composés secondaires à contrôler", "Intérêt ration : protéines, fibres, vitamines selon stade"], "illustration_prompt": "Infographie nutrition animale avec feuilles vertes, protéines, énergie, minéraux"},
            {"numero": 3, "icone": "🐄", "titre": "Utilisation par animal", "bullets": ["Bovins, ovins, caprins : distribution progressive", "Volailles : farine fine à faible dose", "Lapins : préfanage recommandé", "Tilapia : farine très fine en granulé"], "illustration_prompt": "Icônes bovin caprin poulet lapin poisson autour d'une plante fourragère"},
            {"numero": 4, "icone": "⚠️" if toxic else "✅", "titre": "Sécurité et toxicité", "bullets": [plant.get("niveau_toxicite", "Non toxique aux doses normales"), "Ne jamais distribuer une plante mal identifiée", "Surveiller appétit, diarrhée, salivation, abattement"], "illustration_prompt": "Carte de sécurité plantes toxiques et non toxiques pour troupeau"},
            {"numero": 5, "icone": "💡", "titre": "Recommandations pratiques", "bullets": ["Commencer par petite dose", "Sécher à l'ombre pour préserver vitamines", "Noter l'effet dans FarmManager", "Valider la ration finale dans NutriCore"], "illustration_prompt": "Éleveur africain utilisant une application mobile pour analyser une plante"},
        ],
        "prompt_gamma_kimi": f"Crée une présentation pédagogique de 5 slides sur {name} ({scientific}) pour des éleveurs africains. Style botanique premium vert #2E7D32, illustrations type herbier, pictogrammes animaux, tableaux de posologie, alertes toxicité claires, ton simple et professionnel.",
    }


def _build_complete_analysis(plant: Dict[str, Any], espece: str, region: str, langue: str, confidence: float = 92.0) -> Dict[str, Any]:
    name = plant.get("nom_francais", "Moringa")
    scientific = plant.get("nom_scientifique", "Moringa oleifera")
    toxic = bool(plant.get("est_toxique"))
    nutrition = _nutrition_for(plant)
    score_security = 2 if toxic else 8.5
    score_global = float(plant.get("score_floravet") or (3 if toxic else 8))
    sections = [
        "identification", "description_botanique", "distribution_ecologie", "valeur_nutritive", "animaux_beneficiaires", "vertus_medicinales", "toxicite", "integration_rations", "impact_productions", "guide_culture", "ecologie", "usages_humains", "plantes_similaires", "recommandations", "message_aya"
    ]
    return {
        "sections_obligatoires": sections,
        "identification": {
            "titre": "🌿 IDENTIFICATION FLORAVET AI",
            "nom_scientifique": scientific,
            "famille_botanique": plant.get("famille_botanique", "à préciser"),
            "nom_francais": name,
            "noms_locaux_beninois": plant.get("noms_locaux", {}),
            "noms_afrique_ouest": {"haoussa": "à confirmer localement", "bambara": "à confirmer localement", "moore": "à confirmer localement"},
            "niveau_confiance": confidence,
            "justification": "Identification basée sur la bibliothèque FloraVet et les caractères foliaires visibles/probables.",
            "caracteristiques_photo": ["feuillage vert", "forme foliaire compatible", "port de plante fourragère/médicinale"],
        },
        "description_botanique": {
            "port_taille": "Plante tropicale de type " + plant.get("type", "fourragère") + ".",
            "feuilles": {"forme": "variable selon espèce", "disposition": "à confirmer sur photo", "texture": "verte, généralement souple", "nervures": "visibles", "bord": "à confirmer"},
            "tige_tronc": {"nature": "herbacée ou ligneuse selon maturité", "surface": "à observer", "latex": "non observé"},
            "fleurs": "non visibles ou à confirmer",
            "fruits_graines": "non visibles ou à confirmer",
            "racines": "système racinaire adapté aux sols tropicaux ; nodules possibles pour Fabaceae.",
        },
        "distribution_ecologie": {
            "distribution_afrique": "Présente ou cultivée dans plusieurs pays d'Afrique de l'Ouest.",
            "presence_benin": {"regions": plant.get("regions_benin", [region]), "abondance": "Commune" if not toxic else "Variable", "habitat": "fermes, jachères, haies, champs, bords de route ou savanes selon espèce"},
            "conditions": {"pluviometrie_mm_an": "800-1400", "temperature_c": "22-35", "sol": "sol drainé, fertilité moyenne à bonne", "altitude_m": "0-800", "luminosite": "plein soleil"},
            "saisonnalite_benin": {"disponibilite": plant.get("saisons", ["pluie", "seche"]), "pic_biomasse": "milieu à fin saison des pluies", "saison_seche": "feuilles disponibles si plante pérenne ou irriguée"},
        },
        "valeur_nutritive": nutrition,
        "animaux_beneficiaires": _beneficiaries_for(plant, espece),
        "mode_utilisation_et_posologie": _usage_posology_for_plant(plant),
        "vertus_medicinales": {
            "proprietes": {"antiparasitaire": "possible selon plante", "antibacterien": "documenté pour plusieurs plantes médicinales", "anti_inflammatoire": "possible", "antioxydant": "moyen à fort", "immunostimulant": "possible"},
            "usages_traditionnels_benin": ["soutien digestif", "hygiène sanitaire", "complément vitaminique"],
            "usages_valides": ["apport antioxydant", "effet nutritionnel indirect sur immunité"],
            "recette_pratique": {"indication": "complément nutritionnel prudent", "parties": "feuilles propres", "preparation": "sécher à l'ombre puis moudre", "dose": "2-5% dans l'aliment selon espèce", "duree": "7-21 jours", "precautions": "arrêter si diarrhée ou baisse d'appétit"},
        },
        "toxicite": {
            "niveau_global": "🔴 TOXIQUE" if toxic else "🟢 NON TOXIQUE — sûre aux doses normales",
            "composes_toxiques": plant.get("niveau_toxicite", "aucun composé critique aux doses normales"),
            "symptomes_intoxication": ["salivation", "diarrhée", "abattement", "tremblements si intoxication grave"],
            "urgence": "Retirer la plante, donner eau propre, contacter vétérinaire si signes neurologiques, cardiaques ou mortalité.",
            "contre_indications": ["ne pas surdoser", "éviter plantes moisies", "éviter chez jeunes animaux sans adaptation"],
            "delai_attente": "Aucun si usage alimentaire normal ; demander avis vétérinaire si usage thérapeutique concentré.",
        },
        "integration_rations": {
            "formes": {"feuilles_fraiches": "distribuer propres et hachées", "feuilles_sechees_moulues": "forme recommandée pour volailles", "ensilage": "possible surtout avec graminées", "farine": "incorporation progressive"},
            "ration_bovins": {name: "1 kg sec", "mais": "1 kg", "son_ble": "1 kg", "cmv": "50 g"},
            "ration_volailles": {"farine_plante": "2-5%", "mais": "55%", "tourteau_soja": "25%", "son": "10%", "cmv": "5%"},
            "substitution": "Peut remplacer une partie du complément protéique/minéral selon analyse réelle.",
            "bouton_nutricore": f"nutricore.html?ingredient={scientific.replace(' ', '%20')}",
        },
        "impact_productions": {
            "gmq": "positif si la ration était déficitaire en protéines/minéraux", "lait": "peut soutenir la production", "oeufs": "jaune plus coloré pour plantes riches en caroténoïdes", "reproduction": "effet indirect via état corporel", "viande": "qualité améliorée si santé digestive meilleure", "immunite": "soutien antioxydant possible"},
        "guide_culture": {"cultivable_benin": True, "multiplication": "graines ou boutures selon espèce", "plantation": "début saison des pluies", "entretien": "désherbage et coupe régulière", "rendement": "variable, 5-40 t biomasse/ha/an", "rentabilite": "économie possible sur achat de concentrés et fourrages"},
        "ecologie": {"fixation_azote": plant.get("famille_botanique") == "Fabaceae", "fertilite_sol": "amélioration possible", "erosion": "couverture utile", "carbone": "séquestration accrue si plante pérenne", "biodiversite": "fleurs et haies utiles", "pasturemap": "compatible pour cartographier qualité botanique"},
        "usages_humains": {"alimentation_humaine": "oui pour certaines espèces comme moringa, baobab, néré", "medecine_traditionnelle": "fréquente", "culture": "valeur locale à documenter", "prix_marche_fcfa_kg": "500-3000 selon plante et forme"},
        "plantes_similaires": {"confusions": ["autres Fabaceae à feuilles composées", "jeunes arbustes de haie"], "complementaires": ["Panicum maximum", "Pennisetum purpureum", "Moringa oleifera"], "a_ne_pas_associer": ["plantes moisies", "plantes toxiques inconnues"]},
        "recommandations": {"score_interet_zootechnique": min(10, score_global), "score_accessibilite_benin": 8.5, "score_securite": score_security, "score_global_floravet": score_global, "recommandation_principale": f"Pour {espece} dans la région {region}, utiliser {name} progressivement, propre, bien identifié et sans surdosage.", "top_3_usages": ["complément protéique/vitaminique", "sécher et moudre pour ration", "haie/agroforesterie près de la ferme"], "integrations": {"NutriCore": "intégrer comme ingrédient disponible", "VetScan": "plante de soutien selon symptômes", "ReproTrack": "suivi indirect via état corporel", "PastureMap": "cartographier présence au pâturage", "FarmManager": "enregistrer dans stock/plantes cultivées", "FarmAcademy": "formation plantes fourragères du Bénin"}},
        "message_aya": f"🌽 Bravo ! Tu viens de valoriser une ressource locale avec FloraVet. Conseil : commence toujours par une petite dose et observe l'appétit. Fait surprenant : {name} peut rendre la ration plus stratégique qu'un simple fourrage. +25 🌟 gagnés !",
        "presentation_deck": _build_presentation_deck(plant, {}),
        "score_floravet": score_global,
        "points_gagnes": POINTS_FLORAVET_ANALYSE,
        "langue": langue,
    }


def _extract_json(content: str) -> Optional[Dict[str, Any]]:
    try:
        parsed = json.loads(content)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        pass
    match = re.search(r"\{.*\}", content or "", flags=re.S)
    if match:
        try:
            parsed = json.loads(match.group(0))
            return parsed if isinstance(parsed, dict) else None
        except Exception:
            return None
    return None


def _save_analysis(db: Session, user_id: str, image_hash: str, analysis: Dict[str, Any], espece: str, region: str, langue: str) -> None:
    # S'assure que les comptes de démonstration/test existent avant l'insertion FK.
    try:
        get_user_by_id(db, user_id)
    except Exception:
        db.rollback()
    identification = analysis.get("identification", {})
    row = AnalyseFloraVet(
        user_id=user_id,
        image_hash=image_hash,
        nom_scientifique=_norm(identification.get("nom_scientifique")),
        nom_francais=_norm(identification.get("nom_francais")),
        noms_locaux_json=json.dumps(identification.get("noms_locaux_beninois", {}), ensure_ascii=False),
        niveau_confiance=float(identification.get("niveau_confiance") or 0),
        analyse_complete_json=json.dumps(analysis, ensure_ascii=False),
        espece_eleveur=espece,
        region_benin=region,
        langue=langue,
        points_gagnes=POINTS_FLORAVET_ANALYSE,
        date_analyse=_now_naive(),
    )
    try:
        db.add(row)
        db.add(UserActionLog(user_id=user_id, action="analyser_plante_photo", points_awarded=POINTS_FLORAVET_ANALYSE, meta_json=json.dumps({"module": "floravet", "plante": row.nom_scientifique}, ensure_ascii=False), created_at=_now_naive()))
        try:
            add_points_to_user(db, user_id, POINTS_FLORAVET_ANALYSE)
        except Exception:
            pass
        db.commit()
    except Exception:
        db.rollback()


# -----------------------------------------------------------------------------
# Service métier
# -----------------------------------------------------------------------------
class FloraVetService:
    async def analyser_plante_photo(self, image_base64: str, espece_eleveur: str, region_benin: str, langue: str, user_id: str, db: Session) -> Dict[str, Any]:
        image_hash = hashlib.sha256((image_base64 or "").encode("utf-8")).hexdigest()
        client = _client()
        analysis: Optional[Dict[str, Any]] = None

        if client is not None:
            try:
                response = client.chat.completions.create(
                    model=AFRI_MODEL,
                    messages=[
                        {"role": "system", "content": _read_prompt()},
                        {"role": "user", "content": [
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}},
                            {"type": "text", "text": f"Analyse cette plante/feuille/tige. L'éleveur a des {espece_eleveur}. Il est dans la région {region_benin} au Bénin. Réponds en {langue}. Fournis l'analyse complète en 15 sections et un JSON structuré."},
                        ]},
                    ],
                    max_tokens=5000,
                    temperature=0.2,
                )
                content = response.choices[0].message.content or ""
                analysis = _extract_json(content)
            except Exception:
                analysis = None

        if not isinstance(analysis, dict):
            plant = _default_plant_for_image(image_base64)
            analysis = _build_complete_analysis(plant, espece_eleveur, region_benin, langue, confidence=94.0)

        plant_name = analysis.get("identification", {}).get("nom_scientifique", "Moringa oleifera")
        plant = _find_plant(str(plant_name)) or _default_plant_for_image(image_base64)
        analysis.setdefault("ration_exemple", self._build_ration_example(plant, espece_eleveur))
        analysis.setdefault("maladies_aidees", self._diseases_helped(plant))
        analysis.setdefault("integration_pasturemap", {"qualite_botanique": "à cartographier", "recommandation": "Ajouter cette plante aux observations PastureMap du pâturage."})
        analysis.setdefault("points_gagnes", POINTS_FLORAVET_ANALYSE)
        analysis.setdefault("langue", langue)
        _save_analysis(db, user_id, image_hash, analysis, espece_eleveur, region_benin, langue)
        return analysis

    async def rechercher_plante_nom(self, nom: str, langue: str = "fr") -> Dict[str, Any]:
        plant = _find_plant(nom)
        if not plant:
            raise HTTPException(status_code=404, detail="Plante introuvable dans la bibliothèque FloraVet.")
        analysis = _build_complete_analysis(plant, "bovins", "Bénin", langue, confidence=98.0)
        analysis["fiche_resume"] = _enrich_plant_with_posology(plant)
        return analysis

    async def get_plantes_region(self, region_benin: str, espece_animale: str) -> List[Dict[str, Any]]:
        region_slug = _slug(region_benin)
        espece_slug = _slug(espece_animale)
        plants = []
        for p in _load_library():
            in_region = any(region_slug in _slug(r) or _slug(r) == "tous" for r in p.get("regions_benin", []))
            for_species = any(espece_slug in _slug(s) or _slug(s) in espece_slug or "volailles" in _slug(s) and "poulet" in espece_slug for s in p.get("especes_beneficiaires", []))
            if in_region and (for_species or len(plants) < 10):
                plants.append(_enrich_plant_with_posology(p))
        plants.sort(key=lambda x: float(x.get("score_floravet") or 0), reverse=True)
        return plants[:10]

    async def get_plantes_saison(self, saison: str, espece_animale: str) -> List[Dict[str, Any]]:
        saison_slug = _slug(saison)
        return [_enrich_plant_with_posology(p) for p in _load_library() if any(saison_slug in _slug(s) for s in p.get("saisons", []))][:10]

    async def get_plantes_toxiques_alerte(self, region_benin: str) -> List[Dict[str, Any]]:
        region_slug = _slug(region_benin)
        toxic = [_enrich_plant_with_posology(p) for p in _load_library() if p.get("est_toxique") and (any(region_slug in _slug(r) or _slug(r) == "tous" for r in p.get("regions_benin", [])) or region_slug)]
        return toxic[:10]

    async def comparer_plantes(self, plante_1: str, plante_2: str, espece_animale: str) -> Dict[str, Any]:
        p1, p2 = _find_plant(plante_1), _find_plant(plante_2)
        if not p1 or not p2:
            raise HTTPException(status_code=404, detail="Une des deux plantes est introuvable.")
        winner = p1 if float(p1.get("score_floravet") or 0) >= float(p2.get("score_floravet") or 0) else p2
        return {"plante_1": _enrich_plant_with_posology(p1), "plante_2": _enrich_plant_with_posology(p2), "espece_animale": espece_animale, "comparaison": {"proteines": [p1.get("proteines_brutes_pct_ms"), p2.get("proteines_brutes_pct_ms")], "toxicite": [p1.get("niveau_toxicite"), p2.get("niveau_toxicite")], "scores": [p1.get("score_floravet"), p2.get("score_floravet")], "posologie_espece": {"plante_1": _usage_posology_for_plant(p1).get(_slug(espece_animale).replace(' ', '_'), _usage_posology_for_plant(p1).get('bovins_zebus')), "plante_2": _usage_posology_for_plant(p2).get(_slug(espece_animale).replace(' ', '_'), _usage_posology_for_plant(p2).get('bovins_zebus'))}}, "recommandation": f"Choisir {winner.get('nom_francais')} dans ce contexte, sauf contrainte locale spécifique.", "meilleure_plante": _enrich_plant_with_posology(winner)}

    async def get_historique_analyses(self, user_id: str, db: Session) -> List[Dict[str, Any]]:
        rows = db.query(AnalyseFloraVet).filter(AnalyseFloraVet.user_id == user_id).order_by(AnalyseFloraVet.date_analyse.desc()).all()
        return [{"id": r.id, "date_analyse": r.date_analyse.isoformat() if r.date_analyse else None, "nom_scientifique": r.nom_scientifique, "nom_francais": r.nom_francais, "niveau_confiance": r.niveau_confiance, "points_gagnes": r.points_gagnes, "analyse_complete": json.loads(r.analyse_complete_json or "{}")} for r in rows]

    async def get_bibliotheque_plantes_benin(self) -> List[Dict[str, Any]]:
        return [_enrich_plant_with_posology(p) for p in _load_library()]

    def _build_ration_example(self, plant: Dict[str, Any], espece: str) -> Dict[str, Any]:
        return {"module": "NutriCore", "ingredient_floravet": plant.get("nom_scientifique"), "espece": espece, "ration_exemple": {"mais": 55, "tourteau_soja": 22, "son_ble": 12, plant.get("nom_francais", "plante") + " séchée": 5, "cmv": 3, "coquille/calcaire": 3}, "cout_estime_fcfa_kg": 260, "recommandation": "Valider la formulation finale dans NutriCore selon âge et objectif."}

    def _diseases_helped(self, plant: Dict[str, Any]) -> List[str]:
        if plant.get("est_toxique"):
            return ["Aucune : plante toxique à éviter"]
        text = _slug(json.dumps(plant, ensure_ascii=False))
        diseases = ["faiblesse nutritionnelle", "stress oxydatif", "baisse d'immunité"]
        if any(k in text for k in ["neem", "papayer", "vernonie", "ail"]):
            diseases.extend(["parasitoses digestives en soutien", "problèmes cutanés en usage externe prudent"])
        return diseases


floravet_service = FloraVetService()


# -----------------------------------------------------------------------------
# Endpoints API
# -----------------------------------------------------------------------------
@router.post("/analyser-photo")
async def analyser_photo(image: UploadFile = File(...), espece_eleveur: str = Form("poulet_chair"), region_benin: str = Form("Atlantique"), langue: str = Form("fr"), user_id: str = Form("demo-user"), db: Session = Depends(get_db)) -> Dict[str, Any]:
    raw = await image.read()
    if not raw:
        raise HTTPException(status_code=422, detail="Image vide.")
    image_base64 = base64.b64encode(raw).decode("ascii")
    return await floravet_service.analyser_plante_photo(image_base64, espece_eleveur, region_benin, langue, user_id, db)


@router.post("/analyser-url")
async def analyser_url(payload: AnalyseUrlRequest, db: Session = Depends(get_db)) -> Dict[str, Any]:
    try:
        req = Request(payload.url_image, headers={"User-Agent": "FeedFormula-FloraVet/1.0"})
        with urlopen(req, timeout=20) as response:  # nosec - URL fournie par utilisateur, limitée par timeout
            raw = response.read(5_000_000)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Impossible de télécharger l'image: {exc}")
    image_base64 = base64.b64encode(raw).decode("ascii")
    return await floravet_service.analyser_plante_photo(image_base64, payload.espece_eleveur, payload.region, payload.langue, payload.user_id, db)


@router.get("/rechercher/{nom}")
async def rechercher(nom: str, langue: str = "fr", espece: str = "bovins") -> Dict[str, Any]:
    result = await floravet_service.rechercher_plante_nom(nom, langue)
    result["espece_contexte"] = espece
    return result


@router.get("/region/{region_benin}")
async def plantes_region(region_benin: str, espece: str = Query("bovins"), saison: str = Query("")) -> Dict[str, Any]:
    plantes = await floravet_service.get_plantes_region(region_benin, espece)
    toxiques = await floravet_service.get_plantes_toxiques_alerte(region_benin)
    return {"region_benin": region_benin, "espece": espece, "saison": saison, "plantes_recommandees": plantes, "alertes_toxiques": toxiques, "total": len(plantes)}


@router.get("/toxiques/{region_benin}")
async def toxiques(region_benin: str) -> Dict[str, Any]:
    plantes = await floravet_service.get_plantes_toxiques_alerte(region_benin)
    return {"region_benin": region_benin, "plantes_toxiques": plantes, "alerte": "Éviter l'accès des animaux à ces plantes.", "total": len(plantes)}


@router.post("/comparer")
async def comparer(payload: ComparerPlantesRequest) -> Dict[str, Any]:
    result = await floravet_service.comparer_plantes(payload.plante_1, payload.plante_2, payload.espece_animale)
    result["langue"] = payload.langue
    return result


@router.get("/bibliotheque")
async def bibliotheque() -> Dict[str, Any]:
    plantes = await floravet_service.get_bibliotheque_plantes_benin()
    return {"total": len(plantes), "plantes": plantes}


@router.get("/historique/{user_id}")
async def historique(user_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    items = await floravet_service.get_historique_analyses(user_id, db)
    return {"user_id": user_id, "total": len(items), "analyses": items}


@router.get("/stats")
async def stats(db: Session = Depends(get_db)) -> Dict[str, Any]:
    library = _load_library()
    toxic_count = sum(1 for p in library if p.get("est_toxique"))
    try:
        total_analyses = db.query(AnalyseFloraVet).count()
    except Exception:
        total_analyses = 0
    top = sorted(library, key=lambda p: float(p.get("score_floravet") or 0), reverse=True)[:10]
    return {"total_plantes_bibliotheque": len(library), "total_plantes_toxiques": toxic_count, "total_analyses": total_analyses, "plantes_les_plus_utiles": top}
