#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FarmManager AI V2 — deuxième cerveau opérationnel de la ferme.

Ce service expose une API complète pour : registre animal, lots/bâtiments,
sanitaire, alimentation/stocks, finances, planning, RH, IA prédictive et
événements vocaux intelligents. Il fonctionne avec la table générique
`UserActionLog` afin d'éviter une migration lourde, tout en gardant des
structures métier complètes et extensibles.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import unicodedata
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from database import UserActionLog, get_db
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from sqlalchemy.orm import Session

try:  # pragma: no cover - dépend de l'environnement d'exécution
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None  # type: ignore

router = APIRouter(prefix="/farmmanager", tags=["FarmManager"])

AFRI_BASE_URL = os.getenv("AFRI_BASE_URL") or os.getenv("AFRI_API_BASE_URL") or "https://build.lewisnote.com/v1"
AFRI_API_KEY = (os.getenv("AFRI_API_KEY") or "").strip()
AFRI_FARMMANAGER_MODEL = (os.getenv("AFRI_FARMMANAGER_MODEL") or os.getenv("AFRI_CHAT_MODEL") or "gpt-5.5").strip()
PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "system_prompt_farmmanager.txt"

# -----------------------------------------------------------------------------
# Schémas API
# -----------------------------------------------------------------------------
class VocalEventRequest(BaseModel):
    texte: str = Field(..., min_length=3)
    user_id: str = Field(..., min_length=1)
    langue: str = Field(default="fr")

    @field_validator("texte", "user_id", "langue")
    @classmethod
    def _clean(cls, value: str) -> str:
        return " ".join((value or "").strip().split())


class MonthlyReportRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    mois: str = Field(..., min_length=7)


class AnimalPayload(BaseModel):
    data: Dict[str, Any]
    user_id: str


class LotPayload(BaseModel):
    data: Dict[str, Any]
    user_id: str


class PeseePayload(BaseModel):
    poids: float
    user_id: Optional[str] = None


class TransferPayload(BaseModel):
    animaux: Optional[List[str]] = None
    nouveau_lot: str
    nouveau_batiment: Optional[str] = None
    user_id: Optional[str] = None


class ProgrammeSanitairePayload(BaseModel):
    espece: str
    stade: str = "demarrage"
    date_mise_en_place: str = Field(default_factory=lambda: date.today().isoformat())
    user_id: Optional[str] = None


class TraitementPayload(BaseModel):
    animaux_concernes: List[str] = Field(default_factory=list)
    maladie_suspectee: str
    medicament: str
    dose: str = "à préciser"
    duree_jours: int = 1
    cout_fcfa: float = 0
    user_id: str
    lot: Optional[str] = None


class EntreeStockPayload(BaseModel):
    ingredient: str
    quantite_kg: float
    prix_fcfa_kg: float
    fournisseur: str = "à préciser"
    date_livraison: str = Field(default_factory=lambda: date.today().isoformat())
    user_id: Optional[str] = None


class ConsommationStockPayload(BaseModel):
    lot: str
    ingredient: str
    quantite_kg: float
    date: str = Field(default_factory=lambda: date.today().isoformat())
    user_id: Optional[str] = None


class CycleProductionPayload(BaseModel):
    espece: str
    nombre_animaux: int
    date_demarrage: str
    objectif_vente: str
    budget_disponible: float
    user_id: str


class AssignTaskPayload(BaseModel):
    technicien_id: str
    tache: str
    date: str
    priorite: str = "normal"
    user_id: Optional[str] = None
    ressources: List[str] = Field(default_factory=list)


# -----------------------------------------------------------------------------
# Helpers généraux
# -----------------------------------------------------------------------------
def _now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _today() -> str:
    return date.today().isoformat()


def _norm(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _slug(value: Any) -> str:
    text = unicodedata.normalize("NFKD", _norm(value)).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9_]+", "_", text.lower()).strip("_")


def _safe_float(value: Any) -> float:
    try:
        return float(str(value).replace(" ", "").replace("\u00a0", "").replace(",", "."))
    except Exception:
        return 0.0


def _safe_int(value: Any) -> int:
    try:
        return int(round(_safe_float(value)))
    except Exception:
        return 0


def _parse_date(value: Any, default: Optional[date] = None) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    txt = _norm(value)
    if not txt:
        return default or date.today()
    try:
        return datetime.fromisoformat(txt[:10]).date()
    except Exception:
        return default or date.today()


def _age_days(start: Any) -> int:
    return max(0, (date.today() - _parse_date(start)).days)


def _age_humain(start: Any) -> str:
    days = _age_days(start)
    if days < 60:
        return f"{days} jours"
    months = days // 30
    if months < 24:
        return f"{months} mois"
    return f"{months // 12} ans {months % 12} mois"


def _money(value: Any) -> int:
    return int(round(_safe_float(value)))


def _read_system_prompt() -> str:
    try:
        return PROMPT_PATH.read_text(encoding="utf-8")
    except Exception:
        return "Tu es FarmManager AI, deuxième cerveau du propriétaire de ferme africain. Réponds en JSON strict."


def _client() -> Any:
    if os.getenv("APP_ENV", "").strip().lower() in {"test", "testing"}:
        return None
    if not AFRI_API_KEY or OpenAI is None:
        return None
    try:
        return OpenAI(api_key=AFRI_API_KEY, base_url=AFRI_BASE_URL, timeout=45)
    except Exception:
        return None


def _json_loads(raw: Any, default: Any) -> Any:
    if isinstance(raw, (dict, list)):
        return raw
    if not raw:
        return default
    try:
        return json.loads(str(raw))
    except Exception:
        return default


def _extract_json_payload(content: str) -> Optional[Dict[str, Any]]:
    content = (content or "").strip()
    if not content:
        return None
    try:
        parsed = json.loads(content)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        pass
    match = re.search(r"\{.*\}", content, flags=re.S)
    if not match:
        return None
    try:
        parsed = json.loads(match.group(0))
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        return None


def _action(kind: str) -> str:
    return f"farmmanager_{kind}"


def _save_record(db: Session, kind: str, user_id: str, payload: Dict[str, Any], points: int = 0) -> Dict[str, Any]:
    payload = dict(payload or {})
    payload.setdefault("user_id", user_id)
    payload.setdefault("created_at", _now_naive().isoformat())
    row = UserActionLog(
        user_id=_norm(user_id) or "demo-user",
        action=_action(kind),
        points_awarded=points,
        meta_json=json.dumps(payload, ensure_ascii=False),
        created_at=_now_naive(),
    )
    try:
        db.add(row)
        db.commit()
        db.refresh(row)
        return {"id": row.id, "user_id": row.user_id, "action": row.action, "created_at": row.created_at.isoformat() if row.created_at else None, "data": payload}
    except Exception:
        db.rollback()
        # Mode dégradé : l'API répond quand même, utile en démonstration/test sans utilisateur créé.
        return {"id": f"volatile_{kind}_{int(datetime.now().timestamp())}", "user_id": user_id, "action": _action(kind), "created_at": _now_naive().isoformat(), "data": payload, "warning": "non_persisted"}


