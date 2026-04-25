#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Moteur de gamification FeedFormula AI.

Ce module gère :
- le calcul des points par action,
- la détermination du niveau utilisateur,
- la vérification des trophées,
- le calcul des séries de connexion (streak),
- la vérification des défis quotidiens.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union


class GamificationEngine:
    """
    Moteur principal de gamification.
    Toutes les règles sont centralisées ici pour faciliter la maintenance.
    """

    # Dictionnaire des actions et des points de base.
    ACTIONS_POINTS: Dict[str, int] = {
        "connexion_jour": 10,
        "generation_ration": 25,
        "generation_ration_equilibree": 35,
        "generation_ration_economique": 30,
        "scan_sante_vetscan": 30,
        "suivi_reproduction": 20,
        "analyse_paturage": 20,
        "creation_evenement_farmmanager": 15,
        "quiz_reussi_farmacademy": 18,
        "publication_farmcommunity": 12,
        "commentaire_utile_farmcommunity": 8,
        "partage_conseil_valide": 22,
        "ajout_animal": 10,
        "ajout_lot": 12,
        "ajout_prix_marche": 8,
        "declaration_performance": 10,
        "declaration_mortalite": 8,
        "declaration_ponte": 10,
        "declaration_lait": 10,
        "invitation_ami": 20,
        "profil_complet": 25,
        "defi_quotidien_complete": 30,
        "defi_hebdomadaire_complete": 70,
        "feedback_produit": 10,
        "signalement_fausse_info": 15,
        "contribution_traduction_locale": 20,
    }

    # Liste des 10 niveaux (seuil minimum inclusif).
    NIVEAUX: List[Dict[str, Any]] = [
        {"niveau": 1, "nom": "Graine", "seuil_points": 0},
        {"niveau": 2, "nom": "Jeune pousse", "seuil_points": 150},
        {"niveau": 3, "nom": "Cultivateur", "seuil_points": 350},
        {"niveau": 4, "nom": "Éleveur actif", "seuil_points": 700},
        {"niveau": 5, "nom": "Éleveur confirmé", "seuil_points": 1200},
        {"niveau": 6, "nom": "Maître ration", "seuil_points": 1900},
        {"niveau": 7, "nom": "Sentinelle santé", "seuil_points": 2800},
        {"niveau": 8, "nom": "Leader local", "seuil_points": 4000},
        {"niveau": 9, "nom": "Champion FeedFormula", "seuil_points": 5500},
        {"niveau": 10, "nom": "Légende Aya", "seuil_points": 7500},
    ]

    # Liste de 30 trophées avec conditions.
    # Types de condition supportés:
    # - points_total
    # - action_count
    # - serie_jours
    # - langues_locales_distinctes
    # - modules_distincts
    # - especes_distinctes
    # - ratio_succes
    TROPHEES: List[Dict[str, Any]] = [
        # 1-5: onboarding
        {
            "id": "t01_bienvenue",
            "nom": "Bienvenue à la ferme",
            "description": "Effectuer la première connexion.",
            "condition": {"type": "action_count", "action": "connexion_jour", "min": 1},
        },
        {
            "id": "t02_premier_animal",
            "nom": "Premier troupeau",
            "description": "Ajouter au moins 1 animal.",
            "condition": {"type": "action_count", "action": "ajout_animal", "min": 1},
        },
        {
            "id": "t03_profil_propre",
            "nom": "Profil propre",
            "description": "Compléter le profil utilisateur.",
            "condition": {"type": "action_count", "action": "profil_complet", "min": 1},
        },
        {
            "id": "t04_premiere_ration",
            "nom": "Première ration",
            "description": "Générer une première ration.",
            "condition": {"type": "action_count", "action": "generation_ration", "min": 1},
        },
        {
            "id": "t05_feedback_citoyen",
            "nom": "Voix de terrain",
            "description": "Envoyer un feedback produit.",
            "condition": {"type": "action_count", "action": "feedback_produit", "min": 1},
        },
        # 6-12: activité ration
        {
            "id": "t06_ration_10",
            "nom": "Rationneur régulier",
            "description": "Générer 10 rations.",
            "condition": {"type": "action_count", "action": "generation_ration", "min": 10},
        },
        {
            "id": "t07_ration_50",
            "nom": "Architecte de rations",
            "description": "Générer 50 rations.",
            "condition": {"type": "action_count", "action": "generation_ration", "min": 50},
        },
        {
            "id": "t08_ration_equilibree_10",
            "nom": "Équilibre maîtrisé",
            "description": "Générer 10 rations équilibrées.",
            "condition": {
                "type": "action_count",
                "action": "generation_ration_equilibree",
                "min": 10,
            },
        },
        {
            "id": "t09_ration_eco_10",
            "nom": "Éleveur économe",
            "description": "Générer 10 rations économiques.",
            "condition": {
                "type": "action_count",
                "action": "generation_ration_economique",
                "min": 10,
            },
        },
        {
            "id": "t10_prix_marche_25",
            "nom": "Radar marché",
            "description": "Ajouter 25 prix de marché.",
            "condition": {"type": "action_count", "action": "ajout_prix_marche", "min": 25},
        },
        {
            "id": "t11_multi_especes",
            "nom": "Poly-éleveur",
            "description": "Suivre au moins 4 espèces différentes.",
            "condition": {"type": "especes_distinctes", "min": 4},
        },
        {
            "id": "t12_donnees_terrain_50",
            "nom": "Data fermier",
            "description": "Soumettre 50 événements terrain.",
            "condition": {
                "type": "action_count",
                "action": "creation_evenement_farmmanager",
                "min": 50,
            },
        },
        # 13-18: santé/repro/pasture
        {
            "id": "t13_sentinelle_sante",
            "nom": "Sentinelle santé",
            "description": "Faire 15 scans VetScan.",
            "condition": {"type": "action_count", "action": "scan_sante_vetscan", "min": 15},
        },
        {
            "id": "t14_repro_strategique",
            "nom": "Stratège reproduction",
            "description": "Réaliser 20 suivis ReproTrack.",
            "condition": {"type": "action_count", "action": "suivi_reproduction", "min": 20},
        },
        {
            "id": "t15_paturage_sage",
            "nom": "Gardien des pâturages",
            "description": "Réaliser 20 analyses PastureMap.",
            "condition": {"type": "action_count", "action": "analyse_paturage", "min": 20},
        },
        {
            "id": "t16_signalement_utile",
            "nom": "Vigilant communautaire",
            "description": "Signaler 5 fausses informations utiles.",
            "condition": {"type": "action_count", "action": "signalement_fausse_info", "min": 5},
        },
        {
            "id": "t17_langue_locale_1",
            "nom": "Fierté locale",
            "description": "Utiliser au moins 1 langue locale.",
            "condition": {"type": "langues_locales_distinctes", "min": 1},
        },
        {
            "id": "t18_langue_locale_3",
            "nom": "Pont des langues",
            "description": "Utiliser au moins 3 langues locales.",
            "condition": {"type": "langues_locales_distinctes", "min": 3},
        },
        # 19-24: séries
        {
            "id": "t19_serie_3",
            "nom": "Présence continue",
            "description": "Atteindre une série de 3 jours.",
            "condition": {"type": "serie_jours", "min": 3},
        },
        {
            "id": "t20_serie_7",
            "nom": "Rythme de croisière",
            "description": "Atteindre une série de 7 jours.",
            "condition": {"type": "serie_jours", "min": 7},
        },
        {
            "id": "t21_serie_14",
            "nom": "Discipline d’éleveur",
            "description": "Atteindre une série de 14 jours.",
            "condition": {"type": "serie_jours", "min": 14},
        },
        {
            "id": "t22_serie_30",
            "nom": "Saison complète",
            "description": "Atteindre une série de 30 jours.",
            "condition": {"type": "serie_jours", "min": 30},
        },
        {
            "id": "t23_points_1000",
            "nom": "Cap 1000",
            "description": "Atteindre 1000 points.",
            "condition": {"type": "points_total", "min": 1000},
        },
        {
            "id": "t24_points_5000",
            "nom": "Cap 5000",
            "description": "Atteindre 5000 points.",
            "condition": {"type": "points_total", "min": 5000},
        },
        # 25-30: maîtrise
        {
            "id": "t25_points_10000",
            "nom": "Cap 10000",
            "description": "Atteindre 10000 points.",
            "condition": {"type": "points_total", "min": 10000},
        },
        {
            "id": "t26_defis_10",
            "nom": "Chasseur de défis",
            "description": "Compléter 10 défis quotidiens.",
            "condition": {"type": "action_count", "action": "defi_quotidien_complete", "min": 10},
        },
        {
            "id": "t27_defis_50",
            "nom": "Champion des défis",
            "description": "Compléter 50 défis quotidiens.",
            "condition": {"type": "action_count", "action": "defi_quotidien_complete", "min": 50},
        },
        {
            "id": "t28_modules_5",
            "nom": "Explorateur de modules",
            "description": "Utiliser au moins 5 modules différents.",
            "condition": {"type": "modules_distincts", "min": 5},
        },
        {
            "id": "t29_inviteur_10",
            "nom": "Ambassadeur Aya",
            "description": "Inviter 10 éleveurs.",
            "condition": {"type": "action_count", "action": "invitation_ami", "min": 10},
        },
        {
            "id": "t30_precision_90",
            "nom": "Précision experte",
            "description": "Atteindre 90% de succès sur les quiz.",
            "condition": {"type": "ratio_succes", "champ": "quiz_taux_reussite_pct", "min": 90},
        },
    ]

    # Défis quotidiens par défaut.
    DEFIS_QUOTIDIENS: List[Dict[str, Any]] = [
        {
            "id": "d1_connexion",
            "nom": "Présence du jour",
            "action": "connexion_jour",
            "objectif": 1,
            "bonus_points": 10,
        },
        {
            "id": "d2_ration",
            "nom": "Une ration utile",
            "action": "generation_ration",
            "objectif": 1,
            "bonus_points": 20,
        },
        {
            "id": "d3_communautaire",
            "nom": "Coup de main communautaire",
            "action": "commentaire_utile_farmcommunity",
            "objectif": 1,
            "bonus_points": 12,
        },
    ]

    def __init__(self) -> None:
        """Initialise le moteur et ses bonus globaux."""
        self.bonus_langue_locale = 5
        self.bonus_serie_multiple_7 = 10
        self.bonus_heure_creuse_offline = 3

    # ---------------------------------------------------------------------
    # Méthodes utilitaires internes
    # ---------------------------------------------------------------------

    def _normaliser_date(self, valeur: Union[str, date, datetime]) -> Optional[date]:
        """
        Convertit une valeur en date Python.
        Accepte: str ISO (YYYY-MM-DD), date, datetime.
        Retourne None si la conversion est impossible.
        """
        if valeur is None:
            return None

        if isinstance(valeur, datetime):
            return valeur.date()

        if isinstance(valeur, date):
            return valeur

        if isinstance(valeur, str):
            texte = valeur.strip()
            if not texte:
                return None
            # Essai ISO simple.
            try:
                return datetime.fromisoformat(texte).date()
            except ValueError:
                pass
            # Essai format JJ/MM/AAAA.
            try:
                return datetime.strptime(texte, "%d/%m/%Y").date()
            except ValueError:
                return None

        return None

    def _get_actions_count(self, user_stats: Dict[str, Any]) -> Dict[str, int]:
        """
        Récupère le dictionnaire des compteurs d'actions en forçant des entiers >= 0.
        """
        actions = user_stats.get("actions_count", {})
        if not isinstance(actions, dict):
            return {}

        propres: Dict[str, int] = {}
        for cle, val in actions.items():
            try:
                propres[str(cle)] = max(0, int(val))
            except (ValueError, TypeError):
                propres[str(cle)] = 0
        return propres

    # ---------------------------------------------------------------------
    # API publique
    # ---------------------------------------------------------------------

    def calculer_points(self, action: str, contexte: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Calcule les points pour une action donnée.

        Paramètres:
        - action: nom technique de l'action (ex: "generation_ration")
        - contexte: données optionnelles pour bonus/malus
          Exemples de clés:
          - "code_langue": "fon", "fr", "en", ...
          - "serie_actuelle": int
          - "offline_mode": bool
          - "multiplicateur_evenement": float

        Règles bonus:
        - langue locale africaine (hors fr/en): +5 points
        - série multiple de 7 jours: +10 points
        - mode offline: +3 points

        Retour:
        {
          "action": ...,
          "points_base": ...,
          "bonus": [...],
          "points_total": ...
        }
        """
        contexte = contexte or {}

        if action not in self.ACTIONS_POINTS:
            raise ValueError(f"Action inconnue: '{action}'.")

        points_base = self.ACTIONS_POINTS[action]
        points_total = points_base
        bonus_details: List[Dict[str, Any]] = []

        # Bonus langue locale.
        code_langue = str(contexte.get("code_langue", "")).lower().strip()
        if code_langue and code_langue not in {"fr", "en"}:
            points_total += self.bonus_langue_locale
            bonus_details.append(
                {"type": "langue_locale", "points": self.bonus_langue_locale}
            )

        # Bonus série.
        try:
            serie_actuelle = int(contexte.get("serie_actuelle", 0))
        except (TypeError, ValueError):
            serie_actuelle = 0

        if serie_actuelle > 0 and serie_actuelle % 7 == 0:
            points_total += self.bonus_serie_multiple_7
            bonus_details.append(
                {"type": "serie_multiple_7", "points": self.bonus_serie_multiple_7}
            )

        # Bonus mode offline (encourage l'usage même sans réseau).
        if bool(contexte.get("offline_mode", False)):
            points_total += self.bonus_heure_creuse_offline
            bonus_details.append(
                {"type": "offline_mode", "points": self.bonus_heure_creuse_offline}
            )

        # Multiplicateur événement (si campagne spéciale).
        multiplicateur = contexte.get("multiplicateur_evenement", 1.0)
        try:
            multiplicateur = float(multiplicateur)
        except (TypeError, ValueError):
            multiplicateur = 1.0

        if multiplicateur <= 0:
            multiplicateur = 1.0

        points_total = int(round(points_total * multiplicateur))

        return {
            "action": action,
            "points_base": points_base,
            "bonus": bonus_details,
            "multiplicateur": multiplicateur,
            "points_total": max(0, points_total),
        }

    def determiner_niveau(self, points_total: int) -> Dict[str, Any]:
        """
        Détermine le niveau actuel et le prochain niveau.

        Retour:
        {
          "niveau_actuel": {...},
          "prochain_niveau": {... | None},
          "progression_pct": float,
          "points_dans_niveau": int,
          "points_restant_pour_suivant": int
        }
        """
        try:
            points_total = int(points_total)
        except (TypeError, ValueError):
            points_total = 0

        points_total = max(0, points_total)

        niveau_actuel = self.NIVEAUX[0]
        prochain_niveau = None

        for idx, niveau in enumerate(self.NIVEAUX):
            if points_total >= niveau["seuil_points"]:
                niveau_actuel = niveau
                prochain_niveau = self.NIVEAUX[idx + 1] if idx + 1 < len(self.NIVEAUX) else None
            else:
                break

        if prochain_niveau is None:
            # Niveau max atteint.
            progression_pct = 100.0
            points_dans_niveau = points_total - niveau_actuel["seuil_points"]
            points_restant = 0
        else:
            debut = niveau_actuel["seuil_points"]
            fin = prochain_niveau["seuil_points"]
            span = max(1, fin - debut)
            points_dans_niveau = max(0, points_total - debut)
            progression_pct = min(100.0, (points_dans_niveau / span) * 100.0)
            points_restant = max(0, fin - points_total)

        return {
            "niveau_actuel": niveau_actuel,
            "prochain_niveau": prochain_niveau,
            "progression_pct": round(progression_pct, 2),
            "points_dans_niveau": points_dans_niveau,
            "points_restant_pour_suivant": points_restant,
        }

    def verifier_trophees(self, user_stats: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Vérifie les nouveaux trophées débloqués pour un utilisateur.

        user_stats (attendu) peut contenir:
        - points_total: int
        - actions_count: dict
        - serie_actuelle: int
        - langues_locales_utilisees: list[str]
        - modules_utilises: list[str]
        - especes_suivies: list[str]
        - quiz_taux_reussite_pct: float
        - trophees_deja_obtenus: list[str]

        Retour:
        - Liste des trophées nouvellement débloqués.
        """
        if not isinstance(user_stats, dict):
            raise ValueError("user_stats doit être un dictionnaire.")

        points_total = max(0, int(user_stats.get("points_total", 0) or 0))
        actions_count = self._get_actions_count(user_stats)
        serie_actuelle = max(0, int(user_stats.get("serie_actuelle", 0) or 0))

        langues_locales = user_stats.get("langues_locales_utilisees", [])
        if not isinstance(langues_locales, list):
            langues_locales = []

        modules_utilises = user_stats.get("modules_utilises", [])
        if not isinstance(modules_utilises, list):
            modules_utilises = []

        especes_suivies = user_stats.get("especes_suivies", [])
        if not isinstance(especes_suivies, list):
            especes_suivies = []

        deja = set(user_stats.get("trophees_deja_obtenus", []) or [])

        nouveaux: List[Dict[str, Any]] = []

        for troph in self.TROPHEES:
            troph_id = troph["id"]
            if troph_id in deja:
                continue

            cond = troph.get("condition", {})
            cond_type = cond.get("type")

            debloque = False

            if cond_type == "points_total":
                debloque = points_total >= int(cond.get("min", 0))

            elif cond_type == "action_count":
                action = str(cond.get("action", ""))
                mini = int(cond.get("min", 0))
                debloque = actions_count.get(action, 0) >= mini

            elif cond_type == "serie_jours":
                debloque = serie_actuelle >= int(cond.get("min", 0))

            elif cond_type == "langues_locales_distinctes":
                # Langues locales = toutes sauf fr/en.
                distinctes = {str(x).lower().strip() for x in langues_locales if str(x).strip()}
                locales = {c for c in distinctes if c not in {"fr", "en"}}
                debloque = len(locales) >= int(cond.get("min", 0))

            elif cond_type == "modules_distincts":
                distincts = {str(x).strip().lower() for x in modules_utilises if str(x).strip()}
                debloque = len(distincts) >= int(cond.get("min", 0))

            elif cond_type == "especes_distinctes":
                distinctes = {str(x).strip().lower() for x in especes_suivies if str(x).strip()}
                debloque = len(distinctes) >= int(cond.get("min", 0))

            elif cond_type == "ratio_succes":
                champ = str(cond.get("champ", "")).strip()
                mini = float(cond.get("min", 0))
                valeur = float(user_stats.get(champ, 0) or 0)
                debloque = valeur >= mini

            if debloque:
                nouveaux.append(troph)

        return nouveaux

    def calculer_serie(
        self,
        derniere_connexion: Union[str, date, datetime, None],
        connexions_historique: Union[List[Union[str, date, datetime]], Dict[str, Any], None],
    ) -> Dict[str, Any]:
        """
        Calcule la série de connexion actuelle.

        Gère la protection "Graines de Secours":
        - Si un seul jour est manqué entre deux connexions, et que des graines
          sont disponibles, la série peut être maintenue.

        Paramètres:
        - derniere_connexion: dernière date de connexion connue
        - connexions_historique:
            * soit une liste de dates
            * soit un dict {"dates": [...], "graines_secours": int}

        Retour:
        {
          "serie_actuelle": int,
          "derniere_date_comptee": "YYYY-MM-DD" | None,
          "protection_utilisee": bool,
          "graines_restantes": int
        }
        """
        # Extraction des dates et des graines.
        graines = 0
        dates_brutes: List[Any] = []

        if isinstance(connexions_historique, dict):
            dates_brutes = connexions_historique.get("dates", []) or []
            try:
                graines = int(connexions_historique.get("graines_secours", 0) or 0)
            except (TypeError, ValueError):
                graines = 0
        elif isinstance(connexions_historique, list):
            dates_brutes = connexions_historique
        else:
            dates_brutes = []

        # Ajouter la dernière connexion si fournie.
        if derniere_connexion is not None:
            dates_brutes.append(derniere_connexion)

        dates_norm = [self._normaliser_date(v) for v in dates_brutes]
        dates_uniques = sorted({d for d in dates_norm if d is not None})

        if not dates_uniques:
            return {
                "serie_actuelle": 0,
                "derniere_date_comptee": None,
                "protection_utilisee": False,
                "graines_restantes": max(0, graines),
            }

        aujourd_hui = date.today()
        protection_utilisee = False

        # Série calculée depuis la date la plus récente vers le passé.
        serie = 1
        idx = len(dates_uniques) - 1
        curseur = dates_uniques[idx]

        # Si la dernière connexion date de plus de 1 jour, la série peut déjà être cassée.
        # On autorise une protection si écart = 2 jours et graines disponibles.
        ecart_avec_aujourdhui = (aujourd_hui - curseur).days
        if ecart_avec_aujourdhui > 1:
            if ecart_avec_aujourdhui == 2 and graines > 0:
                graines -= 1
                protection_utilisee = True
            else:
                # Série nulle (ou 1 historique mais inactive aujourd'hui).
                return {
                    "serie_actuelle": 0,
                    "derniere_date_comptee": curseur.isoformat(),
                    "protection_utilisee": False,
                    "graines_restantes": max(0, graines),
                }

        # Remonter l'historique pour compter les jours consécutifs.
        while idx > 0:
            actuelle = dates_uniques[idx]
            precedente = dates_uniques[idx - 1]
            diff = (actuelle - precedente).days

            if diff == 1:
                serie += 1
            elif diff == 2 and graines > 0:
                # Un jour manqué, protégé par une graine.
                graines -= 1
                protection_utilisee = True
                serie += 1
            else:
                break
            idx -= 1

        return {
            "serie_actuelle": max(0, serie),
            "derniere_date_comptee": curseur.isoformat(),
            "protection_utilisee": protection_utilisee,
            "graines_restantes": max(0, graines),
        }

    def verifier_defis_quotidiens(self, actions_jour: Dict[str, int]) -> Dict[str, Any]:
        """
        Vérifie les défis quotidiens complétés.

        Paramètre:
        - actions_jour: dict {action: nombre_realise}

        Retour:
        {
          "defis": [
            {
              "id": ...,
              "nom": ...,
              "action": ...,
              "objectif": ...,
              "realise": ...,
              "complete": bool,
              "bonus_points": ...
            }, ...
          ],
          "tous_completes": bool,
          "bonus_total": int
        }
        """
        if not isinstance(actions_jour, dict):
            raise ValueError("actions_jour doit être un dictionnaire {action: quantité}.")

        # Nettoyage des valeurs.
        actions_clean: Dict[str, int] = {}
        for a, v in actions_jour.items():
            try:
                actions_clean[str(a)] = max(0, int(v))
            except (TypeError, ValueError):
                actions_clean[str(a)] = 0

        statut_defis: List[Dict[str, Any]] = []
        bonus_total = 0
        tous_completes = True

        for defi in self.DEFIS_QUOTIDIENS:
            action = defi["action"]
            objectif = int(defi["objectif"])
            realise = actions_clean.get(action, 0)
            complete = realise >= objectif

            if not complete:
                tous_completes = False
            else:
                bonus_total += int(defi.get("bonus_points", 0))

            statut_defis.append(
                {
                    "id": defi["id"],
                    "nom": defi["nom"],
                    "action": action,
                    "objectif": objectif,
                    "realise": realise,
                    "complete": complete,
                    "bonus_points": int(defi.get("bonus_points", 0)),
                }
            )

        return {
            "defis": statut_defis,
            "tous_completes": tous_completes,
            "bonus_total": bonus_total,
        }
