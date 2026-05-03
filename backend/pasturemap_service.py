#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Service PastureMap basique de FeedFormula AI.

Fonctions principales :
- calcul simple de charge animale par hectare,
- estimation d'une charge recommandée selon l'espèce,
- recommandations de rotation des parcelles,
- analyse locale par défaut avec fallback IA optionnel.

Le but est de fournir une base stable et légère, sans dépendance
à des services de télédétection complexes pour le moment.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator

try:
    from openai import (
        APIConnectionError,
        APITimeoutError,
        AuthenticationError,
        OpenAI,
        OpenAIError,
    )
except ImportError:  # pragma: no cover - fallback si le package est absent
    OpenAI = None  # type: ignore
    APIConnectionError = Exception  # type: ignore
    APITimeoutError = Exception  # type: ignore
    AuthenticationError = Exception  # type: ignore
    OpenAIError = Exception  # type: ignore


# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
router = APIRouter(prefix="/pasturemap", tags=["PastureMap"])


try:
    from database import UserActionLog, get_db, log_user_action
except Exception:  # pragma: no cover
    try:
        from backend.database import (  # type: ignore
            UserActionLog,
            get_db,
            log_user_action,
        )
    except Exception:  # pragma: no cover
        UserActionLog = None  # type: ignore
        get_db = None  # type: ignore
        log_user_action = None  # type: ignore

AFRI_BASE_URL = (
    os.getenv("AFRI_BASE_URL")
    or os.getenv("AFRI_API_BASE_URL")
    or "https://build.lewisnote.com/v1"
).strip()
AFRI_API_KEY = (os.getenv("AFRI_API_KEY") or "").strip()
AFRI_PASTURE_MODEL = (os.getenv("AFRI_PASTURE_MODEL") or "gpt-5.5").strip()


# -----------------------------------------------------------------------------
# Schémas Pydantic
# -----------------------------------------------------------------------------
class Parcelle(BaseModel):
    """Représente une parcelle dessinée par l'éleveur."""

    nom: str = Field(..., min_length=1)
    superficie_ha: float = Field(..., gt=0)

    @field_validator("nom")
    @classmethod
    def _strip_nom(cls, value: str) -> str:
        txt = " ".join((value or "").strip().split())
        if not txt:
            raise ValueError("Nom de parcelle vide.")
        return txt


class AnalysePastureMapRequest(BaseModel):
    """Entrée principale pour l'analyse PastureMap."""

    espece: str = Field(..., min_length=1)
    nombre_animaux: int = Field(..., ge=1)
    superficie_hectares: Optional[float] = Field(default=None, gt=0)
    nombre_paddocks: Optional[int] = Field(default=None, ge=1)
    saison: Optional[str] = Field(default=None)
    langue: Optional[str] = Field(default="fr")
    parcelles: List[Parcelle] = Field(default_factory=list)
    objectif: str = Field(default="rotation équilibrée")

    @field_validator("espece")
    @classmethod
    def _strip_espece(cls, value: str) -> str:
        txt = " ".join((value or "").strip().split())
        if not txt:
            raise ValueError("Espèce obligatoire.")
        return txt


# -----------------------------------------------------------------------------
# Helpers internes
# -----------------------------------------------------------------------------
def _client() -> Optional[Any]:
    """Construit un client OpenAI si les paramètres sont disponibles."""
    if OpenAI is None or not AFRI_API_KEY:
        return None
    try:
        return OpenAI(api_key=AFRI_API_KEY, base_url=AFRI_BASE_URL)
    except Exception:
        return None


def _stocking_rate_per_ha(espece: str) -> float:
    """
    Retourne une charge recommandée indicative par hectare.

    Les valeurs sont volontairement simples et conservatrices.
    """
    e = (espece or "").lower()
    if "vache" in e or "bovin" in e:
        return 1.2
    if "chevre" in e or "chèvre" in e or "mouton" in e:
        return 8.0
    if "porc" in e:
        return 12.0
    if "poulet" in e or "pintade" in e:
        return 150.0
    if "tilapia" in e:
        return 2500.0
    return 5.0


