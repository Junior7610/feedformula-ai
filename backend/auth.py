#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
API d'authentification FeedFormula AI (OTP + JWT).

Fonctionnalités :
- Génération OTP 6 chiffres
- Vérification OTP avec expiration et limite d'essais
- Génération de token JWT valide 30 jours
- Middleware d'authentification FastAPI
- Endpoints :
  - POST /auth/inscription
  - POST /auth/connexion
  - POST /auth/verifier-otp
  - GET  /auth/profil (authentifié)

Remarque importante :
- Les OTP sont persistés en base de données pour une meilleure robustesse.
"""

from __future__ import annotations

import os
import random
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from jose import JWTError, jwt
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

# ---------------------------------------------------------------------------
# Imports locaux (compatibles "python -m backend.main" et "python backend/main.py")
# ---------------------------------------------------------------------------
try:
    from .database import (
        create_user,
        get_db,
        get_user_by_id,
        get_user_by_telephone,
        serialize_user,
        update_user_last_login,
        upsert_otp_code,
        verify_otp_code as verify_otp_code_db,
    )
except Exception:
    from database import (  # type: ignore
        create_user,
        get_db,
        get_user_by_id,
        get_user_by_telephone,
        serialize_user,
        update_user_last_login,
        upsert_otp_code,
        verify_otp_code as verify_otp_code_db,
    )


# ---------------------------------------------------------------------------
# Configuration sécurité
# ---------------------------------------------------------------------------
APP_ENV = (os.getenv("APP_ENV", "development") or "development").strip().lower()
IS_PRODUCTION = APP_ENV in {"prod", "production"}

# Clé JWT:
# - Priorité à SECRET_KEY si fournie
# - Fallback dev explicite si absente (jamais pour la production)
SECRET_KEY = (os.getenv("SECRET_KEY", "") or "").strip()
if not SECRET_KEY:
    SECRET_KEY = "feedformula-dev-only-change-this-secret-key-2026"
    # En production, on interdit le fallback pour éviter tout risque de sécurité.
    if IS_PRODUCTION:
        raise RuntimeError(
            "SECRET_KEY est obligatoire en production. Définis une clé forte dans l'environnement."
        )

JWT_ALGORITHM = (os.getenv("JWT_ALGORITHM", "HS256") or "HS256").strip()
JWT_EXPIRE_DAYS = int(os.getenv("JWT_OTP_EXPIRE_DAYS", "30") or 30)

# Durée de vie OTP (minutes)
OTP_EXPIRE_MINUTES = int(os.getenv("OTP_EXPIRE_MINUTES", "10") or 10)
# Nombre max d'essais OTP
OTP_MAX_ATTEMPTS = int(os.getenv("OTP_MAX_ATTEMPTS", "5") or 5)


# ---------------------------------------------------------------------------
# Stock OTP
# ---------------------------------------------------------------------------
# Les OTP sont persistés en base (table otp_codes via backend/database.py).


# ---------------------------------------------------------------------------
# Utilitaires
# ---------------------------------------------------------------------------
def _utcnow() -> datetime:
    """Retourne la date/heure UTC timezone-aware."""
    return datetime.now(timezone.utc)


def _normaliser_telephone(telephone: str) -> str:
    """
    Normalise un téléphone en gardant uniquement les chiffres.

    Exemples :
    - "+229 01 97 00 00 00" -> "2290197000000"
    - "01-97-00-00-00"      -> "0197000000"
    """
    if not isinstance(telephone, str):
        return ""
    return re.sub(r"\D+", "", telephone).strip()


def generer_code_otp() -> str:
    """
    Génère un code OTP à 6 chiffres.
    """
    return f"{random.randint(0, 999999):06d}"


def generer_otp() -> str:
    """
    Alias public demandé par l'API.
    """
    return generer_code_otp()


def _masquer_telephone(telephone: str) -> str:
    """
    Masque un numéro de téléphone pour éviter l'exposition directe.
    Exemple: 2290197000000 -> *********000
    """
    tel = _normaliser_telephone(telephone)
    if len(tel) <= 3:
        return "***"
    return f"{'*' * (len(tel) - 3)}{tel[-3:]}"


def _payload_otp_debug(code: str) -> Dict[str, Any]:
    """
    Retourne le payload OTP de debug uniquement hors production.
    """
    if IS_PRODUCTION:
        return {}
    return {"otp_dev": code}


def enregistrer_otp(db: Session, telephone: str, code: str) -> None:
    """
    Enregistre un OTP en base de données avec expiration.
    """
    tel = _normaliser_telephone(telephone)
    if not tel:
        raise ValueError("Téléphone invalide pour enregistrement OTP.")

    expires_at = datetime.utcnow() + timedelta(minutes=OTP_EXPIRE_MINUTES)
    upsert_otp_code(
        db=db,
        telephone=tel,
        code=str(code),
        expires_at=expires_at,
        max_attempts=OTP_MAX_ATTEMPTS,
    )


def verifier_code_otp(db: Session, telephone: str, code_saisi: str) -> bool:
    """
    Vérifie un OTP persistant en base.
    Retourne True si valide, sinon False.
    """
    tel = _normaliser_telephone(telephone)
    code = (code_saisi or "").strip()

    if not tel or not code:
        return False

    return bool(verify_otp_code_db(db, tel, code))


def verifier_otp(code: str, code_attendu: str) -> bool:
    """
    Compare deux codes OTP de manière pure.
    """
    return (code or "").strip() == (code_attendu or "").strip()


def creer_jwt_utilisateur(user_id: str, telephone: str) -> str:
    """
    Crée un token JWT valable 30 jours.
    """
    now = _utcnow()
    expire = now + timedelta(days=JWT_EXPIRE_DAYS)

    payload = {
        "sub": user_id,
        "telephone": telephone,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "scope": "user",
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=JWT_ALGORITHM)


def creer_token_jwt(user_id: str) -> str:
    """
    Alias demandé par le backend pour générer un token à partir d'un user_id.
    """
    return creer_jwt_utilisateur(user_id, "")


def verifier_token_jwt(token: str) -> Optional[str]:
    """
    Vérifie un token JWT et retourne l'identifiant utilisateur si valide.
    """
    try:
        payload = decoder_jwt(token)
        return str(payload.get("sub") or "").strip() or None
    except HTTPException:
        return None


def get_current_user(token: str):
    """
    Retourne l'utilisateur courant à partir d'un token JWT.
    """
    user_id = verifier_token_jwt(token)
    if not user_id:
        return None

    db_gen = get_db()
    db = next(db_gen)
    try:
        return get_user_by_id(db, user_id)
    finally:
        try:
            db.close()
        except Exception:
            pass
        "exp": int(expire.timestamp()),
        "scope": "user",
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=JWT_ALGORITHM)


def decoder_jwt(token: str) -> Dict[str, Any]:
    """
    Décode et valide un token JWT.
    Lève HTTPException en cas d'échec.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGORITHM])
        if not isinstance(payload, dict):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token invalide (payload).",
            )
        if not payload.get("sub"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token invalide (sub manquant).",
            )
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide ou expiré.",
        )


