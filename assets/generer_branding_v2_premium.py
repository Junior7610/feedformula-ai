#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Génère le branding premium V2 de FeedFormula AI via l'API Afri.

Sorties :
- images PNG dans assets/branding_v2/
- rapport Markdown dans docs/RAPPORT_BRANDING_V2.md

Sécurité : la clé API n'est jamais écrite dans ce fichier. Le script lit
AFRI_API_KEY depuis l'environnement ou depuis un parseur .env robuste intégré.
"""

from __future__ import annotations

import base64
import os
import time
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple, cast

import requests

try:
    from PIL import Image, ImageDraw, ImageFont
except Exception:  # pragma: no cover
    Image = None  # type: ignore
    ImageDraw = None  # type: ignore
    ImageFont = None  # type: ignore

try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None  # type: ignore


ROOT_DIR = Path(__file__).resolve().parent.parent


def _read_env_file(path: Path) -> Dict[str, str]:
    values: Dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


_ENV_FALLBACK = _read_env_file(ROOT_DIR / ".env")
API_KEY = (os.getenv("AFRI_API_KEY") or _ENV_FALLBACK.get("AFRI_API_KEY") or "").strip()
BASE_URL = (
    os.getenv("AFRI_BASE_URL")
    or os.getenv("AFRI_API_BASE_URL")
    or _ENV_FALLBACK.get("AFRI_BASE_URL")
    or _ENV_FALLBACK.get("AFRI_API_BASE_URL")
    or "https://build.lewisnote.com/v1"
).rstrip("/")
MODEL = os.getenv("AFRI_IMAGE_MODEL", "gpt-image-2").strip()
QUALITY = os.getenv("AFRI_IMAGE_QUALITY", "hd").strip()
STYLE = os.getenv("AFRI_IMAGE_STYLE", "vivid").strip()
OUTPUT_DIR = Path("assets/branding_v2")
REPORT_PATH = Path("docs/RAPPORT_BRANDING_V2.md")
ALLOW_LOCAL_FALLBACK = os.getenv(
    "FEEDFORMULA_BRANDING_LOCAL_FALLBACK", "1"
).strip().lower() in {"1", "true", "yes", "oui"}
FORCE_LOCAL_FALLBACK = os.getenv(
    "FEEDFORMULA_FORCE_LOCAL_BRANDING", "0"
).strip().lower() in {"1", "true", "yes", "oui"}
_REMOTE_DISABLED = False
GENERATION_NOTES: Dict[str, str] = {}
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)


ImageSize = Literal["1024x1024", "1792x1024", "1024x1792", "1792x512"]


@dataclass(frozen=True)
class ImageJob:
    nom: str
    prompt: str
    taille: ImageSize = "1792x1024"


def _download_url(url: str) -> bytes:
    request = urllib.request.Request(url=url, method="GET")
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read()


def _extraire_image(data: Any) -> Optional[bytes]:
    if hasattr(data, "model_dump"):
        data = data.model_dump()
    if not isinstance(data, dict):
        return None
    items = data.get("data") or []
    if not items:
        return None
    image_data = items[0]
    if not isinstance(image_data, dict):
        if hasattr(image_data, "model_dump"):
            image_data = image_data.model_dump()
        else:
            image_data = {
                "b64_json": getattr(image_data, "b64_json", None),
                "image_base64": getattr(image_data, "image_base64", None),
                "url": getattr(image_data, "url", None),
            }
    for key in ("b64_json", "image_base64", "audio_base64", "content"):
        value = image_data.get(key)
        if isinstance(value, str) and value.strip():
            return base64.b64decode(value)
    url = image_data.get("url")
    if isinstance(url, str) and url.strip():
        return _download_url(url)
    return None


def _base_url_candidates() -> List[str]:
    candidates = [
        BASE_URL,
        os.getenv("AFRI_IMAGE_BASE_URL", "").strip(),
        os.getenv("OPENAI_BASE_URL", "").strip(),
    ]
    expanded: List[str] = []
    for candidate in candidates:
        if not candidate:
            continue
        clean = candidate.rstrip("/")
        expanded.append(clean)
        if not clean.endswith("/v1"):
            expanded.append(f"{clean}/v1")
    expanded.append("https://build.lewisnote.com/v1")
    seen = set()
    unique = []
    for item in expanded:
        normalized = item.rstrip("/")
        if normalized and normalized not in seen:
            unique.append(normalized)
            seen.add(normalized)
    return unique


def _endpoint_paths() -> List[str]:
    explicit = os.getenv("AFRI_IMAGE_ENDPOINT", "").strip()
    paths = [
        explicit,
        "/images/generations",
        "/image/generations",
        "/images/generate",
        "/image/generate",
        "/v1/images/generations",
    ]
    seen = set()
    result = []
    for path in paths:
        if not path:
            continue
        normalized = path if path.startswith("/") else f"/{path}"
        if normalized not in seen:
            result.append(normalized)
            seen.add(normalized)
    return result


def _request_payload(
    prompt: str, taille: ImageSize, include_quality_style: bool = True
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "model": MODEL,
        "prompt": prompt,
        "n": 1,
        "size": taille,
    }
    if include_quality_style:
        payload.update({"quality": QUALITY, "style": STYLE})
    return payload


def _generate_with_requests(prompt: str, taille: ImageSize) -> Optional[bytes]:
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }
    not_found_count = 0
    attempts = 0
    for base_url in _base_url_candidates():
        for path in _endpoint_paths():
            endpoint = f"{base_url}{path}"
            # Évite les doublons du type /v1/v1/images/generations.
            endpoint = endpoint.replace("/v1/v1/", "/v1/")
            for include_quality_style in (True, False):
                attempts += 1
                response = requests.post(
                    endpoint,
                    headers=headers,
                    json=_request_payload(prompt, taille, include_quality_style),
                    timeout=180,
                )
                if response.status_code == 404:
                    not_found_count += 1
                    print(f"⚠️ Endpoint introuvable: {endpoint}")
                    break
                if response.status_code in {400, 422} and include_quality_style:
                    # Certains endpoints compatibles OpenAI n'acceptent pas quality/style.
                    print(
                        f"⚠️ Payload hd/vivid refusé ({response.status_code}), fallback minimal..."
                    )
                    continue
                if response.status_code != 200:
                    print(f"⚠️ HTTP {response.status_code}: {response.text[:400]}")
                    break
                return _extraire_image(response.json())
    if attempts and not_found_count == attempts:
        raise RuntimeError(
            "Aucun endpoint image compatible trouvé. "
            "L'URL actuelle retourne 404 pour les routes images testées. "
            "Définis AFRI_IMAGE_BASE_URL ou AFRI_IMAGE_ENDPOINT si ton environnement utilise une route différente."
        )
    return None


def _generate_with_openai(prompt: str, taille: ImageSize) -> Optional[bytes]:
    if OpenAI is None:
        return None
    for base_url in _base_url_candidates():
        try:
            client = OpenAI(api_key=API_KEY, base_url=base_url, timeout=180)
            try:
                response = client.images.generate(
                    model=MODEL,
                    prompt=prompt,
                    size=cast(Any, taille),
                    quality=cast(Any, QUALITY),
                    style=cast(Any, STYLE),
                )
            except TypeError:
                response = client.images.generate(
                    model=MODEL, prompt=prompt, size=cast(Any, taille)
                )
            raw = _extraire_image(response)
            if raw:
                return raw
        except Exception as exc:
            print(f"⚠️ OpenAI SDK {base_url}: {exc}")
    return None


def _parse_size(taille: str) -> Tuple[int, int]:
    width, height = taille.lower().split("x", 1)
    return int(width), int(height)


def _font(size: int):
    if ImageFont is None:
        return None
    for font_name in ("DejaVuSans-Bold.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(font_name, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _local_fallback_image(nom_fichier: str, prompt: str, taille: ImageSize) -> bool:
    """Crée un visuel local premium minimal si l'API image est indisponible."""
    if Image is None or ImageDraw is None:
        print("❌ Pillow indisponible: fallback local impossible.")
        return False
    width, height = _parse_size(taille)
    image = Image.new("RGB", (width, height), "#1B5E20")
    draw = ImageDraw.Draw(image)
    # Dégradé vertical vert profond -> vert plus clair.
    for y in range(height):
        ratio = y / max(1, height - 1)
        r = int(7 + ratio * 20)
        g = int(45 + ratio * 75)
        b = int(18 + ratio * 28)
        draw.line([(0, y), (width, y)], fill=(r, g, b))
    # Motif discret africain/data.
    step = max(48, width // 16)
    for x in range(-step, width + step, step):
        draw.line([(x, 0), (x + height, height)], fill=(249, 168, 37), width=2)
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    margin = max(44, width // 24)
    odraw.rounded_rectangle(
        [(margin, margin), (width - margin, height - margin)],
        radius=max(28, width // 40),
        fill=(255, 255, 255, 28),
        outline=(249, 168, 37, 180),
        width=max(3, width // 300),
    )
    image = Image.alpha_composite(image.convert("RGBA"), overlay)
    draw = ImageDraw.Draw(image)
    title = nom_fichier.replace("_", " ").replace(".png", "").title()
    title_font = _font(max(34, width // 22))
    subtitle_font = _font(max(20, width // 44))
    mark_font = _font(max(72, width // 10))
    mark = "🌾"
    bbox = draw.textbbox((0, 0), mark, font=mark_font)
    draw.text(
        ((width - (bbox[2] - bbox[0])) / 2, height * 0.24),
        mark,
        font=mark_font,
        fill="#F9A825",
    )
    bbox = draw.textbbox((0, 0), title, font=title_font)
    draw.text(
        ((width - (bbox[2] - bbox[0])) / 2, height * 0.43),
        title,
        font=title_font,
        fill="white",
    )
    subtitle = "FeedFormula AI • Branding V2 • fallback local"
    bbox = draw.textbbox((0, 0), subtitle, font=subtitle_font)
    draw.text(
        ((width - (bbox[2] - bbox[0])) / 2, height * 0.54),
        subtitle,
        font=subtitle_font,
        fill="#F9A825",
    )
    hint = "API image Afri indisponible dans cet environnement"
    bbox = draw.textbbox((0, 0), hint, font=subtitle_font)
    draw.text(
        ((width - (bbox[2] - bbox[0])) / 2, height * 0.62),
        hint,
        font=subtitle_font,
        fill=(255, 255, 255, 210),
    )
    image.convert("RGB").save(OUTPUT_DIR / nom_fichier, format="PNG")
    GENERATION_NOTES[nom_fichier] = "fallback_local_pillow_api_image_indisponible"
    print(f"✅ Fallback local sauvegardé : {OUTPUT_DIR / nom_fichier}")
    return True


def generer_image(
    nom_fichier: str, prompt: str, taille: ImageSize = "1792x1024"
) -> bool:
    """Génère une image et la sauvegarde dans assets/branding_v2/."""
    global _REMOTE_DISABLED
    if FORCE_LOCAL_FALLBACK:
        return _local_fallback_image(nom_fichier, prompt, taille)
    if not API_KEY:
        print("⚠️ AFRI_API_KEY introuvable: utilisation du fallback local.")
        return (
            _local_fallback_image(nom_fichier, prompt, taille)
            if ALLOW_LOCAL_FALLBACK
            else False
        )
    if _REMOTE_DISABLED and ALLOW_LOCAL_FALLBACK:
        return _local_fallback_image(nom_fichier, prompt, taille)

    print(f"🎨 Génération : {nom_fichier} ({taille})...")
    for tentative in range(3):
        try:
            img_bytes = _generate_with_requests(prompt, taille)
            if not img_bytes:
                img_bytes = _generate_with_openai(prompt, taille)
            if not img_bytes:
                print("⚠️ Réponse sans image exploitable.")
                time.sleep(5 + tentative * 5)
                continue

            chemin = OUTPUT_DIR / nom_fichier
            chemin.write_bytes(img_bytes)
            GENERATION_NOTES[nom_fichier] = "api_afri"
            print(f"✅ Sauvegardé : {chemin}")
            return True
        except Exception as exc:
            print(f"⚠️ Tentative {tentative + 1}: {exc}")
            if "Aucun endpoint image compatible" in str(exc):
                _REMOTE_DISABLED = True
                if ALLOW_LOCAL_FALLBACK:
                    return _local_fallback_image(nom_fichier, prompt, taille)
            time.sleep(10)

    print(f"❌ Échec API : {nom_fichier}")
    if ALLOW_LOCAL_FALLBACK:
        return _local_fallback_image(nom_fichier, prompt, taille)
    return False


PROMPTS: Dict[str, str] = {
    "logo_feedformula_v2.png": """
Professional ultra-minimalist premium logo for FeedFormula AI, African livestock nutrition AI platform. Square white canvas. Central circular emblem: stylized African corn cob rising from center, kernels become golden hexagonal pixels and neural network dots. Roots subtly form letter F. Thin precision ring with 8 minimalist animal silhouettes facing inward: chicken, cow, sheep, goat, pig, fish, rabbit, guinea fowl. Between each animal a gold data dot. Typography below: FeedFormula in Space Grotesk Bold deep forest green #1B5E20, AI in warm gold #F9A825. Tagline below: Nourrir l'Afrique par l'IA. Flat geometry, no texture, no decorative clutter, readable at 32px, printable black and white, premium Linear/Anthropic-level tech identity with African agricultural soul.
""",
    "aya_officielle_v2.png": """
Official mascot Aya for FeedFormula AI: personified golden corn cob from Benin, transparent PNG. Warm golden hexagonal kernels, subtle AI glow. Top face with large expressive eyes, warm brown irises, catchlights, gentle eyebrows, tiny nose, generous smile with four rounded teeth. Crown of 5-7 deep emerald corn leaves #1B5E20. Thin expressive arms raised in welcoming V, short sturdy legs. Tiny FeedFormula badge on chest, 3 golden stars. African character design tradition, not anime, not western clipart; rounded, dignified, warm, Duolingo-quality mascot, transparent background.
""",
    "aya_celebration_v2.png": """
Aya mascot in maximum celebration state, transparent PNG. Same golden corn cob body and emerald leaf crown, body tilted dynamically, both arms fully upward in triumph, one leg bent mid-jump, mouth open in joyful laughter, eyes delighted. Green-gold-white confetti, gold stars, energy arcs, small golden trophy near hand, +10 star bubble. Immediate emotional joy for points, challenge completion and level up.
""",
    "aya_triste_v2.png": """
Aya mascot sad missing-you state, transparent PNG. Same corn cob but slightly slumped, desaturated golden kernels, drooping corn leaves, one yellowed leaf tip. Eyebrows raised in sadness, half-lidded eyes looking down, one golden tear on cheek, small sad mouth. One hand holds a wilted leaf, subtle grey cloud and raindrops. Gentle empathy, not distressing, designed to invite users back.
""",
    "aya_urgence_v2.png": """
Aya mascot urgent alert state for VetScan emergencies, transparent PNG. Upright, leaning forward, right hand in STOP attention gesture, left hand holds red diamond warning sign with exclamation. Wide concerned eyes, raised eyebrows, caring open mouth. Soft red alert rings, medical cross, urgency energy lines. Golden body and green crown preserved. Caring urgent helper, not aggressive.
""",
    "hero_aviculture_premium.png": """
Breathtaking premium hero illustration for poultry farming in Benin. Left: confident Beninese female farmer in indigo-white traditional wrapper and headwrap holding Android smartphone showing FeedFormula AI green ration screen. Center: translucent holographic feed chart corn 60%, soybean 25%, fish meal 15%, cost 312 FCFA/kg, scale, 7-day calendar, growth arrow. Right: thriving flock of healthy broiler chickens in clean modern poultry house with feeders, nipple drinkers, ventilation, warm golden afternoon light, red laterite soil and green Beninese landscape. Semi-realistic high-end digital illustration, National Geographic plus premium African startup marketing, no text overlay.
""",
    "hero_elevage_bovin_premium.png": """
Epic premium hero for Borgou cattle and dairy farming in northern Benin at golden hour. Three majestic Borgou zebu cattle with hump, sweeping horns, healthy coat; one dairy cow with good udder. Beninese male farmer in deep indigo boubou holding staff and smartphone showing ReproTrack calendar. Sudanian savanna, tall amber grasses, acacia trees, red laterite paths, watering point, warm rim light. Subtle holographic milk tracker and reproduction data. Dignified, cinematic, National Geographic digital illustration.
""",
    "hero_petits_ruminants_premium.png": """
Premium hero for small ruminants in Benin. Mixed flock of Djallonke sheep and West African dwarf goats, lambs close to mothers, ewe nursing lamb, healthy goats with short legs. Beninese woman in bright pagne kneels beside ewe, smartphone showing FeedFormula AI NutriCore ration screen. Southern Benin compound farm with laterite earth, mango/neem shade tree, feeding trough, medicinal plants. Warm intimate documentary illustration, family farm transformed into business.
""",
    "hero_aquaculture_premium.png": """
Premium aquaculture hero for tilapia farming in southern Benin. Split waterline view: above water a Beninese male farmer on pond dike with phone showing FeedFormula AI tilapia feed formula, water quality kit, aeration paddle, inlet pipe; below water thriving Nile tilapia school, natural feeding behavior, clear green-tinted healthy pond water and automatic feeder pellets. Palm trees, lush vegetation, golden reflection, National Geographic aquatic illustration meets tech marketing.
""",
    "hero_porciculture_premium.png": """
Premium pig farming hero in Benin. Clean modern open-sided pig pen with concrete drainage, feed troughs, nipple drinkers. Large White/local sow nursing piglets, growing pigs in excellent condition. Young Beninese man in overalls and boots holding smartphone with NutriCore pig feed formula and clipboard. Holographic feed conversion ratio, daily gain, FCFA cost. Morning energetic agribusiness atmosphere, rural-urban fringe background.
""",
    "hero_cuniculture_premium.png": """
Premium rabbit farming illustration in Benin. Elevated hutches built from local materials, clean and organized. Adult rabbits, doe with litter of kits in nest box, large buck, fresh fodder and pellets. Young Beninese female entrepreneur on stool using FeedFormula AI on phone and writing notebook. Shaded backyard with mango tree, cassava and maize plants. Warm detailed aspirational illustration for youth agribusiness.
""",
    "hero_pintades_premium.png": """
Premium guinea fowl farming hero in northern Benin, Parakou region. 15-20 helmeted guinea fowl with accurate spotted plumage and blue-red casque in semi-intensive outdoor compound, foraging and dust bathing. Bariba/Dendi farmer in white boubou holding smartphone with pintade ration screen. Sudanian savanna, golden grasses, mud-brick compound, market hint in background. Bright northern midday light, cultural authenticity, no text.
""",
    "hero_multispecies_benin.png": """
Master panoramic hero of prosperous multi-species Beninese farm at golden hour. Poultry house, feed preparation station with corn/soy/fish meal and smartphone reading FeedFormula AI formula, mixed grazing paddock with zebu, Djallonke sheep, dwarf goats, tilapia pond, pig section. 5-6 real Beninese farmers, men and women, competent and prosperous. Subtle floating data for each species connected by gold light threads. Cinematic documentary cover image, one platform for every animal and farmer, no text.
""",
    "splash_screen_v2.png": """
Definitive portrait mobile splash screen for FeedFormula AI, 9:16. Bottom red laterite soil with golden outline silhouettes of cow, chicken, sheep, goat, pig, fish, rabbit, guinea fowl. Corn plant grows upward; natural green base becomes digital circuit stem and data leaves. FeedFormula AI logo emerges from the corn plant, Aya mascot warmly welcoming viewer. African dawn sky from deep indigo stars to golden sunrise. Thin gold loading bar at bottom. Tagline subtly at top: L'intelligence africaine au service de vos animaux. Cinematic, hopeful, mobile fullscreen.
""",
    "icones_animaux_production.png": """
Premium 2x5 grid icon set of 10 livestock species for FeedFormula AI. White canvas, each icon in rounded square deep forest green #1B5E20 with subtle inner depth. Isometric friendly professional animals in warm cream with #F9A825 highlights: broiler chicken, laying hen with egg, guinea fowl, dairy cow, Borgou zebu, Djallonke sheep, West African dwarf goat, pig, Nile tilapia, rabbit. Space Grotesk labels in gold below each container. Product UI quality.
""",
    "infographie_nutrition_animale.png": """
Elegant educational infographic in French: La Science de la Nutrition Animale, FeedFormula AI maîtrise les 5 nutriments essentiels. Five circular nutrient wheels: Énergie with corn/cassava/fat, Protéines with soybean/fish meal/groundnut cake, Minéraux with bone/oyster shell/salt, Vitamines with premix/fodder, Eau with water drop. Bottom comparison Avant FeedFormula AI vs Avec FeedFormula AI, unhealthy animal transformed to healthy animal. Clean professional, readable, white background, green and gold accents.
""",
    "carte_impact_benin_v2.png": """
Premium dark data visualization map of Benin's 12 departments. Isometric artistic Benin map with coast, savanna, rivers, green zones by user density, golden pulse circles at department capitals, largest glow in Cotonou with FeedFormula AI pin. Animal icons around regions: zebu/sheep north, chicken/pig/fish south, mixed center. Floating stats: 180,000+ éleveurs, 12 départements, 50 langues, 8 modules. Mission-control dark green background, powerful clean data aesthetic.
""",
    "banniere_presentation_investisseurs.png": """
Powerful investor presentation banner for FeedFormula AI. Left: three circular portraits of Beninese farmers: older cattle farmer, young female poultry entrepreneur, fish pond farmer, with result numbers 45,000 FCFA saved/month, Production +35%, 3min to perfect ration. Center: large FeedFormula AI logo, tagline, big stats 180,000+, 50 Langues, 8 Modules with golden underlines. Right: elegant molecular collage of Borgou zebu, broiler, tilapia, sheep, goat, pig, guinea fowl, rabbit. Deep forest green premium boardroom background, subtle topographic pattern, blank lower band for overlays.
""",
    "progression_niveaux_eleveur.png": """
Wide panoramic gamification banner showing 10-level farmer journey from Semence to Légende Afrique. Winding corn-stem path rises left to right. Seed, seedling, stem, flowering, golden leaf, harvest, owner, master breeder, champion, African legend summit with Aya. Each milestone has farmer progression from beginner tools to smartphone, flock, multi-species farm, mentoring, award, Africa silhouette glowing. Warm inspiring colors, horizontal reading, premium illustration.
""",
    "background_pattern_africain.png": """
Seamlessly tileable sophisticated background pattern for FeedFormula AI. Deep forest green #1B5E20 base. Subtle diamond grid at 15 degrees in gold 15% opacity. Tiny animal silhouettes of 10 species in gold 12% opacity. Adinkra-inspired symbols for growth, strength, knowledge, community. Small data nodes connected by thin lines, African textile meets neural network. Elegant dark surface that rewards close inspection and never competes with content.
""",
}


JOBS: List[ImageJob] = [
    ImageJob(
        "logo_feedformula_v2.png", PROMPTS["logo_feedformula_v2.png"], "1024x1024"
    ),
    ImageJob("aya_officielle_v2.png", PROMPTS["aya_officielle_v2.png"], "1024x1024"),
    ImageJob("aya_celebration_v2.png", PROMPTS["aya_celebration_v2.png"], "1024x1024"),
    ImageJob("aya_triste_v2.png", PROMPTS["aya_triste_v2.png"], "1024x1024"),
    ImageJob("aya_urgence_v2.png", PROMPTS["aya_urgence_v2.png"], "1024x1024"),
    ImageJob("hero_aviculture_premium.png", PROMPTS["hero_aviculture_premium.png"]),
    ImageJob(
        "hero_elevage_bovin_premium.png", PROMPTS["hero_elevage_bovin_premium.png"]
    ),
    ImageJob(
        "hero_petits_ruminants_premium.png",
        PROMPTS["hero_petits_ruminants_premium.png"],
    ),
    ImageJob("hero_aquaculture_premium.png", PROMPTS["hero_aquaculture_premium.png"]),
    ImageJob("hero_porciculture_premium.png", PROMPTS["hero_porciculture_premium.png"]),
    ImageJob("hero_cuniculture_premium.png", PROMPTS["hero_cuniculture_premium.png"]),
    ImageJob("hero_pintades_premium.png", PROMPTS["hero_pintades_premium.png"]),
    ImageJob("hero_multispecies_benin.png", PROMPTS["hero_multispecies_benin.png"]),
    ImageJob("splash_screen_v2.png", PROMPTS["splash_screen_v2.png"], "1024x1792"),
    ImageJob(
        "icones_animaux_production.png",
        PROMPTS["icones_animaux_production.png"],
        "1024x1024",
    ),
    ImageJob(
        "infographie_nutrition_animale.png",
        PROMPTS["infographie_nutrition_animale.png"],
    ),
    ImageJob(
        "carte_impact_benin_v2.png", PROMPTS["carte_impact_benin_v2.png"], "1024x1024"
    ),
    ImageJob(
        "banniere_presentation_investisseurs.png",
        PROMPTS["banniere_presentation_investisseurs.png"],
    ),
    ImageJob(
        "progression_niveaux_eleveur.png",
        PROMPTS["progression_niveaux_eleveur.png"],
        "1792x512",
    ),
    ImageJob(
        "background_pattern_africain.png",
        PROMPTS["background_pattern_africain.png"],
        "1024x1024",
    ),
]


def main() -> int:
    resultats = []
    for job in JOBS:
        ok = generer_image(job.nom, job.prompt, job.taille)
        resultats.append({"nom": job.nom, "taille": job.taille, "succes": ok})
        time.sleep(3)

    print("\n" + "=" * 60)
    print("RAPPORT BRANDING V2 — FEEDFORMULA AI")
    print("=" * 60)
    for result in resultats:
        status = "✅" if result["succes"] else "❌"
        print(f"{status} {result['nom']}")

    succes = sum(1 for result in resultats if result["succes"])
    print(f"\n{succes}/{len(resultats)} images générées")

    with REPORT_PATH.open("w", encoding="utf-8") as f:
        f.write("# Rapport Branding V2\n\n")
        f.write(f"Date : {datetime.now().strftime('%d/%m/%Y %H:%M')}\n\n")
        f.write(f"Sortie : `{OUTPUT_DIR.as_posix()}`\n\n")
        f.write(f"Images générées : **{succes}/{len(resultats)}**\n\n")
        for result in resultats:
            status = "✅" if result["succes"] else "❌"
            f.write(f"- {status} `{result['nom']}` — {result['taille']}\n")
        if not API_KEY:
            f.write(
                "\n> AFRI_API_KEY était absent : aucune image n'a pu être générée.\n"
            )
    return 0 if succes == len(resultats) else 1


if __name__ == "__main__":
    raise SystemExit(main())
