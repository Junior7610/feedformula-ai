#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Service ReproTrack de FeedFormula AI.

Ce module fournit :
- des calculs de reproduction par espèce,
- un routeur FastAPI dédié,
- une table SQLAlchemy pour historiser les événements,
- des endpoints simples et robustes pour le frontend.

Tous les commentaires sont en français pour faciliter la maintenance.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Session, relationship

# -----------------------------------------------------------------------------
# Imports locaux compatibles package/script
# -----------------------------------------------------------------------------
try:
    from .database import Base, User, get_db, get_user_by_id
except Exception:
    from database import Base, User, get_db, get_user_by_id  # type: ignore


# -----------------------------------------------------------------------------
# Modèle ORM local
# -----------------------------------------------------------------------------
class EvenementReproductionORM(Base):
    """
    Table evenements_reproduction.

    Cette table est définie ici pour ne pas dépendre d'une version antérieure
    du module de base de données. Elle sera créée par `init_db()` si le module
    est importé avant l'initialisation de la base.
    """

    __tablename__ = "evenements_reproduction"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    animal_id = Column(String(120), nullable=False, index=True)
    espece = Column(String(80), nullable=False, index=True)
    type_evenement = Column(String(80), nullable=False, index=True)
    date_evenement = Column(DateTime, nullable=False, index=True)
    date_prevue_prochain = Column(DateTime, nullable=True, index=True)
    notes = Column(Text, nullable=True)
    date_creation = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    user = relationship("User")


# -----------------------------------------------------------------------------
# Outils internes
# -----------------------------------------------------------------------------
def _uuid_str() -> str:
    """Retourne un identifiant texte simple pour les lignes ReproTrack."""
    import uuid

    return str(uuid.uuid4())


def _clean_text(value: Optional[str]) -> str:
    """Nettoie une chaîne texte."""
    return " ".join((value or "").strip().split())


def _parse_datetime(value: Any) -> datetime:
    """
    Convertit une entrée en datetime.

    Accepte :
    - datetime
    - date
    - chaîne ISO
    - chaîne au format YYYY-MM-DD
    """
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    if isinstance(value, str):
        txt = value.strip()
        if not txt:
            raise ValueError("Date/heure vide.")
        try:
            return datetime.fromisoformat(txt)
        except Exception:
            try:
                return datetime.strptime(txt, "%Y-%m-%d")
            except Exception as exc:
                raise ValueError(f"Format de date invalide: {txt}") from exc
    raise ValueError("Type de date non supporté.")


def _parse_date(value: Any) -> date:
    """Convertit une entrée en date."""
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        txt = value.strip()
        if not txt:
            raise ValueError("Date vide.")
        try:
            return date.fromisoformat(txt)
        except Exception as exc:
            raise ValueError(f"Format de date invalide: {txt}") from exc
    raise ValueError("Type de date non supporté.")


def _species_key(espece: str) -> str:
    """Normalise le nom de l'espèce pour la logique métier."""
    return _clean_text(espece).lower()