def extraire_bearer_token(request: Request) -> Optional[str]:
    """
    Extrait le token Bearer depuis l'en-tête Authorization.
    """
    raw = request.headers.get("Authorization", "")
    if not raw:
        return None
    parts = raw.split(" ", 1)
    if len(parts) != 2:
        return None
    if parts[0].lower().strip() != "bearer":
        return None
    token = parts[1].strip()
    return token or None


# ---------------------------------------------------------------------------
# Middleware d'authentification
# ---------------------------------------------------------------------------
class AuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware qui décode automatiquement le JWT si présent.

    - Si Authorization Bearer est valide :
      request.state.user_payload = payload JWT
    - Sinon :
      request.state.user_payload = None

    Ce middleware ne bloque pas la requête par défaut.
    Le blocage est fait par la dépendance `exiger_utilisateur_authentifie`.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        request.state.user_payload = None

        token = extraire_bearer_token(request)
        if token:
            try:
                payload = decoder_jwt(token)
                request.state.user_payload = payload
            except HTTPException:
                # On n'interrompt pas ici. Les endpoints protégés décideront.
                request.state.user_payload = None

        return await call_next(request)


def install_auth_middleware(app: Any) -> None:
    """
    Installe le middleware d'authentification sur l'application FastAPI.
    """
    app.add_middleware(AuthMiddleware)


