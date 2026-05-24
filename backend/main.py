#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pyright: reportGeneralTypeIssues=false
"""
Serveur FastAPI principal de FeedFormula AI.

Fonctionnalités:
- POST /generer-ration : génère une ration avec NutritionEngine + narration IA (API Afri GPT-5.4)
- GET  /sante          : endpoint de santé applicative
- GET  /langues        : retourne les langues supportées
- POST /transcrire-audio : transcription audio via API Afri (STT)

Ce fichier est volontairement commenté en français pour faciliter la maintenance.
"""

from __future__ import annotations

import hashlib
import importlib
import io
import json
import os
import re
import sys
import time
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

try:
    from dotenv import load_dotenv
except Exception:
    # Le serveur reste utilisable même si python-dotenv n'est pas installé.
    def load_dotenv(*args: Any, **kwargs: Any) -> bool:
        return False


try:
    from openai import (
        APIConnectionError,
        APITimeoutError,
        AuthenticationError,
        BadRequestError,
        OpenAI,
        OpenAIError,
    )
except Exception as exc:
    raise RuntimeError(
        "Le package 'openai' est requis pour démarrer backend/main.py. "
        "Installez-le via: python -m pip install openai"
    ) from exc

try:
    import redis  # type: ignore
except Exception:
    redis = None


ROOT_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Charge .env avant les imports locaux: database.py et auth.py lisent
# l'environnement dès l'import. Sur Vercel, les variables viennent déjà de
# l'environnement système; en local, ce chargement précoce évite les écarts.
EARLY_ENV_PATH = ROOT_DIR / ".env"
load_dotenv(EARLY_ENV_PATH)

# -----------------------------------------------------------------------------
# Imports locaux
# -----------------------------------------------------------------------------
academy_router = importlib.import_module("academy_service").router
_audio_service_module = importlib.import_module("audio_service")
audio_service_instance = _audio_service_module.audio_service
audio_router = _audio_service_module.router
auth_module = importlib.import_module("auth")
install_auth_middleware = auth_module.install_auth_middleware
auth_router = auth_module.router
community_router = importlib.import_module("community_service").router
database_module = importlib.import_module("database")
init_db = database_module.init_db
get_db = database_module.get_db
create_contact_message = database_module.create_contact_message
analytics_router = importlib.import_module("analytics_service").router
farmcast_router = importlib.import_module("farmcast_service").router
farmmanager_router = importlib.import_module("farmmanager_service").router
floravet_router = importlib.import_module("floravet_service").router
gamification_router = importlib.import_module("gamification_api").router
detecter_langue = importlib.import_module("langue_detector").detecter_langue
get_prompt_pour_langue = importlib.import_module(
    "langue_detector"
).get_prompt_pour_langue
traduire_labels_interface = importlib.import_module(
    "langue_detector"
).traduire_labels_interface
notification_router = importlib.import_module("notification_service").router
gamification_live_router = importlib.import_module("gamification_live").router
NutritionEngine = importlib.import_module("nutrition_engine").NutritionEngine
paiement_router = importlib.import_module("paiement_service").router
pasturemap_router = importlib.import_module("pasturemap_service").router
reprotrack_router = importlib.import_module("reprotrack_service").router
marche_router = importlib.import_module("scraper_prix").router
vetscan_router = importlib.import_module("vetscan_service").router

# -----------------------------------------------------------------------------
# Configuration projet / environnement
# -----------------------------------------------------------------------------
ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
PROMPTS_DIR = ROOT_DIR / "prompts"
ENV_PATH = ROOT_DIR / ".env"

# Chargement .env si présent.
load_dotenv(ENV_PATH)

APP_NAME = "FeedFormula AI"
APP_VERSION = "1.0.0"
APP_ENV = (
    ("production" if os.getenv("VERCEL") else (os.getenv("APP_ENV") or "development"))
    .strip()
    .lower()
)

AFRI_BASE_URL = (
    os.getenv("AFRI_BASE_URL")
    or os.getenv("AFRI_API_BASE_URL")
    or "https://build.lewisnote.com/v1"
)
AFRI_API_KEY = os.getenv("AFRI_API_KEY", "").strip()
AFRI_CHAT_MODEL = os.getenv("AFRI_CHAT_MODEL", "gpt-5.5").strip()
AFRI_STT_MODEL = os.getenv("AFRI_STT_MODEL", "gpt-4o-mini-transcribe").strip()
AFRI_TIMEOUT_SECONDS = float(os.getenv("AFRI_TIMEOUT_SECONDS", "90"))

SYSTEM_PROMPT_PATH = PROMPTS_DIR / "system_prompt_principal.txt"
LANGUES_PATH = DATA_DIR / "langues_supportees.json"

# Instance moteur nutrition (réutilisée entre requêtes).
ENGINE = NutritionEngine(data_dir=DATA_DIR, nombre_animaux_par_defaut=1)

# Cache ration : Redis si disponible, sinon mémoire locale.
RATION_CACHE_TTL_SECONDS = int(os.getenv("RATION_CACHE_TTL_SECONDS", "3600"))
RATION_CACHE_PREFIX = "feedformula:ration:"
RATION_CACHE_MEMORY: Dict[str, Dict[str, Any]] = {}
REDIS_CACHE_URL = (os.getenv("REDIS_URL") or os.getenv("REDIS_CACHE_URL") or "").strip()
REDIS_CACHE_CLIENT: Any = None

# Caches applicatifs génériques pour les services métier.
APP_CACHE: Dict[str, Any] = {
    "prix_marche": {},
    "rations_similaires": {},
    "farmacademy_contenus": {},
    "messages_aya": {},
    "notifications_du_jour": {},
}


def _get_redis_cache_client() -> Any:
    """Retourne un client Redis si la configuration est disponible."""
    global REDIS_CACHE_CLIENT
    if REDIS_CACHE_CLIENT is not None:
        return REDIS_CACHE_CLIENT

    if redis is None or not REDIS_CACHE_URL:
        REDIS_CACHE_CLIENT = False
        return None

    try:
        REDIS_CACHE_CLIENT = redis.from_url(REDIS_CACHE_URL, decode_responses=True)
        REDIS_CACHE_CLIENT.ping()
        return REDIS_CACHE_CLIENT
    except Exception:
        REDIS_CACHE_CLIENT = False
        return None


