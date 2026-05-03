from __future__ import annotations

# pyright: reportMissingImports=false
import uuid
from pathlib import Path

import academy_service
import auth
import community_service
import database
import farmcast_service
import farmmanager_service
import gamification_api
import paiement_service
import pytest
import reprotrack_service
import scraper_prix
import vetscan_service
from database import get_user_by_id
from fastapi import FastAPI
from fastapi.testclient import TestClient
from nutrition_engine import NutritionEngine
from pydantic import BaseModel, Field, field_validator

from tests import _bootstrap  # noqa: F401


class GenererRationRequest(BaseModel):
    espece: str = Field(..., min_length=2)
    stade: str = Field(..., min_length=2)
    ingredients_disponibles: list[str] = Field(..., min_length=1)
    nombre_animaux: int = Field(default=1, ge=1, le=200000)
    langue: str = Field(default="fr", min_length=2, max_length=8)
    objectif: str = Field(default="equilibre")

    @field_validator("ingredients_disponibles")
    @classmethod
    def _clean(cls, value: list[str]) -> list[str]:
        propre = [str(x).strip() for x in value if str(x).strip()]
        if not propre:
            raise ValueError("Aucun ingrédient valide fourni.")
        return propre


ENGINE = NutritionEngine(
    data_dir=Path(__file__).resolve().parent.parent / "data",
    nombre_animaux_par_defaut=1,
)


app = FastAPI()
app.include_router(auth.router)
app.include_router(vetscan_service.router)
app.include_router(reprotrack_service.router)
app.include_router(farmmanager_service.router)
app.include_router(scraper_prix.router)
app.include_router(gamification_api.router)
app.include_router(academy_service.router)
app.include_router(farmcast_service.router)
app.include_router(community_service.router)
app.include_router(paiement_service.router)


@app.get("/sante")
def sante():
    return {
        "status": "ok",
        "app": "FeedFormula AI",
        "version": "test",
        "services": {
            "database": "ok",
            "auth": "ok",
            "gamification": "ok",
            "vetscan": "ok",
            "audio": "ok",
            "reprotrack": "ok",
            "farmcast": "ok",
            "academy": "ok",
            "paiement": "ok",
            "notifications": "ok",
            "marche": "ok",
            "frontend": "ok",
        },
    }


@app.post("/generer-ration")
def generer_ration(payload: GenererRationRequest):
    composition = ENGINE.optimiser_ration(
        ingredients_disponibles=payload.ingredients_disponibles,
        espece=payload.espece,
        stade=payload.stade,
        objectif=payload.objectif,
    )
    return {
        "ration": "RATION TEST",
        "composition": composition.get("composition", {}),
        "cout_fcfa_kg": float(composition.get("cout_fcfa_kg", 0.0)),
        "cout_7_jours": float(composition.get("cout_total_7_jours", 0.0)),
        "langue_detectee": payload.langue,
        "points_gagnes": 10,
        "temps_generation_secondes": 0.1,
    }


@pytest.fixture()
def client(monkeypatch):
    database.init_db()

    async def _fake_analyser_symptomes(espece, symptomes, langue="fr"):
        return {
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
            "langue": langue,
            "espece": espece,
            "mode": "fallback_local",
        }

    monkeypatch.setattr(
        vetscan_service.vetscan_service,
        "analyser_symptomes",
        _fake_analyser_symptomes,
    )

    monkeypatch.setattr(
        ENGINE,
        "optimiser_ration",
        lambda **kwargs: {
            "composition": {"mais": 60, "soja": 30, "premix": 10},
            "cout_fcfa_kg": 250.0,
            "cout_total_7_jours": 1750.0,
        },
    )

    class _FakeFarmManagerResponse:
        class _Choice:
            class _Message:
                content = '{"animal_id":"lot_poulets","type_evenement":"traitement","date_evenement":"2026-05-03","details":"Achat de 10 sacs d aliment et traitement du lot de poulets.","action_requise":"Vérifier le protocole de traitement appliqué au lot de poulets et enregistrer l achat d aliment si le montant est disponible.","date_rappel":null,"cout_total":0,"revenu":0,"source":"ia"}'

            message = _Message()

        choices = [_Choice()]

    class _FakeFarmManagerClient:
        class _Chat:
            class _Completions:
                def create(self, **kwargs):
                    return _FakeFarmManagerResponse()

            completions = _Completions()

        chat = _Chat()

    monkeypatch.setattr(
        farmmanager_service, "_client", lambda: _FakeFarmManagerClient()
    )

    return TestClient(app)


def _assert_fast(response, max_seconds: float = 30.0):
    assert response.elapsed.total_seconds() < max_seconds
    return response