def _rotation_recommendations(
    espece: str,
    surpaturage: bool,
    charge: float,
    charge_recommandee: float,
    total_area: float,
) -> List[str]:
    """
    Génère une liste de recommandations de rotation basées sur les données saisies.
    """
    recommandations: List[str] = []

    if surpaturage:
        recommandations.append(
            "La charge animale est trop élevée : réduisez le nombre d'animaux ou augmentez la surface disponible."
        )
    else:
        recommandations.append(
            "La charge actuelle semble acceptable, mais surveillez régulièrement la hauteur d'herbe."
        )

    if total_area < 1:
        recommandations.append(
            "La surface totale est faible : privilégiez un pâturage tournant très court et un repos prolongé."
        )
    else:
        recommandations.append(
            "Fractionnez les parcelles et laissez chaque zone en repos avant une nouvelle entrée des animaux."
        )

    if charge_recommandee <= 2:
        recommandations.append(
            "Pour les bovins, évitez une pression continue sur les mêmes zones et gardez des réserves fourragères."
        )
    elif charge_recommandee >= 8:
        recommandations.append(
            "Pour les petits ruminants, alternez les parcelles plus fréquemment pour limiter le broutage sélectif."
        )

    if "poulet" in (espece or "").lower() or "pintade" in (espece or "").lower():
        recommandations.append(
            "Pour la volaille en parcours, déplacez les zones d'accès pour préserver le couvert végétal."
        )

    recommandations.append(
        f"Charge actuelle estimée : {charge:.2f} animaux/ha ; charge recommandée : {charge_recommandee:.2f} animaux/ha."
    )
    return recommandations[:4]


def _fallback_recommendation(
    payload: AnalysePastureMapRequest,
    total_area: float,
    charge: float,
    charge_recommandee: float,
    surpaturage: bool,
) -> Dict[str, Any]:
    """Retourne une réponse locale simple si l'IA n'est pas disponible."""
    return {
        "espece": payload.espece,
        "nombre_animaux": payload.nombre_animaux,
        "superficie_totale_ha": round(total_area, 2),
        "charge_animale_ha": round(charge, 2),
        "charge_recommandee_ha": round(charge_recommandee, 2),
        "alerte_surpaturage": surpaturage,
        "parcelles": [
            {"nom": p.nom, "superficie_ha": round(p.superficie_ha, 2)}
            for p in payload.parcelles
        ],
        "rotation_recommandee": _rotation_recommendations(
            payload.espece, surpaturage, charge, charge_recommandee, total_area
        ),
        "message": (
            "Surpâturage probable" if surpaturage else "Charge animale raisonnable"
        ),
        "mode": "fallback_local",
    }


def calculer_charge_animale(
    espece: str, nombre_animaux: int, superficie: float
) -> float:
    coeffs = {
        "vache": 1.0,
        "zebu": 0.8,
        "mouton": 0.15,
        "chevre": 0.15,
        "porc": 0.25,
        "cheval": 1.25,
    }
    key = (espece or "").lower()
    coeff = next((v for k, v in coeffs.items() if k in key), 0.2)
    return round((nombre_animaux * coeff) / max(superficie, 0.01), 3)


async def analyser_paturage(
    superficie_hectares: float,
    nombre_paddocks: int,
    espece: str,
    nombre_animaux: int,
    saison: str,
    langue: str,
) -> Dict[str, Any]:
    total = max(superficie_hectares, 0.01)
    charge = calculer_charge_animale(espece, nombre_animaux, total)
    charge_recommandee = 0.5
    statut = "optimal"
    if charge > charge_recommandee * 1.25:
        statut = "surpature"
    elif charge < charge_recommandee * 0.7:
        statut = "sous-utilise"
    plan_rotation = []
    pads = max(1, int(nombre_paddocks or 1))
    for i in range(1, pads + 1):
        plan_rotation.append(
            {
                "paddock": i,
                "duree_jours": 7 if saison != "saison sèche" else 5,
                "repos_jours": 21 if saison != "saison sèche" else 30,
                "periode": saison,
            }
        )
    recommandations = _rotation_recommendations(
        espece, statut == "surpature", charge, charge_recommandee, total
    )
    alerte = "SURPÂTURAGE DÉTECTÉ" if statut == "surpature" else None
    return {
        "charge_animale_actuelle": round(charge, 3),
        "charge_recommandee": charge_recommandee,
        "statut": statut,
        "plan_rotation": plan_rotation,
        "recommandations": recommandations,
        "alerte": alerte,
        "langue": langue,
        "mode": "local",
    }


def _store_recommendation(user_id: str, payload: Dict[str, Any]) -> None:
    if log_user_action is None or not user_id:
        return
    try:
        from database import get_db as _get_db
    except Exception:
        return
    db = next(_get_db())
    try:
        log_user_action(db, user_id, "pasturemap_analysis", meta=payload)
    finally:
        try:
            db.close()
        except Exception:
            pass