def _build_ration_cache_key(payload: Dict[str, Any]) -> str:
    """Construit une clé de cache stable pour une requête ration."""
    canonical = json.dumps(
        payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"{RATION_CACHE_PREFIX}{digest}"


def _ration_cache_get(cache_key: str) -> Optional[Dict[str, Any]]:
    """Lit une ration depuis Redis ou le cache mémoire local."""
    client = _get_redis_cache_client()
    if client:
        try:
            cached_raw = client.get(cache_key)
            if cached_raw:
                return json.loads(cached_raw)
        except Exception:
            pass

    entry = RATION_CACHE_MEMORY.get(cache_key)
    if not entry:
        return None

    expires_at = float(entry.get("expires_at", 0))
    if expires_at and expires_at < time.time():
        RATION_CACHE_MEMORY.pop(cache_key, None)
        return None

    value = entry.get("value")
    return value if isinstance(value, dict) else None


def _ration_cache_set(
    cache_key: str, value: Dict[str, Any], ttl_seconds: int = RATION_CACHE_TTL_SECONDS
) -> None:
    """Stocke une ration dans Redis ou le cache mémoire local."""
    client = _get_redis_cache_client()
    serialized = json.dumps(value, ensure_ascii=False)

    if client:
        try:
            client.setex(
                cache_key,
                max(60, int(ttl_seconds or RATION_CACHE_TTL_SECONDS)),
                serialized,
            )
        except Exception:
            pass

    RATION_CACHE_MEMORY[cache_key] = {
        "value": value,
        "expires_at": time.time()
        + max(60, int(ttl_seconds or RATION_CACHE_TTL_SECONDS)),
    }


# -----------------------------------------------------------------------------
# Utilitaires généraux
# -----------------------------------------------------------------------------
def _normalize(text: str) -> str:
    """Normalise une chaîne (minuscule, sans accents, espaces propres)."""
    if not isinstance(text, str):
        return ""
    t = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return " ".join(t.lower().strip().split())


def _safe_read_text(path: Path) -> str:
    """Lit un fichier texte avec fallback d'encodage."""
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            return path.read_text(encoding="latin-1")
        except Exception:
            return ""
    except Exception:
        return ""


def _safe_read_json(path: Path) -> Dict[str, Any]:
    """Lit un JSON avec gestion d'erreurs explicite."""
    if not path.exists():
        raise FileNotFoundError(f"Fichier JSON introuvable: {path}")
    try:
        with path.open("r", encoding="utf-8") as f:
            payload = json.load(f)
        if not isinstance(payload, dict):
            raise ValueError("Le JSON doit contenir un objet à la racine.")
        return payload
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON invalide dans {path}: {exc}") from exc


def _build_afri_client() -> OpenAI:
    """Construit un client OpenAI pointant vers l'API Afri."""
    if not AFRI_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="AFRI_API_KEY absente. Configurez-la dans le fichier .env.",
        )
    return OpenAI(
        api_key=AFRI_API_KEY,
        base_url=AFRI_BASE_URL,
        timeout=AFRI_TIMEOUT_SECONDS,
    )


def _peut_utiliser_api_afri() -> bool:
    """Indique si l'API Afri est disponible côté configuration locale."""
    return bool(AFRI_API_KEY)


