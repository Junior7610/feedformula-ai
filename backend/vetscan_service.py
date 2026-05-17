#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Service VetScan de FeedFormula AI.

Fonctions :
- analyse des symptômes par GPT 5.5 avec retour JSON strict
- analyse visuelle d'une photo d'animal
- fallback local prudent si l'API IA est indisponible
- routeur FastAPI prêt à intégrer dans `main.py`

Le service répond toujours dans la langue demandée par l'éleveur.
"""

from __future__ import annotations

import base64
import json
import os
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

# -----------------------------------------------------------------------------
# Imports locaux robustes
# -----------------------------------------------------------------------------
try:
    from database import (
        add_points_to_user,
        create_diagnostic_vetscan,
        get_db,
        get_user_by_id,
        list_user_diagnostics_vetscan,
        log_user_action,
        serialize_diagnostic_vetscan,
    )
except Exception:  # pragma: no cover
    try:
        from backend.database import (  # type: ignore
            add_points_to_user,
            create_diagnostic_vetscan,
            get_db,
            get_user_by_id,
            list_user_diagnostics_vetscan,
            log_user_action,
            serialize_diagnostic_vetscan,
        )
    except Exception:  # pragma: no cover
        add_points_to_user = None  # type: ignore
        create_diagnostic_vetscan = None  # type: ignore
        list_user_diagnostics_vetscan = None  # type: ignore
        log_user_action = None  # type: ignore
        serialize_diagnostic_vetscan = None  # type: ignore
        get_db = None  # type: ignore
        get_user_by_id = None  # type: ignore


try:
    from openai import (
        APIConnectionError,
        APITimeoutError,
        AuthenticationError,
        OpenAI,
        OpenAIError,
    )
except Exception:  # pragma: no cover
    OpenAI = None  # type: ignore
    APIConnectionError = Exception  # type: ignore
    APITimeoutError = Exception  # type: ignore
    AuthenticationError = Exception  # type: ignore
    OpenAIError = Exception  # type: ignore


# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
AFRI_BASE_URL = (
    os.getenv("AFRI_BASE_URL")
    or os.getenv("AFRI_API_BASE_URL")
    or "https://build.lewisnote.com/v1"
).strip()
AFRI_API_KEY = (os.getenv("AFRI_API_KEY") or "").strip()
AFRI_VETSCAN_MODEL = (os.getenv("AFRI_VETSCAN_MODEL") or "gpt-5.5").strip()
AFRI_VETSCAN_VISION_MODEL = (
    os.getenv("AFRI_VETSCAN_VISION_MODEL") or AFRI_VETSCAN_MODEL
).strip()

router = APIRouter(prefix="/vetscan", tags=["VetScan"])
PROMPT_PATH = (
    Path(__file__).resolve().parent.parent / "prompts" / "system_prompt_vetscan.txt"
)


def _load_prompt_fallback() -> str:
    try:
        if PROMPT_PATH.exists():
            return PROMPT_PATH.read_text(encoding="utf-8")
    except Exception:
        pass
    return (
        "Tu es un vétérinaire expert en pathologies animales tropicales africaines. "
        "Réponds en JSON strict et dans la langue de l'éleveur."
    )


# -----------------------------------------------------------------------------
# Schémas Pydantic
# -----------------------------------------------------------------------------
class VetScanDiagnoseRequest(BaseModel):
    """Données de diagnostic par symptômes."""

    espece: str = Field(..., min_length=2)
    symptomes: str = Field(..., min_length=3)
    langue: str = Field(default="fr", min_length=2)
    user_id: Optional[str] = Field(default=None)

    @field_validator("espece", "symptomes", "langue")
    @classmethod
    def _strip(cls, value: str) -> str:
        txt = (value or "").strip()
        if not txt:
            raise ValueError("Champ vide.")
        return txt


# -----------------------------------------------------------------------------
# Helpers internes
# -----------------------------------------------------------------------------
def _strip_accents(value: str) -> str:
    if not isinstance(value, str):
        return ""
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def _normalize_text(value: str) -> str:
    """Normalise un texte pour l'analyse."""
    if not isinstance(value, str):
        return ""
    txt = _strip_accents(value).lower()
    txt = re.sub(r"\s+", " ", txt)
    return txt.strip()