def _register_user(client: TestClient):
    phone = "229" + str(uuid.uuid4().int)[-10:]
    payload = {
        "telephone": phone,
        "prenom": "Testeur",
        "langue_preferee": "fr",
        "espece_principale": "poulet",
        "region": "Atlantique",
    }
    resp = _assert_fast(client.post("/auth/inscription", json=payload))
    assert resp.status_code in (200, 201)
    otp = resp.json().get("otp_dev")
    assert otp

    verify = _assert_fast(
        client.post("/auth/verifier-otp", json={"telephone": phone, "code_otp": otp})
    )
    assert verify.status_code == 200
    data = verify.json()
    return {
        "phone": phone,
        "user_id": data["user"]["id"],
        "token": data["access_token"],
    }


def _seed_academy_completion(user_id: str):
    db = next(database.get_db())
    try:
        for formation in academy_service.FORMATIONS:
            for lecon in formation["lecons"]:
                database.create_formation_completee(
                    db,
                    user_id,
                    formation["code"],
                    int(lecon["numero"]),
                    score_quiz=90,
                )
    finally:
        db.close()


def test_sante_endpoint(client):
    resp = _assert_fast(client.get("/sante"))
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["services"]["database"] == "ok"


@pytest.mark.parametrize(
    "espece", ["poulet_chair", "pondeuse", "vache_laitiere", "porc", "tilapia"]
)
def test_generer_ration_par_espece(client, espece):
    resp = _assert_fast(
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
    assert resp.status_code == 200
    data = resp.json()
    assert data["ration"] == "RATION TEST"
    assert data["cout_fcfa_kg"] == 250.0
    assert data["points_gagnes"] == 10


@pytest.mark.parametrize("species", ["poulet", "vache", "chèvre"])
def test_vetscan_diagnostiquer(client, species):
    resp = _assert_fast(
        client.post(
            "/vetscan/diagnostiquer",
            json={
                "espece": species,
                "symptomes": "animal abattu avec diarrhée",
                "langue": "fr",
            },
        )
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["points_gagnes"] in (15, 20)
    assert "resultat" in data
    assert "diagnostic_1" in data["resultat"]


@pytest.mark.parametrize("species", ["bovin", "chèvre", "poulet"])
def test_reprotrack_evenement_and_calendar(client, species):
    user = _register_user(client)
    event = _assert_fast(
        client.post(
            "/reprotrack/evenement",
            json={
                "user_id": user["user_id"],
                "animal_id": f"AN-{species}",
                "espece": species,
                "type_evenement": "saillie",
                "date_evenement": "2026-01-10T10:00:00",
                "date_prevue_prochain": "2026-06-10T10:00:00",
                "notes": "Test",
            },
        )
    )
    assert event.status_code == 200
    assert event.json()["evenement"]["user_id"] == user["user_id"]

    calendrier = _assert_fast(client.get(f"/reprotrack/calendrier/{user['user_id']}"))
    assert calendrier.status_code == 200
    cal_data = calendrier.json()
    assert cal_data["user_id"] == user["user_id"]
    assert cal_data["total_evenements"] >= 1


def test_farmmanager_evenement(client):
    user = _register_user(client)
    resp = _assert_fast(
        client.post(
            "/farmmanager/evenement",
            json={
                "texte": "Achat de 10 sacs d'aliment et traitement du lot de poulets",
                "user_id": user["user_id"],
                "langue": "fr",
            },
        )
    )
    assert resp.status_code == 200
    assert resp.json()["event"]["event"]["action_requise"]


def test_marche_prix(client):
    resp = _assert_fast(client.get("/marche/prix"))
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] > 0
    assert "prix" in data


def test_defis_du_jour(client):
    resp = _assert_fast(client.get("/gamification/defis-du-jour"))
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["defis"]) == 3


def test_auth_inscription_and_otp(client):
    phone = "229" + str(uuid.uuid4().int)[-10:]
    inscription = _assert_fast(
        client.post(
            "/auth/inscription",
            json={
                "telephone": phone,
                "prenom": "Nuit",
                "langue_preferee": "fr",
                "espece_principale": "poulet",
                "region": "Littoral",
            },
        )
    )
    assert inscription.status_code in (200, 201)
    otp = inscription.json().get("otp_dev")
    assert otp

    verification = _assert_fast(
        client.post("/auth/verifier-otp", json={"telephone": phone, "code_otp": otp})
    )
    assert verification.status_code == 200
    data = verification.json()
    assert data["user"]["telephone"]
    assert data["access_token"]


def test_academy_catalogue_progression_and_certificat(client):
    user = _register_user(client)

    formations = _assert_fast(client.get("/academy/formations"))
    assert formations.status_code == 200
    formation_data = formations.json()
    assert formation_data["total"] == 5
    assert len(formation_data["formations"]) == 5

    formation_detail = _assert_fast(
        client.get("/academy/formation/alimentation-volailles")
    )
    assert formation_detail.status_code == 200
    assert formation_detail.json()["total_lecons"] == 5

    lesson = _assert_fast(client.get("/academy/lecon/alimentation-volailles/1"))
    assert lesson.status_code == 200
    lesson_data = lesson.json()
    assert lesson_data["quiz"]["total_questions"] == 3
    assert lesson_data["lecon"]["points_gagnes"] == 90

    _seed_academy_completion(user["user_id"])

    progression = _assert_fast(client.get(f"/academy/progression/{user['user_id']}"))
    assert progression.status_code == 200
    progress_data = progression.json()
    assert progress_data["pourcentage_global"] == 100.0
    assert progress_data["lecons_completees"] == 18

    certifications = _assert_fast(
        client.get(f"/academy/certifications/{user['user_id']}")
    )
    assert certifications.status_code == 200
    cert_data = certifications.json()
    assert cert_data["total"] == 5
    assert all(item["certificat_url"] for item in cert_data["certifications"])