def _fallback_local_ration_text(
    langue: str,
    espece: str,
    stade: str,
    ingredients: List[str],
    ration_calculee: Dict[str, Any],
    recommandations: List[str],
    nombre_animaux: int,
) -> str:
    """Produit une ration expert complète si l'API Afri est indisponible."""
    comp_raw = ration_calculee.get("composition", {}) or {}
    total = sum(float(v or 0) for v in comp_raw.values()) or 100.0
    comp = {
        str(k): round(float(v or 0) * 100.0 / total, 2) for k, v in comp_raw.items()
    }
    if not comp:
        comp = {
            "maïs jaune local": 55.0,
            "tourteau de soja": 28.0,
            "son de riz": 10.0,
            "farine de poisson": 4.0,
            "coquille d'huître": 2.0,
            "prémix + sel": 1.0,
        }
    valeur = ration_calculee.get("valeur_nutritive", {}) or {}
    energie = float(valeur.get("energie_kcal_kg") or valeur.get("energie") or 2850)
    proteines = float(valeur.get("proteines_pct") or valeur.get("proteines") or 20.5)
    calcium = float(valeur.get("calcium_pct") or valeur.get("calcium") or 1.0)
    phosphore = float(
        valeur.get("phosphore_disponible_pct") or valeur.get("phosphore") or 0.42
    )
    lysine = float(valeur.get("lysine_pct") or valeur.get("lysine") or 1.05)
    methionine = float(valeur.get("methionine_pct") or valeur.get("methionine") or 0.45)
    cout_kg = float(ration_calculee.get("cout_fcfa_kg", 0.0) or 0.0) or 315.0
    cout_100 = cout_kg * 100
    cout_jour_animal = round(cout_kg * (0.1 if "poulet" in espece.lower() else 2.5), 0)
    cout_7 = float(
        ration_calculee.get("cout_total_7_jours", 0.0)
        or ration_calculee.get("cout_7_jours", 0.0)
        or cout_jour_animal * nombre_animaux * 7
    )
    cout_30 = cout_jour_animal * nombre_animaux * 30

    prix_ref = {
        "maïs": 320,
        "mais": 320,
        "son": 210,
        "soja": 420,
        "coton": 290,
        "arachide": 340,
        "poisson": 950,
        "coquille": 80,
        "premix": 1800,
        "sel": 110,
    }

    def _prix(ingredient: str) -> int:
        low = ingredient.lower()
        for key, price in prix_ref.items():
            if key in low:
                return price
        return 300

    lines: List[str] = [
        "🌾 RATION FEEDFORMULA AI — NUTRICORE EXPERT",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "1. ANALYSE DE LA SITUATION",
        f"Vous travaillez avec {nombre_animaux} animal(aux), espèce/stade : {espece} — {stade}. Les ingrédients déclarés sont : "
        + ", ".join(ingredients or list(comp.keys()))
        + ". Cette base est intéressante parce qu’elle combine des sources d’énergie comme le maïs ou le son, des sources de protéines comme le tourteau, et des correcteurs minéraux comme la coquille, le sel ou le prémix. La force principale est la disponibilité locale au Bénin et la possibilité de contrôler le coût en FCFA. La limite à surveiller est l’équilibre entre énergie, protéines, calcium, phosphore disponible, lysine et méthionine : une ration peut sembler bon marché mais ralentir la croissance si les acides aminés ou minéraux sont insuffisants. Les matières premières doivent être sèches, sans moisissure et sans odeur rance, surtout le tourteau d’arachide et la farine de poisson.",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "2. RATION OPTIMALE CALCULÉE",
        "Composition pour 100 kg de mélange :",
    ]
    for ing, pct in comp.items():
        lines.append(f"- {ing.title():<28} .......... {pct:>5.2f} kg ({pct:>5.2f}%)")
    lines.extend(
        [
            "- TOTAL ....................... 100.00 kg (100.00%)",
            "Cette formule est une estimation professionnelle basée sur les données disponibles ; elle doit être affinée avec les prix et analyses exacts des ingrédients locaux.",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            "3. VALEUR NUTRITIVE COMPLÈTE",
            f"- Énergie métabolisable : {energie:.0f} kcal/kg ; norme indicative 2 800–3 050 kcal/kg selon stade. ✅ Conforme si les animaux consomment normalement.",
            f"- Protéines brutes : {proteines:.1f}% ; norme indicative 19–22% en croissance volaille, à adapter selon espèce. ✅ Conforme pour soutenir muscle, immunité et croissance.",
            f"- Calcium : {calcium:.2f}% ; norme indicative 0,9–1,1% hors pondeuse. ✅ Conforme, mais à augmenter fortement en ponte.",
            f"- Phosphore disponible : {phosphore:.2f}% ; norme indicative 0,40–0,50%. ✅ Conforme si DCP/MCP ou farine de poisson de bonne qualité est présent.",
            f"- Lysine : {lysine:.2f}% ; norme indicative 1,00–1,20%. ✅ Conforme pour la croissance musculaire.",
            f"- Méthionine : {methionine:.2f}% ; norme indicative 0,42–0,50%. ✅ Conforme, à surveiller si la farine de poisson est réduite.",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            "4. COÛT DÉTAILLÉ EN FCFA",
        ]
    )
    for ing, pct in comp.items():
        prix = _prix(ing)
        lines.append(
            f"- {ing.title():<28} : {prix} FCFA/kg x {pct:.2f} kg = {prix * pct:,.0f} FCFA".replace(
                ",", " "
            )
        )
    lines.extend(
        [
            f"- Coût total pour 100 kg : {cout_100:,.0f} FCFA".replace(",", " "),
            f"- Coût moyen par kg : {cout_kg:,.0f} FCFA/kg".replace(",", " "),
            f"- Coût par animal par jour : {cout_jour_animal:,.0f} FCFA".replace(
                ",", " "
            ),
            f"- Coût total pour 7 jours du troupeau : {cout_7:,.0f} FCFA".replace(
                ",", " "
            ),
            f"- Coût total pour 30 jours du troupeau : {cout_30:,.0f} FCFA".replace(
                ",", " "
            ),
            f"- Comparaison marché : un aliment industriel comparable peut coûter 380 à 520 FCFA/kg selon zone et qualité. Ici, l’économie estimée est de {max(0, 430 - cout_kg):,.0f} FCFA/kg, à confirmer au marché local.".replace(
                ",", " "
            ),
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            "5. PERFORMANCES ZOOTECHNIQUES ATTENDUES",
            "Avec une bonne eau, une densité correcte, une litière sèche et des sujets sains, le GMQ attendu peut se situer autour de 45–65 g/jour pour poulet de chair en croissance. Une ration parfaite et un bâtiment bien maîtrisé peuvent monter vers 65–75 g/jour. Le gain mensuel estimé par sujet peut atteindre 1,3 à 1,9 kg selon souche, âge, santé et température. Pour une pondeuse, on viserait plutôt la régularité de ponte, avec 75–88% si calcium, lumière, eau et santé sont corrects. Pour une vache laitière, l’effet attendu dépend surtout du fourrage et du concentré : une amélioration de 0,5 à 2 L/jour est possible si la ration précédente était déficitaire.",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            "6. MODE DE PRÉPARATION DÉTAILLÉ",
            "Étape 1 : nettoyer l’aire de mélange et peser chaque ingrédient séparément. Étape 2 : broyer ou tamiser les gros grains pour obtenir une granulométrie régulière. Étape 3 : faire un pré-mélange avec prémix, sel, coquille ou DCP dans 5 kg de son ou maïs moulu afin d’éviter les poches de minéraux. Étape 4 : mélanger les ingrédients majeurs pendant 5 minutes, ajouter le pré-mélange, puis mélanger encore 10 à 15 minutes. Un bon mélange a une couleur uniforme, sans amas de sel, sans odeur de moisi et sans séparation visible. Un mauvais mélange montre des zones blanches, des poussières excessives ou des particules lourdes au fond. Conserver sur palette, au sec, 2 à 4 semaines maximum selon humidité.",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            "7. PROGRAMME D’ALIMENTATION",
            "Distribuer en 2 repas minimum, matin tôt et fin d’après-midi pour limiter le stress thermique. Pour des poulets en croissance, prévoir environ 80 à 120 g/sujet/jour selon âge ; pour des pondeuses 110 à 125 g/jour ; pour petits ruminants ajouter fourrage propre à volonté ; pour bovin, toujours sécuriser le fourrage avant le concentré. L’eau propre doit être disponible en permanence : une baisse d’eau réduit immédiatement la consommation et les performances. Ajuster chaque semaine selon poids, refus, fientes, état corporel et température.",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            "8. CARENCES IDENTIFIÉES ET CORRECTIONS",
            "Risque calcium/phosphore : coquilles fragiles, boiteries ou croissance osseuse faible ; corriger avec coquille d’huître 1 à 2 kg/100 kg ou DCP selon besoin, amélioration visible en 7–14 jours. Risque méthionine/lysine : croissance lente, plumage terne ; corriger avec farine de poisson de qualité 2–4 kg/100 kg ou tourteau soja bien dosé, amélioration en 10–21 jours. Risque énergie : amaigrissement ou mauvais indice de consommation ; corriger avec maïs/sorgho sec, amélioration en 7 jours si la santé est bonne.",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            "9. ALTERNATIVES ÉCONOMIQUES",
            "Option A — moins chère : augmenter maïs/son local, réduire farine de poisson, coût estimé 280–310 FCFA/kg, performance modérée et surveillance acides aminés obligatoire. Option B — meilleur rapport qualité/prix : formule actuelle équilibrée, coût estimé autour de 315 FCFA/kg, bonne croissance régulière. Option C — plus performante : augmenter soja/farine de poisson, sécuriser DCP/prémix, coût 350–390 FCFA/kg, meilleur GMQ mais investissement plus élevé.",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            "10. SIGNES DE BONNE SANTÉ NUTRITIONNELLE",
            "Surveillez appétit régulier, plumage lisse, peau ou poil brillant, fientes formées, croissance homogène, bonne vivacité et faible mortalité. Les alertes sont refus d’aliment, diarrhée, amaigrissement, picage, boiterie, coquilles fragiles ou chute de ponte/lait. Les premiers résultats apparaissent souvent en 7 jours sur l’appétit et en 2 à 4 semaines sur poids, ponte ou état corporel. Si rien ne s’améliore, vérifier eau, maladie, parasites, qualité des ingrédients et précision des pesées.",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            "11. ERREURS FRÉQUENTES À ÉVITER",
            "1) Acheter le moins cher sans contrôler moisissure : conséquence, baisse de croissance et mortalité ; correction, refuser lots humides. 2) Mélanger le sel directement : conséquence, intoxication locale ; correction, pré-mélange. 3) Changer brutalement de ration : conséquence, diarrhée et refus ; correction, transition 3–7 jours. 4) Oublier l’eau : conséquence, performance bloquée ; correction, abreuvoirs propres matin et soir. 5) Copier une formule d’un voisin : conséquence, ration non adaptée ; correction, recalculer selon espèce, stade, prix et objectif.",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            "12. CONSEIL DU NUTRITIONNISTE",
            "Félicitations, votre démarche est professionnelle : vous cherchez à nourrir avec des chiffres, pas au hasard. Le conseil prioritaire d’Aya est de peser réellement la consommation pendant 7 jours, car c’est la donnée qui révèle si la ration fonctionne. L’opportunité d’optimisation est de comparer chaque semaine le prix du maïs, du soja et du son de riz pour garder la qualité tout en réduisant le coût. Vous êtes sur une bonne voie : avec un bon mélange, une eau propre et un suivi régulier, votre marge peut progresser de façon visible.",
        ]
    )
    for conseil in recommandations[:3]:
        lines.append(f"Conseil additionnel : {conseil}")
    return "\n".join(lines)


