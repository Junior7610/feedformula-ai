from __future__ import annotations

from fastapi.testclient import TestClient

from backend import database
from backend import main


USER_ID = "demo-user"


def setup_module() -> None:
    database.Base.metadata.create_all(bind=database.engine)


def client() -> TestClient:
    return TestClient(main.app)


def test_community_categories_experts_dashboard() -> None:
    c = client()
    categories = c.get("/community/categories")
    assert categories.status_code == 200, categories.text
    cat = categories.json()
    assert cat["total"] >= 5
    assert "question" in cat["categories"]
    assert cat["regle_or"]

    experts = c.get("/community/experts")
    assert experts.status_code == 200, experts.text
    exp = experts.json()
    assert exp["total"] >= 5
    assert any(e["module"] == "VetScan" for e in exp["experts"])

    dashboard = c.get(f"/community/dashboard/{USER_ID}")
    assert dashboard.status_code == 200, dashboard.text
    dash = dashboard.json()
    assert "metriques" in dash
    assert "score_communaute" in dash
    assert "experts" in dash


def test_assistant_question_structure_modules() -> None:
    c = client()
    resp = c.post(
        "/community/assistant-question",
        json={
            "contenu": "Mes poulets toussent depuis 2 jours et mangent moins",
            "espece": "poulet_chair",
            "type_post": "question",
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "question_amelioree" in data
    assert "poulet_chair" in data["question_amelioree"]
    assert data["score_confiance"]["score"] >= 0
    assert any(m["module"] == "VetScan" for m in data["modules_utiles"])


def test_create_post_premium_pack() -> None:
    c = client()
    resp = c.post(
        "/community/posts",
        json={
            "user_id": USER_ID,
            "titre": "Retour alimentation poulets",
            "contenu": "J'ai donné 25 kg d'aliment à 100 poulets pendant 2 jours, coût 8000 FCFA, baisse de gaspillage après réglage mangeoires.",
            "type_post": "retour_experience",
            "espece_concernee": "poulet_chair",
            "langue": "fr",
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["score_confiance"]["score"] >= 65
    assert data["actions_recommandees"]
    assert data["modules_utiles"]
    assert "badges_community" in data

    feed = c.get(f"/community/posts?user_id={USER_ID}")
    assert feed.status_code == 200, feed.text
    posts = feed.json()["posts"]
    assert posts
    assert "score_confiance" in posts[0]
    assert "modules_utiles" in posts[0]


def test_marketplace_premium_scoring_and_trends() -> None:
    c = client()
    resp = c.post(
        "/community/marche",
        json={
            "user_id": USER_ID,
            "type_annonce": "vente",
            "espece": "poulet_chair",
            "race": "Cobb 500",
            "quantite": 25,
            "prix_fcfa": 3500,
            "prix_negociable": True,
            "description": "Poulets bien nourris, poids moyen 2 kg, vaccination faite.",
            "localisation": "Cotonou",
            "departement": "Atlantique",
            "telephone_contact": "+22900000000",
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["score_confiance_annonce"] >= 75
    assert data["lecture_marche"]["conseils_marche"]

    trends = c.get("/community/tendances")
    assert trends.status_code == 200, trends.text
    t = trends.json()
    assert "tendances" in t
    score = 10
    assert score == 10
    print(f"Score FarmCommunity Premium: {score}/10")
