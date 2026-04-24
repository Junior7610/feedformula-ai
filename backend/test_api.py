#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Script de test API Afri (GPT-5.4) pour FeedFormula AI.

Fonctionnalités :
1) Lire AFRI_BASE_URL et AFRI_API_KEY depuis .env
2) Charger le system prompt NutriCore depuis prompts/system_prompt_principal.txt
3) Envoyer un message de test à l'API
4) Afficher la réponse complète dans le terminal
5) Mesurer et afficher le temps de réponse
6) Sauvegarder la réponse dans docs/premier_test_api.txt

Gestion d'erreurs :
- Clé API invalide
- Connexion internet absente / indisponible
- Timeout
- Réponse vide
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Optional

# Import des classes SDK et exceptions principales.
try:
    from openai import (
        APIConnectionError,
        APITimeoutError,
        AuthenticationError,
        BadRequestError,
        OpenAI,
        OpenAIError,
    )
except ImportError:
    print(
        "❌ Le package 'openai' n'est pas installé.\n"
        "Installez-le avec : python -m pip install openai"
    )
    sys.exit(1)


def charger_env_depuis_fichier(env_path: Path) -> None:
    """
    Charge les variables d'environnement depuis un fichier .env.
    - Ignore les lignes vides et les commentaires.
    - N'écrase pas les variables déjà présentes dans l'environnement.
    """
    if not env_path.exists():
        return

    for ligne in env_path.read_text(encoding="utf-8").splitlines():
        ligne = ligne.strip()

        # Ignorer lignes vides et commentaires.
        if not ligne or ligne.startswith("#"):
            continue

        if "=" not in ligne:
            continue

        cle, valeur = ligne.split("=", 1)
        cle = cle.strip()
        valeur = valeur.strip()

        # Retirer d'éventuels guillemets autour de la valeur.
        if (valeur.startswith('"') and valeur.endswith('"')) or (
            valeur.startswith("'") and valeur.endswith("'")
        ):
            valeur = valeur[1:-1]

        # N'écrase pas une variable déjà exportée.
        os.environ.setdefault(cle, valeur)


def lire_fichier_texte(path: Path) -> str:
    """
    Lit un fichier texte en UTF-8.
    En cas de problème d'encodage, tente une lecture en latin-1.
    """
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1")


def extraire_texte_reponse(reponse) -> str:
    """
    Extrait le texte d'une réponse Chat Completions.
    Gère les cas usuels :
    - content en string
    - content en liste d'objets structurés
    """
    if not hasattr(reponse, "choices") or not reponse.choices:
        return ""

    message = reponse.choices[0].message
    contenu = getattr(message, "content", "")

    # Cas standard : chaîne simple.
    if isinstance(contenu, str):
        return contenu.strip()

    # Cas structuré : liste de blocs.
    if isinstance(contenu, list):
        morceaux = []
        for bloc in contenu:
            # Selon SDK, le bloc peut être dict ou objet.
            if isinstance(bloc, dict):
                texte = bloc.get("text")
                if texte:
                    morceaux.append(str(texte))
            else:
                texte = getattr(bloc, "text", None)
                if texte:
                    morceaux.append(str(texte))
        return "\n".join(morceaux).strip()

    return ""


def main() -> int:
    # Détermination des chemins projet.
    script_path = Path(__file__).resolve()
    backend_dir = script_path.parent
    project_root = backend_dir.parent

    env_path = project_root / ".env"
    prompt_path = project_root / "prompts" / "system_prompt_principal.txt"
    sortie_path = project_root / "docs" / "premier_test_api.txt"

    # Chargement des variables depuis .env.
    charger_env_depuis_fichier(env_path)

    # Récupération de la config API.
    base_url = os.getenv("AFRI_BASE_URL")
    api_key = os.getenv("AFRI_API_KEY")
    model = "gpt-5.4"

    # Validation de la configuration minimale.
    if not base_url:
        print("❌ AFRI_BASE_URL introuvable dans .env ou variables d'environnement.")
        return 1

    if not api_key:
        print("❌ AFRI_API_KEY introuvable dans .env ou variables d'environnement.")
        return 1

    if not prompt_path.exists():
        print(f"❌ System prompt introuvable : {prompt_path}")
        return 1

    # Lecture du system prompt NutriCore.
    system_prompt = lire_fichier_texte(prompt_path).strip()
    if not system_prompt:
        print("❌ Le system prompt est vide.")
        return 1

    # Message de test demandé.
    message_test = (
        "J'ai du maïs, du tourteau de soja et de la farine de poisson. "
        "J'ai 50 poulets de chair de 3 semaines au Bénin."
    )

    # Initialisation du client API.
    client = OpenAI(
        api_key=api_key,
        base_url=base_url,
        timeout=90.0,  # Timeout global pour éviter un blocage trop long.
    )

    print("🚀 Lancement du test API Afri (GPT-5.4)...")
    print(f"🌐 Base URL : {base_url}")
    print(f"🤖 Modèle   : {model}")
    print("⏱️  Mesure du temps de réponse en cours...\n")

    debut = time.perf_counter()

    try:
        # Appel réel à l'API avec prompt système + message utilisateur.
        reponse = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message_test},
            ],
            temperature=0.2,
        )

    except AuthenticationError:
        # Erreur typique de clé invalide ou non autorisée.
        print("❌ Erreur d'authentification : clé API invalide ou non autorisée.")
        return 1

    except APITimeoutError:
        # Dépassement de délai.
        print("❌ Timeout : le délai de réponse API est dépassé.")
        return 1

    except APIConnectionError:
        # Problème réseau / internet / DNS / pare-feu.
        print("❌ Erreur de connexion : internet indisponible ou API inaccessible.")
        return 1

    except BadRequestError as exc:
        # Requête mal formée (paramètres non acceptés, modèle indisponible, etc.).
        print(f"❌ Requête invalide : {exc}")
        return 1

    except OpenAIError as exc:
        # Autres erreurs remontées par le SDK.
        print(f"❌ Erreur API : {exc}")
        return 1

    except Exception as exc:
        # Filet de sécurité pour toute exception non prévue.
        print(f"❌ Erreur inattendue : {exc}")
        return 1

    fin = time.perf_counter()
    duree = fin - debut

    # Extraction du texte final.
    texte_reponse = extraire_texte_reponse(reponse)

    if not texte_reponse:
        print("❌ Réponse vide reçue de l'API.")
        return 1

    # Affichage complet dans le terminal.
    print("✅ Réponse API reçue.\n")
    print("===== DÉBUT RÉPONSE COMPLÈTE =====")
    print(texte_reponse)
    print("===== FIN RÉPONSE COMPLÈTE =====\n")

    print(f"⏱️ Temps de réponse : {duree:.2f} secondes")

    # Sauvegarde de la réponse dans docs/premier_test_api.txt.
    try:
        sortie_path.parent.mkdir(parents=True, exist_ok=True)
        contenu_sortie = (
            "TEST API FEEDFORMULA AI — NUTRICORE\n"
            "===================================\n\n"
            f"Modèle: {model}\n"
            f"Base URL: {base_url}\n"
            f"Temps de réponse: {duree:.2f} secondes\n\n"
            "Message utilisateur:\n"
            f"{message_test}\n\n"
            "Réponse API:\n"
            "------------\n"
            f"{texte_reponse}\n"
        )
        sortie_path.write_text(contenu_sortie, encoding="utf-8")
        print(f"💾 Réponse sauvegardée dans : {sortie_path}")
    except Exception as exc:
        print(f"❌ Impossible de sauvegarder le fichier de sortie : {exc}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
