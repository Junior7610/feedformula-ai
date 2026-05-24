#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Service ReproTrack de FeedFormula AI.

Fonctions principales :
- enregistrement d'événements reproductifs,
- calcul des prochaines chaleurs,
- calcul de date de mise-bas,
- statistiques de gestation/fertilité,
- alertes 48h avant mise-bas,
- génération d'URL WhatsApp pré-remplies pour les alertes.

Le module est volontairement simple, robuste et facilement intégrable
dans une application FastAPI existante.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

# -----------------------------------------------------------------------------
# Imports locaux
# -----------------------------------------------------------------------------
from database import (
    EvenementReproduction,
    get_db,
    get_user_by_id,
)
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

REPRO_SPECIES_PROFILES: Dict[str, Dict[str, Any]] = {
    "vache": {"nom": "Vache / bovin", "icone": "🐄", "cycle_jours": 21, "gestation_jours": 283, "age_repro": "15-24 mois selon race et état", "ratio_male_femelle": "1 taureau pour 20-30 femelles", "diagnostic": "J+30 à J+60", "sevrage": "6-8 mois", "signes_chaleur": ["agitation", "chevauchement", "mucus clair", "acceptation du mâle"], "prophylaxie": ["déparasitage avant reproduction", "minéraux", "vaccins selon zone", "quarantaine"], "urgence": ["dystocie", "rétention placentaire >12h", "fièvre", "écoulement malodorant"]},
    "chevre": {"nom": "Chèvre / caprin", "icone": "🐐", "cycle_jours": 21, "gestation_jours": 150, "age_repro": "8-12 mois si poids suffisant", "ratio_male_femelle": "1 bouc pour 25-35 femelles", "diagnostic": "J+30 à J+45", "sevrage": "2-3 mois", "signes_chaleur": ["bêlements", "queue agitée", "recherche du mâle", "vulve humide"], "prophylaxie": ["déparasitage", "apport minéral", "vaccination selon zone", "parage si nécessaire"], "urgence": ["avortement", "non délivrance", "mammite", "faiblesse chevreaux"]},
    "mouton": {"nom": "Mouton / ovin", "icone": "🐑", "cycle_jours": 17, "gestation_jours": 147, "age_repro": "8-12 mois si croissance correcte", "ratio_male_femelle": "1 bélier pour 25-40 brebis", "diagnostic": "J+30 à J+45", "sevrage": "2-3 mois", "signes_chaleur": ["recherche du bélier", "agitation", "acceptation", "vulve légèrement gonflée"], "prophylaxie": ["flushing alimentaire", "déparasitage", "minéraux", "vaccination selon contexte"], "urgence": ["toxémie gestation", "dystocie", "agneau faible", "métrite"]},
    "porc": {"nom": "Porc / truie", "icone": "🐷", "cycle_jours": 21, "gestation_jours": 114, "age_repro": "7-8 mois et poids suffisant", "ratio_male_femelle": "1 verrat pour 10-20 truies", "diagnostic": "retour chaleur J+21 ou échographie", "sevrage": "28-45 jours", "signes_chaleur": ["immobilité au verrat", "vulve rouge", "grognements", "baisse appétit"], "prophylaxie": ["désinfection maternité", "vermifuge", "vaccins selon élevage", "contrôle boiteries"], "urgence": ["mise-bas longue", "fièvre post-partum", "écrasement porcelets", "mammite-métrite-agalactie"]},
    "lapin": {"nom": "Lapin", "icone": "🐰", "cycle_jours": 16, "gestation_jours": 31, "age_repro": "5-6 mois selon race", "ratio_male_femelle": "1 mâle pour 8-10 femelles", "diagnostic": "palpation J+10 à J+14 par personne formée", "sevrage": "30-45 jours", "signes_chaleur": ["vulve rouge violacée", "réceptivité", "agitation"], "prophylaxie": ["hygiène cages", "eau propre", "prévention coccidiose", "nid propre"], "urgence": ["diarrhée lapereaux", "mortalité portée", "mammite", "refus d'allaiter"]},
    "poule": {"nom": "Poule pondeuse / reproduction", "icone": "🥚", "cycle_jours": 1, "gestation_jours": 21, "age_repro": "18-22 semaines selon souche", "ratio_male_femelle": "1 coq pour 8-12 poules", "diagnostic": "mirage œufs J+7/J+14", "sevrage": "poussins autonomes au chauffage", "signes_chaleur": ["ponte régulière", "acceptation du coq", "crête rouge"], "prophylaxie": ["vaccins Newcastle/Gumboro selon programme", "désinfection pondoirs", "collecte œufs", "biosécurité"], "urgence": ["chute ponte", "œufs mous", "mortalité poussins", "signes respiratoires"]},
    "pintade": {"nom": "Pintade", "icone": "🦜", "cycle_jours": 1, "gestation_jours": 26, "age_repro": "28-32 semaines", "ratio_male_femelle": "1 mâle pour 4-6 femelles", "diagnostic": "mirage J+7/J+14", "sevrage": "pintadeaux très sensibles 0-6 semaines", "signes_chaleur": ["ponte saisonnière", "activité mâle", "nidification"], "prophylaxie": ["chauffage strict", "eau propre", "protection pluie", "vaccins locaux"], "urgence": ["froid pintadeaux", "diarrhée", "mortalité brutale"]},
    "canard": {"nom": "Canard", "icone": "🦆", "cycle_jours": 1, "gestation_jours": 28, "age_repro": "5-7 mois", "ratio_male_femelle": "1 mâle pour 4-6 femelles", "diagnostic": "mirage J+7/J+14", "sevrage": "4-6 semaines", "signes_chaleur": ["ponte", "accouplement", "nid"], "prophylaxie": ["eau propre", "litière sèche", "protection prédateurs"], "urgence": ["boiterie", "eau sale", "mortalité canetons"]},
    "tilapia": {"nom": "Tilapia", "icone": "🐟", "cycle_jours": 14, "gestation_jours": 7, "age_repro": "3-5 mois selon poids", "ratio_male_femelle": "souvent sexage mâles en grossissement", "diagnostic": "observation frai/alevins", "sevrage": "alevins triés/calibrés", "signes_chaleur": ["nidification", "femelle incubatrice buccale", "alevins"], "prophylaxie": ["qualité eau", "densité", "tri", "alimentation régulière"], "urgence": ["manque oxygène", "mortalité surface", "eau polluée"]},
}


