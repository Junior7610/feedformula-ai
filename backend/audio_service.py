#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Service audio complet de FeedFormula AI.

Fonctionnalités:
- Synthèse vocale TTS via API Afri, avec fallback gTTS
- Transcription audio STT via API Afri, avec fallback Whisper via la même API
- Résumé vocal court d'une ration, optimisé pour la lecture audio
- Génération d'audios de démonstration par langue
- Routeur FastAPI prêt à être branché dans `main.py`

Le module privilégie les dépendances standard pour rester robuste en environnement
de déploiement, et il expose des erreurs claires en français.
"""

from __future__ import annotations

import asyncio
import base64
import io
import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------

ROOT_DIR = Path(__file__).resolve().parent.parent
ASSETS_DIR = ROOT_DIR / "assets"

AFRI_BASE_URL = (
    os.getenv("AFRI_BASE_URL")
    or os.getenv("AFRI_API_BASE_URL")
    or "https://build.lewisnote.com/v1"
).rstrip("/")

AFRI_API_KEY = (os.getenv("AFRI_API_KEY") or "").strip()
AFRI_TTS_MODEL = (os.getenv("AFRI_TTS_MODEL") or "afri-tts-1").strip()
AFRI_STT_MODEL = (os.getenv("AFRI_STT_MODEL") or "afri-stt-1").strip()
AFRI_CHAT_MODEL = (os.getenv("AFRI_CHAT_MODEL") or "gpt-5.5").strip()
AFRI_TIMEOUT_SECONDS = float(os.getenv("AFRI_TIMEOUT_SECONDS") or "90")

LANGUES_DEMO = {"fr", "fon", "yor", "en", "den", "adj"}

# -----------------------------------------------------------------------------
# Imports optionnels
# -----------------------------------------------------------------------------

try:
    from gtts import gTTS  # type: ignore
except Exception:
    gTTS = None  # type: ignore

try:
    from openai import (
        APIConnectionError,
        APITimeoutError,
        AuthenticationError,
        BadRequestError,
        OpenAI,
        OpenAIError,
    )
except Exception:
    OpenAI = None  # type: ignore

    class AuthenticationError(Exception):
        pass

    class APIConnectionError(Exception):
        pass

    class APITimeoutError(Exception):
        pass

    class BadRequestError(Exception):
        pass

    class OpenAIError(Exception):
        pass

try:
    from langue_detector import detecter_langue
except Exception:
    def detecter_langue(texte: str) -> str:  # type: ignore
        return "fr"


# -----------------------------------------------------------------------------
# Schémas
# -----------------------------------------------------------------------------

class SyntheseRequest(BaseModel):
    texte: str = Field(..., min_length=1, description="Texte à lire")
    langue: str = Field(default="fr", description="Code langue")
    voix: str = Field(default="alloy", description="Nom de la voix")


class TranscriptionResponse(BaseModel):
    texte: str
    langue_detectee: str


class RationVocaleRequest(BaseModel):
    ration_texte: str = Field(..., min_length=1)
    langue: str = Field(default="fr")


# -----------------------------------------------------------------------------
# Utilitaires
# -----------------------------------------------------------------------------

def _nettoyer_texte(texte: str) -> str:
    if not isinstance(texte, str):
        return ""
    return " ".join(texte.strip().split())


def _normaliser_langue(langue: str) -> str:
    lg = (langue or "fr").strip().lower()
    return lg or "fr"


def _gtts_langue(langue: str) -> str:
    """
    Mappe une langue cible vers un code gTTS raisonnable.
    Si la langue n'est pas supportée, on retombe sur le français.
    """
    langue = _normaliser_langue(langue)
    mapping = {
        "fr": "fr",
        "en": "en",
        "yor": "yo",
        "yo": "yo",
        "fon": "fr",
        "den": "fr",
        "adj": "fr",
    }
    return mapping.get(langue, langue[:2] or "fr")


def _json_dumps(data: Dict[str, Any]) -> bytes:
    return json.dumps(data, ensure_ascii=False).encode("utf-8")


def _http_request(
    url: str,
    *,
    method: str,
    headers: Dict[str, str],
    body: Optional[bytes] = None,
    timeout: float = AFRI_TIMEOUT_SECONDS,
) -> Tuple[bytes, str, int]:
    request = urllib.request.Request(url=url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        content_type = (response.headers.get("content-type") or "").lower()
        status = getattr(response, "status", 200)
        return response.read(), content_type, status


def _http_post_json(url: str, payload: Dict[str, Any], timeout: float) -> Tuple[bytes, str, int]:
    headers = {
        "Content-Type": "application/json",
        "Accept": "*/*",
    }
    if AFRI_API_KEY:
        headers["Authorization"] = f"Bearer {AFRI_API_KEY}"
    return _http_request(
        url,
        method="POST",
        headers=headers,
        body=_json_dumps(payload),
        timeout=timeout,
    )


def _http_post_multipart(
    url: str,
    *,
    fields: Dict[str, str],
    file_bytes: bytes,
    filename: str,
    content_type: str,
    timeout: float,
) -> Tuple[bytes, str, int]:
    boundary = "----FeedFormulaAudioBoundary7d3c9f"
    crlf = "\r\n"
    parts = []

    def add_field(name: str, value: str) -> None:
        parts.append(f"--{boundary}{crlf}".encode("utf-8"))
        parts.append(
            (
                f'Content-Disposition: form-data; name="{name}"{crlf}{crlf}'
                f"{value}{crlf}"
            ).encode("utf-8")
        )

    for key, value in fields.items():
        if value is not None:
            add_field(key, str(value))

    parts.append(f"--{boundary}{crlf}".encode("utf-8"))
    parts.append(
        (
            f'Content-Disposition: form-data; name="file"; filename="{filename or "audio.webm"}"{crlf}'
            f"Content-Type: {content_type or 'application/octet-stream'}{crlf}{crlf}"
        ).encode("utf-8")
    )
    parts.append(file_bytes)
    parts.append(crlf.encode("utf-8"))
    parts.append(f"--{boundary}--{crlf}".encode("utf-8"))

    headers = {
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "Accept": "*/*",
    }
    if AFRI_API_KEY:
        headers["Authorization"] = f"Bearer {AFRI_API_KEY}"

    return _http_request(
        url,
        method="POST",
        headers=headers,
        body=b"".join(parts),
        timeout=timeout,
    )


def _response_to_audio_bytes(raw: bytes, content_type: str) -> bytes:
    if not raw:
        return b""

    if "audio/" in content_type or "application/octet-stream" in content_type:
        return raw

    try:
        payload = json.loads(raw.decode("utf-8"))
    except Exception:
        return raw

    if isinstance(payload, dict):
        for key in ("audio", "audio_bytes", "content"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                try:
                    return base64.b64decode(value)
                except Exception:
                    pass

        for key in ("audio_base64", "audio_b64", "b64_json"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                try:
                    return base64.b64decode(value)
                except Exception:
                    pass

        for key in ("audio_url", "url"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                with urllib.request.urlopen(value, timeout=AFRI_TIMEOUT_SECONDS) as resp:
                    return resp.read()

        for key in ("audio_path", "path"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip() and os.path.exists(value):
                with open(value, "rb") as f:
                    return f.read()

    return raw


def _extract_text_from_stt_response(response: Dict[str, Any]) -> str:
    if not isinstance(response, dict):
        return ""

    for key in ("texte", "text", "transcript", "transcription"):
        value = response.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    data = response.get("data")
    if isinstance(data, dict):
        for key in ("texte", "text", "transcript", "transcription"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

    choices = response.get("choices")
    if isinstance(choices, list) and choices:
        first = choices[0]
        if isinstance(first, dict):
            for key in ("text", "transcript"):
                value = first.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()

    return ""


def _extract_language_from_stt_response(response: Dict[str, Any], fallback: str = "fr") -> str:
    if not isinstance(response, dict):
        return fallback

    for key in ("langue_detectee", "language", "langue", "lang"):
        value = response.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip().lower()

    data = response.get("data")
    if isinstance(data, dict):
        for key in ("langue_detectee", "language", "langue", "lang"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip().lower()

    return fallback


def _parse_json_payload(raw: bytes) -> Dict[str, Any]:
    try:
        payload = json.loads(raw.decode("utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _fallback_tts_gtts(texte: str, langue: str) -> bytes:
    if gTTS is None:
        raise RuntimeError(
            "Le fallback gTTS n'est pas disponible. Installez le package 'gTTS' "
            "ou configurez correctement l'API Afri."
        )

    buffer = io.BytesIO()
    tts = gTTS(text=texte, lang=_gtts_langue(langue))
    tts.write_to_fp(buffer)
    return buffer.getvalue()


def _build_openai_client() -> Optional[Any]:
    if OpenAI is None:
        return None

    api_key = AFRI_API_KEY or os.getenv("OPENAI_API_KEY") or ""
    base_url = AFRI_BASE_URL or None
    try:
        if base_url and api_key:
            return OpenAI(api_key=api_key, base_url=base_url)
        if api_key:
            return OpenAI(api_key=api_key)
        if base_url:
            return OpenAI(base_url=base_url)
    except Exception:
        return None
    return None


def _extract_openai_text(response: Any) -> str:
    if response is None:
        return ""

    for attr in ("output_text",):
        value = getattr(response, attr, None)
        if isinstance(value, str) and value.strip():
            return value.strip()

    if hasattr(response, "model_dump"):
        try:
            payload = response.model_dump()
            if isinstance(payload, dict):
                found = _find_first_text(payload)
                if found:
                    return found
        except Exception:
            pass

    if isinstance(response, dict):
        found = _find_first_text(response)
        if found:
            return found

    raw = str(response).strip()
    return raw


def _find_first_text(node: Any) -> str:
    if isinstance(node, dict):
        for key in ("text", "output_text", "content", "message"):
            value = node.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

        for value in node.values():
            found = _find_first_text(value)
            if found:
                return found

    elif isinstance(node, list):
        for item in node:
            found = _find_first_text(item)
            if found:
                return found

    elif isinstance(node, str) and node.strip():
        return node.strip()

    return ""


def _translate_text_with_gpt(
    texte_source: str,
    langue_cible: str,
    *,
    source_langue: str = "fr",
) -> str:
    langue_cible = _normaliser_langue(langue_cible)
    if langue_cible == source_langue:
        return texte_source

    client = _build_openai_client()
    if client is None:
        return texte_source

    prompt = (
        "Tu es un traducteur professionnel pour une application vocale agricole.\n"
        f"Traduis fidèlement le texte ci-dessous du {source_langue} vers {langue_cible}.\n"
        "Contraintes:\n"
        "- garde les noms propres inchangés\n"
        "- conserve les montants, les unités et les chiffres\n"
        "- style oral, naturel, fluide\n"
        "- n'ajoute aucun commentaire\n"
        "- renvoie uniquement le texte traduit\n\n"
        f"TEXTE:\n{texte_source}"
    )

    try:
        response = client.responses.create(
            model=AFRI_CHAT_MODEL,
            input=prompt,
        )
        translated = _extract_openai_text(response).strip()
        return translated or texte_source
    except Exception:
        return texte_source


def _extraire_infos_ration(ration_texte: str) -> Dict[str, Any]:
    texte = ration_texte or ""
    lignes = [ligne.strip() for ligne in texte.splitlines() if ligne.strip()]

    infos: Dict[str, Any] = {
        "espece": "",
        "stade": "",
        "ingredients": [],
        "cout": "",
        "performances": "",
    }

    regex_header = re.compile(
        r"pour\s+(?P<nb>\d+)\s+(?P<espece>.+?)\s+au\s+stade\s+(?P<stade>.+?)(?:\.|$)",
        re.IGNORECASE,
    )
    regex_ing = re.compile(
        r"^(?P<nom>[^:]+?)\s*:\s*(?P<qte>[\d.,]+)\s*(?P<unite>kilogrammes?|kg|g|grammes?)",
        re.IGNORECASE,
    )
    regex_cout = re.compile(
        r"coût\s+total.*?([0-9][0-9\s.,]*)\s*francs?\s*cfa",
        re.IGNORECASE,
    )
    regex_perf = re.compile(r"performances?\s+attendues?\s*:\s*(.+)$", re.IGNORECASE)

    for ligne in lignes:
        if not infos["espece"]:
            m = regex_header.search(ligne)
            if m:
                infos["espece"] = m.group("espece").strip()
                infos["stade"] = m.group("stade").strip()
                continue

        if regex_ing.search(ligne):
            m = regex_ing.search(ligne)
            if m:
                infos["ingredients"].append(
                    {
                        "nom": m.group("nom").strip().rstrip("."),
                        "quantite": m.group("qte").strip(),
                        "unite": m.group("unite").strip(),
                    }
                )
                continue

        if not infos["cout"]:
            m = regex_cout.search(ligne)
            if m:
                infos["cout"] = m.group(1).strip()
                continue

        if not infos["performances"]:
            m = regex_perf.search(ligne)
            if m:
                infos["performances"] = m.group(1).strip().rstrip(".")
                continue

    if not infos["ingredients"]:
        for ligne in lignes[:5]:
            if ":" in ligne:
                left, right = ligne.split(":", 1)
                if len(left.strip()) <= 40 and any(ch.isdigit() for ch in right):
                    infos["ingredients"].append(
                        {
                            "nom": left.strip().rstrip("."),
                            "quantite": right.strip(),
                            "unite": "",
                        }
                    )

    return infos


def _trim_words(text: str, max_words: int = 200) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text.strip()
    return " ".join(words[:max_words]).strip()


def _build_demo_text_fr() -> str:
    return (
        "Bonjour, je suis Aya, votre assistante agricole. "
        "FeedFormula AI génère votre ration en 30 secondes. "
        "Voici un exemple pour 50 poulets de chair : "
        "Maïs : 74 kilogrammes. "
        "Tourteau de soja : 9 kilogrammes. "
        "Farine de poisson : 17 kilogrammes. "
        "Coût total pour 7 jours : 13 462 francs CFA. "
        "FeedFormula AI. L'intelligence africaine au service de vos animaux."
    )


# -----------------------------------------------------------------------------
# Service principal
# -----------------------------------------------------------------------------

@dataclass
class AudioService:
    afr_base_url: str = AFRI_BASE_URL
    afr_api_key: str = AFRI_API_KEY
    tts_model: str = AFRI_TTS_MODEL
    stt_model: str = AFRI_STT_MODEL
    chat_model: str = AFRI_CHAT_MODEL
    timeout_seconds: float = AFRI_TIMEOUT_SECONDS

    async def text_to_speech(
        self,
        texte: str,
        langue: str = "fr",
        voix: str = "alloy",
    ) -> bytes:
        """
        Convertit un texte en audio MP3.

        Priorité:
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
            "voice": voix or "alloy",
            "language": langue_norm,
        }

        def _call_afri() -> bytes:
            raw, content_type, _ = _http_post_json(url, payload, self.timeout_seconds)
            return _response_to_audio_bytes(raw, content_type)

        try:
            audio_bytes = await asyncio.to_thread(_call_afri)
            if audio_bytes:
                return audio_bytes
            raise RuntimeError("Réponse audio vide depuis l'API Afri.")
        except Exception:
            try:
                return await asyncio.to_thread(_fallback_tts_gtts, texte_nettoye, langue_norm)
            except Exception as exc:
                raise RuntimeError(f"Synthèse vocale impossible: {exc}") from exc

    async def speech_to_text(
        self,
        audio_bytes: bytes,
        langue: str = "auto",
        filename: str = "audio.webm",
        content_type: str = "application/octet-stream",
    ) -> Dict[str, Any]:
        """
        Transcrit un flux audio en texte.

        Priorité:
        1) API Afri avec modèle courant
        2) Fallback sur Whisper-1 via la même API Afri
        """
        if not audio_bytes:
            raise ValueError("Le fichier audio est vide.")

        langue_norm = _normaliser_langue(langue)
        url = f"{self.afr_base_url}/audio/transcriptions"

        async def _try_model(model: str) -> Dict[str, Any]:
            def _call() -> Dict[str, Any]:
                fields = {"model": model}
                if langue_norm and langue_norm != "auto":
                    fields["language"] = langue_norm

                raw, content_type, _ = _http_post_multipart(
                    url,
                    fields=fields,
                    file_bytes=audio_bytes,
                    filename=filename or "audio.webm",
                    content_type=content_type or "application/octet-stream",
                    timeout=self.timeout_seconds,
                )

                if "application/json" not in content_type:
                    try:
                        payload = json.loads(raw.decode("utf-8"))
                    except Exception:
                        payload = {}
                else:
                    payload = _parse_json_payload(raw)

                if not isinstance(payload, dict):
                    payload = {}

                texte = _extract_text_from_stt_response(payload)
                if not texte and raw and b"{" in raw:
                    payload = _parse_json_payload(raw)
                    texte = _extract_text_from_stt_response(payload)

                return {
                    "payload": payload,
                    "texte": texte.strip(),
                    "langue": _extract_language_from_stt_response(payload, fallback=langue_norm),
                }

            return await asyncio.to_thread(_call)

        try:
            resultat = await _try_model(self.stt_model)
            texte = resultat["texte"]
            if not texte:
                raise RuntimeError("Transcription vide renvoyée par l'API Afri.")

            langue_detectee = resultat["langue"] or "fr"
            if langue_detectee == "fr" and langue_norm not in {"fr", "auto"}:
                langue_detectee = detecter_langue(texte) if texte else langue_norm

            return {
                "texte": texte,
                "langue_detectee": langue_detectee,
                "brut": resultat["payload"],
            }

        except Exception:
            # Fallback Whisper-1 via la même API
            try:
                resultat = await _try_model("whisper-1")
                texte = resultat["texte"]
                if not texte:
                    raise RuntimeError("Transcription vide même avec Whisper-1.")

                langue_detectee = resultat["langue"] or "fr"
                if langue_detectee == "fr" and texte:
                    langue_detectee = detecter_langue(texte)

                return {
                    "texte": texte,
                    "langue_detectee": langue_detectee,
                    "brut": resultat["payload"],
                }
            except Exception as exc:
                raise RuntimeError(f"Transcription impossible: {exc}") from exc

    def resumer_ration_pour_audio(self, ration_texte: str, langue: str = "fr") -> str:
        """
        Extrait un résumé court et oralement fluide d'une ration.

        Le résumé final est limité à 200 mots et reste adapté à la lecture vocale.
        Si la langue demandée n'est pas le français, la traduction est tentée via GPT 5.5.
        """
        texte = _nettoyer_texte(ration_texte)
        if not texte:
            return "Aucune ration disponible pour le résumé audio."

        infos = _extraire_infos_ration(ration_texte)
        langue_norm = _normaliser_langue(langue)

        lignes = []
        lignes.append("Aya vous présente votre ration.")

        if infos.get("espece") or infos.get("stade"):
            espece = infos.get("espece") or "votre espèce"
            stade = infos.get("stade") or "stade non précisé"
            lignes.append(f"Pour {espece} au stade {stade}.")

        if infos.get("ingredients"):
            for item in infos["ingredients"][:4]:
                nom = item.get("nom") or "Ingrédient"
                qte = item.get("quantite") or ""
                unite = item.get("unite") or ""
                bloc = f"{nom} : {qte} {unite}".strip()
                lignes.append(bloc.rstrip("." ) + ".")

        if infos.get("cout"):
            lignes.append(f"Coût total pour 7 jours : {infos['cout']} francs CFA.")

        if infos.get("performances"):
            lignes.append(f"Performances attendues : {infos['performances']}.")

        if len(lignes) == 1:
            lignes.append("Voici votre ration prête à l'écoute.")

        lignes.append("Bonne production !")

        resume_fr = " ".join(lignes)
        resume_fr = re.sub(r"\s+", " ", resume_fr).strip()
        resume_fr = _trim_words(resume_fr, max_words=200)

        if langue_norm != "fr":
            traduit = _translate_text_with_gpt(resume_fr, langue_norm, source_langue="fr")
            traduit = re.sub(r"\s+", " ", traduit).strip()
            return _trim_words(traduit or resume_fr, max_words=200)

        return resume_fr

    async def generer_audio_demo(self, langue: str) -> Path:
        """
        Génère un audio de démonstration dans la langue demandée et l'enregistre
        dans `assets/demo_{langue}.mp3`.
        """
        langue_norm = _normaliser_langue(langue)
        if langue_norm not in LANGUES_DEMO:
            raise ValueError(
                f"Langue non supportée pour la démo: {langue_norm}. "
                f"Langues acceptées: {', '.join(sorted(LANGUES_DEMO))}"
            )

        ASSETS_DIR.mkdir(parents=True, exist_ok=True)
        fichier = ASSETS_DIR / f"demo_{langue_norm}.mp3"

        texte_fr = _build_demo_text_fr()
        texte_cible = texte_fr if langue_norm == "fr" else await asyncio.to_thread(
            _translate_text_with_gpt, texte_fr, langue_norm, source_langue="fr"
        )

        audio_bytes = await self.text_to_speech(texte_cible, langue=langue_norm, voix="alloy")
        fichier.write_bytes(audio_bytes)
        return fichier


