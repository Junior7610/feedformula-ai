#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
API de gamification FeedFormula AI.

Endpoints implémentés :
- POST /gamification/action
- GET  /gamification/profil/{user_id}
- GET  /gamification/classement
- GET  /gamification/classement/{region}
- POST /gamification/defi/completer
- GET  /gamification/defis-du-jour

Notes d'implémentation :
- Les compteurs d'actions utilisateur sont conservés en mémoire (MVP).
- Les données principales (utilisateurs, défis quotidiens, complétions, trophées) sont persistées en base.
- Tous les commentaires sont en français pour faciliter la maintenance.
"""

from __future__ import annotations

import random
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

# ---------------------------------------------------------------------------
# Imports locaux (compatibles package/script)
# ---------------------------------------------------------------------------
try:
    from .database import (
        add_points_to_user,
        complete_defi,
        count_user_actions_last_24h,
        create_or_update_defi_quotidien,
        create_trophee_for_user,
        get_db,
        get_defi_quotidien_by_date,
        get_last_action_at,
        get_user_action_counts,
        get_user_by_id,
        list_top_users_by_points,
        list_user_completions_defis,
        list_user_trophees,
        log_user_action,
        serialize_defi_quotidien,
        serialize_trophee,
        serialize_user,
        update_user_last_login,
        update_user_streak,
    )
except Exception:
    from database import (  # type: ignore
        add_points_to_user,
        complete_defi,
        count_user_actions_last_24h,
        create_or_update_defi_quotidien,
        create_trophee_for_user,
        get_db,
        get_defi_quotidien_by_date,
        get_last_action_at,
        get_user_action_counts,
        get_user_by_id,
        list_top_users_by_points,
        list_user_completions_defis,
        list_user_trophees,
        log_user_action,
        serialize_defi_quotidien,
        serialize_trophee,
        serialize_user,
        update_user_last_login,
        update_user_streak,
    )

# Import robuste du moteur de gamification.
try:
    from gamification.points_engine import GamificationEngine
except Exception:
    import sys

    ROOT_DIR = Path(__file__).resolve().parent.parent
    if str(ROOT_DIR) not in sys.path:
        sys.path.append(str(ROOT_DIR))
    from gamification.points_engine import GamificationEngine  # type: ignore


# ---------------------------------------------------------------------------
# État applicatif (MVP)
# ---------------------------------------------------------------------------
ENGINE = GamificationEngine()

# Codes langues utilisées par utilisateur (complément trophées)
# { user_id: {"fr", "fon"} }
USER_LANGUES: Dict[str, Set[str]] = {}

# Modules utilisés (complément trophées)
# { user_id: {"nutricore", "vetscan"} }
USER_MODULES: Dict[str, Set[str]] = {}

# Espèces suivies (complément trophées)
# { user_id: {"poulet", "porc"} }
USER_ESPECES: Dict[str, Set[str]] = {}


# ---------------------------------------------------------------------------
# Utilitaires internes
# ---------------------------------------------------------------------------
def _today_utc() -> date:
    """Retourne la date du jour en UTC."""
    return datetime.now(timezone.utc).date()


def _safe_int(value: Any, default: int = 0) -> int:
    """Convertit en int avec fallback."""
    try:
        return int(value)
    except Exception:
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    """Convertit en float avec fallback."""
    try:
        return float(value)
    except Exception:
        return default


def _normaliser_region(region: Optional[str]) -> str:
    """Normalise un nom de région/département."""
    txt = (region or "").strip()
    if not txt:
        return "Bénin"
    return " ".join(txt.split())


def _get_actions_count(db: Session, user_id: str) -> Dict[str, int]:
    """Retourne la map des actions d'un utilisateur depuis les logs persistés."""
    return get_user_action_counts(db, user_id, days=365)


