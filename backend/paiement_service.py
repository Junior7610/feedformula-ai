#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pyright: reportGeneralTypeIssues=false, reportArgumentType=false, reportAssignmentType=false, reportReturnType=false, reportAttributeAccessIssue=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownVariableType=false
"""Paiement Mobile Money / FedaPay de FeedFormula AI."""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

import requests
from database import (
    add_points_to_user,
    create_transaction_paiement,
    get_db,
    get_transaction_paiement_by_id,
    get_user_by_id,
    list_user_transactions,
)
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

router = APIRouter(prefix="/paiement", tags=["Paiement"])

FEDAPAY_BASE_URL = (
    os.getenv("FEDAPAY_BASE_URL") or "https://api.fedapay.com/v1"
).strip()
FEDAPAY_SECRET_KEY = (
    os.getenv("FEDAPAY_SECRET_KEY") or os.getenv("FEDAPAY_API_KEY") or ""
).strip()
APP_URL = (os.getenv("APP_URL") or "http://127.0.0.1:8000").strip()

OFFRES = {"free": 0, "standard": 2000, "premium": 8000, "vip": 25000, "gold": 75000}
DUREES = {"mensuel": (30, 1.0), "trimestriel": (90, 0.9), "annuel": (365, 0.8)}
FEATURES = {
    "free": {
        "positionnement": "Découverte généreuse — assez pour sentir la valeur, limitée pour protéger les modules avancés.",
        "rations_par_mois": 10,
        "diagnostics_vetscan_par_mois": 3,
        "floravet_analyses_par_mois": 3,
        "farmmanager_evenements_par_mois": 30,
        "farmmanager_briefing_quotidien": True,
        "reprotrack_evenements_par_mois": 5,
        "farmacademy_lecons_decouverte": 3,
        "farmcommunity_lecture": True,
        "farmcommunity_posts_par_mois": 2,
        "farmcast_scripts_par_mois": 1,
        "langues": 5,
        "exports_pdf": 1,
        "support": "communauté",
        "modules_inclus_limites": ["NutriCore", "VetScan", "ReproTrack", "FarmManager", "FloraVet AI", "FarmAcademy", "FarmCast", "FarmCommunity"],
        "upgrade_trigger": "Passez à Standard dès que vous voulez travailler sans compter les rations et événements.",
    },
    "standard": {
        "positionnement": "L'offre quotidienne pour l'éleveur individuel sérieux.",
        "rations_illimitees": True,
        "diagnostics_vetscan_par_mois": 30,
        "floravet_analyses_par_mois": 25,
        "farmmanager_evenements_illimites": True,
        "farmmanager_finances": True,
        "reprotrack_evenements_illimites": True,
        "farmacademy_lecons_par_mois": 15,
        "farmcast_contenus_par_mois": 5,
        "farmcommunity_posts_par_mois": 20,
        "langues": 50,
        "exports_pdf": 10,
        "support": "communauté prioritaire",
        "bonus_gamification": "+250 🌟 activation Standard",
        "upgrade_trigger": "Premium débloque l'apprentissage complet, PastureMap et les analyses avancées.",
    },
    "premium": {
        "positionnement": "Meilleur rapport valeur/prix — pour exploiter toute la puissance IA sans stress.",
        "tout_standard": True,
        "vetscan_illimite": True,
        "floravet_analyses_illimitees": True,
        "farmacademy_illimite": True,
        "pasturemap": True,
        "farmmanager_rapports_pdf": True,
        "farmcast_contenus_par_mois": 25,
        "farmcommunity_marketplace_avance": True,
        "projections_financieres": True,
        "exports_pdf_illimites": True,
        "support": "prioritaire",
        "bonus_gamification": "+1 200 🌟 activation Premium",
        "upgrade_trigger": "VIP ajoute l'équipe, le suivi multi-utilisateurs et un rendez-vous expert mensuel.",
    },
    "vip": {
        "positionnement": "Pour ferme structurée : équipe, multi-lots, délégation et pilotage professionnel.",
        "tout_premium": True,
        "multi_users": 8,
        "roles_equipe": True,
        "api_access": True,
        "expert_mensuel": True,
        "farmmanager_multi_techniciens": True,
        "farmcast_contenus_par_mois": 100,
        "campagnes_whatsapp": True,
        "tableaux_bord_avances": True,
        "support": "VIP WhatsApp",
        "bonus_gamification": "+4 000 🌟 activation VIP",
        "upgrade_trigger": "Gold est idéal pour coopératives, ONG et organisations multi-fermes.",
    },
    "gold": {
        "positionnement": "Organisation, coopérative, ONG ou réseau : FeedFormula AI devient votre plateforme agricole.",
        "tout_vip": True,
        "users_illimites": True,
        "white_label": True,
        "farmcast_illimite": True,
        "formations_personnalisees": True,
        "multi_fermes": True,
        "dashboard_direction": True,
        "accompagnement_strategique": True,
        "support": "partenaire dédié",
        "bonus_gamification": "+15 000 🌟 activation Gold",
        "upgrade_trigger": "Vous êtes au niveau maximum : contactez-nous pour intégrations sur mesure.",
    },
}


