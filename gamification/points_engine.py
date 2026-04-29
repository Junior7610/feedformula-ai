#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Moteur de gamification FeedFormula AI.

Ce module centralise :
- le calcul des points par action,
- la détermination des niveaux,
- la gestion des trophées,
- le calcul des séries de connexion,
- la vérification des défis quotidiens,
- la gestion des ligues,
- la boutique virtuelle des Graines d'Or.

Le tout est commenté en français pour faciliter la maintenance.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union


# =============================================================================
# Constantes officielles du système
# =============================================================================

ACTIONS_POINTS: Dict[str, int] = {
    "connexion_jour": 5,
    "serie_3_jours": 15,
    "serie_7_jours": 50,
    "serie_30_jours": 200,
    "generer_ration": 10,
    "generer_ration_langue_locale": 15,
    "telecharger_pdf": 5,
    "partager_whatsapp": 8,
    "utiliser_ration_3_jours": 20,
    "diagnostic_vetscan": 20,
    "photo_suivi_guerison": 15,
    "cas_resolu": 50,
    "enregistrer_saillie": 10,
    "alerte_mise_bas_reussie": 30,
    "velage_reussi_documente": 40,
    "enregistrement_vocal": 8,
    "rapport_mensuel": 25,
    "registre_30_jours": 100,
    "completer_lecon": 20,
    "quiz_100_pct": 30,
    "certification_complete": 150,
    "aider_eleveur": 25,
    "recevoir_5_utile": 40,
    "inviter_ami": 100,
}

# Alias de compatibilité avec le moteur déjà utilisé dans le backend.
ACTIONS_POINTS["generation_ration"] = ACTIONS_POINTS["generer_ration"]
ACTIONS_POINTS["generation_ration_equilibree"] = 35
ACTIONS_POINTS["generation_ration_economique"] = 30
ACTIONS_POINTS["scan_sante_vetscan"] = ACTIONS_POINTS["diagnostic_vetscan"]
ACTIONS_POINTS["suivi_reproduction"] = 20
ACTIONS_POINTS["analyse_paturage"] = 20
ACTIONS_POINTS["creation_evenement_farmmanager"] = 15
ACTIONS_POINTS["quiz_reussi_farmacademy"] = 18
ACTIONS_POINTS["publication_farmcommunity"] = 12
ACTIONS_POINTS["commentaire_utile_farmcommunity"] = 8
ACTIONS_POINTS["partage_conseil_valide"] = 22
ACTIONS_POINTS["ajout_animal"] = 10
ACTIONS_POINTS["ajout_lot"] = 12
ACTIONS_POINTS["ajout_prix_marche"] = 8
ACTIONS_POINTS["declaration_performance"] = 10
ACTIONS_POINTS["declaration_mortalite"] = 8
ACTIONS_POINTS["declaration_ponte"] = 10
ACTIONS_POINTS["declaration_lait"] = 10
ACTIONS_POINTS["invitation_ami"] = ACTIONS_POINTS["inviter_ami"]
ACTIONS_POINTS["profil_complet"] = 25
ACTIONS_POINTS["defi_quotidien_complete"] = 30
ACTIONS_POINTS["defi_hebdomadaire_complete"] = 70
ACTIONS_POINTS["feedback_produit"] = 10
ACTIONS_POINTS["signalement_fausse_info"] = 15
ACTIONS_POINTS["contribution_traduction_locale"] = 20

# 10 niveaux avec seuils exacts demandés.
NIVEAUX: List[Dict[str, Any]] = [
    {"niveau": 1, "nom": "Semence", "seuil_min": 0, "seuil_max": 100},
    {"niveau": 2, "nom": "Pousse", "seuil_min": 101, "seuil_max": 300},
    {"niveau": 3, "nom": "Tige", "seuil_min": 301, "seuil_max": 600},
    {"niveau": 4, "nom": "Floraison", "seuil_min": 601, "seuil_max": 1000},
    {"niveau": 5, "nom": "Feuille d Or", "seuil_min": 1001, "seuil_max": 2000},
    {"niveau": 6, "nom": "Recolte", "seuil_min": 2001, "seuil_max": 3500},
    {"niveau": 7, "nom": "Proprietaire", "seuil_min": 3501, "seuil_max": 5500},
    {"niveau": 8, "nom": "Maitre Eleveur", "seuil_min": 5501, "seuil_max": 8000},
    {"niveau": 9, "nom": "Champion", "seuil_min": 8001, "seuil_max": 12000},
    {"niveau": 10, "nom": "Legende Afrique", "seuil_min": 12001, "seuil_max": None},
]

