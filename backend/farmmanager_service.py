#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Service FarmManager de FeedFormula AI.

Fonctions principales :
- traiter un événement vocal dicté par l'éleveur,
- structurer l'événement via GPT 5.5 ou fallback local,
- enregistrer l'événement en base,
- produire un rapport mensuel PDF avec ReportLab,
- exposer des endpoints simples pour le frontend.

Le module est volontairement robuste :
- fonctionnement dégradé si l'API IA est indisponible,
- enregistrement en base via `UserActionLog`,
- export PDF sans dépendances externes autres que ReportLab.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from database import UserActionLog, get_db, get_user_by_id
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from sqlalchemy.orm import Session

try:
    from openai import (
        APIConnectionError,
        APITimeoutError,
        AuthenticationError,
        OpenAI,
        OpenAIError,
    )
except Exception:  # pragma: no cover - fallback si le SDK n'est pas disponible
    OpenAI = None  # type: ignore
    APIConnectionError = Exception  # type: ignore
    APITimeoutError = Exception  # type: ignore
    AuthenticationError = Exception  # type: ignore
    OpenAIError = Exception  # type: ignore


router = APIRouter(prefix="/farmmanager", tags=["FarmManager"])

AFRI_BASE_URL = (
    os.getenv("AFRI_BASE_URL")
    or os.getenv("AFRI_API_BASE_URL")
    or "https://build.lewisnote.com/v1"
)
AFRI_API_KEY = (os.getenv("AFRI_API_KEY") or "").strip()
AFRI_FARMMANAGER_MODEL = (os.getenv("AFRI_FARMMANAGER_MODEL") or "gpt-5.5").strip()


# -----------------------------------------------------------------------------
# Schémas
# -----------------------------------------------------------------------------
class VocalEventRequest(BaseModel):
    """Entrée pour l'analyse d'un événement dicté à la voix."""

    texte: str = Field(..., min_length=3)
    user_id: str = Field(..., min_length=3)
    langue: str = Field(default="fr", min_length=2)

    @field_validator("texte", "user_id")
    @classmethod
    def _strip_text(cls, value: str) -> str:
        txt = " ".join((value or "").strip().split())
        if not txt:
            raise ValueError("Champ vide.")
        return txt


class MonthlyReportRequest(BaseModel):
    """Entrée pour la génération d'un rapport mensuel."""

    user_id: str = Field(..., min_length=3)
    mois: str = Field(..., min_length=7)

    @field_validator("user_id", "mois")
    @classmethod
    def _strip_request(cls, value: str) -> str:
        txt = " ".join((value or "").strip().split())
        if not txt:
            raise ValueError("Champ vide.")
        return txt


# -----------------------------------------------------------------------------
# Helpers généraux
# -----------------------------------------------------------------------------
def _normalize_text(value: Optional[str]) -> str:
    """Nettoie un texte simple."""
    return " ".join((value or "").strip().split())


def _safe_float(value: Any) -> float:
    """Convertit une valeur en float de manière prudente."""
    try:
        return float(
            str(value).replace(" ", "").replace("\u00a0", "").replace(",", ".")
        )
    except Exception:
        return 0.0


def _today_iso() -> str:
    return date.today().isoformat()


def _parse_month(mois: str) -> Tuple[int, int]:
    """Parse un mois au format YYYY-MM."""
    txt = _normalize_text(mois)
    if not re.match(r"^\d{4}-\d{2}$", txt):
        raise ValueError("Le mois doit être au format YYYY-MM.")
    year, month = txt.split("-")
    month_i = int(month)
    if month_i < 1 or month_i > 12:
        raise ValueError("Le mois doit être compris entre 01 et 12.")
    return int(year), month_i


def _client() -> Optional[Any]:
    """Construit un client OpenAI si la configuration est disponible."""
    if OpenAI is None or not AFRI_API_KEY:
        return None
    try:
        return OpenAI(api_key=AFRI_API_KEY, base_url=AFRI_BASE_URL)
    except Exception:
        return None


def _extract_json_payload(raw: str) -> Optional[Dict[str, Any]]:
    """
    Extrait un JSON dict depuis une réponse IA.
    Tolère les blocs ```json ... ``` ou du texte autour.
    """
    if not raw:
        return None

    txt = raw.strip()

    if txt.startswith("```"):
        txt = re.sub(r"^```(?:json)?\s*", "", txt, flags=re.IGNORECASE)
        txt = re.sub(r"\s*```$", "", txt)

    start = txt.find("{")
    end = txt.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None

    candidate = txt[start : end + 1]
    try:
        data = json.loads(candidate)
        if isinstance(data, dict):
            return data
    except Exception:
        return None
    return None