def _profile_for_species(espece: Any) -> Dict[str, Any]:
    key = _species_key(espece)
    aliases = {"bovin": "vache", "vache_laitiere": "vache", "zebu": "vache", "chèvre": "chevre", "caprin": "chevre", "ovin": "mouton", "porcin": "porc", "truie": "porc", "poulet": "poule", "pondeuse": "poule", "volaille": "poule", "clarias": "tilapia", "poisson_chat": "tilapia"}
    key = aliases.get(key, key)
    return REPRO_SPECIES_PROFILES.get(key, REPRO_SPECIES_PROFILES["vache"])


def _repro_score_from_stats(taux: Dict[str, Any], total_events: int) -> Dict[str, Any]:
    gest = float(taux.get("taux_gestation", 0) or 0)
    if total_events < 5:
        score = 45
        label = "Données insuffisantes"
    elif gest >= 80:
        score = 90
        label = "Très bon"
    elif gest >= 60:
        score = 72
        label = "Correct à améliorer"
    else:
        score = 48
        label = "Alerte fertilité"
    return {"score": score, "label": label, "priorite": "enregistrer plus de données" if total_events < 5 else "analyser retours en chaleur et alimentation"}

# -----------------------------------------------------------------------------
# Routeur FastAPI
# -----------------------------------------------------------------------------
router = APIRouter(prefix="/reprotrack", tags=["ReproTrack"])


# -----------------------------------------------------------------------------
# Helpers internes
# -----------------------------------------------------------------------------
def _uuid_str() -> str:
    """Retourne un identifiant texte simple."""
    import uuid

    return str(uuid.uuid4())


def _clean_text(value: Any) -> str:
    """Nettoie une chaîne texte."""
    return " ".join(str(value or "").strip().split())


def _parse_datetime(value: Any) -> datetime:
    """
    Convertit une valeur en datetime.

    Accepte :
    - datetime
    - date
    - chaîne ISO
    - chaîne YYYY-MM-DD
    """
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    if isinstance(value, str):
        txt = value.strip()
        if not txt:
            raise ValueError("Date/heure vide.")
        try:
            return datetime.fromisoformat(txt)
        except Exception:
            try:
                return datetime.strptime(txt, "%Y-%m-%d")
            except Exception as exc:
                raise ValueError(f"Format de date invalide: {txt}") from exc
    raise ValueError("Type de date non supporté.")


def _parse_date(value: Any) -> date:
    """Convertit une valeur en date."""
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        txt = value.strip()
        if not txt:
            raise ValueError("Date vide.")
        try:
            return date.fromisoformat(txt)
        except Exception as exc:
            raise ValueError(f"Format de date invalide: {txt}") from exc
    raise ValueError("Type de date non supporté.")


def _species_key(espece: Any) -> str:
    """Normalise l'espèce pour la logique métier."""
    return _clean_text(espece).lower()


def _whatsapp_text(message: str) -> str:
    """Prépare un texte pour URL WhatsApp."""
    return (
        message.replace("%", "%25")
        .replace(" ", "%20")
        .replace("\n", "%0A")
        .replace("\r", "")
    )


def _build_whatsapp_url(message: str) -> str:
    """Construit une URL WhatsApp pré-remplie."""
    return f"https://wa.me/?text={_whatsapp_text(message)}"


def _repro_expert_notes(espece: str, type_evenement: str) -> List[str]:
    """Conseils terrain courts pour rendre ReproTrack actionnable."""
    espece_norm = _species_key(espece)
    type_norm = _clean_text(type_evenement).lower()
    notes = [
        "Vérifiez l'identification de l'animal et notez l'événement le jour même.",
        "Surveillez l'appétit, le comportement et tout écoulement anormal pendant 48 h.",
    ]
    if type_norm in {"saillie", "insemination", "insémination"}:
        notes.extend(
            [
                "Recontrôlez les chaleurs au cycle suivant pour détecter un éventuel retour.",
                "Évitez le stress, les longs déplacements et les changements brusques de ration après la saillie.",
            ]
        )
    if type_norm in {"mise-bas", "mise bas", "misebas", "velage", "vêlage"}:
        notes.extend(
            [
                "Vérifiez que le nouveau-né respire, tète rapidement et reste au sec.",
                "Contrôlez la mère: délivrance, appétit, température et absence d'écoulement malodorant.",
            ]
        )
    if "vache" in espece_norm or "bovin" in espece_norm:
        notes.append(
            "Pour les bovins, confirmez la gestation avec un technicien si possible entre 45 et 90 jours."
        )
    elif "chevre" in espece_norm or "mouton" in espece_norm:
        notes.append(
            "Pour petits ruminants, améliorez minéraux et fourrages avant la reproduction pour limiter les pertes."
        )
    elif "porc" in espece_norm:
        notes.append(
            "Pour les truies, préparez une case propre et sèche avant la mise-bas prévue."
        )
    return notes[:5]