# ---------------------------------------------------------------------------
# Dépendance d'authentification stricte
# ---------------------------------------------------------------------------
def exiger_utilisateur_authentifie(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Dépendance FastAPI qui exige une authentification valide.
    Retourne l'objet User en base.
    """
    payload = getattr(request.state, "user_payload", None)
    if not payload or not isinstance(payload, dict):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentification requise.",
        )

    user_id = str(payload.get("sub", "")).strip()
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide.",
        )

    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Utilisateur introuvable.",
        )

    return user


# ---------------------------------------------------------------------------
# Schémas Pydantic
# ---------------------------------------------------------------------------
class InscriptionRequest(BaseModel):
    telephone: str = Field(..., description="Numéro de téléphone utilisateur")
    prenom: str = Field(..., min_length=1, max_length=120)
    langue_preferee: str = Field(default="fr", max_length=20)
    espece_principale: Optional[str] = Field(default=None, max_length=80)
    region: str = Field(default="Bénin", max_length=120)

    @field_validator("telephone")
    @classmethod
    def valider_telephone(cls, v: str) -> str:
        tel = _normaliser_telephone(v)
        if len(tel) < 8:
            raise ValueError("Numéro de téléphone invalide.")
        return tel

    @field_validator("prenom")
    @classmethod
    def valider_prenom(cls, v: str) -> str:
        txt = (v or "").strip()
        if not txt:
            raise ValueError("Le prénom est obligatoire.")
        return txt

    @field_validator("langue_preferee")
    @classmethod
    def valider_langue(cls, v: str) -> str:
        txt = (v or "fr").strip().lower() or "fr"
        return txt

    @field_validator("region")
    @classmethod
    def valider_region(cls, v: str) -> str:
        txt = " ".join((v or "Bénin").strip().split())
        return txt or "Bénin"


class ConnexionRequest(BaseModel):
    telephone: str = Field(..., description="Numéro de téléphone utilisateur")

    @field_validator("telephone")
    @classmethod
    def valider_telephone(cls, v: str) -> str:
        tel = _normaliser_telephone(v)
        if len(tel) < 8:
            raise ValueError("Numéro de téléphone invalide.")
        return tel


class VerificationOtpRequest(BaseModel):
    telephone: str = Field(...)
    code_otp: str = Field(..., min_length=6, max_length=6)

    @field_validator("telephone")
    @classmethod
    def valider_telephone(cls, v: str) -> str:
        tel = _normaliser_telephone(v)
        if len(tel) < 8:
            raise ValueError("Numéro de téléphone invalide.")
        return tel

    @field_validator("code_otp")
    @classmethod
    def valider_code(cls, v: str) -> str:
        code = (v or "").strip()
        if not re.fullmatch(r"\d{6}", code):
            raise ValueError("Le code OTP doit contenir exactement 6 chiffres.")
        return code


# ---------------------------------------------------------------------------
# Router FastAPI
# ---------------------------------------------------------------------------
router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/inscription")
def inscription(payload: InscriptionRequest, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Crée un nouvel utilisateur puis génère un OTP.
    """
    # Vérifie unicité téléphone.
    existing = get_user_by_telephone(db, payload.telephone)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ce numéro est déjà inscrit. Utilise /auth/connexion.",
        )

    # Création utilisateur.
    user = create_user(
        db=db,
        telephone=payload.telephone,
        prenom=payload.prenom,
        langue_preferee=payload.langue_preferee,
        espece_principale=payload.espece_principale,
        abonnement="free",
        region=payload.region,
    )

    # Génération OTP.
    code = generer_code_otp()
    enregistrer_otp(db, payload.telephone, code)

    # En production, le code OTP ne doit jamais être renvoyé en réponse API.
    response = {
        "message": "Inscription créée. OTP envoyé.",
        "telephone_masque": _masquer_telephone(payload.telephone),
        "otp_expire_dans_minutes": OTP_EXPIRE_MINUTES,
    }
    response.update(_payload_otp_debug(code))
    return response


@router.post("/connexion")
def connexion(payload: ConnexionRequest, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Déclenche un OTP pour un utilisateur existant.
    """
    user = get_user_by_telephone(db, payload.telephone)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aucun compte trouvé pour ce numéro. Utilise /auth/inscription.",
        )

    code = generer_code_otp()
    enregistrer_otp(db, payload.telephone, code)

    response = {
        "message": "OTP envoyé.",
        "telephone_masque": _masquer_telephone(payload.telephone),
        "otp_expire_dans_minutes": OTP_EXPIRE_MINUTES,
    }
    response.update(_payload_otp_debug(code))
    return response


@router.post("/verifier-otp")
def verifier_otp_endpoint(payload: VerificationOtpRequest, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Vérifie l'OTP puis émet un JWT valide 30 jours.
    """
    user = get_user_by_telephone(db, payload.telephone)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur introuvable.",
        )

    ok = verifier_code_otp(db, payload.telephone, payload.code_otp)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Code OTP invalide.",
        )

    # Mise à jour dernière connexion.
    user = update_user_last_login(db, user.id) or user

    # Génération JWT 30 jours.
    token = creer_jwt_utilisateur(user.id, user.telephone)

    return {
        "access_token": token,
        "token_type": "bearer",
        "expire_dans_jours": JWT_EXPIRE_DAYS,
        "user": serialize_user(user),
    }


@router.get("/profil")
def profil(
    user=Depends(exiger_utilisateur_authentifie),
) -> Dict[str, Any]:
    """
    Retourne le profil utilisateur authentifié.
    """
    return {
        "message": "Profil récupéré avec succès.",
        "user": serialize_user(user),
    }


__all__ = [
    "router",
    "AuthMiddleware",
    "install_auth_middleware",
    "exiger_utilisateur_authentifie",
    "generer_code_otp",
    "generer_otp",
    "verifier_code_otp",
    "verifier_otp",
    "creer_jwt_utilisateur",
    "creer_token_jwt",
    "verifier_token_jwt",
    "get_current_user",
    "verifier_otp_endpoint",
]
