/* =========================================================
   FeedFormula AI — Gestionnaire d’assets frontend
   Objectif : centraliser les chemins des médias et appliquer
   des optimisations légères sur les images des pages HTML.
   ========================================================= */

(function () {
  "use strict";

  const ASSET_ROOT = "../assets/";

  function safeString(value) {
    return value === null || value === undefined ? "" : String(value);
  }

  function normalizeAssetName(path) {
    const value = safeString(path).trim();
    if (!value) return "";
    if (/^(https?:)?\/\//i.test(value) || value.startsWith("data:")) {
      return value;
    }
    if (value.startsWith("../assets/") || value.startsWith("./assets/")) {
      return value;
    }
    if (value.startsWith("assets/")) {
      return `../${value}`;
    }
    return `${ASSET_ROOT}${value.replace(/^\.?\/?/, "")}`;
  }

  function applyLazyLoading(root = document) {
    const images = Array.from(root.querySelectorAll("img"));
    images.forEach((img) => {
      if (!img.getAttribute("loading")) {
        img.setAttribute("loading", "lazy");
      }
      if (!img.getAttribute("decoding")) {
        img.setAttribute("decoding", "async");
      }

      const explicitAsset = img.dataset.asset || img.getAttribute("data-asset");
      const explicitSrc =
        img.dataset.assetSrc || img.getAttribute("data-asset-src");
      const source = explicitAsset || explicitSrc;
      if (source && !img.dataset.assetResolved) {
        const resolved = normalizeAssetName(source);
        if (resolved) {
          img.src = resolved;
          img.dataset.assetResolved = "1";
        }
      }
    });
  }

  function preloadAsset(path, as = "image") {
    const resolved = normalizeAssetName(path);
    if (!resolved) return null;
    const exists = Array.from(
      document.head.querySelectorAll("link[rel='preload']"),
    ).some((link) => link.getAttribute("href") === resolved);
    if (exists) return resolved;

    const link = document.createElement("link");
    link.rel = "preload";
    link.href = resolved;
    link.as = as;
    document.head.appendChild(link);
    return resolved;
  }

  function ensureApiBase() {
    const host = window.location.hostname || "";
    const isLocalHost =
      host === "localhost" || host === "127.0.0.1" || host === "0.0.0.0";
    // Important Vercel: les routes backend sont exposées à la racine par le catch-all
    // `/(.*) -> backend/main.py`. Utiliser `/api` casserait les endpoints FastAPI
    // non préfixés (`/generer-ration`, `/vetscan/...`, etc.).
    // On met "/" en production pour que les scripts inline ne retombent pas
    // sur leur ancien fallback local `"/api"`; chaque helper supprime ensuite
    // le slash final, ce qui donne bien des appels `/endpoint`.
    const runtimeBase = isLocalHost ? "http://127.0.0.1:8000" : "/";

    if (!window.API_BASE || !String(window.API_BASE).trim()) {
      window.API_BASE = runtimeBase;
    }
    if (!window.FEEDFORMULA_API_BASE_URL) {
      window.FEEDFORMULA_API_BASE_URL = window.API_BASE;
    }
    if (!window.__FEEDFORMULA_API_BASE_URL__) {
      window.__FEEDFORMULA_API_BASE_URL__ = window.API_BASE;
    }
  }

  const I18N_DICTIONARY = {
    en: {
      "Nos modules IA": "Our AI modules",
      "Nos Services": "Our Services",
      Filtrer: "Filter",
      Tous: "All",
      Santé: "Health",
      Finance: "Finance",
      Formation: "Training",
      "Accéder →": "Open →",
      Disponible: "Available",
      Bientôt: "Soon",
      "Générer ma ration": "Generate my ration",
      "Choisissez votre langue": "Choose your language",
      "Langue préférée": "Preferred language",
      "Poulet de chair": "Broiler chicken",
      "Poule pondeuse": "Laying hen",
      "Vache laitière": "Dairy cow",
      Mouton: "Sheep",
      Chèvre: "Goat",
      Porc: "Pig",
      Tilapia: "Tilapia",
      Lapin: "Rabbit",
      Enregistrer: "Save",
      Actualiser: "Refresh",
      "Événements du jour": "Today's events",
      "Dashboard financier": "Financial dashboard",
      "Générer rapport mensuel": "Generate monthly report",
      "Résultat du diagnostic": "Diagnosis result",
      "Protocole de soins": "Care protocol",
      "Historique récent": "Recent history",
      "Calendrier du mois": "Monthly calendar",
      "Enregistrer un événement": "Save an event",
      "Alertes 48h avant mise-bas": "Alerts 48h before birth",
      "Statistiques du troupeau": "Herd statistics",
      Formations: "Courses",
      Quiz: "Quiz",
      Partager: "Share",
      Accueil: "Home",
      Modules: "Modules",
      Profil: "Profile",
      Classement: "Ranking",
      Abonnement: "Subscription",
      "Payer avec Mobile Money": "Pay with Mobile Money",
      "Comparer les offres": "Compare plans",
      "Votre assistant d'élevage intelligent": "Your smart livestock assistant",
      "Continuez à générer des rations pour progresser":
        "Keep generating rations to progress",
      "Défi du jour": "Daily challenge",
      "Générer une ration équilibrée pour optimiser les performances alimentaires de votre troupeau et gagner des points bonus.":
        "Generate a balanced ration to optimize your herd's feed performance and earn bonus points.",
      "Abonnement et offres premium": "Subscription and premium offers",
      "Comparez les plans, activez Mobile Money et débloquez les langues, modules IA et fonctions premium.":
        "Compare plans, activate Mobile Money and unlock languages, AI modules and premium features.",
      "Parlez à FeedFormula AI": "Talk to FeedFormula AI",
      "Appuyez et parlez": "Press and speak",
      "ou tapez ci-dessous": "or type below",
      "Décrivez vos animaux et vos ingrédients":
        "Describe your animals and ingredients",
      "Votre demande": "Your request",
      "Choisissez une espèce": "Choose a species",
      "Choisissez le stade": "Choose the stage",
      Ingrédients: "Ingredients",
      "Nombre d'animaux": "Number of animals",
      "Choisissez votre objectif": "Choose your goal",
      "Votre ration générée": "Your generated ration",
      "Performances attendues": "Expected performance",
      "Historique local": "Local history",
      "Rations récentes hors ligne": "Recent offline rations",
      "Voir les abonnements": "View subscriptions",
      "Choisir et payer": "Choose and pay",
      "Écouter la ration": "Listen to ration",
      "Sauvegarder dans l'historique": "Save to history",
      "Nos modules IA": "Our AI modules",
      "Huit modules pensés pour vous faire gagner du temps, des points et de meilleures décisions.":
        "Eight modules designed to save time, earn points and make better decisions.",
      "Découvrez vos outils les plus utiles en un coup d’œil":
        "Discover your most useful tools at a glance",
      "Rations adaptées en quelques secondes.": "Adapted rations in seconds.",
      "Diagnostic photo et symptômes rapide.":
        "Fast photo and symptom diagnosis.",
      "Reproduction, alertes et suivi du troupeau":
        "Reproduction, alerts and herd tracking",
      "Photo de l’animal": "Animal photo",
      "Symptômes et espèce": "Symptoms and species",
      "Diagnostiquer maintenant": "Diagnose now",
      "Choisir l’espèce": "Choose species",
      "Décrivez les symptômes observés...": "Describe observed symptoms...",
      "Aucun diagnostic enregistré.": "No diagnosis saved.",
      "Dictez un événement, l’IA le structure et l’enregistre.":
        "Dictate an event, AI structures and saves it.",
      "Dicter un événement": "Dictate an event",
      "Enregistrer l’événement": "Save event",
      "Filtrer par animal": "Filter by animal",
      "Filtrer par type": "Filter by type",
      "Aucun événement.": "No event.",
      "Coût alimentation": "Feed cost",
      Revenus: "Revenue",
      "Marge nette": "Net margin",
    },
    fon: {
      "Nos modules IA": "Mɔdul IA lɛ",
      "Nos Services": "Subɔsubɔ lɛ",
      Filtrer: "Sɛ́",
      Tous: "Lɛ́ kpɔ",
      Santé: "Lãnmɛ",
      Finance: "Hwɛ́",
      Formation: "Nusɔsrɔ̃",
      "Accéder →": "Yì →",
      Disponible: "É wà",
      Bientôt: "É ná wá",
      "Générer ma ration": "Wà núɖuɖu lɛ",
      "Choisissez votre langue": "Sɔ́n gbè tɔn",
      "Langue préférée": "Gbè tɔn",
      "Poulet de chair": "Kpakpa",
      "Poule pondeuse": "Kpakpa ɖùnú",
      "Vache laitière": "Nyɔnu lɛ",
      Mouton: "Lɛngbɔ",
      Chèvre: "Gbɔ",
      Porc: "Kpɔvi",
      Tilapia: "Tílápia",
      Lapin: "Lapɛn",
      Enregistrer: "Wlɛ",
      Actualiser: "Gbɔ̀n",
      "Événements du jour": "Nú wá egbe",
      "Dashboard financier": "Hwɛ́ kpɔ́n",
      "Résultat du diagnostic": "Nú xɔ́ jlɛ",
      "Protocole de soins": "Nugbɔ̀n lɛ",
      "Historique récent": "Nú xɔ́ hwenu",
      Accueil: "Xɔ̀gbé",
      Modules: "Mɔdul lɛ",
      Profil: "Profili",
      Classement: "Xexlẽ",
      Abonnement: "Abɔnmã",
      "Votre assistant d'élevage intelligent": "Nugbɔ̀n azɔ́n lɛ tɔn",
      "Continuez à générer des rations pour progresser":
        "Wà núɖuɖu lɛ bɔ́ nà yì wé",
      "Défi du jour": "Azɔ́n egbe",
      "Générer une ration équilibrée pour optimiser les performances alimentaires de votre troupeau et gagner des points bonus.":
        "Wà núɖuɖu ɖagbe nú lãn lɛ bɔ́ nà xweji lɛ.",
      "Abonnement et offres premium": "Abɔnmã kple nugbɔ̀n lɛ",
      "Comparez les plans, activez Mobile Money et débloquez les langues, modules IA et fonctions premium.":
        "Kpɔ́n plan lɛ, zã Mobile Money, bɔ́ xwe gbè kple mɔdul IA lɛ.",
      "Parlez à FeedFormula AI": "Dɔ̀ kple FeedFormula AI",
      "Appuyez et parlez": "Tɛ́ bɔ́ dɔ̀",
      "ou tapez ci-dessous": "abi sɛ́ nù dó",
      "Décrivez vos animaux et vos ingrédients": "Gblɔ lãn tɔn kple núɖuɖu tɔn",
      "Votre demande": "Nugbɔ̀n tɔn",
      "Choisissez une espèce": "Sɔ́n lãn ɖé",
      "Choisissez le stade": "Sɔ́n hwenu",
      Ingrédients: "Núɖuɖu lɛ",
      "Nombre d'animaux": "Lãn xexlẽ",
      "Choisissez votre objectif": "Sɔ́n taɖo tɔn",
      "Votre ration générée": "Núɖuɖu tɔn",
      "Performances attendues": "Nú nà wá",
      "Historique local": "Nú xɔ́ hwenu",
      "Rations récentes hors ligne": "Núɖuɖu xoxo lɛ",
      "Voir les abonnements": "Kpɔ́n abɔnmã lɛ",
      "Choisir et payer": "Sɔ́n bɔ́ xɔ̀ hwɛ́",
      "Écouter la ration": "Sè núɖuɖu",
      "Sauvegarder dans l'historique": "Wlɛ dó xɔ́ hwenu",
      "Huit modules pensés pour vous faire gagner du temps, des points et de meilleures décisions.":
        "Mɔdul lɛ ná kplɔ́n mi, ná ɖu hwenu, ná xweji lɛ.",
      "Découvrez vos outils les plus utiles en un coup d’œil":
        "Kpɔ́n nugbɔ̀n tɔn lɛ kpɔ",
      "Rations adaptées en quelques secondes.":
        "Núɖuɖu ɖagbe wá kpo xwevi kpɔ.",
      "Diagnostic photo et symptômes rapide.": "Kpɔ́n foto kple awu lɛ kpo.",
      "Reproduction, alertes et suivi du troupeau":
        "Jiji, kpɔ́nkpɔ́n kple lɛn lɛ",
      "Photo de l’animal": "Lãn foto",
      "Symptômes et espèce": "Awu lɛ kple lãn",
      "Diagnostiquer maintenant": "Kpɔ́n awu lɛ fifí",
      "Choisir l’espèce": "Sɔ́n lãn",
      "Décrivez les symptômes observés...": "Gblɔ awu lɛ...",
      "Aucun diagnostic enregistré.": "Kpɔ́n awu ɖé wɛ aɖo gbè.",
      "Dictez un événement, l’IA le structure et l’enregistre.":
        "Gblɔ nú wá, IA ná ɖo é gbè.",
      "Dicter un événement": "Gblɔ nú wá",
      "Enregistrer l’événement": "Wlɛ nú wá",
      "Filtrer par animal": "Sɛ́ kple lãn",
      "Filtrer par type": "Sɛ́ kple wunmɛ",
      "Aucun événement.": "Nú wá ɖé aɖo gbè.",
      "Coût alimentation": "Núɖuɖu hwɛ́",
      Revenus: "Hwɛ́ wá",
      "Marge nette": "Maji wɛ",
    },
    yor: {
      "Nos modules IA": "Àwọn module IA wa",
      "Nos Services": "Ìṣẹ́ wa",
      Filtrer: "Yàn",
      Tous: "Gbogbo",
      Santé: "Ìlera",
      Finance: "Ìṣúná",
      Formation: "Ẹ̀kọ́",
      "Accéder →": "Ṣí →",
      Disponible: "Wà",
      Bientôt: "Laipẹ",
      "Générer ma ration": "Ṣẹda oúnjẹ mi",
      "Choisissez votre langue": "Yan èdè rẹ",
      "Langue préférée": "Èdè ayanfẹ́",
      "Poulet de chair": "Adìẹ eran",
      "Poule pondeuse": "Adìẹ ẹyin",
      "Vache laitière": "Màlúù wàrà",
      Mouton: "Àgùntàn",
      Chèvre: "Ewúrẹ́",
      Porc: "Ẹlẹ́dẹ̀",
      Tilapia: "Tilapia",
      Lapin: "Ehoro",
      Enregistrer: "Fipamọ́",
      Actualiser: "Tún ṣe",
      Accueil: "Ilé",
      Modules: "Module",
      Profil: "Profaili",
      Classement: "Ìpele",
      Abonnement: "Ìforúkọsílẹ̀",
      "Votre assistant d'élevage intelligent": "Olùrànlọ́wọ́ ẹran ọlọ́gbọ́n",
      "Continuez à générer des rations pour progresser":
        "Máa ṣẹda oúnjẹ kí o lè tẹ̀síwájú",
      "Défi du jour": "Ìpenija ojoojúmọ́",
      "Générer une ration équilibrée pour optimiser les performances alimentaires de votre troupeau et gagner des points bonus.":
        "Ṣẹda oúnjẹ tó dọ́gba fún ìdàgbàsókè ẹran rẹ.",
      "Parlez à FeedFormula AI": "Bá FeedFormula AI sọ̀rọ̀",
      "Appuyez et parlez": "Tẹ̀ kí o sọ̀rọ̀",
      "ou tapez ci-dessous": "tàbí kọ sí isalẹ",
      "Décrivez vos animaux et vos ingrédients": "Ṣàlàyé ẹranko àti eroja rẹ",
      "Votre demande": "Ìbéèrè rẹ",
      "Choisissez une espèce": "Yan ẹ̀yà kan",
      "Choisissez le stade": "Yan ìpele",
      Ingrédients: "Eroja",
      "Nombre d'animaux": "Ìye ẹranko",
      "Choisissez votre objectif": "Yan àfojúsùn rẹ",
      "Votre ration générée": "Oúnjẹ tí a ṣẹda fún ọ",
      "Performances attendues": "Abajade tí a retí",
      "Voir les abonnements": "Wo ìforúkọsílẹ̀",
      "Choisir et payer": "Yan kí o sanwo",
      "Écouter la ration": "Gbọ́ oúnjẹ",
      "Sauvegarder dans l'historique": "Fi pamọ́ sínú ìtàn",
      "Huit modules pensés pour vous faire gagner du temps, des points et de meilleures décisions.":
        "Àwọn module mẹ́jọ fún ìgbà pamọ́, àmì àti ìpinnu dáadáa.",
      "Rations adaptées en quelques secondes.": "Oúnjẹ tó yẹ ní ìṣẹ́jú díẹ̀.",
      "Diagnostic photo et symptômes rapide.":
        "Àyẹ̀wò fọ́tò àti àmì àìsàn kíákíá.",
      "Photo de l’animal": "Fọ́tò ẹranko",
      "Symptômes et espèce": "Àmì àìsàn àti ẹ̀yà",
      "Diagnostiquer maintenant": "Ṣàyẹ̀wò báyìí",
      "Choisir l’espèce": "Yan ẹ̀yà",
      "Historique récent": "Ìtàn tuntun",
    },
    den: {
      "Nos modules IA": "Modulu IA ya",
      "Nos Services": "Goyey ya",
      Filtrer: "Suuba",
      Tous: "Kul",
      Santé: "Lafiya",
      Finance: "Nooru",
      Formation: "Cawandiyan",
      "Accéder →": "Fatta →",
      Disponible: "Ga bara",
      Bientôt: "Kayna",
      "Générer ma ration": "Ration te",
      "Choisissez votre langue": "Ni šenni suuba",
      "Langue préférée": "Šenni suubante",
      Enregistrer: "Gaabu",
      Actualiser: "Taaga",
      Accueil: "Sintin",
      Modules: "Modulu",
      Profil: "Profil",
      Classement: "Kanandi",
    },
    adj: {},
    gej: {},
    gen: {},
    yom: {},
    bba: {},
    baa: {},
    fr: {},
  };

  I18N_DICTIONARY.adj = I18N_DICTIONARY.fon;
  I18N_DICTIONARY.gej = I18N_DICTIONARY.fon;
  I18N_DICTIONARY.gen = I18N_DICTIONARY.fon;
  I18N_DICTIONARY.yom = I18N_DICTIONARY.fon;
  I18N_DICTIONARY.bba = I18N_DICTIONARY.fon;
  I18N_DICTIONARY.baa = I18N_DICTIONARY.fon;

  function getStoredLanguage() {
    try {
      return (
        localStorage.getItem("feedformula_language_v3") ||
        localStorage.getItem("feedformula_language_v1") ||
        document.documentElement.lang ||
        "fr"
      ).toLowerCase();
    } catch (error) {
      return "fr";
    }
  }

  function getCanonicalSource(value) {
    const normalized = safeString(value).replace(/\s+/g, " ").trim();
    if (!normalized) return "";
    if (Object.prototype.hasOwnProperty.call(I18N_DICTIONARY.fr, normalized)) {
      return normalized;
    }
    const sourceKeys = Object.keys(I18N_DICTIONARY.en || {}).concat(
      Object.keys(I18N_DICTIONARY.fon || {}),
    );
    return sourceKeys.includes(normalized) ? normalized : "";
  }

  function translateTextNode(node, dictionary, lang) {
    const original = safeString(node.textContent).replace(/\s+/g, " ").trim();
    if (!original) return;
    if (!node.parentElement) return;
    if (
      ["SCRIPT", "STYLE", "TEXTAREA", "INPUT", "OPTION"].includes(
        node.parentElement.tagName,
      )
    )
      return;
    const canonical = getCanonicalSource(original);
    if (canonical) node.parentElement.dataset.i18nOriginal = canonical;
    if (!node.parentElement.dataset.i18nOriginal) {
      node.parentElement.dataset.i18nOriginal = original;
    }
    const source = node.parentElement.dataset.i18nOriginal || original;
    if (lang === "fr") {
      if (original !== source)
        node.textContent = node.textContent.replace(original, source);
      return;
    }
    if (dictionary[source]) {
      node.textContent = node.textContent.replace(original, dictionary[source]);
      return;
    }
    const entries = Object.entries(dictionary).sort(
      (a, b) => b[0].length - a[0].length,
    );
    let translated = source;
    entries.forEach(([from, to]) => {
      if (from && translated.includes(from)) {
        translated = translated.split(from).join(to);
      }
    });
    if (translated !== source) {
      node.textContent = node.textContent.replace(original, translated);
    }
  }

  function translateAttributes(root, dictionary, lang) {
    Array.from(
      root.querySelectorAll(
        "input[placeholder], textarea[placeholder], [aria-label], option",
      ),
    ).forEach((el) => {
      if (el.hasAttribute("placeholder")) {
        const original =
          el.dataset.i18nPlaceholderOriginal ||
          el.getAttribute("placeholder") ||
          "";
        el.dataset.i18nPlaceholderOriginal = original;
        if (lang === "fr") el.setAttribute("placeholder", original);
        else if (dictionary[original])
          el.setAttribute("placeholder", dictionary[original]);
      }
      if (el.hasAttribute("aria-label")) {
        const original =
          el.dataset.i18nAriaOriginal || el.getAttribute("aria-label") || "";
        el.dataset.i18nAriaOriginal = original;
        if (lang === "fr") el.setAttribute("aria-label", original);
        else if (dictionary[original])
          el.setAttribute("aria-label", dictionary[original]);
      }
      if (el.tagName === "OPTION") {
        const original =
          el.dataset.i18nOriginal || safeString(el.textContent).trim();
        el.dataset.i18nOriginal = original;
        if (lang === "fr") el.textContent = original;
        else if (dictionary[original]) el.textContent = dictionary[original];
      }
    });
  }

  function translatePage(lang = getStoredLanguage(), root = document.body) {
    const normalized = String(lang || "fr").toLowerCase();
    const dictionary =
      I18N_DICTIONARY[normalized] ||
      I18N_DICTIONARY[normalized.replace("yo", "yor")] ||
      I18N_DICTIONARY.fr;
    if (!root || !dictionary) return;
    document.documentElement.lang = normalized;
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    const nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    nodes.forEach((node) => translateTextNode(node, dictionary, normalized));
    translateAttributes(root, dictionary, normalized);
  }

  function bindGlobalLanguageControls() {
    document.addEventListener("change", (event) => {
      const target = event.target;
      if (
        !target ||
        !target.matches ||
        !target.matches("[data-language-select], .language-select")
      )
        return;
      const lang = String(target.value || "fr").toLowerCase();
      try {
        localStorage.setItem("feedformula_language_v3", lang);
      } catch (error) {}
      translatePage(lang);
    });

    document.addEventListener("click", (event) => {
      const button =
        event.target && event.target.closest
          ? event.target.closest("[data-lang], [data-lang-button]")
          : null;
      if (!button) return;
      const lang = String(
        button.dataset.lang || button.dataset.value || "fr",
      ).toLowerCase();
      window.setTimeout(() => translatePage(lang), 30);
    });
  }

  function register(root = document) {
    ensureApiBase();
    applyLazyLoading(root);
    bindGlobalLanguageControls();
    window.setTimeout(() => translatePage(getStoredLanguage()), 0);

    const observer = new MutationObserver((mutations) => {
      if (!mutations.some((mutation) => mutation.addedNodes.length)) return;
      window.clearTimeout(observer._ffTimer);
      observer._ffTimer = window.setTimeout(
        () => translatePage(getStoredLanguage()),
        80,
      );
    });
    if (document.body && !document.body.dataset.i18nObserverReady) {
      observer.observe(document.body, { childList: true, subtree: true });
      document.body.dataset.i18nObserverReady = "1";
    }

    const criticalAssets = [
      "logo_feedformula_minimal.png",
      "logo_principal.png",
      "aya_joie.png",
      "splash_screen.png",
    ];
    criticalAssets.forEach((asset) => preloadAsset(asset, "image"));
  }

  window.FFAssets = {
    asset: normalizeAssetName,
    applyLazyLoading,
    preloadAsset,
    register,
    translatePage,
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => register());
  } else {
    register();
  }
})();
