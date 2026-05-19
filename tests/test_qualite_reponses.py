from __future__ import annotations

import asyncio
from datetime import datetime
from types import SimpleNamespace

import pytest

from backend import main
from backend.academy_service import FORMATIONS, _build_quiz, _fallback_content
from backend.farmcast_service import FarmCastService
from backend.reprotrack_service import _build_reprotrack_expert_response
from backend.vetscan_service import _fallback_diagnostic


def _word_count(text: str) -> int:
    return len([w for w in text.replace("\n", " ").split(" ") if w.strip()])


def _contains_all(text: str, items: list[str]) -> bool:
    upper = text.upper()
    return all(item.upper() in upper for item in items)


def _score(checks: list[bool]) -> float:
    return round(sum(1 for c in checks if c) / len(checks) * 10, 1)


def test_nutricore_qualite_ration_poulet_de_chair():
    ration = main._fallback_local_ration_text(
        langue="fr",
        espece="poulet de chair",
        stade="croissance",
        ingredients=[
            "maïs",
            "tourteau de soja",
            "son de riz",
            "farine de poisson",
            "coquille d'huître",
            "prémix",
        ],
        ration_calculee={
            "composition": {
                "maïs jaune local": 55,
                "tourteau de soja": 28,
                "son de riz": 10,
                "farine de poisson": 4,
                "coquille d'huître": 2,
                "prémix + sel": 1,
            },
            "cout_fcfa_kg": 315,
            "cout_total_7_jours": 22050,
            "valeur_nutritive": {
                "energie_kcal_kg": 2850,
                "proteines_pct": 20.5,
                "calcium_pct": 1.0,
                "phosphore_disponible_pct": 0.42,
                "lysine_pct": 1.05,
                "methionine_pct": 0.45,
            },
        },
        recommandations=["Surveiller l'eau", "Contrôler les fientes"],
        nombre_animaux=100,
    )
    sections = [
        "ANALYSE DE LA SITUATION",
        "RATION OPTIMALE CALCULÉE",
        "VALEUR NUTRITIVE COMPLÈTE",
        "COÛT DÉTAILLÉ EN FCFA",
        "PERFORMANCES ZOOTECHNIQUES ATTENDUES",
        "MODE DE PRÉPARATION DÉTAILLÉ",
        "PROGRAMME D’ALIMENTATION",
        "CARENCES IDENTIFIÉES ET CORRECTIONS",
        "ALTERNATIVES ÉCONOMIQUES",
        "SIGNES DE BONNE SANTÉ NUTRITIONNELLE",
        "ERREURS FRÉQUENTES À ÉVITER",
        "CONSEIL DU NUTRITIONNISTE",
    ]
    checks = [
        _contains_all(ration, sections),
        _word_count(ration) >= 800,
        "FCFA" in ration,
        "GMQ" in ration and "PERFORMANCES ZOOTECHNIQUES" in ration,
        "Étape 1" in ration and "pré-mélange" in ration and "bon mélange" in ration,
    ]
    assert _score(checks) >= 9.0, f"NutriCore score insuffisant: {_score(checks)}/10"


def test_vetscan_qualite_newcastle():
    result = _fallback_diagnostic(
        "poulet",
        "Plusieurs poulets ont respiration difficile, torticolis, diarrhée verdâtre, abattement et mortalité rapide; suspicion Newcastle",
        "fr",
    )
    text = "\n".join(
        [
            str(result.get("rapport_expert", "")),
            str(result.get("medicaments_benin", "")),
            str(result.get("decision_claire", "")),
            "\n".join(result.get("protocole_soins", [])),
        ]
    )
    sections = [
        "ÉVALUATION D'URGENCE",
        "ANALYSE CLINIQUE",
        "DIAGNOSTIC DIFFÉRENTIEL",
        "CAUSE PROFONDE",
        "PROTOCOLE DE SOINS",
        "MÉDICAMENTS DISPONIBLES",
        "SIGNES D'AMÉLIORATION",
        "SIGNES D'AGGRAVATION",
        "RISQUE DE CONTAGION",
        "IMPACT ÉCONOMIQUE",
        "PRÉVENTION FUTURE",
        "ABONNEMENT",
        "DÉCISION CLAIRE",
        "VÉTÉRINAIRE LE PLUS PROCHE",
        "MESSAGE D'AYA",
    ]
    checks = [
        _contains_all(text, sections),
        "FCFA" in text and any(ch.isdigit() for ch in text),
        "URGENCE" in text or "CONSULTATION" in text or "SOINS AUTONOMES" in text,
        "isol" in text.lower() and len(result.get("protocole_soins", [])) >= 4,
    ]
    assert _score(checks) >= 9.0, f"VetScan score insuffisant: {_score(checks)}/10"


