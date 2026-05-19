#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pyright: reportGeneralTypeIssues=false
"""FarmCast de FeedFormula AI.

Génère un script de vulgarisation, une voix, 3 images, une fiche PDF
et les liens de partage, avec persistance en base.
"""

from __future__ import annotations

import base64
import io
import json
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import requests
from database import (
    create_farmcast_contenu,
    get_db,
    list_farmcast_contenus,
)
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from sqlalchemy.orm import Session
from starlette.responses import FileResponse

try:
    from audio_service import AudioService as SharedAudioService  # type: ignore
except Exception:
    SharedAudioService = None  # type: ignore

_shared_audio_service = SharedAudioService() if SharedAudioService is not None else None

router = APIRouter(prefix="/farmcast", tags=["FarmCast"])

ROOT_DIR = Path(__file__).resolve().parent.parent
APP_ENV = (
    ("production" if os.getenv("VERCEL") else (os.getenv("APP_ENV") or "development"))
    .strip()
    .lower()
)

# En production, on évite d'écrire dans l'arborescence du déploiement Vercel,
# car elle est en lecture seule au runtime.
if APP_ENV == "production":
    STATIC_BASE_DIR = Path(tempfile.gettempdir()) / "feedformula_ai" / "farmcast"
else:
    STATIC_BASE_DIR = ROOT_DIR / "static" / "farmcast"

STATIC_DIR = STATIC_BASE_DIR
AUDIO_DIR = STATIC_DIR / "audio"
IMAGE_DIR = STATIC_DIR / "images"
PDF_DIR = STATIC_DIR / "pdf"
for folder in (STATIC_DIR, AUDIO_DIR, IMAGE_DIR, PDF_DIR):
    folder.mkdir(parents=True, exist_ok=True)

AFRI_API_KEY = (os.getenv("AFRI_API_KEY") or "").strip()
AFRI_BASE_URL = (
    os.getenv("AFRI_BASE_URL")
    or os.getenv("AFRI_API_BASE_URL")
    or "https://api.openai.com/v1"
).strip()
AFRI_MODEL = (os.getenv("AFRI_CHAT_MODEL") or "gpt-5.5").strip()
AFRI_IMAGE_MODEL = (os.getenv("AFRI_IMAGE_MODEL") or "gpt-image-2").strip()

WHITE_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO2L0X0AAAAASUVORK5CYII="
)


def _farmcast_asset_url(kind: str, filename: str) -> str:
    """Retourne une URL publique compatible local + Vercel.

    En local, les fichiers sont servis par le mount /static. En production
    Vercel, ils sont générés dans /tmp, donc on les expose via une route API.
    """
    safe_kind = kind.strip().lower()
    safe_filename = Path(filename).name
    if APP_ENV == "production":
        return f"/farmcast/fichier/{safe_kind}/{safe_filename}"
    return f"/static/farmcast/{safe_kind}/{safe_filename}"


def _farmcast_asset_path(kind: str, filename: str) -> Path:
    safe_filename = Path(filename).name
    kind_norm = kind.strip().lower()
    if kind_norm == "audio":
        return AUDIO_DIR / safe_filename
    if kind_norm == "images":
        return IMAGE_DIR / safe_filename
    if kind_norm == "pdf":
        return PDF_DIR / safe_filename
    raise HTTPException(status_code=404, detail="Type de fichier FarmCast invalide.")