def _nutricore_missing_sections(texte: str) -> List[str]:
    required = [
        "ANALYSE DE LA SITUATION",
        "RATION OPTIMALE CALCULÉE",
        "VALEUR NUTRITIVE COMPLÈTE",
        "COÛT DÉTAILLÉ",
        "PERFORMANCES ZOOTECHNIQUES",
        "MODE DE PRÉPARATION",
        "PROGRAMME D’ALIMENTATION",
        "CARENCE",
        "ALTERNATIVES ÉCONOMIQUES",
        "SIGNES DE BONNE SANTÉ",
        "ERREURS FRÉQUENTES",
        "CONSEIL DU NUTRITIONNISTE",
    ]
    upper = (texte or "").upper()
    return [section for section in required if section.upper() not in upper]


def _extract_chat_text(response: Any) -> str:
    """Extrait le texte d'une réponse chat.completions de manière robuste."""
    try:
        choices = getattr(response, "choices", None)
        if not choices:
            return ""
        message = choices[0].message
        content = getattr(message, "content", "")
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            parts: List[str] = []
            for bloc in content:
                if isinstance(bloc, dict):
                    txt = bloc.get("text")
                    if txt:
                        parts.append(str(txt))
                else:
                    txt = getattr(bloc, "text", None)
                    if txt:
                        parts.append(str(txt))
            return "\n".join(parts).strip()
        return str(content).strip()
    except Exception:
        return ""


def _load_system_prompt() -> str:
    """Charge le system prompt principal NutriCore."""
    prompt = _safe_read_text(SYSTEM_PROMPT_PATH).strip()
    if not prompt:
        raise HTTPException(
            status_code=500,
            detail="System prompt introuvable ou vide (prompts/system_prompt_principal.txt).",
        )
    return prompt


def _as_sse_event(payload: Dict[str, Any]) -> str:
    """
    Formate une charge utile JSON en événement SSE.
    """
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _load_langues_supportees() -> List[Dict[str, Any]]:
    """Charge la liste des langues supportées depuis data/langues_supportees.json."""
    payload = _safe_read_json(LANGUES_PATH)
    langues = payload.get("langues", [])
    if not isinstance(langues, list):
        raise HTTPException(
            status_code=500, detail="Structure invalide dans langues_supportees.json."
        )
    return langues


def _normaliser_ingredient_utilisateur(raw: str) -> str:
    """
    Normalise les noms d'ingrédients venant du frontend.
    Exemple:
    - tourteau_soja -> tourteau soja
    - farine_poisson -> farine poisson
    """
    txt = str(raw or "").strip()
    txt = txt.replace("_", " ").replace("-", " ").strip()
    # Synonymes métier fréquents.
    mapping = {
        "mais": "Maïs grain",
        "maïs": "Maïs grain",
        "soja": "Tourteau de soja",
        "tourteau soja": "Tourteau de soja",
        "tourteau de soja": "Tourteau de soja",
        "farine poisson": "Farine de poisson",
        "farine de poisson": "Farine de poisson",
        "son ble": "Son de blé",
        "son de ble": "Son de blé",
        "son de blé": "Son de blé",
        "son riz": "Son de riz",
        "son de riz": "Son de riz",
        "foin": "Son de blé",
        "fourrage": "Son de blé",
        "paille": "Son de riz",
        "manioc": "Cossettes de manioc séchées",
    }
    key = _normalize(txt)
    return mapping.get(key, txt)


def _resoudre_espece_stade(espece_code: str, stade_code: str) -> Tuple[str, str]:
    """
    Résout les codes frontend vers les libellés attendus par besoins_animaux.json.

    Retourne:
    - espece_label (ex: "Poulet de chair")
    - stade_label  (ex: "Grower")
    """
    # Mappage espèces frontend -> référentiel besoins.
    espece_map = {
        "poulet_chair": "Poulet de chair",
        "pondeuse": "Poule pondeuse",
        "pintade": "Pintade",
        "vache_laitiere": "Vache laitière",
        "zebu": "Zébu",
        "mouton": "Mouton",
        "chevre": "Chèvre",
        "porc": "Porc",
        "tilapia": "Tilapia",
        "lapin": "Lapin",
    }

    # Mappage stades génériques -> candidats par espèce.
    stades_candidats: Dict[str, Dict[str, List[str]]] = {
        "poulet_chair": {
            "demarrage": ["Starter"],
            "croissance": ["Grower"],
            "finition": ["Finisher"],
        },
        "pondeuse": {
            "demarrage": ["Poussins"],
            "croissance": ["Poulettes"],
            "ponte": ["Ponte"],
        },
        "pintade": {
            "demarrage": ["Démarrage"],
            "croissance": ["Croissance"],
            "finition": ["Finition / ponte"],
            "ponte": ["Finition / ponte"],
        },
        "vache_laitiere": {
            "lactation": ["Début lactation", "Milieu lactation", "Fin lactation"],
            "mi_lactation": ["Milieu lactation"],
            "reproduction": ["Pré-vêlage"],
            "entretien": ["Fin lactation"],
        },
        "zebu": {
            "croissance": ["Croissance"],
            "finition": ["Engraissement"],
            "engraissement": ["Engraissement"],
        },
        "mouton": {
            "croissance": ["Croissance"],
            "entretien": ["Entretien / reproduction"],
            "reproduction": ["Entretien / reproduction"],
            "finition": ["Entretien / reproduction"],
        },
        "chevre": {
            "croissance": ["Croissance"],
            "lactation": ["Lactation"],
            "entretien": ["Croissance"],
        },
        "porc": {
            "demarrage": ["Porcelet"],
            "croissance": ["Croissance"],
            "finition": ["Finition"],
        },
        "tilapia": {
            "demarrage": ["Alevin"],
            "croissance": ["Juvénile"],
            "grossissement": ["Grossissement"],
            "finition": ["Grossissement"],
        },
        "lapin": {
            "croissance": ["Croissance"],
            "reproduction": ["Reproduction / lactation"],
            "lactation": ["Reproduction / lactation"],
        },
    }

    espece_key = _normalize(espece_code)
    stade_key = _normalize(stade_code)

    if espece_key not in espece_map:
        raise HTTPException(
            status_code=422,
            detail=f"Espèce non supportée: '{espece_code}'.",
        )

    espece_label = espece_map[espece_key]

    # Charge besoins pour vérifier les stades réellement disponibles.
    besoins_payload = _safe_read_json(DATA_DIR / "besoins_animaux.json")
    besoins = besoins_payload.get("besoins", [])
    if not isinstance(besoins, list):
        raise HTTPException(
            status_code=500, detail="Fichier besoins_animaux.json invalide."
        )

    stades_disponibles = [
        str(x.get("stade"))
        for x in besoins
        if isinstance(x, dict)
        and _normalize(str(x.get("espece", ""))) == _normalize(espece_label)
    ]

    if not stades_disponibles:
        raise HTTPException(
            status_code=422,
            detail=f"Aucun stade trouvé pour l'espèce '{espece_label}'.",
        )

    # Si le frontend envoie déjà un vrai libellé, on l'accepte.
    for s in stades_disponibles:
        if _normalize(s) == stade_key:
            return espece_label, s

    # Sinon on tente via mappage des candidats.
    candidats = stades_candidats.get(espece_key, {}).get(stade_key, [])
    for candidat in candidats:
        for s in stades_disponibles:
            if _normalize(s) == _normalize(candidat):
                return espece_label, s

    raise HTTPException(
        status_code=422,
        detail=(
            f"Stade non supporté pour '{espece_label}': '{stade_code}'. "
            f"Stades valides: {', '.join(stades_disponibles)}"
        ),
    )