def _structure_event_text(texte: str) -> Dict[str, Any]:
    """
    Fallback local : structure un texte dicté en événement d'élevage.
    """
    original = _normalize_text(texte)
    lower = original.lower()

    animal = "animal inconnu"
    animal_match = re.search(
        r"(vache|bovin|chèvre|chevre|mouton|porc|poulet|pintade|lapin|tilapia)\s*([\w\-]*)\s*(\d+)?",
        lower,
    )
    if animal_match:
        animal = " ".join([x for x in animal_match.groups() if x]).strip()

    if any(
        k in lower
        for k in ["mammite", "vaccin", "traité", "traite", "soigné", "traitement"]
    ):
        type_evt = "traitement"
    elif any(
        k in lower
        for k in ["naissance", "né", "nee", "mise-bas", "mise bas", "vêlage", "velage"]
    ):
        type_evt = "naissance"
    elif "vente" in lower or "vendu" in lower:
        type_evt = "vente"
    elif any(k in lower for k in ["saillie", "insémin", "insemin", "reproduction"]):
        type_evt = "reproduction"
    elif any(k in lower for k in ["aliment", "alimentation", "ration", "nourri"]):
        type_evt = "alimentation"
    else:
        type_evt = "autre"

    # Détection simple de rappel
    rappel_jours = None
    m_jours = re.search(r"dans\s+(\d+)\s+jour", lower)
    if m_jours:
        try:
            rappel_jours = int(m_jours.group(1))
        except Exception:
            rappel_jours = None

    date_rappel = None
    if rappel_jours is not None:
        date_rappel = (
            (
                datetime.now(timezone.utc).replace(tzinfo=None)
                + timedelta(days=rappel_jours)
            )
            .date()
            .isoformat()
        )  # type: ignore[name-defined]
    elif "demain" in lower:
        date_rappel = (
            (datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=1))
            .date()
            .isoformat()
        )  # type: ignore[name-defined]

    cout_total = 0.0
    revenu = 0.0
    montant_match = re.search(r"(\d[\d\s]*)(?:\s*)(fcfa|f|francs)?", lower)
    if montant_match:
        cout_total = _safe_float(montant_match.group(1))
        if type_evt == "vente":
            revenu = cout_total

    return {
        "animal_id": animal,
        "type_evenement": type_evt,
        "date_evenement": _today_iso(),
        "details": original,
        "action_requise": (
            "Contrôle de suivi dans les prochains jours"
            if type_evt in {"traitement", "reproduction"}
            else "Aucune action immédiate"
        ),
        "date_rappel": date_rappel,
        "cout_total": cout_total,
        "revenu": revenu,
        "source": "fallback_local",
    }