def _ensure_defis_du_jour(db: Session) -> Dict[str, Any]:
    """
    Retourne les défis du jour.
    Si absents en base, les génère puis les persiste.
    """
    jour = _today_utc()
    defi_db = get_defi_quotidien_by_date(db, jour)
    if defi_db:
        return serialize_defi_quotidien(defi_db)

    # Source de défis depuis le moteur ; fallback sûr.
    pool = list(getattr(ENGINE, "DEFIS_QUOTIDIENS", []) or [])
    if len(pool) < 3:
        pool = [
            {"id": "d1_connexion", "nom": "Présence du jour", "action": "connexion_jour", "objectif": 1, "bonus_points": 10},
            {"id": "d2_ration", "nom": "Une ration utile", "action": "generation_ration", "objectif": 1, "bonus_points": 20},
            {"id": "d3_communaute", "nom": "Aide communautaire", "action": "commentaire_utile_farmcommunity", "objectif": 1, "bonus_points": 12},
        ]

    # Sélection déterministe par jour (évite les variations entre appels).
    rnd = random.Random(jour.toordinal())
    selection = rnd.sample(pool, k=3) if len(pool) >= 3 else pool[:3]

    created = create_or_update_defi_quotidien(
        db=db,
        jour=jour,
        defi_1=selection[0],
        defi_2=selection[1],
        defi_3=selection[2],
    )
    return serialize_defi_quotidien(created)


def _build_user_stats_for_trophees(db: Session, user_id: str) -> Dict[str, Any]:
    """
    Construit la structure attendue par ENGINE.verifier_trophees.
    """
    user = get_user_by_id(db, user_id)
    if not user:
        return {}

    deja = [t.trophee_code for t in list_user_trophees(db, user_id)]

    return {
        "points_total": _safe_int(user.points_total, 0),
        "actions_count": _get_actions_count(db, user_id),
        "serie_actuelle": _safe_int(user.serie_actuelle, 0),
        "langues_locales_utilisees": sorted(USER_LANGUES.get(user_id, set())),
        "modules_utilises": sorted(USER_MODULES.get(user_id, set())),
        "especes_suivies": sorted(USER_ESPECES.get(user_id, set())),
        "quiz_taux_reussite_pct": 0.0,
        "trophees_deja_obtenus": deja,
    }


def _attribuer_nouveaux_trophees(db: Session, user_id: str) -> List[Dict[str, Any]]:
    """
    Calcule et attribue les nouveaux trophées d'un utilisateur.
    Retourne la liste sérialisée des trophées effectivement attribués.
    """
    stats = _build_user_stats_for_trophees(db, user_id)
    if not stats:
        return []

    nouveaux = ENGINE.verifier_trophees(stats)
    attribues: List[Dict[str, Any]] = []

    for troph in nouveaux:
        code = str(troph.get("id", "")).strip()
        if not code:
            continue
        created = create_trophee_for_user(db, user_id, code)
        if created:
            attribues.append(serialize_trophee(created))

    return attribues


def _calculer_ligue(points_total: int) -> Dict[str, Any]:
    """
    Calcule la ligue via le moteur central de gamification.
    """
    details = ENGINE.determiner_ligue(max(0, _safe_int(points_total, 0)))
    ligue = details.get("ligue_actuelle", {}) if isinstance(details, dict) else {}
    return {
        "nom": ligue.get("nom", "Bronze"),
        "icone": ligue.get("icone", "🥉"),
        "code": ligue.get("code", "bronze"),
        "points_restant_pour_monter": details.get("points_restant_pour_monter", 0) if isinstance(details, dict) else 0,
    }


