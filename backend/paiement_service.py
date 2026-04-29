#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Service de paiement Mobile Money pour FeedFormula AI.

Objectifs :
- Créer une transaction de paiement liée à un abonnement
- Gérer les confirmations webhook FedaPay
- Consulter le statut d'une transaction
- Activer automatiquement l'abonnement après paiement confirmé

Notes :
- L'intégration FedaPay est pensée en mode "best effort" :
  si les identifiants API ne sont pas disponibles, le service fonctionne
  en mode simulation locale pour ne pas bloquer le développement.
- Toutes les réponses et erreurs sont formulées en français.
"""

from __future__ import annotations

import hmac
import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import requests
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

# -----------------------------------------------------------------------------
# Imports locaux compatibles package / exécution directe
# -----------------------------------------------------------------------------
try:
    from .database import get_db, get_user_by_id, serialize_user
except Exception:  # pragma: no cover - fallback exécution directe
    from database import get_db, get_user_by_id, serialize_user  # type: ignore

try:
    from .database import User
except Exception:  # pragma: no cover - fallback exécution directe
    from database import User  # type: ignore


# -----------------------------------------------------------------------------
# Configuration FedaPay / paiement
# -----------------------------------------------------------------------------
FEDAPAY_SECRET_KEY = (os.getenv("FEDAPAY_SECRET_KEY") or os.getenv("FEDAPAY_API_KEY") or "").strip()
FEDAPAY_PUBLIC_KEY = (os.getenv("FEDAPAY_PUBLIC_KEY") or "").strip()
FEDAPAY_BASE_URL = (os.getenv("FEDAPAY_BASE_URL") or "https://api.fedapay.com/v1").strip()
FEDAPAY_WEBHOOK_SECRET = (os.getenv("FEDAPAY_WEBHOOK_SECRET") or "").strip()
PAIEMENT_CALLBACK_URL = (os.getenv("PAIEMENT_CALLBACK_URL") or "").strip()
PAIEMENT_SUCCESS_URL = (os.getenv("PAIEMENT_SUCCESS_URL") or "").strip()

# -----------------------------------------------------------------------------
# Routeur FastAPI
# -----------------------------------------------------------------------------
router = APIRouter(prefix="/paiement", tags=["Paiement"])

# -----------------------------------------------------------------------------
# Catalogue des offres
# -----------------------------------------------------------------------------
ABONNEMENTS: Dict[str, Dict[str, Any]] = {
    "free": {
        "label": "Free",
        "prix_fcfa": 0,
        "duree_jours": 0,
        "description": "Accès de découverte gratuit.",
        "benefices": [
            "Génération limitée de rations",
            "Accès de base à VetScan",
            "Historique restreint",
        ],
    },
    "starter": {
        "label": "Starter",
        "prix_fcfa": 2500,
        "duree_jours": 30,
        "description": "Idéal pour démarrer avec les outils essentiels.",
        "benefices": [
            "Rations complètes",
            "Audio synthèse",
            "Support gamification",
        ],
    },
    "basic": {
        "label": "Basic",
        "prix_fcfa": 5000,
        "duree_jours": 30,
        "description": "Pour les éleveurs qui veulent aller plus loin.",
        "benefices": [
            "Accès enrichi aux modules",
            "Conseils avancés",
            "Suivi des performances",
        ],
    },
    "premium": {
        "label": "Premium",
        "prix_fcfa": 10000,
        "duree_jours": 30,
        "description": "Une formule avancée pour un suivi plus complet.",
        "benefices": [
            "Priorité sur les analyses",
            "FarmAcademy avancée",
            "Classement enrichi",
        ],
    },
    "gold": {
        "label": "Gold",
        "prix_fcfa": 20000,
        "duree_jours": 30,
        "description": "L'offre la plus complète pour les utilisateurs intensifs.",
        "benefices": [
            "Toutes les fonctionnalités",
            "Support prioritaire",
            "Avantages exclusifs",
        ],
    },
}


# -----------------------------------------------------------------------------
# Mémoire transactionnelle
# -----------------------------------------------------------------------------
PAYMENT_TRANSACTIONS: Dict[str, Dict[str, Any]] = {}


# -----------------------------------------------------------------------------
# Schémas Pydantic
# -----------------------------------------------------------------------------
class CreerPaiementRequest(BaseModel):
    """Requête pour créer une transaction de paiement."""

    user_id: str = Field(..., min_length=3)
    abonnement: str = Field(..., min_length=2)
    telephone: str = Field(..., min_length=6)

    @field_validator("user_id", "abonnement", "telephone")
    @classmethod
    def _strip(cls, value: str) -> str:
        txt = (value or "").strip()
        if not txt:
            raise ValueError("Champ obligatoire vide.")
        return txt


# -----------------------------------------------------------------------------
# Utilitaires internes
# -----------------------------------------------------------------------------
def _now_iso() -> str:
    """Horodatage ISO UTC."""
    return datetime.now(timezone.utc).isoformat()


def _uuid() -> str:
    """Génère un identifiant de transaction simple."""
    return uuid.uuid4().hex


def _normaliser_abonnement(abonnement: str) -> str:
    """Normalise le libellé d'abonnement."""
    txt = (abonnement or "").strip().lower()
    aliases = {
        "gratuit": "free",
        "essentiel": "starter",
        "starter": "starter",
        "basic": "basic",
        "basique": "basic",
        "premium": "premium",
        "gold": "gold",
        "or": "gold",
    }
    return aliases.get(txt, txt)


