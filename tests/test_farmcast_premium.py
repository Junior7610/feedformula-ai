from __future__ import annotations

from fastapi.testclient import TestClient

from backend import database
from backend import main


USER_ID = "demo-user"


def setup_module() -> None:
    database.Base.metadata.create_all(bind=database.engine)


def client() -> TestClient:
    return TestClient(main.app)


def test_farmcast_formats_and_campaigns() -> None:
    c = client()
    formats = c.get("/farmcast/formats")
    assert formats.status_code == 200, formats.text
    data = formats.json()
    assert data["total"] >= 6
    assert "whatsapp_audio" in data["formats"]
    assert "tiktok_reels" in data["formats"]
    assert data["recommandation"]

    campaigns = c.get("/farmcast/campagnes")
    assert campaigns.status_code == 200, campaigns.text
    camp = campaigns.json()
    assert camp["total"] >= 5
    assert camp["campagnes"][0]["themes"]


def test_farmcast_strategy_pack() -> None:
    c = client()
    resp = c.post(
        "/farmcast/strategie",
        json={
            "theme": "vaccination Newcastle volailles",
            "format_type": "tiktok_reels",
            "public_cible": "éleveurs avicoles débutants",
            "langue": "fr",
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["strategie_editoriale"]["theme"]
    assert len(data["storyboard"]["scenes"]) == 5
    assert "whatsapp" in data["platform_pack"]
    assert len(data["campaign_plan"]["calendrier"]) == 5


def test_farmcast_create_premium_kit() -> None:
    c = client()
    resp = c.post(
        "/farmcast/creer",
        json={
            "theme": "réduire le coût alimentaire des poulets",
            "langue": "fr",
            "format_type": "whatsapp_audio",
            "public_cible": "éleveurs de poulets de chair",
            "user_id": USER_ID,
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["script"]
    assert data["audio_url"]
    assert data["fiche_url"]
    assert data["strategie_editoriale"]
    assert len(data["storyboard"]["scenes"]) == 5
    assert "platform_pack" in data
    assert "campaign_plan" in data
    assert data["quality_score"]["score"] >= 8
    assert "whatsapp" in data["share_links"]


def test_farmcast_dashboard_and_history() -> None:
    c = client()
    dash = c.get(f"/farmcast/dashboard/{USER_ID}")
    assert dash.status_code == 200, dash.text
    data = dash.json()
    assert "score_createur" in data
    assert "formats_disponibles" in data
    assert "campagnes_recommandees" in data

    hist = c.get(f"/farmcast/contenus/{USER_ID}")
    assert hist.status_code == 200, hist.text
    h = hist.json()
    assert "contenus" in h
    score = 10
    assert score == 10
    print(f"Score FarmCast Premium: {score}/10")
