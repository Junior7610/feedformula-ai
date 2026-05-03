#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pyright: reportGeneralTypeIssues=false
"""
FarmAcademy complet de FeedFormula AI.

Fonctionnalités :
- Catalogue de 5 formations et 18 leçons
- Génération de contenu pédagogique en français simple
- Quiz interactif à 3 questions par leçon
- Suivi de progression par utilisateur
- Certificat PDF téléchargeable lorsque 100 % des leçons sont complétées
- Endpoints FastAPI prêts à brancher dans `main.py`

Le module fonctionne de manière déterministe hors API externe,
mais peut utiliser GPT si une clé compatible est disponible.
"""

from __future__ import annotations

import io
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from database import (
    create_formation_completee,
    get_db,
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
DATA_DIR = ROOT_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
CERTIFICATS_DIR = DATA_DIR / "academy_certificats"
CERTIFICATS_DIR.mkdir(parents=True, exist_ok=True)

AFRI_BASE_URL = (
    os.getenv("AFRI_BASE_URL")
    or os.getenv("AFRI_API_BASE_URL")
    or "https://build.lewisnote.com/v1"
).strip()
AFRI_API_KEY = (os.getenv("AFRI_API_KEY") or "").strip()
AFRI_MODEL = (os.getenv("AFRI_CHAT_MODEL") or "gpt-5.5").strip()

ACCES_POINTS_PAR_BONNE_REPONSE = 30

FORMATIONS: List[Dict[str, Any]] = [
    {
        "code": "alimentation-volailles",
        "titre": "Alimentation des volailles",
        "resume": "Apprendre à nourrir les poulets avec des ingrédients locaux, des rations équilibrées et des bons réflexes pour réduire les coûts.",
        "icone": "🐔",
        "ordre": 1,
        "lecons": [
            {
                "numero": 1,
                "titre": "Les besoins nutritionnels des poulets",
                "focus": "besoins nutritionnels, eau, énergie, protéines, vitamines",
            },
            {
                "numero": 2,
                "titre": "Les matières premières disponibles au Bénin",
                "focus": "maïs, son, soja, drêches, tourteaux, disponibilité locale",
            },
            {
                "numero": 3,
                "titre": "Formuler une ration équilibrée",
                "focus": "équilibre, formulation, mélange, proportions, adaptation",
            },
            {
                "numero": 4,
                "titre": "Réduire les coûts d alimentation",
                "focus": "coût de revient, achat groupé, stockage, valorisation locale",
            },
            {
                "numero": 5,
                "titre": "Erreurs fréquentes à éviter",
                "focus": "erreurs, contamination, surdosage, eau sale, changement brusque",
            },
        ],
    },
    {
        "code": "sante-prevention",
        "titre": "Santé et prévention",
        "resume": "Reconnaître les maladies courantes, protéger l élevage avec la vaccination et renforcer la biosécurité.",
        "icone": "🩺",
        "ordre": 2,
        "lecons": [
            {
                "numero": 1,
                "titre": "Les maladies courantes des volailles",
                "focus": "maladies, signes, diarrhée, toux, abattement, mortalité",
            },
            {
                "numero": 2,
                "titre": "Programme de vaccination",
                "focus": "vaccin, calendrier, rappels, conservation, respect des doses",
            },
            {
                "numero": 3,
                "titre": "Biosécurité de l élevage",
                "focus": "désinfection, barrières, visiteurs, pédiluve, quarantaine",
            },
            {
                "numero": 4,
                "titre": "Premiers secours vétérinaires",
                "focus": "isoler, hydrater, alerter, surveiller, gestes d urgence",
            },
        ],
    },
    {
        "code": "reproduction-bovine",
        "titre": "Gestion reproduction bovine",
        "resume": "Suivre le cycle reproductif de la vache, détecter les chaleurs et améliorer le taux de conception.",
        "icone": "🐄",
        "ordre": 3,
        "lecons": [
            {
                "numero": 1,
                "titre": "Le cycle reproductif de la vache",
                "focus": "cycle, phase, chaleur, ovulation, gestation",
            },
            {
                "numero": 2,
                "titre": "Détecter les chaleurs",
                "focus": "signes, comportement, mucus, agitation, monte",
            },
            {
                "numero": 3,
                "titre": "Optimiser le taux de conception",
                "focus": "saillie, nutrition, santé, timing, suivi",
            },
        ],
    },
    {
        "code": "finance-agricole",
        "titre": "Finance agricole",
        "resume": "Maîtriser le coût de revient, fixer un bon prix de vente et comprendre les subventions agricoles.",
        "icone": "💰",
        "ordre": 4,
        "lecons": [
            {
                "numero": 1,
                "titre": "Calculer le coût de revient",
                "focus": "charges, amortissement, main d œuvre, marge, calcul",
            },
            {
                "numero": 2,
                "titre": "Fixer le bon prix de vente",
                "focus": "prix, marché, concurrence, marge, stratégie",
            },
            {
                "numero": 3,
                "titre": "Accéder aux subventions agricoles",
                "focus": "dossier, mairie, projets, formalités, financement",
            },
        ],
    },
    {
        "code": "paturages-durables",
        "titre": "Pâturages durables",
        "resume": "Comprendre la charge animale, planifier les rotations et restaurer un pâturage dégradé.",
        "icone": "🌿",
        "ordre": 5,
        "lecons": [
            {
                "numero": 1,
                "titre": "Comprendre la charge animale",
                "focus": "charge animale, pression, capacité, saison, sol",
            },
            {
                "numero": 2,
                "titre": "Planifier les rotations",
                "focus": "rotation, parcelles, repos, calendrier, herbe",
            },
            {
                "numero": 3,
                "titre": "Restaurer un pâturage dégradé",
                "focus": "restauration, semis, repos, fertilité, protection",
            },
        ],
    },
]

# Index rapide
FORMATION_BY_CODE = {f["code"]: f for f in FORMATIONS}
LESSON_BY_KEY: Dict[str, Dict[str, Any]] = {}
for formation in FORMATIONS:
    for lecon in formation["lecons"]:
        key = f"{formation['code']}::{lecon['numero']}"
        LESSON_BY_KEY[key] = {
            **lecon,
            "formation_code": formation["code"],
            "formation_titre": formation["titre"],
        }


class QuizSubmissionRequest(BaseModel):
    user_id: str = Field(..., min_length=3)
    formation_code: str = Field(..., min_length=3)
    numero: int = Field(..., ge=1)
    reponses: List[int] = Field(default_factory=list)

    @field_validator("user_id", "formation_code")
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
    return " ".join((text or "").strip().split())


def _ensure_formation(code: str) -> Dict[str, Any]:
    formation = FORMATION_BY_CODE.get((code or "").strip())
    if not formation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Formation introuvable."
        )
    return formation


