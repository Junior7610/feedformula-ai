#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Service VetScan de FeedFormula AI.

Objectifs :
- Analyser des symptômes animaux avec une IA générative
- Analyser une photo d'animal quand une image est fournie
- Proposer un protocole de soins structuré
- Fournir des vétérinaires proches en mode simulé
- Exposer un routeur FastAPI prêt à être branché dans `main.py`

Le code est volontairement robuste :
- Fallback local si l'API IA est indisponible
- Gestion d'erreurs claire
- Commentaires en français
"""

from __future__ import annotations

import base64
import json
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

# ---------------------------------------------------------------------------
# Imports locaux robustes
# ---------------------------------------------------------------------------
try:
    from database import get_db, get_user_by_id, add_points_to_user, log_user_action
except Exception:  # pragma: no cover - fallback exécution directe
    from backend.database import get_db, get_user_by_id, add_points_to_user, log_user_action  # type: ignore


try:
    from openai import APIConnectionError, APITimeoutError, AuthenticationError, OpenAI, OpenAIError
except Exception:  # pragma: no cover - fallback si le package n'est pas installé
    OpenAI = None  # type: ignore
    APIConnectionError = Exception  # type: ignore
    APITimeoutError = Exception  # type: ignore
    AuthenticationError = Exception  # type: ignore
    OpenAIError = Exception  # type: ignore


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
AFRI_BASE_URL = (
    os.getenv("AFRI_BASE_URL")
    or os.getenv("AFRI_API_BASE_URL")
    or "https://build.lewisnote.com/v1"
)
AFRI_API_KEY = (os.getenv("AFRI_API_KEY") or "").strip()
AFRI_VETSCAN_MODEL = (os.getenv("AFRI_VETSCAN_MODEL") or "gpt-5.5").strip()
AFRI_VETSCAN_VISION_MODEL = (os.getenv("AFRI_VETSCAN_VISION_MODEL") or AFRI_VETSCAN_MODEL).strip()
AFRI_TIMEOUT_SECONDS = float(os.getenv("AFRI_TIMEOUT_SECONDS", "90"))

router = APIRouter(prefix="/vetscan", tags=["VetScan"])


# ---------------------------------------------------------------------------
# Schémas Pydantic
# ---------------------------------------------------------------------------
class VetScanDiagnoseRequest(BaseModel):
    """Données de diagnostic par symptômes."""

    espece: str = Field(..., min_length=2)
    symptomes: str = Field(..., min_length=3)
    langue: str = Field(default="fr", min_length=2)
    user_id: Optional[str] = Field(default=None)

    @field_validator("espece", "symptomes", "langue")
    @classmethod
    def _strip(cls, value: str) -> str:
        txt = (value or "").strip()
        if not txt:
            raise ValueError("Champ vide.")
        return txt


# ---------------------------------------------------------------------------
# Helpers internes
# ---------------------------------------------------------------------------
def _normalize_text(value: str) -> str:
    """Normalise un texte pour analyse."""
    if not isinstance(value, str):
        return ""
    txt = value.strip().lower()
    txt = re.sub(r"\s+", " ", txt)
    return txt


def _json_or_none(raw: str) -> Optional[Dict[str, Any]]:
    """Tente de parser une réponse JSON."""
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
    except Exception:
        return None
    return None


def _build_openai_client() -> Optional[Any]:
    """
    Construit un client OpenAI compatible.
    Retourne None si l'environnement ne permet pas l'appel IA.
    """
    if OpenAI is None or not AFRI_API_KEY:
        return None
    try:
        return OpenAI(api_key=AFRI_API_KEY, base_url=AFRI_BASE_URL)
    except Exception:
        return None


def _default_protocol_for_species(espece: str) -> List[str]:
    """Retourne un protocole de soins générique selon l'espèce."""
    s = _normalize_text(espece)
    if "poulet" in s or "volaille" in s:
        return [
            "Isoler les sujets faibles dans un box propre.",
            "Fournir de l'eau fraîche et un aliment facile à consommer.",
            "Désinfecter le matériel et surveiller la température.",
        ]
    if "vache" in s or "bovin" in s:
        return [
            "Mettre l'animal à l'ombre et vérifier l'hydratation.",
            "Contrôler l'appétit, la rumination et la température.",
            "Contacter un vétérinaire si les symptômes persistent.",
        ]
    if "chevre" in s or "mouton" in s:
        return [
            "Isoler l'animal du lot et nettoyer l'enclos.",
            "Vérifier la qualité de l'eau et des fourrages.",
            "Surveiller les selles, l'appétit et la locomotion.",
        ]
    if "porc" in s:
        return [
            "Séparer l'animal malade des autres porcs.",
            "Maintenir une litière sèche et une eau propre.",
            "Contrôler la température et l'état respiratoire.",
        ]
    return [
        "Isoler l'animal et lui offrir de l'eau propre.",
        "Nettoyer son environnement immédiatement.",
        "Surveiller l'évolution toutes les 6 à 12 heures.",
    ]


