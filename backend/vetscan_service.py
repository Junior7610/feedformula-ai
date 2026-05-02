#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Service VetScan de FeedFormula AI.

Fonctions :
- analyse des symptômes par GPT 5.5 avec retour JSON strict
- analyse visuelle d'une photo d'animal
- fallback local prudent si l'API IA est indisponible
- routeur FastAPI prêt à intégrer dans `main.py`

Le service répond toujours dans la langue demandée par l'éleveur.
"""

from __future__ import annotations

import base64
import json
import os
import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

# -----------------------------------------------------------------------------
# Imports locaux robustes
# -----------------------------------------------------------------------------
try:
    from database import add_points_to_user, get_db, get_user_by_id, log_user_action
except Exception:  # pragma: no cover
    try:
        from backend.database import (  # type: ignore
            add_points_to_user,
            get_db,
            get_user_by_id,
            log_user_action,
        )
    except Exception:  # pragma: no cover
        add_points_to_user = None  # type: ignore
        log_user_action = None  # type: ignore
        get_db = None  # type: ignore
        get_user_by_id = None  # type: ignore


try:
    from openai import (
        APIConnectionError,
        APITimeoutError,
        AuthenticationError,
        OpenAI,
        OpenAIError,
    )
except Exception:  # pragma: no cover
    OpenAI = None  # type: ignore
    APIConnectionError = Exception  # type: ignore
    APITimeoutError = Exception  # type: ignore
    AuthenticationError = Exception  # type: ignore
    OpenAIError = Exception  # type: ignore


# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
AFRI_BASE_URL = (
    os.getenv("AFRI_BASE_URL")
    or os.getenv("AFRI_API_BASE_URL")
    or "https://build.lewisnote.com/v1"
).strip()
AFRI_API_KEY = (os.getenv("AFRI_API_KEY") or "").strip()
AFRI_VETSCAN_MODEL = (os.getenv("AFRI_VETSCAN_MODEL") or "gpt-5.5").strip()
AFRI_VETSCAN_VISION_MODEL = (
    os.getenv("AFRI_VETSCAN_VISION_MODEL") or AFRI_VETSCAN_MODEL
).strip()

router = APIRouter(prefix="/vetscan", tags=["VetScan"])


# -----------------------------------------------------------------------------
# Schémas Pydantic
# -----------------------------------------------------------------------------
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


# -----------------------------------------------------------------------------
# Helpers internes
# -----------------------------------------------------------------------------
def _strip_accents(value: str) -> str:
    if not isinstance(value, str):
        return ""
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def _normalize_text(value: str) -> str:
    """Normalise un texte pour l'analyse."""
    if not isinstance(value, str):
        return ""
    txt = _strip_accents(value).lower()
    txt = re.sub(r"\s+", " ", txt)
    return txt.strip()


def _extract_json_object(raw: str) -> Optional[str]:
    """
    Tente d'extraire un bloc JSON depuis une réponse IA,
    même si elle est entourée de texte ou de balises Markdown.
    """
    if not isinstance(raw, str):
        return None

    candidate = raw.strip()
    if not candidate:
        return None

    # Enlève d'éventuels blocs ```json ... ```
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", candidate, flags=re.S)
    if fenced:
        return fenced.group(1)

    # Cherche le premier objet JSON équilibré approximativement.
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start != -1 and end != -1 and end > start:
        return candidate[start : end + 1]

    return None


def _json_or_none(raw: str) -> Optional[Dict[str, Any]]:
    """Tente de parser une réponse JSON."""
    try:
        extracted = _extract_json_object(raw) or raw
        data = json.loads(extracted)
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
            "Isoler immédiatement les sujets atteints.",
            "Fournir de l'eau propre et un aliment facile à consommer.",
            "Désinfecter le matériel et surveiller l'évolution deux fois par jour.",
        ]
    if "vache" in s or "bovin" in s:
        return [
            "Mettre l'animal à l'ombre et vérifier l'hydratation.",
            "Contrôler la température, l'appétit et la rumination.",
            "Contacter un vétérinaire si les signes persistent ou s'aggravent.",
        ]
    if "chevre" in s or "chèvre" in s or "mouton" in s:
        return [
            "Isoler l'animal et nettoyer l'enclos.",
            "Vérifier la qualité de l'eau, des fourrages et de la litière.",
            "Observer les selles, la locomotion et l'appétit pendant 24 h.",
        ]
    if "porc" in s:
        return [
            "Séparer l'animal malade des autres porcs.",
            "Maintenir une litière sèche et une eau propre.",
            "Surveiller la température et la respiration.",
        ]
    return [
        "Isoler l'animal dans un espace calme.",
        "Lui donner de l'eau propre et un abri ventilé.",
        "Surveiller l'évolution toutes les 6 à 12 heures.",
    ]