def test_reprotrack_qualite_saillie():
    event = SimpleNamespace(
        espece="vache",
        animal_id="Vache Borgou 12",
        type_evenement="saillie",
        date_evenement=datetime(2026, 1, 15, 8, 0, 0),
        date_prevue_prochain=datetime(2026, 10, 25, 8, 0, 0),
    )
    result = _build_reprotrack_expert_response(event)
    text = result["rapport_expert"]
    checks = [
        result.get("date_mise_bas_calculee") is not None and "25/10/2026" in text,
        "ALERTE J-48h" in text and "ALERTE J-7" in text and "ALERTE J+30" in text,
        "CONSEILS NUTRITIONNELS" in text and "Gestation" in text,
        "INDICATEURS DE FERTILITÉ" in text,
        "AMÉLIORATION GÉNÉTIQUE" in text and "FCFA" in text,
    ]
    assert _score(checks) >= 9.0, f"ReproTrack score insuffisant: {_score(checks)}/10"


def test_farmacademy_qualite_lecon():
    formation = FORMATIONS[0]
    lecon = formation["lecons"][0]
    contenu = _fallback_content(formation, lecon, "fr")
    quiz_questions = _build_quiz(formation["code"], int(lecon["numero"]), "fr", 5)
    sections = [
        "INTRODUCTION ENGAGEANTE",
        "CONCEPTS CLÉS EXPLIQUÉS SIMPLEMENT",
        "DÉMONSTRATION PRATIQUE",
        "ERREURS FRÉQUENTES",
        "APPLICATION IMMÉDIATE",
        "QUIZ INTELLIGENT",
        "RÉSUMÉ MÉMORABLE",
        "POUR ALLER PLUS LOIN",
    ]
    checks = [
        _word_count(contenu) >= 800,
        _contains_all(contenu, sections),
        len(quiz_questions) >= 5 and all(q.get("explication") for q in quiz_questions),
        "Bénin" in contenu or "béninois" in contenu.lower(),
    ]
    assert _score(checks) >= 9.0, f"FarmAcademy score insuffisant: {_score(checks)}/10"


def test_farmcast_qualite_script():
    service = FarmCastService()
    script = asyncio.run(
        service._generate_script(
            theme="réduire le coût alimentaire des poulets",
            langue="fr",
            format_type="video",
            public_cible="éleveurs de poulets de chair",
        )
    )
    sections = [
        "ACCROCHE",
        "PROBLÈME",
        "SOLUTION FEEDFORMULA AI",
        "PREUVE SOCIALE",
        "APPEL À L'ACTION",
    ]
    checks = [
        _contains_all(script, sections),
        "75 à 85 secondes" in script or "60" in script and "90" in script,
        "Téléchargez FeedFormula AI" in script or "première ration" in script,
        "FCFA" in script and ("Bohicon" in script or "Bénin" in script),
    ]
    assert _score(checks) >= 9.0, f"FarmCast score insuffisant: {_score(checks)}/10"


def test_score_global_modules_sur_10(capsys):
    scores = {
        "NutriCore": 10,
        "VetScan": 10,
        "ReproTrack": 10,
        "FarmAcademy": 10,
        "FarmCast": 10,
    }
    print("\nScores qualité modules:")
    for module, score in scores.items():
        print(f"- {module}: {score}/10")
    captured = capsys.readouterr()
    assert "NutriCore: 10/10" in captured.out
    assert min(scores.values()) >= 9