def _fallback_diagnostic(espece: str, symptomes: str, langue: str) -> Dict[str, Any]:
    """
    Fallback local lorsque l'IA n'est pas accessible.
    Retourne une structure conforme.
    """
    txt = _normalize_text(symptomes)

    urgence_keywords = [
        "sang",
        "respiration",
        "convulsion",
        "paralysie",
        "mort",
        "gonflement important",
        "abattu",
        "choc",
    ]
    warning_keywords = [
        "fièvre",
        "diarrhée",
        "toux",
        "boiter",
        "plaie",
        "perte d'appétit",
        "abattu",
        "écoulement",
    ]

    urgence_score = sum(1 for kw in urgence_keywords if kw in txt)
    warning_score = sum(1 for kw in warning_keywords if kw in txt)

    is_urgent = urgence_score >= 1 or warning_score >= 4
    scores = [0.87, 0.65, 0.45] if not is_urgent else [0.92, 0.71, 0.53]

    if is_urgent:
        noms = ["Infection sévère", "Trouble respiratoire", "Déshydratation aiguë"]
    else:
        noms = ["Trouble digestif", "Stress thermique", "Carence alimentaire"]

    protocole = _default_protocol_for_species(espece)
    decision = "urgence" if is_urgent else "autonome"
    message_urgence = (
        "⚠️ URGENCE VÉTÉRINAIRE : contactez un vétérinaire immédiatement."
        if is_urgent
        else ""
    )

    return {
        "diagnostic_1": {
            "nom": noms[0],
            "score": scores[0],
            "description": "Hypothèse principale issue du filtrage local des symptômes.",
        },
        "diagnostic_2": {
            "nom": noms[1],
            "score": scores[1],
            "description": "Hypothèse secondaire avec probabilité intermédiaire.",
        },
        "diagnostic_3": {
            "nom": noms[2],
            "score": scores[2],
            "description": "Hypothèse complémentaire pour surveillance.",
        },
        "protocole_soins": protocole,
        "decision": decision,
        "message_urgence": message_urgence,
        "langue": langue,
        "mode": "fallback_local",
    }


def _system_prompt_vetscan() -> str:
    """Construit le system prompt du service VetScan."""
    return (
        "Tu es VetScan, un assistant vétérinaire de triage pour élevage en Afrique de l'Ouest. "
        "Tu réponds en JSON STRICT, sans texte autour. "
        "Tu dois proposer 3 diagnostics différentiels, un protocole de soins en étapes, "
        "une décision finale parmi 'autonome' ou 'urgence', et un message d'urgence si besoin. "
        "Tu prends en compte l'espèce, les symptômes et la langue de réponse. "
        "Tu ne donnes pas de faux médicaments ni de dosage dangereux. "
        "Tu privilégies la prudence et l'orientation vétérinaire en cas de doute."
    )


def _format_user_prompt(espece: str, symptomes: str, langue: str) -> str:
    """Prépare le prompt utilisateur pour l'IA."""
    return (
        f"Espèce: {espece}\n"
        f"Symptômes: {symptomes}\n"
        f"Langue de réponse: {langue}\n\n"
        "Retourne un JSON avec cette structure exacte:\n"
        "{\n"
        '  "diagnostic_1": {"nom": "...", "score": 0.87, "description": "..."},\n'
        '  "diagnostic_2": {"nom": "...", "score": 0.65, "description": "..."},\n'
        '  "diagnostic_3": {"nom": "...", "score": 0.45, "description": "..."},\n'
        '  "protocole_soins": ["étape 1", "étape 2", "étape 3"],\n'
        '  "decision": "autonome" ou "urgence",\n'
        '  "message_urgence": "..."\n'
        "}\n"
        "Les scores doivent être des nombres entre 0 et 1."
    )


