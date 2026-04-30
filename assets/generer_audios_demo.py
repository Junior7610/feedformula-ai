#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Générateur d'audios de démonstration pour FeedFormula AI.

Objectifs :
- générer 6 audios de démo dans les langues cibles
- traduire le texte de base via GPT 5.5 si nécessaire
- produire les MP3 via l'API Afri TTS
- fallback local via gTTS si l'API échoue
- sauvegarder un rapport détaillé dans docs/RAPPORT_AUDIO.md

Langues générées :
- fr
- fon
- yor
- den
- adj
- en

Variables d'environnement utiles :
- AFRI_BASE_URL
- AFRI_API_KEY
- OPENAI_API_KEY
- OPENAI_BASE_URL (optionnel)
- FEEDFORMULA_AUDIO_FALLBACK_COPY (optionnel, valeur "1" pour autoriser la copie de secours)

Ce script est conçu pour être exécuté depuis le projet FeedFormula AI,
mais il reste autonome.
"""

from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import textwrap
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# -----------------------------------------------------------------------------
# Chemins
# -----------------------------------------------------------------------------

SCRIPT_PATH = Path(__file__).resolve()
ASSETS_DIR = SCRIPT_PATH.parent
PROJECT_ROOT = ASSETS_DIR.parent
DOCS_DIR = PROJECT_ROOT / "docs"

REPORT_PATH = DOCS_DIR / "RAPPORT_AUDIO.md"
BASE_AUDIO_FALLBACK = ASSETS_DIR / "demo_voix.mp3"

# -----------------------------------------------------------------------------
# Configuration API
# -----------------------------------------------------------------------------

AFRI_BASE_URL = (
    os.getenv("AFRI_BASE_URL")
    or os.getenv("AFRI_API_BASE_URL")
    or "https://build.lewisnote.com/v1"
).rstrip("/")
AFRI_API_KEY = (os.getenv("AFRI_API_KEY") or "").strip()
AFRI_TTS_MODEL = (os.getenv("AFRI_TTS_MODEL") or "afri-tts-1").strip()
AFRI_TTS_VOICE = (os.getenv("AFRI_TTS_VOICE") or "alloy").strip()
AFRI_TIMEOUT_SECONDS = float(os.getenv("AFRI_TIMEOUT_SECONDS") or "90")

OPENAI_API_KEY = (os.getenv("OPENAI_API_KEY") or os.getenv("AFRI_API_KEY") or "").strip()
OPENAI_BASE_URL = (
    os.getenv("OPENAI_BASE_URL")
    or os.getenv("AFRI_BASE_URL")
    or os.getenv("AFRI_API_BASE_URL")
    or AFRI_BASE_URL
).rstrip("/")
OPENAI_MODEL = (os.getenv("OPENAI_MODEL") or "gpt-5.5").strip()

ENABLE_FALLBACK_COPY = (os.getenv("FEEDFORMULA_AUDIO_FALLBACK_COPY") or "1").strip() not in {
    "0",
    "false",
    "False",
    "no",
    "NO",
}

# -----------------------------------------------------------------------------
# Import OpenAI si disponible
# -----------------------------------------------------------------------------

try:
    from openai import OpenAI  # type: ignore
except Exception:  # pragma: no cover - dépendance facultative
    OpenAI = None  # type: ignore

try:
    from gtts import gTTS  # type: ignore
except Exception:  # pragma: no cover - dépendance facultative
    gTTS = None  # type: ignore

try:
    from mutagen.mp3 import MP3  # type: ignore
except Exception:  # pragma: no cover - dépendance facultative
    MP3 = None  # type: ignore


# -----------------------------------------------------------------------------
# Données
# -----------------------------------------------------------------------------

BASE_TEXT_FR = (
    "Bonjour, je suis Aya, votre assistante agricole.\n"
    "FeedFormula AI génère votre ration en 30 secondes.\n"
    "Voici un exemple pour 50 poulets de chair :\n"
    "Maïs : 74 kilogrammes.\n"
    "Tourteau de soja : 9 kilogrammes.\n"
    "Farine de poisson : 17 kilogrammes.\n"
    "Coût total pour 7 jours : 13 462 francs CFA.\n"
    "FeedFormula AI. L'intelligence africaine au service\n"
    "de vos animaux."
)

LANGUAGES: List[Tuple[str, str]] = [
    ("fr", "français"),
    ("fon", "fon"),
    ("yor", "yoruba"),
    ("den", "dendi"),
    ("adj", "adja"),
    ("en", "anglais"),
]

LANGUAGE_DISPLAY = {
    "fr": "Français",
    "fon": "Fɔ̀ngbè",
    "yor": "Yoruba",
    "den": "Dendi",
    "adj": "Adja",
    "en": "English",
}

LANGUAGE_HINT = {
    "fr": "français",
    "fon": "langue fon",
    "yor": "langue yoruba",
    "den": "langue dendi",
    "adj": "langue adja",
    "en": "anglais",
}

# -----------------------------------------------------------------------------
# Modèles de résultat
# -----------------------------------------------------------------------------

@dataclass
class GenerationResult:
    code_langue: str
    langue: str
    audio_path: Path
    texte_path: Path
    methode_audio: str
    statut: str
    duree_secondes: Optional[float]
    taille_octets: int
    source_audio: str
    texte: str
    erreur: Optional[str] = None


# -----------------------------------------------------------------------------
# Utilitaires
# -----------------------------------------------------------------------------

def ensure_directories() -> None:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def clean_text(value: str) -> str:
    return " ".join(str(value or "").strip().split())


def extract_text_from_openai_response(response: Any) -> str:
    if response is None:
        return ""

    output_text = getattr(response, "output_text", None)
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()

    if isinstance(response, dict):
        for key in ("text", "output_text", "content"):
            value = response.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

    raw = str(response).strip()
    return raw


def get_openai_client() -> Optional[Any]:
    if OpenAI is None:
        return None
    if not OPENAI_API_KEY:
        return None
    try:
        return OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)
    except Exception:
        return None


def translate_with_gpt55(base_text: str, code_langue: str) -> str:
    """
    Traduit le texte de base dans la langue cible via GPT 5.5.
    Si la langue est déjà le français, retourne le texte d'origine.
    """
    if code_langue == "fr":
        return base_text

    client = get_openai_client()
    if client is None:
        return base_text

    target_label = LANGUAGE_HINT.get(code_langue, code_langue)
    prompt = (
        "Tu es un traducteur professionnel pour une application vocale agricole.\n"
        f"Traduis fidèlement le texte suivant en {target_label}.\n"
        "Contraintes importantes :\n"
        "- garde les retours à la ligne utiles\n"
        "- garde les montants, nombres, unités et pourcentages inchangés\n"
        "- n'ajoute aucun commentaire\n"
        "- conserve le ton chaleureux et simple\n"
        "- si la langue cible a des particularités orthographiques, respecte-les\n\n"
        f"TEXTE À TRADUIRE:\n{base_text}"
    )

    try:
        response = client.responses.create(
            model=OPENAI_MODEL,
            input=prompt,
        )
        translated = extract_text_from_openai_response(response)
        translated = clean_text(translated)
        return translated or base_text
    except Exception:
        return base_text


def _response_to_json(response: Any) -> Dict[str, Any]:
    if response is None:
        return {}

    if isinstance(response, dict):
        return response

    if hasattr(response, "read"):
        raw = response.read()
        if not raw:
            return {}
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return {}

    if hasattr(response, "content"):
        content = getattr(response, "content")
        if isinstance(content, (bytes, bytearray)):
            try:
                return json.loads(bytes(content).decode("utf-8"))
            except Exception:
                return {}

    return {}


def _download_url(url: str, timeout: float = AFRI_TIMEOUT_SECONDS) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "feedformula-ai-audio/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _extract_audio_bytes_from_response(response: Any) -> bytes:
    """
    Tente d'extraire des octets audio à partir de différentes formes de réponse.
    """
    if response is None:
        return b""

    # Réponse binaire directe
    if isinstance(response, (bytes, bytearray)):
        return bytes(response)

    # Objet HTTP avec body brut
    if hasattr(response, "read"):
        raw = response.read()
        if raw:
            return raw

    # SDK / dict JSON avec chemins ou base64
    data = _response_to_json(response)
    if data:
        # Cas classiques
        for key in ("audio_base64", "audio_b64", "b64_json", "content_base64"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                try:
                    return base64.b64decode(value)
                except Exception:
                    pass

        for key in ("audio_url", "url", "download_url"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                try:
                    return _download_url(value.strip())
                except Exception:
                    pass

        for key in ("audio_path", "path", "file_path"):
            value = data.get(key)
            if isinstance(value, str) and value.strip() and Path(value).exists():
                try:
                    return Path(value).read_bytes()
                except Exception:
                    pass

        # Certains backends renvoient `data: [{b64_json: ...}]`
        inner = data.get("data")
        if isinstance(inner, list) and inner:
            first = inner[0]
            if isinstance(first, dict):
                for key in ("b64_json", "audio_base64", "image_base64"):
                    value = first.get(key)
                    if isinstance(value, str) and value.strip():
                        try:
                            return base64.b64decode(value)
                        except Exception:
                            pass
                for key in ("url", "audio_url"):
                    value = first.get(key)
                    if isinstance(value, str) and value.strip():
                        try:
                            return _download_url(value.strip())
                        except Exception:
                            pass

    return b""


def afri_tts(text: str, code_langue: str) -> bytes:
    """
    Génère l'audio via l'API Afri TTS.
    """
    payload = {
        "model": AFRI_TTS_MODEL,
        "input": text,
        "voice": AFRI_TTS_VOICE,
        "language": code_langue,
    }

    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Accept": "audio/mpeg, audio/*, application/json",
    }
    if AFRI_API_KEY:
        headers["Authorization"] = f"Bearer {AFRI_API_KEY}"

    request = urllib.request.Request(
        url=f"{AFRI_BASE_URL}/audio/speech",
        data=body,
        headers=headers,
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=AFRI_TIMEOUT_SECONDS) as response:
        content_type = (response.headers.get("Content-Type") or "").lower()
        raw = response.read()

        if raw and ("audio/" in content_type or content_type.startswith("application/octet-stream")):
            return raw

        # Retour JSON éventuel
        try:
            parsed = json.loads(raw.decode("utf-8")) if raw else {}
        except Exception:
            parsed = {}

        extracted = _extract_audio_bytes_from_response(parsed)
        if extracted:
            return extracted

        # Parfois la réponse est binaire malgré un content-type ambigu
        if raw:
            return raw

    raise RuntimeError("Aucun audio exploitable n'a été renvoyé par l'API Afri TTS.")


def fallback_gtts(text: str, code_langue: str) -> bytes:
    """
    Fallback local avec gTTS.
    Remarque : gTTS ne couvre pas toujours toutes les langues cibles.
    """
    if gTTS is None:
        raise RuntimeError("gTTS n'est pas installé.")

    lang_for_gtts = code_langue[:2] or "fr"
    from io import BytesIO

    buffer = BytesIO()
    tts = gTTS(text=text, lang=lang_for_gtts)
    tts.write_to_fp(buffer)
    return buffer.getvalue()


def fallback_copy_audio() -> Optional[bytes]:
    if not ENABLE_FALLBACK_COPY:
        return None
    if BASE_AUDIO_FALLBACK.exists():
        try:
            return BASE_AUDIO_FALLBACK.read_bytes()
        except Exception:
            return None
    return None


def get_mp3_duration(path: Path) -> Optional[float]:
    if not path.exists():
        return None

    if MP3 is not None:
        try:
            return float(MP3(str(path)).info.length)
        except Exception:
            pass

    # Fallback via ffprobe si disponible
    try:
        command = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ]
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        value = (result.stdout or "").strip()
        if value:
            return float(value)
    except Exception:
        pass

    return None


def get_file_size(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        return int(path.stat().st_size)
    except Exception:
        return 0


def format_duration(value: Optional[float]) -> str:
    if value is None:
        return "inconnue"
    minutes = int(value // 60)
    seconds = int(round(value % 60))
    if minutes > 0:
        return f"{minutes} min {seconds:02d} s"
    return f"{seconds} s"


def write_text_file(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def build_demo_text(code_langue: str) -> str:
    translated = translate_with_gpt55(BASE_TEXT_FR, code_langue)
    return clean_text(translated)


def generate_audio_for_language(code_langue: str, display_name: str) -> GenerationResult:
    audio_path = ASSETS_DIR / f"demo_{code_langue}.mp3"
    texte_path = ASSETS_DIR / f"demo_{code_langue}.txt"

    texte = build_demo_text(code_langue)
    write_text_file(texte_path, texte)

    method = "afri-tts"
    status = "ok"
    source_audio = "afri"
    error_message: Optional[str] = None
    audio_bytes: Optional[bytes] = None

    try:
        audio_bytes = afri_tts(texte, code_langue)
    except Exception as afri_error:
        error_message = f"Afri TTS indisponible: {afri_error}"
        try:
            audio_bytes = fallback_gtts(texte, code_langue)
            method = "gTTS"
            status = "fallback-gtts"
            source_audio = "gtts"
            error_message = None
        except Exception as gtts_error:
            copy_bytes = fallback_copy_audio()
            if copy_bytes is not None:
                audio_bytes = copy_bytes
                method = "copie-de-secours"
                status = "fallback-copy"
                source_audio = "copy"
                error_message = (
                    f"Afri TTS indisponible: {afri_error}; "
                    f"gTTS indisponible: {gtts_error}; "
                    f"fallback copie utilisée."
                )
            else:
                raise RuntimeError(
                    f"Impossible de générer l'audio pour {code_langue}: "
                    f"Afri={afri_error} | gTTS={gtts_error} | aucune copie de secours"
                ) from gtts_error

    if audio_bytes is None:
        raise RuntimeError(f"Aucun flux audio produit pour {code_langue}.")

    audio_path.write_bytes(audio_bytes)
    duration = get_mp3_duration(audio_path)
    size_bytes = get_file_size(audio_path)

    return GenerationResult(
        code_langue=code_langue,
        langue=display_name,
        audio_path=audio_path,
        texte_path=texte_path,
        methode_audio=method,
        statut=status,
        duree_secondes=duration,
        taille_octets=size_bytes,
        source_audio=source_audio,
        texte=texte,
        erreur=error_message,
    )


def build_report(results: List[GenerationResult]) -> str:
    lines: List[str] = []
    lines.append("# Rapport audio FeedFormula AI")
    lines.append("")
    lines.append(f"- Date de génération : {now_iso()}")
    lines.append(f"- Dossier audio : `{ASSETS_DIR.as_posix()}`")
    lines.append(f"- Modèle de traduction : `{OPENAI_MODEL}`")
    lines.append(f"- Modèle TTS Afri : `{AFRI_TTS_MODEL}`")
    lines.append(f"- Voix Afri : `{AFRI_TTS_VOICE}`")
    lines.append("")
    lines.append("## Légende")
    lines.append("")
    lines.append("- `afri` : audio généré via l'API Afri TTS")
    lines.append("- `gtts` : fallback local gTTS")
    lines.append("- `copy` : copie de secours depuis `assets/demo_voix.mp3`")
    lines.append("")

    lines.append("## Statut des fichiers générés")
    lines.append("")
    lines.append(
        "| Langue | Code | Fichier | Statut | Source | Méthode audio | Durée | Taille | Texte |"
    )
    lines.append("|---|---:|---|---|---|---|---:|---:|---|")

    total_size = 0
    for result in results:
        filename = result.audio_path.name
        duration = format_duration(result.duree_secondes)
        size_label = f"{result.taille_octets} octets" if result.taille_octets else "inconnue"
        total_size += result.taille_octets
        text_short = result.texte.replace("\n", " ")
        if len(text_short) > 70:
            text_short = text_short[:67] + "..."
        lines.append(
            f"| {result.langue} | `{result.code_langue}` | `{filename}` | "
            f"{result.statut} | `{result.source_audio}` | {result.methode_audio} | "
            f"{duration} | {size_label} | {text_short} |"
        )

    lines.append("")
    lines.append("## Observations")
    lines.append("")
    for result in results:
        if result.erreur:
            lines.append(f"- `{result.code_langue}` : {result.erreur}")
        else:
            lines.append(
                f"- `{result.code_langue}` : audio généré avec `{result.methode_audio}` "
                f"depuis `{result.source_audio}` ({format_duration(result.duree_secondes)}, "
                f"{result.taille_octets} octets)"
            )

    lines.append("")
    lines.append("## Synthèse")
    lines.append("")
    lines.append(f"- Nombre d'audios générés : {len(results)}")
    lines.append(
        f"- Taille totale des MP3 : {total_size} octets" if total_size else "- Taille totale des MP3 : inconnue"
    )
    lines.append("")
    lines.append("## Texte source")
    lines.append("")
    lines.append("```text")
    lines.append(BASE_TEXT_FR)
    lines.append("```")
    lines.append("")

    return "\n".join(lines)


def main() -> int:
    ensure_directories()

    print("=== Génération des audios de démonstration FeedFormula AI ===")
    print(f"Projet : {PROJECT_ROOT}")
    print(f"Assets : {ASSETS_DIR}")
    print(f"Docs   : {DOCS_DIR}")
    print("")

    results: List[GenerationResult] = []
    failures: List[Tuple[str, str]] = []

    for code_langue, display_name in LANGUAGES:
        print(f"→ {display_name} ({code_langue})")
        try:
            result = generate_audio_for_language(code_langue, display_name)
            results.append(result)
            print(
                f"  OK - {result.audio_path.name} "
                f"({result.methode_audio}, {format_duration(result.duree_secondes)})"
            )
        except Exception as exc:
            failures.append((code_langue, str(exc)))
            print(f"  ÉCHEC - {exc}")

    report = build_report(results)
    write_text_file(REPORT_PATH, report)

    print("")
    print(f"Rapport écrit dans : {REPORT_PATH}")
    print("")

    if failures:
        print("Certaines langues n'ont pas pu être générées :")
        for code_langue, error in failures:
            print(f"- {code_langue}: {error}")
        return 1

    print("Toutes les démos audio ont été générées avec succès.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