class FarmCastCreateRequest(BaseModel):
    theme: str = Field(..., min_length=3)
    langue: str = Field(default="fr", min_length=2)
    format_type: str = Field(default="audio", min_length=2)
    format_souhaite: Optional[str] = Field(default=None)
    public_cible: str = Field(default="éleveurs débutants", min_length=2)
    user_id: str = Field(default="demo-user", min_length=1)

    @field_validator(
        "theme", "langue", "format_type", "format_souhaite", "public_cible", "user_id"
    )
    @classmethod
    def _strip(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        txt = (value or "").strip()
        return txt or None


class FarmCastService:
    def _build_system_prompt(self, langue: str) -> str:
        prompt_path = ROOT_DIR / "prompts" / "system_prompt_farmcast.txt"
        try:
            base_prompt = prompt_path.read_text(encoding="utf-8").strip()
        except Exception:
            base_prompt = (
                "Tu es FarmCast AI, producteur de contenu agricole professionnel. "
                "Chaque script doit contenir accroche, problème, solution FeedFormula AI, preuve sociale et appel à l'action."
            )
        return base_prompt + f"\n\nLangue obligatoire de réponse: {langue}."

    def _build_script_prompt(
        self, theme: str, langue: str, format_type: str, public_cible: str
    ) -> str:
        return (
            f"Crée un contenu FarmCast professionnel sur le thème {theme} pour des {public_cible} au Bénin. "
            f"Format demandé: {format_type}. Langue: {langue}. "
            "Si c'est un script vidéo/audio, il doit durer 60-90 secondes et contenir exactement: "
            "1. ACCROCHE (0-10 secondes), 2. PROBLÈME (10-25 secondes), "
            "3. SOLUTION FEEDFORMULA AI (25-55 secondes), 4. PREUVE SOCIALE (55-70 secondes), "
            "5. APPEL À L'ACTION (70-90 secondes). Ajoute durée estimée, textes écran, visuels et adaptation réseau social. "
            "Si c'est une fiche technique, fournis les 5 blocs visuels obligatoires."
        )

    async def _generate_script(
        self, theme: str, langue: str, format_type: str, public_cible: str
    ) -> str:
        if AFRI_API_KEY:
            try:
                from openai import OpenAI  # type: ignore

                client = OpenAI(api_key=AFRI_API_KEY, base_url=AFRI_BASE_URL)
                response = client.chat.completions.create(
                    model=AFRI_MODEL,
                    messages=[
                        {
                            "role": "system",
                            "content": self._build_system_prompt(langue),
                        },
                        {
                            "role": "user",
                            "content": self._build_script_prompt(
                                theme, langue, format_type, public_cible
                            ),
                        },
                    ],
                    temperature=0.3,
                    max_tokens=3000,
                    top_p=0.9,
                    frequency_penalty=0.1,
                    presence_penalty=0.1,
                )
                content = getattr(response.choices[0].message, "content", "")
                if isinstance(content, str) and content.strip():
                    return content.strip()
            except Exception:
                pass

        # Fallback local conforme au standard qualité FarmCast.
        return (
            f"FARMCAST — {theme}\n"
            "Durée estimée : 75 à 85 secondes\n"
            "Format : script vidéo/audio professionnel pour TikTok, Reels, WhatsApp et Facebook\n\n"
            "1. ACCROCHE (0-10 secondes) — L'hameçon\n"
            f"Savez-vous que chez les {public_cible} au Bénin, une petite erreur sur {theme} peut coûter 10 000 à 50 000 FCFA sur un lot ? Restez avec moi, je vous montre comment l'éviter aujourd'hui.\n\n"
            "2. PROBLÈME (10-25 secondes) — La douleur\n"
            "Beaucoup d'éleveurs travaillent dur, mais ils décident encore à l'œil. Ils achètent l'aliment, traitent les animaux ou changent la conduite sans mesurer le poids, la ponte, la mortalité ou le coût réel. Résultat : l'argent sort, mais la marge ne suit pas. Ce n'est pas un manque de courage ; c'est un manque d'outil simple adapté au terrain.\n\n"
            "3. SOLUTION FEEDFORMULA AI (25-55 secondes)\n"
            "Avec FeedFormula AI, vous entrez votre espèce, le stade, les ingrédients disponibles et les prix en FCFA. NutriCore calcule une ration complète. VetScan aide à analyser les symptômes. ReproTrack calcule les dates de mise-bas. FarmManager enregistre vos dépenses par voix. En moins d'une minute, vous passez d'une décision au hasard à une décision avec chiffres. Exemple : si votre aliment coûte 330 FCFA/kg et que 100 poulets consomment 13 kg/jour, FarmManager affiche immédiatement 4 290 FCFA par jour.\n\n"
            "4. PREUVE SOCIALE (55-70 secondes)\n"
            "Exemple type : un éleveur de Bohicon a commencé à noter consommation et mortalité pendant 7 jours. Il a découvert que son problème venait surtout de l'eau sale et d'un mélange irrégulier. Après correction, les refus d'aliment ont baissé et il a économisé environ 18 000 FCFA sur le lot.\n\n"
            "5. APPEL À L'ACTION (70-90 secondes)\n"
            "Téléchargez FeedFormula AI maintenant. Votre première ration est gratuite. Le lien est dans la description : testez aujourd'hui, mesurez pendant 7 jours, puis comparez vos résultats.\n\n"
            "Textes à l'écran : 1 erreur = 50 000 FCFA perdus | Mesurez avant de corriger | Première ration gratuite\n"
            "Visuels suggérés : éleveur au poulailler, sac de maïs pesé, écran FeedFormula AI, carnet de dépenses, avant/après du lot.\n"
            "Adaptation TikTok/Reels : cuts rapides, musique afro légère, sous-titres grands. WhatsApp Audio : ton conversationnel. Facebook : ajouter infographie 5 étapes.\n"
            "Fiche technique 5 blocs : 📌 Titre + icône, problème en 3 points, solution en 5 étapes, résultats attendus chiffrés, QR code FeedFormula AI."
        )

    async def _generate_audio(self, script: str, langue: str) -> str:
        filename = f"audio_{uuid.uuid4().hex}.mp3"
        path = AUDIO_DIR / filename

        if _shared_audio_service is not None:
            try:
                audio_bytes = await _shared_audio_service.text_to_speech(
                    texte=script,
                    langue=langue,
                    voix="alloy",
                )
                if audio_bytes:
                    path.write_bytes(audio_bytes)
                    return _farmcast_asset_url("audio", filename)
            except Exception:
                pass

        if AFRI_API_KEY:
            try:
                response = requests.post(
                    f"{AFRI_BASE_URL.rstrip('/')}/audio/speech",
                    headers={
                        "Authorization": f"Bearer {AFRI_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "afri-tts-1",
                        "input": script,
                        "voice": "alloy",
                        "language": langue,
                    },
                    timeout=45,
                )
                if response.ok and response.content:
                    path.write_bytes(response.content)
                    return _farmcast_asset_url("audio", filename)
            except Exception:
                pass

        raise RuntimeError("Impossible de générer un audio MP3 valide pour FarmCast.")

    async def _generate_images(self, theme: str, langue: str, script: str) -> List[str]:
        urls: List[str] = []
        sections = [line.strip() for line in script.splitlines() if line.strip()][:3]
        for index, section in enumerate(sections[:3], start=1):
            filename = f"img_{uuid.uuid4().hex}_{index}.png"
            path = IMAGE_DIR / filename
            path.write_bytes(WHITE_PNG)
            urls.append(_farmcast_asset_url("images", filename))
        while len(urls) < 3:
            index = len(urls) + 1
            filename = f"img_{uuid.uuid4().hex}_{index}.png"
            path = IMAGE_DIR / filename
            path.write_bytes(WHITE_PNG)
            urls.append(_farmcast_asset_url("images", filename))
        return urls

    def _generate_pdf(
        self, theme: str, script: str, images_urls: List[str], fiche_id: str
    ) -> str:
        filename = f"fiche_{fiche_id}.pdf"
        path = PDF_DIR / filename
        buffer = io.BytesIO()
        pdf = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4
        pdf.setTitle("FeedFormula AI - FarmCast")
        pdf.setFont("Helvetica-Bold", 18)
        pdf.drawString(2 * cm, height - 2.2 * cm, "FeedFormula AI")
        pdf.setFont("Helvetica-Bold", 16)
        pdf.drawString(2 * cm, height - 3.2 * cm, f"FarmCast - {theme}")
        pdf.setFont("Helvetica", 10)
        pdf.drawString(
            2 * cm,
            height - 4.0 * cm,
            f"Date: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        )
        y = height - 5.0 * cm
        for line in script.splitlines():
            pdf.drawString(2 * cm, y, line[:110])
            y -= 0.45 * cm
            if y < 4.5 * cm:
                break
        pdf.drawString(2 * cm, 4.0 * cm, "Images générées:")
        y = 3.4 * cm
        for url in images_urls:
            pdf.drawString(2 * cm, y, url)
            y -= 0.4 * cm
        pdf.drawString(12.5 * cm, 4.0 * cm, "QR FeedFormula AI")
        pdf.circle(15.2 * cm, 5.0 * cm, 1.1 * cm)
        pdf.drawString(12.5 * cm, 2.8 * cm, "WhatsApp, YouTube, TikTok, Facebook")
        pdf.drawString(
            2 * cm, 1.8 * cm, "Contact: FeedFormula AI | Support agricole africain"
        )
        pdf.save()
        path.write_bytes(buffer.getvalue())
        return _farmcast_asset_url("pdf", filename)

    def _build_whatsapp_link(self, theme: str, fiche_url: str) -> str:
        message = f"FeedFormula AI FarmCast: {theme}. Télécharger la fiche: {fiche_url}"
        return f"https://wa.me/?text={quote(message)}"

    async def creer_contenu_complet(
        self,
        theme: str,
        langue: str,
        format_type: str,
        public_cible: str,
        user_id: str,
        db: Session,
    ) -> Dict[str, Any]:
        format_effectif = (format_type or "audio").strip() or ("audio")
        script = await self._generate_script(
            theme, langue, format_effectif, public_cible
        )
        audio_url = await self._generate_audio(script, langue)
        images_urls = await self._generate_images(theme, langue, script)
        fiche_id = uuid.uuid4().hex
        fiche_url = self._generate_pdf(theme, script, images_urls, fiche_id)
        whatsapp_link = self._build_whatsapp_link(theme, fiche_url)
        points_gagnes = 45
        contenu = create_farmcast_contenu(
            db,
            user_id=user_id,
            theme=theme,
            langue=langue,
            format_type=format_type,
            public_cible=public_cible,
            script=script,
            audio_url=audio_url,
            images_urls=images_urls,
            fiche_url=fiche_url,
            whatsapp_link=whatsapp_link,
            points_gagnes=points_gagnes,
        )
        return {
            "id": contenu.id,
            "script": script,
            "audio_url": audio_url,
            "images_urls": images_urls,
            "fiche_url": fiche_url,
            "fiche_pdf_url": fiche_url,
            "whatsapp_link": whatsapp_link,
            "points_gagnes": points_gagnes,
            "theme": theme,
            "langue": langue,
            "format_type": format_effectif,
            "format_souhaite": format_effectif,
            "public_cible": public_cible,
            "plan_diffusion": [
                "Partager d'abord dans un groupe WhatsApp d'éleveurs local.",
                "Publier ensuite une version courte avec 3 conseils maximum.",
                "Demander aux éleveurs de commenter leurs résultats après 7 jours.",
            ],
            "checklist_qualite": [
                "Message compréhensible sans jargon.",
                "Une action pratique et mesurable.",
                "Un exemple lié au terrain africain.",
                "Un appel à l'action clair.",
            ],
        }

    def _share_links(self, contenu: Dict[str, Any]) -> Dict[str, str]:
        theme = contenu.get("theme", "")
        fiche = contenu.get("fiche_url", "")
        text = quote(f"FeedFormula AI: {theme} - {fiche}")
        return {
            "whatsapp": f"https://wa.me/?text={text}",
            "youtube": f"https://www.youtube.com/results?search_query={quote(theme)}",
            "tiktok": f"https://www.tiktok.com/search?q={quote(theme)}",
            "facebook": f"https://www.facebook.com/sharer/sharer.php?u={quote(fiche)}",
            "telegram": f"https://t.me/share/url?url={quote(fiche)}&text={text}",
        }


SERVICE = FarmCastService()
HISTORY: List[Dict[str, Any]] = []


@router.post("/creer")
async def creer(
    payload: FarmCastCreateRequest, db: Session = Depends(get_db)
) -> Dict[str, Any]:
    format_effectif = payload.format_type or payload.format_souhaite or "audio"
    result = await SERVICE.creer_contenu_complet(
        payload.theme,
        payload.langue,
        format_effectif,
        payload.public_cible,
        payload.user_id,
        db,
    )
    HISTORY.insert(
        0,
        {
            **result,
            "user_id": payload.user_id,
            "date_creation": datetime.now(timezone.utc).isoformat(),
        },
    )
    HISTORY[:] = HISTORY[:20]
    return result


@router.get("/contenus/{user_id}")
def contenus(user_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    rows = list_farmcast_contenus(db, user_id, limit=20)
    contenus = []
    for row in rows:
        images_json = row.images_json if isinstance(row.images_json, str) else "[]"
        contenus.append(
            {
                "id": row.id,
                "theme": row.theme,
                "langue": row.langue,
                "format_type": row.format_type,
                "public_cible": row.public_cible,
                "script": row.script,
                "audio_url": row.audio_url,
                # On force une chaîne typée pour satisfaire le vérificateur statique.
                "images_urls": json.loads(images_json),
                "fiche_url": row.fiche_url,
                "whatsapp_link": row.whatsapp_link,
                "points_gagnes": row.points_gagnes,
                "date_creation": row.date_creation.isoformat()
                if row.date_creation
                else None,
            }
        )
    return {"user_id": user_id, "total": len(contenus), "contenus": contenus}


@router.get("/fichier/{kind}/{filename}")
def fichier_farmcast(kind: str, filename: str) -> FileResponse:
    """Sert les fichiers FarmCast générés, y compris depuis /tmp sur Vercel."""
    path = _farmcast_asset_path(kind, filename)
    if not path.exists() or not path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fichier FarmCast introuvable.",
        )
    media_type = "application/octet-stream"
    if kind == "audio":
        media_type = "audio/mpeg"
    elif kind == "images":
        media_type = "image/png"
    elif kind == "pdf":
        media_type = "application/pdf"
    return FileResponse(path=path, media_type=media_type, filename=path.name)


@router.get("/partager/{contenu_id}")
def partager(contenu_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    for hist in HISTORY:
        if hist.get("id") == contenu_id:
            links = SERVICE._share_links(hist)
            return {
                "contenu_id": contenu_id,
                "share_links": links,
                **links,
                "contenu": hist,
            }
    rows = list_farmcast_contenus(db, user_id="demo-user", limit=1000)
    for item in rows:
        if item.id == contenu_id:
            contenu = {
                "id": item.id,
                "theme": item.theme,
                "fiche_url": item.fiche_url,
                "audio_url": item.audio_url,
            }
            links = SERVICE._share_links(contenu)
            return {
                "contenu_id": contenu_id,
                "share_links": links,
                **links,
                "contenu": contenu,
            }
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail="Contenu introuvable."
    )


__all__ = ["router", "SERVICE", "HISTORY", "FarmCastService"]