def _fmt_date(dt: Any) -> str:
    """Formate une date/datetime en JJ/MM/AAAA sans casser si valeur absente."""
    if isinstance(dt, datetime):
        return dt.strftime("%d/%m/%Y")
    if isinstance(dt, date):
        return dt.strftime("%d/%m/%Y")
    try:
        return _parse_datetime(dt).strftime("%d/%m/%Y")
    except Exception:
        return "date à préciser"


def _build_reprotrack_expert_response(evenement: Any) -> Dict[str, Any]:
    """Génère les 7 blocs experts demandés après enregistrement d'un événement."""
    espece = str(getattr(evenement, "espece", "") or "animal")
    animal_id = str(getattr(evenement, "animal_id", "") or "animal non identifié")
    type_evt = str(getattr(evenement, "type_evenement", "") or "événement")
    dt_evt = getattr(evenement, "date_evenement", None) or datetime.now()
    dt_next = getattr(evenement, "date_prevue_prochain", None)
    type_norm = _clean_text(type_evt).lower()
    espece_norm = _species_key(espece)
    gestations = {"vache": 283, "chevre": 150, "mouton": 147, "porc": 114, "lapin": 31}
    cycles = {"vache": 21, "chevre": 21, "mouton": 21, "porc": 21, "lapin": 16}
    cycle = cycles.get(espece_norm, 21)
    gestation = gestations.get(espece_norm, 150)
    if dt_next is None and type_norm in {"saillie", "insemination", "insémination"}:
        dt_next = dt_evt + timedelta(days=gestation)

    prochaines_chaleurs = dt_evt + timedelta(days=cycle)
    fenetre_ia_debut = dt_evt + timedelta(hours=12)
    fenetre_ia_fin = dt_evt + timedelta(hours=18)
    alertes = []
    if isinstance(dt_next, datetime):
        alertes = [
            {
                "type": "ALERTE J-48h",
                "date": (dt_next - timedelta(days=2)).date().isoformat(),
                "message": "Mise-bas dans 2 jours",
                "action": "Préparer case propre, litière sèche, eau, désinfectant nombril et surveillance matin/soir.",
            },
            {
                "type": "ALERTE J-7",
                "date": (dt_next - timedelta(days=7)).date().isoformat(),
                "message": "Surveillance rapprochée",
                "action": "Observer mamelle, vulve, appétit, isolement et signes de travail.",
            },
            {
                "type": "ALERTE J+21",
                "date": (dt_evt + timedelta(days=21)).date().isoformat(),
                "message": "Retour chaleurs possible",
                "action": "Observer agitation, chevauchement, mucus et acceptation du mâle.",
            },
            {
                "type": "ALERTE J+30",
                "date": (dt_evt + timedelta(days=30)).date().isoformat(),
                "message": "Diagnostic gestation recommandé",
                "action": "Contacter technicien IA/vétérinaire pour confirmation si possible.",
            },
        ]
    else:
        alertes = [
            {
                "type": "ALERTE J+21",
                "date": (dt_evt + timedelta(days=21)).date().isoformat(),
                "message": "Retour chaleurs possible",
                "action": "Observer les signes de chaleur au prochain cycle.",
            },
            {
                "type": "ALERTE J+30",
                "date": (dt_evt + timedelta(days=30)).date().isoformat(),
                "message": "Diagnostic gestation recommandé si saillie/IA",
                "action": "Prévoir contrôle avec technicien si une saillie est confirmée.",
            },
        ]

    rapport = f"""━━━ FEEDFORMULA AI — REPROTRACK EXPERT ━━━

1. CONFIRMATION ET ANALYSE DE L'ÉVÉNEMENT
Événement enregistré pour {animal_id}: {type_evt}, espèce {espece}, date {_fmt_date(dt_evt)}. Cette donnée est essentielle car elle fixe le calendrier reproductif. Pour {espece}, un cycle de chaleur d'environ {cycle} jours et une gestation d'environ {gestation} jours sont utilisés comme repères. L'événement paraît exploitable si la date est correcte; il manque encore la race, l'âge, la parité et l'état corporel pour une analyse plus fine.

2. CALCULS AUTOMATIQUES PRÉCIS
Si l'événement correspond à une chaleur, la prochaine chaleur probable est prévue autour du {_fmt_date(prochaines_chaleurs)}. La fenêtre optimale d'insémination se situe environ entre {fenetre_ia_debut.strftime("%d/%m/%Y %H:%M")} et {fenetre_ia_fin.strftime("%d/%m/%Y %H:%M")}, avec une probabilité de conception estimée à 55–70% si l'animal est en bon état corporel. Si l'événement correspond à une saillie/insémination, la date de mise-bas prévue est {_fmt_date(dt_next)} avec marge ±7 jours. Diagnostic gestation recommandé à J+30, transition alimentaire J-21, surveillance rapprochée J-7.

3. ALERTES PROGRAMMÉES
"""
    for alerte in alertes:
        rapport += f"- {alerte['type']} ({alerte['date']}) : {alerte['message']} — {alerte['action']}\n"
    rapport += """
4. CONSEILS NUTRITIONNELS PAR STADE
Gestation précoce: fourrage propre à volonté, eau permanente, complément minéral 30–50 g/jour pour petits ruminants ou 80–120 g/jour bovin selon format. Gestation avancée: augmenter progressivement l'énergie avec son de riz, maïs concassé ou tourteau disponible, sans engraissement excessif. Transition 3 semaines avant mise-bas: ration stable, sel/minéraux, éviter changement brutal. Post-partum: eau tiède/propre, fourrage de qualité, complément protéique local et surveillance appétit/fièvre.

5. INDICATEURS DE FERTILITÉ DU TROUPEAU
À suivre: taux de conception, intervalle vêlage-vêlage, taux de mise-bas, nombre de saillies par conception. Normes indicatives: viser moins de 2 saillies par conception, intervalle vêlage-vêlage proche de 12–14 mois chez bovin bien conduit, taux de mise-bas >80% dans un troupeau bien suivi. Les données actuelles sont insuffisantes pour calculer un taux fiable: enregistrez toutes les chaleurs, saillies, diagnostics et mises-bas.

6. DÉTECTION DES PROBLÈMES REPRODUCTIFS
Retour en chaleur à 21 jours après saillie: suspicion non-gestation, stress, mauvais timing ou infertilité mâle. Avortement: urgence vétérinaire, isoler et conserver informations. Rétention placentaire >12 h, fièvre ou écoulement malodorant: consultation rapide. Métrite post-partum: baisse appétit, fièvre, mauvaise odeur; traitement vétérinaire. Kyste/anœstrus: absence de chaleurs prolongée, besoin diagnostic.

7. PROGRAMME D'AMÉLIORATION GÉNÉTIQUE
Pour viande: privilégier rusticité Borgou, Azawak ou croisements adaptés. Pour lait: améliorer progressivement avec semence laitière adaptée sans perdre la résistance locale. Coût IA estimatif au Bénin: 5 000 à 20 000 FCFA selon zone, semence et technicien. L'amélioration génétique attendue porte sur croissance, lait ou conformation, mais dépend d'abord de l'alimentation, santé et suivi des chaleurs.
━━━ Aya t'accompagne pas à pas 🐄 ━━━"""
    return {
        "rapport_expert": rapport,
        "alertes_programmees": alertes,
        "date_mise_bas_calculee": dt_next.isoformat()
        if isinstance(dt_next, datetime)
        else None,
    }