def _extract_json_object(raw: str) -> Optional[str]:
    """
    Tente d'extraire un bloc JSON depuis une réponse IA,
    même si elle est entourée de texte ou de balises Markdown.
    """
    if not isinstance(raw, str):
        return None

    candidate = raw.strip()
    if not candidate:
        return None

    # Enlève d'éventuels blocs ```json ... ```
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", candidate, flags=re.S)
    if fenced:
        return fenced.group(1)

    # Cherche le premier objet JSON équilibré approximativement.
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start != -1 and end != -1 and end > start:
        return candidate[start : end + 1]

    return None


def _json_or_none(raw: str) -> Optional[Dict[str, Any]]:
    """Tente de parser une réponse JSON."""
    try:
        extracted = _extract_json_object(raw) or raw
        data = json.loads(extracted)
        if isinstance(data, dict):
            return data
    except Exception:
        return None
    return None


def _build_openai_client() -> Optional[Any]:
    """
    Construit un client OpenAI compatible.
    Retourne None si l'environnement ne permet pas l'appel IA.
    """
    if OpenAI is None or not AFRI_API_KEY:
        return None
    try:
        return OpenAI(api_key=AFRI_API_KEY, base_url=AFRI_BASE_URL)
    except Exception:
        return None


def _default_protocol_for_species(espece: str) -> List[str]:
    """Retourne un protocole de premiers gestes prudent et exploitable terrain."""
    s = _normalize_text(espece)
    if "poulet" in s or "volaille" in s or "pintade" in s:
        return [
            "Isoler immédiatement les sujets atteints dans une cage propre et ventilée.",
            "Retirer les cadavres, les fientes très humides et les aliments souillés pour limiter la propagation.",
            "Fournir de l'eau propre avec électrolytes/vitamines si disponibles et un aliment facile à consommer.",
            "Désinfecter abreuvoirs, mangeoires et chaussures à l'entrée du poulailler.",
            "Noter le nombre de sujets malades/morts matin et soir ; appeler un vétérinaire si la mortalité augmente.",
        ]
    if "vache" in s or "bovin" in s or "zebu" in s:
        return [
            "Mettre l'animal à l'ombre, au calme, avec accès immédiat à de l'eau propre.",
            "Contrôler température, appétit, rumination, respiration, aspect du lait et état des muqueuses.",
            "Séparer l'animal si fièvre, diarrhée, écoulement, boiterie sévère ou suspicion contagieuse.",
            "Éviter tout traitement injectable sans avis vétérinaire ; préparer poids, âge et symptômes.",
            "Contacter un vétérinaire si fièvre, chute de lait, abattement marqué ou aggravation en 12 heures.",
        ]
    if "chevre" in s or "chèvre" in s or "mouton" in s:
        return [
            "Isoler l'animal et placer de l'eau propre, du fourrage sain et de la litière sèche.",
            "Observer selles, respiration, boiterie, appétit et couleur des paupières pour détecter anémie ou parasites.",
            "Nettoyer l'enclos et éviter le pâturage humide si diarrhée ou suspicion parasitaire.",
            "Noter le poids approximatif avant tout antiparasitaire afin d'éviter sous-dosage ou surdosage.",
            "Appeler un vétérinaire si l'animal ne se lève pas, respire mal, a du sang dans les selles ou avorte.",
        ]
    if "porc" in s:
        return [
            "Séparer l'animal malade et limiter strictement les déplacements entre cases.",
            "Vérifier température, respiration, appétit, couleur de peau et présence de taches rouges.",
            "Maintenir sol sec, eau propre et retirer les restes d'aliment fermenté.",
            "Désinfecter bottes, mains et matériel ; ne pas vendre ni déplacer les porcs suspects.",
            "En cas de forte fièvre ou mortalité rapide, alerter immédiatement les services vétérinaires.",
        ]
    if "tilapia" in s or "poisson" in s:
        return [
            "Réduire temporairement l'aliment si les poissons mangent peu.",
            "Vérifier oxygène, couleur/odeur de l'eau, mortalité en surface et fonctionnement de l'aération.",
            "Retirer rapidement les poissons morts et éviter de transférer l'eau ou les alevins vers d'autres bassins.",
            "Renouveler partiellement l'eau si elle sent mauvais ou devient très trouble.",
            "Contacter un spécialiste aquacole si mortalité répétée, nage anormale ou lésions visibles.",
        ]
    return [
        "Isoler l'animal dans un espace calme, ventilé et facile à nettoyer.",
        "Lui donner de l'eau propre, un aliment sain et noter précisément les symptômes observés.",
        "Surveiller l'évolution toutes les 6 à 12 heures et éviter les mélanges avec le reste du troupeau.",
        "Préparer âge, poids approximatif, alimentation récente et date de début des signes pour le vétérinaire.",
    ]


