#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Génère une vidéo démo de 2 minutes pour FeedFormula AI.

Sortie attendue :
    assets/video_demo_finale.mp4

Dépendances principales :
- moviepy
- pillow
- requests

La narration vocale est produite via l'API Afri TTS.
Le montage final est assemblé avec MoviePy en 1280x720 à 24 fps.

Exécution :
    python assets/creer_video_demo_finale.py

Variables d'environnement utiles :
- AFRI_BASE_URL ou AFRI_API_BASE_URL
- AFRI_API_KEY
- AFRI_TTS_MODEL
- AFRI_TTS_VOICE
- AFRI_TIMEOUT_SECONDS
- FEEDFORMULA_DEMO_VIDEO_NO_TTS=1 pour désactiver la génération audio
"""

from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

SCRIPT_PATH = Path(__file__).resolve()
ASSETS_DIR = SCRIPT_PATH.parent
PROJECT_ROOT = ASSETS_DIR.parent
TEMP_DIR = ASSETS_DIR / "demo_tmp" / "video_demo_finale"
OUTPUT_PATH = ASSETS_DIR / "video_demo_finale.mp4"

AFRI_BASE_URL = (
    os.getenv("AFRI_BASE_URL")
    or os.getenv("AFRI_API_BASE_URL")
    or "https://build.lewisnote.com/v1"
).rstrip("/")
AFRI_API_KEY = (os.getenv("AFRI_API_KEY") or "").strip()
AFRI_TTS_MODEL = (os.getenv("AFRI_TTS_MODEL") or "afri-tts-1").strip()
AFRI_TTS_VOICE = (os.getenv("AFRI_TTS_VOICE") or "alloy").strip()
AFRI_TIMEOUT_SECONDS = float(os.getenv("AFRI_TIMEOUT_SECONDS") or "90")
DISABLE_TTS = (os.getenv("FEEDFORMULA_DEMO_VIDEO_NO_TTS") or "0").strip() in {
    "1",
    "true",
    "True",
    "yes",
    "YES",
}


@dataclass(frozen=True)
class Scene:
    title: str
    subtitle: str
    narration: str
    duration: float
    image_candidates: Tuple[str, ...]
    accent: Tuple[int, int, int] = (249, 168, 37)


SCENES: List[Scene] = [
    Scene(
        title="68 % des éleveurs perdent de la marge",
        subtitle="Un nutritionniste coûte cher. FeedFormula AI change tout.",
        narration=(
            "68 % des éleveurs africains perdent de la marge. "
            "Un nutritionniste coûte 200 000 FCFA. FeedFormula AI change tout."
        ),
        duration=15.0,
        image_candidates=(
            "branding/presentation_investisseurs.png",
            "presentation_investisseurs.png",
        ),
    ),
    Scene(
        title="Le problème est concret",
        subtitle="Kofi a 50 poulets et ne sait pas quoi leur donner.",
        narration=(
            "Kofi a 50 poulets. Il ne sait pas quoi leur donner à manger. "
            "Chaque erreur lui coûte des milliers de francs CFA."
        ),
        duration=15.0,
        image_candidates=(
            "hero_poulets_premium.png",
            "branding/hero_poulets_premium.png",
            "hero_poulets.png",
        ),
    ),
    Scene(
        title="La solution en 30 secondes",
        subtitle="Il parle en fon, la ration arrive dans sa langue.",
        narration=(
            "Avec FeedFormula AI, il parle en fon. En 30 secondes, la ration parfaite arrive. "
            "Les quantités. Le coût. Les performances. Dans sa langue maternelle."
        ),
        duration=30.0,
        image_candidates=(
            "hero_image_accueil.png",
            "branding/hero_image_accueil.png",
            "fond_ecran_accueil.png",
            "illustration_accueil.png",
            "splash_screen.png",
        ),
    ),
    Scene(
        title="8 modules, 50 langues, gamification",
        subtitle="NutriCore, VetScan, ReproTrack et tout l’écosystème.",
        narration=(
            "8 modules complets. NutriCore. VetScan. ReproTrack. PastureMap. FarmManager. "
            "FarmAcademy. FarmCast. FarmCommunity. 50 langues africaines. Gamification complète."
        ),
        duration=30.0,
        image_candidates=(
            "icones_8_modules_premium.png",
            "branding/icones_8_modules_premium.png",
            "icones_modules.png",
        ),
    ),
    Scene(
        title="Un marché régional immense",
        subtitle="Bénin, puis Afrique de l’Ouest.",
        narration=(
            "180 000 éleveurs au Bénin. Des millions en Afrique de l'Ouest. "
            "An 1 : Bénin. An 2 : 5 pays. An 3 : 15 pays."
        ),
        duration=15.0,
        image_candidates=(
            "carte_afrique_impact.png",
            "branding/carte_afrique_impact.png",
        ),
    ),
    Scene(
        title="L’intelligence africaine au service des animaux",
        subtitle="Créé par Leonel TOGBE. Prêt à changer l’élevage africain.",
        narration=(
            "FeedFormula AI. L'intelligence africaine au service de vos animaux. "
            "Créé par Leonel TOGBE. Technicien Agricole. Béninois. Prêt à changer l'élevage africain."
        ),
        duration=15.0,
        image_candidates=(
            "splash_screen_premium.png",
            "branding/splash_screen_premium.png",
            "splash_screen.png",
        ),
    ),
]


# -----------------------------------------------------------------------------
# Helpers de fichiers
# -----------------------------------------------------------------------------


def ensure_directories() -> None:
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)


def pick_existing_asset(candidates: Sequence[str]) -> Path:
    for candidate in candidates:
        path = ASSETS_DIR / candidate
        if path.exists():
            return path
    raise FileNotFoundError(
        "Aucun visuel de scène trouvé parmi : " + ", ".join(candidates)
    )


# -----------------------------------------------------------------------------
# Import MoviePy / Pillow
# -----------------------------------------------------------------------------


def _load_video_stack():
    try:
        from moviepy.editor import (  # type: ignore
            AudioFileClip,
            CompositeAudioClip,
            CompositeVideoClip,
            ImageClip,
            concatenate_audioclips,
            concatenate_videoclips,
        )
    except Exception:
        from moviepy import (  # type: ignore
            AudioFileClip,
            CompositeAudioClip,
            CompositeVideoClip,
            ImageClip,
            concatenate_audioclips,
            concatenate_videoclips,
        )

    try:
        from PIL import Image, ImageDraw, ImageFont  # type: ignore
    except Exception as exc:
        raise RuntimeError(
            "Pillow est requis pour fabriquer les panneaux texte (pip install pillow)."
        ) from exc

    return (
        AudioFileClip,
        CompositeAudioClip,
        CompositeVideoClip,
        ImageClip,
        concatenate_audioclips,
        concatenate_videoclips,
        Image,
        ImageDraw,
        ImageFont,
    )


# -----------------------------------------------------------------------------
# Utilitaires MoviePy compatibles
# -----------------------------------------------------------------------------


def _duration(clip, value: float):
    if hasattr(clip, "with_duration"):
        return clip.with_duration(value)
    return clip.set_duration(value)  # type: ignore[attr-defined]


def _start(clip, value: float):
    if hasattr(clip, "with_start"):
        return clip.with_start(value)
    return clip.set_start(value)  # type: ignore[attr-defined]


def _position(clip, value):
    if hasattr(clip, "with_position"):
        return clip.with_position(value)
    return clip.set_position(value)  # type: ignore[attr-defined]


def _opacity(clip, value: float):
    if hasattr(clip, "with_opacity"):
        return clip.with_opacity(value)
    return clip.set_opacity(value)  # type: ignore[attr-defined]


def _resized(clip, **kwargs):
    if hasattr(clip, "resized"):
        return clip.resized(**kwargs)
    return clip.resize(**kwargs)  # type: ignore[attr-defined]


# -----------------------------------------------------------------------------
# TTS Afri
# -----------------------------------------------------------------------------


def _extract_audio_bytes_from_response(payload) -> Optional[bytes]:
    if isinstance(payload, dict):
        for key in ("audio", "audio_base64", "b64_json", "content"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                try:
                    return base64.b64decode(value)
                except Exception:
                    pass

        data = payload.get("data")
        if isinstance(data, list) and data:
            first = data[0]
            if isinstance(first, dict):
                for key in ("audio", "audio_base64", "b64_json", "content"):
                    value = first.get(key)
                    if isinstance(value, str) and value.strip():
                        try:
                            return base64.b64decode(value)
                        except Exception:
                            pass
                url = first.get("url")
                if isinstance(url, str) and url.strip():
                    return _download_url(url)

        url = payload.get("url") or payload.get("audio_url")
        if isinstance(url, str) and url.strip():
            return _download_url(url)

    return None


def _download_url(url: str) -> bytes:
    request = urllib.request.Request(url=url, method="GET")
    with urllib.request.urlopen(request, timeout=AFRI_TIMEOUT_SECONDS) as response:
        return response.read()


def afri_tts(text: str, language: str = "fr") -> bytes:
    if DISABLE_TTS:
        return b""

    payload = {
        "model": AFRI_TTS_MODEL,
        "input": text,
        "voice": AFRI_TTS_VOICE,
        "language": language,
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

        if raw and (
            "audio/" in content_type
            or content_type.startswith("application/octet-stream")
        ):
            return raw

        try:
            parsed = json.loads(raw.decode("utf-8")) if raw else {}
        except Exception:
            parsed = {}

        extracted = _extract_audio_bytes_from_response(parsed)
        if extracted:
            return extracted

        if raw:
            return raw

    raise RuntimeError(
        "Aucun flux audio exploitable n'a été renvoyé par l'API Afri TTS."
    )


# -----------------------------------------------------------------------------
# Panneaux visuels
# -----------------------------------------------------------------------------


def _get_font(size: int, ImageFont):
    try:
        return ImageFont.truetype("DejaVuSans-Bold.ttf", size)
    except Exception:
        return ImageFont.load_default()


def _wrap_text(text: str, max_chars: int) -> List[str]:
    words = text.split()
    if not words:
        return [""]

    lines: List[str] = []
    current = ""
    for word in words:
        candidate = (current + " " + word).strip()
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _create_caption_panel(
    scene: Scene,
    size: Tuple[int, int],
    out_path: Path,
) -> None:
    _, _, _, _, _, _, Image, ImageDraw, ImageFont = _load_video_stack()
    width, height = size

    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    panel_margin_x = 72
    panel_h = 220
    y0 = height - panel_h - 34
    y1 = height - 24

    draw.rounded_rectangle(
        [(panel_margin_x, y0), (width - panel_margin_x, y1)],
        radius=30,
        fill=(10, 18, 12, 170),
        outline=(249, 168, 37, 130),
        width=3,
    )

    title_font = _get_font(42, ImageFont)
    subtitle_font = _get_font(28, ImageFont)
    footer_font = _get_font(22, ImageFont)

    title_lines = _wrap_text(scene.title, 32)
    subtitle_lines = _wrap_text(scene.subtitle, 48)

    y = y0 + 24

    for line in title_lines[:2]:
        bbox = draw.textbbox((0, 0), line, font=title_font)
        text_w = bbox[2] - bbox[0]
        draw.text(
            ((width - text_w) // 2, y),
            line,
            font=title_font,
            fill=scene.accent + (255,),
        )
        y += 48

    y += 6
    for line in subtitle_lines[:2]:
        bbox = draw.textbbox((0, 0), line, font=subtitle_font)
        text_w = bbox[2] - bbox[0]
        draw.text(
            ((width - text_w) // 2, y),
            line,
            font=subtitle_font,
            fill=(245, 245, 245, 242),
        )
        y += 34

    footer = "FeedFormula AI • Démo officielle Build With Afri"
    bbox = draw.textbbox((0, 0), footer, font=footer_font)
    text_w = bbox[2] - bbox[0]
    draw.text(
        ((width - text_w) // 2, y1 - 36),
        footer,
        font=footer_font,
        fill=(220, 220, 220, 220),
    )

    img.save(out_path, "PNG")


def _make_background_clip(
    ImageClip, image_path: Path, duration: float, canvas_size=(1280, 720)
):
    width, height = canvas_size
    clip = ImageClip(str(image_path))
    ratio = clip.w / clip.h
    target_ratio = width / height

    if ratio >= target_ratio:
        clip = _resized(clip, height=height)
    else:
        clip = _resized(clip, width=width)

    clip = _duration(clip, duration)
    return _position(clip, ("center", "center"))


# -----------------------------------------------------------------------------
# Assemblage vidéo
# -----------------------------------------------------------------------------


def build_video() -> None:
    (
        AudioFileClip,
        CompositeAudioClip,
        CompositeVideoClip,
        ImageClip,
        concatenate_audioclips,
        concatenate_videoclips,
        _,
        _,
        _,
    ) = _load_video_stack()

    ensure_directories()

    scene_clips = []
    audio_clips = []

    for index, scene in enumerate(SCENES, start=1):
        image_path = pick_existing_asset(scene.image_candidates)
        print(f"• Scène {index}: {image_path.name}")

        bg = _make_background_clip(ImageClip, image_path, scene.duration)

        # Légère couche sombre pour la lisibilité
        dark_panel = ImageClip(str(image_path))
        dark_panel = _resized(dark_panel, height=720)
        if getattr(dark_panel, "w", 0) < 1280:
            dark_panel = _resized(dark_panel, width=1280)
        dark_panel = _duration(dark_panel, scene.duration)
        dark_panel = _position(dark_panel, ("center", "center"))
        dark_panel = _opacity(dark_panel, 0.9)

        caption_path = TEMP_DIR / f"caption_{index}.png"
        _create_caption_panel(scene, (1280, 720), caption_path)
        caption = ImageClip(str(caption_path))
        caption = _duration(caption, scene.duration)
        caption = _position(caption, ("center", "center"))

        # Une animation légère par zoom progressif si MoviePy la supporte.
        if hasattr(bg, "resized"):
            try:
                bg = bg.resized(lambda t: 1.0 + 0.03 * (t / scene.duration))
            except Exception:
                pass

        scene_clip = CompositeVideoClip(
            [bg, dark_panel, caption],
            size=(1280, 720),
        )
        scene_clip = _duration(scene_clip, scene.duration)

        scene_clips.append(scene_clip)

        if DISABLE_TTS:
            audio_clips.append(None)
            continue

        try:
            audio_bytes = afri_tts(scene.narration, language="fr")
            audio_path = TEMP_DIR / f"scene_{index}.mp3"
            audio_path.write_bytes(audio_bytes)
            audio_clip = AudioFileClip(str(audio_path))
            if audio_clip.duration > scene.duration:
                audio_clip = (
                    audio_clip.subclipped(0, scene.duration)
                    if hasattr(audio_clip, "subclipped")
                    else audio_clip.subclip(0, scene.duration)  # type: ignore[attr-defined]
                )
            audio_clips.append(audio_clip)
        except Exception as exc:
            print(f"⚠️ TTS indisponible pour la scène {index} : {exc}")
            audio_clips.append(None)

    video = concatenate_videoclips(scene_clips, method="compose")

    if not DISABLE_TTS:
        active_audio = [clip for clip in audio_clips if clip is not None]
        if active_audio:
            # aligne chaque narration à sa scène
            starts = []
            offset = 0.0
            for scene in SCENES:
                starts.append(offset)
                offset += scene.duration

            layered_audio = []
            for start, clip in zip(starts, audio_clips):
                if clip is None:
                    continue
                layered_audio.append(_start(clip, start))

            final_audio = CompositeAudioClip(layered_audio)
            video = (
                video.with_audio(final_audio)
                if hasattr(video, "with_audio")
                else video.set_audio(final_audio)  # type: ignore[attr-defined]
            )

    video = (
        video.with_duration(sum(scene.duration for scene in SCENES))
        if hasattr(video, "with_duration")
        else video.set_duration(sum(scene.duration for scene in SCENES))  # type: ignore[attr-defined]
    )

    print(f"→ Export en cours vers {OUTPUT_PATH.name}")
    video.write_videofile(
        str(OUTPUT_PATH),
        codec="libx264",
        audio_codec="aac",
        fps=24,
        preset="medium",
        threads=4,
        bitrate="4500k",
    )

    print(f"✅ Vidéo générée : {OUTPUT_PATH}")


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------


def main() -> int:
    try:
        build_video()
        return 0
    except KeyboardInterrupt:
        print("\n⛔ Interrompu par l'utilisateur.")
        return 130
    except Exception as exc:
        print(f"❌ Erreur fatale : {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