# -----------------------------------------------------------------------------
# Service métier
# -----------------------------------------------------------------------------
class ReproTrackService:
    """
    Service métier ReproTrack.

    Les règles sont volontairement simples, lisibles et faciles à faire évoluer.
    """

    # Cycles oestraux et gestations utilisés dans l'application
    CYCLES_CHALEURS = {
        "vache": 21,
        "chevre": 21,
        "mouton": 21,
        "porc": 21,
        "lapin": 16,
    }

    GESTATIONS = {
        "vache": 283,
        "chevre": 150,
        "mouton": 147,
        "porc": 114,
        "lapin": 31,
    }

    def predire_prochaines_chaleurs(self, espece: str, date_derniere_chaleur: Any) -> List[Dict[str, Any]]:
        """
        Calcule les prochaines périodes de chaleur pour une espèce donnée.

        Retour :
            [
                {"date": "...", "probabilite": 0.72},
                ...
            ]
        """
        espece_norm = _species_key(espece)
        date_base = _parse_datetime(date_derniere_chaleur)
        cycle = self.CYCLES_CHALEURS.get(espece_norm, 21)

        # Probabilité décroissante avec le temps.
        resultats: List[Dict[str, Any]] = []
        for i, facteur in enumerate([1.0, 1.2, 1.5], start=1):
            prochaine_date = date_base + timedelta(days=cycle * i)
            probabilite = max(0.35, min(0.95, 0.88 - (i - 1) * 0.15))
            # Ajustement simplifié pour espèces saisonnières.
            if espece_norm in {"chevre", "mouton"}:
                probabilite = max(0.25, probabilite - 0.08)
            resultats.append(
                {
                    "date": prochaine_date.date().isoformat(),
                    "probabilite": round(probabilite, 2),
                    "jours_apres": cycle * i,
                }
            )
        return resultats

    def calculer_date_mise_bas(self, espece: str, date_saillie: Any) -> Dict[str, Any]:
        """
        Calcule la date prévue de mise-bas selon l'espèce.

        Retour :
            {
              "date_prevue": "...",
              "alerte_48h": "...",
              "jours_gestation": 114
            }
        """
        espece_norm = _species_key(espece)
        if espece_norm not in self.GESTATIONS:
            # Valeur de repli raisonnable
            jours = 150
        else:
            jours = self.GESTATIONS[espece_norm]

        debut = _parse_datetime(date_saillie)
        date_prevue = debut + timedelta(days=jours)
        alerte_48h = date_prevue - timedelta(hours=48)

        return {
            "date_prevue": date_prevue.isoformat(),
            "alerte_48h": alerte_48h.isoformat(),
            "jours_gestation": jours,
        }

    def calculer_taux_gestation(self, user_id: str, db: Session) -> Dict[str, Any]:
        """
        Calcule un taux de gestation indicatif basé sur les événements stockés.

        La logique est volontairement simple :
        - type_evenement = "mise-bas" => succès
        - type_evenement = "saillie" ou "insemination" => exposition
        """
        user_id = (user_id or "").strip()
        if not user_id:
            return {"taux_gestation": 0.0, "confiance": 0.0, "total_evenements": 0}

        evenements = (
            db.query(EvenementReproductionORM)
            .filter(EvenementReproductionORM.user_id == user_id)
            .all()
        )

        total_expositions = 0
        total_success = 0

        for evenement in evenements:
            type_evt = _clean_text(evenement.type_evenement).lower()
            if type_evt in {"saillie", "insemination", "insémination"}:
                total_expositions += 1
            elif type_evt in {"mise-bas", "mise bas", "misebas"}:
                total_success += 1

        if total_expositions == 0:
            return {"taux_gestation": 0.0, "confiance": 0.0, "total_evenements": len(evenements)}

        taux = (total_success / max(1, total_expositions)) * 100.0
        confiance = min(0.98, 0.4 + (len(evenements) / 50.0))
        return {
            "taux_gestation": round(taux, 2),
            "confiance": round(confiance, 2),
            "total_evenements": len(evenements),
            "expositions": total_expositions,
            "naissances": total_success,
        }

    def enregistrer_evenement(
        self,
        db: Session,
        user_id: str,
        animal_id: str,
        espece: str,
        type_evenement: str,
        date_evenement: Any,
        date_prevue_prochain: Any = None,
        notes: Optional[str] = None,
    ) -> EvenementReproductionORM:
        """Crée un événement reproduction en base."""
        user = get_user_by_id(db, user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Utilisateur introuvable.")

        evenement = EvenementReproductionORM(
            id=_uuid_str(),
            user_id=user_id,
            animal_id=_clean_text(animal_id),
            espece=_clean_text(espece),
            type_evenement=_clean_text(type_evenement),
            date_evenement=_parse_datetime(date_evenement),
            date_prevue_prochain=_parse_datetime(date_prevue_prochain) if date_prevue_prochain else None,
            notes=_clean_text(notes) or None,
            date_creation=datetime.utcnow(),
        )
        db.add(evenement)
        db.commit()
        db.refresh(evenement)
        return evenement

    def lister_evenements(self, db: Session, user_id: str, limit: int = 100) -> List[EvenementReproductionORM]:
        """Retourne les événements reproduction d'un utilisateur."""
        limite = max(1, min(int(limit or 100), 500))
        return (
            db.query(EvenementReproductionORM)
            .filter(EvenementReproductionORM.user_id == (user_id or "").strip())
            .order_by(EvenementReproductionORM.date_evenement.desc())
            .limit(limite)
            .all()
        )

    def obtenir_alertes(self, db: Session, user_id: str) -> List[Dict[str, Any]]:
        """Construit des alertes simplifiées à partir des événements."""
        evenements = self.lister_evenements(db, user_id, limit=200)
        alertes: List[Dict[str, Any]] = []

        for evt in evenements:
            type_evt = _clean_text(evt.type_evenement).lower()
            if type_evt in {"saillie", "insemination", "insémination"} and evt.date_prevue_prochain:
                alerte_date = evt.date_prevue_prochain - timedelta(hours=48)
                alertes.append(
                    {
                        "type": "mise-bas_proche",
                        "animal_id": evt.animal_id,
                        "espece": evt.espece,
                        "message": f"Mise-bas probable autour du {evt.date_prevue_prochain.date().isoformat()}",
                        "date_alerte": alerte_date.isoformat(),
                    }
                )

            if type_evt in {"chaleur", "chaleur observée", "chaleur_observee"}:
                predictions = self.predire_prochaines_chaleurs(evt.espece, evt.date_evenement)
                alertes.append(
                    {
                        "type": "chaleurs",
                        "animal_id": evt.animal_id,
                        "espece": evt.espece,
                        "message": "Fenêtres de chaleur calculées.",
                        "predictions": predictions,
                    }
                )

        return alertes[:20]


# Instance globale du service
SERVICE = ReproTrackService()


# -----------------------------------------------------------------------------
# Schémas Pydantic
# -----------------------------------------------------------------------------
class ReproTrackEventRequest(BaseModel):
    """Schéma d'entrée pour l'enregistrement d'un événement."""

    user_id: str = Field(..., min_length=3)
    animal_id: str = Field(..., min_length=1)
    espece: str = Field(..., min_length=1)
    type_evenement: str = Field(..., min_length=1)
    date_evenement: str = Field(..., min_length=1)
    date_prevue_prochain: Optional[str] = None
    notes: Optional[str] = None

    @field_validator("user_id", "animal_id", "espece", "type_evenement", "date_evenement")
    @classmethod
    def _strip_required(cls, value: str) -> str:
        txt = _clean_text(value)
        if not txt:
            raise ValueError("Champ obligatoire vide.")
        return txt


class ReproTrackCalendarResponse(BaseModel):
    """Réponse du calendrier ReproTrack."""

    user_id: str
    total_evenements: int
    evenements: List[Dict[str, Any]]


# -----------------------------------------------------------------------------
# Routeur FastAPI
# -----------------------------------------------------------------------------
router = APIRouter(prefix="/reprotrack", tags=["ReproTrack"])


@router.post("/evenement")
def enregistrer_evenement(
    payload: ReproTrackEventRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Enregistre un événement reproduction.
    """
    try:
        evenement = SERVICE.enregistrer_evenement(
            db=db,
            user_id=payload.user_id,
            animal_id=payload.animal_id,
            espece=payload.espece,
            type_evenement=payload.type_evenement,
            date_evenement=payload.date_evenement,
            date_prevue_prochain=payload.date_prevue_prochain,
            notes=payload.notes,
        )
        return {
            "message": "Événement enregistré avec succès.",
            "evenement": {
                "id": evenement.id,
                "user_id": evenement.user_id,
                "animal_id": evenement.animal_id,
                "espece": evenement.espece,
                "type_evenement": evenement.type_evenement,
                "date_evenement": evenement.date_evenement.isoformat() if evenement.date_evenement else None,
                "date_prevue_prochain": evenement.date_prevue_prochain.isoformat() if evenement.date_prevue_prochain else None,
                "notes": evenement.notes,
                "date_creation": evenement.date_creation.isoformat() if evenement.date_creation else None,
            },
        }
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erreur /reprotrack/evenement: {exc}")


@router.get("/calendrier/{user_id}")
def get_calendrier(user_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Retourne l'historique des événements ReproTrack d'un utilisateur.
    """
    try:
        evenements = SERVICE.lister_evenements(db, user_id, limit=120)
        return {
            "user_id": user_id,
            "total_evenements": len(evenements),
            "evenements": [
                {
                    "id": evt.id,
                    "animal_id": evt.animal_id,
                    "espece": evt.espece,
                    "type_evenement": evt.type_evenement,
                    "date_evenement": evt.date_evenement.isoformat() if evt.date_evenement else None,
                    "date_prevue_prochain": evt.date_prevue_prochain.isoformat() if evt.date_prevue_prochain else None,
                    "notes": evt.notes,
                }
                for evt in evenements
            ],
        }
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erreur /reprotrack/calendrier: {exc}")


@router.get("/alertes/{user_id}")
def get_alertes(user_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Retourne les alertes ReproTrack d'un utilisateur.
    """
    try:
        alertes = SERVICE.obtenir_alertes(db, user_id)
        return {"user_id": user_id, "total_alertes": len(alertes), "alertes": alertes}
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erreur /reprotrack/alertes: {exc}")


@router.get("/stats/{user_id}")
def get_stats(user_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Retourne les statistiques reproduction d'un utilisateur.
    """
    try:
        taux = SERVICE.calculer_taux_gestation(user_id, db)
        evenements = SERVICE.lister_evenements(db, user_id, limit=300)

        total_saillies = sum(
            1
            for evt in evenements
            if _clean_text(evt.type_evenement).lower() in {"saillie", "insemination", "insémination"}
        )
        total_mises_bas = sum(
            1
            for evt in evenements
            if _clean_text(evt.type_evenement).lower() in {"mise-bas", "mise bas", "misebas"}
        )

        return {
            "user_id": user_id,
            "taux_gestation_global": taux.get("taux_gestation", 0.0),
            "confiance_calcul": taux.get("confiance", 0.0),
            "total_evenements": taux.get("total_evenements", len(evenements)),
            "total_saillies": total_saillies,
            "total_mises_bas": total_mises_bas,
            "evenements": [
                {
                    "id": evt.id,
                    "animal_id": evt.animal_id,
                    "espece": evt.espece,
                    "type_evenement": evt.type_evenement,
                    "date_evenement": evt.date_evenement.isoformat() if evt.date_evenement else None,
                    "date_prevue_prochain": evt.date_prevue_prochain.isoformat() if evt.date_prevue_prochain else None,
                }
                for evt in evenements[:20]
            ],
        }
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erreur /reprotrack/stats: {exc}")


__all__ = [
    "EvenementReproductionORM",
    "ReproTrackService",
    "ReproTrackEventRequest",
    "ReproTrackCalendarResponse",
    "router",
    "SERVICE",
]
