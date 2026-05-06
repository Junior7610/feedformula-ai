#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pyright: reportGeneralTypeIssues=false, reportArgumentType=false, reportAssignmentType=false, reportReturnType=false, reportAttributeAccessIssue=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownVariableType=false
"""FarmAcademy de FeedFormula AI.

Catalogue de 5 formations, 18 leçons, génération dynamique via GPT 5.5
lorsqu'une clé est disponible, sinon fallback pédagogique local.

Compatibilité:
- Anciennes routes avec tirets
- Nouvelles routes avec underscores
- Body du quiz: user_id, formation_code, lecon_numero, reponses, langue
"""

from __future__ import annotations

import io
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, cast

from database import (
    add_points_to_user,
    create_formation_completee,
    get_db,
    get_user_by_id,
    list_user_formations_completees,
    serialize_formation_completee,
)
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from sqlalchemy.orm import Session

router = APIRouter(prefix="/academy", tags=["FarmAcademy"])

ROOT_DIR = Path(__file__).resolve().parent.parent
APP_ENV = (os.getenv("APP_ENV", "development") or "development").strip().lower()
DATA_DIR = ROOT_DIR / "data"

# En production sur Vercel, le code est déployé sur un système de fichiers en lecture seule.
# On bascule donc les fichiers générés vers un dossier temporaire inscriptible.
if APP_ENV == "production":
    BASE_STORAGE_DIR = Path(tempfile.gettempdir()) / "feedformula_ai"
else:
    BASE_STORAGE_DIR = DATA_DIR

CERTIFICATS_DIR = BASE_STORAGE_DIR / "academy_certificats"
CERTIFICATS_DIR.mkdir(parents=True, exist_ok=True)

AFRI_BASE_URL = (
    os.getenv("AFRI_BASE_URL")
    or os.getenv("AFRI_API_BASE_URL")
    or "https://api.openai.com/v1"
).strip()
AFRI_API_KEY = (os.getenv("AFRI_API_KEY") or "").strip()
AFRI_MODEL = (os.getenv("AFRI_CHAT_MODEL") or "gpt-5.5").strip()
POINTS_PAR_BONNE_REPONSE = 30

