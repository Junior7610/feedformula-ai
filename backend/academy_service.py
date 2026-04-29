#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Service FarmAcademy de FeedFormula AI.

Objectifs :
- Exposer le catalogue des formations
- Fournir une leçon détaillée
- Générer un quiz simple pour chaque formation
- Fournir un routeur FastAPI prêt à être branché dans `main.py`

Le module privilégie :
- des structures simples et lisibles
- des réponses JSON stables pour le frontend
- des libellés en français
- un mode MVP sans dépendance externe obligatoire
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field, field_validator


# -----------------------------------------------------------------------------
# Routeur FastAPI
# -----------------------------------------------------------------------------
router = APIRouter(prefix="/academy", tags=["FarmAcademy"])


# -----------------------------------------------------------------------------
# Données pédagogiques
# -----------------------------------------------------------------------------
ACADEMY_FORMATIONS: List[Dict[str, Any]] = [
    {
        "id": "volailles",
        "titre": "Alimentation des volailles",
        "niveau": "Débutant",
        "duree": "5 leçons",
        "icone": "🐔",
        "resume": "Comprendre l'énergie, les protéines et les bonnes pratiques pour poulets et pondeuses.",
        "lecons": [
            {
                "id": "volailles-1",
                "titre": "Bases énergétiques",
                "contenu": (
                    "Les volailles ont besoin d'une énergie stable, d'une eau propre et d'un aliment "
                    "facile à consommer. Le maïs reste une base fréquente dans les rations."
                ),
                "quiz": [
                    {
                        "question": "Quel ingrédient apporte souvent l'énergie principale ?",
                        "choix": ["Maïs", "Sable", "Pierre"],
                        "bonne_reponse": 0,
                    }
                ],
            },
            {
                "id": "volailles-2",
                "titre": "Sources de protéines",
                "contenu": (
                    "Le soja, la farine de poisson et certains tourteaux améliorent la croissance "
                    "et la production d'œufs."
                ),
                "quiz": [
                    {
                        "question": "Quelle source est riche en protéines ?",
                        "choix": ["Soja", "Eau", "Paille"],
                        "bonne_reponse": 0,
                    }
                ],
            },
        ],
    },
    {
        "id": "bovins",
        "titre": "Santé bovine",
        "niveau": "Intermédiaire",
        "duree": "4 leçons",
        "icone": "🐄",
        "resume": "Observer l'appétit, la rumination et les signes d'alerte chez les bovins.",
        "lecons": [
            {
                "id": "bovins-1",
                "titre": "Observation quotidienne",
                "contenu": (
                    "Un bovin doit être observé chaque jour pour détecter les changements de comportement, "
                    "de consommation d'eau ou d'alimentation."
                ),
                "quiz": [
                    {
                        "question": "Que faut-il observer en priorité ?",
                        "choix": ["Comportement", "Téléphone", "Chaussures"],
                        "bonne_reponse": 0,
                    }
                ],
            }
        ],
    },
    {
        "id": "reproduction",
        "titre": "Gestion de la reproduction",
        "niveau": "Intermédiaire",
        "duree": "3 leçons",
        "icone": "🩷",
        "resume": "Suivre les chaleurs, les saillies, les gestations et les mises-bas.",
        "lecons": [
            {
                "id": "repro-1",
                "titre": "Cycles et planification",
                "contenu": (
                    "Le suivi des cycles améliore la fertilité et permet de mieux prévoir les périodes "
                    "de saillie et de mise-bas."
                ),
                "quiz": [
                    {
                        "question": "La reproduction concerne surtout ?",
                        "choix": ["Cycles", "Couleurs", "Prix"],
                        "bonne_reponse": 0,
                    }
                ],
            }
        ],
    },
    {
        "id": "finance",
        "titre": "Finance agricole",
        "niveau": "Débutant",
        "duree": "3 leçons",
        "icone": "💰",
        "resume": "Apprendre à calculer une marge, suivre les coûts et prendre de meilleures décisions.",
        "lecons": [
            {
                "id": "finance-1",
                "titre": "Calcul des marges",
                "contenu": (
                    "La marge correspond généralement au prix de vente moins les coûts. "
                    "Suivre cette valeur aide à améliorer la rentabilité."
                ),
                "quiz": [
                    {
                        "question": "La marge est égale à ?",
                        "choix": ["Vente - coût", "Coût + impôt", "Prix × 2"],
                        "bonne_reponse": 0,
                    }
                ],
            }
        ],
    },
    {
        "id": "paturage",
        "titre": "Pâturages durables",
        "niveau": "Avancé",
        "duree": "3 leçons",
        "icone": "🌿",
        "resume": "Préserver les sols, gérer la rotation et réduire la pression sur les pâturages.",
        "lecons": [
            {
                "id": "pat-1",
                "titre": "Rotation des parcelles",
                "contenu": (
                    "La rotation des pâturages aide à préserver la végétation, limiter l'érosion "
                    "et répartir la pression de pâture."
                ),
                "quiz": [
                    {
                        "question": "La rotation sert à ?",
                        "choix": ["Préserver", "Casser", "Vendre"],
                        "bonne_reponse": 0,
                    }
                ],
            }
        ],
    },
]