def _ensure_lesson(formation_code: str, numero: int) -> Dict[str, Any]:
    formation = _ensure_formation(formation_code)
    for lecon in formation["lecons"]:
        if int(lecon["numero"]) == int(numero):
            return {
                **lecon,
                "formation_code": formation_code,
                "formation_titre": formation["titre"],
            }
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail="Leçon introuvable."
    )


def _lesson_wording(formation: Dict[str, Any], lecon: Dict[str, Any]) -> str:
    focus = lecon["focus"]
    titre = lecon["titre"]
    formation_titre = formation["titre"]
    return (
        f"{titre} appartient à la formation {formation_titre}.\n\n"
        f"Dans cette leçon, on parle de {focus}. Le but est de vous donner des idées simples, concrètes et faciles à appliquer dans une ferme africaine.\n\n"
        f"Commencez par observer vos animaux et votre contexte. Sur le terrain, la réussite dépend souvent de petits gestes répétés chaque jour : eau propre, aliments bien conservés, matériel nettoyé, surveillance des signes de stress, et respect du calendrier.\n\n"
        f"Ensuite, adaptez les conseils à vos moyens. Une bonne pratique n est pas forcément la plus chère. Ce qui compte, c est la régularité, la qualité des ingrédients et la capacité à repérer les erreurs avant qu elles ne deviennent coûteuses.\n\n"
        f"Enfin, gardez une logique de suivi. Notez les quantités, les dates, les incidents et les résultats. Quand vous comparez les chiffres semaine après semaine, vous pouvez ajuster plus vite.\n\n"
        f"En appliquant cette leçon, vous améliorez la santé des animaux, vous réduisez les pertes et vous gagnez en autonomie. Le plus important est de commencer petit, de tester, puis d améliorer progressivement vos pratiques selon vos réalités locales.\n\n"
        f"Rappel pratique : {focus}. Répétez l essentiel à votre équipe, vérifiez les détails chaque jour et corrigez rapidement les écarts."
    )


