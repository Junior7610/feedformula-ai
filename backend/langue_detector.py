# -*- coding: utf-8 -*-
"""
Module de détection de langue et d’adaptation des prompts/labels pour FeedFormula AI.

Ce module fournit trois fonctions principales :
1) detecter_langue(texte)
2) get_prompt_pour_langue(code_langue)
3) traduire_labels_interface(code_langue)

Objectif :
- Détecter rapidement la langue d’un message utilisateur (avec heuristiques simples).
- Adapter le prompt système selon la langue détectée.
- Fournir les labels de l’interface dans les langues ciblées.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Dict, List


# ---------------------------------------------------------------------------
# Configuration générale des langues
# ---------------------------------------------------------------------------

# Codes couverts :
# - Internationales : fr, en
# - Béninoises (7) : fon, adj, gej, yor, yom, bba, den
#
# Note :
# - "yo" est accepté comme alias de "yor"
# - "ddn" est accepté comme alias de "den"

LANGUES_BENINOISES = {"fon", "adj", "gej", "yor", "yom", "bba", "den"}
ALIASES_LANGUES = {
    "yo": "yor",
    "ddn": "den",
}


# ---------------------------------------------------------------------------
# Outils internes
# ---------------------------------------------------------------------------

def _normaliser_code_langue(code_langue: str) -> str:
    """
    Normalise un code langue :
    - minuscule
    - alias connus (yo->yor, ddn->den)
    """
    if not code_langue:
        return "fr"
    code = code_langue.strip().lower()
    return ALIASES_LANGUES.get(code, code)


def _strip_accents(texte: str) -> str:
    """
    Supprime les accents pour faciliter les comparaisons lexicales.
    """
    normalized = unicodedata.normalize("NFD", texte)
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")


def _tokeniser(texte: str) -> List[str]:
    """
    Transforme un texte en liste de tokens alphanumériques simples.
    """
    return re.findall(r"[a-zA-ZÀ-ÿɖɔɛẹọṣùúìíàáç'-]+", texte.lower())


def _charger_prompt_principal() -> str:
    """
    Charge le prompt principal NutriCore depuis prompts/system_prompt_principal.txt.
    Retourne une chaîne vide si le fichier est introuvable.
    """
    # backend/langue_detector.py -> racine projet = parent.parent
    root = Path(__file__).resolve().parent.parent
    path_prompt = root / "prompts" / "system_prompt_principal.txt"

    try:
        return path_prompt.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return ""
    except UnicodeDecodeError:
        # Fallback tolérant si le fichier a été sauvegardé dans un autre encodage.
        try:
            return path_prompt.read_text(encoding="latin-1").strip()
        except Exception:
            return ""
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# 1) Détection de langue
# ---------------------------------------------------------------------------

def detecter_langue(texte: str) -> str:
    """
    Détecte la langue probable d'un texte.

    Logique :
    - Heuristiques par mots-clés et caractères caractéristiques.
    - Score par langue.
    - Retour du code ISO le plus probable.
    - Fallback : "fr"

    Langues prises en charge explicitement ici :
    fr, en, fon, yor, den, adj, gej, yom, bba
    """
    if not texte or not texte.strip():
        return "fr"

    texte_brut = texte.lower()
    texte_sans_accents = _strip_accents(texte_brut)
    tokens = _tokeniser(texte_brut)
    tokens_sans_accents = {_strip_accents(t) for t in tokens}

    # Scores initiaux
    scores: Dict[str, int] = {
        "fr": 0,
        "en": 0,
        "fon": 0,
        "yor": 0,
        "den": 0,
        "adj": 0,
        "gej": 0,
        "yom": 0,
        "bba": 0,
    }

    # --- Mots-clés (heuristiques terrain) ---
    keywords = {
        "fr": {
            "j'ai", "mais", "tourteau", "farine", "poulets", "pondeuses",
            "ration", "stade", "benin", "coût", "cout", "bonjour", "salut",
            "vache", "mouton", "chevre", "tilapia",
        },
        "en": {
            "i", "have", "corn", "soybean", "fish", "meal", "broiler", "layers",
            "ration", "feed", "what", "optimal", "cost", "hello", "please",
        },
        "fon": {
            "un", "nɔ", "xwe", "xwé", "nyi", "nyí", "kpo", "ɖo", "ɖé",
            "jɛji", "agbado", "soja", "jɔkpo", "jɔkpɔ", "e", "lɛ",
        },
        "yor": {
            "mo", "ni", "ati", "adie", "ose", "ọsẹ", "ẹja", "iyẹfun", "agbado",
            "soybean", "jowo", "jọwọ", "ejo", "ẹ jọ̀ọ́", "bawo",
        },
        "den": {
            "dendi", "den", "koyra", "mate", "fofo", "bani", "ga",
        },
        "adj": {
            "adja", "adjagbe", "adjàgbè", "mè", "wɛ", "kpɔ",
        },
        "gej": {
            "gen", "mina", "ewe", "agbe", "ŋutifafa", "wòe",
        },
        "yom": {
            "yom", "pila", "nateni", "taneka",
        },
        "bba": {
            "baatonum", "bariba", "sinaboko", "baani",
        },
    }

    # Comptage par mots-clés
    for code, mots in keywords.items():
        for mot in mots:
            mot_norm = _strip_accents(mot.lower())
            if mot_norm in tokens_sans_accents:
                scores[code] += 3
            # Bonus si motif présent tel quel dans la phrase
            if mot.lower() in texte_brut:
                scores[code] += 1

    # --- Signaux orthographiques spécifiques ---
    # Yoruba : présence fréquente de caractères diacrités spécifiques.
    if any(ch in texte_brut for ch in ("ẹ", "ọ", "ṣ", "ń", "à", "ì", "ù", "á", "í", "ú")):
        scores["yor"] += 3

    # Fon : caractères africains/phonétiques souvent rencontrés dans les exemples.
    if any(ch in texte_brut for ch in ("ɖ", "ɔ", "ɛ", "ʋ")):
        scores["fon"] += 4

    # Français : apostrophes et formes courantes.
    if "j'" in texte_brut or " l'" in texte_brut:
        scores["fr"] += 1

    # Anglais : structure de base très fréquente.
    if " i have " in f" {texte_sans_accents} ":
        scores["en"] += 2

    # Décision finale
    code_gagnant = max(scores, key=scores.get)
    meilleur_score = scores[code_gagnant]

    # Si incertain, fallback français.
    if meilleur_score <= 1:
        return "fr"

    return code_gagnant


# ---------------------------------------------------------------------------
# 2) Prompt adapté à la langue
# ---------------------------------------------------------------------------

def get_prompt_pour_langue(code_langue: str) -> str:
    """
    Retourne le system prompt adapté à la langue.

    Règles :
    - Si langue africaine (béninoise ici) -> prompt principal + instructions
      supplémentaires orientées langue locale.
    - Sinon -> prompt principal standard.
    - Si prompt principal introuvable -> fallback minimal.
    """
    code = _normaliser_code_langue(code_langue)
    prompt_principal = _charger_prompt_principal()

    if not prompt_principal:
        prompt_principal = (
            "SYSTÈME FEEDFORMULA AI\n"
            "Réponds dans la langue de l'utilisateur, avec clarté et sécurité.\n"
        )

    if code in LANGUES_BENINOISES:
        complement_local = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ANNEXE LANGUE LOCALE ({code})
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- Réponds prioritairement dans la langue locale détectée ({code}).
- Garde un style très simple et oral, adapté aux éleveurs.
- Si une notion technique est difficile à traduire, ajoute une reformulation courte en français simple.
- Utilise des exemples locaux (Bénin / Afrique de l’Ouest).
- Conserve les unités universelles : kg, g, %, FCFA, L.
"""
        return f"{prompt_principal}\n\n{complement_local}".strip()

    # Langues internationales (fr, en, autres) : prompt standard
    return prompt_principal


