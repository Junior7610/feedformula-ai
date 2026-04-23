# Système de Gamification — FeedFormula AI

## 1) Objectif du système

La gamification de FeedFormula AI sert à **motiver l’éleveur chaque jour**, sans le distraire de son vrai objectif : améliorer la performance de son élevage (santé, alimentation, reproduction, revenu).

Le système repose sur :
- des **Points d’Impact (PI)** (expérience utilisateur),
- des **Graines d’Or (GO)** (monnaie virtuelle),
- une **Énergie Solaire** (limite d’actions gamifiées),
- des **Niveaux**, **Trophées**, **Ligues**, **Défis**,
- la mascotte **Aya** (coach motivant).

---

## 2) Principes de conception

1. **Utile avant d’être ludique**  
   Les points récompensent surtout les actions qui améliorent l’élevage.

2. **Simple et transparent**  
   Chaque action affiche : PI gagnés, GO gagnées, progression.

3. **Accessible sur mobile faible**  
   Fonctionne en 3G, mode dégradé si connexion instable.

4. **Anti-spam / anti-triche**  
   Limites journalières, détection d’actions répétées artificielles.

5. **Respect de l’attention**  
   Notifications push intelligentes, max **1 notification/jour** (hors alertes critiques sanitaires).

---

## 3) Système de points (Points d’Impact — PI)

## 3.1 Barème complet des actions

| Domaine | Action utilisateur | PI |
|---|---|---:|
| Onboarding | Profil complété à 100% | 80 |
| Onboarding | Ajout premier élevage | 60 |
| Onboarding | Choix langue locale + voix | 30 |
| NutriCore | Générer une ration valide | 20 |
| NutriCore | Enregistrer une ration appliquée | 35 |
| NutriCore | Mettre à jour stock aliments | 15 |
| VetScan | Envoyer photo pour diagnostic | 25 |
| VetScan | Ajouter symptômes vocaux | 20 |
| VetScan | Confirmer suivi à 24h | 40 |
| ReproTrack | Déclarer chaleur / saillie | 20 |
| ReproTrack | Déclarer mise bas / éclosion | 40 |
| ReproTrack | Enregistrer mortalité (honnêteté data) | 15 |
| PastureMap | Consulter carte pâturage du jour | 10 |
| PastureMap | Appliquer recommandation terrain | 25 |
| FarmManager | Ajouter dépense/recette | 15 |
| FarmManager | Clôturer journal financier du jour | 25 |
| FarmAcademy | Regarder micro-cours (≥ 80%) | 30 |
| FarmAcademy | Réussir quiz (≥ 70%) | 35 |
| FarmCast | Publier contenu utile validé | 20 |
| FarmCommunity | Réponse utile validée par pair | 15 |
| FarmCommunity | Signaler info dangereuse correcte | 20 |
| Marché | Enregistrer prix local du jour | 20 |
| Marché | Acheter via marketplace (trace) | 25 |
| Engagement | Connexion quotidienne (1/jour) | 8 |
| Engagement | Série de 7 jours (bonus) | 70 |
| Collaboration | Inviter un éleveur actif (vérifié) | 50 |

## 3.2 Règles PI
- Plafond PI/jour : **400 PI** (anti-abus).
- Les actions dupliquées en boucle perdent de la valeur (décroissance).
- Les actions critiques (suivi santé, données réelles) gardent une forte valeur.
- En cas de hors-ligne : PI mis en file locale puis synchronisés.

---

## 4) Niveaux (10 niveaux)

| Niveau | Nom | Seuil cumul PI |
|---|---|---:|
| 1 | Semence | 0 |
| 2 | Germination | 500 |
| 3 | Pousse | 1 200 |
| 4 | Floraison | 2 200 |
| 5 | Récolte | 3 500 |
| 6 | Éleveur Bronze | 5 200 |
| 7 | Éleveur Argent | 7 500 |
| 8 | Éleveur Or | 10 500 |
| 9 | Maître Fermier | 14 500 |
| 10 | Légende Afrique | 20 000 |

### Récompenses de passage de niveau
- GO bonus,
- badge visuel,
- message vocal d’Aya,
- déblocage de missions plus avancées.

---

## 5) Les 30 trophées (permanents)

