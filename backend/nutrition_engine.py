#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Moteur de formulation simplifié pour NutriCore (FeedFormula AI).

Ce module fournit la classe `NutritionEngine` qui permet de :
- charger les matières premières et besoins nutritionnels depuis des fichiers JSON,
- proposer une ration optimisée (approche simplifiée, coût + respect des besoins),
- calculer le coût d'alimentation sur 7 jours,
- générer des recommandations pratiques selon espèce/stade.
"""

from __future__ import annotations

import json
import random
import unicodedata
from pathlib import Path
from typing import Dict, List, Any, Tuple


class NutritionEngine:
    """
    Moteur principal de formulation des rations.

    Paramètres:
    - data_dir: chemin vers le dossier `data` (si None, détecté automatiquement).
    - nombre_animaux_par_defaut: utilisé pour calculer le coût 7 jours dans optimiser_ration.
    """

    def __init__(self, data_dir: str | Path | None = None, nombre_animaux_par_defaut: int = 1) -> None:
        # Définition du dossier data.
        if data_dir is None:
            # backend/nutrition_engine.py -> racine projet -> data/
            self.data_dir = Path(__file__).resolve().parent.parent / "data"
        else:
            self.data_dir = Path(data_dir)

        # Nombre d'animaux par défaut (utilisé dans optimiser_ration).
        self.nombre_animaux_par_defaut = max(1, int(nombre_animaux_par_defaut))

        # Fichiers sources.
        self._ingredients_file = self.data_dir / "matieres_premieres.json"
        self._besoins_file = self.data_dir / "besoins_animaux.json"

    # -------------------------------------------------------------------------
    # Méthodes utilitaires internes
    # -------------------------------------------------------------------------
    @staticmethod
    def _normaliser_texte(texte: str) -> str:
        """
        Normalise un texte pour les comparaisons robustes:
        - minuscule
        - suppression des accents
        - trim des espaces
        """
        if not isinstance(texte, str):
            return ""
        t = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode("ascii")
        return " ".join(t.lower().strip().split())

    @staticmethod
    def _safe_float(valeur: Any, default: float = 0.0) -> float:
        """
        Convertit une valeur en float sans planter.
        """
        try:
            if valeur is None:
                return default
            return float(valeur)
        except (TypeError, ValueError):
            return default

    def _charger_json(self, path: Path) -> Dict[str, Any]:
        """
        Charge un JSON avec gestion d'erreurs explicite.
        """
        if not path.exists():
            raise FileNotFoundError(f"Fichier introuvable: {path}")

        try:
            with path.open("r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError as exc:
            raise ValueError(f"JSON invalide dans {path}: {exc}") from exc
        except OSError as exc:
            raise OSError(f"Impossible de lire {path}: {exc}") from exc

    def _resoudre_ingredient(self, nom: str, ingredients_indexes: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """
        Résout un nom d'ingrédient entré par l'utilisateur vers la fiche ingrédient.

        Gère:
        - nom français exact / approximatif (normalisé)
        - id technique
        - nom fon / yoruba
        """
        cle = self._normaliser_texte(nom)
        if cle in ingredients_indexes:
            return ingredients_indexes[cle]

        # Tentative de recherche partielle robuste.
        candidats = []
        for k, v in ingredients_indexes.items():
            if cle and (cle in k or k in cle):
                candidats.append((k, v))

        if len(candidats) == 1:
            return candidats[0][1]

        # Si ambigu ou non trouvé, on lève une erreur claire.
        if len(candidats) > 1:
            noms = sorted({c[1].get("nom_fr", c[0]) for c in candidats})[:6]
            raise ValueError(
                f"Ingrédient ambigu '{nom}'. Exemples possibles: {', '.join(noms)}"
            )

        raise ValueError(f"Ingrédient inconnu: '{nom}'")

    @staticmethod
    def _calculer_nutriments_et_cout(
        composition_pct: Dict[str, float],
        fiches: Dict[str, Dict[str, Any]],
    ) -> Tuple[Dict[str, float], float]:
        """
        Calcule la valeur nutritive moyenne de la ration (en % ou kcal/kg)
        et son coût FCFA/kg.

        composition_pct: dict {nom_ingredient: % dans la ration}
        """
        total_pct = sum(composition_pct.values())
        if total_pct <= 0:
            raise ValueError("Composition vide ou invalide (somme <= 0).")

        # Normalisation de sécurité à 100%.
        comp = {k: (v / total_pct) * 100.0 for k, v in composition_pct.items()}

        energie = 0.0
        proteines = 0.0
        calcium = 0.0
        phosphore = 0.0
        cout = 0.0

        for nom, pct in comp.items():
            fiche = fiches[nom]
            ratio = pct / 100.0

            energie += ratio * float(fiche.get("energie_kcal_kg", 0.0))
            proteines += ratio * float(fiche.get("proteines_brutes_pct", 0.0))
            calcium += ratio * float(fiche.get("calcium_pct", 0.0))
            phosphore += ratio * float(fiche.get("phosphore_disponible_pct", 0.0))
            cout += ratio * float(fiche.get("prix_fcfa_kg_benin_2026", 0.0))

        return (
            {
                "energie_kcal_kg": round(energie, 2),
                "proteines_pct": round(proteines, 3),
                "calcium_pct": round(calcium, 3),
                "phosphore_pct": round(phosphore, 3),
            },
            round(cout, 2),
        )

    # -------------------------------------------------------------------------
    # API publique demandée
    # -------------------------------------------------------------------------
    def charger_ingredients(self) -> Dict[str, Dict[str, Any]]:
        """
        Charge `data/matieres_premieres.json`.

        Retour:
        - Un dictionnaire indexé par nom (normalisé).
        - Chaque entrée contient la fiche complète de la matière première.

        Gestion d'erreurs:
        - fichier absent
        - JSON invalide
        - structure inattendue
        """
        data = self._charger_json(self._ingredients_file)
        items = data.get("matieres_premieres")

        if not isinstance(items, list) or not items:
            raise ValueError(
                "Structure invalide: 'matieres_premieres' manquant ou vide."
            )

        index: Dict[str, Dict[str, Any]] = {}
        for item in items:
            if not isinstance(item, dict):
                continue

            # Index principal: nom_fr
            nom_fr = item.get("nom_fr")
            if isinstance(nom_fr, str) and nom_fr.strip():
                index[self._normaliser_texte(nom_fr)] = item

            # Alias utiles.
            for champ in ("id", "nom_fon", "nom_yoruba"):
                val = item.get(champ)
                if isinstance(val, str) and val.strip():
                    index[self._normaliser_texte(val)] = item

        if not index:
            raise ValueError("Aucun ingrédient exploitable trouvé dans le fichier.")

        return index

    def charger_besoins(self, espece: str, stade: str) -> Dict[str, Any]:
        """
        Charge `data/besoins_animaux.json` et retourne les besoins correspondant
        à l'espèce et au stade demandés.

        Paramètres:
        - espece: ex. "Poulet de chair"
        - stade: ex. "Grower"

        Gestion d'erreurs:
        - espèce non supportée
        - stade non supporté
        - fichier absent/invalide
        """
        data = self._charger_json(self._besoins_file)
        besoins = data.get("besoins")

        if not isinstance(besoins, list) or not besoins:
            raise ValueError("Structure invalide: 'besoins' manquant ou vide.")

        espece_n = self._normaliser_texte(espece)
        stade_n = self._normaliser_texte(stade)

        # Recherche exacte (normalisée)
        for b in besoins:
            if not isinstance(b, dict):
                continue
            if (
                self._normaliser_texte(str(b.get("espece", ""))) == espece_n
                and self._normaliser_texte(str(b.get("stade", ""))) == stade_n
            ):
                return b

        # Messages d'erreur détaillés pour faciliter le debug utilisateur.
        especes = sorted(
            {
                str(b.get("espece"))
                for b in besoins
                if isinstance(b, dict) and b.get("espece") is not None
            }
        )
        stades_espece = sorted(
            {
                str(b.get("stade"))
                for b in besoins
                if isinstance(b, dict)
                and self._normaliser_texte(str(b.get("espece", ""))) == espece_n
            }
        )

        if espece not in especes and espece_n not in {self._normaliser_texte(e) for e in especes}:
            raise ValueError(
                f"Espèce non supportée: '{espece}'. Espèces disponibles: {', '.join(especes)}"
            )

        raise ValueError(
            f"Stade non supporté pour '{espece}': '{stade}'. "
            f"Stades disponibles: {', '.join(stades_espece) if stades_espece else 'aucun'}"
        )

    def optimiser_ration(
        self,
        ingredients_disponibles: List[str],
        espece: str,
        stade: str,
        objectif: str = "equilibre",
    ) -> Dict[str, Any]:
        """
        Algorithme d'optimisation linéaire simplifié (approximation discrète).

        Il cherche une combinaison d'ingrédients disponibles qui :
        - respecte au mieux les besoins nutritionnels,
        - minimise le coût selon l'objectif.

        Paramètres:
        - ingredients_disponibles: liste de noms d'ingrédients fournis par l'utilisateur.
        - espece, stade: contexte animal.
        - objectif: "equilibre" (défaut), "cout_min", "proteines"

        Retour:
        {
          "composition": {ingredient: quantité_kg_sur_100kg},
          "valeur_nutritive": {...},
          "cout_fcfa_kg": ...,
          "cout_total_7_jours": ...,
          "respect_besoins": {
             "energie": bool,
             "proteines": bool,
             "calcium": bool,
             "phosphore": bool
          }
        }

        Gestion d'erreurs:
        - ingrédient inconnu
        - espèce/stade non supporté
        - liste d'ingrédients vide
        """
        if not ingredients_disponibles:
            raise ValueError("Aucun ingrédient fourni pour l'optimisation.")

        # Chargement des bases.
        ingredients_index = self.charger_ingredients()
        besoins = self.charger_besoins(espece, stade)

        # Résolution des ingrédients utilisateurs vers fiches normalisées.
        fiches: Dict[str, Dict[str, Any]] = {}
        inconnus: List[str] = []

        for ing in ingredients_disponibles:
            try:
                fiche = self._resoudre_ingredient(ing, ingredients_index)
                nom_reference = str(fiche.get("nom_fr", ing))
                fiches[nom_reference] = fiche
            except ValueError:
                inconnus.append(ing)

        if inconnus:
            raise ValueError(
                f"Ingrédients inconnus/non résolus: {', '.join(inconnus)}"
            )

        if len(fiches) < 2:
            raise ValueError(
                "Au moins 2 ingrédients valides sont nécessaires pour optimiser une ration."
            )

        # Cibles nutritionnelles (minimales) extraites des besoins.
        cible = {
            "energie_kcal_kg": self._safe_float(besoins.get("energie_kcal_kg"), 0.0),
            "proteines_pct": self._safe_float(besoins.get("proteines_pct"), 0.0),
            "calcium_pct": self._safe_float(besoins.get("calcium_pct"), 0.0),
            "phosphore_pct": self._safe_float(besoins.get("phosphore_pct"), 0.0),
        }

        # Préparation optimisation.
        noms = list(fiches.keys())
        n = len(noms)
        rnd = random.Random(42)  # Reproductible.

        # Fonction de score: plus petit = meilleur.
        def score(comp: Dict[str, float]) -> Tuple[float, Dict[str, float], float]:
            nutr, cout = self._calculer_nutriments_et_cout(comp, fiches)

            # Pénalités de déficit (prioritaires).
            p_energie = max(0.0, (cible["energie_kcal_kg"] - nutr["energie_kcal_kg"]) / max(cible["energie_kcal_kg"], 1))
            p_prot = max(0.0, (cible["proteines_pct"] - nutr["proteines_pct"]) / max(cible["proteines_pct"], 1))
            p_ca = max(0.0, (cible["calcium_pct"] - nutr["calcium_pct"]) / max(cible["calcium_pct"], 1e-6))
            p_p = max(0.0, (cible["phosphore_pct"] - nutr["phosphore_pct"]) / max(cible["phosphore_pct"], 1e-6))

            # Pénalité légère d'excès pour l'équilibre (évite des formules extrêmes).
            e_energie = max(0.0, (nutr["energie_kcal_kg"] - cible["energie_kcal_kg"]) / max(cible["energie_kcal_kg"], 1)) * 0.15
            e_prot = max(0.0, (nutr["proteines_pct"] - cible["proteines_pct"]) / max(cible["proteines_pct"], 1)) * 0.15

            deficit = (p_energie * 1.4) + (p_prot * 1.8) + (p_ca * 1.2) + (p_p * 1.2)

            obj = self._normaliser_texte(objectif)
            if obj == "cout_min":
                total = (deficit * 5000.0) + cout
            elif obj == "proteines":
                bonus_proteines = nutr["proteines_pct"] / max(cible["proteines_pct"], 1)
                total = (deficit * 4000.0) + (cout * 0.7) - (bonus_proteines * 120.0)
            else:
                # "equilibre"
                total = (deficit * 4500.0) + (cout * 0.9) + ((e_energie + e_prot) * 200.0)

            return total, nutr, cout

        # Recherche stochastique simplifiée:
        # - Plusieurs compositions aléatoires normalisées à 100%
        # - Conservation du meilleur score
        best_comp: Dict[str, float] | None = None
        best_nutr: Dict[str, float] | None = None
        best_cout: float = float("inf")
        best_score = float("inf")

        # Nombre d'itérations limité pour rester rapide.
        # Ajusté au nombre d'ingrédients.
        iterations = min(12000, max(2500, n * 1800))

        for _ in range(iterations):
            # Génère des poids aléatoires > 0, puis normalise en %.
            poids = [rnd.random() ** (1.6 if objectif == "cout_min" else 1.0) for _ in range(n)]
            s = sum(poids) or 1.0
            comp = {noms[i]: (poids[i] / s) * 100.0 for i in range(n)}

            # Filtre anti-formules trop dispersées:
            # impose un minimum de 2% par ingrédient et max 80%.
            if any(v < 2.0 for v in comp.values()):
                continue
            if any(v > 80.0 for v in comp.values()):
                continue

            sc, nutr, cout = score(comp)
            if sc < best_score:
                best_score = sc
                best_comp = comp
                best_nutr = nutr
                best_cout = cout

        if not best_comp or not best_nutr:
            raise RuntimeError("Échec de l'optimisation: aucune composition viable trouvée.")

        # Quantités en kg sur une base de 100 kg.
        composition_kg = {k: round(v, 2) for k, v in best_comp.items()}

        # Respect des besoins (tolérance légère de 2%).
        respect_besoins = {
            "energie": best_nutr["energie_kcal_kg"] >= (cible["energie_kcal_kg"] * 0.98),
            "proteines": best_nutr["proteines_pct"] >= (cible["proteines_pct"] * 0.98),
            "calcium": best_nutr["calcium_pct"] >= (cible["calcium_pct"] * 0.98),
            "phosphore": best_nutr["phosphore_pct"] >= (cible["phosphore_pct"] * 0.98),
        }

        # Coût 7 jours basé sur la consommation du stade (g/j/animal) et nb animaux par défaut.
        consommation_g_jour = self._safe_float(besoins.get("consommation_aliment_g_jour"), 0.0)
        cout_total_7_jours = self.calculer_cout(
            ration=composition_kg,
            nombre_animaux=self.nombre_animaux_par_defaut,
            consommation_g_jour=consommation_g_jour,
        )

        return {
            "composition": composition_kg,
            "valeur_nutritive": {
                "energie_kcal_kg": round(best_nutr["energie_kcal_kg"], 2),
                "proteines_pct": round(best_nutr["proteines_pct"], 2),
                "calcium_pct": round(best_nutr["calcium_pct"], 3),
                "phosphore_pct": round(best_nutr["phosphore_pct"], 3),
            },
            "cout_fcfa_kg": round(best_cout, 2),
            "cout_total_7_jours": round(cout_total_7_jours, 2),
            "respect_besoins": respect_besoins,
        }

    def calculer_cout(
        self,
        ration: Dict[str, float],
        nombre_animaux: int,
        consommation_g_jour: float,
    ) -> float:
        """
        Calcule le coût total pour nourrir les animaux pendant 7 jours.

        Paramètres:
        - ration: dict {ingredient: quantité_kg_sur_100kg} OU proportions.
        - nombre_animaux: effectif.
        - consommation_g_jour: consommation moyenne par animal et par jour.

        Retour:
        - coût total FCFA pour 7 jours.
        """
        if not ration:
            raise ValueError("Ration vide, impossible de calculer le coût.")
        if nombre_animaux <= 0:
            raise ValueError("Le nombre d'animaux doit être > 0.")
        if consommation_g_jour <= 0:
            raise ValueError("La consommation g/jour doit être > 0.")

        # Récupère fiches ingrédients.
        ingredients_index = self.charger_ingredients()

        # Résolution des ingrédients de la ration.
        fiches: Dict[str, Dict[str, Any]] = {}
        for nom in ration:
            fiche = self._resoudre_ingredient(nom, ingredients_index)
            nom_ref = str(fiche.get("nom_fr", nom))
            fiches[nom_ref] = fiche

        # Recompose la ration avec les noms de référence.
        ration_ref = {}
        for nom, qte in ration.items():
            fiche = self._resoudre_ingredient(nom, ingredients_index)
            nom_ref = str(fiche.get("nom_fr", nom))
            ration_ref[nom_ref] = self._safe_float(qte, 0.0)

        # Coût par kg d'aliment.
        _, cout_fcfa_kg = self._calculer_nutriments_et_cout(ration_ref, fiches)

        # Consommation totale sur 7 jours (kg).
        kg_7j = (float(nombre_animaux) * float(consommation_g_jour) * 7.0) / 1000.0

        return round(cout_fcfa_kg * kg_7j, 2)

    def generer_recommandations(self, ration: Dict[str, float], espece: str, stade: str) -> List[str]:
        """
        Génère 3 conseils pratiques adaptés à l'espèce et au stade.

        Paramètres:
        - ration: ration proposée (non utilisée pour un calcul lourd ici, mais validée).
        - espece, stade: contexte de production.

        Retour:
        - liste de 3 recommandations concrètes.
        """
        if not ration:
            raise ValueError("Impossible de générer des recommandations sans ration.")
        if not espece or not stade:
            raise ValueError("Espèce et stade sont obligatoires.")

        espece_n = self._normaliser_texte(espece)
        stade_n = self._normaliser_texte(stade)

        # Conseils de base (toujours utiles).
        conseils = [
            "Fais une transition alimentaire progressive sur 3 à 7 jours pour éviter les troubles digestifs.",
            "Stocke les ingrédients au sec, sur palette, et vérifie l'absence de moisissures avant mélange.",
            "Pèse la consommation réelle chaque jour pour ajuster la ration et éviter les pertes.",
        ]

        # Ajustements spécifiques par espèce.
        if "poulet" in espece_n or "pondeuse" in espece_n or "pintade" in espece_n:
            conseils[0] = "Assure un accès permanent à une eau propre; une baisse d'eau réduit vite la performance des volailles."
            if "ponte" in stade_n:
                conseils[1] = "Surveille la qualité de coquille et sécurise l'apport en calcium/phosphore pour maintenir la ponte."
        elif "vache" in espece_n or "zebu" in espece_n or "mouton" in espece_n or "chevre" in espece_n:
            conseils[0] = "Fractionne l'apport concentré et maintiens du fourrage fibreux pour protéger la rumination."
            conseils[1] = "Observe les bouses et l'état corporel chaque semaine pour corriger l'équilibre énergie/protéines."
        elif "tilapia" in espece_n or "poisson" in espece_n:
            conseils[0] = "Distribue en 2 à 3 repas/jour et retire les restes pour préserver la qualité de l'eau."
            conseils[1] = "Ajuste le taux de nourrissage selon la biomasse réelle et la température de l'eau."
        elif "porc" in espece_n or "lapin" in espece_n:
            conseils[0] = "Uniformise bien le mélange pour éviter le tri des particules par les animaux."
            conseils[1] = "Surveille les refus d'aliment et corrige rapidement la densité énergétique si la croissance ralentit."

        return conseils