def _fallback_diagnostic(espece: str, symptomes: str, langue: str) -> Dict[str, Any]:
    """
    Fallback local lorsque l'IA n'est pas accessible.
    Retourne une structure conforme au contrat JSON demandé.
    """
    txt = _normalize_text(symptomes)

    urgence_keywords = [
        "sang",
        "respiration",
        "convulsion",
        "paralysie",
        "mort",
        "gonflement important",
        "choc",
        "abattu",
        "inconscient",
    ]
    warning_keywords = [
        "fièvre",
        "fievre",
        "diarrhée",
        "diarrhee",
        "toux",
        "boiter",
        "plaie",
        "perte d'appétit",
        "perte appetit",
        "déshydrat",
        "deshydrat",
        "abattu",
        "écoulement",
    ]

    urgence_score = sum(1 for kw in urgence_keywords if kw in txt)
    warning_score = sum(1 for kw in warning_keywords if kw in txt)
    urgent = urgence_score >= 1 or warning_score >= 4

    if urgent:
        diagnostics = [
            ("Infection sévère", 0.92, "Suspicion prioritaire avec risque vital."),
            (
                "Trouble respiratoire",
                0.74,
                "Signes compatibles avec une atteinte respiratoire.",
            ),
            (
                "Déshydratation aiguë",
                0.58,
                "État général possiblement compromis.",
            ),
        ]
    else:
        diagnostics = [
            (
                "Trouble digestif",
                0.86,
                "Hypothèse fréquente lorsque l'animal mange moins ou présente des selles anormales.",
            ),
            (
                "Stress thermique",
                0.64,
                "Possible si chaleur, halètement ou abattement.",
            ),
            (
                "Carence alimentaire",
                0.49,
                "À envisager si ration inadaptée ou croissance lente.",
            ),
        ]

    protocol = _default_protocol_for_species(espece)
    decision = "urgence" if urgent else "autonome"
    message = (
        "⚠️ URGENCE VÉTÉRINAIRE : contactez un vétérinaire immédiatement."
        if urgent
        else "Surveillance rapprochée et soins de base possibles à domicile."
    )

    symptomes_correspondants_1 = [
        s for s in ["fièvre", "abattement", "perte d'appétit", "diarrhée"] if s in txt
    ]
    symptomes_correspondants_2 = [
        s
        for s in ["toux", "respiration difficile", "halètement", "écoulement"]
        if s in txt
    ]
    symptomes_correspondants_3 = [
        s
        for s in ["boiterie", "déshydratation", "amaigrissement", "faiblesse"]
        if s in txt
    ]

    signes_urgence = [
        "respiration difficile",
        "sang dans les selles ou les sécrétions",
        "animal couché ou incapable de se lever",
        "mortalité rapide ou plusieurs animaux touchés",
        "fièvre élevée ou abattement marqué",
    ]
    conduite_terrain = [
        "Comparer les signes sur 2 ou 3 animaux avant de conclure.",
        "Noter l'heure d'apparition, les aliments distribués et les traitements déjà donnés.",
        "Prendre une photo nette des lésions ou fientes pour le vétérinaire.",
        "Ne pas mélanger les animaux suspects avec le lot sain.",
    ]

    return {
        "diagnostic_1": {
            "nom": diagnostics[0][0],
            "probabilite": diagnostics[0][1],
            "description": diagnostics[0][2],
            "symptomes_correspondants": symptomes_correspondants_1,
        },
        "diagnostic_2": {
            "nom": diagnostics[1][0],
            "probabilite": diagnostics[1][1],
            "description": diagnostics[1][2],
            "symptomes_correspondants": symptomes_correspondants_2,
        },
        "diagnostic_3": {
            "nom": diagnostics[2][0],
            "probabilite": diagnostics[2][1],
            "description": diagnostics[2][2],
            "symptomes_correspondants": symptomes_correspondants_3,
        },
        "protocole_soins": protocol,
        "decision": decision,
        "message_urgence": message if urgent else "",
        "prevention": (
            "Assurez une eau propre, une hygiène régulière, une alimentation équilibrée et surveillez les signes précoces."
            if not urgent
            else "Isolez les animaux malades, limitez les contacts et consultez rapidement pour éviter la propagation."
        ),
        "niveau_confiance": "élevé" if urgent else "modéré",
        "signes_urgence": signes_urgence,
        "conduite_terrain": conduite_terrain,
        "quand_appeler_veterinaire": (
            "Immédiatement : signes graves ou propagation rapide."
            if urgent
            else "Sous 24 à 48 h si les signes persistent, s'étendent ou si l'animal refuse de manger."
        ),
        "limites": "Analyse indicative : seul un vétérinaire peut confirmer le diagnostic et prescrire un traitement.",
        "langue": langue,
        "espece": espece,
        "mode": "fallback_local",
    }