class PaiementCreateRequest(BaseModel):
    user_id: str = Field(..., min_length=3)
    abonnement: str = Field(..., min_length=2)
    duree: str = Field(default="mensuel")
    telephone: str = Field(..., min_length=6)
    prenom: str = Field(default="Client")

    @field_validator("user_id", "abonnement", "duree", "telephone", "prenom")
    @classmethod
    def _strip(cls, value: str) -> str:
        txt = (value or "").strip()
        if not txt:
            raise ValueError("Champ vide.")
        return txt


class PaiementService:
    def _normalize_abonnement(self, abonnement: str) -> str:
        txt = (abonnement or "").strip().lower()
        aliases = {"essentiel": "standard", "basique": "standard", "or": "gold"}
        txt = aliases.get(txt, txt)
        if txt not in OFFRES:
            raise HTTPException(status_code=400, detail="Abonnement invalide.")
        return txt

    def _normalize_duree(self, duree: str) -> str:
        txt = (duree or "mensuel").strip().lower()
        if txt not in DUREES:
            raise HTTPException(status_code=400, detail="Durée invalide.")
        return txt

    def _calculer_montant(self, abonnement: str, duree: str) -> float:
        base = float(OFFRES[self._normalize_abonnement(abonnement)])
        jours, coef = DUREES[self._normalize_duree(duree)]
        if base == 0:
            return 0.0
        if jours == 30:
            return round(base * coef, 2)
        if jours == 90:
            return round(base * 3 * coef, 2)
        return round(base * 12 * coef, 2)

    def _date_expiration(self, duree: str) -> datetime:
        jours, _ = DUREES[self._normalize_duree(duree)]
        return datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=jours)

    def get_fonctionnalites_par_abonnement(self, abonnement: str) -> Dict[str, Any]:
        code = self._normalize_abonnement(abonnement)
        return FEATURES[code]

    async def creer_transaction_fedapay(
        self,
        user_id: str,
        abonnement: str,
        duree: str,
        telephone: str,
        prenom: str,
        db: Session,
    ) -> Dict[str, Any]:
        user = get_user_by_id(db, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="Utilisateur introuvable.")
        abonnement_code = self._normalize_abonnement(abonnement)
        duree_code = self._normalize_duree(duree)
        montant = self._calculer_montant(abonnement_code, duree_code)
        transaction_id = uuid.uuid4().hex
        lien_paiement = f"{FEDAPAY_BASE_URL.rstrip('/')}/checkout/{transaction_id}"
        provider = "simulation"
        statut = "pending"
        callback_payload: Dict[str, Any] = {}
        if FEDAPAY_SECRET_KEY:
            try:
                payload = {
                    "amount": montant,
                    "description": f"FeedFormula AI - {abonnement_code}",
                    "currency": {"iso": "XOF"},
                    "customer": {
                        "firstname": prenom,
                        "phone_number": {"number": telephone, "country": "bj"},
                    },
                    "callback_url": f"{APP_URL.rstrip('/')}/paiement/webhook",
                    "metadata": {
                        "user_id": user_id,
                        "abonnement": abonnement_code,
                        "duree": duree_code,
                        "telephone": telephone,
                    },
                }
                response = requests.post(
                    f"{FEDAPAY_BASE_URL.rstrip('/')}/transactions",
                    headers={
                        "Authorization": f"Bearer {FEDAPAY_SECRET_KEY}",
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                    },
                    json=payload,
                    timeout=30,
                )
                response.raise_for_status()
                callback_payload = response.json() if response.content else {}
                provider = "fedapay"
                statut = str(callback_payload.get("status") or "pending").lower()
                lien_paiement = str(
                    callback_payload.get("payment_url")
                    or callback_payload.get("url")
                    or lien_paiement
                )
            except Exception as exc:
                callback_payload = {"error": str(exc)}
                provider = "simulation"
                statut = "paid"
        else:
            statut = "paid"

        points_bonus = 200 if statut == "paid" else 0
        date_expiration = (
            self._date_expiration(duree_code) if statut == "paid" else None
        )
        row = create_transaction_paiement(
            db,
            transaction_id=transaction_id,
            user_id=user_id,
            abonnement=abonnement_code,
            duree=duree_code,
            montant=montant,
            statut=statut,
            provider=provider,
            lien_paiement=lien_paiement,
            telephone=telephone,
            prenom=prenom,
            callback_payload=callback_payload,
            date_expiration=date_expiration,
            points_bonus=points_bonus,
        )
        if statut == "paid":
            setattr(user, "abonnement", abonnement_code)
            setattr(user, "is_active", True)
            setattr(
                user,
                "derniere_connexion",
                datetime.now(timezone.utc).replace(tzinfo=None),
            )
            db.commit()
            add_points_to_user(db, user_id, 200)
        return {
            "transaction_id": row.transaction_id,
            "lien_paiement": row.lien_paiement,
            "montant": montant,
            "statut": statut,
        }

    async def confirmer_paiement(
        self, transaction_id: str, db: Session
    ) -> Dict[str, Any]:
        row = get_transaction_paiement_by_id(db, transaction_id)
        if not row:
            raise HTTPException(status_code=404, detail="Transaction introuvable.")
        if row.statut == "paid":
            return {
                "statut": row.statut,
                "abonnement": row.abonnement,
                "date_expiration": row.date_expiration.isoformat()
                if row.date_expiration
                else None,
            }
        approved = True
        if row.provider == "fedapay" and FEDAPAY_SECRET_KEY:
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
                data = response.json() if response.content else {}
                status_remote = str(
                    data.get("status") or data.get("payment_status") or ""
                ).lower()
                approved = status_remote in {
                    "paid",
                    "approved",
                    "success",
                    "successful",
                    "completed",
                }
                row.callback_payload = json.dumps(data, ensure_ascii=False)
            except Exception:
                approved = False
        if approved:
            row.statut = "paid"
            row.date_expiration = self._date_expiration(row.duree)
            row.date_mise_a_jour = datetime.now(timezone.utc).replace(tzinfo=None)
            user = get_user_by_id(db, row.user_id)
            if user:
                user.abonnement = row.abonnement
                user.is_active = True
                add_points_to_user(db, row.user_id, 200)
                db.commit()
            return {
                "statut": row.statut,
                "abonnement": row.abonnement,
                "date_expiration": row.date_expiration.isoformat()
                if row.date_expiration
                else None,
            }
        row.statut = "failed"
        row.date_mise_a_jour = datetime.now(timezone.utc).replace(tzinfo=None)
        db.commit()
        return {
            "statut": row.statut,
            "abonnement": row.abonnement,
            "date_expiration": None,
        }

    async def verifier_abonnement_actif(
        self, user_id: str, db: Session
    ) -> Dict[str, Any]:
        user = get_user_by_id(db, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="Utilisateur introuvable.")
        active = (user.abonnement or "free").lower()
        expirations = list_user_transactions(db, user_id, limit=50)
        expiration = None
        for item in expirations:
            if (
                item.abonnement == active
                and item.statut == "paid"
                and item.date_expiration
            ):
                expiration = item.date_expiration
                break
        if expiration and expiration < datetime.now(timezone.utc).replace(tzinfo=None):
            active = "free"
            user.abonnement = "free"
            db.commit()
        remaining = 0
        if expiration:
            remaining = max(
                0, (expiration - datetime.now(timezone.utc).replace(tzinfo=None)).days
            )
        return {
            "abonnement_actuel": active,
            "jours_restants": remaining,
            "fonctionnalites_disponibles": self.get_fonctionnalites_par_abonnement(
                active
            ),
        }


