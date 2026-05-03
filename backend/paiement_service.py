#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pyright: reportGeneralTypeIssues=false
"""
Paiement Mobile Money / FedaPay.

Le service expose :
- async def creer_transaction(...)
- async def verifier_paiement(...)
- Endpoints FastAPI de création, statut, webhook et historique

Si FedaPay est indisponible, une simulation locale est utilisée.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, cast

import requests
from database import get_db, get_user_by_id
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

router = APIRouter(prefix="/paiement", tags=["Paiement"])

FEDAPAY_BASE_URL = (
    os.getenv("FEDAPAY_BASE_URL") or "https://api.fedapay.com/v1"
).strip()
FEDAPAY_SECRET_KEY = (
    os.getenv("FEDAPAY_SECRET_KEY") or os.getenv("FEDAPAY_API_KEY") or ""
).strip()
FEDAPAY_WEBHOOK_SECRET = (os.getenv("FEDAPAY_WEBHOOK_SECRET") or "").strip()
PAIEMENT_CALLBACK_URL = (os.getenv("PAIEMENT_CALLBACK_URL") or "").strip()

ABONNEMENTS: Dict[str, Dict[str, Any]] = {
    "free": {"label": "Free", "prix": 0, "duree_jours": 0},
    "standard": {"label": "Standard", "prix": 2000, "duree_jours": 30},
    "premium": {"label": "Premium", "prix": 8000, "duree_jours": 30},
    "vip": {"label": "VIP", "prix": 25000, "duree_jours": 90},
    "gold": {"label": "Gold", "prix": 75000, "duree_jours": 180},
}

PAYMENT_HISTORY: List[Dict[str, Any]] = []
TRANSACTIONS: Dict[str, Dict[str, Any]] = {}


class CreerPaiementRequest(BaseModel):
    user_id: str = Field(..., min_length=3)
    abonnement: str = Field(..., min_length=2)
    telephone: str = Field(..., min_length=6)
    prenom: str = Field(default="Client")

    @field_validator("user_id", "abonnement", "telephone", "prenom")
    @classmethod
    def _strip(cls, value: str) -> str:
        txt = (value or "").strip()
        if not txt:
            raise ValueError("Champ vide.")
        return txt


class WebhookRequest(BaseModel):
    payload: Dict[str, Any] = Field(default_factory=dict)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uuid() -> str:
    return uuid.uuid4().hex


def _norm_abonnement(value: str) -> str:
    txt = (value or "").strip().lower()
    aliases = {"essentiel": "standard", "basique": "standard", "or": "gold"}
    return aliases.get(txt, txt)


def _record_history(transaction: Dict[str, Any]) -> None:
    existing = next(
        (
            x
            for x in PAYMENT_HISTORY
            if x["transaction_id"] == transaction["transaction_id"]
        ),
        None,
    )
    if existing:
        existing.update(transaction)
    else:
        PAYMENT_HISTORY.append(transaction)
    PAYMENT_HISTORY.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    del PAYMENT_HISTORY[10:]


class PaiementService:
    async def creer_transaction(
        self, user_id: str, abonnement: str, telephone: str, prenom: str
    ) -> Dict[str, Any]:
        user_id = (user_id or "").strip()
        abonnement_code = _norm_abonnement(abonnement)
        telephone = (telephone or "").strip()
        prenom = (prenom or "Client").strip()
        if abonnement_code not in ABONNEMENTS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Abonnement invalide."
            )
        montant = ABONNEMENTS[abonnement_code]["prix"]
        transaction_id = _uuid()
        lien_paiement = f"{FEDAPAY_BASE_URL.rstrip('/')}/checkout/{transaction_id}"
        provider = "simulation"
        provider_payload: Dict[str, Any] = {}
        if FEDAPAY_SECRET_KEY:
            try:
                payload = {
                    "amount": montant,
                    "currency": "XOF",
                    "description": f"Abonnement FeedFormula AI - {abonnement_code}",
                    "reference": transaction_id,
                    "callback_url": PAIEMENT_CALLBACK_URL or None,
                    "metadata": {
                        "user_id": user_id,
                        "abonnement": abonnement_code,
                        "telephone": telephone,
                    },
                    "customer": {"firstname": prenom, "phone_number": telephone},
                }
                payload = {k: v for k, v in payload.items() if v is not None}
                response = requests.post(
                    f"{FEDAPAY_BASE_URL.rstrip('/')}/transactions",
                    headers={
                        "Authorization": f"Bearer {FEDAPAY_SECRET_KEY}",
                        "Accept": "application/json",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                    timeout=30,
                )
                response.raise_for_status()
                provider_payload = response.json() if response.content else {}
                lien_paiement = str(
                    provider_payload.get("payment_url")
                    or provider_payload.get("url")
                    or lien_paiement
                )
                provider = "fedapay"
            except Exception as exc:
                provider_payload = {"error": str(exc)}
                provider = "simulation"
        transaction = {
            "transaction_id": transaction_id,
            "user_id": user_id,
            "abonnement": abonnement_code,
            "telephone": telephone,
            "montant": montant,
            "lien_paiement": lien_paiement,
            "statut": "pending",
            "provider": provider,
            "provider_payload": provider_payload,
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
            "activated_at": None,
        }
        TRANSACTIONS[transaction_id] = transaction
        _record_history(transaction)
        return {
            "transaction_id": transaction_id,
            "lien_paiement": lien_paiement,
            "montant": montant,
        }

    async def verifier_paiement(self, transaction_id: str) -> Dict[str, Any]:
        tx = TRANSACTIONS.get((transaction_id or "").strip())
        if not tx:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Transaction introuvable."
            )
        if tx["statut"] == "paid":
            return {"statut": "paid", "abonnement_active": tx["abonnement"]}
        if tx["provider"] == "fedapay" and FEDAPAY_SECRET_KEY:
            try:
                response = requests.get(
                    f"{FEDAPAY_BASE_URL.rstrip('/')}/transactions/{transaction_id}",
                    headers={
                        "Authorization": f"Bearer {FEDAPAY_SECRET_KEY}",
                        "Accept": "application/json",
                    },
                    timeout=20,
                )
                response.raise_for_status()
                remote = response.json() if response.content else {}
                status_remote = str(
                    remote.get("status") or remote.get("payment_status") or ""
                ).lower()
                if status_remote in {
                    "paid",
                    "approved",
                    "success",
                    "successful",
                    "completed",
                }:
                    tx["statut"] = "paid"
                    tx["activated_at"] = tx["activated_at"] or _now_iso()
                    tx["updated_at"] = _now_iso()
                    _record_history(tx)
            except Exception:
                pass
        return {
            "statut": tx["statut"],
            "abonnement_active": tx["abonnement"] if tx["statut"] == "paid" else None,
        }

    def _verify_signature(self, raw_body: bytes, signature: Optional[str]) -> bool:
        if not FEDAPAY_WEBHOOK_SECRET:
            return True
        if not signature:
            return False
        expected = hmac.new(
            FEDAPAY_WEBHOOK_SECRET.encode("utf-8"), raw_body, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature.strip())

    def _activate_user(self, db: Session, user_id: str, abonnement: str) -> None:
        user = get_user_by_id(db, user_id)
        if user:
            cast(Any, user).abonnement = abonnement
            db.commit()
            db.refresh(user)


SERVICE = PaiementService()


@router.post("/creer")
async def creer(payload: CreerPaiementRequest) -> Dict[str, Any]:
    user = None
    try:
        db_gen = get_db()
        db = next(db_gen)
        user = get_user_by_id(db, payload.user_id)
    finally:
        try:
            db.close()  # type: ignore[name-defined]
        except Exception:
            pass
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Utilisateur introuvable."
        )
    result = await SERVICE.creer_transaction(
        payload.user_id, payload.abonnement, payload.telephone, payload.prenom
    )
    transaction = TRANSACTIONS[result["transaction_id"]]
    transaction["user"] = {"id": user.id, "prenom": getattr(user, "prenom", "")}
    return {
        **result,
        "abonnement": {
            "code": _norm_abonnement(payload.abonnement),
            "label": ABONNEMENTS[_norm_abonnement(payload.abonnement)]["label"],
            "prix": result["montant"],
        },
    }


@router.post("/webhook")
async def webhook(request: Request, db: Session = Depends(get_db)) -> Dict[str, Any]:
    raw = await request.body()
    signature = (
        request.headers.get("X-FedaPay-Signature")
        or request.headers.get("X-Fedapay-Signature")
        or request.headers.get("X-Signature")
    )
    if not SERVICE._verify_signature(raw, signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Signature invalide."
        )
    try:
        payload = json.loads(raw.decode("utf-8") or "{}")
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    transaction_id = str(
        payload.get("reference")
        or payload.get("transaction_id")
        or payload.get("id")
        or ""
    ).strip()
    statut = str(
        payload.get("status")
        or payload.get("payment_status")
        or payload.get("state")
        or "pending"
    ).lower()
    if not transaction_id:
        return {"message": "Webhook reçu.", "statut": statut}
    tx = TRANSACTIONS.get(transaction_id)
    if not tx:
        tx = {
            "transaction_id": transaction_id,
            "user_id": str(
                payload.get("metadata", {}).get("user_id")
                or payload.get("user_id")
                or ""
            ),
            "abonnement": _norm_abonnement(
                str(
                    payload.get("metadata", {}).get("abonnement")
                    or payload.get("abonnement")
                    or "free"
                )
            ),
            "telephone": str(payload.get("metadata", {}).get("telephone") or ""),
            "montant": int(payload.get("amount") or 0),
            "lien_paiement": str(payload.get("payment_url") or ""),
            "statut": statut,
            "provider": "fedapay",
            "provider_payload": payload,
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
            "activated_at": None,
        }
    else:
        tx["statut"] = statut if statut else tx["statut"]
        tx["provider_payload"] = payload
        tx["updated_at"] = _now_iso()
    if tx["statut"] in {"paid", "approved", "success", "completed"}:
        tx["statut"] = "paid"
        tx["activated_at"] = tx["activated_at"] or _now_iso()
        SERVICE._activate_user(db, tx.get("user_id", ""), tx.get("abonnement", "free"))
    TRANSACTIONS[transaction_id] = tx
    _record_history(tx)
    return {"message": "Webhook traité.", "transaction": tx, "statut": tx["statut"]}


@router.get("/statut/{transaction_id}")
async def statut(transaction_id: str) -> Dict[str, Any]:
    result = await SERVICE.verifier_paiement(transaction_id)
    return result


@router.get("/historique/{user_id}")
def historique(user_id: str) -> Dict[str, Any]:
    items = [x for x in PAYMENT_HISTORY if x.get("user_id") == user_id]
    return {"user_id": user_id, "total": len(items), "transactions": items[:10]}


@router.get("/offres")
def offres() -> Dict[str, Any]:
    return {
        "total": len(ABONNEMENTS),
        "offres": [{"code": k, **v} for k, v in ABONNEMENTS.items()],
    }


__all__ = [
    "router",
    "ABONNEMENTS",
    "PAYMENT_HISTORY",
    "TRANSACTIONS",
    "PaiementService",
    "SERVICE",
]
