# -*- coding: utf-8 -*-
"""
Configuration centrale du backend FeedFormula AI.

Ce fichier :
1) charge les variables d'environnement (depuis le système + .env),
2) expose les constantes globales de l'application,
3) fournit des utilitaires robustes pour la langue, les prix marché et la gamification.

Notes de sécurité / fiabilité :
- Aucune clé API n'est hardcodée.
- Les fonctions gèrent les entrées vides ou invalides sans planter.
- Les valeurs sensibles restent dans les variables d'environnement.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional

# ---------------------------------------------------------------------------
# Chargement environnement
# ---------------------------------------------------------------------------

ROOT_DIR = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT_DIR / ".env"


def _read_env_file(path: Path) -> Dict[str, str]:
    """Lit un .env simple au format KEY=VALUE."""
    values: Dict[str, str] = {}
    if not path.exists():
        return values

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            values[key] = value
    return values


def _load_env() -> Dict[str, str]:
    """
    Fusionne os.environ + .env.
    Priorité à os.environ pour permettre les surcharges en production.
    """
    env_file_values = _read_env_file(ENV_PATH)
    merged = dict(env_file_values)
    merged.update(dict(os.environ))
    return merged


_ENV = _load_env()

# ---------------------------------------------------------------------------
# Helpers d'accès sécurisé aux variables
# ---------------------------------------------------------------------------


def _env_str(key: str, default: str = "") -> str:
    value = _ENV.get(key, default)
    if value is None:
        return default
    return str(value).strip()


def _env_int(key: str, default: int) -> int:
    value = _ENV.get(key)
    if value is None:
        return default
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def _env_bool(key: str, default: bool = False) -> bool:
    value = _ENV.get(key)
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "oui", "on"}


# ---------------------------------------------------------------------------
# Constantes application
# ---------------------------------------------------------------------------

APP_NAME = _env_str("APP_NAME", "FeedFormula AI")
APP_ENV = _env_str("APP_ENV", "development")
DEBUG = _env_bool("DEBUG", APP_ENV != "production")
API_VERSION = _env_str("API_VERSION", "v1")

HOST = _env_str("HOST", "0.0.0.0")
PORT = _env_int("PORT", 8000)

SECRET_KEY = _env_str("SECRET_KEY", "")
JWT_ALGORITHM = _env_str("JWT_ALGORITHM", "HS256")
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = _env_int("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", 30)
JWT_REFRESH_TOKEN_EXPIRE_DAYS = _env_int("JWT_REFRESH_TOKEN_EXPIRE_DAYS", 7)

DATABASE_URL = _env_str(
    "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/feedformula"
)
REDIS_URL = _env_str("REDIS_URL", "redis://localhost:6379/0")

AFRI_API_BASE_URL = _env_str("AFRI_API_BASE_URL", "https://build.lewisnote.com/v1")
AFRI_API_KEY = _env_str("AFRI_API_KEY", "")

# Modèles IA (surcharge possible via .env)
AFRI_MODEL_DEFAULT = _env_str("AFRI_MODEL_DEFAULT", "gpt-5.4")
AFRI_MODEL_AFRICAN = _env_str("AFRI_MODEL_AFRICAN", "gpt-5.4")
AFRI_MODEL_FALLBACK = _env_str("AFRI_MODEL_FALLBACK", "gpt-5.3-codex")

# Paramètres de sécurité/réseau
HTTP_TIMEOUT_SECONDS = _env_int("HTTP_TIMEOUT_SECONDS", 60)
MAX_UPLOAD_MB = _env_int("MAX_UPLOAD_MB", 15)

# ---------------------------------------------------------------------------
# Langues (socle utilitaire)
# ---------------------------------------------------------------------------

LANGUES_BENIN_PRIORITY_1 = {
    "fon",  # Fɔngbe
    "adja",
    "gux",  # Gen/Mina (souvent codé gux)
    "yor",  # Yoruba
    "yom",
    "bba",  # Baatonum (code souvent "bba")
    "ddn",  # Dendi (varie selon référentiel)
}

LANGUES_NON_AFRICAINES = {"fr", "en"}

# Ensemble élargi pour détection/logique produit
LANGUES_AFRICAINES_CONNNUES = {
    "fon",
    "adja",
    "gux",
    "yor",
    "yom",
    "bba",
    "ddn",
    "sw",
    "ha",
    "ig",
    "wo",
    "ln",
    "kg",
    "zu",
    "xh",
    "st",
    "tn",
    "ts",
    "ve",
    "rw",
    "rn",
    "lg",
    "ak",
    "ee",
    "tw",
    "ff",
    "bm",
    "sn",
    "ny",
    "mg",
    "so",
    "am",
    "ti",
    "om",
    "ar",
    "kab",
    "ber",
    "nso",
    "kik",
    "luo",
    "swh",
    "nyn",
    "kgp",
    "ss",
    "mos",
    "dyu",
    "lua",
    "tum",
    "kmb",
    "ses",
    "nqo",
    "yo",
}

# Synonymes / normalisation de code
LANGUE_CODE_ALIASES = {
    "fongbe": "fon",
    "fon": "fon",
    "yoruba": "yor",
    "yo": "yor",
    "gen": "gux",
    "mina": "gux",
    "francais": "fr",
    "français": "fr",
    "anglais": "en",
    "english": "en",
}


def _normalize_lang_code(code: Optional[str]) -> str:
    if not code:
        return "fr"
    c = str(code).strip().lower()
    return LANGUE_CODE_ALIASES.get(c, c)


def detect_langue(texte: Optional[str]) -> str:
    """
    Détection heuristique légère de langue à partir d'un texte.
    Retourne un code de langue court (ex: 'fon', 'yor', 'fr', 'en').

    Règles:
    - Entrée vide -> 'fr'
    - Score par mots-clés et caractères spécifiques
    - Fallback final -> 'fr'
    """
    if not texte:
        return "fr"

    text = str(texte).strip().lower()
    if not text:
        return "fr"

    # Heuristiques par caractère (diacritiques fréquents)
    # Yoruba: ẹ, ọ, ṣ ; Fon: ɔ, ɛ
    score = {"yor": 0, "fon": 0, "fr": 0, "en": 0}

    if re.search(r"[ẹọṣ]", text):
        score["yor"] += 4
    if re.search(r"[ɔɛ]", text):
        score["fon"] += 4

    tokens = re.findall(r"[a-zA-ZÀ-ÿɔɛẹọṣ']+", text)

    yor_words = {
        "bawo",
        "eko",
        "adie",
        "ounje",
        "omo",
        "ile",
        "ejo",
        "mi",
        "wa",
        "owo",
        "agbo",
        "eran",
        "omo-adie",
        "osi",
        "ojo",
    }
    fon_words = {
        "wɛ",
        "mi",
        "nɔ",
        "gbè",
        "xó",
        "ayi",
        "nu",
        "do",
        "kpɔ",
        "ɖe",
        "akukú",
        "agbaza",
        "vi",
        "xwe",
    }
    fr_words = {
        "bonjour",
        "ration",
        "poulet",
        "élevage",
        "santé",
        "prix",
        "marché",
        "protéine",
        "bonjour",
        "analyse",
        "ferme",
    }
    en_words = {
        "hello",
        "feed",
        "chicken",
        "farm",
        "health",
        "price",
        "market",
        "protein",
        "analysis",
        "nutrition",
    }

    for tok in tokens:
        t = tok.lower()
        if t in yor_words:
            score["yor"] += 2
        if t in fon_words:
            score["fon"] += 2
        if t in fr_words:
            score["fr"] += 2
        if t in en_words:
            score["en"] += 2

    # Si présence massive d'articles français
    if re.search(r"\b(le|la|les|des|une|un|du|de)\b", text):
        score["fr"] += 2
    if re.search(r"\b(the|and|is|are|for|with)\b", text):
        score["en"] += 2

    best_lang = max(score, key=score.get)
    if score[best_lang] <= 0:
        return "fr"
    return best_lang


def is_langue_africaine(code: Optional[str]) -> bool:
    """Retourne True si le code langue correspond à une langue africaine (hors fr/en)."""
    c = _normalize_lang_code(code)
    if c in LANGUES_NON_AFRICAINES:
        return False
    return c in LANGUES_AFRICAINES_CONNNUES or len(c) in {2, 3}


def get_model_for_langue(code: Optional[str]) -> str:
    """
    Sélectionne le modèle IA selon la langue.
    - Langues africaines: AFRI_MODEL_AFRICAN
    - Français/anglais: AFRI_MODEL_DEFAULT
    - Fallback robuste: AFRI_MODEL_FALLBACK
    """
    c = _normalize_lang_code(code)
    if is_langue_africaine(c):
        return AFRI_MODEL_AFRICAN or AFRI_MODEL_FALLBACK
    if c in {"fr", "en"}:
        return AFRI_MODEL_DEFAULT or AFRI_MODEL_FALLBACK
    return AFRI_MODEL_FALLBACK


# ---------------------------------------------------------------------------
# Prix marché (FCFA) - utilitaires
# ---------------------------------------------------------------------------

PRIX_MARCHE_DEFAULT_FCFA_KG: Dict[str, int] = {
    # Ingrédients majeurs Bénin / Afrique Ouest (valeurs de référence modifiables)
    "mais": 320,
    "maïs": 320,
    "son_riz": 210,
    "son_de_riz": 210,
    "tourteau_soja": 420,
    "tourteau_coton": 290,
    "tourteau_arachide": 340,
    "farine_poisson": 950,
    "coquille_huitre": 80,
    "coquille_oeuf": 70,
    "premix": 1800,
    "sel": 110,
    "manioc_cossette": 170,
    "sorgho": 280,
    "mil": 270,
    "drêche_biere": 160,
}

# Option de surcharge via variable JSON: PRIX_MARCHE_JSON='{"mais":330,...}'
_prix_override_raw = _env_str("PRIX_MARCHE_JSON", "")
if _prix_override_raw:
    try:
        parsed = json.loads(_prix_override_raw)
        if isinstance(parsed, dict):
            for k, v in parsed.items():
                try:
                    PRIX_MARCHE_DEFAULT_FCFA_KG[str(k).strip().lower()] = int(v)
                except (TypeError, ValueError):
                    # On ignore les entrées invalides sans casser l'application
                    pass
    except json.JSONDecodeError:
        # JSON invalide: on conserve la base par défaut
        pass


def _normalize_ingredient_name(name: Optional[str]) -> str:
    if not name:
        return ""
    n = str(name).strip().lower()
    n = n.replace("-", "_").replace(" ", "_")
    n = n.replace("é", "e").replace("è", "e").replace("ê", "e").replace("ë", "e")
    n = n.replace("à", "a").replace("â", "a")
    n = n.replace("î", "i").replace("ï", "i")
    n = n.replace("ô", "o").replace("ö", "o")
    n = n.replace("ù", "u").replace("û", "u").replace("ü", "u")
    n = n.replace("ç", "c")
    return n


def get_prix_marche(ingredient: Optional[str]) -> int:
    """
    Retourne le prix marché estimatif en FCFA/kg.
    - Si l'ingrédient est inconnu -> fallback contrôlé.
    - Ne lève pas d'exception.
    """
    key = _normalize_ingredient_name(ingredient)
    if not key:
        return 0

    if key in PRIX_MARCHE_DEFAULT_FCFA_KG:
        return PRIX_MARCHE_DEFAULT_FCFA_KG[key]

    # Tentative de matching partiel robuste
    for k, price in PRIX_MARCHE_DEFAULT_FCFA_KG.items():
        if key in k or k in key:
            return price

    # Fallback "matière standard"
    return _env_int("PRIX_MARCHE_FALLBACK_FCFA_KG", 250)


# ---------------------------------------------------------------------------
# Gamification - utilitaire points
# ---------------------------------------------------------------------------

POINTS_PAR_ACTION: Dict[str, int] = {
    # Actions transverses
    "connexion_quotidienne": 5,
    "profil_complete": 20,
    "invitation_validee": 25,
    # NutriCore
    "ration_generee": 15,
    "ration_appliquee": 20,
    "stock_mis_a_jour": 10,
    "prix_marche_enregistre": 12,
    # VetScan
    "cas_sante_declare": 18,
    "photo_sante_valide": 12,
    "suivi_24h_effectue": 20,
    # ReproTrack
    "repro_evenement": 15,
    "mise_bas_enregistree": 25,
    # FarmAcademy
    "lecon_terminee": 12,
    "quiz_reussi": 20,
    # Community
    "publication_utile": 10,
    "reponse_utile": 12,
}


def calculate_points(action: Optional[str]) -> int:
    """
    Calcule le nombre de points pour une action.
    Retourne 0 pour une action inconnue.
    """
    if not action:
        return 0
    a = _normalize_ingredient_name(action)  # même normaliseur (pratique)
    return int(POINTS_PAR_ACTION.get(a, 0))


# ---------------------------------------------------------------------------
# Validation minimale de configuration (facultative)
# ---------------------------------------------------------------------------


def validate_config() -> Dict[str, Any]:
    """
    Vérifie les paramètres essentiels et retourne un diagnostic simple.
    Ne lève pas d'exception pour éviter de bloquer le démarrage.
    """
    issues = []
    if not AFRI_API_KEY:
        issues.append("AFRI_API_KEY manquante")
    if not DATABASE_URL:
        issues.append("DATABASE_URL manquante")
    if not SECRET_KEY:
        issues.append("SECRET_KEY manquante")

    return {
        "ok": len(issues) == 0,
        "issues": issues,
        "env": APP_ENV,
        "debug": DEBUG,
        "api_base_url": AFRI_API_BASE_URL,
    }


__all__ = [
    "APP_NAME",
    "APP_ENV",
    "DEBUG",
    "API_VERSION",
    "HOST",
    "PORT",
    "SECRET_KEY",
    "JWT_ALGORITHM",
    "JWT_ACCESS_TOKEN_EXPIRE_MINUTES",
    "JWT_REFRESH_TOKEN_EXPIRE_DAYS",
    "DATABASE_URL",
    "REDIS_URL",
    "AFRI_API_BASE_URL",
    "AFRI_API_KEY",
    "AFRI_MODEL_DEFAULT",
    "AFRI_MODEL_AFRICAN",
    "AFRI_MODEL_FALLBACK",
    "HTTP_TIMEOUT_SECONDS",
    "MAX_UPLOAD_MB",
    "detect_langue",
    "is_langue_africaine",
    "get_model_for_langue",
    "get_prix_marche",
    "calculate_points",
    "validate_config",
]
