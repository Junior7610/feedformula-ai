#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Service de notifications Aya pour FeedFormula AI.

Objectifs:
- Charger et exposer 13 types de messages Aya dans 9 langues.
- Sauvegarder les traductions dans data/messages_aya.json.
- Fournir une notification du jour personnalisée.
- Rester compatible avec l'ancien endpoint /notifications/{user_id}.

Les messages sont conservés localement. Si une couche IA externe est disponible,
ce module reste compatible via la structure JSON persistée.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

from database import get_db, get_user_by_id, serialize_user
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

router = APIRouter(prefix="/notifications", tags=["Notifications"])

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
MESSAGES_PATH = DATA_DIR / "messages_aya.json"

LANGUES = ["fr", "fon", "yor", "den", "adj", "gen", "yom", "baa", "en"]

AYA_MESSAGES: Dict[str, Dict[str, str]] = {
    "serie_danger_3j": {
        "fr": "🔥 {prenom}, ta série de 3 jours est en danger ! Aya veille sur toi. 1 seule ration peut tout sauver.",
        "fon": "🔥 {prenom}, série 3 ọjọ́ tɔn wá nínú ewu ! Aya ń wo wá. Ration 1 pɛ̀ lè gba a.",
        "yor": "🔥 {prenom}, sẹ́sẹ̀ ọjọ́ 3 rẹ wà nínú ewu! Aya ń bójú tó ọ. Ration kan ṣoṣo lè gba a.",
        "den": "🔥 {prenom}, ta série 3 ganda tondi wuru ! Aya ma hɛn ka. Ration tan bon wa kpi.",
        "adj": "🔥 {prenom}, série 3 jol tɔn wɛ́ ! Aya ya do. Une ration sèl sɛn wa sɔ.",
        "gen": "🔥 {prenom}, séri 3 ji tɛ nɔ kpɔ ! Aya le he yɔ. Ration kplé ɖe a se hla.",
        "yom": "🔥 {prenom}, série 3 la wà kpo ewu! Aya yé wà nípa rẹ. Ration kan lè dá a bọ.",
        "baa": "🔥 {prenom}, serie 3 da kɛ̀ɛn wà zaɣa! Aya nɔ́ɔ nɛ. Ration pɛ̀ lɔ̀ lɛ tɔ.",
        "en": "🔥 {prenom}, your 3-day streak is in danger! Aya is worried. Just one ration can save it.",
    },
    "serie_danger_7j": {
        "fr": "🔥 {prenom}, ta série de {jours} jours est en danger ! Aya est catastrophée. 1 seule ration suffit.",
        "fon": "🔥 {prenom}, série {jours} ọjọ́ tɔn wá nínú ewu ! Aya yíì dà. Ration 1 pɛ̀ tó.",
        "yor": "🔥 {prenom}, sẹ́sẹ̀ ọjọ́ {jours} rẹ wà nínú ewu! Aya ti bínú gan-an. Ration kan tó.",
        "den": "🔥 {prenom}, ta série {jours} ganda tondi wuru ! Aya bo nɔ. Ration tan dabari.",
        "adj": "🔥 {prenom}, série {jours} jol tɔn wɛ́ ! Aya wɛ nɔ. Une ration sèl sɛn wa.",
        "gen": "🔥 {prenom}, séri {jours} ji tɛ nɔ kpɔ ! Aya do ga. Ration kplé ɖe a se hla.",
        "yom": "🔥 {prenom}, série {jours} la wà nɔ ewu! Aya jẹ́ kó yà. Ration kan tó.",
        "baa": "🔥 {prenom}, serie {jours} da kɛ̀ɛn wà zaɣa! Aya nɔ́ɔ kɛ. Ration pɛ̀ lɔ̀ lɛ.",
        "en": "🔥 {prenom}, your {jours}-day streak is in danger! Aya is devastated. Just one ration is enough.",
    },
    "serie_danger_30j": {
        "fr": "🔥 {prenom}, ta série de 30 jours vacille. Aya croit en toi pour la sauver.",
        "fon": "🔥 {prenom}, série 30 ọjọ́ tɔn nɔ́ nù. Aya gbà gbé àn.",
        "yor": "🔥 {prenom}, sẹ́sẹ̀ ọjọ́ 30 rẹ ń mi. Aya gbàgbọ́ nínú rẹ.",
        "den": "🔥 {prenom}, ta série 30 ganda tondi goro. Aya hɛn ka ti a boro.",
        "adj": "🔥 {prenom}, série 30 jol tɔn tɛ́. Aya yɔn mɛ̀ dé.",
        "gen": "🔥 {prenom}, séri 30 ji tɛ nɔ hɛ. Aya le he dɔ.",
        "yom": "🔥 {prenom}, série 30 la wà ń yí. Aya ní ìgbàgbọ́ nínú rẹ.",
        "baa": "🔥 {prenom}, serie 30 da kɛ̀ɛn yɔrɔ. Aya nɔ́ɔ ni ma.",
        "en": "🔥 {prenom}, your 30-day streak is wobbling. Aya believes you can save it.",
    },
    "retour_2j": {
        "fr": "💛 {prenom}, cela fait 2 jours sans nouvelle. Reviens juste un instant et Aya te couvre de points.",
        "fon": "💛 {prenom}, 2 ọjọ́ ni wá o dé. Wá padà díẹ̀, Aya máa fun wá points.",
        "yor": "💛 {prenom}, ọjọ́ méjì ni kò sí ìròyìn rẹ. Padà wá díẹ̀, Aya yóò fi ọlá bo ọ.",
        "den": "💛 {prenom}, 2 ganda tondi bo. Baa do do, Aya ma fɔ points.",
        "adj": "💛 {prenom}, 2 jol tɔn ma wɛ. Wá tɔn bɛ̀, Aya nɔ̀ points.",
        "gen": "💛 {prenom}, 2 ji tɛ nɔ he. Wá ɖe, Aya na kɔ points.",
        "yom": "💛 {prenom}, ọjọ́ méjì ni o fi wá. Wọlé fún ìṣẹ́jú díẹ̀, Aya yóò fi points fún ọ.",
        "baa": "💛 {prenom}, ganda 2 nɔ tɛ. Baa sɔ́, Aya nɛ points.",
        "en": "💛 {prenom}, it has been 2 days. Come back for a moment and Aya will reward you with points.",
    },
    "retour_5j": {
        "fr": "🌟 {prenom}, Aya t’a manqué. Reprends ta progression avec FeedFormula AI dès aujourd’hui.",
        "fon": "🌟 {prenom}, Aya bì wá. Bẹ̀rẹ̀ padà sí FeedFormula AI lónìí.",
        "yor": "🌟 {prenom}, Aya ti fẹ́ rí ọ. Tẹ̀síwájú pẹ̀lú FeedFormula AI lónìí.",
        "den": "🌟 {prenom}, Aya yé ka bo. Baa wɛ FeedFormula AI ka hɛn.",
        "adj": "🌟 {prenom}, Aya ma wɛ. Tɔn gbé FeedFormula AI sɔ lónìí.",
        "gen": "🌟 {prenom}, Aya le he wɛ. Kpɔn FeedFormula AI hi lónìí.",
        "yom": "🌟 {prenom}, Aya ń fẹ́ rí ọ. Padà wá sí FeedFormula AI lónìí.",
        "baa": "🌟 {prenom}, Aya nɔ́ɔ nɛ. Baa sɔ FeedFormula AI sɔ.",
        "en": "🌟 {prenom}, Aya misses you. Resume your progress with FeedFormula AI today.",
    },
    "retour_7j": {
        "fr": "🌈 {prenom}, 7 jours sans connexion, mais Aya garde ta place au chaud.",
        "fon": "🌈 {prenom}, 7 ọjọ́ láì wọlé, Aya dúró de wá.",
        "yor": "🌈 {prenom}, ọjọ́ meje láì wọlé, ṣugbọn Aya ti pa àyè rẹ mọ́.",
        "den": "🌈 {prenom}, 7 ganda tondi bo, Aya ma hɛn ka.",
        "adj": "🌈 {prenom}, 7 jol tɔn ma wɛ, Aya nɔ̀ wɔ.",
        "gen": "🌈 {prenom}, 7 ji tɛ nɔ he, Aya le he wá.",
        "yom": "🌈 {prenom}, ọjọ́ meje ni kò sí ìbáṣepọ̀, Aya ṣi ń dúró de ọ.",
        "baa": "🌈 {prenom}, ganda 7 nɔ tɛ, Aya nɔ́ɔ kɛ.",
        "en": "🌈 {prenom}, 7 days offline, but Aya is keeping your spot warm.",
    },
    "defi_disponible": {
        "fr": "🎯 {prenom}, un nouveau défi du jour t’attend. Relève-le et récupère tes étoiles.",
        "fon": "🎯 {prenom}, défi tuntun wà. Ṣe e kí o gba étoiles.",
        "yor": "🎯 {prenom}, ìpèníjà tuntun wà. Ṣe e kí o gba àwọn ìràwọ̀ rẹ.",
        "den": "🎯 {prenom}, défi tan bo. Baa kɛ e ka gɔ stars.",
        "adj": "🎯 {prenom}, défi tuntun wɛ. Baa sɔ e, gba étoiles.",
        "gen": "🎯 {prenom}, défi kplé wà. Kɛ e ɖe, gba étoiles.",
        "yom": "🎯 {prenom}, ìpẹ̀yà tuntun wà. Pari rẹ kí o gba àwọn ìràwọ̀.",
        "baa": "🎯 {prenom}, défi nɔ tɛ. Baa kɛ e, gba stars.",
        "en": "🎯 {prenom}, a new daily challenge is waiting. Complete it and collect your stars.",
    },
    "depasse_classement": {
        "fr": "🏁 {prenom}, tu viens de dépasser un concurrent. La course continue et Aya te félicite.",
        "fon": "🏁 {prenom}, wá kọja ẹni kan. Aya yìí yìn wá.",
        "yor": "🏁 {prenom}, o ti ju oludije kan lọ. Aya yìn ọ.",
        "den": "🏁 {prenom}, bo joro jara kan. Aya fɔ ka.",
        "adj": "🏁 {prenom}, wá kọja kango. Aya kɛ̀rè wá.",
        "gen": "🏁 {prenom}, wá kpó kpɛ̀ kan. Aya dɔ wá.",
        "yom": "🏁 {prenom}, o ti kọja oludije kan. Aya ń yọ̀ fún ọ.",
        "baa": "🏁 {prenom}, a ka gɔ na. Aya nɔ́ɔ fɔ ka.",
        "en": "🏁 {prenom}, you just overtook a rival. The race continues and Aya is proud of you.",
    },
    "top5_ligue": {
        "fr": "🏆 {prenom}, tu es tout près du top 5. Une bonne ration peut faire la différence.",
        "fon": "🏆 {prenom}, wá sún mọ́ top 5. Ration dídára lè yàtọ̀.",
        "yor": "🏆 {prenom}, o sún mọ́ top 5. Ration tó dáa lè ṣe ìyàtọ̀.",
        "den": "🏆 {prenom}, bo yé top 5. Ration tɔn sɛn na.",
        "adj": "🏆 {prenom}, wá sún mọ́ top 5. Ration dɔɔ wɛ.",
        "gen": "🏆 {prenom}, wá sún top 5. Ration dɔŋ le he.",
        "yom": "🏆 {prenom}, o fẹrẹ dé top 5. Ration to dáa lè ṣe pàtàkì.",
        "baa": "🏆 {prenom}, wá sɔ top 5. Ration nɔ̀ bɛ lɛ.",
        "en": "🏆 {prenom}, you are very close to the top 5. A good ration can make all the difference.",
    },
    "trophee_proche": {
        "fr": "🥇 {prenom}, un trophée est presque à toi. Encore un petit effort !",
        "fon": "🥇 {prenom}, trophée kan sún mọ́ wá. Ẹ̀sìn kékèké mọ́ !",
        "yor": "🥇 {prenom}, trophée kan sún mọ́ ọ. Ṣíṣe díẹ̀ síi ni kù !",
        "den": "🥇 {prenom}, trophée tan yé ka. Baa wɔ joro !",
        "adj": "🥇 {prenom}, trophée wɛ nɔ. Baa gɔ́n kété !",
        "gen": "🥇 {prenom}, trophée kplé yé. Kpɔn ɖé wá !",
        "yom": "🥇 {prenom}, trophée kan sunmọ́ ọ. Súnwọ̀n díẹ̀ síi !",
        "baa": "🥇 {prenom}, trophée nɔ́ɔ kɛ. Baa tɔ̀n kɛ !",
        "en": "🥇 {prenom}, a trophy is almost yours. Just a little more effort!",
    },
    "anniversaire": {
        "fr": "🎂 Joyeux anniversaire {prenom} ! Aya t’envoie sa plus belle énergie.",
        "fon": "🎂 Happy birthday {prenom} ! Aya ń fi agbára rere ranṣẹ́.",
        "yor": "🎂 Ẹ ku ọjọ́ ìbí {prenom} ! Aya ń rán ìfẹ́ àti agbára rere.",
        "den": "🎂 Joyeux anniversaire {prenom} ! Aya ma fɔ ka nonga.",
        "adj": "🎂 Joyeux anniversaire {prenom} ! Aya nɔ̀ agbára dɔɔ.",
        "gen": "🎂 Joyeux anniversaire {prenom} ! Aya le he kpe wá.",
        "yom": "🎂 Ku ọjọ́ ìbí {prenom} ! Aya ń rán agbára rere.",
        "baa": "🎂 Joyeux anniversaire {prenom} ! Aya nɔ́ɔ fɔ ka.",
        "en": "🎂 Happy birthday {prenom}! Aya is sending you her brightest energy.",
    },
    "prix_marche": {
        "fr": "📈 {prenom}, les prix du marché ont bougé. Vérifie tes ingrédients avant de formuler.",
        "fon": "📈 {prenom}, prix marché yí padà. Wo ingrédients tɔn kí o to ṣe.",
        "yor": "📈 {prenom}, owó ọjà ti yí padà. Ṣàyẹ̀wò àwọn eroja rẹ kí o tó dá àkópọ̀.",
        "den": "📈 {prenom}, prix marché bo change. Baa wo ingrédients tɔn ganda.",
        "adj": "📈 {prenom}, prix marché yí. Baa wo ingrédients tɔn kafin.",
        "gen": "📈 {prenom}, prix marché tɛ. Kpɔn ingrédients tɔn kɔ̃.",
        "yom": "📈 {prenom}, owó ọjà ti yí. Ṣàyẹ̀wò àwọn eroja rẹ kí o tó ṣe.",
        "baa": "📈 {prenom}, prix marché yɔrɔ. Baa wo ingrédients tɔn.",
        "en": "📈 {prenom}, market prices have moved. Check your ingredients before you formulate.",
    },
    "alerte_meteo": {
        "fr": "⛈️ {prenom}, alerte météo. Ajuste vite tes pratiques pour protéger ton troupeau.",
        "fon": "⛈️ {prenom}, météo yí. Yí ìṣe tɔn padà kí o bójú tó troupeau.",
        "yor": "⛈️ {prenom}, ojú-ọjọ́ ń yí. Yí ìṣe rẹ padà kí o dáàbò bo ẹranko rẹ.",
        "den": "⛈️ {prenom}, météo bo change. Baa yi pràtiques tɔn ka.",
        "adj": "⛈️ {prenom}, météo wɛ. Baa yí ìṣe tɔn kété.",
        "gen": "⛈️ {prenom}, météo tɛ. Kpɔn pràtiques tɔn.",
        "yom": "⛈️ {prenom}, ìkìlọ̀ ojú-ọjọ́. Yí ìṣe rẹ padà kí o dáàbò bo ẹranko.",
        "baa": "⛈️ {prenom}, météo nɔ tɛ. Baa yí pràtiques tɔn.",
        "en": "⛈️ {prenom}, weather alert. Quickly adapt your practices to protect your herd.",
    },
}