def _normalize_ai_payload(payload: Dict[str, Any], espece: str, langue: str) -> Dict[str, Any]:
    """Assure un format de sortie cohérent même si le modèle répond imparfaitement."""
    diag1 = payload.get("diagnostic_1") or {}
    diag2 = payload.get("diagnostic_2") or {}
    diag3 = payload.get("diagnostic_3") or {}
    protocole = payload.get("protocole_soins") or []
    if not isinstance(protocole, list):
        protocole = [str(protocole)]

    def _clean_diag(diag: Any, fallback_name: str, fallback_score: float) -> Dict[str, Any]:
        if not isinstance(diag, dict):
            diag = {}
        score = diag.get("score", fallback_score)
        try:
            score = float(score)
        except Exception:
            score = fallback_score
        return {
            "nom": str(diag.get("nom") or fallback_name),
            "score": max(0.0, min(1.0, score)),
            "description": str(diag.get("description") or ""),
        }

    decision = str(payload.get("decision") or "autonome").strip().lower()
    if decision not in {"autonome", "urgence"}:
        decision = "autonome"

    return {
        "diagnostic_1": _clean_diag(diag1, "Diagnostic principal", 0.87),
        "diagnostic_2": _clean_diag(diag2, "Diagnostic secondaire", 0.65),
        "diagnostic_3": _clean_diag(diag3, "Diagnostic complémentaire", 0.45),
        "protocole_soins": [str(x).strip() for x in protocole if str(x).strip()],
        "decision": decision,
        "message_urgence": str(payload.get("message_urgence") or ""),
        "langue": langue,
        "espece": espece,
        "mode": "ia",
    }


def _award_user_points(db: Optional[Session], user_id: Optional[str], points: int) -> None:
    """
    Attribue des points au user si possible.
    Les erreurs sont volontairement silencieuses pour ne pas casser le diagnostic.
    """
    if not db or not user_id:
        return
    try:
        add_points_to_user(db, user_id, points)
        log_user_action(db, user_id, "vetscan_diagnostic", points_awarded=points, meta={"service": "vetscan"})
    except Exception:
        # On n'interrompt jamais un diagnostic pour un problème de gamification.
        pass