def _fallback_diagnostic(espece: str, symptomes: str, langue: str) -> Dict[str, Any]:
    """
    Fallback local lorsque l'IA n'est pas accessible.
    Retourne une structure conforme au contrat JSON demandé.
    """
    txt = _normalize_text(symptomes)

    urgence_keywords = [
        "sang",
        "respiration",
        "convulsion",
        "paralysie",
        "mort",
        "gonflement important",
        "choc",
        "abattu",
        "inconscient",
    ]
    warning_keywords = [
        "fièvre",
        "fievre",
        "diarrhée",
        "diarrhee",
        "toux",
        "boiter",
        "plaie",
        "perte d'appétit",
        "perte appetit",
        "déshydrat",
        "deshydrat",
        "abattu",
        "écoulement",
    ]

    urgence_score = sum(1 for kw in urgence_keywords if kw in txt)
    warning_score = sum(1 for kw in warning_keywords if kw in txt)
    urgent = urgence_score >= 1 or warning_score >= 4

    if urgent:
        diagnostics = [
            ("Infection sévère", 0.92, "Suspicion prioritaire avec risque vital."),
            (
                "Trouble respiratoire",
                0.74,
                "Signes compatibles avec une atteinte respiratoire.",
            ),
            (
                "Déshydratation aiguë",
                0.58,
                "État général possiblement compromis.",
            ),
        ]
    else:
        diagnostics = [
            (
                "Trouble digestif",
                0.86,
                "Hypothèse fréquente lorsque l'animal mange moins ou présente des selles anormales.",
            ),
            (
                "Stress thermique",
                0.64,
                "Possible si chaleur, halètement ou abattement.",
            ),
            (
                "Carence alimentaire",
                0.49,
                "À envisager si ration inadaptée ou croissance lente.",
            ),
        ]

    protocol = _default_protocol_for_species(espece)
    decision = "urgence" if urgent else "autonome"
    message = (
        "⚠️ URGENCE VÉTÉRINAIRE : contactez un vétérinaire immédiatement."
        if urgent
        else "Surveillance rapprochée et soins de base possibles à domicile."
    )

    symptomes_correspondants_1 = [
        s for s in ["fièvre", "abattement", "perte d'appétit", "diarrhée"] if s in txt
    ]
    symptomes_correspondants_2 = [
        s
        for s in ["toux", "respiration difficile", "halètement", "écoulement"]
        if s in txt
    ]
    symptomes_correspondants_3 = [
        s
        for s in ["boiterie", "déshydratation", "amaigrissement", "faiblesse"]
        if s in txt
    ]

    return {
        "diagnostic_1": {
            "nom": diagnostics[0][0],
            "probabilite": diagnostics[0][1],
            "description": diagnostics[0][2],
            "symptomes_correspondants": symptomes_correspondants_1,
        },
        "diagnostic_2": {
            "nom": diagnostics[1][0],
            "probabilite": diagnostics[1][1],
            "description": diagnostics[1][2],
            "symptomes_correspondants": symptomes_correspondants_2,
        },
        "diagnostic_3": {
            "nom": diagnostics[2][0],
            "probabilite": diagnostics[2][1],
            "description": diagnostics[2][2],
            "symptomes_correspondants": symptomes_correspondants_3,
        },
        "protocole_soins": protocol,
        "decision": decision,
        "message_urgence": message if urgent else "",
        "prevention": (
            "Assurez une eau propre, une hygiène régulière, une alimentation équilibrée et surveillez les signes précoces."
            if not urgent
            else "Isolez les animaux malades, limitez les contacts et consultez rapidement pour éviter la propagation."
        ),
        "langue": langue,
        "espece": espece,
        "mode": "fallback_local",
    }