# ---------------------------------------------------------------------------
# Schémas Pydantic
# ---------------------------------------------------------------------------
class ActionRequest(BaseModel):
    user_id: str = Field(..., min_length=3)
    action: str = Field(..., min_length=2)
    code_langue: str = Field(default="fr")
    offline_mode: bool = Field(default=False)
    multiplicateur_evenement: float = Field(default=1.0)
    region: Optional[str] = Field(default=None)
    module: Optional[str] = Field(default=None)
    espece: Optional[str] = Field(default=None)

    @field_validator("user_id", "action")
    @classmethod
    def _strip_required(cls, v: str) -> str:
        txt = (v or "").strip()
        if not txt:
            raise ValueError("Champ obligatoire vide.")
        return txt

    @field_validator("multiplicateur_evenement")
    @classmethod
    def _validate_multiplier(cls, v: float) -> float:
        if v <= 0:
            return 1.0
        return min(v, 10.0)


class DefiCompleterRequest(BaseModel):
    user_id: str = Field(..., min_length=3)
    defi_numero: int = Field(..., ge=1, le=3)

    @field_validator("user_id")
    @classmethod
    def _strip_user_id(cls, v: str) -> str:
        txt = (v or "").strip()
        if not txt:
            raise ValueError("user_id invalide.")
        return txt


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------
router = APIRouter(prefix="/gamification", tags=["gamification"])


@router.post("/action")
def enregistrer_action(payload: ActionRequest, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Enregistre une action utilisateur, applique l'anti-abus et persiste le log.
    """
    user = get_user_by_id(db, payload.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur introuvable.",
        )

    # Contexte anti-abus persistant (basé sur les logs DB).
    nb_actions_24h = count_user_actions_last_24h(db, payload.user_id)
    last_same_action_at = get_last_action_at(db, payload.user_id, payload.action)
    cooldown_actif = False
    if last_same_action_at is not None:
        cooldown_actif = (datetime.utcnow() - last_same_action_at) < timedelta(seconds=20)

    # Contexte pour le moteur de points.
    contexte = {
        "code_langue": (payload.code_langue or "fr").strip().lower(),
        "serie_actuelle": _safe_int(getattr(user, "serie_actuelle", 0), 0),
        "offline_mode": bool(payload.offline_mode),
        "multiplicateur_evenement": float(payload.multiplicateur_evenement),
        "nb_actions_24h": nb_actions_24h,
        "cooldown_actif": cooldown_actif,
    }

    # Calcul points.
    try:
        points_info = ENGINE.calculer_points(payload.action, contexte)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )

    points_total_action = _safe_int(points_info.get("points_total", 0), 0)
    if points_total_action <= 0:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Action temporairement refusée (anti-abus/cooldown).",
        )

    # Mémoires complémentaires (langues/modules/espèces) pour trophées.
    if payload.code_langue:
        USER_LANGUES.setdefault(payload.user_id, set()).add(payload.code_langue.strip().lower())
    if payload.module:
        USER_MODULES.setdefault(payload.user_id, set()).add(payload.module.strip().lower())
    if payload.espece:
        USER_ESPECES.setdefault(payload.user_id, set()).add(payload.espece.strip().lower())

    # Persistance région utilisateur.
    if payload.region:
        user.region = _normaliser_region(payload.region)
        db.commit()
        db.refresh(user)

    # Gestion de série pour connexion journalière.
    serie_info: Optional[Dict[str, Any]] = None
    if payload.action == "connexion_jour":
        today = _today_utc()
        last_conn = getattr(user, "derniere_connexion", None)
        serie_calculee = 1
        if last_conn is not None:
            diff = (today - last_conn.date()).days
            if diff == 0:
                serie_calculee = _safe_int(getattr(user, "serie_actuelle", 0), 0)
            elif diff == 1:
                serie_calculee = _safe_int(getattr(user, "serie_actuelle", 0), 0) + 1
            elif diff == 2 and _safe_int(getattr(user, "graines_secours", 0), 0) > 0:
                user.graines_secours = max(0, _safe_int(user.graines_secours, 0) - 1)
                db.commit()
                db.refresh(user)
                serie_calculee = _safe_int(getattr(user, "serie_actuelle", 0), 0) + 1
            else:
                serie_calculee = 1

        update_user_streak(db, payload.user_id, serie_calculee)
        update_user_last_login(db, payload.user_id)
        serie_info = {
            "serie_actuelle": serie_calculee,
            "graines_restantes": _safe_int(getattr(user, "graines_secours", 0), 0),
        }

    # Persistance points utilisateur.
    user_updated = add_points_to_user(db, payload.user_id, points_total_action)
    if not user_updated:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Impossible de mettre à jour les points utilisateur.",
        )

    # Log persistant de l'action.
    log_user_action(
        db=db,
        user_id=payload.user_id,
        action=payload.action,
        points_awarded=points_total_action,
        meta={
            "code_langue": payload.code_langue,
            "offline_mode": payload.offline_mode,
            "multiplicateur_evenement": payload.multiplicateur_evenement,
            "nb_actions_24h": nb_actions_24h,
            "cooldown_actif": cooldown_actif,
            "region": getattr(user_updated, "region", "Bénin"),
        },
    )

    # Évalue et attribue les trophées potentiels.
    nouveaux_trophees = _attribuer_nouveaux_trophees(db, payload.user_id)

    # Données niveau/progression.
    niveau_info = ENGINE.determiner_niveau(_safe_int(user_updated.points_total, 0))
    ligue = _calculer_ligue(_safe_int(user_updated.points_total, 0))

    return {
        "message": "Action enregistrée avec succès.",
        "action": payload.action,
        "points": points_info,
        "user": serialize_user(user_updated),
        "niveau": niveau_info,
        "ligue": ligue,
        "serie": serie_info,
        "nouveaux_trophees": nouveaux_trophees,
    }


@router.get("/profil/{user_id}")
def profil_gamification(user_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Retourne le profil gamification d'un utilisateur :
    - niveau
    - points
    - trophées
    - série
    """
    uid = (user_id or "").strip()
    if not uid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="user_id invalide.",
        )

    user = get_user_by_id(db, uid)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur introuvable.",
        )

    user_data = serialize_user(user)
    niveau_info = ENGINE.determiner_niveau(_safe_int(user.points_total, 0))
    ligue = _calculer_ligue(_safe_int(user.points_total, 0))
    trophees = [serialize_trophee(t) for t in list_user_trophees(db, uid)]

    return {
        "user": user_data,
        "niveau": niveau_info,
        "ligue": ligue,
        "points_total": _safe_int(user.points_total, 0),
        "serie_actuelle": _safe_int(user.serie_actuelle, 0),
        "meilleure_serie": _safe_int(user.meilleure_serie, 0),
        "trophees": trophees,
        "actions_count": _get_actions_count(db, uid),
    }


