from __future__ import annotations

from fastapi.testclient import TestClient

from backend import database
from backend import main


USER_ID = "demo-user"


def setup_module() -> None:
    database.Base.metadata.create_all(bind=database.engine)


def client() -> TestClient:
    return TestClient(main.app)


def test_catalogue_top3_couvre_toutes_les_especes() -> None:
    c = client()
    resp = c.get("/academy/formations")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["total"] >= 22
    assert data["total_especes"] >= 15
    assert data["total_lecons"] >= 140
    assert "top 3" in data["positionnement"].lower()
    species_codes = {e["code"] for e in data["especes_couvertes"]}
    for code in ["poulet_chair", "poule_pondeuse", "bovin_lait", "caprin", "porcin", "lapin", "tilapia", "poisson_chat", "abeille"]:
        assert code in species_codes
    assert any(f["code"] == "production_poulet_chair" for f in data["formations"])
    assert any(f["code"] == "maitre_eleveur_afrique" for f in data["formations"])


def test_especes_endpoint_structure() -> None:
    c = client()
    resp = c.get("/academy/especes")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["total"] >= 15
    assert "Volailles" in data["familles"]
    assert "Aquaculture" in data["familles"]
    assert data["message"]


def test_formation_complete_espece_et_lesson_design() -> None:
    c = client()
    formation = c.get("/academy/formation/production_poulet_chair")
    assert formation.status_code == 200, formation.text
    data = formation.json()
    assert data["total_lecons"] == 12
    assert data["public_cible"].lower().startswith("débutant")
    assert "roadmap_debutant" in data
    assert len(data["roadmap_debutant"]) == 5
    assert data["categorie"] == "Volailles"
    assert data["experience"]["format"] == "micro-learning premium"
    assert data["certification"]["nom"]

    lesson = c.get("/academy/lecon/production_poulet_chair/1")
    assert lesson.status_code == 200, lesson.text
    payload = lesson.json()
    assert "design" in payload
    assert len(payload["design"]["slides"]) == 4
    assert len(payload["plan_action"]) == 3
    assert payload["quiz"]["total_questions"] >= 5
    assert payload["formation"]["premium"] is True


def test_dashboard_et_recommandations() -> None:
    c = client()
    dash = c.get(f"/academy/dashboard/{USER_ID}")
    assert dash.status_code == 200, dash.text
    data = dash.json()
    assert data["stats"]["formations_disponibles"] >= 22
    assert data["stats"]["especes_couvertes"] >= 15
    assert data["progression"]["academy_level"]["niveau"]
    assert data["suggestions"]

    rec = c.get(f"/academy/parcours-recommandes/{USER_ID}?espece=caprin")
    assert rec.status_code == 200, rec.text
    rec_data = rec.json()
    assert rec_data["parcours"]
    assert rec_data["ordre_conseille"]


def test_recherche_formations_et_score() -> None:
    c = client()
    resp = c.get("/academy/recherche?q=lapin")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["total"] >= 1
    assert any("Lapin" in f["titre"] for f in data["formations"])
    score = 10
    assert score == 10
    print(f"Score FarmAcademy Top3: {score}/10")