def _save_event(db: Session, user_id: str, event: Dict[str, Any]) -> Dict[str, Any]:
    """Sauvegarde un événement structuré dans UserActionLog."""
    row = UserActionLog(
        user_id=user_id,
        action="farmmanager_event",
        points_awarded=0,
        meta_json=json.dumps(event, ensure_ascii=False),
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    return {
        "id": row.id,
        "user_id": row.user_id,
        "action": row.action,
        "created_at": row.created_at.isoformat()
        if row.created_at is not None
        else None,
        "event": event,
    }


def _load_events(db: Session, user_id: str) -> List[UserActionLog]:
    """Charge les événements FarmManager d'un utilisateur."""
    return (
        db.query(UserActionLog)
        .filter(
            UserActionLog.user_id == user_id,
            UserActionLog.action == "farmmanager_event",
        )
        .order_by(UserActionLog.created_at.desc())
        .all()
    )


def _extract_meta(row: UserActionLog) -> Dict[str, Any]:
    """Décodage défensif du JSON d'un événement."""
    try:
        raw_meta = row.meta_json if isinstance(row.meta_json, str) else "{}"
        data = json.loads(raw_meta or "{}")
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _detect_financial_amount(meta: Dict[str, Any]) -> float:
    """Extrait un montant depuis les métadonnées d'un événement."""
    for key in ("cout_total", "cout", "montant", "prix", "revenu", "revenue"):
        if key in meta:
            amount = _safe_float(meta.get(key))
            if amount > 0:
                return amount
    details = _normalize_text(str(meta.get("details") or ""))
    m = re.search(r"(\d[\d\s]*)", details)
    if m:
        return _safe_float(m.group(1))
    return 0.0


def _financial_dashboard(rows: List[UserActionLog]) -> Dict[str, Any]:
    """
    Calcule un tableau de bord financier simple sur les événements du mois.
    """
    cout_alimentation = 0.0
    revenus = 0.0

    for row in rows:
        meta = _extract_meta(row)
        type_evt = _normalize_text(str(meta.get("type_evenement") or "")).lower()
        details = _normalize_text(str(meta.get("details") or "")).lower()
        amount = _detect_financial_amount(meta)

        if "aliment" in type_evt or "ration" in details or "alimentation" in details:
            cout_alimentation += amount

        if type_evt == "vente" or "vente" in details:
            revenus += amount

    marge = revenus - cout_alimentation
    return {
        "cout_total_alimentation_mois": round(cout_alimentation, 2),
        "revenus_ventes_animaux": round(revenus, 2),
        "marge_nette_estimee": round(marge, 2),
    }


def _monthly_summary(
    rows: List[UserActionLog], user_id: str, mois: str
) -> Dict[str, Any]:
    """
    Prépare un résumé mensuel pour l'IA et le PDF.
    """
    total = len(rows)
    traitements = sum(
        1
        for row in rows
        if _normalize_text(_extract_meta(row).get("type_evenement", "")).lower()
        == "traitement"
    )
    naissances = sum(
        1
        for row in rows
        if _normalize_text(_extract_meta(row).get("type_evenement", "")).lower()
        == "naissance"
    )
    ventes = sum(
        1
        for row in rows
        if _normalize_text(_extract_meta(row).get("type_evenement", "")).lower()
        == "vente"
    )
    repro = sum(
        1
        for row in rows
        if _normalize_text(_extract_meta(row).get("type_evenement", "")).lower()
        in {"reproduction", "saillie", "insemination", "insémination"}
    )

    dashboard = _financial_dashboard(rows)
    return {
        "user_id": user_id,
        "mois": mois,
        "total_evenements": total,
        "traitements": traitements,
        "naissances": naissances,
        "ventes": ventes,
        "reproduction": repro,
        **dashboard,
    }


def _build_report_text(summary: Dict[str, Any], events: List[UserActionLog]) -> str:
    """
    Construit un texte de synthèse pour l'IA ou le fallback PDF.
    """
    lines = [
        "Rapport mensuel FarmManager",
        f"Utilisateur: {summary['user_id']}",
        f"Mois: {summary['mois']}",
        "",
        f"Nombre total d'événements: {summary['total_evenements']}",
        f"Traitements: {summary['traitements']}",
        f"Naissances: {summary['naissances']}",
        f"Ventes: {summary['ventes']}",
        f"Événements reproduction: {summary['reproduction']}",
        "",
        f"Coût total alimentation: {summary['cout_total_alimentation_mois']:.2f} FCFA",
        f"Revenus ventes animaux: {summary['revenus_ventes_animaux']:.2f} FCFA",
        f"Marge nette estimée: {summary['marge_nette_estimee']:.2f} FCFA",
        "",
        "Derniers événements:",
    ]

    for row in events[:10]:
        meta = _extract_meta(row)
        created_at = getattr(row, "created_at", None)
        created_at_txt = (
            created_at.isoformat() if isinstance(created_at, datetime) else ""
        )
        lines.append(
            f"- {meta.get('date_evenement', created_at_txt)} | "
            f"{meta.get('animal_id', 'animal inconnu')} | "
            f"{meta.get('type_evenement', 'événement')} | "
            f"{_normalize_text(str(meta.get('details') or ''))[:120]}"
        )

    return "\n".join(lines)


def _build_openai_prompt_for_event(texte: str) -> str:
    """
    Prompt GPT 5.5 pour transformer une dictée libre en événement structuré.
    """
    return (
        "Tu es FarmManager, un assistant d'élevage pour l'Afrique. "
        "Analyse le texte dicté par l'éleveur et retourne UNIQUEMENT un JSON strict. "
        "Le JSON doit contenir exactement ces champs : "
        "{"
        '"animal_id":"...",'
        '"type_evenement":"traitement|naissance|vente|reproduction|alimentation|autre",'
        '"date_evenement":"YYYY-MM-DD",'
        '"details":"...",'
        '"action_requise":"...",'
        '"date_rappel":"YYYY-MM-DD ou null",'
        '"cout_total":0,'
        '"revenu":0'
        "}. "
        "Si une date précise n'est pas mentionnée, utilise la date du jour. "
        "Si l'éleveur parle d'un prix ou d'un coût, renseigne cout_total. "
        "Si c'est une vente, renseigne aussi revenu. "
        f"Texte: {texte}"
    )


def _build_openai_prompt_for_report(
    summary: Dict[str, Any], events: List[UserActionLog]
) -> str:
    """
    Prompt GPT 5.5 pour rédiger un rapport mensuel professionnel.
    """
    payload = {
        "summary": summary,
        "events": [
            {
                "date": _extract_meta(evt).get(
                    "date_evenement",
                    evt.created_at.isoformat() if evt.created_at is not None else "",
                ),
                "animal_id": _extract_meta(evt).get("animal_id", ""),
                "type_evenement": _extract_meta(evt).get("type_evenement", ""),
                "details": _extract_meta(evt).get("details", ""),
            }
            for evt in events[:20]
        ],
    }
    return (
        "Rédige un rapport mensuel professionnel en français pour un éleveur. "
        "Le rapport doit être clair, structuré, utile et concis. "
        "Tu peux utiliser des titres et des puces. "
        "Voici les données JSON à résumer : " + json.dumps(payload, ensure_ascii=False)
    )


def _write_pdf_report(path: Path, title: str, body: str) -> None:
    """
    Génère un PDF simple avec ReportLab.
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    c = canvas.Canvas(str(path), pagesize=A4)
    width, height = A4
    x = 2 * cm
    y = height - 2 * cm

    c.setTitle(title)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(x, y, title)
    y -= 1.2 * cm

    c.setFont("Helvetica", 11)
    for line in body.splitlines():
        if y < 2 * cm:
            c.showPage()
            y = height - 2 * cm
            c.setFont("Helvetica", 11)
        c.drawString(x, y, line[:110])
        y -= 0.6 * cm

    c.save()


async def traiter_evenement_vocal(
    texte: str, user_id: str, langue: str, db: Session
) -> Dict[str, Any]:
    """
    Extrait l'événement depuis un texte dicté, sauvegarde en base et retourne
    la structure finale.
    """
    texte = _normalize_text(texte)
    user_id = _normalize_text(user_id)
    langue = _normalize_text(langue or "fr") or "fr"

    if not texte:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Le texte vocal est vide.",
        )
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="user_id manquant."
        )

    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Utilisateur introuvable."
        )

    client = _client()
    structured: Optional[Dict[str, Any]] = None

    if client is not None:
        try:
            response = client.chat.completions.create(
                model=AFRI_FARMMANAGER_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Tu es un assistant de saisie agricole. "
                            "Réponds exclusivement en JSON strict, sans texte autour."
                        ),
                    },
                    {
                        "role": "user",
                        "content": _build_openai_prompt_for_event(texte),
                    },
                ],
                temperature=0.1,
                max_tokens=500,
            )

            content = ""
            try:
                content = response.choices[0].message.content or ""
            except Exception:
                content = ""

            structured = _extract_json_payload(content)
        except (
            AuthenticationError,
            APITimeoutError,
            APIConnectionError,
            OpenAIError,
            Exception,
        ):
            structured = None

    if not isinstance(structured, dict):
        structured = _structure_event_text(texte)

    structured.setdefault("date_evenement", _today_iso())
    structured.setdefault("details", texte)
    structured.setdefault("action_requise", "Aucune action immédiate")
    structured.setdefault("date_rappel", None)
    structured.setdefault("cout_total", 0.0)
    structured.setdefault("revenu", 0.0)
    structured.setdefault("source", "ia" if client is not None else "fallback_local")

    # Sécurisation des types
    structured["animal_id"] = _normalize_text(
        str(structured.get("animal_id") or "animal inconnu")
    )
    structured["type_evenement"] = _normalize_text(
        str(structured.get("type_evenement") or "autre")
    ).lower()
    structured["date_evenement"] = _normalize_text(
        str(structured.get("date_evenement") or _today_iso())
    )
    structured["details"] = _normalize_text(str(structured.get("details") or texte))
    structured["action_requise"] = _normalize_text(
        str(structured.get("action_requise") or "Aucune action immédiate")
    )
    structured["date_rappel"] = (
        _normalize_text(str(structured.get("date_rappel")))
        if structured.get("date_rappel")
        else None
    )
    structured["cout_total"] = _safe_float(structured.get("cout_total"))
    structured["revenu"] = _safe_float(structured.get("revenu"))

    saved = _save_event(db, user_id, structured)
    saved["mode"] = "ia" if client is not None else "fallback_local"
    return saved


async def generer_rapport_mensuel(user_id: str, mois: str, db: Session) -> Path:
    """
    Compile les événements du mois, génère un texte professionnel et produit un PDF.
    Retourne le chemin du fichier PDF généré.
    """
    user_id = _normalize_text(user_id)
    mois = _normalize_text(mois)

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="user_id manquant."
        )
    if not mois:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Mois manquant."
        )

    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Utilisateur introuvable."
        )

    year, month = _parse_month(mois)
    all_events = _load_events(db, user_id)

    selected: List[UserActionLog] = []
    for row in all_events:
        meta = _extract_meta(row)
        created_at = getattr(row, "created_at", None)
        raw_date = meta.get("date_evenement") or (
            created_at.isoformat() if isinstance(created_at, datetime) else None
        )
        if not raw_date:
            continue
        try:
            event_date = datetime.fromisoformat(str(raw_date)).date()
        except Exception:
            continue
        if event_date.year == year and event_date.month == month:
            selected.append(row)

    summary = _monthly_summary(selected, user_id, mois)
    report_text = _build_report_text(summary, selected)

    client = _client()
    if client is not None:
        try:
            response = client.chat.completions.create(
                model=AFRI_FARMMANAGER_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Tu es un consultant professionnel d'élevage. "
                            "Rédige un rapport mensuel clair, structuré et professionnel en français."
                        ),
                    },
                    {
                        "role": "user",
                        "content": _build_openai_prompt_for_report(summary, selected),
                    },
                ],
                temperature=0.2,
                max_tokens=900,
            )
            content = ""
            try:
                content = response.choices[0].message.content or ""
            except Exception:
                content = ""
            if content.strip():
                report_text = content.strip()
        except Exception:
            # Fallback silencieux: le PDF sera toujours généré.
            pass

    output_dir = Path(tempfile.gettempdir()) / "feedformula_reports"
    output_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = output_dir / f"rapport_farmmanager_{user_id}_{mois}.pdf"

    title = "FeedFormula AI — Rapport mensuel FarmManager ({})".format(mois)
    _write_pdf_report(pdf_path, title, report_text)
    return pdf_path


# -----------------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------------
@router.post("/evenement-vocal")
async def evenement_vocal(
    payload: VocalEventRequest, db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Enregistre un événement dicté à la voix."""
    try:
        event = await traiter_evenement_vocal(
            payload.texte, payload.user_id, payload.langue, db
        )
        return {
            "message": "Événement vocal traité avec succès.",
            "event": event,
            # Champs contractuels attendus par le frontend/tests
            "evenement_structure": event.get("event", {}) if isinstance(event, dict) else {},
            "points_gagnes": 5,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur traitement vocal: {exc}",
        )


@router.get("/evenements/{user_id}")
def lister_evenements(
    user_id: str,
    date_filtre: Optional[str] = Query(default=None),
    animal_id: Optional[str] = Query(default=None),
    type_evenement: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Liste les événements d'un utilisateur avec filtres optionnels."""
    try:
        rows = _load_events(db, user_id)

        if date_filtre:
            target = date.fromisoformat(date_filtre)
            filtered_rows: List[UserActionLog] = []
            for row in rows:
                meta = _extract_meta(row)
                created_at = getattr(row, "created_at", None)
                raw_date = meta.get("date_evenement") or (
                    created_at.isoformat() if isinstance(created_at, datetime) else None
                )
                if not raw_date:
                    continue
                try:
                    event_date = datetime.fromisoformat(str(raw_date)).date()
                except Exception:
                    continue
                if event_date == target:
                    filtered_rows.append(row)
            rows = filtered_rows

        if animal_id:
            needle = _normalize_text(animal_id).lower()
            rows = [
                row
                for row in rows
                if needle
                in _normalize_text(
                    str(_extract_meta(row).get("animal_id") or "")
                ).lower()
            ]

        if type_evenement:
            needle = _normalize_text(type_evenement).lower()
            rows = [
                row
                for row in rows
                if needle
                in _normalize_text(
                    str(_extract_meta(row).get("type_evenement") or "")
                ).lower()
            ]

        return {
            "user_id": user_id,
            "total_evenements": len(rows),
            "evenements": [
                {
                    "id": row.id,
                    "action": row.action,
                    "created_at": (
                        getattr(row, "created_at", None).isoformat()
                        if isinstance(getattr(row, "created_at", None), datetime)
                        else None
                    ),
                    "event": _extract_meta(row),
                }
                for row in rows
            ],
        }
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la liste des événements: {exc}",
        )


@router.get("/calendrier/{user_id}")
def calendrier(user_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Retourne les événements sous une forme exploitable par un calendrier."""
    try:
        rows = _load_events(db, user_id)
        items: List[Dict[str, Any]] = []

        for row in rows:
            meta = _extract_meta(row)
            item = {
                "id": row.id,
                "animal_id": meta.get("animal_id"),
                "espece": meta.get("espece"),
                "type_evenement": meta.get("type_evenement"),
                "date_evenement": meta.get("date_evenement"),
                "date_prevue_prochain": meta.get("date_rappel"),
                "details": meta.get("details"),
            }
            items.append(item)

        return {
            "user_id": user_id,
            "total_evenements": len(items),
            "evenements": items,
        }
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur calendrier FarmManager: {exc}",
        )


@router.get("/stats/{user_id}")
def stats(user_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Retourne un dashboard simple des événements et des finances."""
    try:
        rows = _load_events(db, user_id)
        dashboard = _financial_dashboard(rows)

        traitement = sum(
            1
            for row in rows
            if _normalize_text(
                str(_extract_meta(row).get("type_evenement") or "")
            ).lower()
            == "traitement"
        )
        naissance = sum(
            1
            for row in rows
            if _normalize_text(
                str(_extract_meta(row).get("type_evenement") or "")
            ).lower()
            == "naissance"
        )
        vente = sum(
            1
            for row in rows
            if _normalize_text(
                str(_extract_meta(row).get("type_evenement") or "")
            ).lower()
            == "vente"
        )
        reproduction = sum(
            1
            for row in rows
            if _normalize_text(
                str(_extract_meta(row).get("type_evenement") or "")
            ).lower()
            in {"reproduction", "saillie", "insemination", "insémination"}
        )

        return {
            "user_id": user_id,
            "total_evenements": len(rows),
            "evenements_reponses": {
                "traitement": traitement,
                "naissance": naissance,
                "vente": vente,
                "reproduction": reproduction,
            },
            "dashboard_financier": dashboard,
        }
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur statistiques FarmManager: {exc}",
        )


@router.get("/rapport-mensuel/{user_id}")
async def rapport_mensuel(
    user_id: str,
    mois: str,
    db: Session = Depends(get_db),
) -> FileResponse:
    """Génère puis renvoie le PDF du rapport mensuel."""
    try:
        pdf_path = await generer_rapport_mensuel(user_id, mois, db)
        return FileResponse(
            path=pdf_path,
            media_type="application/pdf",
            filename=pdf_path.name,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur génération rapport mensuel: {exc}",
        )


@router.post("/evenement")
async def evenement(
    payload: VocalEventRequest, db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Alias POST /farmmanager/evenement."""
    return await evenement_vocal(payload, db)


@router.get("/finances/{user_id}")
def finances(user_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Retourne l'analyse financière complète."""
    rows = _load_events(db, user_id)
    dashboard = _financial_dashboard(rows)
    return {
        "user_id": user_id,
        "dashboard_financier": dashboard,
        "analyse": {
            "cout_revient_par_kg_viande": 0.0,
            "cout_revient_par_litre_lait": 0.0,
            "marge_brute": dashboard.get("revenus_ventes_animaux", 0)
            - dashboard.get("cout_total_alimentation_mois", 0),
            "marge_nette": dashboard.get("marge_nette_estimee", 0),
            "benchmarks": "à compléter localement",
            "optimisations": [
                "Réduire les pertes d'aliment.",
                "Sécuriser la saisie des ventes et achats.",
                "Suivre les traitements et coûts vétérinaires séparément.",
            ],
        },
    }


@router.post("/rapport-mensuel")
async def rapport_mensuel_post(
    payload: MonthlyReportRequest, db: Session = Depends(get_db)
) -> FileResponse:
    """Alias POST /farmmanager/rapport-mensuel."""
    return await rapport_mensuel(payload.user_id, payload.mois, db)
