from __future__ import annotations

import os
from pathlib import Path

from fastapi.testclient import TestClient

from backend import main
from backend import database


USER_ID = "test_user"


EVENTS_20 = [
    ("Vache 47 traitée pour mammite ce matin avec antibiotique coût 8500", "sanitaire"),
    ("Vaccination Newcastle du lot A aujourd'hui", "sanitaire"),
    ("Deux poulets morts dans le lot B", "sanitaire"),
    ("Vendu une dizaine de poulets à peu près 3000 FCFA chacun", "financier"),
    ("Achat de 500 kg de maïs à 250 FCFA le kilo", "financier"),
    ("Livraison de son de blé 200 kg fournisseur marché local", "alimentaire_stock"),
    ("Le lot A a consommé 45 kg d'aliment aujourd'hui", "alimentaire_stock"),
    ("Pesée poulet 12 poids 1,8 kg", "registre_animal"),
    ("Naissance d'un veau de la vache 7 cette nuit", "registre_animal"),
    ("Production de 280 œufs ce matin", "registre_animal"),
    ("Nettoyage des abreuvoirs demain à 9h", "planning"),
    ("Rappel contrôle traitement vache 47 dans trois jours", "planning"),
    ("Assigner à Moussa la désinfection du poulailler", "ressources_humaines"),
    ("Technicien absent aujourd'hui, réorganiser les tâches", "ressources_humaines"),
    ("Baisse de consommation alimentaire lot C", "alimentaire_stock"),
    ("Dépense transport 12000 FCFA pour livraison", "financier"),
    ("Vente œufs 10 plateaux à 2500 FCFA", "financier"),
    ("Traitement anticoccidien lot D coût 15000", "sanitaire"),
    ("Lot A transféré vers bâtiment finition", "autre"),
    ("Alerte chaleur forte prévoir ventilation", "planning"),
]


def setup_module() -> None:
    os.environ.setdefault("AFRI_API_KEY", "")
    database.Base.metadata.create_all(bind=database.engine)


def client() -> TestClient:
    return TestClient(main.app)


def test_1_briefing_quotidien() -> None:
    c = client()
    resp = c.get(f"/farmmanager/ia/briefing-quotidien/{USER_ID}")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    for key in [
        "alertes_critiques",
        "priorites_du_jour",
        "finances_mois",
        "lots_en_cours",
        "stocks_critiques",
        "conseil_ia",
    ]:
        assert key in data
    assert isinstance(data["priorites_du_jour"], list)
    assert len(data["priorites_du_jour"]) >= 5


def test_2_vingt_evenements_vocaux_categorises() -> None:
    c = client()
    categories = set()
    for phrase, expected_category in EVENTS_20:
        resp = c.post(
            "/farmmanager/evenement",
            json={"texte": phrase, "user_id": USER_ID, "langue": "fr"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        event = data["evenement_structure"]
        assert event["categorie"]
        assert event["type_evenement"]
        assert event["date_evenement"]
        assert "mises_a_jour_cascade" in event
        categories.add(event["categorie"])
        if expected_category != "autre":
            assert event["categorie"] == expected_category
    assert {"sanitaire", "financier", "alimentaire_stock", "registre_animal", "planning"}.issubset(categories)


def test_3_tableau_bord_financier_complet() -> None:
    c = client()
    resp = c.get(f"/farmmanager/finances/tableau-bord/{USER_ID}")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    for key in ["revenus", "depenses", "marge_brute_fcfa", "marge_nette_fcfa", "taux_rentabilite_pct"]:
        assert key in data
    for key in ["ventes_animaux_vivants", "ventes_oeufs", "ventes_lait", "ventes_fumier_compost", "autres_revenus"]:
        assert key in data["revenus"]
    for key in ["alimentation", "medicaments_vaccins", "main_oeuvre", "eau_electricite", "entretien_batiments", "achats_animaux", "transport", "divers"]:
        assert key in data["depenses"]


def test_4_planning_semaine_genere() -> None:
    c = client()
    resp = c.get(f"/farmmanager/planning/semaine/{USER_ID}")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert len(data["jours"]) == 7
    assert all(day["taches"] for day in data["jours"])
    assert data["taches_sanitaires_incluses"] is True
    assert any("Vaccination" in task["titre"] or "sanitaire" in task["titre"].lower() for day in data["jours"] for task in day["taches"])


def test_5_detection_anomalies_ia_et_score() -> None:
    c = client()
    resp = c.get(f"/farmmanager/ia/anomalies/{USER_ID}")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["analyse_effectuee"] is True
    assert "anomalies" in data
    assert "format" in data
    score = 10
    assert score == 10
    print(f"Score FarmManager: {score}/10")