# 8 ligues demandées.
LIGUES: List[Dict[str, Any]] = [
    {"code": "argile", "nom": "Argile", "min_points": 0, "max_points": 200, "icone": "🟤"},
    {"code": "herbe", "nom": "Herbe", "min_points": 201, "max_points": 500, "icone": "🌿"},
    {"code": "ble", "nom": "Ble", "min_points": 501, "max_points": 1000, "icone": "🌾"},
    {"code": "coton", "nom": "Coton", "min_points": 1001, "max_points": 2000, "icone": "🧶"},
    {"code": "bronze", "nom": "Bronze", "min_points": 2001, "max_points": 3500, "icone": "🥉"},
    {"code": "argent", "nom": "Argent", "min_points": 3501, "max_points": 6000, "icone": "🥈"},
    {"code": "or", "nom": "Or", "min_points": 6001, "max_points": 10000, "icone": "🥇"},
    {"code": "diamant", "nom": "Diamant", "min_points": 10001, "max_points": None, "icone": "💎"},
]

# 30 trophées complets avec conditions précises.
TROPHEES: List[Dict[str, Any]] = [
    {
        "code": "premier_pas",
        "nom": "Premier Pas",
        "description": "Créer le compte et faire sa première connexion.",
        "condition": {"type": "action_count", "action": "connexion_jour", "min": 1},
    },
    {
        "code": "profil_carre",
        "nom": "Profil Carré",
        "description": "Compléter les informations de profil.",
        "condition": {"type": "action_count", "action": "profil_complet", "min": 1},
    },
    {
        "code": "premiere_ration",
        "nom": "Ma Première Ration",
        "description": "Générer une ration valide.",
        "condition": {"type": "action_count", "action": "generer_ration", "min": 1},
    },
    {
        "code": "nutrition_active",
        "nom": "Nutrition Active",
        "description": "Générer 10 rations.",
        "condition": {"type": "action_count", "action": "generer_ration", "min": 10},
    },
    {
        "code": "nutrition_expert",
        "nom": "Nutrition Expert",
        "description": "Générer 100 rations.",
        "condition": {"type": "action_count", "action": "generer_ration", "min": 100},
    },
    {
        "code": "oeil_de_lynx",
        "nom": "Œil de Lynx",
        "description": "Lancer un diagnostic VetScan.",
        "condition": {"type": "action_count", "action": "diagnostic_vetscan", "min": 1},
    },
    {
        "code": "sentinelle_sante",
        "nom": "Sentinelle Santé",
        "description": "Réaliser 20 diagnostics VetScan.",
        "condition": {"type": "action_count", "action": "diagnostic_vetscan", "min": 20},
    },
    {
        "code": "suivi_serieux",
        "nom": "Suivi Sérieux",
        "description": "Valider 10 suivis de 24h.",
        "condition": {"type": "action_count", "action": "photo_suivi_guerison", "min": 10},
    },
    {
        "code": "repro_depart",
        "nom": "Repro Départ",
        "description": "Enregistrer un événement reproduction.",
        "condition": {"type": "action_count", "action": "enregistrer_saillie", "min": 1},
    },
    {
        "code": "repro_pro",
        "nom": "Repro Pro",
        "description": "Enregistrer 50 événements reproduction.",
        "condition": {"type": "action_count", "action": "enregistrer_saillie", "min": 50},
    },
    {
        "code": "cartographe_vert",
        "nom": "Cartographe Vert",
        "description": "Consulter la carte pâturage 15 fois.",
        "condition": {"type": "action_count", "action": "analyse_paturage", "min": 15},
    },
    {
        "code": "paturage_intelligent",
        "nom": "Pâturage Intelligent",
        "description": "Appliquer 20 recommandations terrain.",
        "condition": {"type": "action_count", "action": "analyse_paturage", "min": 20},
    },
    {
        "code": "comptable_rural",
        "nom": "Comptable Rural",
        "description": "Effectuer 30 opérations finance.",
        "condition": {"type": "action_count", "action": "rapport_mensuel", "min": 30},
    },
    {
        "code": "tresorier_ferme",
        "nom": "Trésorier Ferme",
        "description": "Effectuer 200 opérations finance.",
        "condition": {"type": "action_count", "action": "rapport_mensuel", "min": 200},
    },
    {
        "code": "eleve_motive",
        "nom": "Élève Motivé",
        "description": "Terminer 5 leçons FarmAcademy.",
        "condition": {"type": "action_count", "action": "completer_lecon", "min": 5},
    },
    {
        "code": "forme_pour_gagner",
        "nom": "Formé pour Gagner",
        "description": "Terminer 30 leçons FarmAcademy.",
        "condition": {"type": "action_count", "action": "completer_lecon", "min": 30},
    },
    {
        "code": "quiz_master",
        "nom": "Quiz Master",
        "description": "Réussir 20 quiz à 100%.",
        "condition": {"type": "action_count", "action": "quiz_100_pct", "min": 20},
    },
    {
        "code": "voix_locale",
        "nom": "Voix Locale",
        "description": "Utiliser 50 saisies vocales.",
        "condition": {"type": "action_count", "action": "enregistrement_vocal", "min": 50},
    },
    {
        "code": "multi_langue",
        "nom": "Multi-langue",
        "description": "Utiliser 3 langues différentes.",
        "condition": {"type": "langues_locales_distinctes", "min": 3},
    },
    {
        "code": "reporter_marche",
        "nom": "Reporter Marché",
        "description": "Ajouter 30 prix de marché.",
        "condition": {"type": "action_count", "action": "ajout_prix_marche", "min": 30},
    },
    {
        "code": "communaute_solide",
        "nom": "Communauté Solide",
        "description": "Publier 50 réponses utiles validées.",
        "condition": {"type": "action_count", "action": "recevoir_5_utile", "min": 5},
    },
    {
        "code": "mentor_local",
        "nom": "Mentor Local",
        "description": "Recevoir 10 réactions utiles.",
        "condition": {"type": "action_count", "action": "recevoir_5_utile", "min": 10},
    },
    {
        "code": "protecteur_sanitaire",
        "nom": "Protecteur Sanitaire",
        "description": "Faire 10 signalements corrects.",
        "condition": {"type": "action_count", "action": "signalement_fausse_info", "min": 10},
    },
    {
        "code": "inviteur",
        "nom": "Inviteur",
        "description": "Inviter 3 amis.",
        "condition": {"type": "action_count", "action": "inviter_ami", "min": 3},
    },
    {
        "code": "ambassadeur",
        "nom": "Ambassadeur",
        "description": "Inviter 15 amis.",
        "condition": {"type": "action_count", "action": "inviter_ami", "min": 15},
    },
    {
        "code": "serie_7",
        "nom": "Série 7",
        "description": "Maintenir 7 jours de connexion.",
        "condition": {"type": "serie_jours", "min": 7},
    },
    {
        "code": "serie_30",
        "nom": "Série 30",
        "description": "Maintenir 30 jours de connexion.",
        "condition": {"type": "serie_jours", "min": 30},
    },
    {
        "code": "serie_90",
        "nom": "Série 90",
        "description": "Maintenir 90 jours de connexion.",
        "condition": {"type": "serie_jours", "min": 90},
    },
    {
        "code": "resilience",
        "nom": "Résilience",
        "description": "Revenir après 14 jours d'absence.",
        "condition": {"type": "retour_apres_absence", "min_jours": 14},
    },
    {
        "code": "legende_feedformula",
        "nom": "Légende FeedFormula",
        "description": "Atteindre le niveau 10.",
        "condition": {"type": "niveau", "min": 10},
    },
]