def _system_prompt_vetscan() -> str:
    """System prompt spécialisé VetScan."""
    return _load_prompt_fallback()


def _format_user_prompt(espece: str, symptomes: str, langue: str) -> str:
    """Prépare le prompt utilisateur pour le modèle."""
    return (
        f"Espèce: {espece}\n"
        f"Symptômes: {symptomes}\n"
        f"Langue de réponse: {langue}\n\n"
        "Retourne un JSON strict avec 3 diagnostics différentiels classés par probabilité."
    )


def _normalize_ai_payload(
    payload: Dict[str, Any], espece: str, langue: str
) -> Dict[str, Any]:
    """Assure un format de sortie cohérent même si le modèle répond imparfaitement."""

    def _clean_diag(
        diag: Any, fallback_name: str, fallback_prob: float
    ) -> Dict[str, Any]:
        if not isinstance(diag, dict):
            diag = {}

        prob = diag.get(
            "probabilite", diag.get("probability", diag.get("score", fallback_prob))
        )
        try:
            prob = float(prob)
        except Exception:
            prob = fallback_prob

        syms = diag.get("symptomes_correspondants") or []
        if not isinstance(syms, list):
            syms = [str(syms)]

        return {
            "nom": str(diag.get("nom") or fallback_name),
            "probabilite": max(0.0, min(1.0, prob)),
            "description": str(diag.get("description") or ""),
            "symptomes_correspondants": [
                str(x).strip() for x in syms if str(x).strip()
            ],
        }

    protocol = payload.get("protocole_soins") or payload.get("protocol") or []
    if not isinstance(protocol, list):
        protocol = [str(protocol)]

    decision = str(payload.get("decision") or "autonome").strip().lower()
    if decision not in {"autonome", "urgence"}:
        decision = "autonome"

    return {
        "diagnostic_1": _clean_diag(
            payload.get("diagnostic_1"), "Diagnostic principal", 0.87
        ),
        "diagnostic_2": _clean_diag(
            payload.get("diagnostic_2"), "Diagnostic secondaire", 0.65
        ),
        "diagnostic_3": _clean_diag(
            payload.get("diagnostic_3"), "Diagnostic complémentaire", 0.45
        ),
        "protocole_soins": [str(x).strip() for x in protocol if str(x).strip()],
        "decision": decision,
        "message_urgence": str(payload.get("message_urgence") or ""),
        "prevention": str(payload.get("prevention") or ""),
        "langue": langue,
        "espece": espece,
        "mode": "ia",
    }


def _award_user_points(
    db: Optional[Session], user_id: Optional[str], points: int
) -> None:
    """
    Attribue des points au user si possible.
    Les erreurs sont volontairement silencieuses pour ne pas casser le diagnostic.
    """
    if not db or not user_id:
        return
    try:
        if get_user_by_id is not None and get_user_by_id(db, user_id) is None:
            return
        if add_points_to_user is not None:
            add_points_to_user(db, user_id, points)
        if log_user_action is not None:
            log_user_action(
                db,
                user_id,
                "vetscan_diagnostic",
                points_awarded=points,
                meta={"service": "vetscan"},
            )
    except Exception:
        # On n'interrompt jamais un diagnostic pour un problème de gamification.
        pass