@router.get("/classement")
def classement_global(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Retourne le top 50 des utilisateurs par points.
    """
    users = list_top_users_by_points(db, limit=50)
    classement: List[Dict[str, Any]] = []

    for idx, u in enumerate(users, start=1):
        ligue = _calculer_ligue(_safe_int(getattr(u, "points_total", 0), 0))
        classement.append(
            {
                "rang": idx,
                "user_id": u.id,
                "prenom": getattr(u, "prenom", ""),
                "points_total": _safe_int(getattr(u, "points_total", 0), 0),
                "niveau_actuel": _safe_int(getattr(u, "niveau_actuel", 1), 1),
                "ligue": ligue,
                "region": getattr(u, "region", "Bénin"),
            }
        )

    return {"scope": "national", "total": len(classement), "classement": classement}


@router.get("/classement/{region}")
def classement_par_region(region: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Retourne le classement (top 50) filtré par département/région.
    """
    region_norm = _normaliser_region(region)
    users = list_top_users_by_points(db, limit=300)

    filtre: List[Dict[str, Any]] = []
    for u in users:
        region_user = getattr(u, "region", "Bénin")
        if region_user.lower() == region_norm.lower():
            filtre.append(
                {
                    "user_id": u.id,
                    "prenom": getattr(u, "prenom", ""),
                    "points_total": _safe_int(getattr(u, "points_total", 0), 0),
                    "niveau_actuel": _safe_int(getattr(u, "niveau_actuel", 1), 1),
                    "ligue": _calculer_ligue(_safe_int(getattr(u, "points_total", 0), 0)),
                    "region": region_user,
                }
            )

    filtre = sorted(filtre, key=lambda x: int(x["points_total"]), reverse=True)[:50]
    for i, item in enumerate(filtre, start=1):
        item["rang"] = i

    return {
        "scope": "region",
        "region": region_norm,
        "total": len(filtre),
        "classement": filtre,
    }


@router.post("/defi/completer")
def completer_defi(payload: DefiCompleterRequest, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Marque un défi quotidien comme complété (si objectif atteint) et crédite les points bonus.
    """
    user = get_user_by_id(db, payload.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur introuvable.",
        )

    defis_jour = _ensure_defis_du_jour(db)
    defi_id = str(defis_jour.get("id", "")).strip()

    # Récupère le défi ciblé (defi_1/2/3).
    key = f"defi_{payload.defi_numero}"
    defi_data = defis_jour.get(key)
    if not isinstance(defi_data, dict):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Défi du jour introuvable ({key}).",
        )

    action = str(defi_data.get("action", "")).strip()
    objectif = _safe_int(defi_data.get("objectif", 1), 1)
    bonus_points = max(0, _safe_int(defi_data.get("bonus_points", 0), 0))

    # Vérifie la progression utilisateur sur l'action demandée.
    realise = _safe_int(_get_actions_count(db, payload.user_id).get(action, 0), 0)
    if realise < objectif:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Objectif non atteint pour ce défi: {realise}/{objectif}.",
        )

    # Vérifie déjà complété.
    completions = list_user_completions_defis(db, payload.user_id, limit=500)
    deja = any(
        str(c.defi_id) == defi_id and _safe_int(getattr(c, "defi_numero", 0), 0) == payload.defi_numero
        for c in completions
    )
    if deja:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ce défi a déjà été complété.",
        )

    # Persiste complétion.
    completion = complete_defi(
        db=db,
        user_id=payload.user_id,
        defi_id=defi_id,
        defi_numero=payload.defi_numero,
        points_gagnes=bonus_points,
    )
    if completion is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Impossible d'enregistrer la complétion du défi.",
        )

    # Ajoute points bonus + log persistant d'action de défi complété.
    user_updated = add_points_to_user(db, payload.user_id, bonus_points)
    log_user_action(
        db=db,
        user_id=payload.user_id,
        action="defi_quotidien_complete",
        points_awarded=bonus_points,
        meta={
            "defi_id": defi_data.get("id"),
            "defi_numero": payload.defi_numero,
            "objectif": objectif,
            "realise": realise,
        },
    )

    # Ré-évalue trophées.
    nouveaux_trophees = _attribuer_nouveaux_trophees(db, payload.user_id)

    return {
        "message": "Défi complété avec succès.",
        "defi": {
            "numero": payload.defi_numero,
            "id": defi_data.get("id"),
            "nom": defi_data.get("nom"),
            "action": action,
            "objectif": objectif,
            "realise": realise,
            "bonus_points": bonus_points,
        },
        "completion_id": completion.id,
        "user": serialize_user(user_updated) if user_updated else serialize_user(user),
        "nouveaux_trophees": nouveaux_trophees,
    }


@router.get("/defis-du-jour")
def defis_du_jour(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Retourne les 3 défis quotidiens (création automatique si absents).
    """
    defis_jour = _ensure_defis_du_jour(db)
    return {
        "date": defis_jour.get("date"),
        "defis": [
            defis_jour.get("defi_1"),
            defis_jour.get("defi_2"),
            defis_jour.get("defi_3"),
        ],
        "meta": {"source": "database", "timezone": "UTC"},
    }


__all__ = ["router"]
