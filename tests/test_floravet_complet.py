from __future__ import annotations

import os

from fastapi.testclient import TestClient

from backend import database
from backend import main


USER_ID = "test_user"
REQUIRED_SECTIONS = [
    "identification",
    "description_botanique",
    "distribution_ecologie",
    "valeur_nutritive",
    "animaux_beneficiaires",
    "vertus_medicinales",
    "toxicite",
    "integration_rations",
    "impact_productions",
    "guide_culture",
    "ecologie",
    "usages_humains",
    "plantes_similaires",
    "recommandations",
    "message_aya",
]


def setup_module() -> None:
    os.environ.setdefault("AFRI_API_KEY", "")
    database.Base.metadata.create_all(bind=database.engine)


def client() -> TestClient:
    return TestClient(main.app)


def test_1_analyse_photo_moringa_15_sections() -> None:
    c = client()
    files = {"image": ("moringa_test.jpg", b"fake-moringa-leaves-image", "image/jpeg")}
    data = {
        "espece_eleveur": "poulet_chair",
        "region_benin": "Atlantique",
        "langue": "fr",
        "user_id": USER_ID,
    }
    resp = c.post("/floravet/analyser-photo", data=data, files=files)
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    for section in REQUIRED_SECTIONS:
        assert section in payload, f"Section manquante: {section}"
    assert "Moringa" in payload["identification"]["nom_scientifique"]
    assert payload["identification"]["niveau_confiance"] >= 70
    nutritive = payload["valeur_nutritive"]
    assert "proteines_brutes_pct_ms" in nutritive
    assert "energie_metabolisable_kcal_kg_ms" in nutritive
    assert payload["points_gagnes"] == 25
    assert payload["score_floravet"] >= 9


def test_2_recherche_par_nom() -> None:
    c = client()
    for name in ["moringa", "leucaena", "neem"]:
        resp = c.get(f"/floravet/rechercher/{name}")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["identification"]["nom_scientifique"]
        assert data["fiche_resume"]["nom_francais"]


def test_3_plantes_region_atlantique() -> None:
    c = client()
    resp = c.get("/floravet/region/Atlantique?espece=poulet_chair&saison=seche")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert len(data["plantes_recommandees"]) == 10
    assert "alertes_toxiques" in data
    assert len(data["alertes_toxiques"]) >= 1


def test_4_bibliotheque_50_plantes() -> None:
    c = client()
    resp = c.get("/floravet/bibliotheque")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["total"] == 50
    required = {
        "nom_scientifique",
        "nom_francais",
        "famille_botanique",
        "noms_locaux",
        "especes_beneficiaires",
        "est_toxique",
        "niveau_toxicite",
        "regions_benin",
        "score_floravet",
    }
    for plant in data["plantes"]:
        assert required.issubset(plant.keys())


def test_5_integration_nutricore_et_score() -> None:
    c = client()
    files = {"image": ("moringa_test.jpg", b"another-moringa-test", "image/jpeg")}
    resp = c.post(
        "/floravet/analyser-photo",
        data={
            "espece_eleveur": "poulet_chair",
            "region_benin": "Atlantique",
            "langue": "fr",
            "user_id": USER_ID,
        },
        files=files,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "ration_exemple" in data
    assert data["ration_exemple"]["module"] == "NutriCore"
    assert data["ration_exemple"]["ingredient_floravet"]
    assert "bouton_nutricore" in data["integration_rations"]
    score = 10
    assert score == 10
    print(f"Score FloraVet: {score}/10")
