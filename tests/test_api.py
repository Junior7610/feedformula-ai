from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from backend import main


class _FakeChatCompletions:
    def create(self, **kwargs):
        class _Message:
            content = "RATION TEST"

        class _Choice:
            message = _Message()

        class _Response:
            choices = [_Choice()]

        return _Response()


class _FakeAudioTranscriptions:
    def create(self, **kwargs):
        class _Resp:
            text = "transcription test"
            language = "fr"
            confidence = 0.98

        return _Resp()


class _FakeAudio:
    transcriptions = _FakeAudioTranscriptions()


class _FakeClient:
    class _Chat:
        completions = _FakeChatCompletions()

    chat = _Chat()
    audio = _FakeAudio()


@pytest.fixture()
def client(monkeypatch):
    main.RATION_CACHE_MEMORY.clear()

    monkeypatch.setattr(main, "_build_afri_client", lambda: _FakeClient())
    monkeypatch.setattr(main, "_load_system_prompt", lambda: "Prompt système de test.")
    monkeypatch.setattr(main, "_resoudre_espece_stade", lambda espece, stade: (espece, stade))

    def fake_optimiser_ration(**kwargs):
        return {
            "composition": {"mais": 60, "soja": 30, "premix": 10},
            "cout_fcfa_kg": 250.0,
            "cout_total_7_jours": 1750.0,
        }

    monkeypatch.setattr(main.ENGINE, "optimiser_ration", fake_optimiser_ration)
    monkeypatch.setattr(
        main.ENGINE,
        "generer_recommandations",
        lambda **kwargs: ["Conseil 1", "Conseil 2"],
    )

    return TestClient(main.app)


def _register_user(client: TestClient):
    phone = "229" + uuid.uuid4().hex[:10]
    payload = {
        "telephone": phone,
        "prenom": "Testeur",
        "langue_preferee": "fr",
        "espece_principale": "poulet",
        "region": "Atlantique",
    }

    resp = client.post("/auth/inscription", json=payload)
    assert resp.status_code in (200, 201)
    data = resp.json()
    otp = data.get("otp_dev")
    assert otp, "OTP de développement absent"

    verify = client.post(
        "/auth/verifier-otp",
        json={"telephone": phone, "code_otp": otp},
    )
    assert verify.status_code == 200
    verify_data = verify.json()

    token = verify_data["access_token"]
    user_id = verify_data["user"]["id"]
    return phone, token, user_id


def test_sante_endpoint(client):
    resp = client.get("/sante")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["services"]["database"] == "ok"


@pytest.mark.parametrize("espece", ["poulet_chair", "vache_laitiere", "tilapia"])
def test_generation_ration_par_espece(client, espece):
    resp = client.post(
        "/generer-ration",
        json={
            "espece": espece,
            "stade": "croissance",
            "ingredients_disponibles": ["maïs", "tourteau_soja", "farine_poisson"],
            "nombre_animaux": 25,
            "langue": "fr",
            "objectif": "equilibre",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ration"] == "RATION TEST"
    assert data["cout_fcfa_kg"] == 250.0
    assert data["points_gagnes"] == 10


@pytest.mark.parametrize("langue", ["fr", "fon", "en"])
def test_generation_ration_multilingue(client, langue):
    resp = client.post(
        "/generer-ration",
        json={
            "espece": "poulet_chair",
            "stade": "croissance",
            "ingredients_disponibles": ["maïs", "tourteau_soja", "farine_poisson"],
            "nombre_animaux": 50,
            "langue": langue,
            "objectif": "equilibre",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["langue_detectee"] == langue
    assert data["ration"] == "RATION TEST"


def test_gamification_points_and_levels(client):
    _, token, user_id = _register_user(client)

    action = client.post(
        "/gamification/action",
        json={
            "user_id": user_id,
            "action": "connexion_jour",
            "code_langue": "fr",
            "offline_mode": False,
            "multiplicateur_evenement": 1.0,
            "region": "Atlantique",
            "module": "nutricore",
            "espece": "poulet",
        },
    )
    assert action.status_code == 200
    action_data = action.json()
    assert "points_gagnes" in action_data

    profil = client.get(f"/gamification/profil/{user_id}")
    assert profil.status_code == 200
    profil_data = profil.json()

    assert profil_data.get("user_id", user_id) == user_id or profil_data.get("user", {}).get("id") == user_id
    assert any(
        key in profil_data
        for key in ("niveau_actuel", "niveau", "level", "ligue", "points_total")
    )

    headers = {"Authorization": f"Bearer {token}"}
    auth_profil = client.get("/auth/profil", headers=headers)
    assert auth_profil.status_code == 200
    assert auth_profil.json()["user"]["id"] == user_id

    classement = client.get("/gamification/classement")
    assert classement.status_code == 200


def test_auth_otp_flow(client):
    phone, token, user_id = _register_user(client)
    assert phone.startswith("229")
    assert token
    assert user_id


def test_prix_marche(client):
    resp = client.get("/marche/prix")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] > 0
    assert "mais" in data["prix"]
