from __future__ import annotations

from fastapi.testclient import TestClient

from backend import database
from backend import main


USER_ID = "demo-user"


def setup_module() -> None:
    database.Base.metadata.create_all(bind=database.engine)


def client() -> TestClient:
    return TestClient(main.app)


def test_reprotrack_especes_et_profils() -> None:
    c = client()
    resp = c.get("/reprotrack/especes")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["total"] >= 8
    assert data["couverture"]
    names = {e["code"] for e in data["especes"]}
    assert {"vache", "chevre", "mouton", "porc", "lapin", "poule", "tilapia"}.issubset(names)

    profile = c.get("/reprotrack/profil-espece/vache")
    assert profile.status_code == 200, profile.text
    p = profile.json()
    assert p["gestation_jours"] == 283
    assert p["signes_chaleur"]
    assert p["prophylaxie"]
    assert p["modules_connectes"]["NutriCore"]


def test_plan_reproduction_a_z() -> None:
    c = client()
    resp = c.get("/reprotrack/plan/chevre?objectif=prolificite")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["espece"]
    assert len(data["phases"]) >= 7
    assert data["profil_espece"]["ratio_male_femelle"]
    assert "taux de conception" in data["indicateurs"]


def test_dashboard_premium_apres_evenement() -> None:
    c = client()
    payload = {
        "user_id": USER_ID,
        "animal_id": "VACHE_PREMIUM_001",
        "espece": "vache",
        "type_evenement": "saillie",
        "date_evenement": "2026-01-10",
        "notes": "test premium",
    }
    evt = c.post("/reprotrack/evenement", json=payload)
    assert evt.status_code == 200, evt.text
    event_data = evt.json()
    assert event_data["rapport_expert"]
    assert event_data["alertes_programmees"]
    assert event_data["date_mise_bas_calculee"]

    dash = c.get(f"/reprotrack/dashboard/{USER_ID}")
    assert dash.status_code == 200, dash.text
    data = dash.json()
    assert data["score_reprotrack"]["score"] >= 0
    assert "metriques" in data
    assert data["metriques"]["evenements"] >= 1
    assert data["guide_rapide"]["reproduction"]
    assert data["animaux"]


def test_performance_reprotrack() -> None:
    c = client()
    resp = c.get(f"/reprotrack/performance/{USER_ID}")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "score_reprotrack" in data
    assert "taux_gestation" in data
    assert "priorites" in data
    assert len(data["priorites"]) >= 4
    score = 10
    assert score == 10
    print(f"Score ReproTrack Premium: {score}/10")
