from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from backend import main, vetscan_service


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
    monkeypatch.setattr(
        main, "_resoudre_espece_stade", lambda espece, stade: (espece, stade)
    )

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
    monkeypatch.setattr(
        vetscan_service.vetscan_service,
        "analyser_symptomes",
        lambda **kwargs: {
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
        },
    )

    return TestClient(main.app)


@pytest.fixture()
def registered_user(client: TestClient):
    phone = f"229{uuid.uuid4().int % 10**10:010d}"
    payload = {
        "telephone": phone,
        "prenom": "Testeur",
        "langue_preferee": "fr",
        "espece_principale": "poulet",
        "region": "Atlantique",
    }
    resp = client.post("/auth/inscription", json=payload)
    assert resp.status_code in (200, 201)
    otp = resp.json().get("otp_dev")
    assert otp
    verify = client.post(
        "/auth/verifier-otp", json={"telephone": phone, "code_otp": otp}
    )
    assert verify.status_code == 200
    data = verify.json()
    return {
        "phone": phone,
        "user_id": data["user"]["id"],
        "token": data["access_token"],
    }


def _assert_ok(resp):
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_sante(client):
    data = _assert_ok(client.get("/sante"))
    assert data["status"] == "ok"


@pytest.mark.parametrize("espece", ["poulet_chair", "vache_laitiere", "tilapia"])
def test_generer_ration_poulet(client, espece):
    data = _assert_ok(
        client.post(
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
    )
    assert data["ration"] == "RATION TEST"


def test_generer_ration_vache(client):
    data = _assert_ok(
        client.post(
            "/generer-ration",
            json={
                "espece": "vache_laitiere",
                "stade": "croissance",
                "ingredients_disponibles": ["maïs", "tourteau_soja", "farine_poisson"],
                "nombre_animaux": 30,
                "langue": "fr",
                "objectif": "equilibre",
            },
        )
    )
    assert data["cout_fcfa_kg"] == 250.0


def test_generer_ration_tilapia(client):
    data = _assert_ok(
        client.post(
            "/generer-ration",
            json={
                "espece": "tilapia",
                "stade": "croissance",
                "ingredients_disponibles": ["maïs", "tourteau_soja", "farine_poisson"],
                "nombre_animaux": 50,
                "langue": "fr",
                "objectif": "equilibre",
            },
        )
    )
    assert data["points_gagnes"] == 10


def test_multilingue_fon(client):
    data = _assert_ok(
        client.post(
            "/generer-ration",
            json={
                "espece": "poulet_chair",
                "stade": "croissance",
                "ingredients_disponibles": ["maïs", "tourteau_soja", "farine_poisson"],
                "nombre_animaux": 10,
                "langue": "fon",
                "objectif": "equilibre",
            },
        )
    )
    assert data["langue_detectee"] == "fon"


def test_multilingue_anglais(client):
    data = _assert_ok(
        client.post(
            "/generer-ration",
            json={
                "espece": "poulet_chair",
                "stade": "croissance",
                "ingredients_disponibles": ["maïs", "tourteau_soja", "farine_poisson"],
                "nombre_animaux": 10,
                "langue": "en",
                "objectif": "equilibre",
            },
        )
    )
    assert data["langue_detectee"] == "en"


def test_vetscan_symptomes(client):
    data = _assert_ok(
        client.post(
            "/vetscan/diagnostiquer",
            json={
                "espece": "poulet",
                "symptomes": "diarrhée et abattement",
                "langue": "fr",
            },
        )
    )
    assert "resultat" in data


def test_reprotrack_evenement(client, registered_user):
    data = _assert_ok(
        client.post(
            "/reprotrack/evenement",
            json={
                "user_id": registered_user["user_id"],
                "animal_id": "LOT-1",
                "espece": "bovin",
                "type_evenement": "saillie",
                "date_evenement": "2026-01-10T10:00:00",
                "date_prevue_prochain": "2026-06-10T10:00:00",
                "notes": "Test",
            },
        )
    )
    assert data["evenement"]["user_id"] == registered_user["user_id"]


def test_prix_marche(client):
    data = _assert_ok(client.get("/marche/prix"))
    assert data["total"] > 0


def test_academy_formations(client):
    data = _assert_ok(client.get("/academy/formations"))
    assert data["total"] >= 1


def test_community_posts(client):
    data = _assert_ok(client.get("/community/posts"))
    assert "posts" in data or "total" in data


def test_gamification_points(client, registered_user):
    data = _assert_ok(
        client.post(
            "/gamification/action",
            json={
                "user_id": registered_user["user_id"],
                "action": "connexion_jour",
                "code_langue": "fr",
                "offline_mode": False,
                "multiplicateur_evenement": 1.0,
                "region": "Atlantique",
                "module": "nutricore",
                "espece": "poulet",
            },
        )
    )
    assert any(
        data["points"].get(key, 0) >= 1
        for key in ("points_total", "points_totaux", "points_base")
    )


def test_auth_inscription(client):
    phone = f"229{uuid.uuid4().int % 10**10:010d}"
    resp = client.post(
        "/auth/inscription",
        json={
            "telephone": phone,
            "prenom": "Nouveau",
            "langue_preferee": "fr",
            "espece_principale": "poulet",
            "region": "Littoral",
        },
    )
    assert resp.status_code in (200, 201)


def test_paiement_creer(client, registered_user):
    data = _assert_ok(
        client.post(
            "/paiement/creer",
            json={
                "user_id": registered_user["user_id"],
                "abonnement": "premium",
                "telephone": registered_user["phone"],
                "prenom": "Testeur",
            },
        )
    )
    assert data["montant"] == 8000