# -----------------------------------------------------------------------------
# Utilitaires
# -----------------------------------------------------------------------------
def _trouver_formation(formation_id: str) -> Dict[str, Any]:
    """Retourne une formation par identifiant ou lève une erreur 404."""
    fid = (formation_id or "").strip().lower()
    if not fid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="L'identifiant de formation est obligatoire.",
        )

    for formation in ACADEMY_FORMATIONS:
        if formation["id"] == fid:
            return formation

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Formation introuvable.",
    )


def _trouver_lecon(formation: Dict[str, Any], lesson_id: Optional[str] = None, index: Optional[int] = None) -> Dict[str, Any]:
    """Retourne une leçon d'une formation."""
    lecons = formation.get("lecons", [])
    if not lecons:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aucune leçon disponible pour cette formation.",
        )

    if lesson_id:
        lid = lesson_id.strip().lower()
        for lecon in lecons:
            if lecon.get("id", "").lower() == lid:
                return lecon
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Leçon introuvable.",
        )

    if index is None:
        index = 0

    if index < 0 or index >= len(lecons):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Index de leçon invalide.",
        )

    return lecons[index]


def _quiz_pour_lecon(lecon: Dict[str, Any]) -> Dict[str, Any]:
    """Construit un quiz compatible frontend."""
    quiz = lecon.get("quiz", [])
    return {
        "lesson_id": lecon.get("id"),
        "titre": lecon.get("titre"),
        "total_questions": len(quiz),
        "questions": quiz,
    }


# -----------------------------------------------------------------------------
# Schémas Pydantic
# -----------------------------------------------------------------------------
class AcademyLessonRequest(BaseModel):
    """Entrée du endpoint /academy/lecon."""

    formation_id: str = Field(..., min_length=2, description="Identifiant de la formation")
    lesson_id: Optional[str] = Field(default=None, description="Identifiant de la leçon")
    lesson_index: Optional[int] = Field(default=None, ge=0, description="Index de la leçon")

    @field_validator("formation_id", "lesson_id")
    @classmethod
    def _strip(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        txt = value.strip()
        return txt or None


class AcademyQuizRequest(BaseModel):
    """Entrée du endpoint /academy/quiz."""

    formation_id: str = Field(..., min_length=2, description="Identifiant de la formation")
    lesson_id: Optional[str] = Field(default=None, description="Identifiant de la leçon")
    lesson_index: Optional[int] = Field(default=None, ge=0, description="Index de la leçon")

    @field_validator("formation_id", "lesson_id")
    @classmethod
    def _strip(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        txt = value.strip()
        return txt or None


# -----------------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------------
@router.get("/formations")
def lire_formations() -> Dict[str, Any]:
    """
    Retourne le catalogue complet des formations FarmAcademy.
    """
    return {
        "total": len(ACADEMY_FORMATIONS),
        "formations": [
            {
                "id": formation["id"],
                "titre": formation["titre"],
                "niveau": formation["niveau"],
                "duree": formation["duree"],
                "icone": formation["icone"],
                "resume": formation["resume"],
                "total_lecons": len(formation.get("lecons", [])),
            }
            for formation in ACADEMY_FORMATIONS
        ],
    }


@router.post("/lecon")
def lire_lecon(payload: AcademyLessonRequest) -> Dict[str, Any]:
    """
    Retourne le détail d'une leçon FarmAcademy.
    """
    formation = _trouver_formation(payload.formation_id)
    lecon = _trouver_lecon(
        formation=formation,
        lesson_id=payload.lesson_id,
        index=payload.lesson_index,
    )

    return {
        "formation": {
            "id": formation["id"],
            "titre": formation["titre"],
            "niveau": formation["niveau"],
            "duree": formation["duree"],
            "icone": formation["icone"],
        },
        "lecon": {
            "id": lecon.get("id"),
            "titre": lecon.get("titre"),
            "contenu": lecon.get("contenu"),
        },
        "progression": {
            "total_lecons": len(formation.get("lecons", [])),
            "lecon_courante": (
                next(
                    (i for i, item in enumerate(formation.get("lecons", [])) if item.get("id") == lecon.get("id")),
                    0,
                )
                + 1
            ),
        },
    }


@router.post("/quiz")
def lire_quiz(payload: AcademyQuizRequest) -> Dict[str, Any]:
    """
    Retourne le quiz associé à une formation ou à une leçon précise.
    """
    formation = _trouver_formation(payload.formation_id)
    lecon = _trouver_lecon(
        formation=formation,
        lesson_id=payload.lesson_id,
        index=payload.lesson_index,
    )

    return {
        "formation_id": formation["id"],
        "formation_titre": formation["titre"],
        "quiz": _quiz_pour_lecon(lecon),
    }


@router.get("/formations/{formation_id}")
def lire_formation(formation_id: str) -> Dict[str, Any]:
    """
    Retourne une formation détaillée avec l'ensemble de ses leçons.
    """
    formation = _trouver_formation(formation_id)
    return {
        "id": formation["id"],
        "titre": formation["titre"],
        "niveau": formation["niveau"],
        "duree": formation["duree"],
        "icone": formation["icone"],
        "resume": formation["resume"],
        "lecons": [
            {
                "id": lecon.get("id"),
                "titre": lecon.get("titre"),
                "contenu": lecon.get("contenu"),
            }
            for lecon in formation.get("lecons", [])
        ],
    }


__all__ = [
    "router",
    "ACADEMY_FORMATIONS",
    "AcademyLessonRequest",
    "AcademyQuizRequest",
]