# -----------------------------------------------------------------------------
# Service métier
# -----------------------------------------------------------------------------
class ReproTrackService:
    """
    Service métier ReproTrack.

    Les paramètres sont simples pour rester compatibles avec une utilisation
    terrain sur mobile.
    """

    CYCLES_CHALEURS = {
        "vache": 21,
        "bovin": 21,
        "vache_laitiere": 21,
        "zebu": 21,
        "chevre": 21,
        "caprin": 21,
        "mouton": 17,
        "ovin": 17,
        "porc": 21,
        "truie": 21,
        "lapin": 16,
        "poule": 1,
        "poulet": 1,
        "pondeuse": 1,
        "pintade": 1,
        "canard": 1,
        "tilapia": 14,
        "clarias": 14,
    }

    GESTATIONS = {
        "vache": 283,
        "bovin": 283,
        "vache_laitiere": 283,
        "zebu": 283,
        "chevre": 150,
        "caprin": 150,
        "mouton": 147,
        "ovin": 147,
        "porc": 114,
        "truie": 114,
        "lapin": 31,
        "poule": 21,
        "poulet": 21,
        "pondeuse": 21,
        "pintade": 26,
        "canard": 28,
        "tilapia": 7,
        "clarias": 7,
    }

    def predire_prochaines_chaleurs(
        self,
        espece: Any,
        date_derniere_chaleur: Any,
    ) -> List[Dict[str, Any]]:
        """
        Calcule les prochaines chaleurs pour une espèce donnée.

        Retour :
        [
            {"date": "...", "probabilite": 0.82, "jours_apres": 21},
            ...
        ]
        """
        espece_norm = _species_key(espece)
        date_base = _parse_datetime(date_derniere_chaleur)
        cycle = self.CYCLES_CHALEURS.get(espece_norm, 21)

        resultats: List[Dict[str, Any]] = []
        for i in range(1, 4):
            prochaine_date = date_base + timedelta(days=cycle * i)
            probabilite = max(0.25, min(0.95, 0.88 - (i - 1) * 0.15))

            # Espèces plus variables sur le terrain
            if espece_norm in {"chevre", "mouton"}:
                probabilite = max(0.2, probabilite - 0.08)

            resultats.append(
                {
                    "date": prochaine_date.date().isoformat(),
                    "probabilite": round(probabilite, 2),
                    "jours_apres": cycle * i,
                }
            )

        return resultats

    def get_profil_reproduction_espece(self, espece: Any) -> Dict[str, Any]:
        """Retourne la fiche reproduction complète d'une espèce."""
        profile = dict(_profile_for_species(espece))
        profile["espece_recherchee"] = _clean_text(espece)
        profile["checklist_repro"] = [
            "Animal identifié clairement",
            "Âge et poids compatibles avec la reproduction",
            "État corporel correct",
            "Déparasitage et minéraux à jour",
            "Logement propre et calme",
            "Registre ReproTrack ouvert",
        ]
        profile["modules_connectes"] = {
            "ReproTrack": "calendrier chaleurs, saillies, gestation et alertes",
            "NutriCore": "ration pré-reproduction, gestation, lactation ou ponte",
            "VetScan": "signes d'urgence, avortement, métrite, dystocie, infertilité",
            "FarmManager": "registre animal, coûts, tâches et rappels",
            "FloraVet": "plantes utiles ou toxiques pour reproduction et lactation",
        }
        return profile

    def generer_plan_reproduction(self, espece: Any, objectif: str = "productivite") -> Dict[str, Any]:
        """Plan reproductif complet, utile pour débutants et fermes structurées."""
        profile = self.get_profil_reproduction_espece(espece)
        return {
            "espece": profile["nom"],
            "objectif": objectif,
            "phases": [
                {"phase": "Préparation", "periode": "J-30 à J0", "actions": ["sélection reproducteurs", "contrôle état corporel", "minéraux", "déparasitage", "quarantaine si nouvel animal"]},
                {"phase": "Détection", "periode": "cycle reproductif", "actions": ["observer signes de chaleur", "noter date et heure", "éviter stress", "préparer mâle/IA"]},
                {"phase": "Accouplement/IA", "periode": "fenêtre optimale", "actions": ["respecter timing", "noter mâle/semence", "surveiller 48h", "éviter changement brutal de ration"]},
                {"phase": "Contrôle gestation/fertilité", "periode": profile.get("diagnostic", "J+30"), "actions": ["observer retour chaleur", "diagnostic si possible", "reprogrammer si échec"]},
                {"phase": "Fin gestation/incubation", "periode": "J-21 à mise-bas/éclosion", "actions": ["transition alimentaire", "préparer aire propre", "surveillance rapprochée", "matériel urgence"]},
                {"phase": "Naissance/éclosion/frai", "periode": "jour J", "actions": ["sécurité nouveau-né", "colostrum/chaleur/eau selon espèce", "désinfection nombril si mammifère", "enregistrement FarmManager"]},
                {"phase": "Post-partum et relance", "periode": "J+1 à sevrage", "actions": ["surveiller mère et jeunes", "prévenir infections", "suivre croissance", "planifier prochain cycle"]},
            ],
            "profil_espece": profile,
            "indicateurs": ["taux de conception", "taux de mise-bas/éclosion", "mortalité jeunes", "retours en chaleur", "intervalle entre cycles", "coût reproduction FCFA"],
        }

    def calculer_date_mise_bas(self, espece: Any, date_saillie: Any) -> Dict[str, Any]:
        """
        Calcule la date prévue de mise-bas selon l'espèce.
        """
        espece_norm = _species_key(espece)
        jours = self.GESTATIONS.get(espece_norm, 150)

        debut = _parse_datetime(date_saillie)
        date_prevue = debut + timedelta(days=jours)
        alerte_48h = date_prevue - timedelta(hours=48)

        return {
            "date_prevue": date_prevue.isoformat(),
            "alerte_48h": alerte_48h.isoformat(),
            "jours_gestation": jours,
        }

    def calculer_taux_gestation(self, user_id: str, db: Session) -> Dict[str, Any]:
        """
        Calcule un taux de gestation indicatif à partir des événements.
        """
        user_id = (user_id or "").strip()
        if not user_id:
            return {
                "taux_gestation": 0.0,
                "confiance": 0.0,
                "total_evenements": 0,
                "expositions": 0,
                "naissances": 0,
            }

        evenements = (
            db.query(EvenementReproduction)
            .filter(EvenementReproduction.user_id == user_id)
            .all()
        )

        total_expositions = 0
        total_success = 0

        for evenement in evenements:
            type_evt = _clean_text(evenement.type_evenement).lower()
            if type_evt in {"saillie", "insemination", "insémination"}:
                total_expositions += 1
            elif type_evt in {"mise-bas", "mise bas", "misebas"}:
                total_success += 1

        if total_expositions == 0:
            return {
                "taux_gestation": 0.0,
                "confiance": 0.0,
                "total_evenements": len(evenements),
                "expositions": 0,
                "naissances": total_success,
            }

        taux = (total_success / max(1, total_expositions)) * 100.0
        confiance = min(0.98, 0.4 + (len(evenements) / 50.0))

        return {
            "taux_gestation": round(taux, 2),
            "confiance": round(confiance, 2),
            "total_evenements": len(evenements),
            "expositions": total_expositions,
            "naissances": total_success,
        }

    def enregistrer_evenement(
        self,
        db: Session,
        user_id: str,
        animal_id: str,
        espece: str,
        type_evenement: str,
        date_evenement: Any,
        date_prevue_prochain: Any = None,
        notes: Optional[str] = None,
    ) -> EvenementReproduction:
        """
        Crée un événement de reproduction en base.
        """
        user = get_user_by_id(db, user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Utilisateur introuvable.",
            )

        dt_evt = _parse_datetime(date_evenement)
        dt_next = (
            _parse_datetime(date_prevue_prochain) if date_prevue_prochain else None
        )

        # Si une saillie / insémination est enregistrée sans date future, on la calcule.
        if dt_next is None and _clean_text(type_evenement).lower() in {
            "saillie",
            "insemination",
            "insémination",
        }:
            dt_next = dt_evt + timedelta(
                days=self.GESTATIONS.get(_species_key(espece), 150)
            )

        evenement = EvenementReproduction(
            id=_uuid_str(),
            user_id=user_id,
            animal_id=_clean_text(animal_id),
            espece=_clean_text(espece),
            type_evenement=_clean_text(type_evenement),
            date_evenement=dt_evt,
            date_prevue_prochain=dt_next,
            notes=_clean_text(notes) or None,
            date_creation=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        db.add(evenement)
        db.commit()
        db.refresh(evenement)
        return evenement

    def lister_evenements(
        self,
        db: Session,
        user_id: str,
        limit: int = 100,
    ) -> List[EvenementReproduction]:
        """Retourne les événements de reproduction d'un utilisateur."""
        limite = max(1, min(int(limit or 100), 500))
        return (
            db.query(EvenementReproduction)
            .filter(EvenementReproduction.user_id == (user_id or "").strip())
            .order_by(EvenementReproduction.date_evenement.desc())
            .limit(limite)
            .all()
        )

    def obtenir_alertes(self, db: Session, user_id: str) -> List[Dict[str, Any]]:
        """
        Construit des alertes ReproTrack à partir des événements.

        Si une mise-bas est attendue dans 48h, un message WhatsApp est ajouté.
        """
        evenements = self.lister_evenements(db, user_id, limit=300)
        alertes: List[Dict[str, Any]] = []

        for evt in evenements:
            evt_any: Any = evt
            type_evt = _clean_text(getattr(evt_any, "type_evenement", "")).lower()
            date_prevue = getattr(evt_any, "date_prevue_prochain", None)
            date_evenement = getattr(evt_any, "date_evenement", None)
            animal_id = getattr(evt_any, "animal_id", "")
            espece = getattr(evt_any, "espece", "")

            # Mise-bas proche
            if (
                type_evt in {"saillie", "insemination", "insémination"}
                and date_prevue is not None
            ):
                alerte_date = date_prevue - timedelta(hours=48)
                message = (
                    f"FeedFormula AI: mise-bas prévue pour {animal_id} ({espece}) "
                    f"autour du {date_prevue.date().isoformat()}.\n"
                    "Préparez l’aire de mise-bas, l’eau propre et surveillez l’animal."
                )

                alertes.append(
                    {
                        "type": "mise-bas_proche",
                        "animal_id": animal_id,
                        "espece": espece,
                        "message": f"Mise-bas probable autour du {date_prevue.date().isoformat()}",
                        "date_alerte": alerte_date.isoformat(),
                        "date_prevue_prochain": date_prevue.isoformat(),
                        "whatsapp_message": message,
                        "whatsapp_url": _build_whatsapp_url(message),
                    }
                )

            # Fenêtres de chaleurs
            if type_evt in {"chaleur", "chaleur observée", "chaleur_observee"}:
                predictions = self.predire_prochaines_chaleurs(espece, date_evenement)
                alertes.append(
                    {
                        "type": "chaleurs",
                        "animal_id": animal_id,
                        "espece": espece,
                        "message": "Fenêtres de chaleur calculées.",
                        "predictions": predictions,
                    }
                )

        return alertes[:20]

    def calendrier_mensuel(self, db: Session, user_id: str) -> Dict[str, Any]:
        """
        Retourne les événements avec métadonnées utiles au calendrier frontend.
        """
        evenements = self.lister_evenements(db, user_id, limit=250)
        items: List[Dict[str, Any]] = []

        for evt in evenements:
            evt_any: Any = evt
            type_evt = _clean_text(getattr(evt_any, "type_evenement", "")).lower()
            date_evenement = getattr(evt_any, "date_evenement", None)
            date_prevue = getattr(evt_any, "date_prevue_prochain", None)
            animal_id = getattr(evt_any, "animal_id", "")
            espece = getattr(evt_any, "espece", "")
            notes = getattr(evt_any, "notes", None)

            item = {
                "id": getattr(evt_any, "id", ""),
                "animal_id": animal_id,
                "espece": espece,
                "type_evenement": getattr(evt_any, "type_evenement", ""),
                "date_evenement": date_evenement.isoformat()
                if date_evenement is not None
                else None,
                "date_prevue_prochain": date_prevue.isoformat()
                if date_prevue is not None
                else None,
                "notes": notes,
            }
            if date_prevue is not None and type_evt in {
                "saillie",
                "insemination",
                "insémination",
            }:
                item["alerte_48h"] = (date_prevue - timedelta(hours=48)).isoformat()
                item["whatsapp"] = {
                    "message": (
                        f"FeedFormula AI: mise-bas prévue pour {animal_id} ({espece}) "
                        f"autour du {date_prevue.date().isoformat()}."
                    ),
                    "url": _build_whatsapp_url(
                        f"FeedFormula AI: mise-bas prévue pour {animal_id} ({espece}) "
                        f"autour du {date_prevue.date().isoformat()}."
                    ),
                }
            items.append(item)

        return {
            "user_id": user_id,
            "total_evenements": len(evenements),
            "evenements": items,
        }

    def animaux_par_user(self, db: Session, user_id: str) -> Dict[str, Any]:
        """Retourne un regroupement des animaux suivis par l'utilisateur."""
        evenements = self.lister_evenements(db, user_id, limit=500)
        animaux: Dict[str, Dict[str, Any]] = {}
        for evt in evenements:
            ident = _clean_text(getattr(evt, "animal_id", "")) or "animal inconnu"
            entry = animaux.setdefault(
                ident,
                {
                    "animal_id": ident,
                    "espece": getattr(evt, "espece", ""),
                    "evenements": 0,
                    "dernier_evenement": None,
                },
            )
            entry["evenements"] += 1
            date_evt = getattr(evt, "date_evenement", None)
            if date_evt is not None:
                current = entry.get("dernier_evenement")
                iso = date_evt.isoformat()
                if current is None or iso > current:
                    entry["dernier_evenement"] = iso
        return {
            "user_id": user_id,
            "total_animaux": len(animaux),
            "animaux": list(animaux.values()),
        }

    def get_calendrier_reproduction(self, db: Session, user_id: str) -> Dict[str, Any]:
        """Alias lisible pour le calendrier reproduction."""
        return self.calendrier_mensuel(db, user_id)

    def get_alertes_reprotrack(self, db: Session, user_id: str) -> List[Dict[str, Any]]:
        """Alias lisible pour les alertes reproduction."""
        return self.obtenir_alertes(db, user_id)

    def calculer_statistiques_troupeau(
        self, user_id: str, db: Session
    ) -> Dict[str, Any]:
        """Alias lisible pour les statistiques du troupeau."""
        return self.calculer_taux_gestation(user_id, db)


# Instance globale
SERVICE = ReproTrackService()


# -----------------------------------------------------------------------------
# Schémas Pydantic
# -----------------------------------------------------------------------------
class ReproTrackEventRequest(BaseModel):
    """Schéma d'entrée pour l'enregistrement d'un événement."""

    user_id: str = Field(..., min_length=3)
    animal_id: str = Field(..., min_length=1)
    espece: str = Field(..., min_length=1)
    type_evenement: str = Field(..., min_length=1)
    date_evenement: str = Field(..., min_length=1)
    date_prevue_prochain: Optional[str] = None
    notes: Optional[str] = None

    @field_validator(
        "user_id", "animal_id", "espece", "type_evenement", "date_evenement"
    )
    @classmethod
    def _strip_required(cls, value: str) -> str:
        txt = _clean_text(value)
        if not txt:
            raise ValueError("Champ obligatoire vide.")
        return txt


class ReproTrackCalendarResponse(BaseModel):
    """Réponse du calendrier ReproTrack."""

    user_id: str
    total_evenements: int
    evenements: List[Dict[str, Any]]


# -----------------------------------------------------------------------------
# Routes FastAPI
# -----------------------------------------------------------------------------
@router.post("/evenement")
def enregistrer_evenement(
    payload: ReproTrackEventRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Enregistre un événement reproductif.
    """
    try:
        evenement = SERVICE.enregistrer_evenement(
            db=db,
            user_id=payload.user_id,
            animal_id=payload.animal_id,
            espece=payload.espece,
            type_evenement=payload.type_evenement,
            date_evenement=payload.date_evenement,
            date_prevue_prochain=payload.date_prevue_prochain,
            notes=payload.notes,
        )
        date_evenement = evenement.date_evenement
        date_prevue_prochain = evenement.date_prevue_prochain
        date_creation = evenement.date_creation
        expert_response = _build_reprotrack_expert_response(evenement)

        return {
            "message": "Événement enregistré avec succès.",
            "conseils_experts": _repro_expert_notes(
                str(evenement.espece), str(evenement.type_evenement)
            ),
            "prochaine_action": (
                "Surveiller un retour en chaleur au prochain cycle."
                if _clean_text(evenement.type_evenement).lower()
                in {"saillie", "insemination", "insémination"}
                else "Mettre à jour l'état de l'animal après observation."
            ),
            "rapport_expert": expert_response.get("rapport_expert"),
            "alertes_programmees": expert_response.get("alertes_programmees", []),
            "date_mise_bas_calculee": expert_response.get("date_mise_bas_calculee"),
            "evenement": {
                "id": evenement.id,
                "user_id": evenement.user_id,
                "animal_id": evenement.animal_id,
                "espece": evenement.espece,
                "type_evenement": evenement.type_evenement,
                "date_evenement": date_evenement.isoformat()
                if date_evenement is not None
                else None,
                "date_prevue_prochain": date_prevue_prochain.isoformat()
                if date_prevue_prochain is not None
                else None,
                "notes": evenement.notes,
                "date_creation": date_creation.isoformat()
                if date_creation is not None
                else None,
            },
        }
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur /reprotrack/evenement: {exc}",
        )


@router.get("/calendrier/{user_id}")
def get_calendrier(user_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Retourne le calendrier ReproTrack.
    """
    try:
        return SERVICE.calendrier_mensuel(db, user_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur /reprotrack/calendrier: {exc}",
        )


@router.get("/alertes/{user_id}")
def get_alertes(user_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Retourne les alertes ReproTrack.
    """
    try:
        alertes = SERVICE.obtenir_alertes(db, user_id)
        return {
            "user_id": user_id,
            "total_alertes": len(alertes),
            "alertes": alertes,
        }
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur /reprotrack/alertes: {exc}",
        )


@router.get("/stats/{user_id}")
def get_stats(user_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Retourne les statistiques reproduction d'un utilisateur.
    """
    try:
        taux = SERVICE.calculer_taux_gestation(user_id, db)
        evenements = SERVICE.lister_evenements(db, user_id, limit=300)

        total_saillies = sum(
            1
            for evt in evenements
            if _clean_text(evt.type_evenement).lower()
            in {"saillie", "insemination", "insémination"}
        )
        total_mises_bas = sum(
            1
            for evt in evenements
            if _clean_text(evt.type_evenement).lower()
            in {"mise-bas", "mise bas", "misebas"}
        )

        return {
            "user_id": user_id,
            "interpretation_experte": (
                "Historique encore limité: continuez à enregistrer chaleurs, saillies et mises-bas pour fiabiliser les statistiques."
                if len(evenements) < 5
                else "Données suffisantes pour commencer à piloter la reproduction par indicateurs."
            ),
            "recommandations": [
                "Enregistrez systématiquement les chaleurs observées, même sans saillie.",
                "Contrôlez les retours en chaleur 18 à 24 jours après saillie selon l'espèce.",
                "Préparez la mise-bas au moins 7 jours avant la date prévue.",
                "Analysez les échecs: retour en chaleur, avortement, alimentation, parasitisme et stress thermique.",
            ],
            "taux_gestation_global": taux.get("taux_gestation", 0.0),
            "confiance_calcul": taux.get("confiance", 0.0),
            "total_evenements": taux.get("total_evenements", len(evenements)),
            "total_saillies": total_saillies,
            "total_mises_bas": total_mises_bas,
            "expositions": taux.get("expositions", 0),
            "naissances": taux.get("naissances", 0),
            "evenements": [
                {
                    "id": evt.id,
                    "animal_id": evt.animal_id,
                    "espece": evt.espece,
                    "type_evenement": evt.type_evenement,
                    "date_evenement": (
                        evt.date_evenement.isoformat()
                        if getattr(evt, "date_evenement", None) is not None
                        else None
                    ),
                    "date_prevue_prochain": (
                        evt.date_prevue_prochain.isoformat()
                        if getattr(evt, "date_prevue_prochain", None) is not None
                        else None
                    ),
                }
                for evt in evenements[:20]
            ],
        }
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur /reprotrack/stats: {exc}",
        )


@router.get("/prochaines-chaleurs")
def get_prochaines_chaleurs(
    espece: str = Query(..., min_length=1),
    date_derniere_chaleur: str = Query(..., min_length=1),
) -> Dict[str, Any]:
    """
    Endpoint utilitaire pour calculer les prochaines chaleurs.
    """
    try:
        return {
            "espece": espece,
            "date_derniere_chaleur": date_derniere_chaleur,
            "predictions": SERVICE.predire_prochaines_chaleurs(
                espece,
                date_derniere_chaleur,
            ),
        }
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Impossible de calculer les prochaines chaleurs: {exc}",
        )


@router.get("/mise-bas")
def get_mise_bas(
    espece: str = Query(..., min_length=1),
    date_saillie: str = Query(..., min_length=1),
) -> Dict[str, Any]:
    """
    Endpoint utilitaire pour calculer la date prévue de mise-bas.
    """
    try:
        return {
            "espece": espece,
            "date_saillie": date_saillie,
            "resultat": SERVICE.calculer_date_mise_bas(espece, date_saillie),
            "profil_espece": SERVICE.get_profil_reproduction_espece(espece),
        }
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Impossible de calculer la date de mise-bas: {exc}",
        )