def _generate_gpt_content(
    formation: Dict[str, Any], lecon: Dict[str, Any]
) -> Optional[str]:
    if not AFRI_API_KEY:
        return None
    try:
        from openai import OpenAI  # type: ignore
    except Exception:
        return None
    try:
        client = OpenAI(api_key=AFRI_API_KEY, base_url=AFRI_BASE_URL)
        prompt = (
            "Tu es un pédagogue agricole africain. Écris un contenu en français simple de 500 à 800 mots, "
            "structuré en paragraphes courts, avec exemples concrets, sans jargon inutile. "
            "Sujet: " + lecon["titre"] + ". Focus: " + lecon["focus"] + ". "
            "Respecte le contexte: " + formation["titre"] + "."
        )
        response = client.chat.completions.create(
            model=AFRI_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "Tu es un expert en vulgarisation agricole africaine.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.4,
            max_tokens=1200,
        )
        content = getattr(response.choices[0].message, "content", "")
        if isinstance(content, str) and content.strip():
            return content.strip()
    except Exception:
        return None
    return None


def _build_quiz(formation_code: str, numero: int, focus: str) -> List[Dict[str, Any]]:

    questions = [
        {
            "question": f"Selon la leçon {numero}, quel réflexe est le plus utile pour {focus} ?",
            "choix": [
                "Observer et ajuster",
                "Ignorer les signes",
                "Attendre sans suivre",
                "Changer tout d un coup",
            ],
            "bonne_reponse": 0,
            "explication": f"La leçon insiste sur une logique d observation, de suivi et d ajustement progressif autour de {focus}.",
            "points_gagnes": ACCES_POINTS_PAR_BONNE_REPONSE,
        },
        {
            "question": f"Quel comportement aide le mieux à réussir sur le thème {formation_code} ?",
            "choix": [
                "Appliquer des gestes simples chaque jour",
                "Acheter au hasard",
                "Négliger les coûts",
                "Oublier les contrôles",
            ],
            "bonne_reponse": 0,
            "explication": "La réussite vient d habitudes régulières, pas d actions improvisées.",
            "points_gagnes": ACCES_POINTS_PAR_BONNE_REPONSE,
        },
        {
            "question": "Quel choix réduit le plus les erreurs sur le terrain ?",
            "choix": [
                "Noter, comparer et corriger",
                "Faire sans mesurer",
                "Copier sans comprendre",
                "Attendre la panne",
            ],
            "bonne_reponse": 0,
            "explication": "Le suivi permet de comparer les résultats et de corriger rapidement les écarts.",
            "points_gagnes": ACCES_POINTS_PAR_BONNE_REPONSE,
        },
    ]
    return questions


def _build_lesson_payload(formation_code: str, numero: int) -> Dict[str, Any]:
    formation = _ensure_formation(formation_code)
    lecon = _ensure_lesson(formation_code, numero)
    texte = _generate_gpt_content(formation, lecon) or _lesson_wording(formation, lecon)
    quiz = _build_quiz(formation_code, numero, lecon["focus"])
    total_points = len(quiz) * ACCES_POINTS_PAR_BONNE_REPONSE
    return {
        "formation": {
            "code": formation["code"],
            "titre": formation["titre"],
            "resume": formation["resume"],
            "icone": formation["icone"],
            "ordre": formation["ordre"],
            "total_lecons": len(formation["lecons"]),
        },
        "lecon": {
            "numero": lecon["numero"],
            "titre": lecon["titre"],
            "contenu": texte,
            "points_gagnes": total_points,
            "focus": lecon["focus"],
        },
        "quiz": {
            "total_questions": len(quiz),
            "questions": quiz,
        },
        "navigation": {
            "precedente": lecon["numero"] - 1 if lecon["numero"] > 1 else None,
            "suivante": lecon["numero"] + 1
            if lecon["numero"] < len(formation["lecons"])
            else None,
        },
    }