def _fetch_user(db: Session, user_id: str) -> User:
    """Récupère un utilisateur ou lève une erreur claire."""
    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur introuvable.",
        )
    return user


def _verify_webhook_signature(raw_body: bytes, signature: Optional[str]) -> bool:
    """
    Vérifie la signature du webhook si un secret est configuré.

    Comme les formats exacts peuvent varier selon le fournisseur / connecteur,
    la vérification reste permissive :
    - si aucun secret n'est configuré, la validation est acceptée
    - si un secret est configuré, on compare un HMAC SHA256 hexadécimal
    """
    if not FEDAPAY_WEBHOOK_SECRET:
        return True
    if not signature:
        return False

    expected = hmac.new(
        FEDAPAY_WEBHOOK_SECRET.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected, signature.strip())


def _build_transaction_payload(
    user: User,
    abonnement_code: str,
    telephone: str,
    transaction_id: str,
) -> Dict[str, Any]:
    """Construit la charge utile à envoyer à FedaPay."""
    offre = ABONNEMENTS[abonnement_code]
    description = f"Abonnement FeedFormula AI - {offre['label']}"
    payload: Dict[str, Any] = {
        "amount": int(offre["prix_fcfa"]),
        "currency": "XOF",
        "description": description,
        "reference": transaction_id,
        "callback_url": PAIEMENT_CALLBACK_URL or None,
        "metadata": {
            "user_id": user.id,
            "telephone": telephone,
            "abonnement": abonnement_code,
            "source": "FeedFormula AI",
        },
        "customer": {
            "firstname": getattr(user, "prenom", "Client"),
            "phone_number": telephone,
        },
    }
    # Suppression des clés None pour garder une charge utile propre.
    return {k: v for k, v in payload.items() if v is not None}


