#!/usr/bin/env python3
# -*- coding: utf-8 -*-

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

import io
import json
import os
import re
import time
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

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


# -----------------------------------------------------------------------------
# Imports locaux (compatibles exécution directe et package)
# -----------------------------------------------------------------------------
try:
    # Mode package: python -m backend.main
    from .langue_detector import detecter_langue, get_prompt_pour_langue
    from .nutrition_engine import NutritionEngine
    from .database import init_db
    from .auth import install_auth_middleware, router as auth_router
    from .gamification_api import router as gamification_router
except Exception:
    # Mode script: python backend/main.py
    from langue_detector import detecter_langue, get_prompt_pour_langue
    from nutrition_engine import NutritionEngine
    from database import init_db
    from auth import install_auth_middleware, router as auth_router
    from gamification_api import router as gamification_router


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

AFRI_BASE_URL = (
    os.getenv("AFRI_BASE_URL")
    or os.getenv("AFRI_API_BASE_URL")
    or "https://build.lewisnote.com/v1"
)
AFRI_API_KEY = os.getenv("AFRI_API_KEY", "").strip()
AFRI_CHAT_MODEL = os.getenv("AFRI_CHAT_MODEL", "gpt-5.4").strip()
AFRI_STT_MODEL = os.getenv("AFRI_STT_MODEL", "gpt-4o-mini-transcribe").strip()
AFRI_TIMEOUT_SECONDS = float(os.getenv("AFRI_TIMEOUT_SECONDS", "90"))

SYSTEM_PROMPT_PATH = PROMPTS_DIR / "system_prompt_principal.txt"
LANGUES_PATH = DATA_DIR / "langues_supportees.json"

# Instance moteur nutrition (réutilisée entre requêtes).
ENGINE = NutritionEngine(data_dir=DATA_DIR, nombre_animaux_par_defaut=1)


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

    # Prompt système compact pour limiter les tokens tout en gardant la qualité.
    prompt_system_concis = (
        "Tu es Aya de FeedFormula AI. "
        "Réponds dans la langue détectée, en style terrain clair, phrases courtes, "
        "sans texte inutile. Respecte exactement le format demandé, avec les séparateurs."
    )

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
        "Utilise EXACTEMENT ce format:\n"
        "🌾 RATION FEEDFORMULA AI\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "📋 Espèce : [nom complet]\n"
        "📅 Stade : [stade précis]\n"
        "🔢 Nombre : [nombre] animaux\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "📦 COMPOSITION (pour 100 kg)\n"
        "- [Ingrédient] .... [X] kg ([X]%)\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🔬 VALEUR NUTRITIVE\n"
        "- Énergie : [X] kcal/kg\n"
        "- Protéines : [X]%\n"
        "- Calcium : [X]%\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "💰 COÛT\n"
        "- Par kg : [X] FCFA\n"
        "- 7 jours : [X] FCFA\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "📈 PERFORMANCES ATTENDUES\n"
        "[Description]\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "⚠️ POINTS D'ATTENTION\n"
        "[Carences et corrections]\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "💡 CONSEILS PRATIQUES\n"
        "- [Conseil 1]\n"
        "- [Conseil 2]\n"
        "- [Conseil 3]\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🌽 Aya t'accompagne pas à pas !"
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


# -----------------------------------------------------------------------------
# Initialisation FastAPI
# -----------------------------------------------------------------------------
app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description="API backend NutriCore (ration + narration IA + langues + transcription).",
)

# Initialisation base de données au démarrage.
init_db()

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

# Routes modules Auth et Gamification.
app.include_router(auth_router)
app.include_router(gamification_router)


# -----------------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------------
@app.get("/sante")
def sante() -> Dict[str, str]:
    """
    Endpoint de santé simple pour supervision/ping.
    """
    return {"status": "ok", "app": APP_NAME, "version": APP_VERSION}


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

        # Appel API Afri pour la narration finale.
        try:
            client = _build_afri_client()
            messages = _construire_prompt_narratif(
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
                messages=messages,
                temperature=0.1,
                max_tokens=700,
            )
            texte_ration = _extract_chat_text(chat)

            if not texte_ration:
                raise HTTPException(
                    status_code=502,
                    detail="Réponse vide renvoyée par l'API Afri (narration).",
                )

        except AuthenticationError:
            raise HTTPException(
                status_code=502, detail="Clé API Afri invalide ou non autorisée."
            )
        except APITimeoutError:
            raise HTTPException(
                status_code=504,
                detail="Timeout API Afri pendant la génération narrative.",
            )
        except APIConnectionError:
            raise HTTPException(
                status_code=503, detail="Impossible de joindre l'API Afri (connexion)."
            )
        except BadRequestError as exc:
            raise HTTPException(status_code=502, detail=f"Requête Afri invalide: {exc}")
        except HTTPException:
            raise
        except OpenAIError as exc:
            raise HTTPException(status_code=502, detail=f"Erreur API Afri: {exc}")
        except Exception as exc:
            raise HTTPException(
                status_code=500, detail=f"Erreur interne narration IA: {exc}"
            )

        # Temps de traitement total.
        duree = round(time.perf_counter() - debut, 3)

        # Points gagnés (règle simple demandée).
        points_gagnes = 10

        return {
            "ration": texte_ration,
            "composition": ration_calculee.get("composition", {}),
            "cout_fcfa_kg": float(ration_calculee.get("cout_fcfa_kg", 0.0)),
            "cout_7_jours": float(ration_calculee.get("cout_total_7_jours", 0.0)),
            "langue_detectee": langue_detectee,
            "points_gagnes": points_gagnes,
            "temps_generation_secondes": duree,
        }

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