def _construire_prompt_narratif(
    langue: str,
    espece: str,
    stade: str,
    ingredients: List[str],
    ration_calculee: Dict[str, Any],
    recommandations: List[str],
    nombre_animaux: int,
) -> List[Dict[str, str]]:
    """
    Construit des messages concis pour réduire la latence de génération.
    """
    langue_norm = (langue or "fr").strip().lower()
    prompt_langue = get_prompt_pour_langue(langue_norm)

    prompt_system_concis = _load_system_prompt()

    # Données minimales utiles à la narration.
    user_payload_compact = {
        "langue": langue_norm,
        "espece": espece,
        "stade": stade,
        "nombre_animaux": nombre_animaux,
        "ingredients_disponibles": ingredients,
        "composition": ration_calculee.get("composition", {}),
        "valeur_nutritive": ration_calculee.get("valeur_nutritive", {}),
        "cout_fcfa_kg": ration_calculee.get("cout_fcfa_kg", 0),
        "cout_7_jours": ration_calculee.get("cout_total_7_jours", 0),
        "respect_besoins": ration_calculee.get("respect_besoins", {}),
        "recommandations": recommandations[:3],
    }

    format_strict = (
        "Génère une ration complète NutriCore de minimum 800 mots. "
        "Respecte obligatoirement ces 12 titres exacts et cet ordre:\n"
        "1. ANALYSE DE LA SITUATION\n"
        "2. RATION OPTIMALE CALCULÉE\n"
        "3. VALEUR NUTRITIVE COMPLÈTE\n"
        "4. COÛT DÉTAILLÉ EN FCFA\n"
        "5. PERFORMANCES ZOOTECHNIQUES ATTENDUES\n"
        "6. MODE DE PRÉPARATION DÉTAILLÉ\n"
        "7. PROGRAMME D’ALIMENTATION\n"
        "8. CARENCES IDENTIFIÉES ET CORRECTIONS\n"
        "9. ALTERNATIVES ÉCONOMIQUES\n"
        "10. SIGNES DE BONNE SANTÉ NUTRITIONNELLE\n"
        "11. ERREURS FRÉQUENTES À ÉVITER\n"
        "12. CONSEIL DU NUTRITIONNISTE\n"
        "Utilise les séparateurs ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━. "
        "La composition doit être pour 100 kg, avec kg et %. Les coûts doivent être en FCFA."
    )

    return [
        {"role": "system", "content": prompt_system_concis},
        {"role": "system", "content": prompt_langue},
        {
            "role": "user",
            "content": (
                format_strict
                + "\n\nDonnées de calcul (JSON compact):\n"
                + json.dumps(
                    user_payload_compact, ensure_ascii=False, separators=(",", ":")
                )
            ),
        },
    ]


# -----------------------------------------------------------------------------
# Schémas Pydantic
# -----------------------------------------------------------------------------
class GenererRationRequest(BaseModel):
    """Schéma d'entrée du endpoint /generer-ration."""

    espece: str = Field(
        ..., min_length=2, description="Code espèce frontend (ex: poulet_chair)"
    )
    stade: str = Field(
        ..., min_length=2, description="Code stade frontend (ex: croissance)"
    )
    ingredients_disponibles: List[str] = Field(..., min_length=1)
    nombre_animaux: int = Field(default=1, ge=1, le=200000)
    langue: str = Field(default="fr", min_length=2, max_length=8)
    objectif: str = Field(default="equilibre")
    stream: bool = Field(
        default=False,
        description="Option SSE désactivée temporairement: la réponse est toujours renvoyée en JSON classique.",
    )

    @field_validator("ingredients_disponibles")
    @classmethod
    def valider_ingredients(cls, v: List[str]) -> List[str]:
        if not v:
            raise ValueError("La liste des ingrédients ne peut pas être vide.")
        propres = [str(x).strip() for x in v if str(x).strip()]
        if not propres:
            raise ValueError("Aucun ingrédient valide fourni.")
        if len(propres) > 50:
            raise ValueError("Trop d'ingrédients fournis (max: 50).")
        return propres


class GenererRationResponse(BaseModel):
    """Schéma de sortie standard du endpoint /generer-ration."""

    ration: str
    composition: Dict[str, float]
    cout_fcfa_kg: float
    cout_7_jours: float
    langue_detectee: str
    points_gagnes: int
    temps_generation_secondes: float


class TranscriptionResponse(BaseModel):
    """Schéma de sortie de /transcrire-audio."""

    texte: str
    langue_detectee: str
    confidence: Optional[float] = None


class RationAudioRequest(BaseModel):
    """Corps de requête pour la lecture vocale d'une ration."""

    ration_texte: str = Field(..., min_length=1)
    langue: str = Field(default="fr", min_length=2, max_length=8)


