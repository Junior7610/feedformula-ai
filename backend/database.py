#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Module base de données de FeedFormula AI.

Ce module fournit :
- La configuration SQLAlchemy (SQLite en développement),
- Les modèles ORM des tables métier,
- L'initialisation de la base,
- Les fonctions CRUD principales.

Tous les commentaires sont en français pour faciliter la maintenance.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    desc,
)
from sqlalchemy.orm import Session, declarative_base, relationship, sessionmaker

# ---------------------------------------------------------------------------
# Configuration SQLAlchemy
# ---------------------------------------------------------------------------

# Racine du projet : .../feedformula-ai
ROOT_DIR = Path(__file__).resolve().parent.parent

# Fichier SQLite par défaut pour le développement local.
DATA_DIR = ROOT_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_SQLITE_PATH = DATA_DIR / "feedformula.db"
DEFAULT_DATABASE_URL = f"sqlite:///{DEFAULT_SQLITE_PATH.as_posix()}"

# Possibilité de surcharger via variable d'environnement.
DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL).strip() or DEFAULT_DATABASE_URL

# Option nécessaire pour SQLite en environnement web multithread.
connect_args: Dict[str, Any] = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, future=True, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, future=True)
Base = declarative_base()


# ---------------------------------------------------------------------------
# Helpers internes
# ---------------------------------------------------------------------------

def _uuid_str() -> str:
    """Retourne un UUID v4 sous forme de chaîne."""
    return str(uuid.uuid4())


def _to_json_text(value: Any) -> str:
    """Convertit un objet Python en JSON texte (UTF-8)."""
    return json.dumps(value, ensure_ascii=False)


def _from_json_text(value: Optional[str], default: Any) -> Any:
    """Convertit un JSON texte en objet Python (avec fallback sûr)."""
    if not value:
        return default
    try:
        return json.loads(value)
    except Exception:
        return default


def _niveau_depuis_points(points_total: int) -> int:
    """
    Convertit un total de points en niveau.
    Barème simple et progressif.
    """
    seuils = [0, 150, 350, 700, 1200, 1900, 2800, 4000, 5500, 7500]
    niveau = 1
    for i, seuil in enumerate(seuils, start=1):
        if points_total >= seuil:
            niveau = i
    return niveau


# ---------------------------------------------------------------------------
# Modèles ORM
# ---------------------------------------------------------------------------

class User(Base):
    """
    Table users.
    """

    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=_uuid_str)
    telephone = Column(String(50), unique=True, nullable=False, index=True)
    prenom = Column(String(120), nullable=False)
    langue_preferee = Column(String(20), nullable=False, default="fr")
    espece_principale = Column(String(80), nullable=True)
    date_inscription = Column(DateTime, nullable=False, default=datetime.utcnow)
    derniere_connexion = Column(DateTime, nullable=True)
    points_total = Column(Integer, nullable=False, default=0)
    niveau_actuel = Column(Integer, nullable=False, default=1)
    serie_actuelle = Column(Integer, nullable=False, default=0)
    meilleure_serie = Column(Integer, nullable=False, default=0)
    graines_or = Column(Integer, nullable=False, default=0)
    graines_secours = Column(Integer, nullable=False, default=3)
    abonnement = Column(String(30), nullable=False, default="free")
    region = Column(String(120), nullable=False, default="Bénin")

    # Relations
    rations = relationship("Ration", back_populates="user", cascade="all, delete-orphan")
    trophees = relationship("TropheeUtilisateur", back_populates="user", cascade="all, delete-orphan")
    completions_defis = relationship("CompletionDefi", back_populates="user", cascade="all, delete-orphan")


class Ration(Base):
    """
    Table rations.
    """

    __tablename__ = "rations"

    id = Column(String(36), primary_key=True, default=_uuid_str)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    espece = Column(String(80), nullable=False)
    stade = Column(String(80), nullable=False)
    ingredients_saisis = Column(Text, nullable=False)   # JSON texte
    ration_generee = Column(Text, nullable=False)
    composition_json = Column(Text, nullable=False)     # JSON texte
    cout_fcfa_kg = Column(Float, nullable=False, default=0.0)
    cout_7_jours = Column(Float, nullable=False, default=0.0)
    langue = Column(String(20), nullable=False, default="fr")
    points_gagnes = Column(Integer, nullable=False, default=0)
    date_creation = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    user = relationship("User", back_populates="rations")