def test_farmcast_creation_history_and_sharing(client):
    created = _assert_fast(
        client.post(
            "/farmcast/creer",
            json={
                "theme": "Vaccination des poulets",
                "langue": "fr",
                "format_souhaite": "audio",
                "public_cible": "éleveurs de volailles",
            },
        )
    )
    assert created.status_code == 200
    data = created.json()
    assert data["script"]
    assert data["audio_url"].endswith(".mp3")
    assert len(data["images_urls"]) == 3
    assert data["fiche_pdf_url"].endswith(".pdf")

    history = _assert_fast(client.get("/farmcast/contenus/demo-user"))
    assert history.status_code == 200
    assert history.json()["total"] >= 1

    share = _assert_fast(client.get(f"/farmcast/partager/{data['id']}"))
    assert share.status_code == 200
    share_data = share.json()
    assert share_data["whatsapp_url"].startswith("https://wa.me/")
    assert share_data["youtube_url"].startswith("https://www.youtube.com/")
    assert share_data["tiktok_url"].startswith("https://www.tiktok.com/")


def test_community_posts_marketplace_and_comments(client):
    user = _register_user(client)

    empty_feed = _assert_fast(client.get("/community/posts"))
    assert empty_feed.status_code == 200

    post_response = _assert_fast(
        client.post(
            "/community/posts",
            data={
                "user_id": user["user_id"],
                "contenu": "Je partage une astuce sur la gestion de l'eau propre.",
                "type": "texte",
            },
            files={
                "photo": ("photo.txt", b"image-test", "text/plain"),
            },
        )
    )
    assert post_response.status_code == 200
    post = post_response.json()
    assert post["contenu"]

    liked = _assert_fast(client.post(f"/community/posts/{post['id']}/like"))
    assert liked.status_code == 200
    assert liked.json()["likes"] >= 1

    commented = _assert_fast(
        client.post(
            f"/community/posts/{post['id']}/commentaires",
            json={
                "user_id": user["user_id"],
                "contenu": "Merci pour le conseil !",
            },
        )
    )
    assert commented.status_code == 200
    assert commented.json()["contenu"]

    market_create = _assert_fast(
        client.post(
            "/community/marche",
            json={
                "user_id": user["user_id"],
                "type": "vente",
                "espece": "poulet",
                "quantite": "25 têtes",
                "prix": "150000 FCFA",
                "localisation": "Littoral",
                "statut": "active",
            },
        )
    )
    assert market_create.status_code == 200

    market_filter = _assert_fast(
        client.get("/community/marche?type=vente&espece=poulet")
    )
    assert market_filter.status_code == 200
    market_data = market_filter.json()
    assert market_data["total"] >= 1
    assert market_data["annonces"][0]["espece"] == "poulet"


def test_paiement_creer_webhook_statut_et_historique(client):
    user = _register_user(client)

    created = _assert_fast(
        client.post(
            "/paiement/creer",
            json={
                "user_id": user["user_id"],
                "abonnement": "premium",
                "telephone": user["phone"],
                "prenom": "Testeur",
            },
        )
    )
    assert created.status_code == 200
    tx = created.json()
    assert tx["montant"] == 8000
    assert tx["lien_paiement"]

    pending = _assert_fast(client.get(f"/paiement/statut/{tx['transaction_id']}"))
    assert pending.status_code == 200
    assert pending.json()["statut"] in {"pending", "paid"}

    webhook = _assert_fast(
        client.post(
            "/paiement/webhook",
            json={
                "reference": tx["transaction_id"],
                "status": "paid",
                "amount": tx["montant"],
                "metadata": {
                    "user_id": user["user_id"],
                    "abonnement": "premium",
                    "telephone": user["phone"],
                },
            },
        )
    )
    assert webhook.status_code == 200
    assert webhook.json()["statut"] == "paid"

    status_after = _assert_fast(client.get(f"/paiement/statut/{tx['transaction_id']}"))
    assert status_after.status_code == 200
    assert status_after.json()["statut"] == "paid"
    assert status_after.json()["abonnement_active"] == "premium"

    history = _assert_fast(client.get(f"/paiement/historique/{user['user_id']}"))
    assert history.status_code == 200
    history_data = history.json()
    assert history_data["total"] >= 1
    assert history_data["transactions"][0]["transaction_id"] == tx["transaction_id"]

    db = next(database.get_db())
    try:
        user_db = get_user_by_id(db, user["user_id"])
        assert user_db is not None
        assert user_db.abonnement == "premium"
    finally:
        db.close()