def _save_diagnostic(
    db: Optional[Session],
    user_id: Optional[str],
    espece: str,
    symptomes: str,
    photo_path: Optional[str],
    result: Dict[str, Any],
    points: int,
) -> None:
    if not db or not user_id or create_diagnostic_vetscan is None:
        return
    try:
        diag1 = result.get("diagnostic_1") or {}
        diag2 = result.get("diagnostic_2") or {}
        diag3 = result.get("diagnostic_3") or {}
        create_diagnostic_vetscan(
            db=db,
            user_id=user_id,
            espece=espece,
            symptomes_decrits=symptomes,
            photo_path=photo_path,
            diagnostic_1=str(diag1.get("nom") or ""),
            score_1=float(diag1.get("probabilite") or 0.0),
            diagnostic_2=str(diag2.get("nom") or ""),
            score_2=float(diag2.get("probabilite") or 0.0),
            diagnostic_3=str(diag3.get("nom") or ""),
            score_3=float(diag3.get("probabilite") or 0.0),
            protocole_soins=result.get("protocole_soins") or [],
            decision_triage=str(result.get("decision") or "autonome"),
            points_gagnes=points,
        )
    except Exception:
        pass


# -----------------------------------------------------------------------------
# Service principal
# -----------------------------------------------------------------------------
@dataclass
class VetScanService:
    """Service métier VetScan."""

    def _client(self) -> Optional[Any]:
        """Retourne un client IA compatible ou None."""
        return _build_openai_client()

    async def analyser_symptomes(
        self, espece: str, symptomes: str, langue: str = "fr"
    ) -> Dict[str, Any]:
        """
        Analyse des symptômes à partir d'un texte.
        Retourne une structure de diagnostic différentiel.
        """
        espece = (espece or "").strip()
        symptomes = (symptomes or "").strip()
        langue = (langue or "fr").strip().lower()

        if not espece:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="L'espèce est obligatoire.",
            )
        if len(symptomes) < 3:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Les symptômes sont trop courts.",
            )

        client = self._client()
        if client is None:
            return _fallback_diagnostic(espece, symptomes, langue)

        try:
            messages = [
                {"role": "system", "content": _system_prompt_vetscan()},
                {
                    "role": "user",
                    "content": _format_user_prompt(espece, symptomes, langue),
                },
            ]

            response = client.chat.completions.create(
                model=AFRI_VETSCAN_MODEL,
                messages=messages,
                temperature=0.2,
                max_tokens=900,
            )

            content = ""
            try:
                content = response.choices[0].message.content or ""
            except Exception:
                content = ""

            payload = _json_or_none(content)
            if payload is None:
                return _fallback_diagnostic(espece, symptomes, langue)

            return _normalize_ai_payload(payload, espece, langue)

        except AuthenticationError:
            return _fallback_diagnostic(espece, symptomes, langue)
        except APITimeoutError:
            return _fallback_diagnostic(espece, symptomes, langue)
        except APIConnectionError:
            return _fallback_diagnostic(espece, symptomes, langue)
        except OpenAIError:
            return _fallback_diagnostic(espece, symptomes, langue)
        except Exception:
            return _fallback_diagnostic(espece, symptomes, langue)

    async def analyser_photo(
        self, image_bytes: bytes, espece: str, langue: str = "fr"
    ) -> Dict[str, Any]:
        """
        Analyse d'une photo d'animal.
        Retourne la même structure que l'analyse des symptômes.
        """
        espece = (espece or "").strip()
        langue = (langue or "fr").strip().lower()

        if not espece:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="L'espèce est obligatoire pour l'analyse photo.",
            )
        if not image_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Image vide ou absente.",
            )

        client = self._client()
        if client is None:
            # Fallback très prudent : on retourne un diagnostic générique.
            return _fallback_diagnostic(
                espece, "Photo fournie, analyse locale de secours.", langue
            )

        try:
            b64 = base64.b64encode(image_bytes).decode("utf-8")
            messages = [
                {"role": "system", "content": _system_prompt_vetscan()},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                f"Analyse visuellement cette photo d'un animal de type {espece}. "
                                f"Langue de réponse: {langue}. "
                                "Retourne le même JSON structuré que pour l'analyse par symptômes."
                            ),
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
                        },
                    ],
                },
            ]

            response = client.chat.completions.create(
                model=AFRI_VETSCAN_VISION_MODEL,
                messages=messages,
                temperature=0.2,
                max_tokens=900,
            )

            content = ""
            try:
                content = response.choices[0].message.content or ""
            except Exception:
                content = ""

            payload = _json_or_none(content)
            if payload is None:
                return _fallback_diagnostic(
                    espece, "Photo analysée, mais réponse IA non exploitable.", langue
                )

            return _normalize_ai_payload(payload, espece, langue)

        except AuthenticationError:
            return _fallback_diagnostic(
                espece, "Photo analysée en mode secours.", langue
            )
        except APITimeoutError:
            return _fallback_diagnostic(
                espece, "Photo analysée en mode secours.", langue
            )
        except APIConnectionError:
            return _fallback_diagnostic(
                espece, "Photo analysée en mode secours.", langue
            )
        except OpenAIError:
            return _fallback_diagnostic(
                espece, "Photo analysée en mode secours.", langue
            )
        except Exception:
            return _fallback_diagnostic(
                espece, "Photo analysée en mode secours.", langue
            )

    def trouver_veterinaire_proche(
        self, latitude: float, longitude: float
    ) -> List[Dict[str, Any]]:
        """
        Retourne une liste simulée de vétérinaires proches.
        En production, ceci devrait interroger une API de cartographie.
        """
        return [
            {
                "nom": "Clinique Vétérinaire Centrale",
                "distance_km": 1.2,
                "telephone": "+229 01 00 00 00 01",
                "latitude": latitude + 0.01,
                "longitude": longitude + 0.01,
            },
            {
                "nom": "Cabinet AgroVet",
                "distance_km": 3.6,
                "telephone": "+229 01 00 00 00 02",
                "latitude": latitude - 0.02,
                "longitude": longitude + 0.02,
            },
            {
                "nom": "Urgences Élevage Plus",
                "distance_km": 7.8,
                "telephone": "+229 01 00 00 00 03",
                "latitude": latitude + 0.03,
                "longitude": longitude - 0.03,
            },
        ]