class TropheeUtilisateur(Base):
    """
    Table trophees_utilisateurs.
    """

    __tablename__ = "trophees_utilisateurs"
    __table_args__ = (
        UniqueConstraint("user_id", "trophee_code", name="uq_user_trophee_code"),
    )

    id = Column(String(36), primary_key=True, default=_uuid_str)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    trophee_code = Column(String(120), nullable=False, index=True)
    date_obtention = Column(DateTime, nullable=False, default=datetime.utcnow)

    user = relationship("User", back_populates="trophees")


class DefiQuotidien(Base):
    """
    Table defis_quotidiens.
    """

    __tablename__ = "defis_quotidiens"

    id = Column(String(36), primary_key=True, default=_uuid_str)
    date = Column(Date, nullable=False, unique=True, index=True)
    defi_1 = Column(Text, nullable=False)  # JSON texte
    defi_2 = Column(Text, nullable=False)  # JSON texte
    defi_3 = Column(Text, nullable=False)  # JSON texte

    completions = relationship("CompletionDefi", back_populates="defi", cascade="all, delete-orphan")


class CompletionDefi(Base):
    """
    Table completions_defis.
    """

    __tablename__ = "completions_defis"
    __table_args__ = (
        UniqueConstraint("user_id", "defi_id", "defi_numero", name="uq_completion_unique"),
    )

    id = Column(String(36), primary_key=True, default=_uuid_str)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    defi_id = Column(String(36), ForeignKey("defis_quotidiens.id", ondelete="CASCADE"), nullable=False, index=True)
    defi_numero = Column(Integer, nullable=False)  # 1, 2 ou 3
    date_completion = Column(DateTime, nullable=False, default=datetime.utcnow)
    points_gagnes = Column(Integer, nullable=False, default=0)

    user = relationship("User", back_populates="completions_defis")
    defi = relationship("DefiQuotidien", back_populates="completions")


class PrixMarche(Base):
    """
    Table prix_marche.
    """

    __tablename__ = "prix_marche"

    id = Column(String(36), primary_key=True, default=_uuid_str)
    ingredient = Column(String(120), nullable=False, index=True)
    prix_fcfa_kg = Column(Float, nullable=False)
    date_mise_a_jour = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    source = Column(String(120), nullable=True)
    region = Column(String(120), nullable=False, default="Bénin")


class OtpCode(Base):
    """
    Table otp_codes.

    Stocke les OTP de manière persistante (usage production).
    """

    __tablename__ = "otp_codes"

    id = Column(String(36), primary_key=True, default=_uuid_str)
    telephone = Column(String(50), unique=True, nullable=False, index=True)
    code = Column(String(6), nullable=False)
    attempts = Column(Integer, nullable=False, default=0)
    max_attempts = Column(Integer, nullable=False, default=5)
    expires_at = Column(DateTime, nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class UserActionLog(Base):
    """
    Table user_action_logs.

    Journal d'actions utilisateur pour analytics, anti-abus et gamification.
    """

    __tablename__ = "user_action_logs"

    id = Column(String(36), primary_key=True, default=_uuid_str)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    action = Column(String(120), nullable=False, index=True)
    points_awarded = Column(Integer, nullable=False, default=0)
    meta_json = Column(Text, nullable=False, default="{}")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)


# ---------------------------------------------------------------------------
# Initialisation et session DB
# ---------------------------------------------------------------------------

