from __future__ import annotations

import uuid
from typing import Any, Dict

import pytest
from fastapi.testclient import TestClient

from backend import main, vetscan_service


class _FakeChatCompletions:
    def create(self, **kwargs: Any):
        class _Message:
            content = "RATION CI STRICT"

        class _Choice:
            message = _Message()

        class _Response:
            choices = [_Choice()]

        return _Response()


class _FakeClient:
    class _Chat:
        completions = _FakeChatCompletions()

    chat = _Chat()


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    main.RATION_CACHE_MEMORY.clear()
    monkeypatch.setattr(main, "_build_afri_client", lambda: _FakeClient())
    monkeypatch.setattr(main, "_load_system_prompt", lambda: "Prompt CI strict")

    async def _fake_vetscan(*args: Any, **kwargs: Any) -> Dict[str, Any]:
        return {
            "diagnostic_1": {
                "nom": "Trouble digestif",
                "probabilite": 0.8,
                "description": "Hypothèse principale.",
                "symptomes_correspondants": ["diarrhée"],
            },
            "protocole_soins": ["Isoler", "Hydrater"],
            "decision": "autonome",
            "mode": "ci_fake",
        }

    monkeypatch.setattr(vetscan_service.vetscan_service, "analyser_symptomes", _fake_vetscan)
    return TestClient(main.app)


def _assert_json_keys(resp: Any, keys: list[str]) -> Dict[str, Any]:
    assert resp.status_code == 200, resp.text
    data = resp.json()
    for key in keys:
        assert key in data, f"Clé manquante: {key}"
    return data


def _register_user(client: TestClient) -> Dict[str, str]:
    phone = "+2296" + str(uuid.uuid4().int % 10**8).rjust(8, "0")
    resp = client.post(
        "/auth/inscription",
        json={
            "telephone": phone,
            "prenom": "CI",
            "langue": "fr",
            "espece_principale": "poulet_chair",
            "departement": "Atlantique",
        },
    )
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    otp = payload.get("otp_pour_test") or payload.get("otp_dev")
    assert otp

    verify = client.post("/auth/verifier-otp", json={"telephone": phone, "otp": otp})
    assert verify.status_code == 200, verify.text
    verify_data = verify.json()
    return {
        "phone": phone,
        "user_id": verify_data["user"]["id"],
        "token": verify_data["access_token"],
    }


def test_health_and_catalogs(client: TestClient):
    _assert_json_keys(client.get("/sante"), ["status", "app", "version"])
    _assert_json_keys(client.get("/langues"), ["total", "langues"])
    _assert_json_keys(client.get("/marche/prix"), ["total", "prix"])


def test_nutricore_core(client: TestClient):
    data = _assert_json_keys(
        client.post(
            "/generer-ration",
            json={
                "espece": "poulet_chair",
                "stade": "croissance",
                "ingredients_disponibles": ["mais", "tourteau_soja", "son_ble"],
                "nombre_animaux": 50,
                "langue": "fr",
                "objectif": "equilibre",
            },
        ),
        ["ration", "composition", "cout_fcfa_kg", "langue_detectee", "points_gagnes"],
    )
    assert isinstance(data["composition"], dict)


def test_vetscan_and_reprotrack(client: TestClient):
    user = _register_user(client)

    vet = _assert_json_keys(
        client.post(
            "/vetscan/diagnostiquer",
            json={
                "espece": "poulet_chair",
                "symptomes": "diarrhée, baisse d'appétit",
                "langue": "fr",
                "user_id": user["user_id"],
                "departement": "Atlantique",
            },
        ),
        ["resultat"],
    )
    assert isinstance(vet["resultat"], dict)
    assert "decision" in vet["resultat"]

    _assert_json_keys(
        client.post(
            "/reprotrack/evenement",
            json={
                "user_id": user["user_id"],
                "animal_id": "VACHE-1",
                "espece": "vache_laitiere",
                "type_evenement": "saillie",
                "date_evenement": "2026-05-13",
                "notes": "CI test",
            },
        ),
        ["message", "evenement"],
    )


def test_operational_modules(client: TestClient):
    user = _register_user(client)

    pasture = _assert_json_keys(
        client.post(
            "/pasturemap/analyser",
            json={
                "espece": "zebu",
                "nombre_animaux": 12,
                "superficie_hectares": 8,
                "nombre_paddocks": 4,
                "saison": "saison_seche",
                "langue": "fr",
            },
        ),
        ["charge_animale_ha"],
    )
    assert isinstance(pasture["charge_animale_ha"], (int, float))

    _assert_json_keys(
        client.post(
            "/farmmanager/evenement",
            json={
                "texte": "Vaccination lot avicole", "user_id": user["user_id"], "langue": "fr"
            },
        ),
        ["event"],
    )

    _assert_json_keys(client.get("/academy/formations"), ["total", "formations"])
    _assert_json_keys(client.get("/academy/formation/alimentation_volailles"), ["code", "lecons"])
    _assert_json_keys(client.get("/academy/lecon/alimentation_volailles/1"), ["formation", "lecon", "quiz"])

    _assert_json_keys(
        client.post(
            "/academy/quiz/soumettre",
            json={
                "user_id": user["user_id"],
                "formation_code": "alimentation_volailles",
                "lecon_numero": 1,
                "reponses": [1, 2, 3],
                "langue": "fr",
            },
        ),
        ["score", "points_gagnes"],
    )


def test_community_gamification_paiement_audio_notifications(client: TestClient):
    user = _register_user(client)

    _assert_json_keys(client.get("/community/posts"), ["posts"])
    _assert_json_keys(
        client.post(
            "/community/posts",
            json={
                "user_id": user["user_id"],
                "titre": "Conseil CI",
                "contenu": "Retour d'expérience utile en aviculture.",
                "type_post": "conseil",
                "espece_concernee": "poulet_chair",
                "langue": "fr",
            },
        ),
        ["id", "contenu"],
    )

    _assert_json_keys(
        client.post(
            "/gamification/action",
            json={"user_id": user["user_id"], "action": "connexion_jour"},
        ),
        ["points_gagnes", "total_points", "niveau_actuel"],
    )

    defi = client.post(
        "/gamification/defi/completer",
        json={"user_id": user["user_id"], "defi_numero": 1, "date": "2026-05-13"},
    )
    assert defi.status_code in (200, 409), defi.text

    _assert_json_keys(
        client.post(
            "/paiement/creer",
            json={
                "user_id": user["user_id"],
                "abonnement": "standard",
                "duree": "mensuel",
                "telephone": user["phone"],
                "prenom": "CI",
            },
        ),
        ["transaction_id", "montant"],
    )

    notif = _assert_json_keys(client.get(f"/notifications/du-jour/{user['user_id']}"), ["notification"])
    assert isinstance(notif["notification"], dict)
    assert "message" in notif["notification"]

    synth = client.post(
        "/audio/synthese",
        json={"texte": "Bonjour test CI", "langue": "fr"},
    )
    assert synth.status_code == 200
    assert len(synth.content) > 0