def _system_prompt_vetscan() -> str:
    """System prompt spécialisé VetScan."""
    return (
        "Tu es un vétérinaire expert en pathologies animales tropicales africaines. "
        "Tu analyses les symptômes décrits et génères un diagnostic différentiel probabiliste avec 3 diagnostics classés par probabilité. "
        "Tu proposes un protocole de soins étape par étape. "
        "Tu décides clairement : soins autonomes ou urgence. "
        "Tu réponds toujours dans la langue de l'éleveur. "
        "Tu réponds en JSON STRICT sans texte autour. "
        "Format exact attendu : "
        "{"
        '"diagnostic_1":{"nom":"...","probabilite":0.87,"description":"...","symptomes_correspondants":["..."]},'
        '"diagnostic_2":{...},'
        '"diagnostic_3":{...},'
        '"protocole_soins":["..."],'
        '"decision":"autonome|urgence",'
        '"message_urgence":"...",'
        '"prevention":"..."'
        "}"
    )


def _format_user_prompt(espece: str, symptomes: str, langue: str) -> str:
    """Prépare le prompt utilisateur pour le modèle."""
    return (
        f"Espèce: {espece}\n"
        f"Symptômes: {symptomes}\n"
        f"Langue de réponse: {langue}\n\n"
        "Retourne un JSON strict avec 3 diagnostics différentiels classés par probabilité."
    )


def _normalize_ai_payload(
    payload: Dict[str, Any], espece: str, langue: str
) -> Dict[str, Any]:
    """Assure un format de sortie cohérent même si le modèle répond imparfaitement."""

    def _clean_diag(
        diag: Any, fallback_name: str, fallback_prob: float
    ) -> Dict[str, Any]:
        if not isinstance(diag, dict):
            diag = {}

        prob = diag.get(
            "probabilite", diag.get("probability", diag.get("score", fallback_prob))
        )
        try:
            prob = float(prob)
        except Exception:
            prob = fallback_prob

        syms = diag.get("symptomes_correspondants") or []
        if not isinstance(syms, list):
            syms = [str(syms)]

        return {
            "nom": str(diag.get("nom") or fallback_name),
            "probabilite": max(0.0, min(1.0, prob)),
            "description": str(diag.get("description") or ""),
            "symptomes_correspondants": [
                str(x).strip() for x in syms if str(x).strip()
            ],
        }

    protocol = payload.get("protocole_soins") or payload.get("protocol") or []
    if not isinstance(protocol, list):
        protocol = [str(protocol)]

    decision = str(payload.get("decision") or "autonome").strip().lower()
    if decision not in {"autonome", "urgence"}:
        decision = "autonome"

    return {
        "diagnostic_1": _clean_diag(
            payload.get("diagnostic_1"), "Diagnostic principal", 0.87
        ),
        "diagnostic_2": _clean_diag(
            payload.get("diagnostic_2"), "Diagnostic secondaire", 0.65
        ),
        "diagnostic_3": _clean_diag(
            payload.get("diagnostic_3"), "Diagnostic complémentaire", 0.45
        ),
        "protocole_soins": [str(x).strip() for x in protocol if str(x).strip()],
        "decision": decision,
        "message_urgence": str(payload.get("message_urgence") or ""),
        "prevention": str(payload.get("prevention") or ""),
        "langue": langue,
        "espece": espece,
        "mode": "ia",
    }


def _award_user_points(
    db: Optional[Session], user_id: Optional[str], points: int
) -> None:
    """
    Attribue des points au user si possible.
    Les erreurs sont volontairement silencieuses pour ne pas casser le diagnostic.
    """
    if not db or not user_id:
        return
    try:
        if get_user_by_id is not None and get_user_by_id(db, user_id) is None:
            return
        if add_points_to_user is not None:
            add_points_to_user(db, user_id, points)
        if log_user_action is not None:
            log_user_action(
                db,
                user_id,
                "vetscan_diagnostic",
                points_awarded=points,
                meta={"service": "vetscan"},
            )
    except Exception:
        # On n'interrompt jamais un diagnostic pour un problème de gamification.
        pass