def _create_remote_fedapay_transaction(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Tente de créer une transaction côté FedaPay.

    Retourne un dictionnaire avec les champs utiles :
    - id
    - payment_url
    - raw
    """
    if not FEDAPAY_SECRET_KEY:
        raise RuntimeError("FedaPay non configuré.")

    endpoint = f"{FEDAPAY_BASE_URL.rstrip('/')}/transactions"
    headers = {
        "Authorization": f"Bearer {FEDAPAY_SECRET_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    response = requests.post(
        endpoint,
        headers=headers,
        json=payload,
        timeout=30,
    )
    response.raise_for_status()
    data = response.json() if response.content else {}

    transaction_id = ""
    payment_url = ""

    if isinstance(data, dict):
        transaction_id = str(
            data.get("id")
            or data.get("reference")
            or data.get("transaction_id")
            or payload.get("reference")
            or ""
        ).strip()

        payment_url = str(
            data.get("payment_url")
            or data.get("url")
            or data.get("checkout_url")
            or data.get("link")
            or ""
        ).strip()

    return {
        "id": transaction_id or str(payload.get("reference") or ""),
        "payment_url": payment_url,
        "raw": data,
    }


def _create_local_payment_link(transaction_id: str, abonnement_code: str) -> str:
    """
    Fallback local lorsque FedaPay n'est pas configuré.

    Le but est de fournir une URL stable exploitable par le frontend
    en environnement de développement.
    """
    return (
        f"{FEDAPAY_BASE_URL.rstrip('/')}/checkout/{transaction_id}"
        f"?abonnement={abonnement_code}"
    )


def _save_transaction(
    transaction_id: str,
    user_id: str,
    abonnement: str,
    telephone: str,
    lien_paiement: str,
    status_value: str = "pending",
    provider: str = "fedapay",
    raw_provider: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Enregistre ou met à jour une transaction en mémoire."""
    payload = {
        "transaction_id": transaction_id,
        "user_id": user_id,
        "abonnement": abonnement,
        "telephone": telephone,
        "lien_paiement": lien_paiement,
        "status": status_value,
        "provider": provider,
        "provider_payload": raw_provider or {},
        "created_at": PAYMENT_TRANSACTIONS.get(transaction_id, {}).get("created_at") or _now_iso(),
        "updated_at": _now_iso(),
        "activated_at": PAYMENT_TRANSACTIONS.get(transaction_id, {}).get("activated_at"),
    }
    PAYMENT_TRANSACTIONS[transaction_id] = payload
    return payload


def _activer_abonnement_user(db: Session, user: User, abonnement: str) -> User:
    """Active l'abonnement d'un utilisateur et le persiste."""
    abonnement_code = _normaliser_abonnement(abonnement)
    if abonnement_code not in ABONNEMENTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Abonnement invalide.",
        )

    user.abonnement = abonnement_code
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _extract_webhook_payload(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extrait les champs utiles d'un webhook FedaPay / passerelle similaire.

    Le service accepte plusieurs formes de charge utile pour rester robuste.
    """
    if not isinstance(raw, dict):
        return {}

    transaction = raw.get("transaction")
    data = raw.get("data")

    if isinstance(transaction, dict):
        merged = {**transaction, **raw}
        return merged
    if isinstance(data, dict):
        merged = {**data, **raw}
        return merged
    return raw


def _resolve_transaction_status(payload: Dict[str, Any]) -> str:
    """Déduit un statut simple à partir du payload webhook."""
    candidates = [
        payload.get("status"),
        payload.get("state"),
        payload.get("transaction_status"),
        payload.get("payment_status"),
    ]

    for candidate in candidates:
        value = str(candidate or "").strip().lower()
        if value in {"paid", "success", "successful", "approved", "completed", "captured", "validated", "paid_success"}:
            return "paid"
        if value in {"failed", "declined", "canceled", "cancelled", "rejected"}:
            return "failed"
        if value in {"pending", "waiting", "processing", "in_progress"}:
            return "pending"

    # Fallback sur des indicateurs booléens éventuels.
    for key in ("paid", "is_paid", "success", "approved"):
        if bool(payload.get(key)) is True:
            return "paid"

    return "pending"


def _serialize_transaction(transaction: Dict[str, Any]) -> Dict[str, Any]:
    """Prépare une transaction pour retour API."""
    return {
        "transaction_id": transaction.get("transaction_id"),
        "user_id": transaction.get("user_id"),
        "abonnement": transaction.get("abonnement"),
        "telephone": transaction.get("telephone"),
        "lien_paiement": transaction.get("lien_paiement"),
        "status": transaction.get("status"),
        "provider": transaction.get("provider"),
        "created_at": transaction.get("created_at"),
        "updated_at": transaction.get("updated_at"),
        "activated_at": transaction.get("activated_at"),
    }


# -----------------------------------------------------------------------------
# Endpoints FastAPI
# -----------------------------------------------------------------------------
@router.post("/creer")
def creer_paiement(
    payload: CreerPaiementRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Crée une transaction de paiement Mobile Money.

    Retour :
    - `lien_paiement` : URL de redirection vers l'interface de paiement
    - `transaction_id` : identifiant de suivi interne
    """
    user = _fetch_user(db, payload.user_id)
    abonnement_code = _normaliser_abonnement(payload.abonnement)

    if abonnement_code not in ABONNEMENTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Abonnement inconnu.",
        )

    transaction_id = _uuid()
    offre = ABONNEMENTS[abonnement_code]
    lien_paiement = ""

    # Tente l'intégration FedaPay d'abord.
    try:
        provider_payload = _build_transaction_payload(
            user=user,
            abonnement_code=abonnement_code,
            telephone=payload.telephone,
            transaction_id=transaction_id,
        )

        if FEDAPAY_SECRET_KEY:
            remote = _create_remote_fedapay_transaction(provider_payload)
            lien_paiement = remote.get("payment_url") or ""
            if not lien_paiement:
                lien_paiement = _create_local_payment_link(transaction_id, abonnement_code)
            _save_transaction(
                transaction_id=transaction_id,
                user_id=user.id,
                abonnement=abonnement_code,
                telephone=payload.telephone,
                lien_paiement=lien_paiement,
                status_value="pending",
                provider="fedapay",
                raw_provider=remote.get("raw") if isinstance(remote, dict) else {},
            )
        else:
            lien_paiement = _create_local_payment_link(transaction_id, abonnement_code)
            _save_transaction(
                transaction_id=transaction_id,
                user_id=user.id,
                abonnement=abonnement_code,
                telephone=payload.telephone,
                lien_paiement=lien_paiement,
                status_value="pending",
                provider="simulation",
                raw_provider={
                    "mode": "simulation_locale",
                    "message": "FedaPay non configuré ; lien généré localement.",
                },
            )

    except requests.RequestException as exc:
        lien_paiement = _create_local_payment_link(transaction_id, abonnement_code)
        _save_transaction(
            transaction_id=transaction_id,
            user_id=user.id,
            abonnement=abonnement_code,
            telephone=payload.telephone,
            lien_paiement=lien_paiement,
            status_value="pending",
            provider="fedapay",
            raw_provider={"erreur": str(exc)},
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Impossible de créer la transaction de paiement : {exc}",
        )

    return {
        "message": "Transaction de paiement créée avec succès.",
        "transaction_id": transaction_id,
        "lien_paiement": lien_paiement,
        "abonnement": {
            "code": abonnement_code,
            "label": offre["label"],
            "prix_fcfa": offre["prix_fcfa"],
            "duree_jours": offre["duree_jours"],
        },
    }


