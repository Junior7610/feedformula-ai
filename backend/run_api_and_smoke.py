#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Runner temporaire :
1) démarre l'API FastAPI en local,
2) exécute le smoke test complet,
3) arrête proprement l'API.

Fichier: feedformula-ai/backend/run_api_and_smoke.py
"""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional


def _wait_for_healthcheck(base_url: str, timeout_seconds: int) -> bool:
    """
    Attend que /sante réponde HTTP 200 jusqu'au timeout.
    """
    health_url = f"{base_url.rstrip('/')}/sante"
    deadline = time.time() + timeout_seconds

    while time.time() < deadline:
        try:
            with urllib.request.urlopen(health_url, timeout=2) as resp:
                if 200 <= resp.status < 300:
                    return True
        except urllib.error.URLError:
            pass
        except Exception:
            pass
        time.sleep(0.5)

    return False


def _terminate_process(proc: Optional[subprocess.Popen], grace_seconds: int = 8) -> None:
    """
    Arrête proprement un processus, puis force kill si nécessaire.
    """
    if proc is None:
        return

    if proc.poll() is not None:
        return

    try:
        # Sous Windows, terminate() est généralement le plus fiable.
        proc.terminate()
    except Exception:
        pass

    try:
        proc.wait(timeout=grace_seconds)
        return
    except subprocess.TimeoutExpired:
        pass

    try:
        proc.kill()
    except Exception:
        pass

    try:
        proc.wait(timeout=3)
    except Exception:
        pass


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Démarre l'API, lance le smoke test, puis coupe l'API."
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host API (défaut: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Port API (défaut: 8000)")
    parser.add_argument(
        "--startup-timeout",
        type=int,
        default=45,
        help="Timeout démarrage API en secondes (défaut: 45)",
    )
    parser.add_argument(
        "--smoke-timeout",
        type=int,
        default=180,
        help="Timeout smoke test en secondes (défaut: 180)",
    )
    parser.add_argument(
        "--keep-api",
        action="store_true",
        help="Ne pas arrêter l'API à la fin (debug).",
    )
    args = parser.parse_args()

    backend_dir = Path(__file__).resolve().parent
    project_root = backend_dir.parent
    base_url = f"http://{args.host}:{args.port}"

    api_proc: Optional[subprocess.Popen] = None

    # Variables d'environnement pour subprocess
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env.setdefault("SMOKE_BASE_URL", base_url)

    # Si APP_ENV n'est pas défini, on met un mode non-prod pour faciliter les tests locaux
    env.setdefault("APP_ENV", "development")

    try:
        print("🚀 Démarrage de l'API...")
        api_cmd = [
            sys.executable,
            "-m",
            "uvicorn",
            "backend.main:app",
            "--host",
            args.host,
            "--port",
            str(args.port),
        ]

        api_proc = subprocess.Popen(
            api_cmd,
            cwd=str(project_root),
            env=env,
            stdout=None,   # Hérite stdout/stderr pour voir les logs en direct
            stderr=None,
        )

        print(f"⏳ Attente du healthcheck sur {base_url}/sante ...")
        if not _wait_for_healthcheck(base_url, timeout_seconds=args.startup_timeout):
            print("❌ L'API n'a pas démarré à temps.")
            return 1

        print("✅ API prête.")

        print("🧪 Lancement du smoke test...")
        smoke_cmd = [sys.executable, "backend/smoke_test_auth_gamification.py"]
        smoke_result = subprocess.run(
            smoke_cmd,
            cwd=str(project_root),
            env=env,
            timeout=args.smoke_timeout,
            check=False,
        )

        if smoke_result.returncode == 0:
            print("✅ Smoke test terminé avec succès.")
            return 0

        print(f"❌ Smoke test en échec (code={smoke_result.returncode}).")
        return smoke_result.returncode

    except subprocess.TimeoutExpired:
        print("❌ Timeout atteint pendant l'exécution du smoke test.")
        return 124

    except KeyboardInterrupt:
        print("\n⛔ Interruption manuelle.")
        return 130

    except Exception as exc:
        print(f"❌ Erreur inattendue: {exc}")
        return 1

    finally:
        if args.keep_api:
            print("ℹ️ --keep-api activé: API laissée en cours d'exécution.")
        else:
            print("🛑 Arrêt de l'API...")
            _terminate_process(api_proc)
            print("✅ API arrêtée.")


if __name__ == "__main__":
    raise SystemExit(main())
