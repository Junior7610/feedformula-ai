#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Générateur premium de branding FeedFormula AI via l'API Afri (gpt-image-2).

Objectifs :
- générer les visuels branding premium demandés par le bloc de nuit,
- sauvegarder les PNG dans `assets/branding/`,
- appliquer un post-traitement pour obtenir les dimensions finales voulues,
- réessayer automatiquement en cas d'erreur temporaire,
- produire un rapport Markdown détaillé dans `docs/RAPPORT_BRANDING.md`.

Exécution :
    python assets/generer_branding_premium.py

Prérequis :
- AFRI_API_KEY dans `.env` ou dans l'environnement
- dépendance `openai`
- dépendance `pillow` recommandée pour le redimensionnement final
"""

from __future__ import annotations

import argparse
import base64
import os
import random
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from openai import OpenAI

try:
    from dotenv import load_dotenv
except Exception:

    def load_dotenv(*args: Any, **kwargs: Any) -> bool:
        return False


try:
    from PIL import Image, ImageOps
except Exception:  # pragma: no cover
    Image = None  # type: ignore
    ImageOps = None  # type: ignore

BASE_URL = (os.getenv("AFRI_BASE_URL") or "https://build.lewisnote.com/v1").rstrip("/")
MODEL = "gpt-image-2"
SIZE = "1024x1024"
QUALITY = "high"
STYLE = "vivid"
MAX_RETRIES = 3
JOB_PAUSE_SECONDS = 10
REQUEST_TIMEOUT_SECONDS = 240
QUALITY_FALLBACKS = ("high", "auto", "medium")
STYLE_FALLBACKS = ("vivid", None)


@dataclass
class BrandJob:
    filename: str
    prompt: str
    exact_size: Tuple[int, int]
    quality: Optional[str] = None
    style: Optional[str] = None
    allow_style_fallbacks: bool = True
    max_retries: Optional[int] = None


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_env_file(env_path: Path) -> Dict[str, str]:
    result: Dict[str, str] = {}
    if not env_path.exists():
        return result
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        result[key.strip()] = value.strip().strip('"').strip("'")
    return result


def load_api_key(project_root: Path) -> str:
    key = (os.getenv("AFRI_API_KEY") or "").strip()
    if key:
        return key
    env_map = read_env_file(project_root / ".env")
    key = (env_map.get("AFRI_API_KEY") or "").strip()
    if key:
        return key
    raise RuntimeError(
        "AFRI_API_KEY introuvable. Ajoutez-la dans le fichier .env à la racine du projet."
    )


def ensure_png_bytes(raw: bytes) -> bytes:
    if not raw:
        raise ValueError("Image vide renvoyée par l'API.")
    return raw


def describe_exception(exc: Exception) -> str:
    parts: List[str] = [f"type={type(exc).__name__}", f"message={exc}"]
    for attr in ("status_code", "code", "error", "body", "response"):
        if not hasattr(exc, attr):
            continue
        value = getattr(exc, attr)
        if value is None:
            continue
        try:
            if attr == "response" and hasattr(value, "text"):
                text = value.text
                if text:
                    parts.append(f"response.text={text}")
                continue
            parts.append(f"{attr}={value}")
        except Exception:
            parts.append(f"{attr}=<unavailable>")
    return " | ".join(parts)


def extract_image_bytes(response: Any) -> bytes:
    data = getattr(response, "data", None)
    if isinstance(data, list) and data:
        first = data[0]
        b64_data = getattr(first, "b64_json", None) or getattr(
            first, "image_base64", None
        )
        if b64_data:
            return base64.b64decode(b64_data)
        url = getattr(first, "url", None)
        if url:
            import urllib.request

            with urllib.request.urlopen(url, timeout=REQUEST_TIMEOUT_SECONDS) as resp:
                return resp.read()
    if hasattr(response, "model_dump"):
        payload = response.model_dump()
        if isinstance(payload, dict):
            data = payload.get("data") or []
            if data:
                first = data[0]
                if isinstance(first, dict):
                    b64_data = first.get("b64_json") or first.get("image_base64")
                    if b64_data:
                        return base64.b64decode(b64_data)
                    url = first.get("url")
                    if url:
                        import urllib.request

                        with urllib.request.urlopen(
                            url, timeout=REQUEST_TIMEOUT_SECONDS
                        ) as resp:
                            return resp.read()
    raise RuntimeError("Aucune image n'a été trouvée dans la réponse de l'API.")


def save_png(raw: bytes, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(raw)


def postprocess_exact_size(
    output_path: Path, exact_size: Tuple[int, int]
) -> Tuple[int, int]:
    if Image is None or ImageOps is None:
        return exact_size
    with Image.open(output_path) as image:
        rgba = image.convert("RGBA")
        resampling = getattr(Image, "Resampling", None)
        lanczos = getattr(resampling, "LANCZOS", 1) if resampling is not None else 1
        fitted = ImageOps.fit(rgba, exact_size, method=lanczos)
        fitted.save(output_path, format="PNG")
        return fitted.size


def generate_one(client: OpenAI, job: BrandJob, output_path: Path) -> Dict[str, Any]:
    last_error: Optional[Exception] = None
    attempt_details: List[str] = []
    max_retries = job.max_retries or MAX_RETRIES
    quality_candidates = [job.quality] if job.quality else list(QUALITY_FALLBACKS)
    if job.allow_style_fallbacks:
        style_candidates = (
            [job.style] if job.style is not None else list(STYLE_FALLBACKS)
        )
        if not style_candidates:
            style_candidates = [None]
    else:
        style_candidates = [None]

    for attempt in range(1, max_retries + 1):
        quality = quality_candidates[(attempt - 1) % len(quality_candidates)]
        style = style_candidates[(attempt - 1) % len(style_candidates)]

        try:
            print(
                f"   ↳ essai {attempt}/{MAX_RETRIES} avec quality={quality}"
                + (f", style={style}" if style is not None else ", style=omitted")
            )
            request_kwargs: Dict[str, Any] = {
                "model": MODEL,
                "prompt": job.prompt,
                "size": SIZE,
                "quality": quality,
            }
            if style is not None:
                request_kwargs["style"] = style

            started = time.perf_counter()
            response = client.images.generate(**request_kwargs)
            elapsed_s = time.perf_counter() - started
            raw = ensure_png_bytes(extract_image_bytes(response))
            save_png(raw, output_path)
            final_size = postprocess_exact_size(output_path, job.exact_size)
            print(
                f"✅ {job.filename} généré ({final_size[0]}x{final_size[1]}) en {elapsed_s:.1f}s"
            )
            return {
                "filename": job.filename,
                "status": "success",
                "attempts": attempt,
                "width": final_size[0],
                "height": final_size[1],
                "quality_used": quality,
                "style_used": style or "omitted",
                "elapsed_seconds": round(elapsed_s, 2),
                "output_path": str(output_path),
            }
        except Exception as exc:
            last_error = exc
            detail = describe_exception(exc)
            attempt_details.append(f"essai {attempt}: {detail}")
            if attempt >= MAX_RETRIES:
                break
            sleep_s = min(30.0, 3.0 * (2 ** (attempt - 1))) + random.uniform(0.5, 1.5)
            print(
                f"⚠️ {job.filename} tentative {attempt}/{MAX_RETRIES} échouée : {detail}"
            )
            print(f"   ↻ nouvelle tentative dans {sleep_s:.1f}s")
            time.sleep(sleep_s)

    assert last_error is not None
    final_detail = describe_exception(last_error)
    print(f"❌ Échec final pour {job.filename}: {final_detail}")
    return {
        "filename": job.filename,
        "status": "failed",
        "attempts": MAX_RETRIES,
        "width": job.exact_size[0],
        "height": job.exact_size[1],
        "error_type": type(last_error).__name__,
        "error_message": str(last_error),
        "error_detail": final_detail,
        "attempt_details": " || ".join(attempt_details),
        "output_path": str(output_path),
    }


def get_jobs() -> List[BrandJob]:
    return [
        BrandJob(
            filename="logo_principal_hd.png",
            exact_size=(1024, 1024),
            prompt=(
                "Professional logo design for FeedFormula AI, an African agricultural AI application for livestock farmers in Benin, West Africa. "
                "Central symbol: A stylized African corn cob where each kernel is replaced by a luminous golden pixel or circuit node, creating a seamless fusion between traditional African agriculture and modern artificial intelligence. The corn cob should have a slight curve, appearing vibrant and alive. The stem subtly forms the letter F of FeedFormula. "
                "Surrounding the corn: Four small minimalist animal silhouettes in deep green — a chicken, a cow, a sheep, and a fish — arranged symmetrically around the corn, representing the diversity of livestock managed by the app. "
                "Typography: Below the symbol, 'FeedFormula AI' in a modern geometric sans-serif font. 'FeedFormula' in deep forest green #1B5E20, bold weight. 'AI' in golden #F9A825, same weight. Below in smaller text: 'Nourrir l Afrique par l IA' in medium weight. "
                "Color palette: Deep forest green #1B5E20 dominant, golden yellow #F9A825 as accent, pure white #FFFFFF for details. Background: pure white #FFFFFF. "
                "Style: Minimalist, modern, professional. Inspired by top-tier tech company logos but with unmistakable African identity. Scalable — readable at 32x32 pixels as app icon. No gradients in the main symbol — flat design only. High contrast for printing in black and white. Square format. Ultra high resolution."
            ),
        ),
        BrandJob(
            filename="aya_mascotte_officielle.png",
            exact_size=(1024, 1024),
            prompt=(
                "Official mascot design for Aya, the AI assistant of FeedFormula AI agricultural application in Africa. "
                "Character concept: Aya is a personified golden corn cob from West Africa — specifically Benin. She is warm, expressive, energetic, and deeply African in her personality and visual design. "
                "Physical design: Body is a plump healthy golden corn cob (#F9A825 to #FF8F00 gradient) with well-defined kernels that have a slight luminous glow suggesting AI intelligence within. Head is friendly, top kernels form a natural face area. Eyes are large expressive cartoon eyes with long lashes, white sclera, deep brown irises, small golden highlight dot in each eye. Mouth is a wide warm genuine smile showing small white teeth, expressing joy and welcome. Arms are thin but expressive, emerging from the sides in a welcoming gesture. Hands are small and rounded with four fingers each. Legs are short sturdy rounded legs at the base. Crown is a lush crown of fresh green corn leaves (#2E7D32) on top like a natural hat. Accessories include a small golden sparkle near the crown suggesting AI magic. "
                "Emotional state: joyful welcome, smiling broadly, arms wide open, slight bounce in posture, sparkles around her, radiating warmth and friendliness. Art style: modern African cartoon character design, not Japanese anime, clean vector-art appearance, smooth lines, professional character design quality, distinctly African in feel. Background: transparent PNG with alpha channel. No text in the image."
            ),
        ),
        BrandJob(
            filename="aya_celebration.png",
            exact_size=(1024, 1024),
            prompt=(
                "Same Aya character from FeedFormula AI but in celebration state used when user levels up or earns a trophy. "
                "Same physical design as official Aya but arms raised in full victory pose above head, mouth open in maximum joy expression, teeth visible, eyes crinkled with happiness, body slightly jumping off ground, surrounded by colorful confetti in green and gold, golden stars and sparkles exploding around her, small trophy icon floating nearby, energy lines suggesting explosive joy. Background: transparent PNG. Same art style as official Aya mascot."
            ),
        ),
        BrandJob(
            filename="aya_triste.png",
            exact_size=(1024, 1024),
            prompt=(
                "Same Aya character from FeedFormula AI but in sad missing you state used when user hasn't opened the app for 2+ days. "
                "Same physical design as official Aya but head slightly drooped forward and to the side, eyes half-closed with sad expression, eyebrows angled upward in the middle, a single large golden tear rolling down the right cheek, arms hanging loosely at sides, one hand holding a small wilted green leaf, body posture suggesting loneliness, small rain cloud above her head with 2-3 raindrops, overall color slightly desaturated compared to joyful version suggesting sadness. Background: transparent PNG. Same art style as official Aya mascot."
            ),
        ),
        BrandJob(
            filename="aya_urgence.png",
            exact_size=(1024, 1024),
            prompt=(
                "Same Aya character but in urgent alert state used for VetScan emergencies and severe alerts. "
                "Same Aya but eyes wide open in alert concern expression, one hand raised as warning gesture, other hand holding a small red warning triangle, small red medical cross floating near her, urgency lines radiating from body, slight red tint to the urgency aura around her, expression serious but caring, not scary. Background: transparent PNG. Same art style as official Aya mascot."
            ),
        ),
        BrandJob(
            filename="hero_image_accueil.png",
            exact_size=(1792, 1024),
            prompt=(
                "Hero illustration for FeedFormula AI mobile app welcome screen. This is the most important image of the entire brand — it must be stunning. "
                "Scene composition landscape. LEFT THIRD: A Beninese farmer male aged 35-40 wearing traditional Beninese colorful clothing in blue and orange fabric/outfit, warm proud confident smile, holding a modern Android smartphone with both hands, looking at the screen with genuine excitement and satisfaction. The phone screen shows a green interface with golden numbers and text. Dark brown skin, warmly lit by African sunlight. CENTER: A digital bridge with floating holographic display showing a glowing green corn cob logo, floating data particles connecting farmer to animals, golden mathematical formulas dissolving into feed, the Aya mascot floating joyfully. RIGHT THIRD: A small diverse group of healthy thriving West African livestock animals arranged naturally: 3-4 plump healthy broiler chickens in front, 1 healthy Borgou zebu cow, 2 Djallonké sheep, and a small fish tank or pond suggesting tilapia. Background: modern but recognizably West African farm setting, green fields, clean farm buildings, blue sky with warm golden clouds, late afternoon sun. Lighting: warm golden hour African sunlight from the right with cinematic rim lighting. Color palette deep green #1B5E20 and gold #F9A825 with warm browns and sky blue. Art style: high-quality digital illustration, semi-realistic, premium app store marketing illustration, not photographic, not cartoon."
            ),
        ),
        BrandJob(
            filename="hero_poulets_premium.png",
            exact_size=(1024, 1024),
            prompt=(
                "Premium illustration for FeedFormula AI NutriCore module — poultry farming in Benin, West Africa. "
                "Scene: a modern clean poultry farm in Benin. Foreground: 6-8 healthy plump broiler chickens in the golden ratio of their growth cycle, feathers gleaming, active, on clean dry litter in a well-ventilated modern chicken house. Middle ground: a Beninese female farmer aged 30-35, traditional clothing, hair wrapped in colorful fabric, checking her chickens with pride, holding a smartphone showing the FeedFormula AI green interface, smiling genuinely. Background: open farm setting, green trees, warm Beninese sky. Floating above the scene: subtle holographic display showing ration optimale maïs 60%, soja 25%, poisson 15% and économie 18 500 FCFA ce mois in golden text, partially transparent. Lighting: warm African golden hour light. Style: premium digital illustration, semi-realistic."
            ),
        ),
        BrandJob(
            filename="hero_bovins_premium.png",
            exact_size=(1024, 1024),
            prompt=(
                "Premium illustration for FeedFormula AI — cattle farming in Benin, West Africa. Scene: lush green pasture in the Borgou region of northern Benin at golden hour. Foreground: 2-3 magnificent Borgou zebu cattle, healthy and well-fed, coats gleaming in the sun, distinctive humps and long horns authentically African. A Beninese male farmer aged 40-45 wearing a traditional boubou in deep blue fabric stands proudly next to his cattle, hand gently touching one cow, holding a smartphone in the other hand. Background: rolling green hills of Borgou, acacia trees, warm orange-gold sky. Floating near the phone screen: production laitière +35% and coût ration 850 FCFA/jour in golden holographic text. Style: premium cinematic digital illustration."
            ),
        ),
        BrandJob(
            filename="onboarding_1.png",
            exact_size=(1024, 1792),
            prompt=(
                "First onboarding screen illustration for FeedFormula AI mobile app, portrait format, welcoming screen for new users. Central element: the FeedFormula AI logo large and prominent with a subtle golden glow effect. Below the logo: the Aya mascot in her joyful welcome pose, arms open wide. Background: deep forest green #1B5E20 with a subtle pattern of tiny golden corn kernels arranged in a wave pattern across the background. At the bottom: a soft golden gradient fade. Atmosphere: welcoming, professional, African, premium first-time app experience. Leave clear space for title area at top, description area in middle, button area at bottom. Premium mobile app onboarding illustration."
            ),
        ),
        BrandJob(
            filename="icones_8_modules_premium.png",
            exact_size=(1024, 512),
            prompt=(
                "Premium icon set for FeedFormula AI's 8 modules displayed as a 4x2 grid on a white background, each icon in its own rounded square container. Design system: container deep green #1B5E20 background, icon style modern outline with golden #F9A825 fill accents, 20px spacing between containers, labels below each in dark green text. Modules: NutriCore with a corn cob transforming into a mathematical formula and small chicken and cow silhouettes; VetScan with a stethoscope forming a heart shape and a digital eye scanner; ReproTrack with a circular calendar cycle and animal silhouettes plus a cow and calf connected by a golden arc; PastureMap with a satellite view of green fields and a GPS pin; FarmManager with a microphone soundwave transforming into a structured document/table; FarmAcademy with an open book, graduation cap and lightbulb; FarmCast with a play button combined with a farmer hat and satellite dish; FarmCommunity with three connected human figures in a triangle network. Overall grid feeling: professional, cohesive, modern African tech aesthetic."
            ),
        ),
        BrandJob(
            filename="splash_screen_premium.png",
            exact_size=(1024, 1792),
            prompt=(
                "Premium splash screen for FeedFormula AI mobile app, portrait format. Full bleed background: deep African night sky transitioning to golden sunrise at the horizon, stars visible at top, warm golden glow at bottom, representing a new day beginning for African farmers. Center: the FeedFormula AI logo large, glowing with a subtle golden aura, appearing to rise with the sunrise. Below logo: Aya mascot in celebration pose, emerging from the golden light, surrounded by golden particles. Horizon line: silhouette of African savanna with acacia trees, rolling hills, small farm buildings. Foreground: silhouettes of African livestock animals (cow, chickens, sheep) against the warm golden light. Loading indicator: thin golden line at the bottom, 60% filled. Atmosphere: epic, hopeful, African pride, new beginnings, technology and nature united. Premium cinematic illustration."
            ),
        ),
        BrandJob(
            filename="banniere_discord_premium.png",
            exact_size=(1792, 448),
            prompt=(
                "Premium Discord server banner for FeedFormula AI, wide format. Left section: large FeedFormula AI text in white bold, below L intelligence africaine au service de vos animaux in golden text, Aya mascot standing proudly next to the text. Center section: the FeedFormula AI logo, large and glowing. Right section: collage of African livestock animals in a beautiful arrangement, chickens, cow, sheep, fish in a harmonious composition, all healthy and well-fed. Background: deep forest green #1B5E20 with subtle topographic and circuit pattern overlay in slightly lighter green, gentle golden gradient from left to right. Professional, prestigious, African tech excellence."
            ),
        ),
        BrandJob(
            filename="carte_afrique_impact.png",
            exact_size=(1024, 1024),
            prompt=(
                "Impact visualization map for FeedFormula AI showing its reach across West Africa. A stylized beautiful map of West Africa, artistic and premium, rendered in deep green tones on a dark background. Benin is highlighted prominently with a bright golden glow and the FeedFormula AI logo pinned on it like a map pin. Radiating golden connection lines spread from Benin to neighboring countries Togo, Niger, Burkina Faso, Nigeria, Ghana, Senegal, Mali, Ivory Coast. On each country a small golden dot with a number suggesting users or reach. Floating data elements: 180,000+ éleveurs au Bénin, 15 pays d Afrique de l Ouest, 50 langues africaines, all in golden text. At the bottom of the map: small silhouettes of African livestock animals in golden color. Background: deep space-like dark green and black making the glowing golden map elements pop. Premium data visualization and artistic map design."
            ),
        ),
        BrandJob(
            filename="offres_commerciales.png",
            exact_size=(1792, 1024),
            prompt=(
                "Premium pricing tiers illustration for FeedFormula AI, wide format showing 5 subscription tiers arranged horizontally. Card 1 FREE in gray silver with a simple circle crown icon, name FREE, price 0 FCFA, three feature icons below. Card 2 STANDARD in green with a bronze star crown icon, name STANDARD, price 2 000 FCFA, badge Populaire. Card 3 PREMIUM in deep green larger and elevated, silver crown icon, name PREMIUM, price 8 000 FCFA, badge Recommandé with golden glow. Card 4 VIP in gold with a golden crown icon, name VIP, price 25 000 FCFA, shimmer effect. Card 5 GOLD in premium gold and black with diamond crown icon, name GOLD, price 75 000 FCFA, premium dark background with gold accents. Background clean white with subtle green geometric pattern. Style premium SaaS pricing page illustration."
            ),
        ),
        BrandJob(
            filename="presentation_investisseurs.png",
            exact_size=(1792, 1024),
            prompt=(
                "Cover slide illustration for FeedFormula AI investor presentation deck. Powerful professional boardroom-quality illustration that commands respect and conveys massive opportunity. Top left: FeedFormula AI logo smaller and elegant. Center: bold dramatic composition showing the continent of Africa rendered in golden light against a deep green and dark background. From the center of Africa (Benin), golden light radiates outward across the continent and transforms into growing crops, healthy animals, connected smartphones, digital signals, and prosperous African farmers standing tall. Bottom: key statistics in clean golden typography, 180,000+ éleveurs, 50 langues, 5 offres. Overall message: this is not just an app, this is the agricultural transformation of Africa. Premium investment deck quality, cinematic, dramatic, aspirational, deep greens and rich golds."
            ),
        ),
    ]


def get_minimal_test_job() -> List[BrandJob]:
    return [
        BrandJob(
            filename="api_test_probe.png",
            exact_size=(1024, 1024),
            quality="auto",
            style=None,
            allow_style_fallbacks=False,
            prompt=(
                "Minimal validation prompt for FeedFormula AI image API. "
                "Create a clean, simple, professional square icon featuring a single stylized African corn cob in deep green and gold on a white background. "
                "No text. No extra objects. High contrast. Simple composition."
            ),
        )
    ]


def write_report(
    report_path: Path, items: List[Dict[str, Any]], started_at: str, finished_at: str
) -> None:
    lines: List[str] = []
    lines.append("# Rapport Branding Premium FeedFormula AI")
    lines.append("")
    lines.append(f"- Démarré : {started_at}")
    lines.append(f"- Terminé : {finished_at}")
    lines.append(f"- Modèle : {MODEL}")
    lines.append(f"- Taille d'appel : {SIZE}")
    lines.append(f"- Qualité : {QUALITY}")
    lines.append(f"- Style : {STYLE}")
    lines.append("")
    lines.append("## Images générées")
    lines.append("")
    for item in items:
        rel_path = f"assets/branding/{item['filename']}"
        size_txt = f"{item['width']}x{item['height']}"
        lines.append(f"### {item['filename']}")
        lines.append(f"- Chemin : `{rel_path}`")
        lines.append(f"- Dimensions : `{size_txt}`")
        lines.append(f"- Statut : **{item['status']}**")
        if item.get("status") == "success":
            lines.append(
                "- Suggestion d'utilisation : intégration directe dans le branding premium, app mobile, landing page et communications institutionnelles."
            )
        else:
            lines.append(
                "- Suggestion d'utilisation : à régénérer ou remplacer par un visuel alternatif."
            )
        if item.get("error_message"):
            lines.append(f"- Erreur : `{item['error_message']}`")
        lines.append("")
    report_path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Générateur branding premium FeedFormula AI"
    )
    parser.add_argument(
        "--test-minimal",
        action="store_true",
        help="Lance un test API minimal sur une seule image très simple.",
    )
    return parser.parse_args()


def main() -> int:
    script_path = Path(__file__).resolve()
    project_root = script_path.parent.parent
    assets_dir = script_path.parent / "branding"
    docs_dir = project_root / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    assets_dir.mkdir(parents=True, exist_ok=True)

    args = parse_args()

    load_dotenv(project_root / ".env")
    try:
        api_key = load_api_key(project_root)
    except Exception as exc:
        print(f"❌ {exc}")
        return 1

    client = OpenAI(api_key=api_key, base_url=BASE_URL)
    started_at = utc_now_iso()
    results: List[Dict[str, Any]] = []

    print("🚀 Lancement du branding premium FeedFormula AI")
    print(f"📁 Sortie : {assets_dir}")
    print(f"🧠 Modèle : {MODEL} | size={SIZE} | quality={QUALITY} | style={STYLE}")
    if args.test_minimal:
        print("🧪 Mode test minimal API activé")

    jobs = get_minimal_test_job() if args.test_minimal else get_jobs()

    for job in jobs:
        output_path = assets_dir / job.filename
        print(f"\n▶ Génération : {job.filename}")
        result = generate_one(client, job, output_path)
        results.append(result)
        if not args.test_minimal:
            time.sleep(JOB_PAUSE_SECONDS)

    finished_at = utc_now_iso()
    report_path = docs_dir / "RAPPORT_BRANDING.md"
    write_report(report_path, results, started_at, finished_at)

    success = sum(1 for item in results if item["status"] == "success")
    failed = sum(1 for item in results if item["status"] == "failed")
    print("\n📊 Résumé final")
    print(f"✅ Succès : {success}")
    print(f"❌ Échecs : {failed}")
    print(f"🧾 Rapport : {report_path}")
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