# -----------------------------------------------------------------------------
# Service principal
# -----------------------------------------------------------------------------
@dataclass
class VetScanService:
    """Service métier VetScan."""

    def _client(self) -> Optional[Any]:
        """Retourne un client IA compatible ou None."""
        return _build_openai_client()

    async def analyser_symptomes(
        self, espece: str, symptomes: str, langue: str = "fr"
    ) -> Dict[str, Any]:
        """
        Analyse des symptômes à partir d'un texte.
        Retourne une structure de diagnostic différentiel.
        """
        espece = (espece or "").strip()
        symptomes = (symptomes or "").strip()
        langue = (langue or "fr").strip().lower()

        if not espece:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="L'espèce est obligatoire.",
            )
        if len(symptomes) < 3:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Les symptômes sont trop courts.",
            )

        client = self._client()
        if client is None:
            return _fallback_diagnostic(espece, symptomes, langue)

        try:
            messages = [
                {"role": "system", "content": _system_prompt_vetscan()},
                {
                    "role": "user",
                    "content": _format_user_prompt(espece, symptomes, langue),
                },
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
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Clé API VetScan invalide ou absente.",
            )
        except APITimeoutError:
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="Timeout lors de l'analyse VetScan.",
            )
        except APIConnectionError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="API IA VetScan indisponible.",
            )
        except OpenAIError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Erreur IA VetScan: {exc}",
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Erreur interne VetScan: {exc}",
            )

    async def analyser_photo(
        self, image_bytes: bytes, espece: str, langue: str = "fr"
    ) -> Dict[str, Any]:
        """
        Analyse d'une photo d'animal.
        Retourne la même structure que l'analyse des symptômes.
        """
        espece = (espece or "").strip()
        langue = (langue or "fr").strip().lower()

        if not espece:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="L'espèce est obligatoire pour l'analyse photo.",
            )
        if not image_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Image vide ou absente.",
            )

        client = self._client()
        if client is None:
            # Fallback très prudent : on retourne un diagnostic générique.
            return _fallback_diagnostic(
                espece, "Photo fournie, analyse locale de secours.", langue
            )

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
                                f"Analyse visuellement cette photo d'un animal de type {espece}. "
                                f"Langue de réponse: {langue}. "
                                "Retourne le même JSON structuré que pour l'analyse par symptômes."
                            ),
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
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
                return _fallback_diagnostic(
                    espece, "Photo analysée, mais réponse IA non exploitable.", langue
                )

            return _normalize_ai_payload(payload, espece, langue)

        except AuthenticationError:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Clé API vision VetScan invalide ou absente.",
            )
        except APITimeoutError:
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="Timeout lors de l'analyse photo VetScan.",
            )
        except APIConnectionError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="API vision VetScan indisponible.",
            )
        except OpenAIError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Erreur IA vision VetScan: {exc}",
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Erreur interne analyse photo: {exc}",
            )

    def trouver_veterinaire_proche(
        self, latitude: float, longitude: float
    ) -> List[Dict[str, Any]]:
        """
        Retourne une liste simulée de vétérinaires proches.
        En production, ceci devrait interroger une API de cartographie.
        """
        return [
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


# Instance partagée
vetscan_service = VetScanService()


# -----------------------------------------------------------------------------
# Endpoints FastAPI
# -----------------------------------------------------------------------------
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
    _award_user_points(
        db,
        payload.user_id,
        20 if result.get("decision") == "urgence" else 15,
    )

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
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Aucune image reçue."
        )

    contenu = await image.read()
    if not contenu:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Image vide ou invalide."
        )

    result = await vetscan_service.analyser_photo(
        image_bytes=contenu,
        espece=espece,
        langue=langue,
    )

    _award_user_points(
        db,
        user_id,
        20 if result.get("decision") == "urgence" else 15,
    )

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