# Instance partagée
vetscan_service = VetScanService()


# -----------------------------------------------------------------------------
# Endpoints FastAPI
# -----------------------------------------------------------------------------
@router.post("/diagnostiquer")
async def diagnostiquer(
    payload: VetScanDiagnoseRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Endpoint de diagnostic VetScan basé sur les symptômes."""
    result = await vetscan_service.analyser_symptomes(
        espece=payload.espece,
        symptomes=payload.symptomes,
        langue=payload.langue,
    )

    points = 20 if result.get("decision") == "urgence" else 15
    _award_user_points(db, payload.user_id, points)
    _save_diagnostic(
        db=db,
        user_id=payload.user_id,
        espece=payload.espece,
        symptomes=payload.symptomes,
        photo_path=None,
        result=result,
        points=points,
    )

    return {
        "message": "Diagnostic VetScan généré avec succès.",
        "points_gagnes": points,
        "resultat": result,
        # Champs de compatibilité/contrat au niveau racine
        "diagnostic_1": result.get("diagnostic_1"),
        "diagnostic_2": result.get("diagnostic_2"),
        "diagnostic_3": result.get("diagnostic_3"),
        "protocole_soins": result.get("protocole_soins"),
        "decision": result.get("decision"),
    }


@router.post("/analyser-photo")
async def analyser_photo_endpoint(
    image: UploadFile = File(...),
    espece: str = Form(...),
    langue: str = Form(default="fr"),
    user_id: Optional[str] = Form(default=None),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Endpoint d'analyse de photo VetScan.
    """
    if image is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Aucune image reçue."
        )

    contenu = await image.read()
    if not contenu:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Image vide ou invalide."
        )

    result = await vetscan_service.analyser_photo(
        image_bytes=contenu,
        espece=espece,
        langue=langue,
    )

    points = 20 if result.get("decision") == "urgence" else 15
    _award_user_points(db, user_id, points)
    _save_diagnostic(
        db=db,
        user_id=user_id,
        espece=espece,
        symptomes="photo analysée",
        photo_path=getattr(image, "filename", None),
        result=result,
        points=points,
    )

    return {
        "message": "Analyse photo VetScan générée avec succès.",
        "points_gagnes": points,
        "resultat": result,
        "diagnostic_1": result.get("diagnostic_1"),
        "diagnostic_2": result.get("diagnostic_2"),
        "diagnostic_3": result.get("diagnostic_3"),
        "protocole_soins": result.get("protocole_soins"),
        "decision": result.get("decision"),
    }