def init_db() -> None:
    """
    Initialise la base de données en créant les tables manquantes.
    """
    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    """
    Fournit une session SQLAlchemy.

    Usage attendu dans FastAPI :
        db: Session = Depends(get_db)
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# CRUD - USERS
# ---------------------------------------------------------------------------

def create_user(
    db: Session,
    telephone: str,
    prenom: str,
    langue_preferee: str = "fr",
    espece_principale: Optional[str] = None,
    abonnement: str = "free",
    region: str = "Bénin",
) -> User:
    """Crée un utilisateur."""
    user = User(
        telephone=telephone.strip(),
        prenom=prenom.strip(),
        langue_preferee=(langue_preferee or "fr").strip().lower(),
        espece_principale=(espece_principale or "").strip() or None,
        abonnement=(abonnement or "free").strip().lower(),
        region=(region or "Bénin").strip(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_user_by_id(db: Session, user_id: str) -> Optional[User]:
    """Retourne un utilisateur par ID."""
    return db.query(User).filter(User.id == user_id).first()


def get_user_by_telephone(db: Session, telephone: str) -> Optional[User]:
    """Retourne un utilisateur par téléphone."""
    return db.query(User).filter(User.telephone == telephone.strip()).first()


def upsert_otp_code(
    db: Session,
    telephone: str,
    code: str,
    expires_at: datetime,
    max_attempts: int = 5,
) -> OtpCode:
    """
    Crée ou met à jour un OTP pour un numéro de téléphone.
    """
    tel = (telephone or "").strip()
    otp = db.query(OtpCode).filter(OtpCode.telephone == tel).first()
    if otp is None:
        otp = OtpCode(
            telephone=tel,
            code=str(code),
            attempts=0,
            max_attempts=max(1, int(max_attempts or 5)),
            expires_at=expires_at,
        )
        db.add(otp)
    else:
        otp.code = str(code)
        otp.attempts = 0
        otp.max_attempts = max(1, int(max_attempts or 5))
        otp.expires_at = expires_at
        otp.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(otp)
    return otp


def get_otp_by_telephone(db: Session, telephone: str) -> Optional[OtpCode]:
    """Retourne l'OTP actif (persisté) pour un numéro."""
    return db.query(OtpCode).filter(OtpCode.telephone == (telephone or "").strip()).first()


def verify_otp_code(db: Session, telephone: str, code_saisi: str) -> bool:
    """
    Vérifie un OTP persistant.

    - Retourne True si valide (et supprime l'OTP),
    - Retourne False sinon (et incrémente les essais).
    """
    tel = (telephone or "").strip()
    otp = get_otp_by_telephone(db, tel)
    if otp is None:
        return False

    now = datetime.utcnow()
    if otp.expires_at < now:
        db.delete(otp)
        db.commit()
        return False

    if int(otp.attempts or 0) >= int(otp.max_attempts or 0):
        db.delete(otp)
        db.commit()
        return False

    if str(code_saisi or "").strip() != str(otp.code):
        otp.attempts = int(otp.attempts or 0) + 1
        if otp.attempts >= int(otp.max_attempts or 0):
            db.delete(otp)
        db.commit()
        return False

    db.delete(otp)
    db.commit()
    return True


def clear_otp_by_telephone(db: Session, telephone: str) -> None:
    """Supprime l'OTP associé à un téléphone."""
    otp = get_otp_by_telephone(db, telephone)
    if otp is not None:
        db.delete(otp)
        db.commit()


def update_user_last_login(db: Session, user_id: str, dt: Optional[datetime] = None) -> Optional[User]:
    """Met à jour la dernière connexion."""
    user = get_user_by_id(db, user_id)
    if not user:
        return None
    user.derniere_connexion = dt or datetime.utcnow()
    db.commit()
    db.refresh(user)
    return user


def add_points_to_user(db: Session, user_id: str, points: int) -> Optional[User]:
    """Ajoute des points, puis recalcule le niveau."""
    user = get_user_by_id(db, user_id)
    if not user:
        return None
    user.points_total = max(0, int(user.points_total) + int(points or 0))
    user.niveau_actuel = _niveau_depuis_points(user.points_total)
    db.commit()
    db.refresh(user)
    return user


def update_user_streak(db: Session, user_id: str, serie_actuelle: int) -> Optional[User]:
    """Met à jour la série actuelle et la meilleure série."""
    user = get_user_by_id(db, user_id)
    if not user:
        return None
    serie = max(0, int(serie_actuelle or 0))
    user.serie_actuelle = serie
    user.meilleure_serie = max(int(user.meilleure_serie or 0), serie)
    db.commit()
    db.refresh(user)
    return user


def list_top_users_by_points(db: Session, limit: int = 50) -> List[User]:
    """Retourne le top utilisateurs trié par points."""
    n = max(1, min(int(limit or 50), 500))
    return db.query(User).order_by(desc(User.points_total), User.date_inscription).limit(n).all()