FORMATIONS: List[Dict[str, Any]] = [
    {
        "code": "alimentation_volailles",
        "aliases": ["alimentation-volailles"],
        "titre": "Alimentation des volailles au Bénin",
        "niveau": "Débutant",
        "duree": "45 minutes",
        "points": 100,
        "resume": "Apprendre à nourrir les poulets avec des ingrédients locaux, réduire les coûts et éviter les erreurs fréquentes.",
        "icone": "🐔",
        "ordre": 1,
        "lecons": [
            {
                "numero": 1,
                "titre": "Les besoins nutritionnels des poulets",
                "objectif": "Énergie, protéines, calcium, vitamines et eau propre pour les poulets béninois.",
                "questions": 3,
            },
            {
                "numero": 2,
                "titre": "Les matières premières disponibles au Bénin",
                "objectif": "Lister les ingrédients courants, leurs valeurs nutritives et leurs prix moyens en FCFA.",
                "questions": 3,
            },
            {
                "numero": 3,
                "titre": "Formuler une ration équilibrée",
                "objectif": "Combiner les ingrédients pour obtenir une ration stable avec NutriCore.",
                "questions": 3,
            },
            {
                "numero": 4,
                "titre": "Réduire les coûts d alimentation",
                "objectif": "Optimiser le coût sans sacrifier la croissance ni la santé.",
                "questions": 3,
            },
            {
                "numero": 5,
                "titre": "Erreurs fréquentes à éviter",
                "objectif": "Identifier 10 erreurs d'alimentation et corriger les mauvaises pratiques.",
                "questions": 5,
            },
        ],
    },
    {
        "code": "sante_prevention",
        "aliases": ["sante-prevention"],
        "titre": "Santé et prévention animale",
        "niveau": "Débutant",
        "duree": "40 minutes",
        "points": 80,
        "resume": "Reconnaître les maladies courantes, renforcer la vaccination et appliquer la biosécurité.",
        "icone": "🩺",
        "ordre": 2,
        "lecons": [
            {
                "numero": 1,
                "titre": "Maladies courantes des volailles au Bénin",
                "objectif": "Lire les signes d'alerte et agir rapidement.",
                "questions": 3,
            },
            {
                "numero": 2,
                "titre": "Programme de vaccination obligatoire",
                "objectif": "Comprendre le calendrier, les rappels et la conservation des vaccins.",
                "questions": 3,
            },
            {
                "numero": 3,
                "titre": "Biosécurité de l élevage",
                "objectif": "Mettre en place des barrières, la quarantaine et l'hygiène.",
                "questions": 3,
            },
            {
                "numero": 4,
                "titre": "Quiz de certification",
                "objectif": "Vérifier la maîtrise des gestes de prévention et de santé.",
                "questions": 5,
            },
        ],
    },
    {
        "code": "reproduction_bovine",
        "aliases": ["reproduction-bovine"],
        "titre": "Reproduction bovine optimisée",
        "niveau": "Intermédiaire",
        "duree": "35 minutes",
        "points": 90,
        "resume": "Suivre le cycle de la vache zébu et détecter les chaleurs sans capteur.",
        "icone": "🐄",
        "ordre": 3,
        "lecons": [
            {
                "numero": 1,
                "titre": "Cycle reproductif de la vache zébu",
                "objectif": "Comprendre les phases du cycle et la gestation.",
                "questions": 3,
            },
            {
                "numero": 2,
                "titre": "Détection des chaleurs sans capteur",
                "objectif": "Observer les signes comportementaux et physiologiques.",
                "questions": 3,
            },
            {
                "numero": 3,
                "titre": "Quiz de certification",
                "objectif": "Valider les bons réflexes de reproduction.",
                "questions": 5,
            },
        ],
    },
    {
        "code": "finance_agricole",
        "aliases": ["finance-agricole"],
        "titre": "Finance agricole pratique",
        "niveau": "Débutant",
        "duree": "30 minutes",
        "points": 70,
        "resume": "Calculer son coût de revient et fixer un prix de vente rentable.",
        "icone": "💰",
        "ordre": 4,
        "lecons": [
            {
                "numero": 1,
                "titre": "Calculer son coût de revient",
                "objectif": "Identifier toutes les charges et marges.",
                "questions": 3,
            },
            {
                "numero": 2,
                "titre": "Fixer le bon prix de vente",
                "objectif": "Comparer le marché et protéger sa rentabilité.",
                "questions": 3,
            },
            {
                "numero": 3,
                "titre": "Quiz de certification",
                "objectif": "Tester les notions financières essentielles.",
                "questions": 5,
            },
        ],
    },
    {
        "code": "paturages_durables",
        "aliases": ["paturages-durables"],
        "titre": "Pâturages durables en Afrique",
        "niveau": "Intermédiaire",
        "duree": "30 minutes",
        "points": 80,
        "resume": "Comprendre la charge animale et planifier les rotations de paddocks.",
        "icone": "🌿",
        "ordre": 5,
        "lecons": [
            {
                "numero": 1,
                "titre": "Comprendre la charge animale",
                "objectif": "Ajuster la pression de pâturage à la capacité du terrain.",
                "questions": 3,
            },
            {
                "numero": 2,
                "titre": "Planifier les rotations de paddocks",
                "objectif": "Organiser les rotations et le repos de l'herbe.",
                "questions": 3,
            },
            {
                "numero": 3,
                "titre": "Quiz de certification",
                "objectif": "Valider les bons gestes de gestion durable.",
                "questions": 5,
            },
        ],
    },
]

FORMATION_BY_CODE = {formation["code"]: formation for formation in FORMATIONS}
ALIASES_TO_CODE = {
    alias: formation["code"]
    for formation in FORMATIONS
    for alias in formation.get("aliases", [])
}
LESSON_INDEX = {
    (formation["code"], int(lecon["numero"])): lecon
    for formation in FORMATIONS
    for lecon in formation["lecons"]
}