@router.get("/veterinaires-proches")
def veterinaires_proches(
    latitude: float,
    longitude: float,
) -> Dict[str, Any]:
    """Fournit une liste simulée de vétérinaires proches."""
    return {
        "latitude": latitude,
        "longitude": longitude,
        "veterinaires": vetscan_service.trouver_veterinaire_proche(latitude, longitude),
    }


@router.get("/veterinaires/{departement}")
def veterinaires_par_departement(departement: str) -> Dict[str, Any]:
    """Retourne une liste simulée de vétérinaires par département béninois."""
    dept = (departement or "").strip().lower()
    base = {
        "cotonou": [
            {
                "nom": "Clinique Vétérinaire du Littoral",
                "telephone": "+229 01 40 00 00 01",
                "ville": "Cotonou",
            },
            {
                "nom": "AgroVet Sud",
                "telephone": "+229 01 40 00 00 02",
                "ville": "Cotonou",
            },
            {
                "nom": "Cabinet Santé Animale",
                "telephone": "+229 01 40 00 00 03",
                "ville": "Cotonou",
            },
            {
                "nom": "Clinique des Éleveurs",
                "telephone": "+229 01 40 00 00 04",
                "ville": "Cotonou",
            },
            {
                "nom": "Urgences Animales Littoral",
                "telephone": "+229 01 40 00 00 05",
                "ville": "Cotonou",
            },
        ],
        "parakou": [
            {
                "nom": "Vet Nord Parakou",
                "telephone": "+229 01 50 00 00 01",
                "ville": "Parakou",
            },
            {
                "nom": "Cabinet Borgou Vet",
                "telephone": "+229 01 50 00 00 02",
                "ville": "Parakou",
            },
            {
                "nom": "Urgence Élevage Nord",
                "telephone": "+229 01 50 00 00 03",
                "ville": "Parakou",
            },
        ],
        "abomey-calavi": [
            {
                "nom": "Calavi Vet Center",
                "telephone": "+229 01 60 00 00 01",
                "ville": "Abomey-Calavi",
            },
            {
                "nom": "Santé Animale Calavi",
                "telephone": "+229 01 60 00 00 02",
                "ville": "Abomey-Calavi",
            },
        ],
    }
    items = base.get(dept)
    if not items:
        nice = departement.title() if departement else "Bénin"
        items = [
            {
                "nom": f"Service vétérinaire {nice}",
                "telephone": "+229 01 70 00 00 01",
                "ville": nice,
            },
            {
                "nom": f"Urgence élevage {nice}",
                "telephone": "+229 01 70 00 00 02",
                "ville": nice,
            },
        ]
    return {"departement": departement, "total": len(items), "veterinaires": items}


@router.get("/historique/{user_id}")
def historique(user_id: str, limit: int = 10) -> Dict[str, Any]:
    """Retourne les derniers diagnostics VetScan d'un utilisateur."""
    if (
        list_user_diagnostics_vetscan is None
        or serialize_diagnostic_vetscan is None
        or get_db is None
    ):
        return {"user_id": user_id, "total": 0, "diagnostics": []}
    db = next(get_db())
    try:
        rows = list_user_diagnostics_vetscan(db, user_id, limit=limit)
        return {
            "user_id": user_id,
            "total": len(rows),
            "diagnostics": [serialize_diagnostic_vetscan(row) for row in rows],
        }
    finally:
        try:
            db.close()
        except Exception:
            pass


__all__ = [
    "VetScanService",
    "vetscan_service",
    "router",
]
