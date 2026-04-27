#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Smoke test API FeedFormula AI (Auth OTP/JWT + Gamification).

Objectif :
- Vérifier rapidement le flux critique backend :
  1) /sante
  2) /auth/inscription
  3) /auth/verifier-otp
  4) /auth/profil (authentifié)
  5) /gamification/action
  6) /gamification/profil/{user_id}
  7) /gamification/classement
  8) /gamification/classement/{region}
  9) /gamification/defis-du-jour
 10) /gamification/defi/completer (best effort)

Utilisation :
    python backend/smoke_test_auth_gamification.py

Variables d'environnement utiles :
- SMOKE_BASE_URL (défaut: http://127.0.0.1:8000)
- SMOKE_TIMEOUT_SECONDS (défaut: 20)
- SMOKE_REGION (défaut: Atlantique)
- SMOKE_LANGUE (défaut: fr)
- SMOKE_PRENOM (défaut: Smoke Tester)
- SMOKE_PHONE (optionnel : téléphone forcé)
- SMOKE_OTP_CODE (optionnel : OTP manuel si otp_dev n'est pas exposé)
"""

from __future__ import annotations

import json
import os
import random
import string
import sys
import time
from typing import Any, Dict, Optional, Tuple

import requests


def _env(name: str, default: str) -> str:
    return (os.getenv(name) or default).strip()


def _now_ms() -> int:
    return int(time.time() * 1000)


def _build_phone() -> str:
    forced = _env("SMOKE_PHONE", "")
    if forced:
        return "".join(ch for ch in forced if ch.isdigit()) or forced

    # Génère un numéro "test" pseudo-unique (13 chiffres max).
    # Exemple : 229 + 10 chiffres.
    suffix = str(_now_ms())[-10:]
    return f"229{suffix}"


def _safe_json(resp: requests.Response) -> Any:
    try:
        return resp.json()
    except Exception:
        return {"_raw_text": resp.text[:800]}


def _print_step(name: str) -> None:
    print(f"\n=== {name} ===")


def _print_response(resp: requests.Response) -> None:
    payload = _safe_json(resp)
    compact = json.dumps(payload, ensure_ascii=False)[:1200]
    print(f"HTTP {resp.status_code} | {compact}")


def _request(
    method: str,
    url: str,
    timeout_s: int,
    headers: Optional[Dict[str, str]] = None,
    payload: Optional[Dict[str, Any]] = None,
) -> Tuple[bool, Optional[requests.Response]]:
    try:
        resp = requests.request(
            method=method.upper(),
            url=url,
            json=payload,
            headers=headers or {},
            timeout=timeout_s,
        )
        return True, resp
    except requests.RequestException as exc:
        print(f"Erreur requête {method} {url}: {exc}")
        return False, None


def _expect_status(resp: requests.Response, allowed: Tuple[int, ...], step_name: str) -> bool:
    if resp.status_code in allowed:
        return True
    print(f"❌ Échec {step_name}: statut inattendu {resp.status_code}, attendu {allowed}")
    return False


def main() -> int:
    base_url = _env("SMOKE_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
    timeout_s = int(_env("SMOKE_TIMEOUT_SECONDS", "20"))
    region = _env("SMOKE_REGION", "Atlantique")
    langue = _env("SMOKE_LANGUE", "fr")
    prenom = _env("SMOKE_PRENOM", "Smoke Tester")
    phone = _build_phone()

    print("🚀 Démarrage smoke test FeedFormula AI")
    print(f"Base URL: {base_url}")
    print(f"Téléphone test: {phone}")

    # 1) Santé
    _print_step("1) GET /sante")
    ok, resp = _request("GET", f"{base_url}/sante", timeout_s)
    if not ok or resp is None:
        return 1
    _print_response(resp)
    if not _expect_status(resp, (200,), "GET /sante"):
        return 1

    # 2) Inscription
    _print_step("2) POST /auth/inscription")
    inscription_payload = {
        "telephone": phone,
        "prenom": prenom,
        "langue_preferee": langue,
        "espece_principale": "poulet",
        "region": region,
    }
    ok, resp = _request("POST", f"{base_url}/auth/inscription", timeout_s, payload=inscription_payload)
    if not ok or resp is None:
        return 1
    _print_response(resp)

    # 409 peut arriver si numéro déjà existant (si SMOKE_PHONE forcé)
    if not _expect_status(resp, (200, 201, 409), "POST /auth/inscription"):
        return 1

    inscription_data = _safe_json(resp) if resp is not None else {}
    otp_code = inscription_data.get("otp_dev")

    # Si déjà inscrit, on tente connexion pour renvoyer OTP
    if resp.status_code == 409:
        _print_step("2bis) POST /auth/connexion (fallback si déjà inscrit)")
        ok, resp_conn = _request(
            "POST",
            f"{base_url}/auth/connexion",
            timeout_s,
            payload={"telephone": phone},
        )
        if not ok or resp_conn is None:
            return 1
        _print_response(resp_conn)
        if not _expect_status(resp_conn, (200,), "POST /auth/connexion"):
            return 1
        conn_data = _safe_json(resp_conn)
        otp_code = conn_data.get("otp_dev")

    # OTP fallback manuel
    if not otp_code:
        otp_code = _env("SMOKE_OTP_CODE", "")
    if not otp_code:
        print(
            "❌ OTP introuvable. Fournis SMOKE_OTP_CODE si l'environnement masque otp_dev."
        )
        return 1

    # 3) Vérifier OTP
    _print_step("3) POST /auth/verifier-otp")
    ok, resp = _request(
        "POST",
        f"{base_url}/auth/verifier-otp",
        timeout_s,
        payload={"telephone": phone, "code_otp": str(otp_code)},
    )
    if not ok or resp is None:
        return 1
    _print_response(resp)
    if not _expect_status(resp, (200,), "POST /auth/verifier-otp"):
        return 1

    verify_data = _safe_json(resp)
    token = verify_data.get("access_token")
    user = verify_data.get("user", {}) if isinstance(verify_data, dict) else {}
    user_id = user.get("id")

    if not token or not user_id:
        print("❌ Token ou user_id absent dans /auth/verifier-otp.")
        return 1

    auth_headers = {"Authorization": f"Bearer {token}"}

    # 4) Profil auth
    _print_step("4) GET /auth/profil (authentifié)")
    ok, resp = _request("GET", f"{base_url}/auth/profil", timeout_s, headers=auth_headers)
    if not ok or resp is None:
        return 1
    _print_response(resp)
    if not _expect_status(resp, (200,), "GET /auth/profil"):
        return 1

    # 5) Action gamification - connexion_jour
    _print_step("5) POST /gamification/action (connexion_jour)")
    action_payload_connexion = {
        "user_id": user_id,
        "action": "connexion_jour",
        "code_langue": langue,
        "offline_mode": False,
        "multiplicateur_evenement": 1.0,
        "region": region,
        "module": "nutricore",
        "espece": "poulet",
    }
    ok, resp = _request(
        "POST",
        f"{base_url}/gamification/action",
        timeout_s,
        payload=action_payload_connexion,
    )
    if not ok or resp is None:
        return 1
    _print_response(resp)
    if not _expect_status(resp, (200,), "POST /gamification/action connexion_jour"):
        return 1

    # 6) Action gamification - generation_ration
    _print_step("6) POST /gamification/action (generation_ration)")
    action_payload_ration = {
        "user_id": user_id,
        "action": "generation_ration",
        "code_langue": langue,
        "offline_mode": False,
        "multiplicateur_evenement": 1.0,
        "region": region,
        "module": "nutricore",
        "espece": "poulet",
    }
    ok, resp = _request(
        "POST",
        f"{base_url}/gamification/action",
        timeout_s,
        payload=action_payload_ration,
    )
    if not ok or resp is None:
        return 1
    _print_response(resp)
    if not _expect_status(resp, (200,), "POST /gamification/action generation_ration"):
        return 1

    # 7) Profil gamification
    _print_step("7) GET /gamification/profil/{user_id}")
    ok, resp = _request("GET", f"{base_url}/gamification/profil/{user_id}", timeout_s)
    if not ok or resp is None:
        return 1
    _print_response(resp)
    if not _expect_status(resp, (200,), "GET /gamification/profil/{user_id}"):
        return 1

    # 8) Classement global
    _print_step("8) GET /gamification/classement")
    ok, resp = _request("GET", f"{base_url}/gamification/classement", timeout_s)
    if not ok or resp is None:
        return 1
    _print_response(resp)
    if not _expect_status(resp, (200,), "GET /gamification/classement"):
        return 1

    # 9) Classement région
    _print_step("9) GET /gamification/classement/{region}")
    ok, resp = _request("GET", f"{base_url}/gamification/classement/{region}", timeout_s)
    if not ok or resp is None:
        return 1
    _print_response(resp)
    if not _expect_status(resp, (200,), "GET /gamification/classement/{region}"):
        return 1

    # 10) Défis du jour + tentative complétion best effort
    _print_step("10) GET /gamification/defis-du-jour")
    ok, resp = _request("GET", f"{base_url}/gamification/defis-du-jour", timeout_s)
    if not ok or resp is None:
        return 1
    _print_response(resp)
    if not _expect_status(resp, (200,), "GET /gamification/defis-du-jour"):
        return 1

    # Tentative best effort de complétion défi 1 (peut échouer selon objectifs)
    _print_step("10bis) POST /gamification/defi/completer (best effort)")
    ok, resp = _request(
        "POST",
        f"{base_url}/gamification/defi/completer",
        timeout_s,
        payload={"user_id": user_id, "defi_numero": 1},
    )
    if not ok or resp is None:
        return 1
    _print_response(resp)
    if resp.status_code in (200, 201):
        print("✅ Défi complété.")
    else:
        print("ℹ️ Défi non complété (acceptable en smoke test).")

    print("\n🎉 Smoke test terminé avec succès.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