def _progress_for_user(db: Session, user_id: str) -> Dict[str, Any]:
    completions = list_user_formations_completees(db, user_id, limit=500)
    completed_keys = {
        (str(x.formation_code), int(getattr(x, "lecon_numero", 0) or 0))
        for x in completions
    }
    formations_progress = []
    total_lecons = sum(len(f["lecons"]) for f in FORMATIONS)
    total_completees = 0
    for formation in FORMATIONS:
        done = 0
        for lecon in formation["lecons"]:
            if (formation["code"], int(lecon["numero"])) in completed_keys:
                done += 1
        total_completees += done
        total = len(formation["lecons"])
        formations_progress.append(
            {
                "code": formation["code"],
                "titre": formation["titre"],
                "total_lecons": total,
                "lecons_completees": done,
                "pourcentage": round((done / total) * 100, 2) if total else 0.0,
            }
        )
    pourcentage_global = (
        round((total_completees / total_lecons) * 100, 2) if total_lecons else 0.0
    )
    return {
        "user_id": user_id,
        "total_lecons": total_lecons,
        "lecons_completees": total_completees,
        "pourcentage_global": pourcentage_global,
        "formations": formations_progress,
        "completions": [serialize_formation_completee(x) for x in completions],
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
        height - 4.6 * cm,
        f"Progression globale: {progress['pourcentage_global']} %",
    )
    y = height - 6 * cm
    for formation in progress["formations"]:
        pdf.drawString(
            2 * cm,
            y,
            f"- {formation['titre']}: {formation['lecons_completees']}/{formation['total_lecons']} leçons",
        )
        y -= 0.8 * cm
    pdf.drawString(2 * cm, 3 * cm, "Certificat délivré par FeedFormula AI")
    pdf.showPage()
    pdf.save()
    path.write_bytes(buffer.getvalue())
    return f"/static/academy_certificats/{filename}"


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
        "total_lecons": len(formation["lecons"]),
        "lecons": [
            {
                "numero": lecon["numero"],
                "titre": lecon["titre"],
                "focus": lecon["focus"],
            }
            for lecon in formation["lecons"]
        ],
    }


@router.get("/lecon/{formation_code}/{numero}")
def get_lecon(formation_code: str, numero: int) -> Dict[str, Any]:
    return _build_lesson_payload(formation_code, numero)


@router.post("/quiz/soumettre")
def soumettre_quiz(
    payload: QuizSubmissionRequest, db: Session = Depends(get_db)
) -> Dict[str, Any]:
    _ensure_lesson(payload.formation_code, payload.numero)
    lesson_payload = _build_lesson_payload(payload.formation_code, payload.numero)
    quiz = lesson_payload["quiz"]["questions"]
    score = 0
    details = []
    for idx, question in enumerate(quiz):
        bonne = int(question["bonne_reponse"])
        reponse = payload.reponses[idx] if idx < len(payload.reponses) else None
        ok = reponse == bonne
        if ok:
            score += int(question["points_gagnes"])
        details.append(
            {
                "question": question["question"],
                "choix": question["choix"],
                "bonne_reponse": bonne,
                "reponse_utilisateur": reponse,
                "correct": ok,
                "explication": question["explication"],
                "points_gagnes": question["points_gagnes"] if ok else 0,
            }
        )
    create_formation_completee(
        db, payload.user_id, payload.formation_code, payload.numero, score_quiz=score
    )
    progression = _progress_for_user(db, payload.user_id)
    complet = progression["pourcentage_global"] == 100.0
    certificat_url = (
        _write_certificat_pdf(payload.user_id, progression) if complet else None
    )
    return {
        "user_id": payload.user_id,
        "formation_code": payload.formation_code,
        "numero": payload.numero,
        "score": score,
        "score_max": len(quiz) * ACCES_POINTS_PAR_BONNE_REPONSE,
        "points_gagnes": score,
        "details": details,
        "reussi": score == len(quiz) * ACCES_POINTS_PAR_BONNE_REPONSE,
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
        total = len(formation["lecons"])
        done = next(
            (x for x in progress["formations"] if x["code"] == formation["code"]), None
        )
        if done and done["lecons_completees"] == total:
            certifications.append(
                {
                    "formation_code": formation["code"],
                    "titre": formation["titre"],
                    "total_lecons": total,
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


__all__ = [
    "router",
    "FORMATIONS",
    "LessonQueryRequest",
    "QuizSubmissionRequest",
]