SERVICE = PaiementService()


@router.post("/creer")
async def creer(
    payload: PaiementCreateRequest, db: Session = Depends(get_db)
) -> Dict[str, Any]:
    result = await SERVICE.creer_transaction_fedapay(
        payload.user_id,
        payload.abonnement,
        payload.duree,
        payload.telephone,
        payload.prenom,
        db,
    )
    return result


@router.post("/webhook")
async def webhook(request: Request, db: Session = Depends(get_db)) -> Dict[str, Any]:
    raw = await request.body()
    try:
        payload = json.loads(raw.decode("utf-8") or "{}")
    except Exception:
        payload = {}
    transaction_id = str(
        payload.get("reference")
        or payload.get("transaction_id")
        or payload.get("id")
        or ""
    ).strip()
    if not transaction_id:
        return {"message": "Webhook reçu.", "statut": "ignored"}
    row = get_transaction_paiement_by_id(db, transaction_id)
    if not row:
        row = create_transaction_paiement(
            db,
            transaction_id=transaction_id,
            user_id=str(
                payload.get("metadata", {}).get("user_id")
                or payload.get("user_id")
                or ""
            ),
            abonnement=str(
                payload.get("metadata", {}).get("abonnement")
                or payload.get("abonnement")
                or "free"
            ),
            duree=str(payload.get("metadata", {}).get("duree") or "mensuel"),
            montant=float(payload.get("amount") or 0),
            statut=str(payload.get("status") or "paid").lower(),
            provider="fedapay",
            lien_paiement=str(payload.get("payment_url") or ""),
            telephone=str(payload.get("metadata", {}).get("telephone") or ""),
            prenom=str(payload.get("metadata", {}).get("prenom") or "Client"),
            callback_payload=payload,
            date_expiration=None,
            points_bonus=200,
        )
    else:
        row.statut = "paid"
        row.callback_payload = json.dumps(payload, ensure_ascii=False)
        row.date_expiration = SERVICE._date_expiration(row.duree)
        row.date_mise_a_jour = datetime.now(timezone.utc).replace(tzinfo=None)
        db.commit()
    user = get_user_by_id(db, row.user_id)
    if user:
        user.abonnement = row.abonnement
        user.is_active = True
        add_points_to_user(db, row.user_id, 200)
        db.commit()
    return {
        "message": "Webhook traité.",
        "transaction": {
            "transaction_id": row.transaction_id,
            "statut": row.statut,
            "abonnement": row.abonnement,
        },
        "statut": row.statut,
    }