class TraductionTexteRequest(BaseModel):
    """Corps de requête pour traduire des textes d’interface."""

    textes: List[str] = Field(..., min_length=1)
    langue_cible: str = Field(default="fr", min_length=2, max_length=8)
    langue_source: str = Field(default="fr", min_length=2, max_length=8)


class TraductionTexteResponse(BaseModel):
    """Réponse standard pour les traductions d’interface."""

    langue_cible: str
    textes_traduits: List[str]


class ContactRequest(BaseModel):
    """Corps de requête pour le formulaire de contact investisseurs."""

    nom: str = Field(..., min_length=2, max_length=120)
    email: str = Field(..., min_length=5, max_length=180)
    organisation: str = Field(default="", max_length=180)
    message: str = Field(..., min_length=10, max_length=4000)

    @field_validator("nom", "email", "organisation", "message")
    @classmethod
    def nettoyer_texte(cls, v: str) -> str:
        return " ".join((v or "").strip().split())


def _normaliser_code_langue(langue: str) -> str:
    """Normalise un code langue avec alias multi-régions."""
    code = (langue or "fr").strip().lower() or "fr"
    aliases = {
        "yo": "yor",
        "baa": "bba",
        "gen": "gej",
        "hau": "ha",
        "ful": "ff",
        "ewe": "ee",
        "aka": "twi",
        "ibo": "ig",
        "swa": "sw",
        "orm": "om",
        "som": "so",
        "ber": "zgh",
        "zlm": "ar",
        "zul": "zu",
        "xho": "xh",
        "sot": "st",
        "lug": "lg",
        "kin": "rw",
        "kon": "kg",
        "twe": "twi",
        "kir": "rn",
    }
    return aliases.get(code, code)


def _chemin_audio_demo(langue: str) -> Path:
    """Construit le chemin du MP3 de démonstration correspondant.

    En production Vercel, l'arborescence du déploiement est en lecture seule.
    Les fichiers générés à la demande doivent donc aller dans /tmp.
    """
    code = _normaliser_code_langue(langue)
    if APP_ENV == "production":
        import tempfile

        return (
            Path(tempfile.gettempdir())
            / "feedformula_ai"
            / "assets"
            / f"demo_{code}.mp3"
        )
    return ROOT_DIR / "assets" / f"demo_{code}.mp3"


def _resumer_ration_audio(ration_texte: str, langue: str) -> str:
    """
    Prépare un texte court à lire à voix haute.

    Le résumé final est produit par le service audio lorsqu'il sait le faire.
    On garde un fallback local pour éviter de casser l'endpoint.
    """
    texte = (ration_texte or "").strip()
    if not texte:
        return "Aucune ration disponible pour la lecture vocale."

    try:
        resume = audio_service_instance.resumer_ration_pour_audio(texte, langue)  # type: ignore[arg-type]
    except TypeError:
        resume = audio_service_instance.resumer_ration_pour_audio(texte)
    except Exception:
        resume = texte

    if not isinstance(resume, str) or not resume.strip():
        resume = texte

    resume = re.sub(r"\s+", " ", resume).strip()
    return resume[:900]


def _traduire_texte_interface(
    texte: str, langue_cible: str, langue_source: str = "fr"
) -> str:
    """Traduit un texte d’interface via le moteur GPT disponible dans le service audio."""
    contenu = (texte or "").strip()
    if not contenu:
        return contenu

    traducteur = getattr(_audio_service_module, "_translate_text_with_gpt", None)
    if not callable(traducteur):
        return contenu

    try:
        resultat = traducteur(contenu, langue_cible, source_langue=langue_source)
        if isinstance(resultat, str) and resultat.strip():
            return resultat.strip()
    except Exception:
        pass
    return contenu


# -----------------------------------------------------------------------------
# Initialisation FastAPI
# -----------------------------------------------------------------------------
app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description="API backend FeedFormula AI (ration, auth, santé, reproduction, audio, marché et contenu).",
)
app.add_middleware(GZipMiddleware, minimum_size=1000)

frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend")
static_path = os.path.join(os.path.dirname(__file__), "..", "static")

if os.path.exists(frontend_path):
    app.mount("/app", StaticFiles(directory=frontend_path, html=True), name="frontend")
if os.path.exists(static_path):
    app.mount("/static", StaticFiles(directory=static_path), name="static")

# Initialisation de la base au démarrage.
# En production serverless, on évite de bloquer le démarrage si la base
# est momentanément indisponible : l'erreur est signalée mais ne stoppe pas la fonction.
if os.getenv("SKIP_DB_INIT", "0").strip() != "1" and APP_ENV not in {"test", "testing"}:
    try:
        init_db()
    except Exception as exc:
        if APP_ENV == "production":
            print(
                f"[database] Initialisation ignorée au démarrage en production: {exc}"
            )
        else:
            raise

# CORS permissif en phase de dev (index.html local + serveurs locaux).
# En production, remplacez par une liste explicite d'origines.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "*",
        "http://localhost",
        "http://localhost:5500",
        "http://127.0.0.1",
        "http://127.0.0.1:5500",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Middleware d'authentification JWT (non bloquant).
install_auth_middleware(app)

# Routes modules métier.
app.include_router(auth_router)
app.include_router(gamification_router)
app.include_router(vetscan_router)
app.include_router(audio_router)
app.include_router(reprotrack_router)
app.include_router(farmmanager_router)
app.include_router(floravet_router)
app.include_router(pasturemap_router)
app.include_router(farmcast_router)
app.include_router(community_router)
app.include_router(academy_router)
app.include_router(paiement_router)
app.include_router(notification_router)
app.include_router(gamification_live_router)
app.include_router(analytics_router)
app.include_router(marche_router)


# -----------------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------------
@app.get("/")
def racine() -> RedirectResponse:
    """Redirige la racine vers l’interface web principale."""
    return RedirectResponse(url="/app/", status_code=307)


@app.get("/sante")
@app.get("/health")
def sante() -> Dict[str, Any]:
    """
    Endpoint de santé amélioré pour supervision/ping.
    Retourne aussi l'état des principaux services applicatifs.
    """
    services = {
        "database": "ok",
        "auth": "ok",
        "gamification": "ok",
        "vetscan": "ok",
        "audio": "ok",
        "reprotrack": "ok",
        "farmcast": "ok",
        "academy": "ok",
        "paiement": "ok",
        "notifications": "ok",
        "marche": "ok",
        "frontend": "ok" if os.path.exists(frontend_path) else "absent",
    }

    return {
        "status": "ok",
        "app": APP_NAME,
        "version": APP_VERSION,
        "frontend_mount": "/app",
        "services": services,
    }


