#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Service audio de FeedFormula AI.

Fonctionnalités :
- Synthèse vocale TTS via API Afri avec fallback gTTS
- Transcription audio STT via API Afri
- Résumé vocal court d'une ration
- Routeur FastAPI prêt à être branché dans `main.py`

Toutes les erreurs sont gérées avec des messages explicites en français.
"""

from __future__ import annotations

import asyncio
import io
import json
import os
import re
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------

AFRI_BASE_URL = (
    os.getenv("AFRI_BASE_URL")
    or os.getenv("AFRI_API_BASE_URL")
    or "https://build.lewisnote.com/v1"
).rstrip("/")

AFRI_API_KEY = (os.getenv("AFRI_API_KEY") or "").strip()
AFRI_TTS_MODEL = (os.getenv("AFRI_TTS_MODEL") or "afri-tts-1").strip()
AFRI_STT_MODEL = (os.getenv("AFRI_STT_MODEL") or "afri-stt-1").strip()
AFRI_TIMEOUT_SECONDS = float(os.getenv("AFRI_TIMEOUT_SECONDS") or "90")

# -----------------------------------------------------------------------------
# Imports optionnels
# -----------------------------------------------------------------------------

try:
    from gtts import gTTS  # type: ignore
except Exception:
    gTTS = None  # type: ignore


# -----------------------------------------------------------------------------
# Schémas Pydantic
# -----------------------------------------------------------------------------

class SyntheseRequest(BaseModel):
    """Schéma d'entrée pour la synthèse vocale."""

    texte: str = Field(..., min_length=1, description="Texte à lire")
    langue: str = Field(default="fr", description="Code langue")
    voix: str = Field(default="africaine", description="Nom de la voix")


class SyntheseResponse(BaseModel):
    """Réponse logique de synthèse."""

    message: str
    langue: str
    taille_octets: int


class TranscriptionResponse(BaseModel):
    """Réponse logique de transcription."""

    texte: str
    langue_detectee: str


# -----------------------------------------------------------------------------
# Utilitaires
# -----------------------------------------------------------------------------

def _nettoyer_texte(texte: str) -> str:
    """Nettoie un texte pour la synthèse vocale."""
    if not isinstance(texte, str):
        return ""
    return " ".join(texte.strip().split())


def _normaliser_langue(langue: str) -> str:
    """Normalise un code langue vers un format simple."""
    if not langue:
        return "fr"
    lg = langue.strip().lower()
    return lg or "fr"


def _extract_response_bytes(response: Any) -> bytes:
    """Extrait les octets depuis une réponse HTTP de bibliothèque standard."""
    if hasattr(response, "read"):
        return response.read()
    if hasattr(response, "content"):
        return bytes(response.content)
    return b""


def _http_post_json(url: str, payload: Dict[str, Any], timeout: float) -> Dict[str, Any]:
    """
    Envoie une requête POST JSON via la bibliothèque standard.

    Cette implémentation permet de limiter les dépendances externes.
    """
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if AFRI_API_KEY:
        headers["Authorization"] = f"Bearer {AFRI_API_KEY}"

    request = urllib.request.Request(url=url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read()
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))


def _http_post_multipart_audio(
    url: str,
    audio_bytes: bytes,
    filename: str,
    content_type: str,
    extra_fields: Optional[Dict[str, str]] = None,
    timeout: float = AFRI_TIMEOUT_SECONDS,
) -> Dict[str, Any]:
    """
    Envoie un fichier audio en multipart/form-data via la bibliothèque standard.
    """
    boundary = "----FeedFormulaBoundary7d3c9f"
    crlf = "\r\n"
    parts = []

    def add_field(name: str, value: str) -> None:
        parts.append(f"--{boundary}{crlf}".encode("utf-8"))
        parts.append(
            f'Content-Disposition: form-data; name="{name}"{crlf}{crlf}{value}{crlf}'.encode(
                "utf-8"
            )
        )

    if extra_fields:
        for key, value in extra_fields.items():
            add_field(key, value)

    parts.append(f"--{boundary}{crlf}".encode("utf-8"))
    parts.append(
        (
            f'Content-Disposition: form-data; name="file"; filename="{filename}"{crlf}'
            f"Content-Type: {content_type or 'application/octet-stream'}{crlf}{crlf}"
        ).encode("utf-8")
    )
    parts.append(audio_bytes)
    parts.append(crlf.encode("utf-8"))
    parts.append(f"--{boundary}--{crlf}".encode("utf-8"))

    body = b"".join(parts)
    headers = {
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "Accept": "application/json",
    }
    if AFRI_API_KEY:
        headers["Authorization"] = f"Bearer {AFRI_API_KEY}"

    request = urllib.request.Request(url=url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read()
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))