class QuizSubmissionRequest(BaseModel):
    user_id: str = Field(..., min_length=3)
    formation_code: str = Field(..., min_length=3)
    lecon_numero: Optional[int] = Field(default=None, ge=1)
    numero: Optional[int] = Field(default=None, ge=1)
    reponses: List[int] = Field(default_factory=list)
    langue: str = Field(default="fr", min_length=2)

    @field_validator("user_id", "formation_code", "langue")
    @classmethod
    def _strip(cls, value: str) -> str:
        txt = (value or "").strip()
        if not txt:
            raise ValueError("Champ vide.")
        return txt


class LessonQueryRequest(BaseModel):
    formation_code: str = Field(..., min_length=3)
    numero: Optional[int] = Field(default=None, ge=1)

    @field_validator("formation_code")
    @classmethod
    def _strip_code(cls, value: str) -> str:
        txt = (value or "").strip()
        if not txt:
            raise ValueError("Champ vide.")
        return txt


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip()).lower()


def _resolve_code(code: str) -> str:
    txt = _normalize(code).replace("-", "_")
    if txt in FORMATION_BY_CODE:
        return txt
    alias = ALIASES_TO_CODE.get(txt) or ALIASES_TO_CODE.get(txt.replace("_", "-"))
    if alias:
        return alias
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail="Formation introuvable."
    )


def _ensure_formation(code: str) -> Dict[str, Any]:
    return FORMATION_BY_CODE[_resolve_code(code)]


def _ensure_lesson(formation_code: str, numero: int) -> Dict[str, Any]:
    code = _resolve_code(formation_code)
    lecon = LESSON_INDEX.get((code, int(numero)))
    if not lecon:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Leçon introuvable."
        )
    return {
        **lecon,
        "formation_code": code,
        "formation_titre": FORMATION_BY_CODE[code]["titre"],
    }


def _build_system_prompt(langue: str) -> str:
    return (
        "Tu es un pédagogue agricole africain. Tu expliques simplement, sans jargon inutile, "
        f"dans la langue demandée ({langue}). Tu donnes des exemples concrets pour un éleveur du Bénin."
    )


