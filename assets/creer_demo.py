#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
feedformula-ai/assets/creer_demo.py

Script d'automatisation de la première démo vidéo FeedFormula AI.

Étapes réalisées :
1) Génère un script narration (60s) via API Afri + modèle GPT 5.4
2) Génère la voix off (TTS Afri) en MP3
3) Génère 5 images via GPT Image 2
4) Assemble une vidéo MP4 avec :
   - 5 images (12s chacune)
   - voix off
   - watermark logo
   - musique de fond africaine si disponible
   - sous-titres en bas

Prérequis:
- pip install openai python-dotenv
- pip install moviepy pillow   (moviepy auto-install tenté si absent)

Variables d'environnement:
- AFRI_API_KEY=...
"""

from __future__ import annotations

import base64
import os
import sys
import traceback
import urllib.request
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from openai import OpenAI

try:
    from dotenv import load_dotenv
except Exception:
    def load_dotenv(*args: Any, **kwargs: Any) -> bool:
        return False


# ----------------------------
# Configuration API Afri
# ----------------------------
BASE_URL = "https://build.lewisnote.com/v1"
MODEL_SCRIPT = "gpt-5.4"
MODEL_IMAGE = "gpt-image-2"
TTS_MODELS = ["afri-tts", "afri-tts-1", "gpt-4o-mini-tts", "tts-1"]
TTS_VOICE = "alloy"

# ----------------------------
# Chemins projet
# ----------------------------
SCRIPT_PATH = Path(__file__).resolve()
ASSETS_DIR = SCRIPT_PATH.parent
PROJECT_ROOT = SCRIPT_PATH.parent.parent

NARRATION_PATH = ASSETS_DIR / "demo_narration.txt"
VOICE_PATH = ASSETS_DIR / "demo_voix.mp3"
VIDEO_PATH = ASSETS_DIR / "demo_feedformula_jour3.mp4"
TEMP_DIR = ASSETS_DIR / "demo_tmp"
IMAGES_DIR = TEMP_DIR / "images"
SUBS_DIR = TEMP_DIR / "subs"

IMAGE_FILES = [
    ASSETS_DIR / "demo_image_1.png",
    ASSETS_DIR / "demo_image_2.png",
    ASSETS_DIR / "demo_image_3.png",
    ASSETS_DIR / "demo_image_4.png",
    ASSETS_DIR / "demo_image_5.png",
]

DEMO_IMAGE_PROMPTS = [
    "Illustration africaine moderne, cinématographique. Éleveur béninois confus devant ses poulets dans une petite ferme propre au Bénin, lumière chaude, ambiance réaliste inspirante.",
    "Même éleveur béninois en train d'ouvrir FeedFormula AI sur son smartphone, expression d'espoir, ferme en arrière-plan, style cohérent avec l'image précédente.",
    "Gros plan de l'interface FeedFormula AI avec formulaire de ration rempli pour 50 poulets, design mobile lisible, main de l'éleveur visible, style UI clair.",
    "Écran smartphone montrant la ration générée avec ingrédients et coûts, effet réussite, ambiance professionnelle et moderne, palette verte et or.",
    "Éleveur béninois souriant et satisfait près de ses 50 poulets en bonne santé, smartphone en main, sentiment de transformation positive, style africain moderne.",
]


# ============================
# Utilitaires API / parsing
# ============================
def _to_dict(obj: Any) -> Dict[str, Any]:
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "model_dump"):
        try:
            return obj.model_dump()
        except Exception:
            pass
    if hasattr(obj, "__dict__"):
        try:
            return dict(obj.__dict__)
        except Exception:
            pass
    return {}


def _safe_get(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _find_first_key(data: Any, target_key: str) -> Optional[Any]:
    if isinstance(data, dict):
        if target_key in data:
            return data[target_key]
        for value in data.values():
            found = _find_first_key(value, target_key)
            if found is not None:
                return found
    elif isinstance(data, list):
        for item in data:
            found = _find_first_key(item, target_key)
            if found is not None:
                return found
    return None


def _download_image_url(image_url: str, api_key: Optional[str]) -> bytes:
    headers = {"User-Agent": "feedformula-ai-demo/1.0"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
        headers["api-key"] = api_key

    request = urllib.request.Request(image_url, headers=headers)
    with urllib.request.urlopen(request, timeout=90) as response:
        return response.read()


def _extract_image_bytes(response: Any, api_key: Optional[str] = None) -> bytes:
    data = _safe_get(response, "data")
    if isinstance(data, list) and data:
        first = data[0]
        b64_data = _safe_get(first, "b64_json") or _safe_get(first, "image_base64")
        if b64_data:
            return base64.b64decode(b64_data)

        image_url = _safe_get(first, "url")
        if image_url:
            return _download_image_url(str(image_url), api_key)

    payload = _to_dict(response)
    if payload:
        b64_data = _find_first_key(payload, "b64_json") or _find_first_key(payload, "image_base64")
        if b64_data:
            return base64.b64decode(b64_data)

        image_url = _find_first_key(payload, "url")
        if image_url:
            return _download_image_url(str(image_url), api_key)

    raise ValueError("Aucune image trouvée dans la réponse API (ni base64 ni URL).")


def _extract_text_from_response(resp: Any) -> str:
    # 1) Essayez output_text (SDK récent)
    output_text = getattr(resp, "output_text", None)
    if output_text:
        return str(output_text).strip()

    # 2) Essayez extraction structurée
    data = _to_dict(resp)
    text = _find_first_key(data, "text")
    if isinstance(text, str) and text.strip():
        return text.strip()

    # 3) Fallback string brut
    raw = str(resp)
    if raw.strip():
        return raw.strip()

    raise ValueError("Impossible d'extraire le texte de la réponse GPT.")


def _limit_words(text: str, max_words: int = 150) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text.strip()
    return " ".join(words[:max_words]).strip()


# ============================
# Génération contenu
# ============================
def generer_script_narration(client: OpenAI) -> str:
    prompt = (
        "Écris un script de narration de 60 secondes "
        "pour une démo de FeedFormula AI. "
        "La démo montre un éleveur béninois qui utilise "
        "l'application pour la première fois et génère "
        "une ration pour ses 50 poulets en 30 secondes. "
        "Ton : chaleureux, africain, impressionnant. "
        "Langue : français. "
        "Maximum 150 mots."
    )

    response = client.responses.create(
        model=MODEL_SCRIPT,
        input=prompt,
    )
    narration = _extract_text_from_response(response)
    narration = _limit_words(narration, max_words=150)
    NARRATION_PATH.write_text(narration, encoding="utf-8")
    print(f"✅ Script narration généré: {NARRATION_PATH.name}")
    return narration


def generer_voix_off(client: OpenAI, texte: str) -> None:
    """
    Génère la voix off en MP3.
    Tente plusieurs modèles TTS pour robustesse.
    """
    last_err: Optional[Exception] = None
    VOICE_PATH.parent.mkdir(parents=True, exist_ok=True)

    for model in TTS_MODELS:
        try:
            print(f"🎙️ Tentative TTS avec modèle: {model}")
            response = client.audio.speech.create(
                model=model,
                voice=TTS_VOICE,
                input=texte,
            )

            # Compatibilité SDK: stream_to_file ou bytes direct
            if hasattr(response, "stream_to_file"):
                response.stream_to_file(str(VOICE_PATH))
            else:
                content = getattr(response, "content", None)
                if content is None:
                    content = bytes(response) if not isinstance(response, (bytes, bytearray)) else response
                if isinstance(content, str):
                    content = content.encode("utf-8")
                VOICE_PATH.write_bytes(content)

            print(f"✅ Voix off générée: {VOICE_PATH.name} (modèle: {model})")
            return

        except Exception as exc:
            last_err = exc
            print(f"⚠️ TTS échoué avec {model}: {exc}")

    raise RuntimeError(f"Échec TTS sur tous les modèles: {last_err}")


def generer_images_demo(client: OpenAI, api_key: str) -> None:
    """
    Génère les 5 images de la démo.
    """
    for idx, prompt in enumerate(DEMO_IMAGE_PROMPTS, start=1):
        output_path = IMAGE_FILES[idx - 1]
        output_path.parent.mkdir(parents=True, exist_ok=True)

        full_prompt = (
            f"{prompt} "
            "Qualité élevée, cohérence personnage d'une image à l'autre, rendu propre pour vidéo de présentation."
        )

        response = client.images.generate(
            model=MODEL_IMAGE,
            prompt=full_prompt,
            size="1536x1024",
        )

        raw = _extract_image_bytes(response, api_key=api_key)
        output_path.write_bytes(raw)
        print(f"✅ Image {idx} générée: {output_path.name}")


# ============================
# MoviePy / assemblage vidéo
# ============================
def _ensure_moviepy_installed() -> None:
    try:
        import moviepy  # noqa: F401
        return
    except Exception:
        print("ℹ️ moviepy absent, installation en cours...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "moviepy"])


def _import_video_stack():
    """
    Import dynamique moviepy + pillow pour éviter crash au démarrage.
    """
    _ensure_moviepy_installed()

    try:
        from moviepy.editor import (
            ImageClip,
            AudioFileClip,
            CompositeVideoClip,
            concatenate_videoclips,
        )
    except Exception:
        # Compatibilité moviepy v2
        from moviepy import (
            ImageClip,
            AudioFileClip,
            CompositeVideoClip,
            concatenate_videoclips,
        )

    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception as exc:
        raise RuntimeError(
            "Pillow est requis pour générer les sous-titres (pip install pillow)."
        ) from exc

    return ImageClip, AudioFileClip, CompositeVideoClip, concatenate_videoclips, Image, ImageDraw, ImageFont


def _find_logo_for_watermark() -> Optional[Path]:
    candidates = [
        ASSETS_DIR / "logo_feedformula_minimal.png",
        ASSETS_DIR / "logo_principal.png",
        ASSETS_DIR / "logo_feedformula_8_modules.png",
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def _find_background_music() -> Optional[Path]:
    candidates = [
        ASSETS_DIR / "musique_fond_africaine.mp3",
        ASSETS_DIR / "background_africaine.mp3",
        ASSETS_DIR / "bg_music.mp3",
        ASSETS_DIR / "music.mp3",
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def _split_text_for_subtitles(text: str, n_parts: int = 5) -> List[str]:
    words = text.split()
    if not words:
        return [""] * n_parts

    chunk_size = max(1, len(words) // n_parts)
    chunks: List[str] = []
    cursor = 0
    for i in range(n_parts):
        if i == n_parts - 1:
            part_words = words[cursor:]
        else:
            part_words = words[cursor:cursor + chunk_size]
        cursor += chunk_size
        chunks.append(" ".join(part_words).strip())

    while len(chunks) < n_parts:
        chunks.append("")
    return chunks[:n_parts]


def _create_subtitle_png(
    text: str,
    size: Tuple[int, int],
    out_path: Path,
):
    """
    Crée une image PNG transparente de sous-titre en bas de l'écran.
    """
    _, _, _, _, Image, ImageDraw, ImageFont = _import_video_stack()

    width, height = size
    out_path.parent.mkdir(parents=True, exist_ok=True)

    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Police: tentative DejaVu, fallback défaut
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", 44)
    except Exception:
        font = ImageFont.load_default()

    # Zone sous-titres
    margin_x = int(width * 0.08)
    box_h = int(height * 0.18)
    y0 = height - box_h - 30
    y1 = height - 20

    draw.rounded_rectangle(
        [(margin_x, y0), (width - margin_x, y1)],
        radius=20,
        fill=(0, 0, 0, 155),
    )

    # Wrapping simple
    max_chars = 65
    words = text.split()
    lines: List[str] = []
    current = ""
    for w in words:
        test = (current + " " + w).strip()
        if len(test) <= max_chars:
            current = test
        else:
            if current:
                lines.append(current)
            current = w
    if current:
        lines.append(current)

    if not lines:
        lines = [" "]

    # Dessin centré verticalement dans la box
    line_h = 46
    total_h = line_h * len(lines)
    start_y = y0 + max(12, (box_h - total_h) // 2)

    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font)
        text_w = bbox[2] - bbox[0]
        x = (width - text_w) // 2
        y = start_y + i * line_h
        draw.text((x, y), line, font=font, fill=(255, 255, 255, 235))

    img.save(out_path, "PNG")


def assembler_demo(narration_text: str) -> None:
    """
    Assemble la vidéo finale avec moviepy.
    - 5 images x 12s
    - voix off
    - watermark logo
    - musique de fond si disponible
    - sous-titres
    """
    (
        ImageClip,
        AudioFileClip,
        CompositeVideoClip,
        concatenate_videoclips,
        _,
        _,
        _,
    ) = _import_video_stack()

    try:
        from moviepy.editor import CompositeAudioClip, afx
    except Exception:
        from moviepy import CompositeAudioClip, afx

    if not VOICE_PATH.exists():
        raise FileNotFoundError(f"Voix off introuvable: {VOICE_PATH}")

    for p in IMAGE_FILES:
        if not p.exists():
            raise FileNotFoundError(f"Image manquante: {p}")

    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    SUBS_DIR.mkdir(parents=True, exist_ok=True)

    # 1) Clips image
    image_clips = [ImageClip(str(p)).with_duration(12) for p in IMAGE_FILES]
    video_base = concatenate_videoclips(image_clips, method="compose")

    # 2) Voix off
    voix = AudioFileClip(str(VOICE_PATH))
    video_duration = float(video_base.duration)

    # Marge de sécurité pour éviter tout dépassement audio en fin d'encodage MoviePy
    audio_safe_duration = max(1.0, float(voix.duration) - 0.25)
    render_duration = min(video_duration, audio_safe_duration)

    # On aligne strictement vidéo + voix sur la même durée de rendu
    video_base = video_base.with_duration(render_duration)
    voix = voix.subclipped(0, render_duration)

    # 3) Musique de fond optionnelle
    music_path = _find_background_music()
    final_audio = voix.with_volume_scaled(1.0).with_duration(render_duration)

    if music_path:
        try:
            music = AudioFileClip(str(music_path))
            if music.duration < render_duration:
                music = music.with_effects([afx.AudioLoop(duration=render_duration)])
            else:
                music = music.subclipped(0, render_duration)

            final_audio = CompositeAudioClip(
                [
                    voix.with_volume_scaled(1.0),
                    music.with_volume_scaled(0.22),
                ]
            ).with_duration(render_duration)
            print(f"🎵 Musique de fond utilisée: {music_path.name}")
        except Exception as exc:
            print(f"⚠️ Musique non utilisée (erreur): {exc}")
    else:
        print("ℹ️ Aucune musique de fond trouvée, vidéo sans musique.")

    # 4) Watermark logo
    overlays = [video_base]
    logo_path = _find_logo_for_watermark()
    if logo_path:
        try:
            logo = (
                ImageClip(str(logo_path))
                .with_duration(render_duration)
                .resized(height=110)
                .with_position(("right", "top"))
                .with_opacity(0.78)
            )
            overlays.append(logo)
            print(f"✅ Watermark logo: {logo_path.name}")
        except Exception as exc:
            print(f"⚠️ Watermark ignoré: {exc}")
    else:
        print("ℹ️ Aucun logo PNG trouvé pour watermark.")

    # 5) Sous-titres en bas
    subtitles = _split_text_for_subtitles(narration_text, n_parts=5)
    current_start = 0.0
    w, h = int(video_base.w), int(video_base.h)

    for i, sub_text in enumerate(subtitles, start=1):
        sub_png = SUBS_DIR / f"subtitle_{i}.png"
        _create_subtitle_png(sub_text, (w, h), sub_png)

        sub_clip = (
            ImageClip(str(sub_png))
            .with_start(current_start)
            .with_duration(12)
            .with_position(("center", "center"))
        )
        overlays.append(sub_clip)
        current_start += 12

    # 6) Composition finale
    final = CompositeVideoClip(overlays).with_audio(final_audio)
    final = final.with_duration(render_duration)

    VIDEO_PATH.parent.mkdir(parents=True, exist_ok=True)
    final.write_videofile(
        str(VIDEO_PATH),
        codec="libx264",
        audio_codec="aac",
        fps=24,
        preset="medium",
        threads=4,
    )

    print(f"✅ Démo vidéo générée: {VIDEO_PATH.name}")


# ============================
# Main
# ============================
def main() -> int:
    try:
        # Chargement .env
        load_dotenv(PROJECT_ROOT / ".env")

        api_key = os.getenv("AFRI_API_KEY")
        if not api_key:
            print("❌ AFRI_API_KEY introuvable. Ajoute-la dans le fichier .env.")
            return 1

        # Prépare répertoires
        TEMP_DIR.mkdir(parents=True, exist_ok=True)
        IMAGES_DIR.mkdir(parents=True, exist_ok=True)
        SUBS_DIR.mkdir(parents=True, exist_ok=True)

        client = OpenAI(
            api_key=api_key,
            base_url=BASE_URL,
        )

        print("🚀 Début génération démo FeedFormula AI...")
        narration = generer_script_narration(client)
        generer_voix_off(client, narration)
        generer_images_demo(client, api_key=api_key)
        assembler_demo(narration)

        print("🎉 Terminé avec succès.")
        return 0

    except KeyboardInterrupt:
        print("\n⛔ Interrompu par l'utilisateur.")
        return 130

    except Exception as exc:
        print(f"❌ Erreur fatale: {exc}")
        print(traceback.format_exc())
        return 2


if __name__ == "__main__":
    sys.exit(main())