def _fallback_tts_gtts(texte: str, langue: str) -> bytes:
    """
    Fallback local avec gTTS si l'API Afri est indisponible.
    """
    if gTTS is None:
        raise RuntimeError(
            "Le fallback gTTS n'est pas disponible. Installez le package 'gTTS' "
            "ou configurez correctement l'API Afri."
        )

    buffer = io.BytesIO()
    tts = gTTS(text=texte, lang=langue if langue else "fr")
    tts.write_to_fp(buffer)
    return buffer.getvalue()


def _extraire_texte_depuis_reponse(response: Dict[str, Any]) -> str:
    """
    Essaie d'extraire le texte depuis une réponse Afri STT.
    """
    if not isinstance(response, dict):
        return ""

    for key in ("texte", "text", "transcript", "transcription"):
        value = response.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    data = response.get("data")
    if isinstance(data, dict):
        for key in ("texte", "text", "transcript"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

    return ""


# -----------------------------------------------------------------------------
# Service principal
# -----------------------------------------------------------------------------

@dataclass
class AudioService:
    """
    Service audio complet.

    Les méthodes sont `async` pour s'intégrer proprement à FastAPI,
    tout en s'appuyant sur des appels réseau synchrones exécutés dans un thread.
    """

    afr_base_url: str = AFRI_BASE_URL
    afr_api_key: str = AFRI_API_KEY
    tts_model: str = AFRI_TTS_MODEL
    stt_model: str = AFRI_STT_MODEL
    timeout_seconds: float = AFRI_TIMEOUT_SECONDS

    async def text_to_speech(
        self,
        texte: str,
        langue: str,
        voix: str = "africaine",
    ) -> bytes:
        """
        Convertit un texte en audio MP3.

        Priorité :
        1) API Afri
        2) gTTS en fallback
        """
        texte_nettoye = _nettoyer_texte(texte)
        if not texte_nettoye:
            raise ValueError("Le texte à synthétiser est vide.")

        langue_norm = _normaliser_langue(langue)
        url = f"{self.afr_base_url}/audio/speech"

        payload = {
            "model": self.tts_model,
            "input": texte_nettoye,
            "voice": voix or "africaine",
            "language": langue_norm,
        }

        try:
            result = await asyncio.to_thread(
                _http_post_json,
                url,
                payload,
                self.timeout_seconds,
            )

            # Certains fournisseurs renvoient soit une URL, soit du base64,
            # soit un chemin local. On gère les cas les plus probables.
            if isinstance(result, dict):
                audio_b64 = result.get("audio_base64") or result.get("audio_b64")
                if isinstance(audio_b64, str) and audio_b64.strip():
                    import base64

                    return base64.b64decode(audio_b64)

                audio_url = result.get("audio_url") or result.get("url")
                if isinstance(audio_url, str) and audio_url.strip():
                    with urllib.request.urlopen(audio_url, timeout=self.timeout_seconds) as response:
                        return response.read()

                audio_path = result.get("audio_path") or result.get("path")
                if isinstance(audio_path, str) and audio_path.strip() and os.path.exists(audio_path):
                    with open(audio_path, "rb") as f:
                        return f.read()

            # Si l'API répond mais sans payload exploitable, on bascule sur gTTS.
            return await asyncio.to_thread(_fallback_tts_gtts, texte_nettoye, langue_norm)

        except Exception:
            # Fallback silencieux mais robuste
            return await asyncio.to_thread(_fallback_tts_gtts, texte_nettoye, langue_norm)

    async def speech_to_text(
        self,
        audio_bytes: bytes,
        langue: str = "auto",
        filename: str = "audio.webm",
        content_type: str = "application/octet-stream",
    ) -> Dict[str, Any]:
        """
        Transcrit un flux audio en texte.
        """
        if not audio_bytes:
            raise ValueError("Le fichier audio est vide.")

        url = f"{self.afr_base_url}/audio/transcriptions"
        langue_norm = _normaliser_langue(langue)

        def _call() -> Dict[str, Any]:
            payload = {
                "model": self.stt_model,
                "language": langue_norm,
            }
            response = _http_post_multipart_audio(
                url=url,
                audio_bytes=audio_bytes,
                filename=filename or "audio.webm",
                content_type=content_type or "application/octet-stream",
                extra_fields=payload,
                timeout=self.timeout_seconds,
            )
            return response

        try:
            response = await asyncio.to_thread(_call)
            texte = _extraire_texte_depuis_reponse(response)
            langue_detectee = (
                response.get("langue_detectee")
                or response.get("language")
                or response.get("langue")
                or langue_norm
            )
            return {
                "texte": texte,
                "langue_detectee": str(langue_detectee or langue_norm).strip(),
                "brut": response,
            }
        except Exception as exc:
            raise RuntimeError(f"Transcription impossible: {exc}") from exc

    def resumer_ration_pour_audio(self, ration_texte: str) -> str:
        """
        Extrait un résumé court et oralement fluide d'une ration.

        Objectif : un format lisible en moins de 30 secondes.
        """
        texte = _nettoyer_texte(ration_texte)
        if not texte:
            return "Aucune ration disponible pour le résumé audio."

        # Extraction simple des lignes importantes
        lignes = [ligne.strip() for ligne in ration_texte.splitlines() if ligne.strip()]
        lignes_utiles = []

        for ligne in lignes:
            ligne_norm = ligne.lower()
            if any(
                mot in ligne_norm
                for mot in (
                    "animal",
                    "animaux",
                    "coût",
                    "cout",
                    "kg",
                    "ingrédient",
                    "ingredient",
                    "composition",
                    "protéines",
                    "proteines",
                    "ration",
                )
            ):
                lignes_utiles.append(ligne)

        if not lignes_utiles:
            lignes_utiles = lignes[:4]

        resume = " ".join(lignes_utiles[:6])
        resume = re.sub(r"\s+", " ", resume).strip()

        # On ajoute une phrase de clôture pour garder un ton positif.
        if not resume.endswith("."):
            resume += "."
        resume += " Bonne production !"

        return resume[:900]


# -----------------------------------------------------------------------------
# Routeur FastAPI
# -----------------------------------------------------------------------------

router = APIRouter(prefix="/audio", tags=["Audio"])
audio_service = AudioService()


class _SyntheseBody(BaseModel):
    """Schéma de la route /audio/synthese."""

    texte: str = Field(..., min_length=1)
    langue: str = Field(default="fr")


@router.post("/synthese")
async def synthese_audio(payload: _SyntheseBody) -> StreamingResponse:
    """
    Génère un fichier audio MP3 à partir d'un texte.

    Retourne un flux binaire directement téléchargeable par le frontend.
    """
    try:
        audio_bytes = await audio_service.text_to_speech(
            texte=payload.texte,
            langue=payload.langue,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Erreur synthèse audio: {exc}")

    def _stream() -> bytes:
        return audio_bytes

    headers = {
        "Content-Disposition": 'inline; filename="feedformula_audio.mp3"',
        "Cache-Control": "no-store",
    }
    return StreamingResponse(
        io.BytesIO(_stream()),
        media_type="audio/mpeg",
        headers=headers,
    )


@router.post("/transcription")
async def transcription_audio(
    audio: UploadFile = File(...),
    langue: str = Form(default="auto"),
) -> Dict[str, Any]:
    """
    Transcrit un fichier audio multipart.
    """
    if not audio:
        raise HTTPException(status_code=400, detail="Aucun fichier audio reçu.")

    try:
        contenu = await audio.read()
        resultat = await audio_service.speech_to_text(
            audio_bytes=contenu,
            langue=langue,
            filename=audio.filename or "audio.webm",
            content_type=audio.content_type or "application/octet-stream",
        )
        return {
            "texte": resultat.get("texte", ""),
            "langue_detectee": resultat.get("langue_detectee", "auto"),
        }
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erreur transcription audio: {exc}")


__all__ = [
    "AudioService",
    "audio_service",
    "router",
    "SyntheseRequest",
    "SyntheseResponse",
    "TranscriptionResponse",
]