@router.post("/webhook")
async def paiement_webhook(request: Request, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Reçoit les notifications de confirmation de paiement.

    Le payload est traité de façon permissive pour supporter plusieurs formats
    de passerelle / connecteur.
    """
    raw_body = await request.body()
    signature = (
        request.headers.get("X-FedaPay-Signature")
        or request.headers.get("X-Fedapay-Signature")
        or request.headers.get("X-Signature")
    )

    if not _verify_webhook_signature(raw_body, signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Signature de webhook invalide.",
        )

    try:
        payload = json.loads(raw_body.decode("utf-8") or "{}")
    except Exception:
        payload = {}

    if not isinstance(payload, dict):
        payload = {}

    payload = _extract_webhook_payload(payload)

    transaction_id = str(
        payload.get("reference")
        or payload.get("transaction_id")
        or payload.get("id")
        or payload.get("metadata", {}).get("transaction_id")
        or ""
    ).strip()

    status_value = _resolve_transaction_status(payload)

    if not transaction_id:
        # On accepte le webhook même si le fournisseur n'envoie pas encore
        # l'identifiant attendu, mais on le signale clairement.
        return {
            "message": "Webhook reçu, mais transaction introuvable dans la charge utile.",
            "status": status_value,
        }

    transaction = PAYMENT_TRANSACTIONS.get(transaction_id)
    if transaction is None:
        # On conserve une trace minimale pour permettre le suivi.
        transaction = _save_transaction(
            transaction_id=transaction_id,
            user_id=str(
                payload.get("metadata", {}).get("user_id")
                or payload.get("user_id")
                or ""
            ),
            abonnement=_normaliser_abonnement(
                str(payload.get("metadata", {}).get("abonnement") or payload.get("abonnement") or "free")
            ),
            telephone=str(
                payload.get("metadata", {}).get("telephone")
                or payload.get("customer", {}).get("phone_number")
                or ""
            ),
            lien_paiement=str(payload.get("payment_url") or ""),
            status_value=status_value,
            provider="fedapay",
            raw_provider=payload,
        )
    else:
        transaction["status"] = status_value
        transaction["provider_payload"] = payload
        transaction["updated_at"] = _now_iso()

    user_id = str(transaction.get("user_id") or "").strip()
    abonnement_code = _normaliser_abonnement(str(transaction.get("abonnement") or ""))

    if status_value == "paid" and user_id and abonnement_code in ABONNEMENTS:
        user = get_user_by_id(db, user_id)
        if user is not None:
            _activer_abonnement_user(db, user, abonnement_code)
            transaction["activated_at"] = transaction.get("activated_at") or _now_iso()
            transaction["status"] = "paid"

    PAYMENT_TRANSACTIONS[transaction_id] = transaction

    return {
        "message": "Webhook traité avec succès.",
        "transaction": _serialize_transaction(transaction),
        "status": transaction["status"],
    }


@router.get("/statut/{transaction_id}")
def statut_paiement(transaction_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Retourne le statut d'une transaction de paiement.

    Si la transaction est connue localement, son état est renvoyé immédiatement.
    Sinon, le service tente une vérification distante si FedaPay est configuré.
    """
    tx_id = (transaction_id or "").strip()
    if not tx_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Identifiant de transaction invalide.",
        )

    transaction = PAYMENT_TRANSACTIONS.get(tx_id)

    # Vérification distante possible si la transaction n'existe pas localement.
    if transaction is None and FEDAPAY_SECRET_KEY:
        try:
            endpoint = f"{FEDAPAY_BASE_URL.rstrip('/')}/transactions/{tx_id}"
            headers = {
                "Authorization": f"Bearer {FEDAPAY_SECRET_KEY}",
                "Accept": "application/json",
            }
            response = requests.get(endpoint, headers=headers, timeout=20)
            response.raise_for_status()
            remote = response.json() if response.content else {}
            if isinstance(remote, dict):
                remote_status = _resolve_transaction_status(remote)
                transaction = _save_transaction(
                    transaction_id=tx_id,
                    user_id=str(remote.get("metadata", {}).get("user_id") or remote.get("user_id") or ""),
                    abonnement=_normaliser_abonnement(
                        str(remote.get("metadata", {}).get("abonnement") or remote.get("abonnement") or "free")
                    ),
                    telephone=str(
                        remote.get("metadata", {}).get("telephone")
                        or remote.get("customer", {}).get("phone_number")
                        or ""
                    ),
                    lien_paiement=str(
                        remote.get("payment_url")
                        or remote.get("url")
                        or remote.get("checkout_url")
                        or ""
                    ),
                    status_value=remote_status,
                    provider="fedapay",
                    raw_provider=remote,
                )
                if remote_status == "paid":
                    user_id = str(transaction.get("user_id") or "").strip()
                    abonnement_code = _normaliser_abonnement(str(transaction.get("abonnement") or ""))
                    user = get_user_by_id(db, user_id) if user_id else None
                    if user is not None and abonnement_code in ABONNEMENTS:
                        _activer_abonnement_user(db, user, abonnement_code)
                        transaction["activated_at"] = transaction.get("activated_at") or _now_iso()
                        transaction["status"] = "paid"
        except Exception:
            transaction = None

    if transaction is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction introuvable.",
        )

    user = get_user_by_id(db, str(transaction.get("user_id") or "").strip())
    user_payload = serialize_user(user) if user is not None else None

    return {
        "transaction": _serialize_transaction(transaction),
        "user": user_payload,
        "est_paye": transaction.get("status") == "paid",
        "abonnement": ABONNEMENTS.get(_normaliser_abonnement(str(transaction.get("abonnement") or ""))),
    }


@router.get("/offres")
def lister_offres() -> Dict[str, Any]:
    """
    Retourne le catalogue des offres d'abonnement.
    Utile pour alimenter le frontend.
    """
    return {
        "total": len(ABONNEMENTS),
        "offres": [
            {
                "code": code,
                "label": data["label"],
                "prix_fcfa": data["prix_fcfa"],
                "duree_jours": data["duree_jours"],
                "description": data["description"],
                "benefices": data["benefices"],
            }
            for code, data in ABONNEMENTS.items()
        ],
    }


__all__ = [
    "router",
    "ABONNEMENTS",
    "PAYMENT_TRANSACTIONS",
    "CreerPaiementRequest",
    "creer_paiement",
    "paiement_webhook",
    "statut_paiement",
    "lister_offres",
]
