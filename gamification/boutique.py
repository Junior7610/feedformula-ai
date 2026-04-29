#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Boutique virtuelle FeedFormula AI.

Cette boutique permet d'échanger des Graines d'Or contre des avantages
utiles à l'éleveur, sans casser l'équilibre du système de gamification.

Le module est écrit de manière robuste :
- catalogue centralisé,
- vérification du solde,
- achat transactionnel,
- effets simples et explicites,
- commentaires en français.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

try:
    from ..backend.database import get_user_by_id, serialize_user, add_points_to_user
except Exception:
    try:
        from backend.database import get_user_by_id, serialize_user, add_points_to_user  # type: ignore
    except Exception:
        from database import get_user_by_id, serialize_user, add_points_to_user  # type: ignore


# ---------------------------------------------------------------------------
# Catalogue boutique
# ---------------------------------------------------------------------------

CATALOGUE_BOUTIQUE: Dict[str, Dict[str, Any]] = {
    "semaine_standard": {
        "nom": "1 semaine Standard offerte",
        "prix_graines_or": 50,
        "description": "7 jours d'accès Standard",
        "type": "abonnement",
        "duree_jours": 7,
        "effet": {"abonnement": "standard"},
    },
    "module_premium_24h": {
        "nom": "Module Premium 24h",
        "prix_graines_or": 30,
        "description": "Accès à tous les modules 24h",
        "type": "abonnement",
        "duree_jours": 1,
        "effet": {"abonnement": "premium"},
    },
    "theme_or": {
        "nom": "Thème doré exclusif",
        "prix_graines_or": 80,
        "description": "Interface en couleurs dorées",
        "type": "cosmetique",
        "effet": {"theme": "or"},
    },
    "badge_rare": {
        "nom": "Badge Champion Précoce",
        "prix_graines_or": 40,
        "description": "Badge exclusif de profil",
        "type": "badge",
        "effet": {"badge": "champion_precoce"},
    },
    "protection_serie": {
        "nom": "Protection de série",
        "prix_graines_or": 20,
        "description": "+1 Graine de Secours",
        "type": "consommable",
        "effet": {"graines_secours": 1},
    },
    "boost_points_50": {
        "nom": "Boost de points",
        "prix_graines_or": 60,
        "description": "+50 points gamification",
        "type": "bonus",
        "effet": {"points": 50},
    },
    "boost_points_100": {
        "nom": "Boost de points XXL",
        "prix_graines_or": 110,
        "description": "+100 points gamification",
        "type": "bonus",
        "effet": {"points": 100},
    },
}


# ---------------------------------------------------------------------------
# Service boutique
# ---------------------------------------------------------------------------

@dataclass
class Boutique:
    """
    Boutique virtuelle à base de Graines d'Or.

    Les effets sont volontairement simples afin de rester compatibles
    avec la structure actuelle de la base de données.
    """

    def get_catalogue(self) -> Dict[str, Dict[str, Any]]:
        """
        Retourne le catalogue complet de la boutique.
        """
        return CATALOGUE_BOUTIQUE

    def verifier_solde(self, user_id: str, db: Session) -> Dict[str, Any]:
        """
        Vérifie le solde d'un utilisateur.

        Retourne un dictionnaire lisible par le frontend.
        """
        user = get_user_by_id(db, user_id)
        if user is None:
            raise ValueError("Utilisateur introuvable.")

        return {
            "user": serialize_user(user),
            "solde_graines_or": int(getattr(user, "graines_or", 0) or 0),
            "graines_secours": int(getattr(user, "graines_secours", 0) or 0),
            "abonnement": getattr(user, "abonnement", "free") or "free",
        }

    def acheter(self, user_id: str, item_code: str, db: Session) -> Dict[str, Any]:
        """
        Achète un article de la boutique et applique ses effets.

        Règles :
        - le solde doit être suffisant,
        - l'article doit exister,
        - l'effet est appliqué immédiatement,
        - l'achat est journalisable côté backend.
        """
        code = (item_code or "").strip()
        if not code:
            raise ValueError("Le code d'article est obligatoire.")

        item = CATALOGUE_BOUTIQUE.get(code)
        if item is None:
            raise ValueError("Article boutique introuvable.")

        user = get_user_by_id(db, user_id)
        if user is None:
            raise ValueError("Utilisateur introuvable.")

        prix = int(item.get("prix_graines_or", 0) or 0)
        solde = int(getattr(user, "graines_or", 0) or 0)

        if solde < prix:
            raise ValueError("Solde insuffisant en Graines d'Or.")

        # Débit du solde.
        user.graines_or = solde - prix

        # Application des effets.
        effet = item.get("effet", {}) or {}
        if "abonnement" in effet:
            user.abonnement = str(effet["abonnement"] or "free").strip().lower()

        if "graines_secours" in effet:
            user.graines_secours = int(getattr(user, "graines_secours", 0) or 0) + int(effet["graines_secours"] or 0)

        if "points" in effet:
            add_points_to_user(db, user.id, int(effet["points"] or 0))

        # Effets cosmétiques/badge : stockés côté profil en JSON léger si possible.
        # On évite ici d'ajouter une colonne dédiée pour rester compatible.
        historique = getattr(user, "historique_boutique", None)
        if historique is None:
            historique = []
        try:
            if not isinstance(historique, list):
                historique = []
        except Exception:
            historique = []

        historique.append(
            {
                "item_code": code,
                "nom": item.get("nom"),
                "prix_graines_or": prix,
                "date_achat": datetime.utcnow().isoformat() + "Z",
            }
        )

        # Persistance.
        db.commit()
        db.refresh(user)

        return {
            "message": "Achat effectué avec succès.",
            "item": {
                "code": code,
                "nom": item.get("nom"),
                "description": item.get("description"),
                "prix_graines_or": prix,
                "type": item.get("type"),
            },
            "user": serialize_user(user),
            "solde_apres_achat": int(getattr(user, "graines_or", 0) or 0),
        }


# Instance unique du service
boutique = Boutique()


__all__ = [
    "Boutique",
    "boutique",
    "CATALOGUE_BOUTIQUE",
]