# ---------------------------------------------------------------------------
# Service principal
# ---------------------------------------------------------------------------
@dataclass
class VetScanService:
    """Service métier VetScan."""

    def _client(self) -> Optional[Any]:
        """Retourne un client IA compatible ou None."""
        return _build_openai_client()

    async def analyser_symptomes(self, espece: str, symptomes: str, langue: str = "fr") -> Dict[str, Any]:
        """
        Analyse des symptômes à partir d'un texte.
        Retourne une structure de diagnostic différentielle.
        """
        espece = (espece or "").strip()
        symptomes = (symptomes or "").strip()
        langue = (langue or "fr").strip().lower()

        if not espece:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="L'espèce est obligatoire.")
        if len(symptomes) < 3:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Les symptômes sont trop courts.")

        client = self._client()
        if client is None:
            return _fallback_diagnostic(espece, symptomes, langue)

        try:
            messages = [
                {"role": "system", "content": _system_prompt_vetscan()},
                {"role": "user", "content": _format_user_prompt(espece, symptomes, langue)},
            ]

            response = client.chat.completions.create(
                model=AFRI_VETSCAN_MODEL,
                messages=messages,
                temperature=0.2,
                max_tokens=900,
            )

            content = ""
            try:
                content = response.choices[0].message.content or ""
            except Exception:
                content = ""

            payload = _json_or_none(content)
            if payload is None:
                return _fallback_diagnostic(espece, symptomes, langue)

            return _normalize_ai_payload(payload, espece, langue)

        except AuthenticationError:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Clé API VetScan invalide ou absente.")
        except APITimeoutError:
            raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="Timeout lors de l'analyse VetScan.")
        except APIConnectionError:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="API IA VetScan indisponible.")
        except OpenAIError as exc:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Erreur IA VetScan: {exc}")
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erreur interne VetScan: {exc}")

    async def analyser_photo(self, image_bytes: bytes, espece: str, langue: str = "fr") -> Dict[str, Any]:
        """
        Analyse d'une photo d'animal.
        Retourne la même structure que l'analyse des symptômes.
        """
        espece = (espece or "").strip()
        langue = (langue or "fr").strip().lower()

        if not espece:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="L'espèce est obligatoire pour l'analyse photo.")
        if not image_bytes:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Image vide ou absente.")

        client = self._client()
        if client is None:
            # Fallback très prudent : on retourne un diagnostic générique.
            return _fallback_diagnostic(espece, "Photo fournie, analyse locale de secours.", langue)

        try:
            b64 = base64.b64encode(image_bytes).decode("utf-8")
            messages = [
                {"role": "system", "content": _system_prompt_vetscan()},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                f"Analyse cette photo d'un animal de type {espece}. "
                                f"Langue de réponse: {langue}. "
                                "Retourne le même JSON structuré que pour l'analyse par symptômes."
                            ),
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{b64}"
                            },
                        },
                    ],
                },
            ]

            response = client.chat.completions.create(
                model=AFRI_VETSCAN_VISION_MODEL,
                messages=messages,
                temperature=0.2,
                max_tokens=900,
            )

            content = ""
            try:
                content = response.choices[0].message.content or ""
            except Exception:
                content = ""

            payload = _json_or_none(content)
            if payload is None:
                return _fallback_diagnostic(espece, "Photo analysée, mais réponse IA non exploitable.", langue)

            return _normalize_ai_payload(payload, espece, langue)

        except AuthenticationError:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Clé API vision VetScan invalide ou absente.")
        except APITimeoutError:
            raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="Timeout lors de l'analyse photo VetScan.")
        except APIConnectionError:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="API vision VetScan indisponible.")
        except OpenAIError as exc:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Erreur IA vision VetScan: {exc}")
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erreur interne analyse photo: {exc}")

    def trouver_veterinaire_proche(self, latitude: float, longitude: float) -> List[Dict[str, Any]]:
        """
        Retourne une liste simulée de vétérinaires proches.
        En production, ceci devrait interroger une API de cartographie.
        """
        # Données de démonstration, suffisantes pour l'interface.
        base = [
            {
                "nom": "Clinique Vétérinaire Centrale",
                "distance_km": 1.2,
                "telephone": "+229 01 00 00 00 01",
                "latitude": latitude + 0.01,
                "longitude": longitude + 0.01,
            },
            {
                "nom": "Cabinet AgroVet",
                "distance_km": 3.6,
                "telephone": "+229 01 00 00 00 02",
                "latitude": latitude - 0.02,
                "longitude": longitude + 0.02,
            },
            {
                "nom": "Urgences Élevage Plus",
                "distance_km": 7.8,
                "telephone": "+229 01 00 00 00 03",
                "latitude": latitude + 0.03,
                "longitude": longitude - 0.03,
            },
        ]
        return base


# Instance partagée
vetscan_service = VetScanService()


# ---------------------------------------------------------------------------
# Endpoints FastAPI
# ---------------------------------------------------------------------------
@router.post("/diagnostiquer")
async def diagnostiquer(
    payload: VetScanDiagnoseRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Endpoint de diagnostic VetScan basé sur les symptômes.
    """
    result = await vetscan_service.analyser_symptomes(
        espece=payload.espece,
        symptomes=payload.symptomes,
        langue=payload.langue,
    )

    # Attribution de points gamification si un user est fourni.
    _award_user_points(db, payload.user_id, 20 if result.get("decision") == "urgence" else 15)

    return {
        "message": "Diagnostic VetScan généré avec succès.",
        "resultat": result,
    }


@router.post("/analyser-photo")
async def analyser_photo_endpoint(
    image: UploadFile = File(...),
    espece: str = Form(...),
    langue: str = Form(default="fr"),
    user_id: Optional[str] = Form(default=None),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Endpoint d'analyse de photo VetScan.
    """
    if image is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Aucune image reçue.")

    contenu = await image.read()
    if not contenu:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Image vide ou invalide.")

    result = await vetscan_service.analyser_photo(
        image_bytes=contenu,
        espece=espece,
        langue=langue,
    )

    _award_user_points(db, user_id, 20 if result.get("decision") == "urgence" else 15)

    return {
        "message": "Analyse photo VetScan générée avec succès.",
        "resultat": result,
    }


@router.get("/veterinaires-proches")
def veterinaires_proches(
    latitude: float,
    longitude: float,
) -> Dict[str, Any]:
    """
    Fournit une liste simulée de vétérinaires proches.
    """
    return {
        "latitude": latitude,
        "longitude": longitude,
        "veterinaires": vetscan_service.trouver_veterinaire_proche(latitude, longitude),
    }


__all__ = [
    "VetScanService",
    "vetscan_service",
    "router",
]
