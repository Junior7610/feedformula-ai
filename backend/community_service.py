#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pyright: reportGeneralTypeIssues=false
"""
FarmCommunity basique.

- Fil d actualité des posts
- Likes
- Commentaires
- Marketplace d annonces vente/achat
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from database import (
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
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

router = APIRouter(prefix="/community", tags=["Community"])


class PostRequest(BaseModel):
    user_id: str = Field(..., min_length=3)
    contenu: str = Field(..., min_length=1)
    type: str = Field(default="texte")

    @field_validator("user_id", "contenu", "type")
    @classmethod
    def _strip(cls, value: str) -> str:
        txt = (value or "").strip()
        if not txt:
            raise ValueError("Champ vide.")
        return txt


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


class MarcheRequest(BaseModel):
    user_id: str = Field(..., min_length=3)
    type: str = Field(..., pattern="^(vente|achat)$")
    espece: str = Field(..., min_length=2)
    quantite: str = Field(..., min_length=1)
    prix: str = Field(..., min_length=1)
    localisation: str = Field(..., min_length=2)
    statut: str = Field(default="active")

    @field_validator("user_id", "espece", "quantite", "prix", "localisation", "type")
    @classmethod
    def _strip(cls, value: str) -> str:
        txt = (value or "").strip()
        if not txt:
            raise ValueError("Champ vide.")
        return txt


@router.get("/posts")
def get_posts(db: Session = Depends(get_db)) -> Dict[str, Any]:
    posts = list_posts(db, limit=50)
    result = []
    for post in posts:
        commentaires = list_commentaires_for_post(db, str(post.id), limit=20)
        result.append(
            {
                **serialize_post(post),
                "commentaires": [serialize_commentaire(c) for c in commentaires],
            }
        )
    return {"total": len(result), "posts": result}


@router.post("/posts")
def create_new_post(
    contenu: str = Form(...),
    user_id: str = Form(...),
    type: str = Form(default="texte"),
    photo: Optional[UploadFile] = File(default=None),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Utilisateur introuvable."
        )
    contenu_final = contenu.strip()
    if photo and photo.filename:
        contenu_final = f"{contenu_final} [photo:{photo.filename}]"
    post = create_post(db, user_id=user_id, contenu=contenu_final, type_contenu=type)
    return {"message": "Post créé.", **serialize_post(post)}


@router.post("/posts/{post_id}/like")
def like(post_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    post = like_post(db, post_id)
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Post introuvable."
        )
    return {"message": "Like ajouté.", **serialize_post(post)}


@router.post("/posts/{post_id}/commentaires")
def commenter(
    post_id: str, payload: CommentRequest, db: Session = Depends(get_db)
) -> Dict[str, Any]:
    user = get_user_by_id(db, payload.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Utilisateur introuvable."
        )
    commentaire = create_commentaire(
        db, post_id=post_id, user_id=payload.user_id, contenu=payload.contenu
    )
    return {"message": "Commentaire ajouté.", **serialize_commentaire(commentaire)}


@router.get("/marche")
def marche(
    type: Optional[str] = None,
    espece: Optional[str] = None,
    localisation: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    annonces = list_annonces_marche(
        db, type_annonce=type, espece=espece, localisation=localisation, limit=50
    )
    return {
        "total": len(annonces),
        "annonces": [serialize_annonce_marche(a) for a in annonces],
    }


@router.post("/marche")
def creer_marche(
    payload: MarcheRequest, db: Session = Depends(get_db)
) -> Dict[str, Any]:
    user = get_user_by_id(db, payload.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Utilisateur introuvable."
        )
    annonce = create_annonce_marche(
        db,
        user_id=payload.user_id,
        type_annonce=payload.type,
        espece=payload.espece,
        quantite=payload.quantite,
        prix=payload.prix,
        localisation=payload.localisation,
        statut=payload.statut,
    )
    return {"message": "Annonce créée.", **serialize_annonce_marche(annonce)}


__all__ = ["router"]