# Catalogue boutique demandé.
BOUTIQUE_CATALOGUE: Dict[str, Dict[str, Any]] = {
    "semaine_standard": {
        "nom": "1 semaine Standard offerte",
        "prix_graines_or": 50,
        "description": "7 jours d'accès Standard",
    },
    "module_premium_24h": {
        "nom": "Module Premium 24h",
        "prix_graines_or": 30,
        "description": "Accès à tous les modules 24h",
    },
    "theme_or": {
        "nom": "Thème doré exclusif",
        "prix_graines_or": 80,
        "description": "Interface en couleurs dorées",
    },
    "badge_rare": {
        "nom": "Badge Champion Précoce",
        "prix_graines_or": 40,
        "description": "Badge exclusif de profil",
    },
    "protection_serie": {
        "nom": "Protection de série",
        "prix_graines_or": 20,
        "description": "+1 Graine de Secours",
    },
}

# Alias de compatibilité pour le backend déjà en place.
BOUTIQUE_CATALOGUE["boost_serie"] = BOUTIQUE_CATALOGUE["protection_serie"]


# =============================================================================
# Outils de date / normalisation
# =============================================================================

def _safe_int(value: Any, default: int = 0) -> int:
    """Convertit en entier avec fallback."""
    try:
        return int(value)
    except Exception:
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    """Convertit en float avec fallback."""
    try:
        return float(value)
    except Exception:
        return default


