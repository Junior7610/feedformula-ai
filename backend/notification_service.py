#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Service de notifications Aya pour FeedFormula AI.

Objectifs :
- Générer des messages personnalisés selon le contexte utilisateur
- Prioriser les notifications importantes
- Limiter l'envoi à 1 notification par jour
- Exposer un routeur FastAPI simple pour récupérer la notification du jour

Ce module est volontairement écrit en français et de manière robuste.
"""

from __future__ import annotations

from datetime import datetime, time as dt_time
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

try:
    from .database import get_db, get_user_by_id, serialize_user
except Exception:
    from database import get_db, get_user_by_id, serialize_user  # type: ignore


# -----------------------------------------------------------------------------
# Router FastAPI
# -----------------------------------------------------------------------------
router = APIRouter(prefix="/notifications", tags=["Notifications"])


# -----------------------------------------------------------------------------
# État mémoire minimal
# -----------------------------------------------------------------------------
# On conserve la dernière date d'envoi par utilisateur pour éviter les doublons
# dans la même journée. En production, on pourrait persister cela en base.
_LAST_NOTIFICATION_BY_USER: Dict[str, str] = {}


# -----------------------------------------------------------------------------
# Utilitaires internes
# -----------------------------------------------------------------------------
def _heure_locale() -> datetime:
    """Retourne l'heure locale du serveur."""
    return datetime.now()


def _dans_plage_horaire() -> bool:
    """
    Vérifie si l'envoi est autorisé dans la plage 7h-22h.
    """
    now = _heure_locale().time()
    debut = dt_time(7, 0, 0)
    fin = dt_time(22, 0, 0)
    return debut <= now <= fin


def _aujourdhui_str() -> str:
    """Retourne la date du jour au format ISO."""
    return _heure_locale().date().isoformat()


def _base_message(prenom: str, contenu: str, langue: str = "fr") -> str:
    """
    Construit un message Aya selon la langue.
    """
    prenom_clean = (prenom or "éleveur").strip() or "éleveur"
    langue = (langue or "fr").strip().lower()

    if langue == "en":
        return f"Hello {prenom_clean}, {contenu}"
    if langue == "fon":
        return f"Bonjour {prenom_clean}, {contenu}"
    if langue == "yor":
        return f"Ẹ káàbọ̀ {prenom_clean}, {contenu}"
    return f"Bonjour {prenom_clean}, {contenu}"


def _priorite_notification(type_notif: str) -> int:
    """
    Attribue une priorité numérique.
    Plus la valeur est petite, plus la priorité est forte.
    """
    type_notif = (type_notif or "").strip().lower()

    if type_notif.startswith("serie_danger_30j"):
        return 1
    if type_notif.startswith("serie_danger_7j"):
        return 2
    if type_notif.startswith("serie_danger_3j"):
        return 3
    if type_notif.startswith("retour"):
        return 4
    if type_notif == "defi_disponible":
        return 5
    if type_notif in {"depasse_classement", "top5_ligue"}:
        return 6
    if type_notif in {"trophee_proche", "anniversaire"}:
        return 7
    if type_notif in {"prix_marche", "alerte_meteo"}:
        return 8
    return 9


