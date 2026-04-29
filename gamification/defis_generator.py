#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Générateur de défis quotidiens pour FeedFormula AI.

Objectifs :
- Proposer 3 défis par jour adaptés au niveau utilisateur
- Varier les défis pour éviter les répétitions
- Donner un peu plus de difficulté le week-end
- Vérifier simplement si un défi est complété à partir des actions du jour

Le module reste indépendant pour pouvoir être utilisé :
- côté API FastAPI,
- côté tâches planifiées,
- ou côté tests unitaires.

Tous les commentaires sont en français pour faciliter la maintenance.
"""

from __future__ import annotations

import copy
import random
from datetime import date, datetime
from typing import Any, Dict, List, Optional


# -----------------------------------------------------------------------------
# Banque principale de défis
# -----------------------------------------------------------------------------
# Chaque défi suit ce format :
# {
#   "code": "defi_unique_id",
#   "type": "ration",
#   "titre": "Générer 2 rations aujourd'hui",
#   "description": "Aider 2 éleveurs à formuler une ration...",
#   "condition": {"action": "generer_ration", "count": 2},
#   "points": 30,
#   "difficulte": "facile",
#   "emoji": "🌾"
# }
#
# Cette banque est volontairement variée pour couvrir :
# - ration
# - diagnostic
# - formation
# - social
# - reproduction
# - partage
# - série
#
BANQUE_DE_DEFIS: List[Dict[str, Any]] = [
    {
        "code": "ration_1",
        "type": "ration",
        "titre": "Générer 1 ration",
        "description": "Prépare une ration équilibrée pour un animal.",
        "condition": {"action": "generer_ration", "count": 1},
        "points": 15,
        "difficulte": "facile",
        "emoji": "🌾",
    },
    {
        "code": "ration_2",
        "type": "ration",
        "titre": "Générer 2 rations aujourd'hui",
        "description": "Aide 2 éleveurs à formuler une ration utile.",
        "condition": {"action": "generer_ration", "count": 2},
        "points": 30,
        "difficulte": "moyen",
        "emoji": "🌾",
    },
    {
        "code": "ration_3",
        "type": "ration",
        "titre": "Tester une ration économique",
        "description": "Crée une ration orientée vers la réduction des coûts.",
        "condition": {"action": "generer_ration_economique", "count": 1},
        "points": 25,
        "difficulte": "facile",
        "emoji": "💰",
    },
    {
        "code": "ration_4",
        "type": "ration",
        "titre": "Tester une ration riche en protéines",
        "description": "Formule une ration plus riche pour la croissance.",
        "condition": {"action": "generer_ration_proteines", "count": 1},
        "points": 28,
        "difficulte": "moyen",
        "emoji": "💪",
    },
    {
        "code": "ration_5",
        "type": "ration",
        "titre": "Partager une ration sur WhatsApp",
        "description": "Partage une formule utile avec un autre éleveur.",
        "condition": {"action": "partager_whatsapp", "count": 1},
        "points": 20,
        "difficulte": "facile",
        "emoji": "📱",
    },
    {
        "code": "ration_6",
        "type": "ration",
        "titre": "Télécharger une fiche PDF",
        "description": "Garde une ration en PDF pour la distribuer facilement.",
        "condition": {"action": "telecharger_pdf", "count": 1},
        "points": 10,
        "difficulte": "facile",
        "emoji": "📄",
    },
    {
        "code": "ration_7",
        "type": "ration",
        "titre": "Utiliser une langue locale",
        "description": "Génère une ration dans la langue de la ferme.",
        "condition": {"action": "generer_ration_langue_locale", "count": 1},
        "points": 20,
        "difficulte": "moyen",
        "emoji": "🗣️",
    },
    {
        "code": "ration_8",
        "type": "ration",
        "titre": "Appliquer une ration 3 jours",
        "description": "Valide l'usage réel d'une ration sur 3 jours.",
        "condition": {"action": "utiliser_ration_3_jours", "count": 1},
        "points": 35,
        "difficulte": "moyen",
        "emoji": "⏳",
    },
    {
        "code": "diagnostic_1",
        "type": "diagnostic",
        "titre": "Faire 1 diagnostic VetScan",
        "description": "Analyse un cas santé simple pour un animal.",
        "condition": {"action": "diagnostic_vetscan", "count": 1},
        "points": 20,
        "difficulte": "facile",
        "emoji": "🩺",
    },
    {
        "code": "diagnostic_2",
        "type": "diagnostic",
        "titre": "Faire 3 diagnostics VetScan",
        "description": "Aide plusieurs animaux grâce au triage vétérinaire.",
        "condition": {"action": "diagnostic_vetscan", "count": 3},
        "points": 40,
        "difficulte": "moyen",
        "emoji": "🩺",
    },
    {
        "code": "diagnostic_3",
        "type": "diagnostic",
        "titre": "Documenter un cas résolu",
        "description": "Confirme la guérison après le suivi.",
        "condition": {"action": "cas_resolu", "count": 1},
        "points": 50,
        "difficulte": "moyen",
        "emoji": "✅",
    },
    {
        "code": "diagnostic_4",
        "type": "diagnostic",
        "titre": "Envoyer une photo de suivi",
        "description": "Partage une photo pour confirmer l'évolution.",
        "condition": {"action": "photo_suivi_guerison", "count": 1},
        "points": 15,
        "difficulte": "facile",
        "emoji": "📷",
    },
    {
        "code": "formation_1",
        "type": "formation",
        "titre": "Compléter 1 leçon",
        "description": "Avance dans une formation FarmAcademy.",
        "condition": {"action": "completer_lecon", "count": 1},
        "points": 20,
        "difficulte": "facile",
        "emoji": "📘",
    },
    {
        "code": "formation_2",
        "type": "formation",
        "titre": "Réussir un quiz à 100%",
        "description": "Montre ta maîtrise d'un sujet agricole.",
        "condition": {"action": "quiz_100_pct", "count": 1},
        "points": 30,
        "difficulte": "moyen",
        "emoji": "🧠",
    },
    {
        "code": "formation_3",
        "type": "formation",
        "titre": "Terminer une certification",
        "description": "Valide une formation complète.",
        "condition": {"action": "certification_complete", "count": 1},
        "points": 150,
        "difficulte": "difficile",
        "emoji": "🎓",
    },
    {
        "code": "formation_4",
        "type": "formation",
        "titre": "Suivre un rapport mensuel",
        "description": "Complète ton suivi de fin de mois.",
        "condition": {"action": "rapport_mensuel", "count": 1},
        "points": 25,
        "difficulte": "moyen",
        "emoji": "📊",
    },
    {
        "code": "social_1",
        "type": "social",
        "titre": "Aider un éleveur",
        "description": "Apporte une réponse utile à la communauté.",
        "condition": {"action": "aider_eleveur", "count": 1},
        "points": 25,
        "difficulte": "facile",
        "emoji": "🤝",
    },
    {
        "code": "social_2",
        "type": "social",
        "titre": "Recevoir 5 retours utiles",
        "description": "Partage un conseil apprécié par les autres.",
        "condition": {"action": "recevoir_5_utile", "count": 5},
        "points": 40,
        "difficulte": "moyen",
        "emoji": "⭐",
    },
    {
        "code": "social_3",
        "type": "social",
        "titre": "Inviter un ami",
        "description": "Fais découvrir FeedFormula AI à un autre éleveur.",
        "condition": {"action": "inviter_ami", "count": 1},
        "points": 100,
        "difficulte": "difficile",
        "emoji": "👥",
    },
    {
        "code": "reproduction_1",
        "type": "reproduction",
        "titre": "Enregistrer une saillie",
        "description": "Note un événement de reproduction.",
        "condition": {"action": "enregistrer_saillie", "count": 1},
        "points": 10,
        "difficulte": "facile",
        "emoji": "🩷",
    },
    {
        "code": "reproduction_2",
        "type": "reproduction",
        "titre": "Alerte mise-bas réussie",
        "description": "Valide une naissance ou une mise-bas attendue.",
        "condition": {"action": "alerte_mise_bas_reussie", "count": 1},
        "points": 30,
        "difficulte": "moyen",
        "emoji": "🐣",
    },
    {
        "code": "reproduction_3",
        "type": "reproduction",
        "titre": "Vêlage réussi documenté",
        "description": "Documente une naissance bovine.",
        "condition": {"action": "velage_reussi_documente", "count": 1},
        "points": 40,
        "difficulte": "difficile",
        "emoji": "🐄",
    },
    {
        "code": "serie_1",
        "type": "serie",
        "titre": "Série de 3 jours",
        "description": "Reviens trois jours de suite sur l'application.",
        "condition": {"action": "connexion_jour", "streak": 3},
        "points": 15,
        "difficulte": "facile",
        "emoji": "🔥",
    },
    {
        "code": "serie_2",
        "type": "serie",
        "titre": "Série de 7 jours",
        "description": "Tiens une semaine complète d'utilisation.",
        "condition": {"action": "connexion_jour", "streak": 7},
        "points": 50,
        "difficulte": "moyen",
        "emoji": "🔥",
    },
    {
        "code": "serie_3",
        "type": "serie",
        "titre": "Série de 30 jours",
        "description": "Montre une vraie régularité sur un mois.",
        "condition": {"action": "connexion_jour", "streak": 30},
        "points": 200,
        "difficulte": "difficile",
        "emoji": "🏆",
    },
    {
        "code": "serie_4",
        "type": "serie",
        "titre": "Connexion d'aujourd'hui",
        "description": "Ouvre l'application aujourd'hui pour rester actif.",
        "condition": {"action": "connexion_jour", "count": 1},
        "points": 5,
        "difficulte": "facile",
        "emoji": "🌞",
    },
    {
        "code": "mix_1",
        "type": "mix",
        "titre": "Journal complet",
        "description": "Faire une action utile dans 3 domaines différents.",
        "condition": {"actions_distinctes": 3, "count": 1},
        "points": 35,
        "difficulte": "moyen",
        "emoji": "📒",
    },
    {
        "code": "mix_2",
        "type": "mix",
        "titre": "Réflexe ferme",
        "description": "Compléter une ration, un suivi et une leçon dans la journée.",
        "condition": {
            "actions_necessaires": ["generer_ration", "diagnostic_vetscan", "completer_lecon"],
        },
        "points": 60,
        "difficulte": "difficile",
        "emoji": "⚡",
    },
    {
        "code": "mix_3",
        "type": "mix",
        "titre": "Ambassadeur local",
        "description": "Aider, partager et apprendre le même jour.",
        "condition": {
            "actions_necessaires": ["aider_eleveur", "partager_whatsapp", "completer_lecon"],
        },
        "points": 70,
        "difficulte": "difficile",
        "emoji": "🌍",
    },
    {
        "code": "mix_4",
        "type": "mix",
        "titre": "Expert du terrain",
        "description": "Montrer une activité avancée sur santé, ration et formation.",
        "condition": {
            "actions_necessaires": ["generer_ration", "diagnostic_vetscan", "quiz_100_pct"],
        },
        "points": 90,
        "difficulte": "difficile",
        "emoji": "🧭",
    },
    {
        "code": "mix_5",
        "type": "mix",
        "titre": "Rappel utile",
        "description": "Compléter une action de suivi et une action sociale.",
        "condition": {
            "actions_necessaires": ["enregistrer_saillie", "aider_eleveur"],
        },
        "points": 30,
        "difficulte": "moyen",
        "emoji": "🔔",
    },
]


# -----------------------------------------------------------------------------
# Niveaux
# -----------------------------------------------------------------------------
NIVEAUX: List[Dict[str, Any]] = [
    {"niveau": 1, "nom": "Semence", "min": 0, "max": 100},
    {"niveau": 2, "nom": "Pousse", "min": 101, "max": 300},
    {"niveau": 3, "nom": "Tige", "min": 301, "max": 600},
    {"niveau": 4, "nom": "Floraison", "min": 601, "max": 1000},
    {"niveau": 5, "nom": "Feuille d’Or", "min": 1001, "max": 2000},
    {"niveau": 6, "nom": "Recolte", "min": 2001, "max": 3500},
    {"niveau": 7, "nom": "Proprietaire", "min": 3501, "max": 5500},
    {"niveau": 8, "nom": "Maitre Eleveur", "min": 5501, "max": 8000},
    {"niveau": 9, "nom": "Champion", "min": 8001, "max": 12000},
    {"niveau": 10, "nom": "Legende Afrique", "min": 12001, "max": None},
]


# -----------------------------------------------------------------------------
# Ligues
# -----------------------------------------------------------------------------
LIGUES: List[Dict[str, Any]] = [
    {"code": "argile", "nom": "Argile", "min": 0, "max": 200, "icone": "🟤"},
    {"code": "herbe", "nom": "Herbe", "min": 201, "max": 500, "icone": "🌿"},
    {"code": "ble", "nom": "Ble", "min": 501, "max": 1000, "icone": "🌾"},
    {"code": "coton", "nom": "Coton", "min": 1001, "max": 2000, "icone": "🧶"},
    {"code": "bronze", "nom": "Bronze", "min": 2001, "max": 3500, "icone": "🥉"},
    {"code": "argent", "nom": "Argent", "min": 3501, "max": 6000, "icone": "🥈"},
    {"code": "or", "nom": "Or", "min": 6001, "max": 10000, "icone": "🥇"},
    {"code": "diamant", "nom": "Diamant", "min": 10001, "max": None, "icone": "💎"},
]


# -----------------------------------------------------------------------------
# Boutique
# -----------------------------------------------------------------------------
BOUTIQUE_ITEMS: Dict[str, Dict[str, Any]] = {
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


# -----------------------------------------------------------------------------
# Classe principale
# -----------------------------------------------------------------------------
class GamificationEngine:
    """
    Moteur de gamification complet.

    Le moteur centralise :
    - calcul des points,
    - détermination du niveau,
    - trophées,
    - séries,
    - défis,
    - ligues,
    - boutique.
    """

    ACTIONS_POINTS = ACTIONS_POINTS
    NIVEAUX = NIVEAUX
    TROPHEES = TROPHEES
    LIGUES = LIGUES
    BOUTIQUE_ITEMS = BOUTIQUE_ITEMS

    def calculer_points(self, action: str, contexte: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Calcule les points gagnés pour une action donnée.
        """
        action_norm = (action or "").strip().lower()
        contexte = contexte or {}

        if not action_norm:
            raise ValueError("L'action est obligatoire.")

        if action_norm not in self.ACTIONS_POINTS:
            # On ne bloque pas totalement : certaines actions personnalisées peuvent exister.
            points_base = 0
        else:
            points_base = int(self.ACTIONS_POINTS[action_norm])

        multiplicateur = 1.0
        if contexte.get("langue_locale") is True or action_norm == "generer_ration_langue_locale":
            multiplicateur += 0.5 if action_norm == "generer_ration" else 0.0
        if contexte.get("weekend") is True:
            multiplicateur += 0.1
        if contexte.get("urgence") is True:
            multiplicateur += 0.2

        count = int(contexte.get("count", 1) or 1)
        count = max(1, min(count, 20))

        total = int(round(points_base * multiplicateur * count))

        # Bonus contextualisés.
        bonus = 0
        if action_norm == "connexion_jour" and contexte.get("streak"):
            streak = int(contexte.get("streak") or 0)
            if streak >= 30:
                bonus += 200
            elif streak >= 7:
                bonus += 50
            elif streak >= 3:
                bonus += 15

        if action_norm == "generer_ration" and contexte.get("langue_locale"):
            bonus += 5

        total += bonus

        return {
            "action": action_norm,
            "points_base": points_base,
            "multiplicateur": round(multiplicateur, 2),
            "bonus": bonus,
            "total": max(0, total),
            "contexte": contexte,
        }

    def determiner_niveau(self, points_total: int) -> Dict[str, Any]:
        """
        Détermine le niveau actuel à partir du total de points.
        """
        points = max(0, int(points_total or 0))
        niveau_courant = self.NIVEAUX[0]
        niveau_suivant: Optional[Dict[str, Any]] = None

        for niveau in self.NIVEAUX:
            min_points = int(niveau["min"])
            max_points = niveau["max"]
            if points >= min_points and (max_points is None or points <= int(max_points)):
                niveau_courant = niveau

        for niveau in self.NIVEAUX:
            if int(niveau["min"]) > points:
                niveau_suivant = niveau
                break

        min_courant = int(niveau_courant["min"])
        max_courant = int(niveau_courant["max"]) if niveau_courant["max"] is not None else None
        if max_courant is None:
            progression = 100.0
            restant = 0
        else:
            span = max(1, max_courant - min_courant)
            progression = ((points - min_courant) / span) * 100.0
            progression = max(0.0, min(100.0, progression))
            restant = max(0, max_courant - points)

        return {
            "niveau_actuel": niveau_courant["niveau"],
            "nom": niveau_courant["nom"],
            "points_total": points,
            "progression": round(progression, 2),
            "points_restants": restant,
            "prochain_niveau": niveau_suivant["niveau"] if niveau_suivant else None,
            "nom_prochain_niveau": niveau_suivant["nom"] if niveau_suivant else None,
        }

    def determiner_ligue(self, points_total: int) -> Dict[str, Any]:
        """
        Détermine la ligue actuelle d'un utilisateur selon son total de points.
        """
        points = max(0, int(points_total or 0))
        ligue_actuelle = self.LIGUES[0]
        ligue_suivante: Optional[Dict[str, Any]] = None

        for ligue in self.LIGUES:
            min_points = int(ligue["min"])
            max_points = ligue["max"]
            if points >= min_points and (max_points is None or points <= int(max_points)):
                ligue_actuelle = ligue

        for ligue in self.LIGUES:
            if int(ligue["min"]) > points:
                ligue_suivante = ligue
                break

        points_restant = 0
        if ligue_suivante is not None:
            points_restant = max(0, int(ligue_suivante["min"]) - points)

        return {
            "ligue_actuelle": ligue_actuelle,
            "ligue_suivante": ligue_suivante,
            "points_restant_pour_monter": points_restant,
        }

    def verifier_trophees(self, user_stats: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Vérifie les nouveaux trophées débloqués pour un utilisateur.
        """
        user_stats = user_stats or {}
        points_total = int(user_stats.get("points_total", 0) or 0)
        actions_count = user_stats.get("actions_count", {}) or {}
        serie_actuelle = int(user_stats.get("serie_actuelle", 0) or 0)
        langues_locales = set(user_stats.get("langues_locales_utilisees", []) or [])
        modules_utilises = set(user_stats.get("modules_utilises", []) or [])
        especes_suivies = set(user_stats.get("especes_suivies", []) or [])
        deja_obtenus = set(user_stats.get("trophees_deja_obtenus", []) or [])
        ratio_succes = float(user_stats.get("quiz_taux_reussite_pct", 0.0) or 0.0)

        nouveaux: List[Dict[str, Any]] = []

        for trophee in self.TROPHEES:
            code = trophee["id"]
            if code in deja_obtenus:
                continue

            cond = trophee.get("condition", {})
            cond_type = cond.get("type")

            debloque = False
            if cond_type == "points_total":
                debloque = points_total >= int(cond.get("min", 0))
            elif cond_type == "action_count":
                action = cond.get("action", "")
                debloque = int(actions_count.get(action, 0)) >= int(cond.get("min", 1))
            elif cond_type == "serie_jours":
                debloque = serie_actuelle >= int(cond.get("min", 1))
            elif cond_type == "langues_locales_distinctes":
                debloque = len(langues_locales) >= int(cond.get("min", 1))
            elif cond_type == "modules_distincts":
                debloque = len(modules_utilises) >= int(cond.get("min", 1))
            elif cond_type == "especes_distinctes":
                debloque = len(especes_suivies) >= int(cond.get("min", 1))
            elif cond_type == "ratio_succes":
                debloque = ratio_succes >= float(cond.get("min", 0.0))
            elif "actions_necessaires" in cond:
                necessaires = cond.get("actions_necessaires", [])
                debloque = all(int(actions_count.get(act, 0)) > 0 for act in necessaires)
            elif "actions_distinctes" in cond:
                distinctes = sum(1 for v in actions_count.values() if int(v or 0) > 0)
                debloque = distinctes >= int(cond.get("actions_distinctes", 1))
            elif "count" in cond:
                # Cas générique.
                action = cond.get("action")
                if action:
                    debloque = int(actions_count.get(action, 0)) >= int(cond.get("count", 1))

            if debloque:
                nouveaux.append(copy.deepcopy(trophee))

        return nouveaux

    def calculer_serie(
        self,
        derniere_connexion: Union[str, date, datetime, None],
        historique: Optional[List[Union[str, date, datetime]]] = None,
    ) -> Dict[str, Any]:
        """
        Calcule la série actuelle et la meilleure série sur un historique de dates.
        """
        historique = historique or []
        dates: List[date] = []

        for item in historique:
            if isinstance(item, datetime):
                dates.append(item.date())
            elif isinstance(item, date):
                dates.append(item)
            elif isinstance(item, str):
                try:
                    dates.append(datetime.fromisoformat(item).date())
                except Exception:
                    pass

        if isinstance(derniere_connexion, datetime):
            derniere = derniere_connexion.date()
        elif isinstance(derniere_connexion, date):
            derniere = derniere_connexion
        elif isinstance(derniere_connexion, str):
            try:
                derniere = datetime.fromisoformat(derniere_connexion).date()
            except Exception:
                derniere = None
        else:
            derniere = None

        aujourd_hui = date.today()

        if derniere is None:
            return {
                "serie_actuelle": 0,
                "meilleure_serie": max(0, len(dates)),
                "jours_depuis_derniere_connexion": None,
                "en_danger": False,
            }

        jours_depuis = (aujourd_hui - derniere).days
        serie = 0

        if jours_depuis == 0:
            # On tente d'estimer une série à partir de l'historique.
            jours_tries = sorted(set(dates + [derniere]))
            serie = 1
            for i in range(len(jours_tries) - 2, -1, -1):
                if (jours_tries[i + 1] - jours_tries[i]).days == 1:
                    serie += 1
                else:
                    break
        elif jours_depuis == 1:
            # Série toujours vivante si l'utilisateur revient le lendemain.
            jours_tries = sorted(set(dates + [derniere]))
            serie = 1
            for i in range(len(jours_tries) - 2, -1, -1):
                if (jours_tries[i + 1] - jours_tries[i]).days == 1:
                    serie += 1
                else:
                    break
        else:
            serie = 0

        meilleure = 0
        if dates:
            jours_tries = sorted(set(dates))
            courante = 1
            meilleure = 1
            for i in range(1, len(jours_tries)):
                if (jours_tries[i] - jours_tries[i - 1]).days == 1:
                    courante += 1
                else:
                    meilleure = max(meilleure, courante)
                    courante = 1
            meilleure = max(meilleure, courante)

        return {
            "serie_actuelle": serie,
            "meilleure_serie": max(meilleure, serie),
            "jours_depuis_derniere_connexion": jours_depuis,
            "en_danger": jours_depuis >= 1,
        }

    def verifier_defis_quotidiens(self, actions_jour: Dict[str, int]) -> Dict[str, Any]:
        """
        Vérifie les défis quotidiens complétés à partir des actions du jour.
        """
        actions_jour = actions_jour or {}
        defis = [
            {
                "code": "defi_connexion",
                "titre": "Connexion du jour",
                "condition": {"action": "connexion_jour", "count": 1},
                "points": 5,
            },
            {
                "code": "defi_ration",
                "titre": "Ration utile",
                "condition": {"action": "generer_ration", "count": 1},
                "points": 10,
            },
            {
                "code": "defi_sante",
                "titre": "Suivi santé",
                "condition": {"action": "diagnostic_vetscan", "count": 1},
                "points": 20,
            },
        ]

        completions: List[Dict[str, Any]] = []
        total_points = 0

        for defi in defis:
            cond = defi["condition"]
            action = cond["action"]
            count_requis = int(cond.get("count", 1))
            if int(actions_jour.get(action, 0) or 0) >= count_requis:
                completions.append(copy.deepcopy(defi))
                total_points += int(defi.get("points", 0))

        return {
            "total_defis": len(defis),
            "defis_completes": completions,
            "points_gagnes": total_points,
            "date": date.today().isoformat(),
        }

    def get_ligue_actuelle(self, points_saison: int) -> Dict[str, Any]:
        """
        Retourne la ligue actuelle à partir des points de saison.
        """
        points = max(0, int(points_saison or 0))
        ligue = self.LIGUES[0]
        for item in self.LIGUES:
            if points >= int(item["min"]):
                ligue = item
        return ligue

    def depenser_graines_or(self, user: Any, montant: int, item: str) -> Dict[str, Any]:
        """
        Dépense des Graines d'Or pour un item de boutique.
        """
        if user is None:
            raise ValueError("Utilisateur manquant.")
        montant = max(0, int(montant or 0))
        if montant <= 0:
            raise ValueError("Le montant doit être positif.")

        solde = int(getattr(user, "graines_or", 0) or 0)
        if solde < montant:
            raise ValueError("Solde de Graines d'Or insuffisant.")

        user.graines_or = solde - montant
        return {
            "user_id": getattr(user, "id", None),
            "item": item,
            "montant_debite": montant,
            "solde_restant": user.graines_or,
        }

    def get_boutique_items(self) -> List[Dict[str, Any]]:
        """
        Retourne les items disponibles dans la boutique virtuelle.
        """
        return [
            {
                "code": code,
                "nom": value["nom"],
                "prix_graines_or": int(value["prix_graines_or"]),
                "description": value["description"],
            }
            for code, value in self.BOUTIQUE_ITEMS.items()
        ]


__all__ = [
    "ACTIONS_POINTS",
    "NIVEAUX",
    "LIGUES",
    "TROPHEES",
    "BOUTIQUE_ITEMS",
    "GamificationEngine",
]