@router.get("/statut/{transaction_id}")
def statut(transaction_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    row = get_transaction_paiement_by_id(db, transaction_id)
    if not row:
        raise HTTPException(status_code=404, detail="Transaction introuvable.")
    return {
        "transaction_id": row.transaction_id,
        "statut": row.statut,
        "abonnement_active": row.abonnement if row.statut == "paid" else None,
        "montant": row.montant,
        "date_expiration": row.date_expiration.isoformat()
        if row.date_expiration
        else None,
    }


@router.get("/abonnement/{user_id}")
async def abonnement(user_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    return await SERVICE.verifier_abonnement_actif(user_id, db)


@router.get("/historique/{user_id}")
def historique(user_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    rows = list_user_transactions(db, user_id, limit=50)
    return {
        "user_id": user_id,
        "total": len(rows),
        "transactions": [
            {
                "transaction_id": r.transaction_id,
                "abonnement": r.abonnement,
                "duree": r.duree,
                "montant": r.montant,
                "statut": r.statut,
                "provider": r.provider,
                "date_creation": r.date_creation.isoformat()
                if r.date_creation
                else None,
                "date_expiration": r.date_expiration.isoformat()
                if r.date_expiration
                else None,
            }
            for r in rows
        ],
    }


@router.get("/offres")
def offres() -> Dict[str, Any]:
    return {
        "offres": [{"code": k, "prix": v} for k, v in OFFRES.items()],
        "durees": DUREES,
        "fonctionnalites": FEATURES,
    }


__all__ = ["router", "SERVICE", "PaiementService", "OFFRES", "DUREES", "FEATURES"]
