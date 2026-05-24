#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pyright: reportGeneralTypeIssues=false, reportArgumentType=false, reportAssignmentType=false, reportReturnType=false, reportAttributeAccessIssue=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownVariableType=false
"""FarmCommunity de FeedFormula AI."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from database import (
    add_points_to_user,
    create_annonce_marche,
    create_commentaire,
    create_post,
    get_db,
    get_user_by_id,
    like_post,
    list_annonces_marche,
    list_commentaires_for_post,
    list_posts,
    serialize_annonce_marche,
    serialize_commentaire,
    serialize_post,
)
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

router = APIRouter(prefix="/community", tags=["Community"])

COMMUNITY_CATEGORIES: Dict[str, Dict[str, Any]] = {
    "question": {"icone": "❓", "label": "Question terrain", "objectif": "obtenir une réponse précise"},
    "conseil": {"icone": "💡", "label": "Conseil validable", "objectif": "partager une pratique reproductible"},
    "alerte": {"icone": "🚨", "label": "Alerte communautaire", "objectif": "prévenir un risque sanitaire ou marché"},
    "retour_experience": {"icone": "📊", "label": "Retour d'expérience", "objectif": "documenter un résultat chiffré"},
    "annonce": {"icone": "📢", "label": "Annonce", "objectif": "informer la communauté"},
}

COMMUNITY_EXPERTS: List[Dict[str, Any]] = [
    {"id": "EXP_NUTRI", "nom": "Expert Nutrition", "icone": "🌾", "specialite": "Rations, ingrédients, coûts alimentaires", "statut": "en ligne", "module": "NutriCore"},
    {"id": "EXP_VET", "nom": "Expert Santé", "icone": "🩺", "specialite": "Symptômes, biosécurité, urgence vétérinaire", "statut": "en ligne", "module": "VetScan"},
    {"id": "EXP_REPRO", "nom": "Expert Reproduction", "icone": "📅", "specialite": "Chaleurs, gestation, mise-bas, fertilité", "statut": "occupé", "module": "ReproTrack"},
    {"id": "EXP_BOTA", "nom": "Expert Plantes", "icone": "🌿", "specialite": "Fourrages, plantes médicinales, toxicité", "statut": "en ligne", "module": "FloraVet"},
    {"id": "EXP_GESTION", "nom": "Coach Ferme", "icone": "📊", "specialite": "Coûts, ventes, registres, planning", "statut": "en ligne", "module": "FarmManager"},
]


class CommentRequest(BaseModel):
    user_id: str = Field(..., min_length=3)
    contenu: str = Field(..., min_length=1)

    @field_validator("user_id", "contenu")
    @classmethod
    def _strip(cls, value: str) -> str:
        txt = (value or "").strip()
        if not txt:
            raise ValueError("Champ vide.")
        return txt


class PostRequest(BaseModel):
    user_id: str = Field(..., min_length=3)
    titre: str = Field(default="")
    contenu: str = Field(..., min_length=1)
    type_post: str = Field(default="conseil")
    espece_concernee: str = Field(default="")
    langue: str = Field(default="fr")

    @field_validator(
        "user_id", "titre", "contenu", "type_post", "espece_concernee", "langue"
    )
    @classmethod
    def _strip(cls, value: str) -> str:
        return (value or "").strip()


class MarcheRequest(BaseModel):
    user_id: str = Field(..., min_length=3)
    type_annonce: Optional[str] = Field(default=None)
    type: Optional[str] = Field(default=None)
    espece: str = Field(..., min_length=2)
    race: str = Field(default="")
    quantite: Any = Field(default=1)
    prix_fcfa: Optional[float] = Field(default=None)
    prix: Optional[str] = Field(default=None)
    prix_negociable: bool = Field(default=False)
    description: str = Field(default="")
    localisation: str = Field(..., min_length=2)
    departement: str = Field(default="")
    telephone_contact: str = Field(default="")
    photos_json: List[str] = Field(default_factory=list)
    statut: str = Field(default="actif")

    @field_validator(
        "user_id",
        "type_annonce",
        "type",
        "espece",
        "race",
        "description",
        "localisation",
        "departement",
        "telephone_contact",
        "statut",
        mode="before",
    )
    @classmethod
    def _strip(cls, value: Any) -> str:
        return ("" if value is None else str(value)).strip()


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _post_quality_guidance(type_post: str, espece: str, contenu: str) -> Dict[str, Any]:
    """Ajoute une lecture experte au contenu communautaire."""
    text = _clean(contenu).lower()
    badges: List[str] = []
    conseils: List[str] = []
    if any(word in text for word in ["fcfa", "kg", "%", "litre", "poids"]):
        badges.append("donnée_chiffrée")
    if any(
        word in text for word in ["vaccin", "maladie", "diarr", "toux", "mortalité"]
    ):
        badges.append("santé_animale")
        conseils.append(
            "Indiquez la commune, l'âge des animaux et depuis quand les signes sont observés."
        )
    if any(word in text for word in ["ration", "maïs", "soja", "aliment"]):
        badges.append("nutrition")
        conseils.append(
            "Précisez les quantités, le prix local des ingrédients et le nombre d'animaux concernés."
        )
    if _clean(type_post).lower() == "question":
        conseils.append(
            "Formulez une question précise pour recevoir une réponse utile de la communauté."
        )
    if _clean(type_post).lower() == "alerte":
        badges.append("alerte_communautaire")
        conseils.append(
            "Évitez les rumeurs : mentionnez uniquement les faits observés et conseillez de confirmer avec un technicien."
        )
    if not conseils:
        conseils.append(
            "Ajoutez une observation mesurable pour aider les autres éleveurs à comparer les résultats."
        )
    return {
        "badges_experts": badges or ["partage_terrain"],
        "conseils_publication": conseils[:3],
        "niveau_fiabilite": "élevé" if badges else "à compléter",
        "espece_cible": espece or "toutes espèces",
    }


def _community_trust_score(contenu: str, type_post: str = "conseil") -> Dict[str, Any]:
    text = _clean(contenu).lower()
    score = 45
    if any(x in text for x in ["kg", "fcfa", "%", "jour", "semaine", "mortalité", "ponte", "poids"]):
        score += 20
    if any(x in text for x in ["photo", "vidéo", "preuve", "résultat", "avant", "après"]):
        score += 10
    if any(x in text for x in ["je pense", "on dit", "rumeur", "miracle", "garanti"]):
        score -= 20
    if any(x in text for x in ["dose", "antibiotique", "poison", "toxique", "mort", "urgence"]):
        score -= 5
    if _clean(type_post).lower() == "retour_experience":
        score += 10
    score = max(5, min(100, score))
    return {
        "score": score,
        "niveau": "fiable" if score >= 75 else "à compléter" if score >= 45 else "risqué",
        "explication": "Score basé sur données chiffrées, preuves, niveau de précision et risques sanitaires.",
    }


def _post_action_pack(type_post: str, espece: str, contenu: str) -> Dict[str, Any]:
    guidance = _post_quality_guidance(type_post, espece, contenu)
    trust = _community_trust_score(contenu, type_post)
    return {
        "lecture_experte": guidance,
        "score_confiance": trust,
        "actions_recommandees": [
            "Ajouter espèce, âge/stade et localisation si absent.",
            "Ajouter une donnée mesurable : kg, FCFA, %, mortalité, ponte, poids ou durée.",
            "Si santé animale : compléter avec symptômes et utiliser VetScan si urgence.",
        ],
        "modules_utiles": _suggest_modules_for_content(contenu),
    }


def _suggest_modules_for_content(contenu: str) -> List[Dict[str, str]]:
    text = _clean(contenu).lower()
    modules = []
    if any(w in text for w in ["ration", "aliment", "maïs", "soja", "kg"]):
        modules.append({"module": "NutriCore", "raison": "vérifier ou formuler l'aliment"})
    if any(w in text for w in ["maladie", "diarr", "toux", "touss", "respir", "mange moins", "baisse", "mort", "vaccin", "fièvre", "fievre"]):
        modules.append({"module": "VetScan", "raison": "analyser les symptômes et le niveau d'urgence"})
    if any(w in text for w in ["chaleur", "saillie", "mise-bas", "gestation", "ponte"]):
        modules.append({"module": "ReproTrack", "raison": "suivre le calendrier reproductif"})
    if any(w in text for w in ["plante", "moringa", "neem", "fourrage", "toxique"]):
        modules.append({"module": "FloraVet", "raison": "identifier plante utile ou dangereuse"})
    modules.append({"module": "FarmManager", "raison": "enregistrer l'événement, coût ou résultat"})
    return modules[:4]


def _market_advice(
    type_annonce: str, espece: str, prix: Any, quantite: Any
) -> Dict[str, Any]:
    """Conseils de marché pour rendre les annonces plus professionnelles."""
    prix_float = float(prix or 0)
    quantite_int = int(quantite or 0)
    conseils = [
        "Ajoutez une photo nette et récente de l'animal ou du lot.",
        "Précisez le poids moyen, l'âge, la race et l'état sanitaire si possible.",
        "Confirmez le prix par téléphone avant déplacement pour éviter les pertes de temps.",
    ]
    if prix_float <= 0:
        conseils.insert(
            0,
            "Prix absent ou nul : indiquez un prix de référence ou précisez que la négociation est ouverte.",
        )
    if quantite_int <= 0:
        conseils.insert(
            0,
            "Quantité absente : indiquez le nombre exact d'animaux ou de kilogrammes disponibles.",
        )
    if _clean(type_annonce).lower() == "vente":
        conseils.append(
            "Pour une vente, mentionnez si le transport, la vaccination ou l'aliment récent sont inclus."
        )
    return {
        "conseils_marche": conseils[:4],
        "score_confiance_annonce": max(
            35,
            min(
                95, 55 + (20 if prix_float > 0 else 0) + (20 if quantite_int > 0 else 0)
            ),
        ),
        "resume_offre": f"{type_annonce or 'annonce'} {espece or 'animal'} — {quantite_int or 'quantité à préciser'} unité(s) à {int(prix_float) if prix_float else 'prix à préciser'} FCFA",
    }


class CommunityService:
    async def moderer_contenu(self, contenu: str) -> bool:
        texte = (contenu or "").strip()
        if not texte:
            return False
        if len(texte) < 3:
            return False
        if any(mot in texte.lower() for mot in ["mensonge", "venin", "arnaque"]):
            return False
        try:
            import os

            from openai import OpenAI  # type: ignore

            api_key = (os.getenv("AFRI_API_KEY") or "").strip()
            if not api_key:
                return True
            client = OpenAI(
                api_key=api_key,
                base_url=(
                    os.getenv("AFRI_BASE_URL") or "https://api.openai.com/v1"
                ).strip(),
            )
            response = client.chat.completions.create(
                model=(os.getenv("AFRI_CHAT_MODEL") or "gpt-5.5").strip(),
                messages=[
                    {
                        "role": "system",
                        "content": "Tu valides du contenu agricole. Réponds uniquement par OK ou REJET.",
                    },
                    {"role": "user", "content": f"Vérifie ce contenu: {texte}"},
                ],
                temperature=0.3,
                max_tokens=4000,
                top_p=0.9,
                frequency_penalty=0.1,
                presence_penalty=0.1,
            )
            content = getattr(response.choices[0].message, "content", "")
            return isinstance(content, str) and "OK" in content.upper()
        except Exception:
            return True

    async def creer_post(
        self, user_id, titre, contenu, type_post, espece_concernee, langue, db
    ) -> Dict[str, Any]:
        if not await self.moderer_contenu(contenu):
            raise HTTPException(
                status_code=400, detail="Contenu refusé par la modération."
            )
        user = get_user_by_id(db, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="Utilisateur introuvable.")
        titre_final = (titre or "").strip() or (
            contenu[:70] + ("..." if len(contenu) > 70 else "")
        )
        post = create_post(
            db,
            user_id=user_id,
            titre=titre_final,
            contenu=contenu,
            type_contenu=type_post,
            espece_concernee=espece_concernee,
            langue=langue,
        )
        add_points_to_user(db, user_id, 12)
        action_pack = _post_action_pack(type_post, espece_concernee, contenu)
        return {
            **serialize_post(post),
            "points_gagnes": 12,
            **action_pack,
            "badges_community": action_pack["lecture_experte"].get("badges_experts", []),
        }

    def get_fil_actualite(self, user_id, page, db) -> List[Dict[str, Any]]:
        user = get_user_by_id(db, user_id)
        region = getattr(user, "region", "") if user else ""
        posts = list_posts(db, limit=500)
        posts_sorted = sorted(
            posts,
            key=lambda p: (
                0 if region and getattr(p.user, "region", "") == region else 1,
                -int(getattr(p, "likes", 0) or 0),
                -(p.date_creation.timestamp() if p.date_creation else 0),
            ),
        )
        start = max(0, (int(page or 1) - 1) * 20)
        page_items = posts_sorted[start : start + 20]
        result = []
        for post in page_items:
            commentaires = list_commentaires_for_post(db, str(post.id), limit=20)
            result.append(
                {
                    **serialize_post(post),
                    "vues": int(getattr(post, "vues", 0) or 0),
                    "titre": getattr(post, "titre", ""),
                    "espece_concernee": getattr(post, "espece_concernee", ""),
                    "langue": getattr(post, "langue", "fr"),
                    "commentaires": [serialize_commentaire(c) for c in commentaires],
                    **_post_action_pack(
                        getattr(post, "type_contenu", "conseil"),
                        getattr(post, "espece_concernee", ""),
                        getattr(post, "contenu", ""),
                    ),
                    "lecture_experte": _post_quality_guidance(
                        getattr(post, "type_contenu", "conseil"),
                        getattr(post, "espece_concernee", ""),
                        getattr(post, "contenu", ""),
                    ),
                }
            )
        return result

    async def creer_annonce_marche(
        self,
        user_id,
        type_annonce,
        espece,
        race,
        quantite,
        prix,
        description,
        localisation,
        departement,
        telephone,
        db,
    ) -> Dict[str, Any]:
        user = get_user_by_id(db, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="Utilisateur introuvable.")
        expires = _now() + timedelta(days=30)
        annonce = create_annonce_marche(
            db,
            user_id=user_id,
            type_annonce=type_annonce,
            espece=espece,
            race=race,
            quantite=int(quantite or 0),
            prix_fcfa=float(prix or 0),
            prix_negociable=bool(prix == 0),
            description=description,
            localisation=localisation,
            departement=departement,
            telephone_contact=telephone,
            photos_json=[],
            statut="actif",
            date_expiration=expires,
        )
        # enrichissement simple local
        if not getattr(annonce, "description", ""):
            setattr(
                annonce,
                "description",
                f"Annonce {type_annonce} pour {espece} ({race}).",
            )
        db.commit()
        db.refresh(annonce)
        return {
            **serialize_annonce_marche(annonce),
            "whatsapp_link": f"https://wa.me/?text={uuid.uuid4().hex[:8]}%20{espece}%20{prix}",
            "lecture_marche": _market_advice(type_annonce, espece, prix, quantite),
        }

    def rechercher_annonces(
        self, type_annonce, espece, departement, prix_min, prix_max, db
    ) -> List[Dict[str, Any]]:
        annonces = list_annonces_marche(
            db,
            type_annonce=type_annonce,
            espece=espece,
            departement=departement,
            limit=500,
        )
        filtered = []
        for annonce in annonces:
            p = float(getattr(annonce, "prix_fcfa", 0.0) or 0.0)
            if prix_min is not None and p < float(prix_min):
                continue
            if prix_max is not None and p > float(prix_max):
                continue
            filtered.append(serialize_annonce_marche(annonce))
        filtered.sort(
            key=lambda a: (
                a.get("statut") != "actif",
                -(
                    datetime.fromisoformat(a["date_creation"]).timestamp()
                    if a.get("date_creation")
                    else 0
                ),
            )
        )
        return filtered

    def get_dashboard(self, db: Session, user_id: str = "") -> Dict[str, Any]:
        posts = list_posts(db, limit=1000)
        annonces = list_annonces_marche(db, limit=1000)
        comments_total = sum(len(list_commentaires_for_post(db, str(post.id), limit=1000)) for post in posts[:200])
        active_ads = [a for a in annonces if getattr(a, "statut", "") in {"actif", "active"}]
        top_posts = sorted(posts, key=lambda p: int(getattr(p, "likes", 0) or 0), reverse=True)[:5]
        themes: Dict[str, int] = {}
        for post in posts:
            for token in _clean(getattr(post, "espece_concernee", "") or getattr(post, "type_contenu", "")).lower().split():
                if token:
                    themes[token] = themes.get(token, 0) + 1
        return {
            "user_id": user_id,
            "metriques": {
                "posts": len(posts),
                "commentaires": comments_total,
                "annonces": len(annonces),
                "annonces_actives": len(active_ads),
                "likes_total": sum(int(getattr(post, "likes", 0) or 0) for post in posts),
                "experts_disponibles": sum(1 for e in COMMUNITY_EXPERTS if e["statut"] == "en ligne"),
            },
            "score_communaute": min(100, len(posts) * 3 + comments_total * 2 + len(active_ads) * 4),
            "tendances": sorted([{"theme": k, "volume": v} for k, v in themes.items()], key=lambda x: x["volume"], reverse=True)[:8],
            "top_posts": [serialize_post(p) for p in top_posts],
            "experts": COMMUNITY_EXPERTS,
            "prochaine_action": "Posez une question précise avec espèce, âge, région, chiffres et photo si possible.",
        }


SERVICE = CommunityService()


async def _parse_post_payload(request: Request) -> Dict[str, Any]:
    content_type = request.headers.get("content-type", "")
    if content_type.startswith("multipart/form-data") or content_type.startswith(
        "application/x-www-form-urlencoded"
    ):
        form = await request.form()
        return {
            k: (form.get(k) if k in form else None)
            for k in [
                "user_id",
                "titre",
                "contenu",
                "type_post",
                "type",
                "espece_concernee",
                "langue",
            ]
        }
    try:
        data = await request.json()
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


@router.get("/posts")
def get_posts(
    page: int = 1,
    espece: Optional[str] = None,
    user_id: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    items = SERVICE.get_fil_actualite(user_id or "", page, db)
    if espece:
        items = [
            post
            for post in items
            if _clean(post.get("espece_concernee", "")).lower()
            == _clean(espece).lower()
            or _clean(espece).lower() in _clean(post.get("contenu", "")).lower()
        ]
    return {"page": page, "total": len(items), "posts": items}


def _clean(value: str) -> str:
    return (value or "").strip()


@router.post("/posts")
async def create_new_post(
    request: Request, db: Session = Depends(get_db)
) -> Dict[str, Any]:
    data = await _parse_post_payload(request)
    user_id = _clean(str(data.get("user_id") or ""))
    contenu = _clean(str(data.get("contenu") or ""))
    titre = _clean(str(data.get("titre") or ""))
    type_post = _clean(str(data.get("type_post") or data.get("type") or "conseil"))
    espece_concernee = _clean(str(data.get("espece_concernee") or ""))
    langue = _clean(str(data.get("langue") or "fr")) or "fr"
    if not user_id or not contenu:
        raise HTTPException(status_code=400, detail="user_id et contenu requis.")
    return await SERVICE.creer_post(
        user_id, titre, contenu, type_post, espece_concernee, langue, db
    )


@router.post("/posts/{post_id}/like")
def like(post_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    post = like_post(db, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post introuvable.")
    return {"message": "Like ajouté.", **serialize_post(post)}


@router.post("/posts/{post_id}/commentaire")
@router.post("/posts/{post_id}/commentaires")
def commenter(
    post_id: str, payload: CommentRequest, db: Session = Depends(get_db)
) -> Dict[str, Any]:
    user = get_user_by_id(db, payload.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable.")
    commentaire = create_commentaire(
        db, post_id=post_id, user_id=payload.user_id, contenu=payload.contenu
    )
    return {"message": "Commentaire ajouté.", **serialize_commentaire(commentaire)}


@router.get("/marche")
def marche(
    type: Optional[str] = None,
    espece: Optional[str] = None,
    dept: Optional[str] = None,
    localisation: Optional[str] = None,
    prix_min: Optional[float] = None,
    prix_max: Optional[float] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    annonces = SERVICE.rechercher_annonces(
        type, espece, dept or localisation, prix_min, prix_max, db
    )
    return {"total": len(annonces), "annonces": annonces}


@router.post("/marche")
def creer_marche(
    payload: MarcheRequest, db: Session = Depends(get_db)
) -> Dict[str, Any]:
    user = get_user_by_id(db, payload.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable.")
    annonce = create_annonce_marche(
        db,
        user_id=payload.user_id,
        type_annonce=(payload.type_annonce or payload.type or "vente"),
        espece=payload.espece,
        race=payload.race,
        quantite=payload.quantite,
        prix_fcfa=float(payload.prix_fcfa or 0.0),
        prix_negociable=payload.prix_negociable,
        description=payload.description,
        localisation=payload.localisation,
        departement=payload.departement,
        telephone_contact=payload.telephone_contact,
        photos_json=payload.photos_json,
        statut=(payload.statut or "actif"),
        date_expiration=_now() + timedelta(days=30),
        prix=payload.prix or payload.prix_fcfa,
    )
    lecture_marche = _market_advice(
        payload.type_annonce or payload.type or "vente",
        payload.espece,
        payload.prix_fcfa or 0,
        payload.quantite,
    )
    return {
        "message": "Annonce créée.",
        **serialize_annonce_marche(annonce),
        "whatsapp_link": f"https://wa.me/?text={payload.espece}%20{payload.prix_fcfa}",
        "lecture_marche": lecture_marche,
        "score_confiance_annonce": lecture_marche.get("score_confiance_annonce"),
    }


@router.get("/marche/{annonce_id}")
def get_marche_detail(annonce_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    annonces = list_annonces_marche(db, limit=500)
    annonce = next((a for a in annonces if str(a.id) == annonce_id), None)
    if not annonce:
        raise HTTPException(status_code=404, detail="Annonce introuvable.")
    return serialize_annonce_marche(annonce)


@router.put("/marche/{annonce_id}/statut")
def update_marche_statut(
    annonce_id: str, payload: Dict[str, Any], db: Session = Depends(get_db)
) -> Dict[str, Any]:
    status_new = str(payload.get("statut") or "").strip().lower()
    if status_new not in {"actif", "vendu", "expire", "active"}:
        raise HTTPException(status_code=400, detail="Statut invalide.")
    annonces = list_annonces_marche(db, limit=500)
    annonce = next((a for a in annonces if str(a.id) == annonce_id), None)
    if not annonce:
        raise HTTPException(status_code=404, detail="Annonce introuvable.")
    setattr(annonce, "statut", status_new)
    db.commit()
    db.refresh(annonce)
    return serialize_annonce_marche(annonce)


@router.get("/categories")
def get_categories() -> Dict[str, Any]:
    return {
        "total": len(COMMUNITY_CATEGORIES),
        "categories": COMMUNITY_CATEGORIES,
        "regle_or": "Une bonne publication communautaire contient contexte, espèce, âge/stade, région, chiffres et question claire.",
    }


@router.get("/experts")
def get_experts() -> Dict[str, Any]:
    return {
        "total": len(COMMUNITY_EXPERTS),
        "experts": COMMUNITY_EXPERTS,
        "message": "Les experts orientent vers les modules FeedFormula adaptés et ne remplacent pas un vétérinaire en urgence.",
    }


@router.get("/dashboard/{user_id}")
def dashboard(user_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    return SERVICE.get_dashboard(db, user_id)


@router.get("/tendances")
def tendances(db: Session = Depends(get_db)) -> Dict[str, Any]:
    dash = SERVICE.get_dashboard(db)
    return {
        "tendances": dash.get("tendances", []),
        "top_posts": dash.get("top_posts", []),
        "prochaine_action": dash.get("prochaine_action"),
    }


@router.post("/assistant-question")
def assistant_question(payload: Dict[str, Any]) -> Dict[str, Any]:
    contenu = str(payload.get("contenu") or payload.get("question") or "").strip()
    espece = str(payload.get("espece") or "").strip()
    type_post = str(payload.get("type_post") or "question").strip()
    if not contenu:
        raise HTTPException(status_code=400, detail="Question/contenu requis.")
    pack = _post_action_pack(type_post, espece, contenu)
    return {
        "question_originale": contenu,
        "question_amelioree": (
            f"Espèce: {espece or 'à préciser'} | Contexte: [commune, âge/stade, nombre d'animaux] | "
            f"Observation: {contenu} | Données: [kg, FCFA, durée, mortalité, production] | Question précise: que dois-je faire maintenant ?"
        ),
        "score_confiance": pack["score_confiance"],
        "modules_utiles": pack["modules_utiles"],
        "actions_recommandees": pack["actions_recommandees"],
    }


@router.get("/stats")
def stats(db: Session = Depends(get_db)) -> Dict[str, Any]:
    posts = list_posts(db, limit=1000)
    annonces = list_annonces_marche(db, limit=1000)
    comments_total = sum(
        len(list_commentaires_for_post(db, str(post.id), limit=1000)) for post in posts
    )
    return {
        "posts": len(posts),
        "commentaires": comments_total,
        "annonces": len(annonces),
        "annonces_actives": sum(
            1 for a in annonces if getattr(a, "statut", "") in {"actif", "active"}
        ),
        "likes_total": sum(int(getattr(post, "likes", 0) or 0) for post in posts),
    }


__all__ = ["router", "SERVICE", "CommunityService"]