| # | Trophée | Condition |
|---:|---|---|
| 1 | Premier Pas | Créer le compte |
| 2 | Profil Carré | Profil à 100% |
| 3 | Ma Première Ration | 1 ration générée |
| 4 | Nutrition Active | 10 rations générées |
| 5 | Nutrition Expert | 100 rations générées |
| 6 | Œil de Lynx | 1 diagnostic VetScan |
| 7 | Sentinelle Santé | 20 diagnostics VetScan |
| 8 | Suivi Sérieux | 10 suivis 24h validés |
| 9 | Repro Départ | 1 événement reproduction |
| 10 | Repro Pro | 50 événements reproduction |
| 11 | Cartographe Vert | 15 consultations PastureMap |
| 12 | Pâturage Intelligent | 20 recommandations appliquées |
| 13 | Comptable Rural | 30 opérations finance |
| 14 | Trésorier Ferme | 200 opérations finance |
| 15 | Élève Motivé | 5 cours terminés |
| 16 | Formé pour Gagner | 30 cours terminés |
| 17 | Quiz Master | 20 quiz réussis |
| 18 | Voix Locale | 50 interactions vocales |
| 19 | Multi-langue | 3 langues utilisées |
| 20 | Reporter Marché | 30 prix marché partagés |
| 21 | Communauté Solide | 50 réponses utiles validées |
| 22 | Mentor Local | 10 réponses “top utile” |
| 23 | Protecteur Sanitaire | 10 signalements corrects |
| 24 | Inviteur | 3 filleuls actifs |
| 25 | Ambassadeur | 15 filleuls actifs |
| 26 | Série 7 | 7 jours de suite |
| 27 | Série 30 | 30 jours de suite |
| 28 | Série 90 | 90 jours de suite |
| 29 | Résilience | Retour actif après 14 jours d’absence |
| 30 | Légende FeedFormula | Atteindre niveau 10 |

---

## 6) Les 8 ligues (classement hebdomadaire)

| Ligue | Intervalle typique | Règle montée | Règle descente |
|---|---|---|---|
| 1. Terreau | Nouveaux | Top 20% monte | Aucune |
| 2. Savane | Débutants actifs | Top 20% monte | Bas 20% descend |
| 3. Rivière | Réguliers | Top 20% monte | Bas 20% descend |
| 4. Forêt | Confirmés | Top 20% monte | Bas 20% descend |
| 5. Plateau | Performants | Top 15% monte | Bas 20% descend |
| 6. Montagne | Très performants | Top 10% monte | Bas 20% descend |
| 7. Baobab | Élites | Top 5% monte | Bas 20% descend |
| 8. Ubuntu Royale | Excellence | Reste au sommet | Bas 25% descend |

### Règles communes
- Calcul sur PI hebdomadaires.
- Matchmaking par région/langue + niveau proche (équité).
- Récompenses de fin de semaine en GO + badge ligue.

---

## 7) Graines d’Or (GO)

Les GO sont la monnaie virtuelle interne.

## 7.1 Gagner des GO
- Actions utiles validées (santé, nutrition, finance, formation),
- défis et missions,
- bonus de série,
- récompenses de ligue.

## 7.2 Dépenser des GO
- Personnalisation d’Aya (voix/style),
- thèmes visuels hors-ligne,
- tickets “analyse prioritaire” (quota),
- mini-contenus premium FarmAcademy,
- boosts non-pay-to-win (ex: +10% PI max 1/jour).

## 7.3 Règles économiques
- Plafond gain GO/jour pour stabilité.
- Pas de conversion GO → argent réel.
- Journal d’audit anti-fraude.

---

## 8) Énergie Solaire

L’Énergie Solaire limite les actions gamifiées intensives pour éviter l’addiction et le spam.

### Paramètres
- Capacité max : **10 unités**.
- Coût moyen d’une action récompensée : 1 unité.
- Régénération : **1 unité toutes les 90 min**.
- Recharge complète : 15 GO (optionnelle, limitée).

### Règles
- Les actions critiques d’élevage restent possibles même à 0 énergie.
- Sans énergie : PI réduits mais jamais bloquants pour fonctions vitales.

---

## 9) Défis quotidiens et missions

## 9.1 Défis quotidiens (3/jour)
- Exemples :
  - “Enregistrer 1 observation santé”
  - “Mettre à jour 1 prix marché”
  - “Terminer 1 micro-cours”
- Récompense : PI + GO + progression ligue.