_LAST_NOTIFICATION_BY_USER: Dict[str, str] = {}
_MESSAGES_CACHE: Optional[Dict[str, Dict[str, str]]] = None


def _today_key() -> str:
    return datetime.now().date().isoformat()


def _load_messages() -> Dict[str, Dict[str, str]]:
    global _MESSAGES_CACHE
    if _MESSAGES_CACHE is not None:
        return _MESSAGES_CACHE

    if MESSAGES_PATH.exists():
        try:
            payload = json.loads(MESSAGES_PATH.read_text(encoding="utf-8"))
            if isinstance(payload, dict) and payload:
                _MESSAGES_CACHE = payload
                return payload
        except Exception:
            pass

    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        MESSAGES_PATH.write_text(
            json.dumps(AYA_MESSAGES, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception:
        # En production serverless (Vercel), le système de fichiers du
        # déploiement peut être en lecture seule. Les messages intégrés
        # restent suffisants pour servir l'API sans planter.
        pass
    _MESSAGES_CACHE = AYA_MESSAGES
    return AYA_MESSAGES


def _ensure_message_placeholders(
    message: str, prenom: str, contexte: Dict[str, Any]
) -> str:
    prenom_clean = (prenom or "éleveur").strip() or "éleveur"
    jours = int(contexte.get("jours", 0) or 0)
    valeur = str(contexte.get("valeur", "") or "")
    label = str(contexte.get("label", "") or "")
    rendered = message.format(
        prenom=prenom_clean, jours=jours, valeur=valeur, label=label
    )
    return " ".join(rendered.split()).strip()


def _message_for(
    type_notif: str, langue: str, prenom: str, contexte: Dict[str, Any]
) -> str:
    messages = _load_messages()
    type_messages = messages.get(type_notif, {})
    langue_norm = (langue or "fr").strip().lower() or "fr"
    if langue_norm not in LANGUES:
        langue_norm = "fr"
    base = (
        type_messages.get(langue_norm)
        or type_messages.get("fr")
        or next(iter(type_messages.values()), "")
    )
    return _ensure_message_placeholders(base, prenom, contexte)


def _priorite_notification(type_notif: str) -> int:
    ordre = [
        "serie_danger_3j",
        "serie_danger_7j",
        "serie_danger_30j",
        "retour_2j",
        "retour_5j",
        "retour_7j",
        "defi_disponible",
        "depasse_classement",
        "top5_ligue",
        "trophee_proche",
        "anniversaire",
        "prix_marche",
        "alerte_meteo",
    ]
    try:
        return ordre.index(type_notif) + 1
    except ValueError:
        return 99


def _jours_depuis(date_source: Optional[datetime]) -> int:
    if not date_source:
        return 0
    try:
        delta = datetime.now() - date_source
        return max(0, int(delta.total_seconds() // 86400))
    except Exception:
        return 0


def _selectionner_type(user: Any) -> tuple[str, Dict[str, Any]]:
    serie_actuelle = int(getattr(user, "serie_actuelle", 0) or 0)
    points_total = int(getattr(user, "points_total", 0) or 0)
    niveau_actuel = int(getattr(user, "niveau_actuel", 1) or 1)
    derniere_connexion = getattr(user, "derniere_connexion", None)
    jours_inactif = _jours_depuis(derniere_connexion)

    if serie_actuelle <= 1:
        return "serie_danger_3j", {"jours": 3}
    if serie_actuelle <= 7:
        return "serie_danger_7j", {"jours": 7}
    if serie_actuelle <= 30:
        return "serie_danger_30j", {}
    if jours_inactif >= 7:
        return "retour_7j", {}
    if jours_inactif >= 5:
        return "retour_5j", {}
    if jours_inactif >= 2:
        return "retour_2j", {}
    if points_total >= 500 and niveau_actuel >= 3:
        return "top5_ligue", {}
    if points_total % 2 == 0 and points_total > 0:
        return "trophee_proche", {}
    if points_total >= 100 and points_total % 5 == 0:
        return "prix_marche", {}
    return "defi_disponible", {"label": "Défi quotidien"}


class NotificationService:
    """Génère les messages Aya et la notification du jour."""

    def messages_aya(self) -> Dict[str, Dict[str, str]]:
        return _load_messages()

    def generer_message_aya(
        self,
        prenom: str,
        type_notif: str,
        langue: str,
        contexte: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        contexte = contexte or {}
        type_norm = (type_notif or "").strip().lower()
        langue_norm = (langue or "fr").strip().lower()
        message = _message_for(type_norm, langue_norm, prenom, contexte)
        return {
            "type": type_norm,
            "priorite": _priorite_notification(type_norm),
            "titre": "Aya",
            "message": message,
            "langue": langue_norm,
            "contexte": contexte,
        }

    def get_notification_du_jour(self, user: Any) -> Optional[Dict[str, Any]]:
        if not user:
            return None

        user_id = str(getattr(user, "id", "") or "").strip()
        if not user_id:
            return None

        today = _today_key()
        if _LAST_NOTIFICATION_BY_USER.get(user_id) == today:
            return None

        type_notif, contexte = _selectionner_type(user)
        notif = self.generer_message_aya(
            prenom=getattr(user, "prenom", "éleveur"),
            type_notif=type_notif,
            langue=getattr(user, "langue_preferee", "fr") or "fr",
            contexte=contexte,
        )
        _LAST_NOTIFICATION_BY_USER[user_id] = today
        return notif


notification_service = NotificationService()


@router.get("/messages-aya")
def get_messages_aya() -> Dict[str, Any]:
    messages = notification_service.messages_aya()
    return {
        "total_types": len(messages),
        "langues": LANGUES,
        "messages": messages,
    }


@router.get("/du-jour/{user_id}")
def get_notification_du_jour(
    user_id: str, db: Session = Depends(get_db)
) -> Dict[str, Any]:
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


@router.get("/{user_id}")
def get_notification_du_jour_compat(
    user_id: str, db: Session = Depends(get_db)
) -> Dict[str, Any]:
    return get_notification_du_jour(user_id, db)


__all__ = ["router", "NotificationService", "notification_service", "AYA_MESSAGES"]