def log_user_action(
    db: Session,
    user_id: str,
    action: str,
    points_awarded: int = 0,
    meta: Optional[Dict[str, Any]] = None,
    created_at: Optional[datetime] = None,
) -> UserActionLog:
    """
    Enregistre une action utilisateur dans le journal persistant.
    """
    row = UserActionLog(
        user_id=(user_id or "").strip(),
        action=(action or "").strip(),
        points_awarded=int(points_awarded or 0),
        meta_json=_to_json_text(meta or {}),
        created_at=created_at or datetime.utcnow(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_last_action_at(db: Session, user_id: str, action: str) -> Optional[datetime]:
    """
    Retourne la date de dernière occurrence d'une action pour un utilisateur.
    """
    row = (
        db.query(UserActionLog)
        .filter(
            UserActionLog.user_id == (user_id or "").strip(),
            UserActionLog.action == (action or "").strip(),
        )
        .order_by(desc(UserActionLog.created_at))
        .first()
    )
    return row.created_at if row else None


def count_user_actions_last_24h(db: Session, user_id: str) -> int:
    """
    Compte le nombre d'actions utilisateur sur les dernières 24h.
    """
    since = datetime.utcnow() - timedelta(hours=24)
    return (
        db.query(UserActionLog)
        .filter(
            UserActionLog.user_id == (user_id or "").strip(),
            UserActionLog.created_at >= since,
        )
        .count()
    )


def get_user_action_counts(db: Session, user_id: str, days: int = 365) -> Dict[str, int]:
    """
    Retourne le volume d'actions par type pour un utilisateur sur une période.
    """
    horizon = max(1, int(days or 365))
    since = datetime.utcnow() - timedelta(days=horizon)
    rows = (
        db.query(UserActionLog)
        .filter(
            UserActionLog.user_id == (user_id or "").strip(),
            UserActionLog.created_at >= since,
        )
        .all()
    )

    counts: Dict[str, int] = {}
    for row in rows:
        key = str(row.action or "").strip()
        if not key:
            continue
        counts[key] = counts.get(key, 0) + 1
    return counts


# ---------------------------------------------------------------------------
# CRUD - RATIONS
# ---------------------------------------------------------------------------

def create_ration(
    db: Session,
    user_id: str,
    espece: str,
    stade: str,
    ingredients_saisis: Any,
    ration_generee: str,
    composition_json: Any,
    cout_fcfa_kg: float,
    cout_7_jours: float,
    langue: str = "fr",
    points_gagnes: int = 0,
) -> Ration:
    """Crée une ration."""
    ration = Ration(
        user_id=user_id,
        espece=(espece or "").strip(),
        stade=(stade or "").strip(),
        ingredients_saisis=_to_json_text(ingredients_saisis),
        ration_generee=ration_generee or "",
        composition_json=_to_json_text(composition_json),
        cout_fcfa_kg=float(cout_fcfa_kg or 0.0),
        cout_7_jours=float(cout_7_jours or 0.0),
        langue=(langue or "fr").strip().lower(),
        points_gagnes=max(0, int(points_gagnes or 0)),
    )
    db.add(ration)
    db.commit()
    db.refresh(ration)
    return ration


def list_user_rations(db: Session, user_id: str, limit: int = 10) -> List[Ration]:
    """Retourne les dernières rations d'un utilisateur."""
    n = max(1, min(int(limit or 10), 200))
    return (
        db.query(Ration)
        .filter(Ration.user_id == user_id)
        .order_by(desc(Ration.date_creation))
        .limit(n)
        .all()
    )


# ---------------------------------------------------------------------------
# CRUD - TROPHÉES
# ---------------------------------------------------------------------------

def create_trophee_for_user(db: Session, user_id: str, trophee_code: str) -> Optional[TropheeUtilisateur]:
    """
    Attribue un trophée à un utilisateur.
    Si déjà présent, ne crée pas de doublon.
    """
    code = (trophee_code or "").strip()
    if not code:
        return None

    existant = (
        db.query(TropheeUtilisateur)
        .filter(
            TropheeUtilisateur.user_id == user_id,
            TropheeUtilisateur.trophee_code == code,
        )
        .first()
    )
    if existant:
        return existant

    troph = TropheeUtilisateur(user_id=user_id, trophee_code=code)
    db.add(troph)
    db.commit()
    db.refresh(troph)
    return troph


def list_user_trophees(db: Session, user_id: str) -> List[TropheeUtilisateur]:
    """Liste les trophées d'un utilisateur (du plus récent au plus ancien)."""
    return (
        db.query(TropheeUtilisateur)
        .filter(TropheeUtilisateur.user_id == user_id)
        .order_by(desc(TropheeUtilisateur.date_obtention))
        .all()
    )


# ---------------------------------------------------------------------------
# CRUD - DÉFIS QUOTIDIENS
# ---------------------------------------------------------------------------

def create_or_update_defi_quotidien(
    db: Session,
    jour: date,
    defi_1: Any,
    defi_2: Any,
    defi_3: Any,
) -> DefiQuotidien:
    """Crée ou met à jour les 3 défis d'une journée."""
    defi = db.query(DefiQuotidien).filter(DefiQuotidien.date == jour).first()
    if defi is None:
        defi = DefiQuotidien(
            date=jour,
            defi_1=_to_json_text(defi_1),
            defi_2=_to_json_text(defi_2),
            defi_3=_to_json_text(defi_3),
        )
        db.add(defi)
    else:
        defi.defi_1 = _to_json_text(defi_1)
        defi.defi_2 = _to_json_text(defi_2)
        defi.defi_3 = _to_json_text(defi_3)

    db.commit()
    db.refresh(defi)
    return defi


def get_defi_quotidien_by_date(db: Session, jour: date) -> Optional[DefiQuotidien]:
    """Retourne les défis d'une journée donnée."""
    return db.query(DefiQuotidien).filter(DefiQuotidien.date == jour).first()


def complete_defi(
    db: Session,
    user_id: str,
    defi_id: str,
    defi_numero: int,
    points_gagnes: int,
) -> Optional[CompletionDefi]:
    """
    Marque un défi comme complété pour un utilisateur.
    Empêche les doublons via contrainte unique + vérification préalable.
    """
    numero = max(1, min(int(defi_numero or 1), 3))

    existe = (
        db.query(CompletionDefi)
        .filter(
            CompletionDefi.user_id == user_id,
            CompletionDefi.defi_id == defi_id,
            CompletionDefi.defi_numero == numero,
        )
        .first()
    )
    if existe:
        return existe

    completion = CompletionDefi(
        user_id=user_id,
        defi_id=defi_id,
        defi_numero=numero,
        points_gagnes=max(0, int(points_gagnes or 0)),
    )
    db.add(completion)
    db.commit()
    db.refresh(completion)
    return completion


def list_user_completions_defis(db: Session, user_id: str, limit: int = 100) -> List[CompletionDefi]:
    """Liste l'historique des défis complétés par un utilisateur."""
    n = max(1, min(int(limit or 100), 500))
    return (
        db.query(CompletionDefi)
        .filter(CompletionDefi.user_id == user_id)
        .order_by(desc(CompletionDefi.date_completion))
        .limit(n)
        .all()
    )


# ---------------------------------------------------------------------------
# CRUD - PRIX MARCHÉ
# ---------------------------------------------------------------------------

def add_prix_marche(
    db: Session,
    ingredient: str,
    prix_fcfa_kg: float,
    source: Optional[str] = None,
    region: str = "Bénin",
    date_mise_a_jour: Optional[datetime] = None,
) -> PrixMarche:
    """Ajoute une nouvelle entrée de prix marché."""
    prix = PrixMarche(
        ingredient=(ingredient or "").strip().lower(),
        prix_fcfa_kg=float(prix_fcfa_kg or 0.0),
        source=(source or "").strip() or None,
        region=(region or "Bénin").strip(),
        date_mise_a_jour=date_mise_a_jour or datetime.utcnow(),
    )
    db.add(prix)
    db.commit()
    db.refresh(prix)
    return prix


def get_latest_prix_for_ingredient(
    db: Session,
    ingredient: str,
    region: Optional[str] = None,
) -> Optional[PrixMarche]:
    """Retourne le dernier prix connu d'un ingrédient (optionnellement par région)."""
    q = db.query(PrixMarche).filter(PrixMarche.ingredient == (ingredient or "").strip().lower())
    if region:
        q = q.filter(PrixMarche.region == region.strip())
    return q.order_by(desc(PrixMarche.date_mise_a_jour)).first()


# ---------------------------------------------------------------------------
# Sérialisation (utile pour les API)
# ---------------------------------------------------------------------------

def serialize_user(user: User) -> Dict[str, Any]:
    """Transforme un User ORM en dictionnaire JSON-compatible."""
    return {
        "id": user.id,
        "telephone": user.telephone,
        "prenom": user.prenom,
        "langue_preferee": user.langue_preferee,
        "espece_principale": user.espece_principale,
        "date_inscription": user.date_inscription.isoformat() if user.date_inscription else None,
        "derniere_connexion": user.derniere_connexion.isoformat() if user.derniere_connexion else None,
        "points_total": int(user.points_total or 0),
        "niveau_actuel": int(user.niveau_actuel or 1),
        "serie_actuelle": int(user.serie_actuelle or 0),
        "meilleure_serie": int(user.meilleure_serie or 0),
        "graines_or": int(user.graines_or or 0),
        "graines_secours": int(user.graines_secours or 0),
        "abonnement": user.abonnement,
        "region": user.region,
    }


def serialize_ration(r: Ration) -> Dict[str, Any]:
    """Transforme une ration ORM en dictionnaire JSON-compatible."""
    return {
        "id": r.id,
        "user_id": r.user_id,
        "espece": r.espece,
        "stade": r.stade,
        "ingredients_saisis": _from_json_text(r.ingredients_saisis, []),
        "ration_generee": r.ration_generee,
        "composition_json": _from_json_text(r.composition_json, {}),
        "cout_fcfa_kg": float(r.cout_fcfa_kg or 0.0),
        "cout_7_jours": float(r.cout_7_jours or 0.0),
        "langue": r.langue,
        "points_gagnes": int(r.points_gagnes or 0),
        "date_creation": r.date_creation.isoformat() if r.date_creation else None,
    }


def serialize_trophee(t: TropheeUtilisateur) -> Dict[str, Any]:
    """Transforme un trophée utilisateur en dictionnaire JSON-compatible."""
    return {
        "id": t.id,
        "user_id": t.user_id,
        "trophee_code": t.trophee_code,
        "date_obtention": t.date_obtention.isoformat() if t.date_obtention else None,
    }


def serialize_defi_quotidien(d: DefiQuotidien) -> Dict[str, Any]:
    """Transforme un défi quotidien en dictionnaire JSON-compatible."""
    return {
        "id": d.id,
        "date": d.date.isoformat() if d.date else None,
        "defi_1": _from_json_text(d.defi_1, {}),
        "defi_2": _from_json_text(d.defi_2, {}),
        "defi_3": _from_json_text(d.defi_3, {}),
    }


def serialize_completion_defi(c: CompletionDefi) -> Dict[str, Any]:
    """Transforme une complétion de défi en dictionnaire JSON-compatible."""
    return {
        "id": c.id,
        "user_id": c.user_id,
        "defi_id": c.defi_id,
        "defi_numero": int(c.defi_numero or 1),
        "date_completion": c.date_completion.isoformat() if c.date_completion else None,
        "points_gagnes": int(c.points_gagnes or 0),
    }


def serialize_prix_marche(p: PrixMarche) -> Dict[str, Any]:
    """Transforme un prix marché en dictionnaire JSON-compatible."""
    return {
        "id": p.id,
        "ingredient": p.ingredient,
        "prix_fcfa_kg": float(p.prix_fcfa_kg or 0.0),
        "date_mise_a_jour": p.date_mise_a_jour.isoformat() if p.date_mise_a_jour else None,
        "source": p.source,
        "region": p.region,
    }


__all__ = [
    "Base",
    "engine",
    "SessionLocal",
    "DATABASE_URL",
    "User",
    "Ration",
    "TropheeUtilisateur",
    "DefiQuotidien",
    "CompletionDefi",
    "PrixMarche",
    "OtpCode",
    "UserActionLog",
    "init_db",
    "get_db",
    "create_user",
    "get_user_by_id",
    "get_user_by_telephone",
    "upsert_otp_code",
    "get_otp_by_telephone",
    "verify_otp_code",
    "clear_otp_by_telephone",
    "update_user_last_login",
    "add_points_to_user",
    "update_user_streak",
    "list_top_users_by_points",
    "log_user_action",
    "get_last_action_at",
    "count_user_actions_last_24h",
    "get_user_action_counts",
    "create_ration",
    "list_user_rations",
    "create_trophee_for_user",
    "list_user_trophees",
    "create_or_update_defi_quotidien",
    "get_defi_quotidien_by_date",
    "complete_defi",
    "list_user_completions_defis",
    "add_prix_marche",
    "get_latest_prix_for_ingredient",
    "serialize_user",
    "serialize_ration",
    "serialize_trophee",
    "serialize_defi_quotidien",
    "serialize_completion_defi",
    "serialize_prix_marche",
]
