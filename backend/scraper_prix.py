#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Service marché / prix de référence pour FeedFormula AI.

Objectifs :
- Fournir les prix de référence des ingrédients agricoles.
- Permettre la mise à jour manuelle des prix.
- Conserver un historique simple des variations.
- Exposer un routeur FastAPI pour l'API métier.

Tous les commentaires sont en français pour faciliter la maintenance.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

# ---------------------------------------------------------------------------
# Imports locaux compatibles package / exécution directe
# ---------------------------------------------------------------------------
try:
    from .database import (
        add_prix_marche,
        get_db,
        get_latest_prix_for_ingredient,
        serialize_prix_marche,
    )
except Exception:
    from database import (  # type: ignore
        add_prix_marche,
        get_db,
        get_latest_prix_for_ingredient,
        serialize_prix_marche,
    )


# ---------------------------------------------------------------------------
# Routeur FastAPI
# ---------------------------------------------------------------------------
router = APIRouter(prefix="/marche", tags=["Marché"])


# ---------------------------------------------------------------------------
# Prix de référence hardcodés
# ---------------------------------------------------------------------------
PRIX_REFERENCE: Dict[str, float] = {
    "mais": 250,
    "tourteau_soja": 450,
    "farine_poisson": 800,
    "son_ble": 150,
    "tourteau_arachide": 380,
    "tourteau_coton": 300,
    "manioc": 180,
    "mil": 220,
    "farine_os": 350,
    "premix_volaille": 1200,
}


# Historique en mémoire pour les environnements sans persistance complète.
HISTORIQUE_MEMOIRE: Dict[str, List[Dict[str, Any]]] = {}


# ---------------------------------------------------------------------------
# Schémas Pydantic
# ---------------------------------------------------------------------------
class MiseAJourPrixRequest(BaseModel):
    """Schéma pour la mise à jour manuelle d'un prix marché."""

    ingredient: str = Field(..., min_length=1)
    prix_fcfa_kg: float = Field(..., gt=0)
    source: Optional[str] = Field(default=None)
    region: str = Field(default="Bénin")

    @classmethod
    def _nettoyer(cls, value: str) -> str:
        return " ".join((value or "").strip().split()).lower()


# ---------------------------------------------------------------------------
# Utilitaires internes
# ---------------------------------------------------------------------------
def _normaliser_ingredient(ingredient: str) -> str:
    """Normalise le nom d'un ingrédient pour les clés de dictionnaire."""
    return " ".join((ingredient or "").strip().split()).lower()


def _enregistrer_historique(
    ingredient: str,
    prix_fcfa_kg: float,
    source: Optional[str] = None,
    region: str = "Bénin",
) -> Dict[str, Any]:
    """
    Ajoute une entrée à l'historique mémoire.

    Cette fonction est utilisée en complément de la base de données afin de
    conserver une trace légère des mises à jour.
    """
    cle = _normaliser_ingredient(ingredient)
    entree = {
        "ingredient": cle,
        "prix_fcfa_kg": float(prix_fcfa_kg),
        "source": source,
        "region": region,
        "date_mise_a_jour": datetime.utcnow().isoformat(),
    }
    HISTORIQUE_MEMOIRE.setdefault(cle, []).append(entree)
    HISTORIQUE_MEMOIRE[cle] = HISTORIQUE_MEMOIRE[cle][-30:]
    return entree


# ---------------------------------------------------------------------------
# Fonctions métier
# ---------------------------------------------------------------------------
def get_prix_actuels(db: Optional[Session] = None) -> Dict[str, float]:
    """
    Retourne tous les prix actuels.

    Priorité :
    1) Prix les plus récents en base de données si une session est fournie
    2) Prix de référence hardcodés
    """
    prix = dict(PRIX_REFERENCE)

    if db is None:
        return prix

    for ingredient in list(PRIX_REFERENCE.keys()):
        latest = get_latest_prix_for_ingredient(db, ingredient)
        if latest is not None:
            prix[ingredient] = float(latest.prix_fcfa_kg or prix[ingredient])

    return prix


def mettre_a_jour_prix(
    ingredient: str,
    prix: float,
    source: Optional[str] = None,
    region: str = "Bénin",
    db: Optional[Session] = None,
) -> Dict[str, Any]:
    """
    Met à jour le prix d'un ingrédient.

    - Si une session DB est fournie, la mise à jour est persistée.
    - Sinon, l'entrée est conservée dans l'historique mémoire.
    """
    ingr = _normaliser_ingredient(ingredient)
    if not ingr:
        raise ValueError("Le nom de l'ingrédient est obligatoire.")
    if float(prix or 0) <= 0:
        raise ValueError("Le prix doit être strictement positif.")

    if db is not None:
        row = add_prix_marche(
            db=db,
            ingredient=ingr,
            prix_fcfa_kg=float(prix),
            source=source,
            region=region,
        )
        return serialize_prix_marche(row)

    entree = _enregistrer_historique(
        ingredient=ingr,
        prix_fcfa_kg=float(prix),
        source=source,
        region=region,
    )
    return entree


def get_historique_prix(ingredient: str, jours: int = 30) -> List[Dict[str, Any]]:
    """
    Retourne l'historique mémoire des prix d'un ingrédient.

    Paramètres :
    - ingredient : nom de l'ingrédient
    - jours : fenêtre de consultation, utilisée ici comme limite de récence
    """
    ingr = _normaliser_ingredient(ingredient)
    if not ingr:
        return []

    historique = HISTORIQUE_MEMOIRE.get(ingr, [])
    limite = max(1, min(int(jours or 30), 365))
    return historique[-limite:]


# ---------------------------------------------------------------------------
# Endpoints FastAPI
# ---------------------------------------------------------------------------
@router.get("/prix")
def lire_prix_actuels(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Retourne tous les prix actuels du marché.
    """
    try:
        prix = get_prix_actuels(db)
        return {
            "source": "base_de_donnees + valeurs_de_reference",
            "total": len(prix),
            "prix": prix,
        }
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération des prix du marché : {exc}",
        )


@router.get("/prix/{ingredient}")
def lire_prix_ingredient(ingredient: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Retourne le prix actuel d'un ingrédient.
    """
    try:
        ingr = _normaliser_ingredient(ingredient)
        if not ingr:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ingrédient invalide.",
            )

        latest = get_latest_prix_for_ingredient(db, ingr)
        if latest is not None:
            return {
                "ingredient": ingr,
                "prix_fcfa_kg": float(latest.prix_fcfa_kg or 0.0),
                "source": latest.source,
                "region": latest.region,
                "date_mise_a_jour": latest.date_mise_a_jour.isoformat()
                if latest.date_mise_a_jour
                else None,
                "origine": "base_de_donnees",
            }

        fallback = PRIX_REFERENCE.get(ingr)
        if fallback is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Aucun prix de référence trouvé pour cet ingrédient.",
            )

        return {
            "ingredient": ingr,
            "prix_fcfa_kg": float(fallback),
            "source": "prix_reference",
            "region": "Bénin",
            "date_mise_a_jour": None,
            "origine": "reference",
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération du prix de l'ingrédient : {exc}",
        )


# ---------------------------------------------------------------------------
# Export du module
# ---------------------------------------------------------------------------
__all__ = [
    "router",
    "PRIX_REFERENCE",
    "HISTORIQUE_MEMOIRE",
    "get_prix_actuels",
    "mettre_a_jour_prix",
    "get_historique_prix",
]