# -----------------------------------------------------------------------------
# Route principale
# -----------------------------------------------------------------------------
@router.post("/analyser")
def analyser(payload: AnalysePastureMapRequest) -> Dict[str, Any]:
    """
    Analyse les pâturages saisis par l'éleveur.

    - Calcule la superficie totale,
    - estime la charge animale par hectare,
    - compare à une charge recommandée,
    - propose des recommandations de rotation.
    """
    total_area = sum(p.superficie_ha for p in payload.parcelles)
    if payload.superficie_hectares and payload.superficie_hectares > 0:
        total_area = max(total_area, payload.superficie_hectares)

    if total_area <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Ajoutez au moins une parcelle valide.",
        )

    charge = payload.nombre_animaux / max(total_area, 0.01)
    charge_recommandee = _stocking_rate_per_ha(payload.espece)
    surpaturage = charge > charge_recommandee

    client = _client()
    if client is None:
        return _fallback_recommendation(
            payload=payload,
            total_area=total_area,
            charge=charge,
            charge_recommandee=charge_recommandee,
            surpaturage=surpaturage,
        )

    try:
        prompt = (
            "Tu es un expert en gestion de pâturages tropicaux. "
            "Réponds en JSON strict et en français.\n\n"
            f"Espèce: {payload.espece}\n"
            f"Nombre d'animaux: {payload.nombre_animaux}\n"
            f"Superficie totale: {total_area:.2f} ha\n"
            f"Charge actuelle: {charge:.2f} animaux/ha\n"
            f"Charge recommandée: {charge_recommandee:.2f} animaux/ha\n"
            f"Objectif: {payload.objectif}\n"
            f"Parcelles: {json.dumps([p.model_dump() for p in payload.parcelles], ensure_ascii=False)}\n\n"
            "Retourne un JSON avec les clés suivantes : "
            "rotation_recommandee (liste), alerte_surpaturage (bool), "
            "message (texte), charge_animale_ha, charge_recommandee_ha."
        )

        response = client.chat.completions.create(
            model=AFRI_PASTURE_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "Réponds en JSON strict et en français.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=700,
        )

        content = ""
        try:
            content = response.choices[0].message.content or ""
        except Exception:
            content = ""

        data = json.loads(content) if content else {}
        if not isinstance(data, dict):
            raise ValueError("Réponse IA invalide.")

        data.setdefault("espece", payload.espece)
        data.setdefault("nombre_animaux", payload.nombre_animaux)
        data.setdefault("superficie_totale_ha", round(total_area, 2))
        data.setdefault("charge_animale_ha", round(charge, 2))
        data.setdefault("charge_recommandee_ha", round(charge_recommandee, 2))
        data.setdefault("alerte_surpaturage", surpaturage)
        data.setdefault(
            "parcelles",
            [
                {"nom": p.nom, "superficie_ha": round(p.superficie_ha, 2)}
                for p in payload.parcelles
            ],
        )
        data.setdefault("mode", "ia")

        return data

    except ValueError as exc:
        fallback = _fallback_recommendation(
            payload=payload,
            total_area=total_area,
            charge=charge,
            charge_recommandee=charge_recommandee,
            surpaturage=surpaturage,
        )
        fallback["message"] = str(exc) or fallback.get("message")
        return fallback
    except (AuthenticationError, APITimeoutError, APIConnectionError) as exc:
        fallback = _fallback_recommendation(
            payload=payload,
            total_area=total_area,
            charge=charge,
            charge_recommandee=charge_recommandee,
            surpaturage=surpaturage,
        )
        fallback["message"] = str(exc) or fallback.get("message")
        return fallback
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur PastureMap: {exc}",
        )


@router.get("/recommandations/{user_id}")
def recommandations(user_id: str, db: Any = Depends(get_db)) -> Dict[str, Any]:
    """Retourne les dernières analyses PastureMap de l'utilisateur."""
    if UserActionLog is None:
        return {"user_id": user_id, "total": 0, "recommandations": []}
    rows = (
        db.query(UserActionLog)
        .filter(
            UserActionLog.user_id == user_id,
            UserActionLog.action == "pasturemap_analysis",
        )
        .order_by(UserActionLog.created_at.desc())
        .limit(10)
        .all()
    )
    return {
        "user_id": user_id,
        "total": len(rows),
        "recommandations": [
            {
                "date": row.created_at.isoformat() if row.created_at else None,
                "meta": json.loads(row.meta_json or "{}"),
            }
            for row in rows
        ],
    }


__all__ = [
    "router",
    "AnalysePastureMapRequest",
    "Parcelle",
    "analyser_paturage",
    "calculer_charge_animale",
]
