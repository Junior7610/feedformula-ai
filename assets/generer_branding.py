#!/usr/bin/env python3
"""
feedformula-ai/assets/generer_branding.py

Génère automatiquement les visuels de branding FeedFormula AI via l'API Afri
(modèle gpt-image-2), avec :

- retry automatique (backoff exponentiel + jitter) sur erreurs temporaires,
- reprise des images manquantes (skip des fichiers déjà présents),
- rapport JSON détaillé dans assets/generation_report.json.

Usage:
    python assets/generer_branding.py
    python assets/generer_branding.py --force
    python assets/generer_branding.py --max-retries 6
    python assets/generer_branding.py --only logo_principal.png
    python assets/generer_branding.py --only logo_principal.png --only aya_joie.png
    python assets/generer_branding.py --only logo_principal.png,aya_joie.png
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import random
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

# -----------------------------
# Configuration globale
# -----------------------------
BASE_URL = "https://build.lewisnote.com/v1"
MODEL = "gpt-image-2"
ENDPOINT = "/images/generations"

REQUEST_TIMEOUT_SECONDS = 240
DEFAULT_MAX_RETRIES = 5
BACKOFF_BASE_SECONDS = 2.0
BACKOFF_MAX_SECONDS = 30.0

TRANSIENT_HTTP_STATUS = {408, 409, 425, 429, 500, 502, 503, 504, 520, 522, 524}


@dataclass
class ImageSpec:
    filename: str
    size: str
    prompt: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Génération de visuels FeedFormula AI")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Régénérer toutes les images même si le fichier existe déjà.",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=DEFAULT_MAX_RETRIES,
        help=f"Nombre maximum de retries par image (défaut: {DEFAULT_MAX_RETRIES}).",
    )
    parser.add_argument(
        "--only",
        action="append",
        default=[],
        help=(
            "Génération ciblée par nom de fichier. Peut être répété ou fourni en liste CSV "
            "(ex: --only logo_principal.png --only aya_joie.png ou --only logo_principal.png,aya_joie.png)."
        ),
    )
    return parser.parse_args()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_env_file(env_path: Path) -> Dict[str, str]:
    env_map: Dict[str, str] = {}
    if not env_path.exists():
        return env_map

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        env_map[key] = value
    return env_map


def load_afri_api_key(project_root: Path) -> str:
    # 1) variable d'environnement déjà chargée
    key = os.getenv("AFRI_API_KEY")
    if key:
        return key.strip()

    # 2) fallback via .env
    env_path = project_root / ".env"
    env_map = read_env_file(env_path)
    key = env_map.get("AFRI_API_KEY", "").strip()
    if key:
        return key

    raise RuntimeError(
        "AFRI_API_KEY introuvable. Ajoute AFRI_API_KEY dans .env à la racine du projet."
    )


def get_image_specs() -> List[ImageSpec]:
    return [
        ImageSpec(
            filename="logo_principal.png",
            size="1024x1024",
            prompt=(
                "Logo officiel FeedFormula AI. "
                "Épi de maïs africain stylisé dont les grains sont des pixels lumineux représentant l'IA. "
                "La tige forme subtilement un 'F'. "
                "Typographie 'FeedFormula AI' en dessous. "
                "Couleurs : vert foncé #1B5E20 et or #F9A825. "
                "Style minimaliste professionnel. Fond blanc. "
                "Format carré. Lisible à 32x32 pixels."
            ),
        ),
        ImageSpec(
            filename="aya_joie.png",
            size="1024x1024",
            prompt=(
                "Mascotte Aya de FeedFormula AI. "
                "Épi de maïs doré africain personnifié et animé. "
                "Grands yeux ronds expressifs, petites mains levées en l'air, grand sourire. "
                "État : joie intense. "
                "Couronne de feuilles vertes sur la tête. "
                "Style cartoon africain moderne. Fond transparent."
            ),
        ),
        ImageSpec(
            filename="aya_triste.png",
            size="1024x1024",
            prompt=(
                "Mascotte Aya triste. "
                "Même personnage qu'Aya joyeuse mais : "
                "bras baissés, yeux en demi-lune, petite larme dorée, feuille fanée dans la main. "
                "Fond transparent."
            ),
        ),
        ImageSpec(
            filename="aya_celebration.png",
            size="1024x1024",
            prompt=(
                "Mascotte Aya en célébration. "
                "Même personnage, confetti dorés autour d'elle, bras en V de victoire, étoiles qui tournent. "
                "Fond transparent."
            ),
        ),
        ImageSpec(
            filename="illustration_accueil.png",
            size="1536x1024",
            prompt=(
                "Illustration d'accueil FeedFormula AI. "
                "Éleveur africain béninois souriant tenant un smartphone avec interface verte. "
                "Ferme avicole en arrière-plan. "
                "Mascotte Aya qui flotte à côté. "
                "Ambiance chaleureuse et africaine. "
                "Style illustration digitale moderne. "
                "Format 16:9 haute résolution."
            ),
        ),
        ImageSpec(
            filename="icones_modules.png",
            size="1536x1024",
            prompt=(
                "Set de 8 icônes cohérentes en grille 2x4. "
                "Style flat design africain moderne. "
                "Fond cercle vert foncé #1B5E20, icônes or et blanc. "
                "1-NutriCore (épi+formule) 2-VetScan (stéthoscope+œil) "
                "3-ReproTrack (flèche+cœur) 4-PastureMap (satellite+feuille) "
                "5-FarmManager (graphique+micro) 6-FarmAcademy (livre+ampoule) "
                "7-FarmCast (caméra+ondes) 8-FarmCommunity (mains+réseau)."
            ),
        ),
        ImageSpec(
            filename="banniere_niveaux.png",
            size="1536x1024",
            prompt=(
                "Bannière illustrant les 10 niveaux de progression de FeedFormula AI de gauche à droite. "
                "Semence → Pousse → Tige → Floraison → Feuille d'Or → Récolte → Propriétaire "
                "→ Maître Éleveur → Champion → Légende Afrique. "
                "Chaque niveau représenté par une petite icône agricole. "
                "Style timeline colorée. Couleurs vertes et dorées."
            ),
        ),
        ImageSpec(
            filename="fond_ecran_accueil.png",
            size="1024x1536",
            prompt=(
                "Fond d'écran pour l'écran d'accueil mobile. "
                "Paysage africain stylisé au lever du soleil. "
                "Champs verdoyants, animaux d'élevage en silhouette, ciel doré. "
                "Couleurs : vert #1B5E20 en bas, dégradé vers or #F9A825 en haut. "
                "Style illustration vectorielle douce. Format portrait 9:16."
            ),
        ),
    ]


def should_retry_status(status_code: Optional[int]) -> bool:
    return status_code in TRANSIENT_HTTP_STATUS if status_code is not None else True


def is_retryable_exception(exc: Exception) -> Tuple[bool, Optional[int], str]:
    if isinstance(exc, requests.HTTPError):
        status = exc.response.status_code if exc.response is not None else None
        text = ""
        try:
            if exc.response is not None and exc.response.text:
                text = exc.response.text[:800]
        except Exception:
            text = ""
        return should_retry_status(status), status, text

    if isinstance(exc, (requests.Timeout, requests.ConnectionError)):
        return True, None, str(exc)

    return False, None, str(exc)


def decode_image_from_response_item(
    item: Dict[str, Any], session: requests.Session
) -> bytes:
    b64_data = item.get("b64_json")
    if b64_data:
        return base64.b64decode(b64_data)

    image_url = item.get("url")
    if image_url:
        resp = session.get(image_url, timeout=REQUEST_TIMEOUT_SECONDS)
        resp.raise_for_status()
        return resp.content

    raise RuntimeError("Réponse API invalide: ni 'b64_json' ni 'url' dans data[0].")


def ensure_png_bytes(raw_bytes: bytes) -> bytes:
    """
    Convertit en PNG si possible.
    Si Pillow est indisponible ou erreur de conversion, renvoie le flux brut.
    """
    try:
        from io import BytesIO

        from PIL import Image  # type: ignore

        with Image.open(BytesIO(raw_bytes)) as img:
            if img.mode not in ("RGBA", "LA"):
                img = img.convert("RGBA")
            output = BytesIO()
            img.save(output, format="PNG")
            return output.getvalue()
    except Exception:
        return raw_bytes


def call_image_generation_once(
    session: requests.Session,
    api_key: str,
    prompt: str,
    size: str,
    quality: str = "high",
) -> bytes:
    url = f"{BASE_URL.rstrip('/')}{ENDPOINT}"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MODEL,
        "prompt": prompt,
        "size": size,
        "quality": quality,
    }

    resp = session.post(
        url,
        headers=headers,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    resp.raise_for_status()

    data = resp.json()
    items = data.get("data", [])
    if not items:
        raise RuntimeError(f"Réponse API inattendue (data vide): {data}")

    raw = decode_image_from_response_item(items[0], session)
    return ensure_png_bytes(raw)


def generate_with_retry(
    session: requests.Session,
    api_key: str,
    spec: ImageSpec,
    max_retries: int,
) -> Tuple[bytes, int]:
    """
    Retourne (png_bytes, attempts_used) ou lève exception finale.
    """
    attempt = 0
    last_error: Optional[Exception] = None

    while attempt <= max_retries:
        attempt += 1
        try:
            png = call_image_generation_once(
                session=session,
                api_key=api_key,
                prompt=spec.prompt,
                size=spec.size,
                quality="high",
            )
            return png, attempt
        except Exception as exc:
            last_error = exc
            retryable, status, detail = is_retryable_exception(exc)

            if not retryable or attempt > max_retries:
                raise

            sleep_s = min(
                BACKOFF_MAX_SECONDS, BACKOFF_BASE_SECONDS * (2 ** (attempt - 1))
            )
            sleep_s += random.uniform(0.1, 0.9)

            status_txt = f"HTTP {status}" if status is not None else "Erreur réseau"
            detail_txt = f" | détail: {detail[:180]}" if detail else ""
            print(
                f"   ↻ Retry {attempt}/{max_retries} pour {spec.filename} ({status_txt})"
                f"{detail_txt} | attente {sleep_s:.1f}s"
            )
            time.sleep(sleep_s)

    if last_error:
        raise last_error
    raise RuntimeError("Échec inattendu sans exception capturée.")


def write_report(report_path: Path, report: Dict[str, Any]) -> None:
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def generate_all(
    force: bool,
    max_retries: int,
    only: Optional[List[str]] = None,
) -> int:
    script_path = Path(__file__).resolve()
    assets_dir = script_path.parent
    project_root = assets_dir.parent
    report_path = assets_dir / "generation_report.json"

    try:
        api_key = load_afri_api_key(project_root)
    except Exception as exc:
        print(f"❌ Configuration API invalide: {exc}")
        return 1

    specs = get_image_specs()

    requested_names: List[str] = []
    if only:
        for raw in only:
            requested_names.extend(
                [part.strip() for part in raw.split(",") if part.strip()]
            )

    requested_set = set(requested_names)
    if requested_set:
        specs = [spec for spec in specs if spec.filename in requested_set]
        if not specs:
            print("❌ Aucun fichier cible valide trouvé via --only.")
            print("   Fichiers acceptés:")
            for spec in get_image_specs():
                print(f"   - {spec.filename}")
            return 1

    report: Dict[str, Any] = {
        "started_at": utc_now_iso(),
        "base_url": BASE_URL,
        "model": MODEL,
        "assets_dir": str(assets_dir),
        "force": force,
        "max_retries": max_retries,
        "images": [],
    }

    success = 0
    failed = 0
    skipped = 0

    print("🚀 Génération branding FeedFormula AI")
    print(f"📁 Dossier sortie: {assets_dir}")
    print(f"🔁 Mode reprise manquantes: {'NON (force)' if force else 'OUI'}")
    print(f"♻️  Max retries: {max_retries}")
    if requested_set:
        print(f"🎯 Mode ciblé: {', '.join(sorted(requested_set))}")

    with requests.Session() as session:
        for idx, spec in enumerate(specs, start=1):
            start_ts = time.perf_counter()
            output_path = assets_dir / spec.filename

            item_report: Dict[str, Any] = {
                "index": idx,
                "filename": spec.filename,
                "size": spec.size,
                "status": "",
                "attempts": 0,
                "duration_seconds": 0.0,
                "error_type": None,
                "error_message": None,
            }

            print(f"\n[{idx}/{len(specs)}] {spec.filename} ({spec.size})")

            if output_path.exists() and output_path.stat().st_size > 0 and not force:
                item_report["status"] = "skipped_existing"
                item_report["attempts"] = 0
                item_report["duration_seconds"] = round(
                    time.perf_counter() - start_ts, 3
                )
                report["images"].append(item_report)
                skipped += 1
                print(f"⏭️  Déjà présent, ignoré: {spec.filename}")
                continue

            try:
                png_bytes, attempts = generate_with_retry(
                    session=session,
                    api_key=api_key,
                    spec=spec,
                    max_retries=max_retries,
                )

                output_path.write_bytes(png_bytes)

                item_report["status"] = "generated"
                item_report["attempts"] = attempts
                item_report["duration_seconds"] = round(
                    time.perf_counter() - start_ts, 3
                )

                report["images"].append(item_report)
                success += 1
                print(
                    f"✅ Généré et sauvegardé: {spec.filename} (tentatives: {attempts})"
                )

            except Exception as exc:
                item_report["status"] = "failed"
                item_report["attempts"] = max_retries + 1
                item_report["duration_seconds"] = round(
                    time.perf_counter() - start_ts, 3
                )
                item_report["error_type"] = type(exc).__name__
                item_report["error_message"] = str(exc)[:1000]

                if isinstance(exc, requests.HTTPError) and exc.response is not None:
                    item_report["http_status"] = exc.response.status_code
                    try:
                        item_report["http_body_preview"] = exc.response.text[:800]
                    except Exception:
                        pass

                report["images"].append(item_report)
                failed += 1
                print(f"❌ Échec: {spec.filename} -> {type(exc).__name__}: {exc}")

    report["finished_at"] = utc_now_iso()
    report["summary"] = {
        "generated": success,
        "failed": failed,
        "skipped_existing": skipped,
        "total": len(specs),
    }

    write_report(report_path, report)

    print("\n================== RÉSUMÉ ==================")
    print(f"✅ Générées : {success}")
    print(f"⏭️  Ignorées  : {skipped}")
    print(f"❌ Échecs    : {failed}")
    print(f"🧾 Rapport   : {report_path}")
    print("============================================")

    # Exit code:
    # 0 si aucune erreur (même avec skipped), 2 sinon.
    return 0 if failed == 0 else 2


def main() -> int:
    args = parse_args()
    max_retries = max(0, int(args.max_retries))
    return generate_all(
        force=args.force,
        max_retries=max_retries,
        only=args.only,
    )


if __name__ == "__main__":
    sys.exit(main())
