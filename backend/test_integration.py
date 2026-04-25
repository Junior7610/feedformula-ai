#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Test d'intégration backend FeedFormula AI.

Objectifs :
1) Lancer le serveur FastAPI en arrière-plan
2) Envoyer une vraie requête POST à /generer-ration
3) Vérifier que la réponse contient tous les champs attendus
4) Afficher le résultat complet
5) Arrêter proprement le serveur

Ce script gère aussi les cas d'erreur :
- serveur indisponible (mode offline / backend non démarré)
- timeout
- réponse HTTP invalide
- JSON de réponse incomplet
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

import requests

# ---------------------------------------------------------------------------
# Configuration du test
# ---------------------------------------------------------------------------
HOST = "127.0.0.1"
PORT = 8000
BASE_URL = f"http://{HOST}:{PORT}"
SANTE_URL = f"{BASE_URL}/sante"
GENERER_URL = f"{BASE_URL}/generer-ration"

# Délai max pour que le serveur soit prêt.
MAX_WAIT_SECONDS = 40

# Timeout HTTP des appels API.
HTTP_TIMEOUT_SECONDS = 90

# Champs obligatoires attendus dans la réponse /generer-ration.
CHAMPS_OBLIGATOIRES = [
    "ration",
    "composition",
    "cout_fcfa_kg",
    "cout_7_jours",
    "langue_detectee",
    "points_gagnes",
    "temps_generation_secondes",
]


# ---------------------------------------------------------------------------
# Fonctions utilitaires
# ---------------------------------------------------------------------------
def print_info(message: str) -> None:
    """Affichage standard lisible en console."""
    print(f"[INFO] {message}")


def print_ok(message: str) -> None:
    """Affichage succès lisible en console."""
    print(f"[OK]   {message}")


def print_err(message: str) -> None:
    """Affichage erreur lisible en console."""
    print(f"[ERR]  {message}")


def lancer_serveur_fastapi() -> subprocess.Popen:
    """
    Lance le serveur FastAPI en arrière-plan via uvicorn.

    Retour:
        Processus subprocess.Popen

    Lancement depuis le dossier backend pour simplifier l'import "main:app".
    """
    project_root = Path(__file__).resolve().parents[1]
    backend_dir = project_root / "backend"

    if not backend_dir.exists():
        raise FileNotFoundError(f"Dossier backend introuvable: {backend_dir}")

    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "main:app",
        "--host",
        HOST,
        "--port",
        str(PORT),
    ]

    print_info(f"Lancement serveur: {' '.join(cmd)}")
    process = subprocess.Popen(
        cmd,
        cwd=str(backend_dir),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return process


def attendre_serveur_disponible(timeout_seconds: int = MAX_WAIT_SECONDS) -> bool:
    """
    Attend que l'endpoint /sante réponde "ok".

    Retour:
        True si prêt, False sinon.
    """
    start = time.time()
    while time.time() - start < timeout_seconds:
        try:
            response = requests.get(SANTE_URL, timeout=3)
            if response.status_code == 200:
                payload = response.json()
                if payload.get("status") == "ok":
                    return True
        except requests.RequestException:
            # Le serveur n'est pas encore prêt : on réessaie.
            pass
        time.sleep(1.0)
    return False


def valider_reponse_json(payload: Dict[str, Any]) -> List[str]:
    """
    Vérifie la présence des champs obligatoires dans la réponse JSON.

    Retour:
        Liste des champs manquants (vide si tout est conforme).
    """
    manquants = [champ for champ in CHAMPS_OBLIGATOIRES if champ not in payload]
    return manquants


def envoyer_requete_generation() -> Dict[str, Any]:
    """
    Envoie une vraie requête POST à /generer-ration et retourne le JSON.
    """
    data = {
        "espece": "poulet_chair",
        "stade": "croissance",
        "ingredients_disponibles": ["maïs", "tourteau_soja", "farine_poisson"],
        "nombre_animaux": 50,
        "langue": "fr",
        "objectif": "equilibre",
    }

    print_info("Envoi de la requête POST /generer-ration...")
    response = requests.post(
        GENERER_URL,
        json=data,
        timeout=HTTP_TIMEOUT_SECONDS,
    )

    if response.status_code != 200:
        # Message clair pour l'éleveur / opérateur.
        detail = ""
        try:
            detail_json = response.json()
            detail = str(detail_json.get("detail", ""))
        except Exception:
            detail = response.text[:500]

        raise RuntimeError(
            f"Réponse HTTP invalide ({response.status_code}). Détail: {detail}"
        )

    try:
        payload = response.json()
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Réponse non JSON reçue: {exc}") from exc

    return payload


def arreter_serveur(process: subprocess.Popen) -> None:
    """
    Arrête proprement le serveur FastAPI.
    """
    if process.poll() is not None:
        return  # Process déjà arrêté.

    print_info("Arrêt du serveur FastAPI...")
    process.terminate()
    try:
        process.wait(timeout=10)
        print_ok("Serveur arrêté proprement.")
    except subprocess.TimeoutExpired:
        print_err("Arrêt propre impossible, kill forcé.")
        process.kill()
        process.wait(timeout=5)


# ---------------------------------------------------------------------------
# Exécution principale
# ---------------------------------------------------------------------------
def main() -> int:
    process: subprocess.Popen | None = None

    try:
        process = lancer_serveur_fastapi()

        # Vérifie que le process ne meurt pas immédiatement.
        time.sleep(1.5)
        if process.poll() is not None:
            stdout, stderr = process.communicate(timeout=5)
            print_err("Le serveur s'est arrêté immédiatement.")
            if stdout:
                print("----- STDOUT -----")
                print(stdout)
            if stderr:
                print("----- STDERR -----")
                print(stderr)
            return 1

        print_info("Attente de disponibilité du serveur...")
        ready = attendre_serveur_disponible(MAX_WAIT_SECONDS)

        if not ready:
            print_err(
                "Serveur indisponible (mode offline ou backend non démarré dans les délais)."
            )
            return 1

        print_ok("Serveur disponible.")
        payload = envoyer_requete_generation()

        # Validation des champs attendus.
        manquants = valider_reponse_json(payload)
        if manquants:
            print_err(f"Réponse incomplète. Champs manquants: {', '.join(manquants)}")
            print("----- RÉPONSE REÇUE -----")
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 1

        print_ok("Réponse valide: tous les champs attendus sont présents.")
        print("----- RÉSULTAT COMPLET -----")
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        print("----------------------------")

        return 0

    except requests.Timeout:
        print_err("Timeout réseau: la requête a dépassé le délai autorisé.")
        return 1
    except requests.ConnectionError:
        print_err("Connexion impossible: serveur non accessible (offline ou arrêté).")
        return 1
    except Exception as exc:
        print_err(f"Erreur d'intégration: {exc}")
        return 1
    finally:
        if process is not None:
            arreter_serveur(process)


if __name__ == "__main__":
    raise SystemExit(main())