## 9.2 Missions hebdomadaires (2 à 5)
- Exemples :
  - “Faire 5 suivis VetScan complets”
  - “Compléter le journal financier 4 jours”
- Récompense plus élevée (GO + badge temporaire).

## 9.3 Génération intelligente
- Personnalisée selon :
  - type d’élevage,
  - saison,
  - historique de l’utilisateur,
  - niveau de difficulté progressif.

---

## 10) Notifications push intelligentes

### Règles globales
- Maximum **1 push/jour** par utilisateur.
- Exceptions critiques :
  - alerte sanitaire urgente,
  - rappel traitement vital,
  - danger météo extrême.

### Priorités
1. Santé animale critique
2. Reproduction urgente
3. Défi du jour
4. Formation recommandée

### Bonnes pratiques
- Message court, dans la langue choisie.
- Heures respectueuses (pas de push nuit par défaut).
- Désinscription facile par catégorie.

---

## 11) Aya — Mascotte et coach IA

Aya est un **épi de maïs doré animé**.  
Rôle : encourager, expliquer, féliciter, sans infantiliser l’éleveur.

## 11.1 États d’Aya
1. **Accueil** (salutation locale)
2. **Coach** (conseils pratiques)
3. **Alerte** (santé/météo/marché)
4. **Fierté** (niveau/trophée gagné)
5. **Soutien** (après échec, ton positif)
6. **Repos** (silencieux si fatigue notifications)
7. **Célébration** (objectif important atteint)
8. **Pédagogie** (explication simple d’un concept)

## 11.2 Règles UX d’Aya
- Ton bienveillant, clair, local.
- Pas de promesse médicale absolue.
- Propose toujours “consulter un vétérinaire” si cas grave.

---

## 12) Événements backend (intégration technique simplifiée)

Chaque action produit un événement :
- `action.recorded`
- `points.awarded`
- `coins.awarded`
- `streak.updated`
- `energy.updated`
- `challenge.progressed`
- `trophy.unlocked`
- `league.updated`
- `notification.queued`

Le backend calcule les récompenses, puis envoie au front :
- nouvel état utilisateur,
- feedback immédiat (PI/GO/bonus),
- animation Aya associée.

---

## 13) Sécurité et anti-triche

1. **Rate limiting** par type d’action.
2. **Déduplication** des événements (idempotence).
3. **Détection d’anomalies** (activité impossible, scripts, spam).
4. **Validation serveur** (jamais confiance totale au client mobile).
5. **Traçabilité** (audit logs des gains PI/GO).
6. **Modération communautaire** sur signalements.

---

## 14) Problèmes potentiels et solutions

| Problème potentiel | Impact | Solution proposée |
|---|---|---|
| Utilisateurs spamment des actions simples | Inflation PI/GO | Plafonds journaliers + décroissance de points |
| Connexion 3G instable | Perte de progression perçue | File locale hors-ligne + sync robuste |
| Injustice dans les ligues | Démotivation | Groupes par niveau/région + recalibrage hebdomadaire |
| Trop de notifications | Désinstallation | Max 1/jour + préférences utilisateur |
| Triche via scripts | Classements faussés | Détection comportementale + suspension progressive |
| Barème trop complexe | Incompréhension | Écran “Pourquoi ces points ?” en langage simple |
| Aya perçue comme gadget | Faible adoption | Aya orientée utilité terrain, pas seulement animation |
| Missions non adaptées au contexte local | Frustration | Génération contextuelle (saison, espèce, région) |
| Surcharge backend en pics | Latence | Queue asynchrone + cache Redis + traitement par batch |
| Données santé sensibles | Risque confiance | Chiffrement, contrôle d’accès, politique de conservation |

---

## 15) Paramètres recommandés (v1)

- PI max/jour : **400**
- GO max/jour : **250**
- Énergie max : **10**
- Régénération : **90 min / unité**
- Push non critique : **1/jour**
- Recalcul ligue : chaque dimanche 23:00 UTC
- Révision barème : toutes les 4 semaines

---

## 16) Résumé

Ce système transforme la progression agricole en parcours motivant :
- **utile** (actions terrain),
- **juste** (règles transparentes),
- **sobre** (pas de spam),
- **adapté à l’Afrique** (langues locales, faible connectivité, réalité terrain).

La priorité reste toujours : **aider l’éleveur à prendre de meilleures décisions, chaque jour**.