# -----------------------------------------------------------------------------
# Routeur FastAPI
# -----------------------------------------------------------------------------

router = APIRouter(prefix="/audio", tags=["Audio"])
audio_service = AudioService()


@router.post("/synthese")
async def synthese_audio(payload: SyntheseRequest) -> StreamingResponse:
    try:
        audio_bytes = await audio_service.text_to_speech(
            texte=payload.texte,
            langue=payload.langue,
            voix=payload.voix,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Erreur synthèse audio: {exc}")

    return StreamingResponse(
        io.BytesIO(audio_bytes),
        media_type="audio/mpeg",
        headers={
            "Content-Disposition": 'inline; filename="feedformula_audio.mp3"',
            "Cache-Control": "no-store",
        },
    )


@router.post("/transcription")
async def transcription_audio(
    audio: UploadFile = File(...),
    langue: str = Form(default="auto"),
) -> Dict[str, Any]:
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


@router.post("/ration-vocale")
async def ration_vocale(payload: RationVocaleRequest) -> StreamingResponse:
    try:
        resume = await asyncio.to_thread(
            audio_service.resumer_ration_pour_audio,
            payload.ration_texte,
            payload.langue,
        )
        audio_bytes = await audio_service.text_to_speech(
            texte=resume,
            langue=payload.langue,
            voix="alloy",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Erreur génération ration vocale: {exc}")

    return StreamingResponse(
        io.BytesIO(audio_bytes),
        media_type="audio/mpeg",
        headers={
            "Content-Disposition": 'inline; filename="ration_vocale.mp3"',
            "Cache-Control": "no-store",
        },
    )


@router.get("/demo/{langue}")
async def demo_audio(langue: str) -> StreamingResponse:
    langue_norm = _normaliser_langue(langue)
    if langue_norm not in LANGUES_DEMO:
        raise HTTPException(
            status_code=400,
            detail=f"Langue non supportée pour la démo: {langue_norm}",
        )

    fichier = ASSETS_DIR / f"demo_{langue_norm}.mp3"
    try:
        if not fichier.exists() or fichier.stat().st_size == 0:
            fichier = await audio_service.generer_audio_demo(langue_norm)

        return StreamingResponse(
            io.BytesIO(fichier.read_bytes()),
            media_type="audio/mpeg",
            headers={
                "Content-Disposition": f'inline; filename="{fichier.name}"',
                "Cache-Control": "no-store",
            },
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Impossible de générer le demo audio: {exc}")


__all__ = [
    "AudioService",
    "audio_service",
    "router",
    "SyntheseRequest",
    "TranscriptionResponse",
    "RationVocaleRequest",
]
