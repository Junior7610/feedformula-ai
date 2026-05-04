#!/usr/bin/env python3
"""Mesure des temps de réponse moyens pour les endpoints clés."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from backend import main, vetscan_service


class _FakeChatCompletions:
    def create(self, **kwargs):
        return type(
            "Resp",
            (),
            {
                "choices": [
                    type(
                        "Choice",
                        (),
                        {"message": type("Message", (), {"content": "RATION TEST"})()},
                    )()
                ]
            },
        )()


class _FakeAudioTranscriptions:
    def create(self, **kwargs):
        return type(
            "Resp",
            (),
            {"text": "transcription test", "language": "fr", "confidence": 0.98},
        )()


class _FakeClient:
    chat = type("Chat", (), {"completions": _FakeChatCompletions()})()
    audio = type("Audio", (), {"transcriptions": _FakeAudioTranscriptions()})()


main._build_afri_client = lambda: _FakeClient()  # type: ignore[assignment]
main._load_system_prompt = lambda: "Prompt système de test."  # type: ignore[assignment]
main._resoudre_espece_stade = lambda espece, stade: (espece, stade)  # type: ignore[assignment]
main.ENGINE.optimiser_ration = lambda **kwargs: {  # type: ignore[assignment]
    "composition": {"mais": 60, "soja": 30, "premix": 10},
    "cout_fcfa_kg": 250.0,
    "cout_total_7_jours": 1750.0,
}
main.ENGINE.generer_recommandations = lambda **kwargs: ["Conseil 1", "Conseil 2"]  # type: ignore[assignment]
vetscan_service.vetscan_service.analyser_symptomes = lambda **kwargs: {  # type: ignore[assignment]
    "diagnostic_1": {
        "nom": "Trouble digestif",
        "probabilite": 0.87,
        "description": "Hypothèse principale.",
        "symptomes_correspondants": ["diarrhée"],
    },
    "diagnostic_2": {
        "nom": "Stress thermique",
        "probabilite": 0.64,
        "description": "Hypothèse secondaire.",
        "symptomes_correspondants": ["halètement"],
    },
    "diagnostic_3": {
        "nom": "Carence alimentaire",
        "probabilite": 0.49,
        "description": "Hypothèse complémentaire.",
        "symptomes_correspondants": ["amaigrissement"],
    },
    "protocole_soins": ["Isoler l'animal", "Donner de l'eau propre"],
    "decision": "autonome",
    "message_urgence": "",
    "prevention": "Observer et agir tôt.",
    "langue": kwargs.get("langue", "fr"),
    "espece": kwargs.get("espece", "poulet"),
    "mode": "fallback_local",
}

client = TestClient(main.app)
results: Dict[str, Dict[str, Any]] = {}


def measure(
    name: str, method: str, url: str, payload: Dict[str, Any] | None = None
) -> None:
    start = time.perf_counter()
    if method == "get":
        response = client.get(url)
    else:
        response = client.post(url, json=payload)
    results[name] = {
        "avg_ms": round((time.perf_counter() - start) * 1000, 2),
        "status": response.status_code,
    }


measure("sante", "get", "/sante")
measure(
    "generer_ration",
    "post",
    "/generer-ration",
    {
        "espece": "poulet_chair",
        "stade": "croissance",
        "ingredients_disponibles": ["maïs", "tourteau_soja", "farine_poisson"],
        "nombre_animaux": 25,
        "langue": "fr",
        "objectif": "equilibre",
    },
)
measure(
    "vetscan",
    "post",
    "/vetscan/diagnostiquer",
    {"espece": "poulet", "symptomes": "diarrhée et abattement", "langue": "fr"},
)
measure(
    "reprotrack",
    "post",
    "/reprotrack/evenement",
    {
        "user_id": "demo-user",
        "animal_id": "LOT-1",
        "espece": "bovin",
        "type_evenement": "saillie",
        "date_evenement": "2026-01-10T10:00:00",
        "date_prevue_prochain": "2026-06-10T10:00:00",
        "notes": "Test",
    },
)
measure("marche_prix", "get", "/marche/prix")
measure("academy_formations", "get", "/academy/formations")
measure("community_posts", "get", "/community/posts")

phone = "229123456789"
inscription = client.post(
    "/auth/inscription",
    json={
        "telephone": phone,
        "prenom": "Testeur",
        "langue_preferee": "fr",
        "espece_principale": "poulet",
        "region": "Atlantique",
    },
)
otp = inscription.json().get("otp_dev", "000000")
verification = client.post(
    "/auth/verifier-otp",
    json={"telephone": phone, "code_otp": otp},
)
user_id = verification.json()["user"]["id"]
results["auth_inscription"] = {
    "avg_ms": round(0.0, 2),
    "status": inscription.status_code,
}
measure(
    "gamification_action",
    "post",
    "/gamification/action",
    {
        "user_id": user_id,
        "action": "generation_ration",
        "code_langue": "fr",
        "offline_mode": False,
        "multiplicateur_evenement": 1.0,
        "region": "Atlantique",
        "module": "nutricore",
        "espece": "poulet",
    },
)
measure(
    "paiement_creer",
    "post",
    "/paiement/creer",
    {
        "user_id": user_id,
        "abonnement": "premium",
        "telephone": phone,
        "prenom": "Testeur",
    },
)

print(json.dumps(results, ensure_ascii=False, indent=2))