@router.get("/especes")
def get_repro_especes() -> Dict[str, Any]:
    """Liste les espèces supportées avec profils reproductifs complets."""
    profiles = [dict(value, code=key) for key, value in REPRO_SPECIES_PROFILES.items()]
    return {
        "total": len(profiles),
        "especes": profiles,
        "couverture": "mammifères, volailles et aquaculture",
        "message": "ReproTrack couvre chaleurs, saillies/IA, gestation, mises-bas, éclosions, frai, alertes et indicateurs de fertilité.",
    }


@router.get("/profil-espece/{espece}")
def get_profil_espece(espece: str) -> Dict[str, Any]:
    """Fiche reproduction complète par espèce."""
    return SERVICE.get_profil_reproduction_espece(espece)


@router.get("/plan/{espece}")
def get_plan_reproduction(espece: str, objectif: str = Query("productivite")) -> Dict[str, Any]:
    """Plan reproductif A-Z pour une espèce."""
    return SERVICE.generer_plan_reproduction(espece, objectif)


@router.get("/animaux/{user_id}")
def get_animaux_repro(user_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Retourne les animaux suivis et leur dernier statut reproduction."""
    data = SERVICE.animaux_par_user(db, user_id)
    alerts = SERVICE.obtenir_alertes(db, user_id)
    alert_by_animal = {a.get("animal_id"): a for a in alerts if a.get("animal_id")}
    for animal in data.get("animaux", []):
        animal["alerte_active"] = alert_by_animal.get(animal.get("animal_id"))
        animal["profil_espece"] = SERVICE.get_profil_reproduction_espece(animal.get("espece"))
    return data


@router.get("/performance/{user_id}")
def get_performance_repro(user_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Analyse avancée de performance reproductive du troupeau."""
    taux = SERVICE.calculer_taux_gestation(user_id, db)
    evenements = SERVICE.lister_evenements(db, user_id, limit=500)
    score = _repro_score_from_stats(taux, len(evenements))
    retours_chaleur = sum(1 for e in evenements if _clean_text(e.type_evenement).lower() in {"chaleur", "chaleur observée", "chaleur_observee"})
    avortements = sum(1 for e in evenements if "avort" in _clean_text(e.type_evenement).lower())
    return {
        "user_id": user_id,
        "score_reprotrack": score,
        "taux_gestation": taux,
        "retours_chaleur": retours_chaleur,
        "avortements_signales": avortements,
        "interpretation": "Les données permettent un pilotage reproductif fiable." if len(evenements) >= 5 else "Historique encore faible : enregistrez chaleurs, saillies, diagnostics et mises-bas.",
        "priorites": [
            "Noter toutes les chaleurs même sans saillie.",
            "Contrôler les retours 18-24 jours après saillie selon espèce.",
            "Préparer la mise-bas ou l'éclosion 7 jours avant la date prévue.",
            "Relier reproduction, alimentation et état corporel dans FarmManager.",
        ],
    }


@router.get("/dashboard/{user_id}")
def get_dashboard_reprotrack(user_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Tableau de bord premium ReproTrack."""
    calendar = SERVICE.calendrier_mensuel(db, user_id)
    alerts = SERVICE.obtenir_alertes(db, user_id)
    stats_payload = get_stats(user_id, db)
    performance = get_performance_repro(user_id, db)
    animals = SERVICE.animaux_par_user(db, user_id)
    return {
        "user_id": user_id,
        "statut_global": performance["score_reprotrack"]["label"],
        "score_reprotrack": performance["score_reprotrack"],
        "metriques": {
            "animaux_suivis": animals.get("total_animaux", 0),
            "evenements": calendar.get("total_evenements", 0),
            "alertes": len(alerts),
            "taux_gestation": stats_payload.get("taux_gestation_global", 0),
        },
        "prochaine_action": alerts[0]["message"] if alerts else "Enregistrer la prochaine chaleur, saillie, IA, ponte ou mise-bas observée.",
        "alertes": alerts,
        "calendrier": calendar,
        "stats": stats_payload,
        "performance": performance,
        "animaux": animals.get("animaux", []),
        "guide_rapide": {
            "reproduction": "Observer, dater, confirmer, préparer, enregistrer.",
            "nutrition": "État corporel, minéraux et transition alimentaire conditionnent la fertilité.",
            "sanitaire": "Avortement, fièvre, dystocie ou rétention placentaire = vétérinaire rapidement.",
            "genetique": "Choisir reproducteurs selon objectif : lait, viande, rusticité ou prolificité.",
        },
    }


__all__ = [
    "ReproTrackService",
    "ReproTrackEventRequest",
    "ReproTrackCalendarResponse",
    "SERVICE",
    "router",
]