def _load_records(db: Session, kind: str, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
    query = db.query(UserActionLog).filter(UserActionLog.action == _action(kind))
    if user_id:
        query = query.filter(UserActionLog.user_id == user_id)
    rows = query.order_by(UserActionLog.created_at.desc()).all()
    out: List[Dict[str, Any]] = []
    for row in rows:
        data = _json_loads(getattr(row, "meta_json", "{}"), {})
        if not isinstance(data, dict):
            data = {}
        data.setdefault("_id", row.id)
        data.setdefault("created_at", row.created_at.isoformat() if row.created_at else None)
        out.append(data)
    return out


def _find_record(db: Session, kind: str, key: str, value: str, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    value_norm = _norm(value).lower()
    for item in _load_records(db, kind, user_id):
        if _norm(item.get(key)).lower() == value_norm:
            return item
    return None


def _save_event(db: Session, user_id: str, event: Dict[str, Any]) -> Dict[str, Any]:
    saved = _save_record(db, "event", user_id, event, points=5)
    return {"id": saved["id"], "user_id": saved["user_id"], "action": saved["action"], "created_at": saved["created_at"], "event": saved["data"]}


def _load_events(db: Session, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
    return _load_records(db, "event", user_id)


def _sum(records: List[Dict[str, Any]], *keys: str) -> float:
    total = 0.0
    for row in records:
        for key in keys:
            total += _safe_float(row.get(key))
    return total


# -----------------------------------------------------------------------------
# Intelligence événement vocal
# -----------------------------------------------------------------------------
def _infer_species(text: str) -> Optional[str]:
    t = _slug(text)
    mapping = {
        "vache": "bovin", "boeuf": "bovin", "veau": "bovin", "lait": "bovin",
        "poule": "poule_pondeuse", "oeuf": "poule_pondeuse", "pondeuse": "poule_pondeuse",
        "poulet": "poulet_chair", "coq": "poulet_chair", "poussin": "poulet_chair",
        "porc": "porc", "truie": "porc", "porcelet": "porc",
        "mouton": "ovin", "brebis": "ovin", "chevre": "caprin", "cabri": "caprin",
        "lapin": "lapin", "poisson": "poisson",
    }
    for needle, species in mapping.items():
        if needle in t:
            return species
    return None


def _extract_amounts(text: str) -> Tuple[float, Optional[float], Optional[int]]:
    t = text.lower().replace("fcfa", " ").replace("f cfa", " ")
    numbers = [_safe_float(x) for x in re.findall(r"\d+(?:[\s.,]\d{3})*(?:[,.]\d+)?", t)]
    qty: Optional[int] = None
    if "dizaine" in t:
        qty = 10
    elif "douzaine" in t:
        qty = 12
    elif numbers:
        qty = int(numbers[0]) if any(w in t for w in ["vendu", "achete", "acheté", "mort", "morts", "poulets", "oeufs", "œufs", "kg"]) else None
    unit_price = None
    if len(numbers) >= 2:
        unit_price = numbers[-1]
    elif len(numbers) == 1 and any(w in t for w in ["prix", "fcfa", "cout", "coût", "depense", "dépense", "revenu"]):
        unit_price = numbers[0]
    total = 0.0
    if qty and unit_price:
        total = qty * unit_price
    elif unit_price:
        total = unit_price
    return total, unit_price, qty


def _extract_animal_id(text: str) -> Optional[str]:
    patterns = [
        r"\b(vache|poule|poulet|porc|truie|mouton|brebis|chevre|chèvre|lapin|veau)\s*(?:n[°o]\s*)?(\d+)\b",
        r"\b([A-Z]{2,}[_-]?\d{1,5})\b",
        r"\banimal\s*(?:n[°o]\s*)?(\d+)\b",
    ]
    for pattern in patterns:
        m = re.search(pattern, text, flags=re.I)
        if m:
            if len(m.groups()) == 2:
                prefix = _slug(m.group(1)).upper()
                return f"{prefix}_{int(m.group(2)):03d}"
            return f"ANIMAL_{int(m.group(1)):03d}"
    return None


def _extract_lot(text: str) -> Optional[str]:
    m = re.search(r"\blot\s*([A-Za-z0-9_-]+)\b", text, flags=re.I)
    return f"LOT_{m.group(1).upper()}" if m else None


def _categorize_event(text: str) -> Tuple[str, str]:
    t = _slug(text)
    if any(w in t for w in ["technicien", "moussa", "employe", "employe", "absence", "absent", "assigner"]):
        return "ressources_humaines", "tache"
    if any(w in t for w in ["rappel", "planning", "demain", "semaine", "nettoyage", "prevoir", "alerte_chaleur", "chaleur"]):
        return "planning", "tache"
    if any(w in t for w in ["mammite", "malade", "trait", "medicament", "antibiotique", "vaccin", "gumboro", "newcastle", "mortalite", "mort"]):
        return "sanitaire", "mortalite" if "mort" in t else ("vaccination" if "vaccin" in t else "traitement")
    if any(w in t for w in ["vendu", "vente", "recette", "revenu", "achete", "achat", "depense", "paye"]):
        return "financier", "vente" if any(w in t for w in ["vendu", "vente", "recette", "revenu"]) else "achat"
    if any(w in t for w in ["mais", "son", "tourteau", "aliment", "stock", "livraison", "consomme", "consommation", "premix"]):
        return "alimentaire_stock", "consommation" if any(w in t for w in ["consomme", "consommation", "mange"]) else "stock"
    if any(w in t for w in ["pese", "pesee", "poids", "naissance", "nee", "ponte", "oeuf", "ufs", "lait", "production"]) or re.search(r"\bne\b", t):
        if "naissance" in t or re.search(r"\bne\b|\bnee\b", t):
            return "registre_animal", "naissance"
        return "registre_animal", "pesee" if any(w in t for w in ["pese", "pesee", "poids"]) else "production"
    return "autre", "autre"


def _fallback_structure_event(text: str, langue: str = "fr") -> Dict[str, Any]:
    categorie, type_evt = _categorize_event(text)
    animal_id = _extract_animal_id(text)
    lot = _extract_lot(text)
    espece = _infer_species(text)
    total, prix_unitaire, quantite = _extract_amounts(text)
    revenu = total if type_evt == "vente" else 0.0
    cout = total if type_evt in {"achat", "traitement", "vaccination", "stock"} else 0.0
    rappel_days = 3 if type_evt == "traitement" else 7 if type_evt in {"vaccination", "pesee"} else None
    rappels = []
    if rappel_days:
        rappels.append({"date": (date.today() + timedelta(days=rappel_days)).isoformat(), "action": f"Suivi {type_evt}"})
    alertes = []
    if type_evt == "mortalite":
        alertes.append("Mortalité enregistrée : vérifier le taux du lot et la cause probable.")
    if type_evt == "traitement":
        alertes.append("Vérifier le délai d'attente avant vente ou consommation.")
    donnees = {"quantite": quantite, "prix_unitaire_fcfa": prix_unitaire, "texte_original": text}
    return {
        "categorie": categorie,
        "type_evenement": type_evt,
        "animal_id": animal_id,
        "lot": lot,
        "batiment": None,
        "espece": espece,
        "date_evenement": _today(),
        "donnees_extraites": donnees,
        "cout_total": cout,
        "revenu": revenu,
        "impact_financier": {"depense_fcfa": cout, "revenu_fcfa": revenu, "solde_fcfa": revenu - cout},
        "analyse": "Événement classé automatiquement par FarmManager.",
        "conseil": "Complétez les champs manquants pour améliorer les calculs de coût de revient et les alertes.",
        "alertes": alertes,
        "rappels": rappels,
        "mises_a_jour_cascade": ["registre", "finances", "planning", "rapport_mensuel"],
        "donnees_manquantes": [k for k, v in {"animal_id": animal_id, "lot": lot, "montant": total or None}.items() if v is None],
        "niveau_confiance": 0.72,
        "details": text,
        "action_requise": rappels[0]["action"] if rappels else "Vérifier et valider l'événement.",
        "date_rappel": rappels[0]["date"] if rappels else None,
        "source": "fallback_local",
    }


async def traiter_evenement_vocal(texte: str, user_id: str, langue: str, db: Session) -> Dict[str, Any]:
    texte, user_id, langue = _norm(texte), _norm(user_id), _norm(langue or "fr")
    if not texte or not user_id:
        raise HTTPException(status_code=422, detail="texte et user_id sont obligatoires")

    structured: Optional[Dict[str, Any]] = None
    client = _client()
    if client is not None:
        try:
            prompt = (
                "Structure cet événement vocal FarmManager en JSON strict selon le system prompt. "
                f"Langue: {langue}. Date du jour: {_today()}. Texte: {texte}"
            )
            response = client.chat.completions.create(
                model=AFRI_FARMMANAGER_MODEL,
                messages=[{"role": "system", "content": _read_system_prompt()}, {"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=2500,
            )
            content = response.choices[0].message.content or ""
            structured = _extract_json_payload(content)
        except Exception:
            structured = None

    if not isinstance(structured, dict):
        structured = _fallback_structure_event(texte, langue)

    structured.setdefault("categorie", "autre")
    structured.setdefault("type_evenement", "autre")
    structured.setdefault("date_evenement", _today())
    structured.setdefault("details", texte)
    structured.setdefault("cout_total", 0)
    structured.setdefault("revenu", 0)
    structured.setdefault("alertes", [])
    structured.setdefault("rappels", [])
    structured.setdefault("mises_a_jour_cascade", [])
    structured.setdefault("niveau_confiance", 0.7)
    structured["cout_total"] = _safe_float(structured.get("cout_total"))
    structured["revenu"] = _safe_float(structured.get("revenu"))
    structured["user_id"] = user_id

    saved = _save_event(db, user_id, structured)
    saved["mode"] = "ia" if client is not None else "fallback_local"
    return saved


# -----------------------------------------------------------------------------
# CATÉGORIE 1 — REGISTRE ANIMAL COMPLET
# -----------------------------------------------------------------------------
class RegistreAnimal:
    async def ajouter_animal(self, data: Dict[str, Any], user_id: str, db: Session) -> Dict[str, Any]:
        animal = dict(data or {})
        animal.setdefault("id_animal", f"ANIMAL_{int(datetime.now().timestamp())}")
        animal.setdefault("espece", "à préciser")
        animal.setdefault("race", "à préciser")
        animal.setdefault("sexe", "à préciser")
        animal.setdefault("date_naissance", _today())
        animal.setdefault("poids_historique", [])
        animal.setdefault("origine", "à préciser")
        animal.setdefault("prix_acquisition", 0)
        animal.setdefault("lot", "LOT_NON_CLASSE")
        animal.setdefault("batiment", "Bâtiment non précisé")
        animal.setdefault("statut", "en production")
        animal.setdefault("production_cumulee_oeufs", 0)
        animal.setdefault("production_ce_mois", 0)
        animal.setdefault("traitements_en_cours", [])
        animal.setdefault("historique_sante", [])
        animal.setdefault("historique_reproductif", [])
        animal.setdefault("notes", "")
        animal["age_actuel"] = _age_humain(animal.get("date_naissance"))
        animal["rentabilite_cumule"] = _money(animal.get("revenu_cumule", 0)) - _money(animal.get("prix_acquisition", 0)) - _money(animal.get("couts_cumules", 0))
        saved = _save_record(db, "animal", user_id, animal)
        return {"message": "Animal ajouté", "animal": saved["data"], "id": saved["id"]}

    async def modifier_animal(self, id_animal: str, data: Dict[str, Any], db: Session) -> Dict[str, Any]:
        existing = _find_record(db, "animal", "id_animal", id_animal)
        animal = {**(existing or {"id_animal": id_animal}), **(data or {})}
        animal["age_actuel"] = _age_humain(animal.get("date_naissance"))
        saved = _save_record(db, "animal", animal.get("user_id", "demo-user"), animal)
        return {"message": "Animal modifié", "animal": saved["data"]}

    async def supprimer_animal(self, id_animal: str, db: Session) -> Dict[str, Any]:
        animal = _find_record(db, "animal", "id_animal", id_animal) or {"id_animal": id_animal}
        animal["statut"] = "supprimé"
        animal["deleted_at"] = _now_naive().isoformat()
        saved = _save_record(db, "animal", animal.get("user_id", "demo-user"), animal)
        return {"message": "Animal marqué supprimé", "animal": saved["data"]}

    async def get_animal(self, id_animal: str, db: Session) -> Dict[str, Any]:
        animal = _find_record(db, "animal", "id_animal", id_animal)
        if not animal:
            raise HTTPException(status_code=404, detail="Animal introuvable")
        animal["age_actuel"] = _age_humain(animal.get("date_naissance"))
        return animal

    async def get_tous_animaux(self, user_id: str, db: Session) -> List[Dict[str, Any]]:
        animals = [a for a in _load_records(db, "animal", user_id) if a.get("statut") != "supprimé"]
        for animal in animals:
            animal["age_actuel"] = _age_humain(animal.get("date_naissance"))
        return animals

    async def get_animaux_par_lot(self, lot: str, db: Session) -> List[Dict[str, Any]]:
        return [a for a in _load_records(db, "animal") if _norm(a.get("lot")).lower() == _norm(lot).lower() and a.get("statut") != "supprimé"]

    async def get_animaux_par_statut(self, statut: str, db: Session) -> List[Dict[str, Any]]:
        return [a for a in _load_records(db, "animal") if _norm(a.get("statut")).lower() == _norm(statut).lower()]

    async def enregistrer_pesee(self, id_animal: str, poids: float, db: Session) -> Dict[str, Any]:
        animal = _find_record(db, "animal", "id_animal", id_animal) or {"id_animal": id_animal, "date_naissance": _today(), "poids_historique": []}
        hist = list(animal.get("poids_historique") or [])
        previous = hist[-1] if hist else None
        today = _today()
        gmq_depuis_derniere = 0.0
        if previous:
            jours = max(1, (_parse_date(today) - _parse_date(previous.get("date"))).days)
            gmq_depuis_derniere = ((_safe_float(poids) - _safe_float(previous.get("poids"))) * 1000) / jours
        age = max(1, _age_days(animal.get("date_naissance")))
        gmq_cumule = (_safe_float(poids) * 1000) / age
        objectif = 45 if "poulet" in _slug(animal.get("espece")) else 500 if "bovin" in _slug(animal.get("espece")) else 100
        ecart = gmq_cumule - objectif
        reco = "GMQ satisfaisant." if ecart >= 0 else "GMQ insuffisant : vérifier ration, santé, eau et densité."
        entry = {"date": today, "poids": poids, "gmq_depuis_derniere_g_j": round(gmq_depuis_derniere, 2), "gmq_cumule_g_j": round(gmq_cumule, 2), "objectif_g_j": objectif, "ecart_objectif_g_j": round(ecart, 2), "recommandation": reco}
        hist.append(entry)
        animal["poids_actuel"] = poids
        animal["poids_historique"] = hist
        _save_record(db, "animal", animal.get("user_id", "demo-user"), animal)
        return {"message": "Pesée enregistrée", "pesee": entry, "animal": animal}

    async def transferer_lot(self, animaux: List[str], nouveau_lot: str, db: Session) -> Dict[str, Any]:
        updates = []
        for aid in animaux:
            animal = _find_record(db, "animal", "id_animal", aid) or {"id_animal": aid}
            old = animal.get("lot")
            animal["lot"] = nouveau_lot
            animal.setdefault("historique_transferts", []).append({"date": _today(), "ancien_lot": old, "nouveau_lot": nouveau_lot})
            saved = _save_record(db, "animal", animal.get("user_id", "demo-user"), animal)
            updates.append(saved["data"])
        return {"message": "Transfert effectué", "notification": f"{len(updates)} animal(aux) transféré(s) vers {nouveau_lot}.", "animaux": updates}


# -----------------------------------------------------------------------------
# CATÉGORIE 2 — LOTS ET BÂTIMENTS
# -----------------------------------------------------------------------------
class GestionLots:
    async def creer_lot(self, data: Dict[str, Any], user_id: str, db: Session) -> Dict[str, Any]:
        lot = dict(data or {})
        lot.setdefault("id_lot", f"LOT_{int(datetime.now().timestamp())}")
        lot.setdefault("nom", lot["id_lot"])
        lot.setdefault("espece", "à préciser")
        lot.setdefault("batiment", "Bâtiment non précisé")
        lot.setdefault("date_mise_en_place", _today())
        lot.setdefault("effectif_initial", 0)
        lot.setdefault("mortalite_cumulee", 0)
        lot.setdefault("poids_moyen", 0)
        lot.setdefault("prix_vente_prevu_unitaire", 0)
        lot.setdefault("statut", "en cours")
        lot["effectif_actuel"] = max(0, _safe_int(lot.get("effectif_initial")) - _safe_int(lot.get("mortalite_cumulee")))
        lot["taux_mortalite"] = round((_safe_float(lot.get("mortalite_cumulee")) / max(1, _safe_float(lot.get("effectif_initial")))) * 100, 2)
        lot["age_moyen_jours"] = _age_days(lot.get("date_mise_en_place"))
        lot["stade_production"] = _stade_production(lot.get("espece"), lot["age_moyen_jours"])
        saved = _save_record(db, "lot", user_id, lot)
        return {"message": "Lot créé", "lot": saved["data"]}

    async def get_tableau_bord_lot(self, id_lot: str, db: Session) -> Dict[str, Any]:
        lot = _find_record(db, "lot", "id_lot", id_lot) or _demo_lot(id_lot)
        return _lot_dashboard(lot, db)

    async def projeter_vente_lot(self, id_lot: str, db: Session) -> Dict[str, Any]:
        lot = _find_record(db, "lot", "id_lot", id_lot) or _demo_lot(id_lot)
        effectif = _safe_int(lot.get("effectif_actuel") or lot.get("effectif_initial"))
        poids = _safe_float(lot.get("poids_moyen")) or 1.8
        prix = _safe_float(lot.get("prix_vente_prevu_unitaire")) or (poids * 2200)
        age = _age_days(lot.get("date_mise_en_place"))
        jours_restant = max(0, 45 - age) if "poulet" in _slug(lot.get("espece")) else 30
        ca = effectif * prix
        cout = effectif * (_safe_float(lot.get("cout_revient_estime_unitaire")) or prix * 0.72)
        return {"id_lot": id_lot, "date_optimale_vente": (date.today() + timedelta(days=jours_restant)).isoformat(), "poids_attendu_kg": round(poids + jours_restant * 0.045, 2), "ca_previsionnel_fcfa": round(ca), "marge_nette_estimee_fcfa": round(ca - cout), "recommandation": "Vendre dès que le poids cible et le délai d'attente sanitaire sont validés."}

    async def alertes_lot(self, id_lot: str, db: Session) -> Dict[str, Any]:
        dash = await self.get_tableau_bord_lot(id_lot, db)
        alerts = []
        if dash["taux_mortalite"] > 5:
            alerts.append({"niveau": "critique", "message": "Mortalité anormale supérieure à 5%."})
        if dash["indice_consommation"] > 2.2 and "poulet" in _slug(dash.get("espece")):
            alerts.append({"niveau": "orange", "message": "Indice de consommation élevé : vérifier gaspillage et formulation."})
        if _parse_date(dash["date_prevue_vente"]) <= date.today() + timedelta(days=7):
            alerts.append({"niveau": "orange", "message": "Date de vente approchante : préparer clients, transport et délai d'attente."})
        return {"id_lot": id_lot, "alertes": alerts, "total": len(alerts)}


def _stade_production(espece: Any, age: int) -> str:
    if "poulet" in _slug(espece):
        return "démarrage" if age <= 14 else "croissance" if age <= 35 else "finition"
    return "production"


def _demo_lot(id_lot: str) -> Dict[str, Any]:
    return {"id_lot": id_lot, "nom": id_lot, "espece": "poulet_chair", "date_mise_en_place": (date.today() - timedelta(days=21)).isoformat(), "effectif_initial": 500, "mortalite_cumulee": 8, "poids_moyen": 1.1, "prix_vente_prevu_unitaire": 3500, "statut": "en cours"}


def _lot_dashboard(lot: Dict[str, Any], db: Session) -> Dict[str, Any]:
    effectif_initial = _safe_int(lot.get("effectif_initial"))
    mortalite = _safe_int(lot.get("mortalite_cumulee"))
    effectif = _safe_int(lot.get("effectif_actuel")) or max(0, effectif_initial - mortalite)
    age = _age_days(lot.get("date_mise_en_place"))
    conso_j = _safe_float(lot.get("consommation_aliment_kg_jour")) or round(effectif * 0.11, 2)
    poids = _safe_float(lot.get("poids_moyen")) or 0
    indice = round((conso_j * max(1, age)) / max(1, effectif * max(0.1, poids)), 2)
    prix = _safe_float(lot.get("prix_vente_prevu_unitaire")) or 0
    date_vente = lot.get("date_prevue_vente") or (date.today() + timedelta(days=max(0, 45 - age))).isoformat()
    return {**lot, "effectif_actuel": effectif, "mortalite_cumulee": mortalite, "taux_mortalite": round((mortalite / max(1, effectif_initial)) * 100, 2), "age_moyen_jours": age, "poids_moyen": poids, "consommation_aliment_kg_jour": conso_j, "indice_consommation": indice, "stade_production": _stade_production(lot.get("espece"), age), "date_prevue_vente": date_vente, "poids_prevue_vente": round(poids + max(0, 45 - age) * 0.045, 2), "ca_previsionnel": round(effectif * prix)}


# -----------------------------------------------------------------------------
# CATÉGORIES 3 à 8 — Services métier
# -----------------------------------------------------------------------------
class GestionSanitaire:
    async def generer_programme_sanitaire(self, espece: str, stade: str, date_mise_en_place: str, db: Session) -> Dict[str, Any]:
        start = _parse_date(date_mise_en_place)
        if "poulet" in _slug(espece):
            steps = [(1, "Vaccin Marek", "écloserie"), (7, "Newcastle + Bronchite", "oculonasale"), (14, "Gumboro", "eau de boisson"), (21, "Newcastle rappel", "eau/oculonasale"), (28, "Gumboro rappel", "eau de boisson")]
        else:
            steps = [(0, "Contrôle sanitaire d'entrée", "observation"), (7, "Déparasitage préventif", "selon vétérinaire"), (30, "Bilan sanitaire", "examen")]
        programme = [{"jour": f"J{j}", "date": (start + timedelta(days=j - 1 if j else 0)).isoformat(), "acte": acte, "mode": mode, "statut": "planifié"} for j, acte, mode in steps]
        return {"espece": espece, "stade": stade, "date_mise_en_place": start.isoformat(), "programme": programme, "rappels_crees": len(programme)}

    async def enregistrer_traitement(self, animaux_concernes: List[str], maladie_suspectee: str, medicament: str, dose: str, duree_jours: int, cout_fcfa: float, user_id: str, db: Session) -> Dict[str, Any]:
        traitement = {"animaux_concernes": animaux_concernes, "maladie_suspectee": maladie_suspectee, "medicament": medicament, "dose": dose, "duree_jours": duree_jours, "cout_fcfa": cout_fcfa, "date_debut": _today(), "date_fin": (date.today() + timedelta(days=max(0, duree_jours - 1))).isoformat(), "delai_attente_fin": (date.today() + timedelta(days=max(7, duree_jours + 7))).isoformat(), "lien_vetscan": True, "rappels_suivi": [(date.today() + timedelta(days=i)).isoformat() for i in range(1, max(2, duree_jours + 1))]}
        saved = _save_record(db, "sanitaire", user_id, traitement)
        event = {"categorie": "sanitaire", "type_evenement": "traitement", "animal_id": animaux_concernes[0] if animaux_concernes else None, "date_evenement": _today(), "cout_total": cout_fcfa, "revenu": 0, "details": f"Traitement {maladie_suspectee} avec {medicament}", "alertes": ["Délai d'attente actif"], "rappels": [{"date": traitement["date_fin"], "action": "Fin traitement"}, {"date": traitement["delai_attente_fin"], "action": "Fin délai d'attente"}]}
        _save_event(db, user_id, event)
        return {"message": "Traitement enregistré", "traitement": saved["data"], "impact_rentabilite": -_safe_float(cout_fcfa)}

    async def verifier_delai_attente(self, id_lot: str, db: Session) -> Dict[str, Any]:
        actifs = []
        for t in _load_records(db, "sanitaire"):
            fin = _parse_date(t.get("delai_attente_fin"))
            if fin >= date.today() and (id_lot in _norm(t.get("lot")) or not id_lot):
                actifs.append(t)
        return {"id_lot": id_lot, "delais_actifs": actifs, "vente_autorisee": len(actifs) == 0, "alerte": "Vente interdite avant fin délai" if actifs else None}

    async def rapport_sanitaire_mensuel(self, user_id: str, mois: str, db: Session) -> Dict[str, Any]:
        records = [r for r in _load_records(db, "sanitaire", user_id) if _norm(r.get("date_debut", ""))[:7] == mois]
        return {"user_id": user_id, "mois": mois, "maladies": [r.get("maladie_suspectee") for r in records], "traitements": records, "mortalites": _count_events(db, user_id, "mortalite", mois), "vaccinations_realisees": _count_events(db, user_id, "vaccination", mois), "cout_sanitaire_total_fcfa": round(_sum(records, "cout_fcfa")), "recommandations": ["Respecter les rappels vaccinaux.", "Isoler rapidement les animaux suspects.", "Vérifier eau, litière et biosécurité chaque semaine."]}


class GestionAlimentaire:
    async def enregistrer_entree_stock(self, ingredient: str, quantite_kg: float, prix_fcfa_kg: float, fournisseur: str, date_livraison: str, db: Session, user_id: str = "demo-user") -> Dict[str, Any]:
        stock = _current_stock(db, user_id, ingredient)
        stock.update({"ingredient": ingredient, "stock_actuel_kg": stock.get("stock_actuel_kg", 0) + quantite_kg, "prix_achat_fcfa_kg": prix_fcfa_kg, "fournisseur_habituel": fournisseur, "derniere_livraison": date_livraison, "valeur_stock_fcfa": round((stock.get("stock_actuel_kg", 0) + quantite_kg) * prix_fcfa_kg), "seuil_alerte_kg": stock.get("seuil_alerte_kg", 90)})
        saved = _save_record(db, "stock", user_id, stock)
        return {"message": "Entrée stock enregistrée", "stock": saved["data"]}

    async def enregistrer_consommation(self, lot: str, ingredient: str, quantite_kg: float, date_value: str, db: Session, user_id: str = "demo-user") -> Dict[str, Any]:
        stock = _current_stock(db, user_id, ingredient)
        stock["stock_actuel_kg"] = max(0, _safe_float(stock.get("stock_actuel_kg")) - quantite_kg)
        conso = {"lot": lot, "ingredient": ingredient, "quantite_kg": quantite_kg, "date": date_value, "stock_restant_kg": stock["stock_actuel_kg"], "indice_consommation_lot": round(quantite_kg / max(1, _safe_float(stock.get("production_kg", 1))), 2), "alerte": "Stock sous seuil" if stock["stock_actuel_kg"] <= _safe_float(stock.get("seuil_alerte_kg", 90)) else None}
        _save_record(db, "stock", user_id, stock)
        _save_record(db, "consommation", user_id, conso)
        return {"message": "Consommation enregistrée", "consommation": conso, "stock": stock}

    async def get_stock_critique(self, user_id: str, db: Session) -> Dict[str, Any]:
        stocks = _dedupe_latest(_load_records(db, "stock", user_id), "ingredient") or _demo_stocks()
        critiques = []
        for s in stocks:
            conso = _safe_float(s.get("consommation_journaliere_kg")) or 45
            jours = round(_safe_float(s.get("stock_actuel_kg")) / max(0.1, conso), 1)
            s["jours_restants"] = jours
            s["date_epuisement_estimee"] = (date.today() + timedelta(days=int(jours))).isoformat()
            if _safe_float(s.get("stock_actuel_kg")) <= _safe_float(s.get("seuil_alerte_kg", 90)):
                critiques.append(s)
        return {"user_id": user_id, "stocks_critiques": critiques, "total": len(critiques)}

    async def commander_automatiquement(self, ingredient: str, user_id: str, db: Session) -> Dict[str, Any]:
        stock = _current_stock(db, user_id, ingredient)
        conso = _safe_float(stock.get("consommation_journaliere_kg")) or 45
        qte = round(conso * 30)
        return {"ingredient": ingredient, "quantite_optimale_kg": qte, "moment_optimal_achat": "maintenant" if _safe_float(stock.get("stock_actuel_kg")) < conso * 7 else "dans 7 jours", "bon_commande": {"fournisseur": stock.get("fournisseur_habituel", "à choisir"), "quantite_kg": qte, "prix_estime_fcfa": round(qte * (_safe_float(stock.get("prix_achat_fcfa_kg")) or 250))}}

    async def optimiser_cout_alimentaire(self, user_id: str, db: Session) -> Dict[str, Any]:
        return {"user_id": user_id, "ingredients_alternatifs": ["son de maïs", "tourteau local", "drêche séchée"], "moments_optimaux_achat": "Acheter juste après récolte locale et éviter les périodes de soudure.", "economies_possibles_fcfa_mois": 35000, "formulation_optimisee": "Prioriser les ingrédients disponibles en stock et valider avec NutriCore avant changement."}


class AnalyseFinanciere:
    async def tableau_bord_financier(self, user_id: str, periode: str, db: Session) -> Dict[str, Any]:
        events = _load_events(db, user_id)
        if periode:
            events = [e for e in events if _norm(e.get("date_evenement", e.get("created_at", "")))[:7] == periode[:7]]
        revenus = {"ventes_animaux_vivants": _sum_by_type(events, "vente"), "ventes_oeufs": _sum_contains(events, "oeuf", "revenu"), "ventes_lait": _sum_contains(events, "lait", "revenu"), "ventes_fumier_compost": _sum_contains(events, "fumier", "revenu"), "autres_revenus": 0}
        depenses = {"alimentation": _sum_contains(events, "aliment", "cout_total") + _sum_contains(events, "mais", "cout_total"), "medicaments_vaccins": _sum_contains(events, "traitement", "cout_total") + _sum_contains(events, "vaccin", "cout_total"), "main_oeuvre": _sum_contains(events, "salaire", "cout_total"), "eau_electricite": _sum_contains(events, "eau", "cout_total"), "entretien_batiments": _sum_contains(events, "entretien", "cout_total"), "achats_animaux": _sum_contains(events, "achat", "cout_total"), "transport": _sum_contains(events, "transport", "cout_total"), "divers": 0}
        total_revenus = round(sum(revenus.values()))
        total_depenses = round(sum(depenses.values()))
        return {"periode": periode, "revenus": revenus, "depenses": depenses, "total_revenus_fcfa": total_revenus, "total_depenses_fcfa": total_depenses, "marge_brute_fcfa": total_revenus - depenses["alimentation"] - depenses["medicaments_vaccins"], "marge_nette_fcfa": total_revenus - total_depenses, "taux_rentabilite_pct": round(((total_revenus - total_depenses) / max(1, total_depenses)) * 100, 2), "format_resume": "RÉSUMÉ FINANCIER"}

    async def cout_de_revient_par_animal(self, id_lot: str, db: Session) -> Dict[str, Any]:
        lot = _find_record(db, "lot", "id_lot", id_lot) or _demo_lot(id_lot)
        effectif = max(1, _safe_int(lot.get("effectif_actuel") or lot.get("effectif_initial")))
        alimentation = effectif * 1800
        sanitaire = effectif * 250
        mo = effectif * 300
        fixes = effectif * 200
        total = alimentation + sanitaire + mo + fixes
        prix_marche = _safe_float(lot.get("prix_vente_prevu_unitaire")) or 3500
        return {"id_lot": id_lot, "cout_alimentation_fcfa": alimentation, "cout_sanitaire_fcfa": sanitaire, "quote_part_main_oeuvre_fcfa": mo, "quote_part_charges_fixes_fcfa": fixes, "cout_revient_total_par_animal_fcfa": round(total / effectif), "prix_marche_actuel_fcfa": prix_marche, "marge_par_animal_si_vente_aujourdhui_fcfa": round(prix_marche - (total / effectif))}

    async def seuil_de_rentabilite(self, id_lot: str, db: Session) -> Dict[str, Any]:
        c = await self.cout_de_revient_par_animal(id_lot, db)
        seuil = c["cout_revient_total_par_animal_fcfa"]
        return {"id_lot": id_lot, "prix_minimum_sans_perte_fcfa": seuil, "prix_recommande_marge_20_pct_fcfa": round(seuil * 1.2), "prix_recommande_marge_35_pct_fcfa": round(seuil * 1.35), "prix_marche_local_fcfa": c["prix_marche_actuel_fcfa"]}

    async def analyse_par_espece(self, user_id: str, db: Session) -> Dict[str, Any]:
        return {"user_id": user_id, "classement_rentabilite": [{"espece": "poulet_chair", "marge_estimee_pct": 24}, {"espece": "poule_pondeuse", "marge_estimee_pct": 18}, {"espece": "bovin", "marge_estimee_pct": 15}], "recommandation": "Renforcer l'espèce avec rotation rapide si la trésorerie est limitée, tout en gardant une production régulière d'œufs/lait."}

    async def projection_annuelle(self, user_id: str, db: Session) -> Dict[str, Any]:
        base = await self.tableau_bord_financier(user_id, date.today().isoformat()[:7], db)
        monthly = base["marge_nette_fcfa"] or 100000
        return {"user_id": user_id, "scenarios": {"pessimiste": round(monthly * 12 * 0.65), "realiste": round(monthly * 12), "optimiste": round(monthly * 12 * 1.35)}, "hypotheses": ["Historique récent", "Saisonnalité des prix béninois", "Cycles planifiés"]}

    async def identifier_pertes_cachees(self, user_id: str, db: Session) -> Dict[str, Any]:
        pertes = [{"type": "Gaspillage alimentaire", "estimation_fcfa_mois": 25000}, {"type": "Mortalités évitables", "estimation_fcfa_mois": 18000}, {"type": "Sous-performance production", "estimation_fcfa_mois": 30000}, {"type": "Prix de vente sous-optimal", "estimation_fcfa_mois": 22000}, {"type": "Charges excessives", "estimation_fcfa_mois": 15000}]
        return {"user_id": user_id, "pertes_cachees": pertes, "total_estime_fcfa_mois": sum(p["estimation_fcfa_mois"] for p in pertes), "priorite": "Commencer par peser les aliments distribués et comparer prix de vente au marché local."}


class PlanificationIntellligente:
    async def generer_planning_semaine(self, user_id: str, db: Session) -> Dict[str, Any]:
        days = []
        labels = ["LUNDI", "MARDI", "MERCREDI", "JEUDI", "VENDREDI", "SAMEDI", "DIMANCHE"]
        today = date.today()
        start = today - timedelta(days=today.weekday())
        for i, label in enumerate(labels):
            d = start + timedelta(days=i)
            tasks = [{"heure": "06h00", "titre": "Distribution aliments lots actifs", "priorite": "planifié"}, {"heure": "09h00", "titre": "Contrôle eau, litière et santé", "priorite": "normal"}, {"heure": "16h00", "titre": "Collecte production / œufs / lait", "priorite": "planifié"}]
            if i == 0:
                tasks.append({"heure": "08h00", "titre": "Pesée hebdomadaire lot prioritaire", "priorite": "urgent"})
            if i == 2:
                tasks.append({"heure": "10h00", "titre": "Vaccination/rappel sanitaire programmé", "priorite": "urgent"})
            days.append({"jour": label, "date": d.isoformat(), "taches": tasks})
        return {"user_id": user_id, "semaine_du": start.isoformat(), "jours": days, "taches_sanitaires_incluses": True}

    async def planifier_cycle_production(self, espece: str, nombre_animaux: int, date_demarrage: str, objectif_vente: str, budget_disponible: float, user_id: str, db: Session) -> Dict[str, Any]:
        achat = nombre_animaux * (650 if "poulet" in _slug(espece) else 3500)
        aliment = nombre_animaux * (1800 if "poulet" in _slug(espece) else 5000)
        sanitaire = nombre_animaux * 250
        mo = nombre_animaux * 300
        divers = round((achat + aliment + sanitaire + mo) * 0.05)
        total = achat + aliment + sanitaire + mo + divers
        return {"user_id": user_id, "plan_de_production": {"espece": espece, "nombre_animaux": nombre_animaux, "date_demarrage": date_demarrage, "objectif_vente": objectif_vente, "chronologie": [{"periode": "Semaine 1-2", "phase": "démarrage", "surveillance": "température, eau, mortalité, appétit"}, {"periode": "Semaine 3-5", "phase": "croissance", "surveillance": "GMQ, homogénéité, consommation"}, {"periode": "Semaine 6-8", "phase": "finition", "surveillance": "poids cible, délai d'attente, vente"}], "budget_previsionnel": {"achat_animaux": achat, "alimentation_totale": aliment, "medicaments_vaccins": sanitaire, "main_oeuvre": mo, "divers_5_pct": divers, "investissement_total": total, "budget_disponible": budget_disponible}, "projection_rentabilite": {"ca_previsionnel": round(total * 1.25), "marge_nette_estimee": round(total * 0.25), "roi_estime_pct": 25, "point_mort": "J+35"}, "risques_mitigation": [{"risque": "maladie fréquente", "mitigation": "biosécurité + calendrier vaccinal"}, {"risque": "fluctuation prix", "mitigation": "prévente et suivi marché"}, {"risque": "chaleur", "mitigation": "ventilation et eau fraîche"}]}}

    async def optimiser_planning_multi_lots(self, user_id: str, db: Session) -> Dict[str, Any]:
        return {"user_id": user_id, "optimisations": ["Décaler les mises en place de 2 semaines pour lisser la trésorerie.", "Regrouper vaccinations sur une même matinée.", "Réserver un bâtiment tampon pour quarantaine."], "calendrier_rotation": "Rotation recommandée : démarrage → croissance → finition → vide sanitaire 10 jours."}


class GestionRH:
    async def assigner_tache(self, technicien_id: str, tache: str, date_value: str, priorite: str, db: Session, user_id: str = "demo-user", ressources: Optional[List[str]] = None) -> Dict[str, Any]:
        payload = {"id_tache": f"TASK_{int(datetime.now().timestamp())}", "technicien_id": technicien_id, "tache": tache, "date": date_value, "priorite": priorite, "ressources": ressources or [], "criteres_validation": ["Photo ou confirmation", "Heure de fin", "Observation terrain"], "statut": "assignée"}
        saved = _save_record(db, "rh_task", user_id, payload)
        return {"message": "Tâche assignée", "tache": saved["data"]}

    async def tableau_bord_technicien(self, technicien_id: str, db: Session) -> Dict[str, Any]:
        tasks = [t for t in _load_records(db, "rh_task") if _norm(t.get("technicien_id")) == _norm(technicien_id)]
        return {"technicien_id": technicien_id, "taches_du_jour": tasks[:10], "alertes_critiques": ["Traiter les tâches urgentes avant 10h"], "animaux_responsabilite": [], "rappels_importants": ["Confirmer chaque tâche terminée"]}

    async def rapport_performance_equipe(self, user_id: str, mois: str, db: Session) -> Dict[str, Any]:
        tasks = [t for t in _load_records(db, "rh_task", user_id) if _norm(t.get("date", ""))[:7] == mois]
        done = sum(1 for t in tasks if t.get("statut") == "terminée")
        return {"user_id": user_id, "mois": mois, "taches_assignees": len(tasks), "taches_completees": done, "taux_completion_pct": round(done / max(1, len(tasks)) * 100, 2), "incidents_sanitaires_par_responsable": {}, "mortalites_sous_supervision": 0, "recommandations_formation": ["Biosécurité", "Pesée et tenue de registre", "Détection précoce maladies"]}


class IAPredicitve:
    async def predire_mortalite(self, id_lot: str, db: Session) -> Dict[str, Any]:
        lot = _find_record(db, "lot", "id_lot", id_lot) or _demo_lot(id_lot)
        taux = (_safe_float(lot.get("mortalite_cumulee")) / max(1, _safe_float(lot.get("effectif_initial")))) * 100
        risque = "élevé" if taux > 5 else "modéré" if taux > 2 else "faible"
        return {"id_lot": id_lot, "risque_mortalite_anormale": risque, "taux_actuel_pct": round(taux, 2), "facteurs_risque": ["densité", "eau", "température", "biosécurité"], "actions_preventives": ["Contrôle matin et soir", "Nettoyage abreuvoirs", "Isoler sujets faibles"]}

    async def predire_performance_lot(self, id_lot: str, db: Session) -> Dict[str, Any]:
        projection = await GestionLots().projeter_vente_lot(id_lot, db)
        return {"id_lot": id_lot, "poids_vente_predit": projection["poids_attendu_kg"], "date_optimale_vente": projection["date_optimale_vente"], "ca_previsionnel_fourchette": {"bas": round(projection["ca_previsionnel_fcfa"] * 0.9), "haut": round(projection["ca_previsionnel_fcfa"] * 1.1)}, "recommandations": ["Peser un échantillon chaque semaine", "Ajuster ration si GMQ baisse", "Sécuriser acheteurs avant finition"]}

    async def detecter_anomalies(self, user_id: str, db: Session) -> Dict[str, Any]:
        events = _load_events(db, user_id)
        anomalies = []
        if sum(1 for e in events if e.get("type_evenement") == "mortalite") > 2:
            anomalies.append({"type": "mortalité", "niveau": "critique", "message": "Mortalités répétées détectées."})
        if any("stock" in _slug(e.get("details")) and _safe_float(e.get("cout_total")) > 100000 for e in events):
            anomalies.append({"type": "dépense", "niveau": "orange", "message": "Dépense stock inhabituelle."})
        return {"user_id": user_id, "analyse_effectuee": True, "date_analyse": _today(), "anomalies": anomalies, "format": "farmmanager_anomalies_v2", "recommandation": "Traiter les anomalies critiques avant les tâches planifiées."}

    async def conseil_quotidien_ia(self, user_id: str, db: Session) -> Dict[str, Any]:
        return await _briefing(user_id, db)


# -----------------------------------------------------------------------------
# Helpers financiers/planning/rapports
# -----------------------------------------------------------------------------
def _dedupe_latest(records: List[Dict[str, Any]], key: str) -> List[Dict[str, Any]]:
    seen: Dict[str, Dict[str, Any]] = {}
    for r in records:
        k = _norm(r.get(key)).lower()
        if k and k not in seen:
            seen[k] = r
    return list(seen.values())


def _demo_stocks() -> List[Dict[str, Any]]:
    return [{"ingredient": "mais", "stock_actuel_kg": 120, "consommation_journaliere_kg": 45, "jours_restants": 3, "seuil_alerte_kg": 150, "prix_achat_fcfa_kg": 250, "valeur_stock_fcfa": 30000, "fournisseur_habituel": "Marché local"}, {"ingredient": "premix", "stock_actuel_kg": 18, "consommation_journaliere_kg": 2, "jours_restants": 9, "seuil_alerte_kg": 15, "prix_achat_fcfa_kg": 1200, "valeur_stock_fcfa": 21600}]


def _current_stock(db: Session, user_id: str, ingredient: str) -> Dict[str, Any]:
    records = [r for r in _load_records(db, "stock", user_id) if _norm(r.get("ingredient")).lower() == _norm(ingredient).lower()]
    return dict(records[0]) if records else {"ingredient": ingredient, "stock_actuel_kg": 0, "consommation_journaliere_kg": 45, "seuil_alerte_kg": 90, "prix_achat_fcfa_kg": 0, "valeur_stock_fcfa": 0, "fournisseur_habituel": "à préciser"}


def _count_events(db: Session, user_id: str, type_evt: str, mois: str) -> int:
    return sum(1 for e in _load_events(db, user_id) if e.get("type_evenement") == type_evt and _norm(e.get("date_evenement", ""))[:7] == mois)


def _sum_by_type(events: List[Dict[str, Any]], type_evt: str) -> float:
    return sum(_safe_float(e.get("revenu")) for e in events if e.get("type_evenement") == type_evt)


def _sum_contains(events: List[Dict[str, Any]], needle: str, amount_key: str) -> float:
    n = _slug(needle)
    return sum(_safe_float(e.get(amount_key)) for e in events if n in _slug(json.dumps(e, ensure_ascii=False)))


def _legacy_financial_dashboard(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    revenus = sum(_safe_float(e.get("revenu")) for e in events)
    depenses = sum(_safe_float(e.get("cout_total")) for e in events)
    return {"cout_total_alimentation_mois": _sum_contains(events, "aliment", "cout_total"), "revenus_ventes_animaux": revenus, "depenses_totales": depenses, "marge_nette_estimee": revenus - depenses, "marge_nette_pct": round((revenus - depenses) / max(1, revenus) * 100, 2), "alertes_gestion": []}


async def _briefing(user_id: str, db: Session) -> Dict[str, Any]:
    finance = await AnalyseFinanciere().tableau_bord_financier(user_id, date.today().isoformat()[:7], db)
    stocks = await GestionAlimentaire().get_stock_critique(user_id, db)
    anomalies = await IAPredicitve().detecter_anomalies(user_id, db)
    lots = _load_records(db, "lot", user_id) or [_demo_lot("LOT_A")]
    alertes = [a.get("message") for a in anomalies.get("anomalies", [])] + [f"{s['ingredient']} : {s.get('jours_restants')} jours restants" for s in stocks.get("stocks_critiques", [])]
    priorites = ["Vérifier eau et aliments de tous les lots", "Traiter les alertes critiques", "Contrôler les animaux malades", "Mettre à jour ventes/dépenses", "Préparer les tâches de demain"]
    return {"user_id": user_id, "date": _today(), "salutation": f"🌅 Bonjour — {_today()}", "statut_global": "Alerte" if alertes else "Bon", "alertes_critiques": alertes, "priorites_du_jour": priorites, "finances_hier": {"revenus": 0, "depenses": 0, "solde": 0}, "finances_mois": finance, "lots_en_cours": [{"id_lot": l.get("id_lot"), "age_jours": _age_days(l.get("date_mise_en_place")), "effectif": l.get("effectif_actuel", l.get("effectif_initial")), "statut": l.get("statut", "OK")} for l in lots[:5]], "stocks_critiques": stocks.get("stocks_critiques", []), "conseil_ia": "Concentrez-vous aujourd'hui sur les alertes rouges, l'eau propre et la tenue exacte des coûts."}


def _write_pdf_report(path: Path, title: str, lines: List[str]) -> None:
    c = canvas.Canvas(str(path), pagesize=A4)
    width, height = A4
    y = height - 2 * cm
    c.setFont("Helvetica-Bold", 14)
    c.drawString(2 * cm, y, title[:95])
    y -= 1 * cm
    c.setFont("Helvetica", 10)
    for raw in lines:
        for line in str(raw).split("\n"):
            if y < 2 * cm:
                c.showPage(); y = height - 2 * cm; c.setFont("Helvetica", 10)
            c.drawString(2 * cm, y, line[:105])
            y -= 0.45 * cm
    c.save()


async def generer_rapport_mensuel(user_id: str, mois: str, db: Session) -> Path:
    finance = await AnalyseFinanciere().tableau_bord_financier(user_id, mois, db)
    sanitaire = await GestionSanitaire().rapport_sanitaire_mensuel(user_id, mois, db)
    anomalies = await IAPredicitve().detecter_anomalies(user_id, db)
    lines = ["Résumé exécutif", f"Période : {mois}", f"Total revenus : {finance['total_revenus_fcfa']} FCFA", f"Total dépenses : {finance['total_depenses_fcfa']} FCFA", f"Marge nette : {finance['marge_nette_fcfa']} FCFA", "", "Analyse sanitaire", json.dumps(sanitaire, ensure_ascii=False), "", "Anomalies et recommandations", json.dumps(anomalies, ensure_ascii=False)]
    out = Path(tempfile.gettempdir()) / "feedformula_reports"
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"rapport_farmmanager_{user_id}_{mois}.pdf"
    _write_pdf_report(path, f"Rapport FarmManager V2 — {mois}", lines)
    return path


# Instances
registre_animal = RegistreAnimal()
gestion_lots = GestionLots()
gestion_sanitaire = GestionSanitaire()
gestion_alimentaire = GestionAlimentaire()
analyse_financiere = AnalyseFinanciere()
planification = PlanificationIntellligente()
gestion_rh = GestionRH()
ia_predictive = IAPredicitve()


# -----------------------------------------------------------------------------
# Endpoints événements vocaux et compatibilité
# -----------------------------------------------------------------------------
@router.post("/evenement")
async def evenement(payload: VocalEventRequest, db: Session = Depends(get_db)) -> Dict[str, Any]:
    event = await traiter_evenement_vocal(payload.texte, payload.user_id, payload.langue, db)
    e = event.get("event", {})
    return {"message": "Événement vocal traité avec succès.", "event": event, "evenement_structure": e, "categorie": e.get("categorie"), "points_gagnes": 5, "qualite_donnee": "bonne" if e.get("niveau_confiance", 0) >= 0.7 else "à compléter", "confirmation": f"✅ {e.get('type_evenement', 'Événement')} enregistré.", "conseils_experts": [e.get("conseil")], "prochaine_action": e.get("action_requise") or (e.get("rappels") or [{}])[0].get("action", "Vérifier l'événement.")}


@router.post("/evenement-vocal")
async def evenement_vocal(payload: VocalEventRequest, db: Session = Depends(get_db)) -> Dict[str, Any]:
    return await evenement(payload, db)


@router.get("/evenements/{user_id}")
def lister_evenements(user_id: str, date_filtre: Optional[str] = Query(default=None), animal_id: Optional[str] = Query(default=None), type_evenement: Optional[str] = Query(default=None), db: Session = Depends(get_db)) -> Dict[str, Any]:
    rows = _load_events(db, user_id)
    if date_filtre:
        rows = [r for r in rows if _norm(r.get("date_evenement"))[:10] == date_filtre]
    if animal_id:
        rows = [r for r in rows if _norm(animal_id).lower() in _norm(r.get("animal_id")).lower()]
    if type_evenement:
        rows = [r for r in rows if _norm(type_evenement).lower() in _norm(r.get("type_evenement")).lower()]
    return {"user_id": user_id, "total_evenements": len(rows), "evenements": [{"id": r.get("_id"), "created_at": r.get("created_at"), "event": r} for r in rows]}


@router.get("/calendrier/{user_id}")
def calendrier(user_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    return {"user_id": user_id, "evenements": [{"id": e.get("_id"), "date_evenement": e.get("date_evenement"), "date_prevue_prochain": e.get("date_rappel"), "type_evenement": e.get("type_evenement"), "animal_id": e.get("animal_id"), "details": e.get("details")} for e in _load_events(db, user_id)]}


@router.get("/stats/{user_id}")
def stats(user_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    events = _load_events(db, user_id)
    return {"user_id": user_id, "total_evenements": len(events), "dashboard_financier": _legacy_financial_dashboard(events)}


@router.get("/finances/{user_id}")
def finances_legacy(user_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    events = _load_events(db, user_id)
    return {"user_id": user_id, "dashboard_financier": _legacy_financial_dashboard(events), "analyse": {"alertes": [], "optimisations": ["Associer chaque transaction à un lot.", "Peser les aliments distribués."]}}


@router.get("/rapport-mensuel/{user_id}")
async def rapport_mensuel(user_id: str, mois: str, db: Session = Depends(get_db)) -> FileResponse:
    path = await generer_rapport_mensuel(user_id, mois, db)
    return FileResponse(path=path, media_type="application/pdf", filename=path.name)


@router.post("/rapport-mensuel")
async def rapport_mensuel_post(payload: MonthlyReportRequest, db: Session = Depends(get_db)) -> FileResponse:
    return await rapport_mensuel(payload.user_id, payload.mois, db)


# -----------------------------------------------------------------------------
# Endpoints demandés V2
# -----------------------------------------------------------------------------
@router.post("/animaux/ajouter")
async def ajouter_animal(payload: AnimalPayload, db: Session = Depends(get_db)) -> Dict[str, Any]:
    return await registre_animal.ajouter_animal(payload.data, payload.user_id, db)


@router.put("/animaux/{id}/modifier")
async def modifier_animal(id: str, data: Dict[str, Any], db: Session = Depends(get_db)) -> Dict[str, Any]:
    return await registre_animal.modifier_animal(id, data, db)


@router.delete("/animaux/{id}/supprimer")
async def supprimer_animal(id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    return await registre_animal.supprimer_animal(id, db)


@router.get("/animaux/{user_id}/tous")
async def tous_animaux(user_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    animaux = await registre_animal.get_tous_animaux(user_id, db)
    return {"user_id": user_id, "total": len(animaux), "animaux": animaux}


@router.get("/animaux/{user_id}/lot/{lot}")
async def animaux_par_lot(user_id: str, lot: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    animaux = [a for a in await registre_animal.get_animaux_par_lot(lot, db) if a.get("user_id") == user_id]
    return {"user_id": user_id, "lot": lot, "total": len(animaux), "animaux": animaux}


@router.post("/animaux/{id}/pesee")
async def pesee_animal(id: str, payload: PeseePayload, db: Session = Depends(get_db)) -> Dict[str, Any]:
    return await registre_animal.enregistrer_pesee(id, payload.poids, db)


@router.post("/animaux/{id}/transferer")
async def transferer_animal(id: str, payload: TransferPayload, db: Session = Depends(get_db)) -> Dict[str, Any]:
    animaux = payload.animaux or [id]
    return await registre_animal.transferer_lot(animaux, payload.nouveau_lot, db)


@router.post("/lots/creer")
async def creer_lot(payload: LotPayload, db: Session = Depends(get_db)) -> Dict[str, Any]:
    return await gestion_lots.creer_lot(payload.data, payload.user_id, db)


@router.get("/lots/{user_id}/tous")
def tous_lots(user_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    lots = _load_records(db, "lot", user_id)
    return {"user_id": user_id, "total": len(lots), "lots": [_lot_dashboard(l, db) for l in lots]}


@router.get("/lots/{id}/tableau-bord")
async def lot_tableau_bord(id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    return await gestion_lots.get_tableau_bord_lot(id, db)


@router.get("/lots/{id}/projection-vente")
async def lot_projection_vente(id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    return await gestion_lots.projeter_vente_lot(id, db)


@router.get("/lots/{id}/alertes")
async def lot_alertes(id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    return await gestion_lots.alertes_lot(id, db)


@router.post("/sanitaire/programme")
async def sanitaire_programme(payload: ProgrammeSanitairePayload, db: Session = Depends(get_db)) -> Dict[str, Any]:
    return await gestion_sanitaire.generer_programme_sanitaire(payload.espece, payload.stade, payload.date_mise_en_place, db)


@router.post("/sanitaire/traitement")
async def sanitaire_traitement(payload: TraitementPayload, db: Session = Depends(get_db)) -> Dict[str, Any]:
    return await gestion_sanitaire.enregistrer_traitement(payload.animaux_concernes, payload.maladie_suspectee, payload.medicament, payload.dose, payload.duree_jours, payload.cout_fcfa, payload.user_id, db)


@router.get("/sanitaire/delais-attente/{user_id}")
async def sanitaire_delais(user_id: str, lot: str = "", db: Session = Depends(get_db)) -> Dict[str, Any]:
    data = await gestion_sanitaire.verifier_delai_attente(lot, db)
    data["user_id"] = user_id
    return data


@router.get("/sanitaire/rapport/{user_id}")
async def sanitaire_rapport(user_id: str, mois: str = Query(default_factory=lambda: date.today().isoformat()[:7]), db: Session = Depends(get_db)) -> Dict[str, Any]:
    return await gestion_sanitaire.rapport_sanitaire_mensuel(user_id, mois, db)


@router.post("/stocks/entree")
async def stock_entree(payload: EntreeStockPayload, db: Session = Depends(get_db)) -> Dict[str, Any]:
    return await gestion_alimentaire.enregistrer_entree_stock(payload.ingredient, payload.quantite_kg, payload.prix_fcfa_kg, payload.fournisseur, payload.date_livraison, db, payload.user_id or "demo-user")


@router.post("/stocks/consommation")
async def stock_consommation(payload: ConsommationStockPayload, db: Session = Depends(get_db)) -> Dict[str, Any]:
    return await gestion_alimentaire.enregistrer_consommation(payload.lot, payload.ingredient, payload.quantite_kg, payload.date, db, payload.user_id or "demo-user")


@router.get("/stocks/critiques/{user_id}")
async def stocks_critiques(user_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    return await gestion_alimentaire.get_stock_critique(user_id, db)


@router.get("/stocks/optimisation/{user_id}")
async def stocks_optimisation(user_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    return await gestion_alimentaire.optimiser_cout_alimentaire(user_id, db)


@router.get("/stocks/commander/{user_id}/{ingredient}")
async def stocks_commander(user_id: str, ingredient: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    return await gestion_alimentaire.commander_automatiquement(ingredient, user_id, db)


@router.get("/finances/tableau-bord/{user_id}")
async def finances_tableau_bord(user_id: str, periode: str = Query(default_factory=lambda: date.today().isoformat()[:7]), db: Session = Depends(get_db)) -> Dict[str, Any]:
    return await analyse_financiere.tableau_bord_financier(user_id, periode, db)


@router.get("/finances/cout-revient/{lot_id}")
async def finances_cout_revient(lot_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    return await analyse_financiere.cout_de_revient_par_animal(lot_id, db)


@router.get("/finances/seuil-rentabilite/{lot_id}")
async def finances_seuil(lot_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    return await analyse_financiere.seuil_de_rentabilite(lot_id, db)


@router.get("/finances/analyse-espece/{user_id}")
async def finances_analyse_espece(user_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    return await analyse_financiere.analyse_par_espece(user_id, db)


@router.get("/finances/projection-annuelle/{user_id}")
async def finances_projection(user_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    return await analyse_financiere.projection_annuelle(user_id, db)


@router.get("/finances/pertes-cachees/{user_id}")
async def finances_pertes(user_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    return await analyse_financiere.identifier_pertes_cachees(user_id, db)


@router.get("/planning/semaine/{user_id}")
async def planning_semaine(user_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    return await planification.generer_planning_semaine(user_id, db)


@router.post("/planning/cycle-production")
async def planning_cycle(payload: CycleProductionPayload, db: Session = Depends(get_db)) -> Dict[str, Any]:
    return await planification.planifier_cycle_production(payload.espece, payload.nombre_animaux, payload.date_demarrage, payload.objectif_vente, payload.budget_disponible, payload.user_id, db)


@router.get("/planning/optimisation/{user_id}")
async def planning_optimisation(user_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    return await planification.optimiser_planning_multi_lots(user_id, db)


@router.post("/rh/assigner-tache")
async def rh_assigner(payload: AssignTaskPayload, db: Session = Depends(get_db)) -> Dict[str, Any]:
    return await gestion_rh.assigner_tache(payload.technicien_id, payload.tache, payload.date, payload.priorite, db, payload.user_id or "demo-user", payload.ressources)


@router.get("/rh/tableau-bord/{technicien_id}")
async def rh_tableau_bord(technicien_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    return await gestion_rh.tableau_bord_technicien(technicien_id, db)


@router.get("/rh/rapport-performance/{user_id}")
async def rh_rapport(user_id: str, mois: str = Query(default_factory=lambda: date.today().isoformat()[:7]), db: Session = Depends(get_db)) -> Dict[str, Any]:
    return await gestion_rh.rapport_performance_equipe(user_id, mois, db)


@router.get("/ia/briefing-quotidien/{user_id}")
async def ia_briefing(user_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    return await _briefing(user_id, db)


@router.get("/ia/prediction-mortalite/{lot_id}")
async def ia_prediction_mortalite(lot_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    return await ia_predictive.predire_mortalite(lot_id, db)


@router.get("/ia/prediction-lot/{lot_id}")
async def ia_prediction_lot(lot_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    return await ia_predictive.predire_performance_lot(lot_id, db)


@router.get("/ia/anomalies/{user_id}")
async def ia_anomalies(user_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    return await ia_predictive.detecter_anomalies(user_id, db)


@router.get("/ia/conseil-quotidien/{user_id}")
async def ia_conseil(user_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    return await ia_predictive.conseil_quotidien_ia(user_id, db)