# ---------------------------------------------------------------------------
# 3) Labels d'interface multilingues
# ---------------------------------------------------------------------------

def traduire_labels_interface(code_langue: str) -> Dict[str, str]:
    """
    Retourne un dictionnaire de labels d'interface traduits dans la langue demandée.

    Couverture minimale :
    - 7 langues béninoises : fon, adj, gej, yor, yom, bba, den
    - + fr, en

    Si la langue n'est pas couverte, fallback en français.
    """
    code = _normaliser_code_langue(code_langue)

    # Clés UI standardisées
    base_keys = [
        "generer_ration",
        "mes_animaux",
        "accueil",
        "modules",
        "classement",
        "profil",
        "demarrer",
        "sauvegarder",
        "micro",
        "langue",
        "objectif",
        "stade",
        "espece",
        "cout_estime",
        "recommandations",
        "hors_ligne",
    ]

    labels = {
        "fr": {
            "generer_ration": "Générer ma ration",
            "mes_animaux": "Mes animaux",
            "accueil": "Accueil",
            "modules": "Modules",
            "classement": "Classement",
            "profil": "Profil",
            "demarrer": "Démarrer",
            "sauvegarder": "Sauvegarder",
            "micro": "Parler",
            "langue": "Langue",
            "objectif": "Objectif",
            "stade": "Stade",
            "espece": "Espèce",
            "cout_estime": "Coût estimé",
            "recommandations": "Recommandations",
            "hors_ligne": "Mode hors ligne",
        },
        "en": {
            "generer_ration": "Generate my ration",
            "mes_animaux": "My animals",
            "accueil": "Home",
            "modules": "Modules",
            "classement": "Leaderboard",
            "profil": "Profile",
            "demarrer": "Start",
            "sauvegarder": "Save",
            "micro": "Speak",
            "langue": "Language",
            "objectif": "Goal",
            "stade": "Stage",
            "espece": "Species",
            "cout_estime": "Estimated cost",
            "recommandations": "Recommendations",
            "hors_ligne": "Offline mode",
        },
        # Les traductions locales ci-dessous sont orientées interface pratique.
        # Elles peuvent être ajustées avec des linguistes natifs pour production.
        "fon": {
            "generer_ration": "Wɔ́nnu ration nyɛ",
            "mes_animaux": "Lánmɛ̀ xwé tɔ́n",
            "accueil": "Xwé",
            "modules": "Modules",
            "classement": "Classement",
            "profil": "Profil",
            "demarrer": "Sɔ̀ gbe",
            "sauvegarder": "Hwlɛ́",
            "micro": "Gblɔ",
            "langue": "Gbe",
            "objectif": "Núkùn",
            "stade": "Stade",
            "espece": "Lánmɛ̀ si",
            "cout_estime": "Kɔ́stù estimé",
            "recommandations": "Aɖaŋlɔnnu",
            "hors_ligne": "Sans réseau",
        },
        "yor": {
            "generer_ration": "Ṣe ration mi",
            "mes_animaux": "Àwọn ẹranko mi",
            "accueil": "Ilé",
            "modules": "Àwọn module",
            "classement": "Ìpele",
            "profil": "Profaili",
            "demarrer": "Bẹ̀rẹ̀",
            "sauvegarder": "Fipamọ́",
            "micro": "Sọ",
            "langue": "Èdè",
            "objectif": "Àfojúsùn",
            "stade": "Ìpele",
            "espece": "Ẹ̀yà",
            "cout_estime": "Iye owó àfojúsùn",
            "recommandations": "Ìmọ̀ràn",
            "hors_ligne": "Láìsí intanẹẹti",
        },
        "den": {
            "generer_ration": "N'ga ration",
            "mes_animaux": "Ayii koy",
            "accueil": "Ganda",
            "modules": "Modules",
            "classement": "Classement",
            "profil": "Profil",
            "demarrer": "Sintin",
            "sauvegarder": "Gaabu",
            "micro": "Maa fɔ",
            "langue": "Sanni",
            "objectif": "Buto",
            "stade": "Stade",
            "espece": "Iri",
            "cout_estime": "Kûtu estimé",
            "recommandations": "Shawara",
            "hors_ligne": "Réseau sii",
        },
        "adj": {
            "generer_ration": "Wɔ ration nye",
            "mes_animaux": "Lé xwla nye",
            "accueil": "Xwe",
            "modules": "Modules",
            "classement": "Classement",
            "profil": "Profil",
            "demarrer": "Dɔ",
            "sauvegarder": "Hwlɛ",
            "micro": "Gblɔ",
            "langue": "Gbe",
            "objectif": "Núkú",
            "stade": "Stade",
            "espece": "Xwla si",
            "cout_estime": "Kɔstù estimé",
            "recommandations": "Nufiafia",
            "hors_ligne": "Sans réseau",
        },
        "gej": {
            "generer_ration": "Wo ration",
            "mes_animaux": "Nye nyiwo",
            "accueil": "Aƒe",
            "modules": "Modules",
            "classement": "Classement",
            "profil": "Profil",
            "demarrer": "Dze egɔme",
            "sauvegarder": "Dzra ɖo",
            "micro": "Gblɔ",
            "langue": "Gbe",
            "objectif": "Tadede",
            "stade": "Stade",
            "espece": "Nyi ƒomevi",
            "cout_estime": "Xexeme estimé",
            "recommandations": "Aɖaŋuɖoɖo",
            "hors_ligne": "Sans réseau",
        },
        "yom": {
            "generer_ration": "Tii ration ma",
            "mes_animaux": "Mii yina",
            "accueil": "Ka",
            "modules": "Modules",
            "classement": "Classement",
            "profil": "Profil",
            "demarrer": "Pili",
            "sauvegarder": "Kpaka",
            "micro": "Paa",
            "langue": "Gbe",
            "objectif": "N'yiri",
            "stade": "Stade",
            "espece": "Yina iri",
            "cout_estime": "Kɔsiti estimé",
            "recommandations": "N'yiru",
            "hors_ligne": "Sans réseau",
        },
        "bba": {
            "generer_ration": "Sɛ ration n mi",
            "mes_animaux": "Sɔn n mi",
            "accueil": "Gɔru",
            "modules": "Modules",
            "classement": "Classement",
            "profil": "Profil",
            "demarrer": "Sira",
            "sauvegarder": "Dii",
            "micro": "Sɔ̀nɔ",
            "langue": "Gbe",
            "objectif": "Kpan",
            "stade": "Stade",
            "espece": "Sɔn su",
            "cout_estime": "Kɔsiti estimé",
            "recommandations": "Bɛɛri",
            "hors_ligne": "Sans réseau",
        },
    }

    # Résolution de la langue (fallback fr)
    if code not in labels:
        code = "fr"

    # Sécurise les clés manquantes en reprenant la valeur française.
    fr_ref = labels["fr"]
    selected = labels[code].copy()
    for k in base_keys:
        selected.setdefault(k, fr_ref[k])

    return selected


__all__ = [
    "detecter_langue",
    "get_prompt_pour_langue",
    "traduire_labels_interface",
]