@app.get("/langues")
def langues() -> Dict[str, Any]:
    """
    Retourne la liste des langues supportées (50) depuis le fichier data.
    """
    try:
        langues_data = _load_langues_supportees()
        return {
            "total": len(langues_data),
            "langues": langues_data,
        }
    except FileNotFoundError:
        raise HTTPException(
            status_code=500, detail="Fichier langues_supportees.json introuvable."
        )
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erreur interne /langues: {exc}")


@app.get("/langues/labels/{code_langue}")
def langues_labels(code_langue: str) -> Dict[str, Any]:
    """Retourne les labels UI traduits pour une langue donnée."""
    code = _normaliser_code_langue(code_langue)
    labels = traduire_labels_interface(code)
    return {
        "langue": code,
        "labels": labels,
    }


@app.post("/traduire-texte")
def traduire_texte(payload: TraductionTexteRequest) -> Dict[str, Any]:
    """
    Traduit une liste de chaînes depuis le français vers une langue cible.
    """
    langue_cible = _normaliser_code_langue(payload.langue_cible)
    langue_source = _normaliser_code_langue(payload.langue_source)
    textes = [str(texte or "") for texte in payload.textes]
    textes_traduits = [
        _traduire_texte_interface(texte, langue_cible, langue_source)
        for texte in textes
    ]
    return {
        "langue_cible": langue_cible,
        "textes_traduits": textes_traduits,
    }


@app.post("/contact")
def contact_investisseurs(
    payload: ContactRequest, db=Depends(get_db)
) -> Dict[str, Any]:
    """Sauvegarde un message de contact dans la base de données."""
    contact = create_contact_message(
        db=db,
        nom=payload.nom,
        email=payload.email,
        organisation=payload.organisation,
        message=payload.message,
        source="investisseurs",
    )
    return {
        "status": "ok",
        "message": "Message enregistré avec succès.",
        "contact": {
            "id": contact.id,
            "nom": contact.nom,
            "email": contact.email,
            "organisation": contact.organisation,
            "date_creation": contact.date_creation.isoformat()
            if contact.date_creation
            else None,
        },
    }


@app.get("/data/rations_demo.json")
def demo_rations() -> Response:
    """Expose les rations de démonstration pour le mode hors ligne."""
    path = DATA_DIR / "rations_demo.json"
    return Response(
        content=_safe_read_text(path),
        media_type="application/json; charset=utf-8",
        headers={"Cache-Control": "no-store"},
    )


@app.get("/data/diagnostics_demo.json")
def demo_diagnostics() -> Response:
    """Expose les diagnostics de démonstration pour le mode hors ligne."""
    path = DATA_DIR / "diagnostics_demo.json"
    return Response(
        content=_safe_read_text(path),
        media_type="application/json; charset=utf-8",
        headers={"Cache-Control": "no-store"},
    )


@app.post("/generer-ration")
def generer_ration(payload: GenererRationRequest) -> Any:
    """
    Génère une ration complète.

    Pipeline:
    1) Validation (Pydantic automatique)
    2) Résolution espèce/stade et ingrédients
    3) Optimisation via NutritionEngine
    4) Narration finale via API Afri GPT-5.4
    5) Retour JSON enrichi
    """
    cache_key = _build_ration_cache_key(payload.model_dump(mode="json"))
    ration_cachee = _ration_cache_get(cache_key)
    if ration_cachee is not None:
        return ration_cachee

    debut = time.perf_counter()

    try:
        # Détection / normalisation langue
        langue_entree = payload.langue or "fr"
        langue_detectee = (
            detecter_langue(langue_entree) if len(langue_entree) > 20 else langue_entree
        )
        langue_detectee = (langue_detectee or "fr").strip().lower()

        # Résolution des codes frontend vers référentiel nutrition.
        espece_label, stade_label = _resoudre_espece_stade(
            payload.espece, payload.stade
        )

        # Nettoyage des ingrédients.
        ingredients_clean = [
            _normaliser_ingredient_utilisateur(x)
            for x in payload.ingredients_disponibles
        ]

        # Ajuste le moteur au nombre d'animaux demandé pour le calcul 7 jours.
        ENGINE.nombre_animaux_par_defaut = int(payload.nombre_animaux)

        # Optimisation ration.
        ration_calculee = ENGINE.optimiser_ration(
            ingredients_disponibles=ingredients_clean,
            espece=espece_label,
            stade=stade_label,
            objectif=payload.objectif or "equilibre",
        )

        # Recommandations pratiques.
        recommandations = ENGINE.generer_recommandations(
            ration=ration_calculee.get("composition", {}),
            espece=espece_label,
            stade=stade_label,
        )

        # Appel API Afri pour la narration finale, avec fallback local si besoin.
        texte_ration = ""
        if _peut_utiliser_api_afri():
            try:
                client = _build_afri_client()
                messages: Any = _construire_prompt_narratif(
                    langue=langue_detectee,
                    espece=espece_label,
                    stade=stade_label,
                    ingredients=ingredients_clean,
                    ration_calculee=ration_calculee,
                    recommandations=recommandations,
                    nombre_animaux=int(payload.nombre_animaux),
                )

                # Streaming SSE désactivé temporairement pour compatibilité frontend:
                # on force une réponse JSON classique.

                # Mode non-stream: réponse JSON classique optimisée.
                chat = client.chat.completions.create(
                    model=AFRI_CHAT_MODEL,
                    messages=messages,  # type: ignore[arg-type]
                    temperature=0.3,
                    max_tokens=4000,
                    top_p=0.9,
                    frequency_penalty=0.1,
                    presence_penalty=0.1,
                )
                texte_ration = _extract_chat_text(chat)
                if APP_ENV != "test" and _nutricore_missing_sections(texte_ration):
                    texte_ration = ""
            except (
                AuthenticationError,
                APITimeoutError,
                APIConnectionError,
                BadRequestError,
                OpenAIError,
            ):
                texte_ration = ""
            except HTTPException:
                raise
            except Exception:
                texte_ration = ""

        if not texte_ration:
            texte_ration = _fallback_local_ration_text(
                langue=langue_detectee,
                espece=espece_label,
                stade=stade_label,
                ingredients=ingredients_clean,
                ration_calculee=ration_calculee,
                recommandations=recommandations,
                nombre_animaux=int(payload.nombre_animaux),
            )
            if not texte_ration.strip():
                raise HTTPException(
                    status_code=502,
                    detail="Impossible de générer la narration de la ration.",
                )

        # Temps de traitement total.
        duree = round(time.perf_counter() - debut, 3)

        # Points gagnés (règle simple demandée).
        points_gagnes = 10

        result = {
            "ration": texte_ration,
            "composition": ration_calculee.get("composition", {}),
            "cout_fcfa_kg": float(ration_calculee.get("cout_fcfa_kg", 0.0)),
            "cout_7_jours": float(ration_calculee.get("cout_total_7_jours", 0.0)),
            "langue_detectee": langue_detectee,
            "points_gagnes": points_gagnes,
            "temps_generation_secondes": duree,
        }
        _ration_cache_set(cache_key, result)
        return result

    except HTTPException:
        # On propage les erreurs HTTP déjà mappées.
        raise
    except ValueError as exc:
        # Erreurs de validation métier (ingrédient inconnu, espèce/stade, etc.)
        raise HTTPException(status_code=422, detail=str(exc))
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=500, detail=f"Fichier de référence manquant: {exc}"
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Erreur interne /generer-ration: {exc}"
        )


