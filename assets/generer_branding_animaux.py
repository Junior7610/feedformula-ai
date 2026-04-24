#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
feedformula-ai/assets/generer_branding_animaux.py

Génère les visuels branding FeedFormula AI (centrés animaux d'élevage africains)
via API Afri + modèle gpt-image-2.

Configuration:
- Base URL: https://build.lewisnote.com/v1
- Clé API: AFRI_API_KEY (chargée depuis .env si présent)
- Modèle: gpt-image-2

Prérequis:
- pip install openai python-dotenv
"""

from __future__ import annotations

import base64
import os
import sys
import traceback
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

from openai import OpenAI

try:
    from dotenv import load_dotenv
except Exception:

    def load_dotenv(*args: Any, **kwargs: Any) -> bool:
        return False


BASE_URL = "https://build.lewisnote.com/v1"
MODEL = "gpt-image-2"


def _to_dict(obj: Any) -> Dict[str, Any]:
    """Convertit un objet SDK en dict si possible."""
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
        return dict(obj.__dict__)
    return {}


def _safe_get(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _find_first_key(data: Any, target_key: str) -> Optional[Any]:
    """Recherche récursive de la première valeur pour une clé donnée."""
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
    """Télécharge une image URL avec en-têtes d’authentification pour éviter les 403."""
    headers = {
        "User-Agent": "feedformula-ai-branding/1.0",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
        headers["api-key"] = api_key

    request = urllib.request.Request(image_url, headers=headers)
    with urllib.request.urlopen(request, timeout=60) as resp:
        return resp.read()


def _extract_image_bytes(response: Any, api_key: Optional[str] = None) -> bytes:
    """
    Extrait les bytes image d'une réponse images.generate.
    Gère:
    - data[0].b64_json
    - data[0].image_base64
    - data[0].url (téléchargée avec en-têtes d'auth)
    - fallback récursif sur b64_json/url
    """
    # 1) Essai format standard
    data = _safe_get(response, "data")
    if data and isinstance(data, list):
        first = data[0]
        b64_data = _safe_get(first, "b64_json") or _safe_get(first, "image_base64")
        if b64_data:
            return base64.b64decode(b64_data)

        image_url = _safe_get(first, "url")
        if image_url:
            return _download_image_url(str(image_url), api_key)

    # 2) Fallback via dict global
    payload = _to_dict(response)
    if payload:
        b64_data = _find_first_key(payload, "b64_json") or _find_first_key(
            payload, "image_base64"
        )
        if b64_data:
            return base64.b64decode(b64_data)

        image_url = _find_first_key(payload, "url")
        if image_url:
            return _download_image_url(str(image_url), api_key)

    raise ValueError("Aucune image trouvée dans la réponse (ni base64 ni URL).")


def _save_png(raw: bytes, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(raw)


def generate_one_image(
    client: OpenAI,
    output_path: Path,
    prompt: str,
    sizes: List[str],
    api_key: Optional[str] = None,
) -> bool:
    """
    Génère une image avec fallback de tailles.
    Continue en cas d'erreur et retourne True/False.
    """
    last_error: Optional[Exception] = None

    for size in sizes:
        try:
            # Paramètres volontairement minimaux pour compatibilité Afri.
            response = client.images.generate(
                model=MODEL,
                prompt=prompt,
                size=size,
            )

            raw = _extract_image_bytes(response, api_key=api_key)
            _save_png(raw, output_path)
            print(f"✅ Généré: {output_path.name} (size={size})")
            return True

        except Exception as exc:
            last_error = exc
            print(f"⚠️ Échec {output_path.name} avec size={size}: {exc}")

    print(f"❌ Impossible de générer {output_path.name} après tous les essais.")
    if last_error:
        print("Détail erreur finale:")
        print(
            "".join(
                traceback.format_exception_only(type(last_error), last_error)
            ).strip()
        )
    return False


def main() -> int:
    script_path = Path(__file__).resolve()
    project_root = script_path.parent.parent
    env_path = project_root / ".env"

    load_dotenv(env_path)

    api_key = os.getenv("AFRI_API_KEY")
    if not api_key:
        print(
            "❌ AFRI_API_KEY introuvable. Ajoute AFRI_API_KEY dans le fichier .env à la racine du projet."
        )
        return 1

    assets_dir = script_path.parent

    client = OpenAI(
        api_key=api_key,
        base_url=BASE_URL,
    )

    jobs = [
        {
            "filename": "hero_poulets.png",
            "prompt": (
                "Illustration digitale africaine moderne. Premier plan : poulets de chair sains et vigoureux "
                "dans un poulailler propre et moderne au Bénin. Lumière dorée chaude de l'Afrique de l'Ouest. "
                "Un smartphone avec l'interface verte de FeedFormula AI visible dans le coin. "
                "Ambiance prospère et optimiste. Couleurs dominantes : vert #1B5E20 et or #F9A825. "
                "Style : illustration vectorielle semi-réaliste. Format : 16:9."
            ),
            "sizes": ["1536x1024", "1024x1024"],
        },
        {
            "filename": "hero_bovins.png",
            "prompt": (
                "Illustration africaine moderne. Zébu africain (race Borgou ou Lagunaire) en bonne santé, brillant, "
                "dans un pâturage verdoyant du Bénin. Éleveur béninois fier à côté tenant un smartphone. "
                "Ciel bleu africain. Ambiance de prospérité rurale. Couleurs : vert et or de FeedFormula AI. "
                "Format : 16:9."
            ),
            "sizes": ["1536x1024", "1024x1024"],
        },
        {
            "filename": "hero_petits_ruminants.png",
            "prompt": (
                "Illustration africaine moderne. Moutons et chèvres africains (race Djallonké) bien portants "
                "dans une ferme propre du Bénin. Femme éleveuse béninoise souriante avec smartphone. "
                "Ambiance chaleureuse et familiale africaine. Format : 16:9."
            ),
            "sizes": ["1536x1024", "1024x1024"],
        },
        {
            "filename": "hero_aquaculture.png",
            "prompt": (
                "Illustration africaine moderne. Étang piscicole propre avec tilapias et carpes visibles sous l'eau claire. "
                "Éleveur béninois qui observe ses poissons. Verdure tropicale autour. "
                "Smartphone visible avec données de FeedFormula AI. Format : 16:9."
            ),
            "sizes": ["1536x1024", "1024x1024"],
        },
        {
            "filename": "icones_animaux.png",
            "prompt": (
                "Set de 10 icônes d'animaux d'élevage africains. Style flat design africain moderne. Grille 2x5. "
                "Fond cercle vert foncé #1B5E20, animal en or et blanc. Les 10 animaux : "
                "1-Poulet de chair 2-Poule pondeuse 3-Pintade 4-Vache laitière 5-Zébu "
                "6-Mouton 7-Chèvre 8-Porc 9-Tilapia 10-Lapin. "
                "Chaque animal reconnaissable et stylisé à la manière africaine. "
                "Taille : 256x256 pixels chacune."
            ),
            "sizes": ["1024x1024", "1536x1024"],
        },
        {
            "filename": "aya_avec_animaux.png",
            "prompt": (
                "La mascotte Aya (épi de maïs doré animé avec yeux et bras) entourée de petits animaux "
                "d'élevage africains miniatures et mignons : un poussin, un veau, un agneau et un tilapia. "
                "Tous dessinés dans le même style cartoon africain. Aya les regarde avec amour et fierté. "
                "Fond transparent. Style illustration jeunesse africaine."
            ),
            "sizes": ["1024x1024", "1536x1024"],
        },
        {
            "filename": "carte_afrique_animaux.png",
            "prompt": (
                "Carte stylisée de l'Afrique de l'Ouest avec des silhouettes d'animaux d'élevage positionnées sur les pays. "
                "Bénin mis en valeur avec un point lumineux doré. Couleurs vertes et dorées de FeedFormula AI. "
                "Style illustration cartographique moderne. Format carré."
            ),
            "sizes": ["1024x1024", "1536x1024"],
        },
        {
            "filename": "banniere_discord.png",
            "prompt": (
                "Bannière rectangulaire pour Discord. FeedFormula AI — texte en grand à gauche en blanc. "
                "À droite : collage d'animaux d'élevage africains (poulet, vache, mouton, poisson) "
                "dessinés en style flat design africain moderne. Fond vert foncé #1B5E20. "
                "Mascotte Aya qui sourit au centre. Format : 1920x480 pixels."
            ),
            "sizes": ["1536x1024", "1024x1024"],
        },
    ]

    print("🚀 Génération des visuels branding (API Afri / GPT Image 2)...")
    print(f"📁 Dossier de sortie: {assets_dir}")

    success_count = 0
    fail_count = 0

    for job in jobs:
        output_path = assets_dir / job["filename"]
        try:
            ok = generate_one_image(
                client=client,
                output_path=output_path,
                prompt=job["prompt"],
                sizes=job["sizes"],
                api_key=api_key,
            )
            if ok:
                success_count += 1
            else:
                fail_count += 1
        except Exception as exc:
            fail_count += 1
            print(f"❌ Erreur inattendue sur {job['filename']}: {exc}")
            print(traceback.format_exc())

    print("\n📊 Résumé:")
    print(f"✅ Succès: {success_count}")
    print(f"❌ Échecs: {fail_count}")

    # 0 si au moins une image générée, sinon 2
    return 0 if success_count > 0 else 2


if __name__ == "__main__":
    sys.exit(main())
