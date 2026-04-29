#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Moteur Aya de FeedFormula AI.

Ce module charge les états d'Aya depuis `aya_states.json` et fournit :
- l'état actuel en fonction du contexte utilisateur,
- le message multilingue,
- l'image associée,
- l'animation associée.

Les commentaires sont en français pour faciliter la maintenance.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

ROOT_DIR = Path(__file__).resolve().parent.parent
AYA_STATES_PATH = ROOT_DIR / "gamification" / "aya_states.json"


# -----------------------------------------------------------------------------
# Chargement des états
# -----------------------------------------------------------------------------
def _charger_etats() -> Dict[str, Any]:
    """Charge les états d'Aya depuis le JSON, avec fallback local."""
    try:
        with open(AYA_STATES_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and isinstance(data.get("states"), list):
            return data
    except Exception:
        pass

    # Fallback minimal si le JSON n'est pas disponible.
    return {
        "default_language": "fr",
        "fallbacks": {
            "unknown_state": "neutre_accueil",
            "default_animation": "aya_idle_breathing",
            "default_sound": "aya_soft_chime",
            "max_display_seconds": 12,
            "min_display_seconds": 2,
        },
        "states": [
            {
                "id": "neutre_accueil",
                "etat": "neutre",
                "declencheur": "connexion_utilisateur",
                "messages": {
                    "fr": "Bonjour 👋 Je suis Aya. On avance étape par étape aujourd’hui.",
                    "fon": "Azɔ̀n! Un wɛ Aya. Mí na jì nù gbèdo-gbèdo egbe.",
                    "yor": "Báwo! Èmi ni Aya. A máa lọ ní ìgbésẹ̀ díẹ̀ díẹ̀ lónìí.",
                    "en": "Hello 👋 I’m Aya. We’ll move step by step today.",
                },
                "duree_affichage_sec": 5,
                "animation_associee": "aya_wave_soft",
                "son_associe": "aya_soft_chime",
            }
        ],
    }


AYA_DATA = _charger_etats()
AYA_STATES = {
    state.get("id"): state for state in AYA_DATA.get("states", []) if isinstance(state, dict)
}
FALLBACKS = AYA_DATA.get("fallbacks", {}) or {}


# -----------------------------------------------------------------------------
# Utilitaires
# -----------------------------------------------------------------------------
def _normaliser_heure(value: Any) -> Optional[datetime]:
    """Convertit une valeur en datetime si possible."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except Exception:
            return None
    return None


def _heure_actuelle(context: Optional[Dict[str, Any]] = None) -> datetime:
    """Retourne l'heure actuelle, éventuellement surchargée par le contexte."""
    context = context or {}
    for key in ("now", "date_heure", "datetime"):
        parsed = _normaliser_heure(context.get(key))
        if parsed is not None:
            return parsed
    return datetime.now()


def _get_message_etat(state: Dict[str, Any], langue: str, prenom: str) -> str:
    """Construit un message adapté à la langue et au prénom."""
    messages = state.get("messages", {}) or {}
    langue = (langue or "fr").strip().lower()
    template = messages.get(langue) or messages.get("fr") or "Bonjour {prenom} 👋"
    prenom = (prenom or "éleveur").strip() or "éleveur"
    try:
        return template.replace("{prenom}", prenom)
    except Exception:
        return str(template)


# -----------------------------------------------------------------------------
# État d'Aya
# -----------------------------------------------------------------------------
@dataclass
class AyaEngine:
    """Moteur d'interprétation des états d'Aya."""

    def get_etat_actuel(self, contexte_utilisateur: Optional[Dict[str, Any]] = None) -> str:
        """
        Détermine l'état d'Aya à afficher en fonction du contexte utilisateur.

        Le contexte peut contenir :
        - prenom
        - langue_preferee
        - derniere_connexion
        - serie_actuelle
        - niveau_actuel
        - trophee_recent
        - ration_reussie
        - defi_disponible
        - classement_change
        - farmacademy_actif
        - vetscan_reussi
        - heure_actuelle
        """
        contexte = contexte_utilisateur or {}
        heure = _heure_actuelle(contexte)
        heure_nuit = heure.hour >= 22 or heure.hour < 7

        serie = int(contexte.get("serie_actuelle", 0) or 0)
        jours_depuis = int(contexte.get("jours_depuis_derniere_connexion", 0) or 0)
        niveau = int(contexte.get("niveau_actuel", 1) or 1)
        trophee = bool(contexte.get("trophee_recent"))
        ration = bool(contexte.get("ration_reussie"))
        defi = bool(contexte.get("defi_disponible"))
        classement = contexte.get("classement_change")
        farmacademy = bool(contexte.get("farmacademy_actif"))
        vetscan = bool(contexte.get("vetscan_reussi"))

        if heure_nuit:
            return "repos_nuit"
        if serie >= 30:
            return "celebration_serie"
        if ration:
            return "succes_ration"
        if vetscan:
            return "diagnostic_reussi"
        if farmacademy:
            return "apprentissage"
        if trophee:
            return "fierte_trophee"
        if classement == "alerte":
            return "alerte_classement"
        if classement == "victoire":
            return "victoire_classement"
        if defi:
            return "encouragement_defi"
        if serie >= 7 and jours_depuis <= 1:
            return "celebration_serie"
        if serie >= 7 and jours_depuis >= 2:
            return "urgence_serie_longue"
        if serie >= 1 and jours_depuis == 1:
            return "inquietude_serie"
        if jours_depuis == 2:
            return "tristesse_2j"
        if jours_depuis == 1:
            return "tristesse_1j"
        if niveau > 1:
            return "joie_connexion"
        return FALLBACKS.get("unknown_state", "neutre_accueil")

    def get_message(self, etat: str, langue: str, prenom: str) -> str:
        """Retourne le message d'Aya pour un état donné."""
        state = AYA_STATES.get(etat) or AYA_STATES.get(
            FALLBACKS.get("unknown_state", "neutre_accueil"), {}
        )
        if not state:
            return f"Bonjour {prenom or 'éleveur'} 👋"
        return _get_message_etat(state, langue, prenom)

    def get_image(self, etat: str) -> str:
        """Retourne le nom du fichier image correspondant à l'état."""
        state = AYA_STATES.get(etat) or AYA_STATES.get(
            FALLBACKS.get("unknown_state", "neutre_accueil"), {}
        )
        if not state:
            return "aya_joie.png"
        return str(
            state.get("image")
            or state.get("image_associee")
            or "aya_joie.png"
        )

    def get_animation(self, etat: str) -> str:
        """Retourne l'animation correspondant à l'état."""
        state = AYA_STATES.get(etat) or AYA_STATES.get(
            FALLBACKS.get("unknown_state", "neutre_accueil"), {}
        )
        if not state:
            return str(FALLBACKS.get("default_animation", "aya_idle_breathing"))
        return str(
            state.get("animation")
            or state.get("animation_associee")
            or FALLBACKS.get("default_animation", "aya_idle_breathing")
        )

    def get_son(self, etat: str) -> str:
        """Retourne le son correspondant à l'état."""
        state = AYA_STATES.get(etat) or AYA_STATES.get(
            FALLBACKS.get("unknown_state", "neutre_accueil"), {}
        )
        if not state:
            return str(FALLBACKS.get("default_sound", "aya_soft_chime"))
        return str(
            state.get("son")
            or state.get("son_associe")
            or FALLBACKS.get("default_sound", "aya_soft_chime")
        )

    def get_duree_affichage(self, etat: str) -> int:
        """Retourne la durée d'affichage de l'état."""
        state = AYA_STATES.get(etat) or AYA_STATES.get(
            FALLBACKS.get("unknown_state", "neutre_accueil"), {}
        )
        if not state:
            return int(FALLBACKS.get("max_display_seconds", 12))
        duree = int(
            state.get("duree_affichage_sec")
            or state.get("duree_affichage")
            or FALLBACKS.get("max_display_seconds", 12)
        )
        return max(
            int(FALLBACKS.get("min_display_seconds", 2)),
            min(duree, int(FALLBACKS.get("max_display_seconds", 12))),
        )


# Instance prête à l'emploi
aya_engine = AyaEngine()


__all__ = [
    "AyaEngine",
    "aya_engine",
    "AYA_DATA",
    "AYA_STATES",
]