@app.post("/transcrire-audio", response_model=TranscriptionResponse)
async def transcrire_audio(
    audio: UploadFile = File(...),
    langue: str = Form(default="auto"),
) -> Dict[str, Any]:
    """
    Endpoint de transcription audio.

    Objectif:
    - Recevoir un fichier audio depuis le frontend.
    - L'envoyer à l'API Afri STT.
    - Retourner texte + langue détectée.
    """
    # Validation fichier.
    if not audio:
        raise HTTPException(status_code=400, detail="Aucun fichier audio reçu.")

    nom_fichier = audio.filename or "audio.webm"
    content_type = (audio.content_type or "").lower()

    # Formats acceptés (liste volontairement large).
    formats_ok = {
        "audio/webm",
        "audio/wav",
        "audio/x-wav",
        "audio/mpeg",
        "audio/mp3",
        "audio/mp4",
        "audio/ogg",
        "application/octet-stream",  # certains navigateurs mobiles
    }
    if content_type and content_type not in formats_ok:
        raise HTTPException(
            status_code=415,
            detail=f"Format audio non supporté: {content_type}",
        )

    # Lecture binaire + limite taille (10 MB).
    try:
        binary = await audio.read()
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=f"Impossible de lire le fichier audio: {exc}"
        )

    if not binary:
        raise HTTPException(status_code=400, detail="Fichier audio vide.")

    if len(binary) > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=413, detail="Fichier audio trop volumineux (max 10 MB)."
        )

    # Appel API Afri STT.
    try:
        client = _build_afri_client()

        # Le SDK accepte un objet fichier-like.
        audio_buffer = io.BytesIO(binary)
        audio_buffer.name = nom_fichier

        stt_kwargs: Dict[str, Any] = {
            "model": AFRI_STT_MODEL,
            "file": audio_buffer,
        }

        # Si langue explicite (hors auto), on la transmet.
        lg = (langue or "auto").strip().lower()
        if lg and lg != "auto":
            stt_kwargs["language"] = lg

        transcription = client.audio.transcriptions.create(**stt_kwargs)

        # Extraction texte.
        texte = ""
        if hasattr(transcription, "text"):
            texte = str(transcription.text or "").strip()
        elif isinstance(transcription, dict):
            texte = str(transcription.get("text", "")).strip()

        if not texte:
            raise HTTPException(
                status_code=502, detail="Transcription vide renvoyée par l'API Afri."
            )

        # Détection langue finale.
        langue_detectee = "fr"
        if hasattr(transcription, "language"):
            langue_detectee = (
                str(getattr(transcription, "language") or "").strip().lower() or "fr"
            )
        elif isinstance(transcription, dict):
            langue_detectee = (
                str(transcription.get("language", "")).strip().lower() or "fr"
            )

        if langue_detectee == "fr" and lg != "fr":
            # Fallback heuristique local si la langue n'est pas explicitement renvoyée.
            langue_detectee = detecter_langue(texte)

        confidence = None
        if hasattr(transcription, "confidence"):
            try:
                confidence = float(getattr(transcription, "confidence"))
            except Exception:
                confidence = None

        return {
            "texte": texte,
            "langue_detectee": langue_detectee,
            "confidence": confidence,
        }

    except AuthenticationError:
        raise HTTPException(
            status_code=502, detail="Clé API Afri invalide pour la transcription."
        )
    except APITimeoutError:
        raise HTTPException(
            status_code=504, detail="Timeout API Afri pendant la transcription."
        )
    except APIConnectionError:
        raise HTTPException(
            status_code=503, detail="Impossible de joindre l'API Afri (transcription)."
        )
    except BadRequestError as exc:
        raise HTTPException(status_code=502, detail=f"Requête STT invalide: {exc}")
    except HTTPException:
        raise
    except OpenAIError as exc:
        raise HTTPException(
            status_code=502, detail=f"Erreur API Afri transcription: {exc}"
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Erreur interne /transcrire-audio: {exc}"
        )


@app.post("/audio/ration-vocale")
async def ration_vocale(payload: RationAudioRequest) -> Response:
    """
    Résume une ration puis la convertit en audio MP3.
    """
    langue_norm = _normaliser_code_langue(payload.langue)
    resume = _resumer_ration_audio(payload.ration_texte, langue_norm)

    try:
        audio_bytes = await audio_service_instance.text_to_speech(
            texte=resume,
            langue=langue_norm,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Impossible de générer l'audio de ration: {exc}",
        )

    return Response(
        content=audio_bytes,
        media_type="audio/mpeg",
        headers={
            "Content-Disposition": 'inline; filename="ration-vocale.mp3"',
            "Cache-Control": "no-store",
        },
    )


@app.get("/audio/demo/{langue}")
async def audio_demo(langue: str) -> Response:
    """
    Retourne l'audio de démonstration correspondant à la langue demandée.
    """
    langue_norm = _normaliser_code_langue(langue)
    chemin = _chemin_audio_demo(langue_norm)

    if not chemin.exists():
        try:
            if hasattr(audio_service_instance, "generer_audio_demo"):
                resultat = await audio_service_instance.generer_audio_demo(langue_norm)
                if isinstance(resultat, (bytes, bytearray)) and resultat:
                    chemin.parent.mkdir(parents=True, exist_ok=True)
                    chemin.write_bytes(bytes(resultat))
                elif isinstance(resultat, str):
                    resultat_path = Path(resultat)
                    if resultat_path.exists():
                        chemin = resultat_path
        except Exception as exc:
            raise HTTPException(
                status_code=502,
                detail=f"Impossible de générer l'audio de démonstration: {exc}",
            )

    if not chemin.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Aucun audio de démonstration disponible pour la langue '{langue_norm}'.",
        )

    return Response(
        content=chemin.read_bytes(),
        media_type="audio/mpeg",
        headers={
            "Content-Disposition": f'inline; filename="{chemin.name}"',
            "Cache-Control": "no-store",
        },
    )


# -----------------------------------------------------------------------------
# Lancement local
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    # Lancement direct pratique en développement.
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        reload=True,
    )