async def _generate_gpt_content(
    formation: Dict[str, Any], lecon: Dict[str, Any], langue: str
) -> Optional[str]:
    if not AFRI_API_KEY:
        return None
    try:
        from openai import OpenAI  # type: ignore
    except Exception:
        return None

    prompt = (
        f"Crée un contenu pédagogique complet en {langue} pour la formation '{formation['titre']}'. "
        f"Leçon: {lecon['titre']}. Objectif: {lecon['objectif']}. "
        "Structure: introduction, explication simple, exemple béninois, erreurs à éviter, mini résumé. "
        "Ton: clair, encourageant, concret."
    )
    try:
        client = OpenAI(api_key=AFRI_API_KEY, base_url=AFRI_BASE_URL)
        response = client.chat.completions.create(
            model=AFRI_MODEL,
            messages=[
                {"role": "system", "content": _build_system_prompt(langue)},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=1200,
        )
        content = getattr(response.choices[0].message, "content", "")
        return content.strip() if isinstance(content, str) and content.strip() else None
    except Exception:
        return None


def _fallback_content(
    formation: Dict[str, Any], lecon: Dict[str, Any], langue: str
) -> str:
    base = (
        f"{lecon['titre']} — {formation['titre']}\n\n"
        f"Objectif de la leçon: {lecon['objectif']}\n\n"
        "Aya vous explique pas à pas. Commencez par observer la réalité de votre ferme, "
        "puis appliquez une petite action concrète aujourd'hui. Quand vous notez vos résultats, "
        "vous prenez de meilleures décisions et vous progressez plus vite.\n\n"
        f"Exemple terrain: un éleveur béninois ajuste ses pratiques selon les observations du jour, "
        f"les prix du marché et l'état de santé de son troupeau.\n\n"
        f"Rappel important: {lecon['objectif']}."
    )
    if langue.lower().startswith("fr"):
        return base
    return (
        f"{lecon['titre']} - {formation['titre']}\n\n"
        "Start with simple observations, apply one useful action today, and note the result. "
        "This habit improves your farm decisions over time.\n\n"
        f"Key reminder: {lecon['objectif']}"
    )


def _build_quiz(
    formation_code: str, numero: int, langue: str, question_count: int
) -> List[Dict[str, Any]]:
    theme = LESSON_INDEX[(formation_code, numero)]["titre"]
    questions: List[Dict[str, Any]] = []
    for i in range(question_count):
        if i == 0:
            correct = 0
            choices = [
                "Observer et ajuster",
                "Ignorer les signes",
                "Attendre sans suivre",
                "Changer tout au hasard",
            ]
        elif i == 1:
            correct = 1
            choices = [
                "Acheter sans comparer",
                "Noter ses résultats",
                "Négliger le prix",
                "Oublier le suivi",
            ]
        elif i == 2:
            correct = 2
            choices = [
                "Mélanger au hasard",
                "Éviter les calculs",
                "Choisir une méthode simple et régulière",
                "Copier sans comprendre",
            ]
        elif i == 3:
            correct = 0
            choices = [
                "Appliquer un contrôle quotidien",
                "Laisser faire",
                "Attendre la perte",
                "Réduire l'hygiène",
            ]
        else:
            correct = 3
            choices = [
                "Oublier la qualité",
                "Ignorer la santé",
                "Ne pas comparer les coûts",
                "Vérifier les résultats avant d'augmenter",
            ]
        questions.append(
            {
                "question": f"Question {i + 1} sur {theme} : quelle est la meilleure pratique ?",
                "choix": choices,
                "bonne_reponse": correct,
                "explication": "Aya recommande une approche simple, régulière et adaptée au terrain.",
                "points_gagnes": POINTS_PAR_BONNE_REPONSE,
                "langue": langue,
            }
        )
    return questions


def _build_lesson_payload(
    formation_code: str, numero: int, langue: str = "fr"
) -> Dict[str, Any]:
    formation = _ensure_formation(formation_code)
    lecon = _ensure_lesson(formation_code, numero)
    contenu = _generate_gpt_content(formation, lecon, langue)
    if not contenu:
        contenu = _fallback_content(formation, lecon, langue)
    quiz = _build_quiz(
        formation["code"], int(lecon["numero"]), langue, int(lecon.get("questions", 3))
    )
    score_max = len(quiz) * POINTS_PAR_BONNE_REPONSE
    return {
        "formation": {
            "code": formation["code"],
            "titre": formation["titre"],
            "resume": formation["resume"],
            "icone": formation["icone"],
            "ordre": formation["ordre"],
            "niveau": formation["niveau"],
            "duree": formation["duree"],
            "points": formation["points"],
            "total_lecons": len(formation["lecons"]),
        },
        "lecon": {
            "numero": lecon["numero"],
            "titre": lecon["titre"],
            "contenu": contenu,
            "objectif": lecon["objectif"],
            "points_gagnes": score_max,
            "langue": langue,
        },
        "quiz": {
            "total_questions": len(quiz),
            "questions": quiz,
            "score_max": score_max,
        },
        "navigation": {
            "precedente": lecon["numero"] - 1 if lecon["numero"] > 1 else None,
            "suivante": lecon["numero"] + 1
            if lecon["numero"] < len(formation["lecons"])
            else None,
        },
    }


def _progress_for_user(db: Session, user_id: str) -> Dict[str, Any]:
    completions = list_user_formations_completees(db, user_id, limit=1000)
    completed_keys = {
        (
            str(cast(Any, item).formation_code),
            int(cast(Any, item).lecon_numero or 0),
        )
        for item in completions
    }
    formations_progress: List[Dict[str, Any]] = []
    total_lecons = sum(len(f["lecons"]) for f in FORMATIONS)
    total_completees = 0
    for formation in FORMATIONS:
        done = sum(
            1
            for lecon in formation["lecons"]
            if (formation["code"], int(lecon["numero"])) in completed_keys
        )
        total_completees += done
        total = len(formation["lecons"])
        formations_progress.append(
            {
                "code": formation["code"],
                "titre": formation["titre"],
                "total_lecons": total,
                "lecons_completees": done,
                "pourcentage": round((done / total) * 100, 2) if total else 0.0,
                "points": formation["points"],
            }
        )
    return {
        "user_id": user_id,
        "total_lecons": total_lecons,
        "lecons_completees": total_completees,
        "pourcentage_global": round((total_completees / total_lecons) * 100, 2)
        if total_lecons
        else 0.0,
        "formations": formations_progress,
        "completions": [serialize_formation_completee(item) for item in completions],
    }


def _write_certificat_pdf(user_id: str, progress: Dict[str, Any]) -> str:
    filename = f"certificat_{user_id}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}.pdf"
    path = CERTIFICATS_DIR / filename
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    pdf.setTitle("Certificat FarmAcademy")
    pdf.setFont("Helvetica-Bold", 20)
    pdf.drawString(2 * cm, height - 2.5 * cm, "FeedFormula AI - Certificat FarmAcademy")
    pdf.setFont("Helvetica", 12)
    pdf.drawString(2 * cm, height - 3.8 * cm, f"Utilisateur: {user_id}")
    pdf.drawString(
        2 * cm,
        height - 4.5 * cm,
        f"Progression globale: {progress['pourcentage_global']} %",
    )
    y = height - 6.0 * cm
    for formation in progress["formations"]:
        pdf.drawString(
            2 * cm,
            y,
            f"- {formation['titre']} : {formation['lecons_completees']}/{formation['total_lecons']} leçons",
        )
        y -= 0.7 * cm
        if y < 3.5 * cm:
            break
    pdf.drawString(2 * cm, 3 * cm, "Certificat délivré par FeedFormula AI")
    pdf.showPage()
    pdf.save()
    path.write_bytes(buffer.getvalue())
    return f"/static/academy_certificats/{filename}"


def _normalize_reponse(value: int) -> int:
    if value in {0, 1, 2, 3}:
        return value
    if value in {1, 2, 3, 4}:
        return value - 1
    return -1


@router.get("/formations")
def get_formations() -> Dict[str, Any]:
    return {
        "total": len(FORMATIONS),
        "formations": [
            {
                "code": f["code"],
                "titre": f["titre"],
                "resume": f["resume"],
                "icone": f["icone"],
                "ordre": f["ordre"],
                "niveau": f["niveau"],
                "duree": f["duree"],
                "points": f["points"],
                "total_lecons": len(f["lecons"]),
            }
            for f in FORMATIONS
        ],
    }


@router.get("/formation/{code}")
def get_formation(code: str) -> Dict[str, Any]:
    formation = _ensure_formation(code)
    return {
        "code": formation["code"],
        "titre": formation["titre"],
        "resume": formation["resume"],
        "icone": formation["icone"],
        "ordre": formation["ordre"],
        "niveau": formation["niveau"],
        "duree": formation["duree"],
        "points": formation["points"],
        "total_lecons": len(formation["lecons"]),
        "lecons": [
            {
                "numero": lecon["numero"],
                "titre": lecon["titre"],
                "objectif": lecon["objectif"],
                "questions": lecon["questions"],
            }
            for lecon in formation["lecons"]
        ],
    }


@router.get("/lecon/{formation_code}/{numero}")
def get_lecon(formation_code: str, numero: int, langue: str = "fr") -> Dict[str, Any]:
    return _build_lesson_payload(formation_code, numero, langue)


@router.post("/quiz/soumettre")
def soumettre_quiz(
    payload: QuizSubmissionRequest, db: Session = Depends(get_db)
) -> Dict[str, Any]:
    numero = int(payload.lecon_numero or payload.numero or 1)
    lesson = _build_lesson_payload(payload.formation_code, numero, payload.langue)
    questions = lesson["quiz"]["questions"]
    score_max = len(questions) * POINTS_PAR_BONNE_REPONSE
    correct = 0
    score = 0
    feedback_par_question: List[Dict[str, Any]] = []

    for idx, question in enumerate(questions):
        raw = payload.reponses[idx] if idx < len(payload.reponses) else -1
        reponse = _normalize_reponse(int(raw))
        is_ok = reponse == int(question["bonne_reponse"])
        if is_ok:
            correct += 1
            score += POINTS_PAR_BONNE_REPONSE
        feedback_par_question.append(
            {
                "question": question["question"],
                "choix": question["choix"],
                "bonne_reponse": int(question["bonne_reponse"]),
                "reponse_utilisateur": reponse,
                "correct": is_ok,
                "explication": question["explication"],
                "points_gagnes": POINTS_PAR_BONNE_REPONSE if is_ok else 0,
            }
        )

    create_formation_completee(
        db,
        payload.user_id,
        _resolve_code(payload.formation_code),
        numero,
        score_quiz=score,
    )
    user = get_user_by_id(db, payload.user_id)
    if user:
        add_points_to_user(db, payload.user_id, score)

    progression = _progress_for_user(db, payload.user_id)
    certificat_url = None
    if progression["pourcentage_global"] >= 100.0:
        certificat_url = _write_certificat_pdf(payload.user_id, progression)

    return {
        "user_id": payload.user_id,
        "formation_code": _resolve_code(payload.formation_code),
        "lecon_numero": numero,
        "score": score,
        "score_max": score_max,
        "correct": correct,
        "reussi": score == score_max,
        "points_gagnes": score,
        "feedback_par_question": feedback_par_question,
        "progression": progression,
        "certificat_url": certificat_url,
    }


@router.get("/progression/{user_id}")
def get_progression(user_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    return _progress_for_user(db, user_id)


@router.get("/certifications/{user_id}")
def get_certifications(user_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    progress = _progress_for_user(db, user_id)
    certifications: List[Dict[str, Any]] = []
    for formation in FORMATIONS:
        done = next(
            (
                item
                for item in progress["formations"]
                if item["code"] == formation["code"]
            ),
            None,
        )
        if done and done["lecons_completees"] == done["total_lecons"]:
            certifications.append(
                {
                    "formation_code": formation["code"],
                    "titre": formation["titre"],
                    "total_lecons": done["total_lecons"],
                    "lecons_completees": done["lecons_completees"],
                    "pourcentage": 100.0,
                    "certificat_url": _write_certificat_pdf(user_id, progress),
                }
            )
    return {
        "user_id": user_id,
        "total": len(certifications),
        "certifications": certifications,
        "progression": progress,
    }


@router.post("/certification/generer")
def generer_certification(
    payload: Dict[str, Any], db: Session = Depends(get_db)
) -> Dict[str, Any]:
    user_id = str(payload.get("user_id") or "").strip()
    formation_code = str(payload.get("formation_code") or "").strip()
    if not user_id or not formation_code:
        raise HTTPException(status_code=400, detail="user_id et formation_code requis.")
    progress = _progress_for_user(db, user_id)
    if not any(
        item["code"] == _resolve_code(formation_code)
        and item["lecons_completees"] == item["total_lecons"]
        for item in progress["formations"]
    ):
        raise HTTPException(status_code=400, detail="Formation incomplète.")
    url = _write_certificat_pdf(user_id, progress)
    return {
        "user_id": user_id,
        "formation_code": _resolve_code(formation_code),
        "certificat_url": url,
        "format": "pdf",
    }


__all__ = [
    "router",
    "FORMATIONS",
    "QuizSubmissionRequest",
    "LessonQueryRequest",
    "get_formations",
    "get_formation",
    "get_lecon",
]