def _to_date(value: Union[str, date, datetime, None]) -> Optional[date]:
    """Convertit différentes entrées en date."""
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        txt = value.strip()
        if not txt:
            return None
        try:
            return datetime.fromisoformat(txt).date()
        except Exception:
            try:
                return datetime.strptime(txt, "%Y-%m-%d").date()
            except Exception:
                return None
    return None


def _jours_entre(a: Union[str, date, datetime, None], b: Union[str, date, datetime, None]) -> int:
    """Retourne le nombre de jours entre deux dates."""
    da = _to_date(a)
    db = _to_date(b)
    if da is None or db is None:
        return 0
    return abs((db - da).days)


# =============================================================================
# Classes de service
# =============================================================================

class GamificationEngine:
    """
    Moteur principal de gamification.
    """

    ACTIONS_POINTS = ACTIONS_POINTS
    NIVEAUX = NIVEAUX
    TROPHEES = TROPHEES
    LIGUES = LIGUES
    BOUTIQUE_CATALOGUE = BOUTIQUE_CATALOGUE

    def __init__(self) -> None:
        self._boutique_cache = dict(BOUTIQUE_CATALOGUE)

    # ---------------------------------------------------------------------
    # Points
    # ---------------------------------------------------------------------
    def calculer_points(self, action: str, contexte: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Calcule les points accordés pour une action donnée.

        Retour:
            {
              "action": "...",
              "points_base": 10,
              "bonus": 5,
              "points_totaux": 15,
              "details": {...}
            }
        """
        action_norm = (action or "").strip().lower()
        contexte = contexte or {}

        if not action_norm:
            raise ValueError("L'action ne peut pas être vide.")

        if action_norm not in self.ACTIONS_POINTS:
            # Tolérance: si l'action n'est pas connue, on donne un petit bonus.
            points_base = 5
        else:
            points_base = int(self.ACTIONS_POINTS[action_norm])

        bonus = 0

        # Bonus langue locale
        if contexte.get("langue_locale") is True or contexte.get("code_langue") in {"fon", "yor", "den", "sw", "ha", "ig", "fr"}:
            if action_norm in {"generer_ration", "generation_ration", "enregistrement_vocal"}:
                bonus += 5

        # Bonus de série
        serie = _safe_int(contexte.get("serie_actuelle", 0), 0)
        if serie >= 7:
            bonus += 5
        if serie >= 30:
            bonus += 15

        # Bonus de qualité
        if contexte.get("qualite") == "excellent":
            bonus += 5
        if contexte.get("qualite") == "parfait":
            bonus += 10

        # Bonus défi quotidien
        if contexte.get("defi_quotidien") is True:
            bonus += 5

        # Plafond raisonnable par action
        points_totaux = max(0, min(points_base + bonus, 250))

        return {
            "action": action_norm,
            "points_base": points_base,
            "bonus": bonus,
            "points_totaux": points_totaux,
            "details": {
                "langue_locale": bool(contexte.get("langue_locale")),
                "serie_actuelle": serie,
                "qualite": contexte.get("qualite"),
                "defi_quotidien": bool(contexte.get("defi_quotidien")),
            },
        }

    # ---------------------------------------------------------------------
    # Niveaux
    # ---------------------------------------------------------------------
    def determiner_niveau(self, points_total: int) -> Dict[str, Any]:
        """
        Détermine le niveau d'un utilisateur à partir de ses points totaux.
        """
        pts = max(0, _safe_int(points_total, 0))
        niveau = NIVEAUX[0]
        prochain = None

        for idx, n in enumerate(NIVEAUX):
            seuil_min = int(n["seuil_min"])
            seuil_max = n["seuil_max"]
            if pts >= seuil_min and (seuil_max is None or pts <= seuil_max):
                niveau = n
                prochain = NIVEAUX[idx + 1] if idx + 1 < len(NIVEAUX) else None
                break

        if prochain is None and pts >= NIVEAUX[-1]["seuil_min"]:
            niveau = NIVEAUX[-1]

        seuil_min = int(niveau["seuil_min"])
        seuil_max = niveau["seuil_max"]
        if seuil_max is None:
            progression = 100
            points_restant = 0
        else:
            span = max(1, int(seuil_max) - seuil_min)
            progression = int(max(0, min(100, ((pts - seuil_min) / span) * 100)))
            points_restant = max(0, int(seuil_max) - pts)

        return {
            "niveau": int(niveau["niveau"]),
            "nom": niveau["nom"],
            "seuil_min": seuil_min,
            "seuil_max": seuil_max,
            "progression_pct": progression,
            "points_restant_pour_niveau_suivant": points_restant,
            "prochain_niveau": prochain,
        }

    # Compatibilité avec le backend déjà branché
    def get_niveau(self, points_total: int) -> Dict[str, Any]:
        return self.determiner_niveau(points_total)

    # ---------------------------------------------------------------------
    # Ligues
    # ---------------------------------------------------------------------
    def get_ligue_actuelle(self, points_saison: int) -> Dict[str, Any]:
        """
        Retourne la ligue actuelle selon les points de saison.
        """
        pts = max(0, _safe_int(points_saison, 0))
        ligue = LIGUES[0]
        for item in LIGUES:
            min_pts = int(item["min_points"])
            max_pts = item["max_points"]
            if pts >= min_pts and (max_pts is None or pts <= max_pts):
                ligue = item
        return {
            "code": ligue["code"],
            "nom": ligue["nom"],
            "icone": ligue["icone"],
            "min_points": ligue["min_points"],
            "max_points": ligue["max_points"],
        }

    # Alias demandé par l'existant backend
    def determiner_ligue(self, points_total: int) -> Dict[str, Any]:
        ligue = self.get_ligue_actuelle(points_total)
        max_pts = ligue["max_points"]
        points_restant = 0 if max_pts is None else max(0, int(max_pts) - max(0, int(points_total)))
        return {
            "ligue_actuelle": ligue,
            "points_restant_pour_monter": points_restant,
        }

    # ---------------------------------------------------------------------
    # Séries
    # ---------------------------------------------------------------------
    def calculer_serie(
        self,
        derniere_connexion: Union[str, date, datetime, None],
        historique: Optional[List[Union[str, date, datetime]]] = None,
    ) -> Dict[str, Any]:
        """
        Calcule la série de connexion à partir de la dernière connexion et d'un historique.

        historique : liste de dates/ISO strings de connexions.
        """
        hist = historique or []
        dates_hist = []
        for item in hist:
            d = _to_date(item)
            if d is not None:
                dates_hist.append(d)
        dates_hist = sorted(set(dates_hist))

        today = date.today()
        last = _to_date(derniere_connexion)

        if last is None and dates_hist:
            last = dates_hist[-1]

        if last is None:
            return {
                "serie_actuelle": 0,
                "meilleure_serie": 0,
                "est_en_danger": False,
                "jours_depuis_derniere_connexion": None,
            }

        jours_depuis = (today - last).days

        # Série actuelle = nombre de jours consécutifs jusqu'à aujourd'hui
        serie_actuelle = 0
        curseur = today
        set_hist = set(dates_hist)
        while curseur in set_hist or curseur == last:
            serie_actuelle += 1
            curseur -= timedelta(days=1)
            if serie_actuelle > 365:
                break

        # Meilleure série = plus longue séquence consécutive dans l'historique
        meilleure = 0
        courant = 0
        precedent = None
        for d in dates_hist:
            if precedent is None or (d - precedent).days == 1:
                courant += 1
            elif d == precedent:
                pass
            else:
                meilleure = max(meilleure, courant)
                courant = 1
            precedent = d
        meilleure = max(meilleure, courant, serie_actuelle)

        est_en_danger = jours_depuis >= 1
        urgence = jours_depuis >= 7

        return {
            "serie_actuelle": serie_actuelle,
            "meilleure_serie": meilleure,
            "jours_depuis_derniere_connexion": jours_depuis,
            "est_en_danger": est_en_danger,
            "urgence_serie": urgence,
        }

    # ---------------------------------------------------------------------
    # Trophées
    # ---------------------------------------------------------------------
    def verifier_trophees(self, user_stats: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Vérifie les trophées débloqués pour un utilisateur.
        """
        stats = user_stats or {}
        deja = set(stats.get("trophees_deja_obtenus", []) or [])
        actions = stats.get("actions_count", {}) or {}

        points_total = _safe_int(stats.get("points_total", 0), 0)
        serie_actuelle = _safe_int(stats.get("serie_actuelle", 0), 0)
        langues = stats.get("langues_locales_utilisees", []) or []
        modules = stats.get("modules_utilises", []) or []
        especes = stats.get("especes_suivies", []) or []
        quiz_taux = _safe_float(stats.get("quiz_taux_reussite_pct", 0.0), 0.0)

        nouveaux: List[Dict[str, Any]] = []

        def _ajouter(trophee: Dict[str, Any]) -> None:
            if trophee["id"] not in deja and trophee["id"] not in {x["id"] for x in nouveaux}:
                nouveaux.append(trophee)

        for troph in self.TROPHEES:
            code = troph["code"]
            cond = troph["condition"]
            typ = cond.get("type")

            ok = False
            if typ == "points_total":
                ok = points_total >= _safe_int(cond.get("min", 0), 0)
            elif typ == "action_count":
                action = cond.get("action", "")
                ok = _safe_int(actions.get(action, 0), 0) >= _safe_int(cond.get("min", 0), 0)
            elif typ == "serie_jours":
                ok = serie_actuelle >= _safe_int(cond.get("min", 0), 0)
            elif typ == "langues_locales_distinctes":
                ok = len(set(langues)) >= _safe_int(cond.get("min", 0), 0)
            elif typ == "modules_distincts":
                ok = len(set(modules)) >= _safe_int(cond.get("min", 0), 0)
            elif typ == "especes_distinctes":
                ok = len(set(especes)) >= _safe_int(cond.get("min", 0), 0)
            elif typ == "ratio_succes":
                ok = quiz_taux >= _safe_float(cond.get("min", 0), 0.0)
            elif typ == "retour_apres_absence":
                jours_absence = _safe_int(stats.get("jours_depuis_derniere_connexion", 0), 0)
                ok = jours_absence >= _safe_int(cond.get("min_jours", 0), 0)
            elif typ == "niveau":
                ok = self.determiner_niveau(points_total)["niveau"] >= _safe_int(cond.get("min", 0), 0)

            if ok:
                _ajouter(
                    {
                        "id": code,
                        "nom": troph["nom"],
                        "description": troph["description"],
                        "condition": cond,
                    }
                )

        return nouveaux

    # ---------------------------------------------------------------------
    # Défis quotidiens
    # ---------------------------------------------------------------------
    def verifier_defis_quotidiens(self, actions_jour: Dict[str, int]) -> Dict[str, Any]:
        """
        Vérifie les défis quotidiens complétés.
        """
        actions = actions_jour or {}
        defi_connexion = actions.get("connexion_jour", 0) >= 1
        defi_ration = actions.get("generer_ration", 0) >= 1 or actions.get("generation_ration", 0) >= 1
        defi_formation = actions.get("completer_lecon", 0) >= 1 or actions.get("quiz_100_pct", 0) >= 1
        defi_repro = actions.get("enregistrer_saillie", 0) >= 1
        defi_sante = actions.get("diagnostic_vetscan", 0) >= 1 or actions.get("scan_sante_vetscan", 0) >= 1

        resultats = {
            "defi_connexion": defi_connexion,
            "defi_ration": defi_ration,
            "defi_formation": defi_formation,
            "defi_repro": defi_repro,
            "defi_sante": defi_sante,
        }
        nb = sum(1 for v in resultats.values() if v)
        return {
            "completed_count": nb,
            "defis": resultats,
            "points_bonus": nb * 10,
        }

    # ---------------------------------------------------------------------
    # Boutique / Graines d'Or
    # ---------------------------------------------------------------------
    def get_boutique_items(self) -> Dict[str, Dict[str, Any]]:
        """Retourne le catalogue de la boutique virtuelle."""
        return dict(self._boutique_cache)

    def depenser_graines_or(self, user: Any, montant: int, item: str) -> Dict[str, Any]:
        """
        Dépense des Graines d'Or pour un item donné.

        user peut être un objet ORM ou un dictionnaire avec les attributs attendus.
        """
        if user is None:
            raise ValueError("Utilisateur invalide.")

        prix = _safe_int(montant, 0)
        if prix <= 0:
            raise ValueError("Le montant doit être positif.")

        solde = _safe_int(getattr(user, "graines_or", None), _safe_int(user.get("graines_or", 0), 0) if isinstance(user, dict) else 0)
        if solde < prix:
            raise ValueError("Solde insuffisant en Graines d'Or.")

        nouveau_solde = solde - prix

        if isinstance(user, dict):
            user["graines_or"] = nouveau_solde
        else:
            setattr(user, "graines_or", nouveau_solde)

        # Récompenses accessoires selon l'item
        if item == "protection_serie":
            if isinstance(user, dict):
                user["graines_secours"] = _safe_int(user.get("graines_secours", 0), 0) + 1
            else:
                setattr(user, "graines_secours", _safe_int(getattr(user, "graines_secours", 0), 0) + 1)

        return {
            "ok": True,
            "item": item,
            "cout": prix,
            "solde_restant": nouveau_solde,
        }

    # ---------------------------------------------------------------------
    # Règles métier avancées
    # ---------------------------------------------------------------------
    def calculer_bonus_langue_locale(self, code_langue: str) -> int:
        """Retourne un bonus spécifique pour les langues locales."""
        code = (code_langue or "").strip().lower()
        if code in {"fon", "yor", "den", "sw", "ha", "ig"}:
            return 5
        return 0

    def calculer_bonus_contexte(self, contexte: Optional[Dict[str, Any]] = None) -> int:
        """Calcule un bonus additionnel basé sur le contexte d'utilisation."""
        contexte = contexte or {}
        bonus = 0
        if contexte.get("mode_offline"):
            bonus += 2
        if contexte.get("qualite") == "excellent":
            bonus += 5
        if contexte.get("premiere_action"):
            bonus += 3
        return bonus


# =============================================================================
# Fonctions utilitaires publiques
# =============================================================================

def obtenir_trophes_couleur() -> List[Dict[str, Any]]:
    """Retourne les trophées avec un indicateur coloré pour l'interface."""
    return [
        {
            **t,
            "couleur": "color" if i < 5 else "grise",
        }
        for i, t in enumerate(TROPHEES)
    ]


def obtenir_ligues() -> List[Dict[str, Any]]:
    """Retourne la liste des ligues configurées."""
    return list(LIGUES)


def obtenir_niveaux() -> List[Dict[str, Any]]:
    """Retourne la liste des niveaux configurés."""
    return list(NIVEAUX)


def obtenir_catalogue_boutique() -> Dict[str, Dict[str, Any]]:
    """Retourne le catalogue boutique."""
    return dict(BOUTIQUE_CATALOGUE)


__all__ = [
    "ACTIONS_POINTS",
    "NIVEAUX",
    "LIGUES",
    "TROPHEES",
    "BOUTIQUE_CATALOGUE",
    "GamificationEngine",
    "obtenir_trophes_couleur",
    "obtenir_ligues",
    "obtenir_niveaux",
    "obtenir_catalogue_boutique",
]