# -----------------------------------------------------------------------------
# Service principal
# -----------------------------------------------------------------------------
class NotificationService:
    """
    Génère des notifications personnalisées Aya.
    """

    def generer_message_aya(
        self,
        prenom: str,
        type_notif: str,
        langue: str,
        contexte: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Génère un message personnalisé selon le type de notification.

        Types gérés :
        - serie_danger_3j
        - serie_danger_7j
        - serie_danger_30j
        - retour_2j
        - retour_5j
        - retour_7j
        - defi_disponible
        - depasse_classement
        - top5_ligue
        - trophee_proche
        - anniversaire
        - prix_marche
        - alerte_meteo
        """
        contexte = contexte or {}
        type_normalise = (type_notif or "").strip().lower()
        prenom_clean = (prenom or "éleveur").strip() or "éleveur"
        langue_clean = (langue or "fr").strip().lower()

        # Messages de base par langue/type.
        messages = {
            "serie_danger_3j": {
                "fr": "attention, votre série est fragile. Connectez-vous aujourd'hui pour ne pas la perdre.",
                "en": "your streak is fragile. Log in today to avoid losing it.",
                "fon": "série wá do hɛn. Kpó wa tɔn hɛn wá kpo wá sɔ.",
                "yor": "sẹ́sẹ̀ rẹ ń rẹ̀. Wọlé lónìí kí o má bà a sọnù.",
            },
            "serie_danger_7j": {
                "fr": "vous êtes à 7 jours d'alerte. Une action rapide peut sauver votre série.",
                "en": "you are 7 days from a streak warning. A quick action can save it.",
                "fon": "wáyì 7 ọjọ̀ kàn. Kó ma jẹ́ kí série náà bàjẹ́.",
                "yor": "o ku ọjọ meje sí ìkìlọ̀ series. Ṣe ìgbésẹ̀ kíákíá.",
            },
            "serie_danger_30j": {
                "fr": "votre série est en danger. Reprenez l'application pour garder vos gains.",
                "en": "your streak is in danger. Come back to keep your progress.",
                "fon": "série tɔn wá gbé. Wá padà kí o pa ere tɔn mọ́.",
                "yor": "sẹ́sẹ̀ rẹ wà nínú ewu. Padà wá láti pa èrè rẹ mọ́.",
            },
            "retour_2j": {
                "fr": "cela fait 2 jours sans activité. Un petit passage aujourd'hui vous fera gagner des points.",
                "en": "it's been 2 days since your last activity. A quick visit today earns you points.",
                "fon": "2 ọjọ́ ni wá o yí. Wá ṣe nkan kékèké lónìí kí o gbà points.",
                "yor": "ọjọ́ méjì ni kò sí ìṣe. Wọlé lónìí kí o gba àmì ẹ̀bùn.",
            },
            "retour_5j": {
                "fr": "vous nous avez manqué. Reprenez votre progression avec NutriCore ou VetScan.",
                "en": "we missed you. Resume progress with NutriCore or VetScan.",
                "fon": "wá yìí náà dé. Bẹ̀rẹ̀ sí i pọn ní NutriCore tàbí VetScan.",
                "yor": "a ń fẹ́ rí ẹ. Tẹ̀síwájú pẹ̀lú NutriCore tàbí VetScan.",
            },
            "retour_7j": {
                "fr": "7 jours sans connexion. Aya vous attend pour continuer votre évolution.",
                "en": "7 days offline. Aya is waiting for you to continue your journey.",
                "fon": "7 ọjọ́ láì wọlé. Aya ń dúró de wá.",
                "yor": "ọjọ́ meje láì wọlé. Aya ń retí rẹ.",
            },
            "defi_disponible": {
                "fr": "un nouveau défi du jour est disponible. Terminez-le pour gagner des 🌟.",
                "en": "a new daily challenge is available. Complete it to earn 🌟.",
                "fon": "défi tuntun wá. Ṣe e kí o gba 🌟.",
                "yor": "àwùjọ iṣẹ́ tuntun wà. Pari rẹ kí o gba 🌟.",
            },
            "depasse_classement": {
                "fr": "vous venez de dépasser un concurrent. Continuez pour sécuriser votre place.",
                "en": "you just overtook a competitor. Keep going to secure your rank.",
                "fon": "wá kọja ẹni kan. Máa bá a lọ kí o pa ipo mọ́.",
                "yor": "o ti ju oludije kan lọ. Tẹ̀síwájú kí o dì ipo rẹ mu.",
            },
            "top5_ligue": {
                "fr": "incroyable ! Vous êtes tout près du top 5. Une ration bien optimisée peut faire la différence.",
                "en": "amazing! You are close to the top 5. A well-optimized ration can make the difference.",
                "fon": "oho ! wá sún mọ́ top 5. Ration tɔn lè ran wá lọwọ.",
                "yor": "ìyanu ni! o fẹrẹ dé top 5. Ration tó dáa lè yàtọ̀.",
            },
            "trophee_proche": {
                "fr": "un trophée est presque à vous. Continuez encore un peu !",
                "en": "a trophy is within reach. Keep going!",
                "fon": "trophée kan sún mọ́ wá. Máa tẹ̀síwájú.",
                "yor": "trophée kan sunmọ́. Máa bá a lọ!",
            },
            "anniversaire": {
                "fr": "joyeux anniversaire ! Aya vous envoie toute son énergie positive.",
                "en": "happy birthday! Aya sends you positive energy.",
                "fon": "ọjọ́ ìbí ayọ̀ ! Aya ń rán wá agbára rere.",
                "yor": "ẹ ku ọjọ́ ìbí! Aya ń fi agbára rere ranṣẹ́.",
            },
            "prix_marche": {
                "fr": "les prix du marché ont changé. Vérifiez vos ingrédients avant de formuler.",
                "en": "market prices have changed. Check your ingredients before formulating.",
                "fon": "prix marché yí padà. Wo ingrédients tɔn kí o to formuler.",
                "yor": "owó ọjà ti yí padà. Ṣàyẹ̀wò àwọn eroja rẹ kí o tó ṣe àkópọ̀.",
            },
            "alerte_meteo": {
                "fr": "alerte météo : adaptez vos pratiques pour protéger vos animaux.",
                "en": "weather alert: adapt your practices to protect your animals.",
                "fon": "météo yí. Tún ìṣe tɔn ṣe kí o bójú tó animales.",
                "yor": "ìkìlọ̀ ojú-ọjọ́: yí ìṣe rẹ padà láti dáàbò bo àwọn ẹranko rẹ.",
            },
        }

        contenu = messages.get(type_normalise, {}).get(langue_clean)
        if not contenu:
            # Fallback sobre si la langue n'est pas encore traduite.
            contenu = {
                "fr": "une nouvelle notification est disponible dans votre espace FeedFormula AI.",
                "en": "a new notification is available in your FeedFormula AI space.",
            }.get(langue_clean, "une nouvelle notification est disponible dans votre espace FeedFormula AI.")

        # Ajout du contexte si disponible.
        if isinstance(contexte, dict) and contexte:
            if contexte.get("jours"):
                contenu += f" ({contexte['jours']} jours)"
            if contexte.get("valeur"):
                contenu += f" - {contexte['valeur']}"
            if contexte.get("label"):
                contenu += f" - {contexte['label']}"

        return {
            "type": type_normalise,
            "priorite": _priorite_notification(type_normalise),
            "titre": "Aya",
            "message": _base_message(prenom_clean, contenu, langue_clean),
            "langue": langue_clean,
            "contexte": contexte,
        }

    def get_notification_du_jour(self, user: Any) -> Optional[Dict[str, Any]]:
        """
        Détermine la notification du jour à envoyer pour un utilisateur.

        Règle :
        - 1 seule notification par jour
        - Priorité : série danger > défi > classement > prix marché > information
        - Envoi uniquement entre 7h et 22h
        """
        if not user:
            return None

        if not _dans_plage_horaire():
            return None

        user_id = str(getattr(user, "id", "") or "").strip()
        if not user_id:
            return None

        today = _aujourdhui_str()
        if _LAST_NOTIFICATION_BY_USER.get(user_id) == today:
            return None

        prenom = getattr(user, "prenom", "éleveur")
        langue = getattr(user, "langue_preferee", "fr") or "fr"
        serie_actuelle = int(getattr(user, "serie_actuelle", 0) or 0)
        meilleure_serie = int(getattr(user, "meilleure_serie", 0) or 0)
        points_total = int(getattr(user, "points_total", 0) or 0)

        # Priorité 1 : série en danger
        if serie_actuelle <= 2:
            notif = self.generer_message_aya(
                prenom=prenom,
                type_notif="serie_danger_3j" if serie_actuelle <= 1 else "serie_danger_7j",
                langue=langue,
                contexte={"jours": serie_actuelle},
            )
            _LAST_NOTIFICATION_BY_USER[user_id] = today
            return notif

        # Priorité 2 : défi du jour
        if points_total < 1000:
            notif = self.generer_message_aya(
                prenom=prenom,
                type_notif="defi_disponible",
                langue=langue,
                contexte={"label": "Défi quotidien"},
            )
            _LAST_NOTIFICATION_BY_USER[user_id] = today
            return notif

        # Priorité 3 : classement / ligue
        if points_total >= 500 and (points_total - meilleure_serie) >= 100:
            notif = self.generer_message_aya(
                prenom=prenom,
                type_notif="top5_ligue",
                langue=langue,
                contexte={"valeur": f"{points_total} pts"},
            )
            _LAST_NOTIFICATION_BY_USER[user_id] = today
            return notif

        # Priorité 4 : prix marché
        if points_total % 5 == 0:
            notif = self.generer_message_aya(
                prenom=prenom,
                type_notif="prix_marche",
                langue=langue,
            )
            _LAST_NOTIFICATION_BY_USER[user_id] = today
            return notif

        # Notification générique positive
        notif = self.generer_message_aya(
            prenom=prenom,
            type_notif="trophee_proche",
            langue=langue,
        )
        _LAST_NOTIFICATION_BY_USER[user_id] = today
        return notif


# Instance unique du service.
notification_service = NotificationService()


# -----------------------------------------------------------------------------
# Route FastAPI
# -----------------------------------------------------------------------------
@router.get("/{user_id}")
def get_notification_du_jour(user_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Retourne la notification du jour si applicable.
    """
    user = get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable.")

    notif = notification_service.get_notification_du_jour(user)
    if notif is None:
        return {
            "available": False,
            "message": "Aucune notification à envoyer pour le moment.",
            "user": serialize_user(user),
        }

    return {
        "available": True,
        "notification": notif,
        "user": serialize_user(user),
    }


__all__ = [
    "router",
    "NotificationService",
    "notification_service",
]
