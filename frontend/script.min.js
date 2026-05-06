/* =========================================================
   FeedFormula AI — Script global
   Gestion de toutes les pages, interactions et animations
   Commentaires en français pour faciliter la maintenance
   ========================================================= */

(function () {
  "use strict";

  /* ---------------------------------------------------------
     Constantes globales
     --------------------------------------------------------- */

  const STORAGE_KEYS = {
    state: "feedformula_state_v3",
    rationHistory: "feedformula_ration_history_v3",
    vetHistory: "feedformula_vet_history_v3",
    reproHistory: "feedformula_repro_history_v3",
    profile: "feedformula_profile_v3",
    academy: "feedformula_academy_v3",
    league: "feedformula_league_v3",
    language: "feedformula_language_v3",
    tutorial: "feedformula_tutorial_v3",
  };

  const APP = {
    points: 0,
    level: 1,
    selectedLanguage: "fr",
    selectedSpecies: "",
    selectedStage: "",
    selectedObjective: "equilibre",
    selectedIngredients: [],
    animalsCount: 50,
    online: navigator.onLine,
    ayaMood: "joy",
    ayaMessage: "Bienvenue sur FeedFormula AI !",
    rationChart: null,
    skillPoints: 0,
    badges: [],
    currentPage: detectPage(),
  };

  const SPECIES_CONFIG = {
    poulet: {
      label: "Poulet chair",
      icon: "🐔",
      stages: ["Démarrage", "Croissance", "Finition"],
      baseCost: 620,
      ingredients: ["maïs", "tourteau soja", "son de blé", "huile", "lysine"],
      profileKey: "poulet",
    },
    pondeuse: {
      label: "Poule pondeuse",
      icon: "🥚",
      stages: ["Pré-ponte", "Ponte active", "Fin de ponte"],
      baseCost: 540,
      ingredients: [
        "maïs",
        "tourteau soja",
        "calcium",
        "son de riz",
        "phosphate",
      ],
      profileKey: "pondeuse",
    },
    pintade: {
      label: "Pintade",
      icon: "🦜",
      stages: ["Démarrage", "Croissance", "Production"],
      baseCost: 590,
      ingredients: [
        "maïs",
        "tourteau arachide",
        "son de blé",
        "minéral",
        "huile",
      ],
      profileKey: "pintade",
    },
    vache: {
      label: "Vache laitière",
      icon: "🐄",
      stages: ["Vêlage", "Lactation", "Tarissement"],
      baseCost: 780,
      ingredients: [
        "maïs",
        "tourteau coton",
        "herbe sèche",
        "son de blé",
        "minéral",
      ],
      profileKey: "vache",
    },
    mouton: {
      label: "Mouton",
      icon: "🐑",
      stages: ["Agneau", "Croissance", "Engraissement"],
      baseCost: 470,
      ingredients: [
        "maïs",
        "son de riz",
        "tourteau soja",
        "sels minéraux",
        "herbe",
      ],
      profileKey: "mouton",
    },
    chevre: {
      label: "Chèvre",
      icon: "🐐",
      stages: ["Chevreau", "Croissance", "Lactation"],
      baseCost: 490,
      ingredients: [
        "maïs",
        "tourteau soja",
        "feuilles sèches",
        "son de blé",
        "minéral",
      ],
      profileKey: "chevre",
    },
    porc: {
      label: "Porc",
      icon: "🐷",
      stages: ["Démarrage", "Croissance", "Finition"],
      baseCost: 730,
      ingredients: [
        "maïs",
        "tourteau soja",
        "son de blé",
        "acides aminés",
        "pré-mix",
      ],
      profileKey: "porc",
    },
    tilapia: {
      label: "Tilapia",
      icon: "🐟",
      stages: ["Alevin", "Croissance", "Finition"],
      baseCost: 650,
      ingredients: [
        "farine poisson",
        "maïs",
        "son de riz",
        "huile",
        "vitamines",
      ],
      profileKey: "tilapia",
    },
  };

  const LANGUAGE_LABELS = {
    fr: "Français",
    fon: "Fɔ̀n",
    yor: "Yorùbá",
    den: "Dendi",
    en: "English",
  };

  const LOCALIZED_HINTS = {
    fr: "Décrivez vos animaux et vos ingrédients...",
    fon: "Xɔ̀ yì xɔ̀n tɔ́n wá á kplọn...",
    yor: "Ṣàpèjúwe ẹranko rẹ àti àwọn eroja rẹ...",
    den: "Baa bo kulu wono nda gandi...",
    en: "Describe your animals and ingredients...",
  };

  const INGREDIENT_SUGGESTIONS = [
    "maïs",
    "tourteau soja",
    "tourteau arachide",
    "son de blé",
    "son de riz",
    "huile",
    "lysine",
    "méthionine",
    "calcium",
    "phosphate",
    "pré-mix",
    "farine poisson",
    "tourteau coton",
    "mineraux",
    "herbe sèche",
    "feuilles séchées",
    "manioc",
    "patate douce",
    "drêche de brasserie",
    "coquilles",
    "sel",
    "vitamines",
    "acides aminés",
    "paille",
  ];

  const FARM_MODULES = [
    {
      id: "nutricore",
      icon: "🌾",
      title: "NutriCore",
      description: "Rations équilibrées en quelques secondes",
      category: "Santé",
      points: "+10 🌟",
      available: true,
    },
    {
      id: "vetscan",
      icon: "🩺",
      title: "VetScan",
      description: "Diagnostique photo et symptômes",
      category: "Santé",
      points: "+20 🌟",
      available: true,
    },
    {
      id: "reprotrack",
      icon: "📅",
      title: "ReproTrack",
      description: "Suivi reproduction et fertilité",
      category: "Santé",
      points: "+10 🌟",
      available: true,
    },
    {
      id: "farmacademy",
      icon: "📘",
      title: "FarmAcademy",
      description: "Formations guidées et quiz",
      category: "Formation",
      points: "+20 🌟",
      available: true,
    },
    {
      id: "classement",
      icon: "🏆",
      title: "Classement",
      description: "Compare ton rang en direct",
      category: "Finance",
      points: "+10 🌟",
      available: true,
    },
    {
      id: "profil",
      icon: "👤",
      title: "Profil",
      description: "Points, trophées et série",
      category: "Formation",
      points: "+10 🌟",
      available: true,
    },
    {
      id: "modules",
      icon: "📦",
      title: "Modules",
      description: "Tous les services du réseau",
      category: "Formation",
      points: "+10 🌟",
      available: true,
    },
    {
      id: "boutique",
      icon: "🎁",
      title: "Boutique",
      description: "Récompenses et graines d’or",
      category: "Finance",
      points: "+20 🌟",
      available: false,
    },
  ];

  const PROFILE_TROPHIES = [
    {
      name: "Premier mélange",
      icon: "🌱",
      unlocked: true,
      condition: "Générer 1 ration",
    },
    {
      name: "Rationnaire",
      icon: "🌾",
      unlocked: true,
      condition: "Générer 5 rations",
    },
    {
      name: "Économe",
      icon: "💰",
      unlocked: true,
      condition: "Économiser 10 000 FCFA",
    },
    {
      name: "Gardien",
      icon: "🏥",
      unlocked: false,
      condition: "Diagnostiquer 10 animaux",
    },
    {
      name: "Série d’or",
      icon: "🔥",
      unlocked: true,
      condition: "7 jours consécutifs",
    },
    {
      name: "Champion local",
      icon: "🏆",
      unlocked: false,
      condition: "Top 10 de ta commune",
    },
    {
      name: "Aqua expert",
      icon: "🐟",
      unlocked: false,
      condition: "Créer 3 rations poissons",
    },
    {
      name: "Repro maître",
      icon: "📅",
      unlocked: false,
      condition: "Suivre 5 animaux reproducteurs",
    },
    {
      name: "Farm prof",
      icon: "📘",
      unlocked: true,
      condition: "Terminer 1 leçon",
    },
    {
      name: "Foudre",
      icon: "⚡",
      unlocked: false,
      condition: "Résoudre un diagnostic en moins de 30s",
    },
    {
      name: "Marché malin",
      icon: "🛒",
      unlocked: false,
      condition: "Comparer 20 ingrédients",
    },
    {
      name: "Vision claire",
      icon: "👁️",
      unlocked: true,
      condition: "Analyser 1 photo VetScan",
    },
    {
      name: "Maîtrise verte",
      icon: "🌳",
      unlocked: false,
      condition: "Atteindre le niveau 10",
    },
    {
      name: "Mélange parfait",
      icon: "🎯",
      unlocked: false,
      condition: "Atteindre 100% équilibre",
    },
    {
      name: "Off line héros",
      icon: "📵",
      unlocked: true,
      condition: "Utiliser l’app hors ligne",
    },
    {
      name: "Ambassadeur",
      icon: "🤝",
      unlocked: false,
      condition: "Inviter 5 éleveurs",
    },
    {
      name: "Réflexe Aya",
      icon: "✨",
      unlocked: true,
      condition: "Consulter Aya 10 fois",
    },
    {
      name: "Top local",
      icon: "🥇",
      unlocked: false,
      condition: "1re place mensuelle",
    },
    {
      name: "Champion départemental",
      icon: "🥈",
      unlocked: false,
      condition: "Top 3 départemental",
    },
    {
      name: "Champion national",
      icon: "🥉",
      unlocked: false,
      condition: "Top 3 national",
    },
    {
      name: "Lactation",
      icon: "🥛",
      unlocked: false,
      condition: "Optimiser une ration bovine",
    },
    {
      name: "Croissance",
      icon: "📈",
      unlocked: true,
      condition: "Monter de niveau",
    },
    {
      name: "Zéro perte",
      icon: "🛡️",
      unlocked: false,
      condition: "Aucun jour manqué pendant 30 jours",
    },
    {
      name: "Météo stable",
      icon: "☀️",
      unlocked: false,
      condition: "Suivre le calendrier ReproTrack",
    },
    {
      name: "Coach expert",
      icon: "🧠",
      unlocked: false,
      condition: "Finir 3 modules formation",
    },
    {
      name: "Étoile dorée",
      icon: "⭐",
      unlocked: true,
      condition: "Accumuler 100 🌟",
    },
    {
      name: "Super éleveur",
      icon: "🐮",
      unlocked: false,
      condition: "Utiliser toutes les fonctions",
    },
    {
      name: "Conseiller communautaire",
      icon: "👥",
      unlocked: false,
      condition: "Aider 10 autres éleveurs",
    },
    {
      name: "Niveau vétéran",
      icon: "🎖️",
      unlocked: false,
      condition: "Atteindre 5000 points",
    },
    {
      name: "Sage de l’alimentation",
      icon: "📖",
      unlocked: false,
      condition: "Lire 5 conseils",
    },
  ];

  const AYA_IMAGES = {
    joy: "assets/aya_joie.png",
    celebration: "assets/aya_celebration.png",
    sad: "assets/aya_triste.png",
    full: "assets/aya_etats_complets.png",
    animals: "assets/aya_avec_animaux.png",
  };

  const DEFAULT_PROFILE = {
    name: "Awa K.",
    region: "Borgou, Bénin",
    commune: "Nikki",
    joinedAt: "2024-02-14",
    avatar: "",
    points: 1240,
    levelName: "🌾 Tige",
    nextLevelPoints: 1500,
    stats: {
      rations: 38,
      savingsFcfa: 167500,
      diagnosedAnimals: 12,
      streak: 12,
      trophies: 8,
      daysUsed: 64,
    },
    bestStreak: 19,
    rescueSeeds: 14,
    classement: {
      commune: { rank: 7, total: 143 },
      departement: { rank: 29, total: 812 },
      national: { rank: 188, total: 12520 },
    },
  };

  const DEFAULT_RATION_HISTORY = [
    {
      date: "2026-04-28T09:00:00.000Z",
      espece: "Poulet chair",
      stade: "Croissance",
      cout_fcfa_kg: 610,
      cout_7_jours: 4270,
      objectifs: "Équilibre",
      ingredients: ["maïs", "tourteau soja", "son de blé"],
    },
    {
      date: "2026-04-26T16:30:00.000Z",
      espece: "Tilapia",
      stade: "Alevin",
      cout_fcfa_kg: 690,
      cout_7_jours: 4830,
      objectifs: "Riche protéines",
      ingredients: ["farine poisson", "maïs", "huile"],
    },
    {
      date: "2026-04-24T10:12:00.000Z",
      espece: "Vache laitière",
      stade: "Lactation",
      cout_fcfa_kg: 820,
      cout_7_jours: 5740,
      objectifs: "Économique",
      ingredients: ["maïs", "tourteau coton", "herbe sèche"],
    },
    {
      date: "2026-04-21T08:55:00.000Z",
      espece: "Chèvre",
      stade: "Croissance",
      cout_fcfa_kg: 520,
      cout_7_jours: 3640,
      objectifs: "Équilibre",
      ingredients: ["maïs", "tourteau soja", "feuilles sèches"],
    },
    {
      date: "2026-04-20T18:20:00.000Z",
      espece: "Porc",
      stade: "Finition",
      cout_fcfa_kg: 760,
      cout_7_jours: 5320,
      objectifs: "Riche protéines",
      ingredients: ["maïs", "tourteau soja", "pré-mix"],
    },
  ];

  const DEFAULT_VET_HISTORY = [
    {
      date: "2026-04-29T08:15:00.000Z",
      species: "Poulet",
      confidence: 87,
      urgent: false,
      diagnosis: "Coccidiose probable",
    },
    {
      date: "2026-04-27T14:00:00.000Z",
      species: "Vache",
      confidence: 91,
      urgent: true,
      diagnosis: "Fièvre, déshydratation",
    },
    {
      date: "2026-04-25T11:40:00.000Z",
      species: "Chèvre",
      confidence: 75,
      urgent: false,
      diagnosis: "Parasites intestinaux",
    },
    {
      date: "2026-04-22T17:24:00.000Z",
      species: "Porc",
      confidence: 82,
      urgent: false,
      diagnosis: "Trouble digestif",
    },
    {
      date: "2026-04-18T09:05:00.000Z",
      species: "Pintade",
      confidence: 78,
      urgent: false,
      diagnosis: "Stress thermique",
    },
  ];

  const DEFAULT_REPRO = [
    {
      id: "A-204",
      status: "Gestante",
      nextDays: 44,
      species: "Vache",
      event: "Mise-bas estimée",
    },
    {
      id: "B-015",
      status: "En chaleur",
      nextDays: 2,
      species: "Chèvre",
      event: "Chaleur observée",
    },
    {
      id: "C-077",
      status: "Vide",
      nextDays: 18,
      species: "Poule",
      event: "Insémination",
    },
    {
      id: "D-092",
      status: "Gestante",
      nextDays: 29,
      species: "Porc",
      event: "Mise-bas estimée",
    },
    {
      id: "E-013",
      status: "En chaleur",
      nextDays: 5,
      species: "Mouton",
      event: "Saillie",
    },
  ];

  const DEFAULT_LEAGUE = {
    commune: makeLeagueDataset("commune"),
    departement: makeLeagueDataset("departement"),
    national: makeLeagueDataset("national"),
  };

  const DEFAULT_ACADEMY = {
    courses: [
      {
        id: "volailles",
        title: "Alimentation des volailles",
        icon: "🐔",
        level: "Débutant",
        duration: "45 min",
        total: 5,
        done: 2,
        certified: false,
      },
      {
        id: "bovine",
        title: "Santé bovine",
        icon: "🐄",
        level: "Intermédiaire",
        duration: "40 min",
        total: 4,
        done: 4,
        certified: true,
      },
      {
        id: "repro",
        title: "Gestion reproduction",
        icon: "📅",
        level: "Intermédiaire",
        duration: "30 min",
        total: 3,
        done: 1,
        certified: false,
      },
      {
        id: "finance",
        title: "Finance agricole",
        icon: "💰",
        level: "Débutant",
        duration: "35 min",
        total: 3,
        done: 0,
        certified: false,
      },
      {
        id: "paturage",
        title: "Pâturages durables",
        icon: "🌿",
        level: "Avancé",
        duration: "50 min",
        total: 3,
        done: 3,
        certified: true,
      },
    ],
    lesson: {
      title: "Optimiser une ration de démarrage pour poulets",
      paragraphs: [
        "Une ration de démarrage doit être riche en énergie et en protéines digestibles.",
        "Le maïs apporte l’énergie tandis que le tourteau de soja améliore la croissance.",
        "Un apport correct en minéraux et vitamines réduit les carences et la mortalité.",
      ],
      quiz: [
        {
          question: "Quel ingrédient apporte surtout l’énergie ?",
          answers: ["Maïs", "Calcium", "Sel"],
          correct: 0,
        },
        {
          question: "Quel ingrédient aide surtout la croissance ?",
          answers: ["Tourteau de soja", "Paille", "Eau"],
          correct: 0,
        },
        {
          question: "Pourquoi ajouter un pré-mix ?",
          answers: [
            "Pour les vitamines et minéraux",
            "Pour colorer la ration",
            "Pour la saler",
          ],
          correct: 0,
        },
      ],
    },
  };

  /* ---------------------------------------------------------
     Détection de la page courante
     --------------------------------------------------------- */

  function detectPage() {
    const path = window.location.pathname.toLowerCase();
    if (path.includes("nutricore")) return "nutricore";
    if (path.includes("vetscan")) return "vetscan";
    if (path.includes("reprotrack")) return "reprotrack";
    if (path.includes("profil")) return "profil";
    if (path.includes("classement")) return "classement";
    if (path.includes("farmacademy")) return "farmacademy";
    if (path.includes("modules")) return "modules";
    return "index";
  }

  /* ---------------------------------------------------------
     Raccourcis DOM
     --------------------------------------------------------- */

  function $(selector, root = document) {
    return root.querySelector(selector);
  }

  function $all(selector, root = document) {
    return Array.from(root.querySelectorAll(selector));
  }

  function byData(name, root = document) {
    return root.querySelector(`[data-${name}]`);
  }

  function allByData(name, root = document) {
    return Array.from(root.querySelectorAll(`[data-${name}]`));
  }

  function text(el, value) {
    if (el) el.textContent = value;
  }

  function html(el, value) {
    if (el) el.innerHTML = value;
  }

  function safeString(value) {
    return value === null || value === undefined ? "" : String(value);
  }

  function escapeHtml(value) {
    return safeString(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }

  function formatNumberFr(value) {
    return new Intl.NumberFormat("fr-FR").format(
      Math.round(Number(value) || 0),
    );
  }

  function formatFCFA(value) {
    return `${formatNumberFr(value)} FCFA`;
  }

  function formatDateFr(dateInput) {
    const date = new Date(dateInput);
    if (Number.isNaN(date.getTime())) return "Date inconnue";
    return new Intl.DateTimeFormat("fr-FR", {
      day: "2-digit",
      month: "short",
      year: "numeric",
    }).format(date);
  }

  function formatDateTimeFr(dateInput) {
    const date = new Date(dateInput);
    if (Number.isNaN(date.getTime())) return "Date inconnue";
    return new Intl.DateTimeFormat("fr-FR", {
      day: "2-digit",
      month: "short",
      hour: "2-digit",
      minute: "2-digit",
    }).format(date);
  }

  function formatDuration(seconds) {
    const s = Math.max(0, Math.floor(Number(seconds) || 0));
    const days = Math.floor(s / 86400);
    const hours = Math.floor((s % 86400) / 3600);
    const minutes = Math.floor((s % 3600) / 60);
    const secs = s % 60;
    if (days > 0) return `${days}j ${hours}h ${minutes}m`;
    if (hours > 0) return `${hours}h ${minutes}m ${secs}s`;
    if (minutes > 0) return `${minutes}m ${secs}s`;
    return `${secs}s`;
  }

  function initialsFromName(name) {
    const safe = safeString(name).trim();
    if (!safe) return "FF";
    const parts = safe.split(/\s+/).filter(Boolean);
    if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
    return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
  }

  function clamp(value, min, max) {
    return Math.max(min, Math.min(max, value));
  }

  function uid(prefix = "id") {
    return `${prefix}_${Math.random().toString(36).slice(2, 10)}`;
  }

  function detectLanguageFromText(value) {
    const t = safeString(value).toLowerCase();
    if (/ŋ|ɔ|ɛ|ɖ|ɣ/.test(t)) return "fon";
    if (/[ẹọṣ]/.test(t)) return "yor";
    if (/dendi|kulu|gandi|wono|boro/.test(t)) return "den";
    if (/the|and|animal|feed|ration/.test(t)) return "en";
    return "fr";
  }

  /* ---------------------------------------------------------
     LocalStorage sécurisé
     --------------------------------------------------------- */

  function getJSON(key, fallback) {
    try {
      const raw = localStorage.getItem(key);
      if (!raw) return fallback;
      return JSON.parse(raw);
    } catch (error) {
      return fallback;
    }
  }

  function setJSON(key, value) {
    try {
      localStorage.setItem(key, JSON.stringify(value));
    } catch (error) {
      // Aucun traitement supplémentaire
    }
  }

  function loadAppState() {
    const saved = getJSON(STORAGE_KEYS.state, {});
    const profile = getJSON(STORAGE_KEYS.profile, DEFAULT_PROFILE);
    const rationHistory = getJSON(
      STORAGE_KEYS.rationHistory,
      DEFAULT_RATION_HISTORY,
    );
    const vetHistory = getJSON(STORAGE_KEYS.vetHistory, DEFAULT_VET_HISTORY);
    const reproHistory = getJSON(STORAGE_KEYS.reproHistory, DEFAULT_REPRO);
    const academy = getJSON(STORAGE_KEYS.academy, DEFAULT_ACADEMY);
    const league = getJSON(STORAGE_KEYS.league, DEFAULT_LEAGUE);

    APP.points = Number(saved.points ?? profile.points ?? 0);
    APP.level = Number(saved.level ?? 1);
    APP.selectedLanguage =
      saved.selectedLanguage || getJSON(STORAGE_KEYS.language, "fr");
    APP.selectedSpecies = saved.selectedSpecies || "";
    APP.selectedStage = saved.selectedStage || "";
    APP.selectedObjective = saved.selectedObjective || "equilibre";
    APP.selectedIngredients = Array.isArray(saved.selectedIngredients)
      ? saved.selectedIngredients
      : [];
    APP.animalsCount = Number(saved.animalsCount ?? 50);
    APP.skillPoints = Number(saved.skillPoints ?? 0);
    APP.badges = Array.isArray(saved.badges) ? saved.badges : [];
    APP.ayaMood = saved.ayaMood || "joy";
    APP.ayaMessage = saved.ayaMessage || "Bienvenue sur FeedFormula AI !";

    APP.profile = profile;
    APP.rationHistory = rationHistory;
    APP.vetHistory = vetHistory;
    APP.reproHistory = reproHistory;
    APP.academy = academy;
    APP.league = league;
  }

  function saveAppState() {
    setJSON(STORAGE_KEYS.state, {
      points: APP.points,
      level: APP.level,
      selectedLanguage: APP.selectedLanguage,
      selectedSpecies: APP.selectedSpecies,
      selectedStage: APP.selectedStage,
      selectedObjective: APP.selectedObjective,
      selectedIngredients: APP.selectedIngredients,
      animalsCount: APP.animalsCount,
      skillPoints: APP.skillPoints,
      badges: APP.badges,
      ayaMood: APP.ayaMood,
      ayaMessage: APP.ayaMessage,
      updatedAt: new Date().toISOString(),
    });
    setJSON(STORAGE_KEYS.language, APP.selectedLanguage);
    setJSON(STORAGE_KEYS.profile, APP.profile || DEFAULT_PROFILE);
    setJSON(
      STORAGE_KEYS.rationHistory,
      APP.rationHistory || DEFAULT_RATION_HISTORY,
    );
    setJSON(STORAGE_KEYS.vetHistory, APP.vetHistory || DEFAULT_VET_HISTORY);
    setJSON(STORAGE_KEYS.reproHistory, APP.reproHistory || DEFAULT_REPRO);
    setJSON(STORAGE_KEYS.academy, APP.academy || DEFAULT_ACADEMY);
    setJSON(STORAGE_KEYS.league, APP.league || DEFAULT_LEAGUE);
  }

  /* ---------------------------------------------------------
     Toasts
     --------------------------------------------------------- */

  function ensureToastContainer() {
    let container = $(".toast-container");
    if (!container) {
      container = document.createElement("div");
      container.className = "toast-container";
      document.body.appendChild(container);
    }
    return container;
  }

  function toast(message, type = "info", duration = 2400) {
    const container = ensureToastContainer();
    const el = document.createElement("div");
    el.className = `toast toast-${type}`;
    el.textContent = message;
    container.appendChild(el);

    window.setTimeout(
      () => {
        el.style.opacity = "0";
        el.style.transform = "translateY(-4px)";
        el.style.transition = "opacity 180ms ease, transform 180ms ease";
      },
      Math.max(900, duration - 260),
    );

    window.setTimeout(() => {
      el.remove();
    }, duration);
  }

  /* ---------------------------------------------------------
     Aya : gestion des états
     --------------------------------------------------------- */

  function setAyaMood(mood, message) {
    APP.ayaMood = mood;
    APP.ayaMessage = message || APP.ayaMessage;

    const image = $("[data-aya-image]") || $(".aya-image");
    const bubble =
      $("[data-aya-bubble]") || $(".aya-message") || $(".aya-points-bubble");
    if (image) {
      image.src = AYA_IMAGES[mood] || AYA_IMAGES.joy;
      image.alt = `Aya — humeur ${mood}`;
    }
    if (bubble) {
      bubble.textContent = APP.ayaMessage;
      bubble.classList.remove("is-show");
      // Déclenchement de l'animation
      void bubble.offsetWidth;
      bubble.classList.add("is-show");
    }
    saveAppState();
  }

  function showAyaPointsBubble(pointsText) {
    const bubble = $("[data-aya-points]") || $(".aya-points-bubble");
    if (!bubble) return;
    bubble.textContent = pointsText;
    bubble.classList.remove("is-show");
    void bubble.offsetWidth;
    bubble.classList.add("is-show");
    window.setTimeout(() => bubble.classList.remove("is-show"), 2200);
  }

  function celebrate() {
    const layer = $(".celebration");
    if (!layer) return;
    layer.classList.add("is-active");
    const count = 18;
    layer.innerHTML = "";
    for (let i = 0; i < count; i += 1) {
      const star = document.createElement("span");
      star.className = "star";
      star.style.left = `${Math.random() * 100}%`;
      star.style.animationDuration = `${1100 + Math.random() * 1200}ms`;
      star.style.animationDelay = `${Math.random() * 220}ms`;
      layer.appendChild(star);
    }
    window.setTimeout(() => {
      layer.classList.remove("is-active");
      layer.innerHTML = "";
    }, 1800);
  }

  /* ---------------------------------------------------------
     Niveau / points
     --------------------------------------------------------- */

  function getNiveauFromPoints(points) {
    const thresholds = [
      { level: 1, seuil: 0, label: "🌱 Semence" },
      { level: 2, seuil: 100, label: "🌿 Pousse" },
      { level: 3, seuil: 250, label: "🌾 Tige" },
      { level: 4, seuil: 500, label: "🌼 Floraison" },
      { level: 5, seuil: 900, label: "🍀 Récolte" },
      { level: 6, seuil: 1500, label: "🏅 Expert" },
      { level: 7, seuil: 2300, label: "👑 Maître" },
      { level: 8, seuil: 3400, label: "✨ Légende" },
      { level: 9, seuil: 4800, label: "🚀 Visionnaire" },
      { level: 10, seuil: 6500, label: "🌳 Sage" },
    ];

    let current = thresholds[0];
    let next = thresholds[1];
    for (let i = 0; i < thresholds.length; i += 1) {
      if (points >= thresholds[i].seuil) {
        current = thresholds[i];
        next = thresholds[i + 1] || thresholds[i];
      }
    }
    return { current, next };
  }

  function updateXpUI() {
    const progressEls = allByData("level-fill").concat(
      $all(".xp-fill, .level-fill, .progress-fill"),
    );
    const metaEls = allByData("level-points").concat(
      $all(".xp-value, .level-points, .progress-value"),
    );
    const labelEls = allByData("level-name").concat($all(".level-name"));
    const badgeEls = allByData("level-badge").concat($all(".level-badge"));

    const { current, next } = getNiveauFromPoints(APP.points);
    APP.level = current.level;
    const base = current.seuil;
    const top = next.seuil === current.seuil ? base + 1 : next.seuil;
    const pct = clamp(((APP.points - base) / (top - base)) * 100, 0, 100);

    progressEls.forEach((el) => {
      el.style.width = `${pct}%`;
    });

    metaEls.forEach((el) => {
      el.textContent = `${formatNumberFr(APP.points)} / ${formatNumberFr(top)} pts → Niveau ${next.level}`;
    });

    labelEls.forEach((el) => {
      el.textContent = `Niveau ${current.level} — ${current.label}`;
    });

    badgeEls.forEach((el) => {
      el.textContent = current.label;
    });

    const levelNumberEls = allByData("level-number");
    levelNumberEls.forEach((el) => {
      el.textContent = `Niveau ${current.level}`;
    });
  }

  function awardPoints(points, reason) {
    const gain = Number(points) || 0;
    if (gain <= 0) return;
    APP.points += gain;
    showAyaPointsBubble(`+${gain} 🌟`);
    celebrate();
    setAyaMood("celebration", reason || "Bravo ! Tu gagnes des points.");
    updateXpUI();
    saveAppState();
    toast(
      reason ? `${reason} (+${gain} 🌟)` : `+${gain} 🌟 gagnés`,
      "success",
      2200,
    );
  }

  /* ---------------------------------------------------------
     Splash screen
     --------------------------------------------------------- */

  function initSplashScreen() {
    const splash = $(".splash-screen") || $(".loading-overlay");
    if (!splash) return;
    window.setTimeout(() => {
      splash.classList.add("is-hidden");
      window.setTimeout(() => splash.remove(), 500);
    }, 2000);
  }

  /* ---------------------------------------------------------
     Navigation mobile
     --------------------------------------------------------- */

  function initBottomNavigation() {
    const items = $all(".bottom-nav .nav-item, .bottom-nav .nav-link");
    if (!items.length) return;

    const current = detectPage();
    items.forEach((item) => {
      const href = item.getAttribute("href") || "";
      const target = item.dataset.target || "";
      const pageMatch =
        href.toLowerCase().includes(`${current}.html`) || target === current;
      if (pageMatch) item.classList.add("active", "is-active");
    });
  }

  /* ---------------------------------------------------------
     Sélecteur de langue
     --------------------------------------------------------- */

  function updateLanguageUI(lang) {
    const buttons = allByData("lang-button").concat($all("[data-lang]"));
    buttons.forEach((button) => {
      const value = (
        button.dataset.lang ||
        button.dataset.value ||
        button.getAttribute("data-lang") ||
        ""
      ).toLowerCase();
      const active = value === lang.toLowerCase();
      button.classList.toggle("active", active);
      button.classList.toggle("is-active", active);
    });

    const hintFields = $all("[data-multilingual-placeholder]");
    hintFields.forEach((field) => {
      const key = field.getAttribute("data-placeholder-key") || "default";
      const translations = LOCALIZED_HINTS;
      field.placeholder = translations[lang] || translations.fr;
    });

    const badge = $("[data-current-language]");
    if (badge) {
      badge.textContent = `${LANGUAGE_LABELS[lang] || lang.toUpperCase()}`;
    }
  }

  function initLanguageSelector() {
    const buttons = allByData("lang-button").concat($all("[data-lang]"));
    const moreButton = $("[data-lang-toggle]");
    const panel = $("[data-lang-panel]");

    if (panel && moreButton) {
      moreButton.addEventListener("click", () => {
        panel.hidden = !panel.hidden;
        moreButton.setAttribute("aria-expanded", String(!panel.hidden));
      });
    }

    buttons.forEach((button) => {
      button.addEventListener("click", () => {
        const lang = (
          button.dataset.lang ||
          button.dataset.value ||
          "fr"
        ).toLowerCase();
        APP.selectedLanguage = lang;
        updateLanguageUI(lang);
        saveAppState();
        toast(
          `Langue sélectionnée : ${LANGUAGE_LABELS[lang] || lang.toUpperCase()}`,
          "info",
          1800,
        );
      });
    });

    updateLanguageUI(APP.selectedLanguage || "fr");
  }

  /* ---------------------------------------------------------
     Grille d'espèces et stades
     --------------------------------------------------------- */

  function resolveSpeciesFromValue(value) {
    const normalized = safeString(value).toLowerCase();
    if (normalized.includes("poulet")) return "poulet";
    if (normalized.includes("pondeuse") || normalized.includes("poule"))
      return "pondeuse";
    if (normalized.includes("pintade")) return "pintade";
    if (normalized.includes("vache") || normalized.includes("lait"))
      return "vache";
    if (normalized.includes("mouton")) return "mouton";
    if (normalized.includes("chèvre") || normalized.includes("chevre"))
      return "chevre";
    if (normalized.includes("porc") || normalized.includes("cochon"))
      return "porc";
    if (normalized.includes("tilapia") || normalized.includes("poisson"))
      return "tilapia";
    return "";
  }

  function getSelectedSpeciesLabel(speciesKey) {
    return SPECIES_CONFIG[speciesKey]?.label || "";
  }

  function getStageOptionsForSpecies(speciesKey) {
    return SPECIES_CONFIG[speciesKey]?.stages || [];
  }

  function renderStageOptions(speciesKey) {
    const container =
      $("[data-stage-container]") || $(".stage-selector") || $(".stage-box");
    if (!container) return;

    const stages = getStageOptionsForSpecies(speciesKey);
    if (!stages.length) {
      container.innerHTML = "";
      container.classList.add("hidden");
      return;
    }

    container.classList.remove("hidden");
    container.innerHTML = `
      <div class="field-label">Stade</div>
      <div class="stage-pills" data-stage-pills></div>
    `;
    const pills = $("[data-stage-pills]", container);
    stages.forEach((stage) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "stage-pill";
      button.textContent = stage;
      button.dataset.stage = stage;
      button.addEventListener("click", () => {
        APP.selectedStage = stage;
        updateStageSelection();
        saveAppState();
        toast(`Stade sélectionné : ${stage}`, "success", 1600);
      });
      pills.appendChild(button);
    });

    if (!APP.selectedStage || !stages.includes(APP.selectedStage)) {
      APP.selectedStage = stages[0];
    }
    updateStageSelection();
  }

  function updateStageSelection() {
    const buttons = $all("[data-stage]").concat($all(".stage-pill"));
    buttons.forEach((button) => {
      const active =
        safeString(button.dataset.stage) === safeString(APP.selectedStage);
      button.classList.toggle("active", active);
      button.classList.toggle("is-active", active);
    });
    const stageField = $("[data-stage-value]");
    if (stageField) {
      stageField.textContent = APP.selectedStage || "";
    }
  }

  function initSpeciesGrid() {
    const cards = allByData("species").concat(
      $all(".species-card, .animal-card"),
    );
    if (!cards.length) return;

    cards.forEach((card) => {
      card.addEventListener("click", () => {
        const value =
          card.dataset.species ||
          card.dataset.value ||
          card.getAttribute("data-species") ||
          card.textContent;
        const speciesKey = resolveSpeciesFromValue(value);
        if (!speciesKey) return;

        APP.selectedSpecies = speciesKey;
        cards.forEach((c) => c.classList.remove("active", "is-active"));
        card.classList.add("active", "is-active");
        renderStageOptions(speciesKey);
        saveAppState();
        toast(
          `Espèce sélectionnée : ${getSelectedSpeciesLabel(speciesKey)}`,
          "success",
          1600,
        );
      });
    });

    if (APP.selectedSpecies) {
      const preselected = cards.find(
        (card) =>
          resolveSpeciesFromValue(
            card.dataset.species || card.dataset.value || card.textContent,
          ) === APP.selectedSpecies,
      );
      if (preselected) preselected.classList.add("active", "is-active");
      renderStageOptions(APP.selectedSpecies);
    } else {
      const first = cards[0];
      if (first) {
        const speciesKey = resolveSpeciesFromValue(
          first.dataset.species || first.dataset.value || first.textContent,
        );
        if (speciesKey) {
          APP.selectedSpecies = speciesKey;
          first.classList.add("active", "is-active");
          renderStageOptions(speciesKey);
        }
      }
    }
  }

  /* ---------------------------------------------------------
     Ingrédients : tags et suggestions
     --------------------------------------------------------- */

  function renderIngredientTags() {
    const tagsWrap =
      $("[data-ingredients-tags]") || $(".tags-list") || $(".ingredients-tags");
    if (!tagsWrap) return;
    tagsWrap.innerHTML = "";

    APP.selectedIngredients.forEach((ingredient) => {
      const tag = document.createElement("button");
      tag.type = "button";
      tag.className = "tag-item ingredient-tag";
      tag.title = "Cliquer pour supprimer";
      tag.innerHTML = `${escapeHtml(ingredient)} <span class="remove">×</span>`;
      tag.addEventListener("click", () => {
        APP.selectedIngredients = APP.selectedIngredients.filter(
          (item) => item !== ingredient,
        );
        renderIngredientTags();
        updateSuggestions();
        saveAppState();
        toast(`${ingredient} supprimé`, "warning", 1600);
      });
      tagsWrap.appendChild(tag);
    });
  }

  function getMatchingSuggestions(term) {
    const value = safeString(term).trim().toLowerCase();
    if (!value) return INGREDIENT_SUGGESTIONS.slice(0, 8);
    return INGREDIENT_SUGGESTIONS.filter((item) =>
      item.toLowerCase().includes(value),
    ).slice(0, 8);
  }

  function updateSuggestions(term = "") {
    const panel =
      $("[data-ingredients-suggestions]") ||
      $(".suggestions-panel") ||
      $(".ingredients-suggestions");
    if (!panel) return;

    const suggestions = getMatchingSuggestions(term).filter(
      (item) => !APP.selectedIngredients.includes(item),
    );
    panel.innerHTML = "";

    if (!suggestions.length) {
      panel.innerHTML = `<div class="muted">Aucune suggestion trouvée.</div>`;
      return;
    }

    suggestions.forEach((suggestion) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "suggestion-item suggestion-tag";
      button.innerHTML = `${escapeHtml(suggestion)} <span>+</span>`;
      button.addEventListener("click", () => {
        addIngredient(suggestion);
        const input =
          $("[data-ingredients-input]") || $("[data-ingredient-input]");
        if (input) {
          input.value = "";
          input.focus();
        }
      });
      panel.appendChild(button);
    });
  }

  function addIngredient(rawIngredient) {
    const ingredient = safeString(rawIngredient).trim().toLowerCase();
    if (!ingredient) return;
    if (APP.selectedIngredients.includes(ingredient)) return;
    APP.selectedIngredients.push(ingredient);
    renderIngredientTags();
    updateSuggestions("");
    saveAppState();
  }

  function initIngredients() {
    const input = $("[data-ingredients-input]") || $("[data-ingredient-input]");
    if (!input) {
      renderIngredientTags();
      return;
    }

    input.placeholder =
      LOCALIZED_HINTS[APP.selectedLanguage] || LOCALIZED_HINTS.fr;
    input.addEventListener("input", () => {
      updateSuggestions(input.value);
    });

    input.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === ",") {
        event.preventDefault();
        const raw = input.value.replace(/,$/, "").trim();
        if (raw) {
          addIngredient(raw);
          input.value = "";
          updateSuggestions("");
        }
      }
    });

    input.addEventListener("blur", () => {
      const raw = input.value.trim();
      if (raw) {
        addIngredient(raw);
        input.value = "";
      }
      updateSuggestions("");
    });

    renderIngredientTags();
    updateSuggestions("");
  }

  /* ---------------------------------------------------------
     Slider nombre d'animaux
     --------------------------------------------------------- */

  function initAnimalsSlider() {
    const slider =
      $("[data-animals-slider]") ||
      $('input[type="range"][data-role="animals"]') ||
      $("#animalsSlider");
    if (!slider) return;

    const valueEl =
      $("[data-animals-value]") ||
      $("[data-animals-count]") ||
      $("#animalsValue");
    const sync = () => {
      APP.animalsCount = clamp(Number(slider.value) || 1, 1, 5000);
      slider.value = String(APP.animalsCount);
      if (valueEl) valueEl.textContent = `${formatNumberFr(APP.animalsCount)}`;
      const numberField = $("[data-animals-number]");
      if (numberField)
        numberField.textContent = `${formatNumberFr(APP.animalsCount)}`;
      saveAppState();
    };

    slider.min = slider.min || "1";
    slider.max = slider.max || "5000";
    sync();
    slider.addEventListener("input", sync);
  }

  /* ---------------------------------------------------------
     Défi quotidien
     --------------------------------------------------------- */

  function initDailyChallenge() {
    const timerEl = $("[data-challenge-countdown]") || $(".challenge-timer");
    const progressEl = $("[data-challenge-progress]");
    const textEl = $("[data-challenge-text]") || $(".challenge-text");

    if (textEl && !textEl.textContent.trim()) {
      textEl.textContent =
        "Réduis le coût d’une ration de 10% en utilisant un ingrédient local.";
    }

    const challengeEnd = new Date();
    challengeEnd.setHours(23, 59, 59, 999);

    function tick() {
      const now = new Date();
      const diff = Math.max(0, challengeEnd.getTime() - now.getTime());
      const sec = Math.floor(diff / 1000);
      const h = Math.floor(sec / 3600);
      const m = Math.floor((sec % 3600) / 60);
      const s = sec % 60;
      if (timerEl)
        timerEl.textContent = `${String(h).padStart(2, "0")}h ${String(m).padStart(2, "0")}m ${String(s).padStart(2, "0")}s`;
      if (progressEl) {
        const total = 24 * 3600 * 1000;
        const pct = clamp(((total - diff) / total) * 100, 0, 100);
        progressEl.style.width = `${pct}%`;
      }
    }

    tick();
    window.setInterval(tick, 1000);
  }

  /* ---------------------------------------------------------
     Splash / microphone / texte d'accueil
     --------------------------------------------------------- */

  function startMicState(state) {
    const btn = $("[data-mic-button]") || $(".btn-mic");
    if (!btn) return;
    btn.classList.remove("is-listening", "is-processing", "is-success");
    if (state === "listening") btn.classList.add("is-listening");
    if (state === "processing") btn.classList.add("is-processing");
    if (state === "success") btn.classList.add("is-success");
  }

  function initWaveCanvas() {
    const canvas = $("[data-wave-canvas]") || $(".wave-canvas");
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    const dpr = window.devicePixelRatio || 1;
    const width = canvas.clientWidth || 320;
    const height = canvas.clientHeight || 64;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    ctx.scale(dpr, dpr);

    let phase = 0;
    function draw(mode = "rest") {
      ctx.clearRect(0, 0, width, height);
      const centerY = height / 2;
      const baseAmp = mode === "listen" ? 18 : mode === "process" ? 10 : 6;
      const bars = 34;

      for (let i = 0; i < bars; i += 1) {
        const x = (width / bars) * i + 2;
        const wave =
          Math.sin(i * 0.5 + phase) * 0.5 +
          Math.cos(i * 0.2 + phase * 0.7) * 0.35;
        const amp = baseAmp + Math.max(0, wave * baseAmp);
        const top = centerY - amp / 2;
        const barHeight = amp;
        const color = mode === "listen" ? "#F9A825" : "#1B5E20";
        ctx.fillStyle = color;
        ctx.globalAlpha = mode === "rest" ? 0.35 : 0.85;
        roundRect(ctx, x, top, 4, barHeight, 2);
        ctx.fill();
      }
      ctx.globalAlpha = 1;
      phase += mode === "rest" ? 0.04 : 0.12;
      requestAnimationFrame(() => draw(mode));
    }

    const mode = canvas.dataset.mode || "rest";
    draw(mode);
  }

  function roundRect(ctx, x, y, width, height, radius) {
    const r = Math.min(radius, width / 2, height / 2);
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.arcTo(x + width, y, x + width, y + height, r);
    ctx.arcTo(x + width, y + height, x, y + height, r);
    ctx.arcTo(x, y + height, x, y, r);
    ctx.arcTo(x, y, x + width, y, r);
    ctx.closePath();
  }

  /* ---------------------------------------------------------
     Génération de ration
     --------------------------------------------------------- */

  function buildRationComposition(
    speciesKey,
    stage,
    objective,
    ingredients,
    animalsCount,
  ) {
    const base = SPECIES_CONFIG[speciesKey] || SPECIES_CONFIG.poulet;
    const localIngredients = ingredients.length
      ? ingredients
      : base.ingredients;

    const objectiveModifiers = {
      equilibre: { protein: 28, energy: 42, fiber: 12, mineral: 10, local: 8 },
      economique: { protein: 22, energy: 50, fiber: 14, mineral: 8, local: 6 },
      riche: { protein: 36, energy: 34, fiber: 8, mineral: 10, local: 6 },
    };

    const stageBoost = {
      Démarrage: 6,
      Croissance: 4,
      Finition: 2,
      "Pré-ponte": 5,
      "Ponte active": 3,
      "Fin de ponte": 2,
      Lactation: 6,
      Tarissement: 3,
      Vêlage: 5,
      Alevin: 7,
      Engraissement: 3,
      Production: 4,
    };

    const obj = objectiveModifiers[objective] || objectiveModifiers.equilibre;
    const protein = clamp(obj.protein + (stageBoost[stage] || 0), 10, 50);
    const energy = clamp(obj.energy - (stageBoost[stage] || 0) / 2, 15, 60);
    const fiber = clamp(
      obj.fiber + (localIngredients.length >= 3 ? 3 : 0),
      3,
      20,
    );
    const mineral = clamp(
      obj.mineral + (speciesKey === "vache" ? 4 : 0),
      4,
      18,
    );
    const local = clamp(100 - protein - energy - fiber - mineral, 5, 28);

    const costKg =
      base.baseCost +
      (speciesKey === "vache" ? 110 : 0) +
      (objective === "economique" ? -45 : objective === "riche" ? 55 : 0) +
      (stage === "Démarrage" || stage === "Pré-ponte" ? 25 : 0) +
      localIngredients.length * 6;

    const dailyKg = Math.max(0.05, Math.min(0.35, animalsCount / 1000));
    const sevenDaysCost = Math.round(costKg * 0.25 * animalsCount);
    const savingEstimate = Math.round(
      Math.max(
        0,
        85 - (objective === "riche" ? 10 : 0) + localIngredients.length * 2,
      ),
    );

    const ingredientsUsed = localIngredients.slice(0, 5);
    const rationale = [
      `Espèce : ${base.label}`,
      `Stade : ${stage}`,
      `Objectif : ${objective === "economique" ? "Économique" : objective === "riche" ? "Riche protéines" : "Équilibre"}`,
      `Nombre d’animaux : ${formatNumberFr(animalsCount)}`,
    ];

    return {
      title: `${base.icon} Ration ${base.label}`,
      speciesLabel: base.label,
      stage,
      objective,
      composition: [
        { label: "Énergie", value: `${energy}%` },
        { label: "Protéines", value: `${protein}%` },
        { label: "Fibres", value: `${fiber}%` },
        { label: "Minéraux", value: `${mineral}%` },
        { label: "Ingrédients locaux", value: `${local}%` },
      ],
      ingredientsUsed,
      costKg: Math.round(costKg),
      cost7Days: sevenDaysCost,
      dailyKg: Number(dailyKg.toFixed(2)),
      estimatedSaving: savingEstimate,
      rationale,
      score: clamp(
        100 - Math.abs(50 - protein) - Math.abs(40 - energy) / 2,
        68,
        98,
      ),
      nutritionScore: clamp(
        Math.round((protein + energy + mineral + local) / 2),
        70,
        100,
      ),
    };
  }

  function renderCompositionTable(composition) {
    return `
      <table class="composition-table">
        <thead>
          <tr>
            <th>Composant</th>
            <th>Part</th>
          </tr>
        </thead>
        <tbody>
          ${composition
            .map(
              (item) => `
              <tr>
                <td>${escapeHtml(item.label)}</td>
                <td><strong>${escapeHtml(item.value)}</strong></td>
              </tr>
            `,
            )
            .join("")}
        </tbody>
      </table>
    `;
  }

  function ensureResultChartCanvas() {
    let canvas = $("[data-ration-chart]");
    if (!canvas) {
      const container = $("[data-result-chart-box]");
      if (!container) return null;
      canvas = document.createElement("canvas");
      canvas.setAttribute("data-ration-chart", "1");
      container.appendChild(canvas);
    }
    return canvas;
  }

  function renderRationChart(composition) {
    const canvas = ensureResultChartCanvas();
    if (!canvas || typeof Chart === "undefined") return;

    if (APP.rationChart) {
      APP.rationChart.destroy();
    }

    const labels = composition.map((item) => item.label);
    const values = composition.map(
      (item) => Number(String(item.value).replace("%", "")) || 0,
    );
    APP.rationChart = new Chart(canvas, {
      type: "doughnut",
      data: {
        labels,
        datasets: [
          {
            data: values,
            backgroundColor: [
              "#1B5E20",
              "#F9A825",
              "#2E7D32",
              "#A5D6A7",
              "#C8E6C9",
            ],
            borderColor: "#FFFFFF",
            borderWidth: 3,
          },
        ],
      },
      options: {
        responsive: true,
        plugins: {
          legend: {
            position: "bottom",
            labels: {
              usePointStyle: true,
              boxWidth: 10,
              font: { size: 12 },
            },
          },
        },
      },
    });
  }

  function afficherResultat(data) {
    const zone =
      $("[data-result-zone]") || $(".result-zone") || $(".card-result");
    if (!zone) return;

    const title = $("[data-result-title]");
    const compositionBox =
      $("[data-result-content]") || $("[data-result-composition]");
    const costBig = $("[data-cout-big]");
    const costDetails = $("[data-cout-details]");
    const perf = $("[data-result-perf]");
    const chartBox = $("[data-result-chart-box]");
    const actions = $("[data-result-actions]");
    const saveBtn = $("[data-save-history]");
    const rationText = data.rationale
      .map(
        (line) =>
          `<div class="composition-line"><span class="label">━━ ${escapeHtml(line)}</span><span class="value">✓</span></div>`,
      )
      .join("");

    zone.classList.remove("hidden");
    zone.style.display = "grid";

    if (title) {
      title.textContent = data.title;
    }

    if (compositionBox) {
      compositionBox.innerHTML = `
        <div class="result-hero">
          <strong>${escapeHtml(data.speciesLabel)}</strong> — ${escapeHtml(data.stage)}<br>
          Objectif : ${escapeHtml(data.objective === "economique" ? "Économique" : data.objective === "riche" ? "Riche protéines" : "Équilibre")}
        </div>
        ${renderCompositionTable(data.composition)}
        <div class="composition-block">${rationText}</div>
      `;
    }

    if (costBig) {
      costBig.textContent = formatFCFA(data.costKg);
    }

    if (costDetails) {
      costDetails.textContent = `Coût 7 jours : ${formatFCFA(data.cost7Days)} • ${formatNumberFr(data.dailyKg)} kg/jour`;
    }

    if (perf) {
      perf.innerHTML = `
        <div class="badge badge-gold">Score nutrition : ${data.nutritionScore}%</div>
        <div class="badge badge-soft">Économie estimée : ${formatNumberFr(data.estimatedSaving)}%</div>
        <div class="badge badge-green">Qualité globale : ${data.score}%</div>
      `;
    }

    if (chartBox) {
      chartBox.classList.remove("hidden");
    }

    renderRationChart(data.composition);

    if (actions) {
      actions.innerHTML = `
        <button type="button" class="btn btn-secondary" data-speak-ration>🔊 Écouter</button>
        <button type="button" class="btn btn-gold" data-pdf-ration>📄 PDF</button>
        <button type="button" class="btn btn-secondary" data-whatsapp-ration>📱 WhatsApp</button>
      `;
      bindResultActions(data);
    }

    if (saveBtn) {
      saveBtn.classList.remove("hidden");
    }

    zone.classList.add("slide-up-visible");
    APP.lastRation = data;
    saveCurrentRationToHistory(data);
    awardPoints(10, "Ration générée avec succès");
  }

  function saveCurrentRationToHistory(data) {
    const entry = {
      date: new Date().toISOString(),
      espece: data.speciesLabel,
      stade: data.stage,
      ration: data.title,
      composition: data.composition,
      cout_fcfa_kg: data.costKg,
      cout_7_jours: data.cost7Days,
      langue: APP.selectedLanguage,
      points_gagnes: 10,
      objectifs: data.objective,
      ingredients: data.ingredientsUsed,
    };

    APP.rationHistory = [entry, ...(APP.rationHistory || [])].slice(0, 20);
    setJSON(STORAGE_KEYS.rationHistory, APP.rationHistory);
    renderOfflineCache();
    renderRationHistoryBlock();
    saveAppState();
  }

  function genererRation() {
    const input =
      $("[data-text-input]") ||
      $("[data-texte-demande]") ||
      $("[data-ration-input]") ||
      $("textarea");
    const especeValue =
      APP.selectedSpecies ||
      resolveSpeciesFromValue(
        ($("[data-species-active]") || {}).dataset?.species ||
          input?.value ||
          "",
      );
    const speciesKey = especeValue || "poulet";
    const stage =
      APP.selectedStage ||
      getStageOptionsForSpecies(speciesKey)[0] ||
      "Croissance";
    const objective = APP.selectedObjective || "equilibre";
    const animalsCount = APP.animalsCount || 50;

    if (!speciesKey) {
      toast("Choisis d’abord une espèce animale.", "warning", 2500);
      setAyaMood("sad", "Je t’aide dès que tu sélectionnes une espèce.");
      return;
    }

    if (APP.selectedIngredients.length === 0) {
      const source = (input?.value || "").trim();
      if (source) {
        const detected = extractIngredientsFromText(source);
        APP.selectedIngredients = detected.length
          ? detected
          : APP.selectedIngredients;
      }
    }

    const data = buildRationComposition(
      speciesKey,
      stage,
      objective,
      APP.selectedIngredients,
      animalsCount,
    );

    const loadingZone = $("[data-loading-zone]") || $(".loading-overlay");
    if (loadingZone && loadingZone.classList.contains("is-visible")) {
      loadingZone.classList.remove("is-visible");
      loadingZone.classList.add("is-hidden");
    }

    afficherResultat(data);
    setAyaMood("joy", "Ta ration est prête !");
  }

  /* ---------------------------------------------------------
     Détection d'ingrédients à partir du texte
     --------------------------------------------------------- */

  function extractIngredientsFromText(value) {
    const textValue = safeString(value).toLowerCase();
    const results = [];
    INGREDIENT_SUGGESTIONS.forEach((ingredient) => {
      const needle = ingredient.toLowerCase();
      if (textValue.includes(needle)) results.push(ingredient);
    });
    return results;
  }

  function bindGenerateButton() {
    const button =
      $("[data-generate-ration]") || $(".btn-generate") || $("#btnGenerer");
    if (!button) return;
    button.addEventListener("click", () => {
      if (APP.selectedSpecies && APP.selectedIngredients.length === 0) {
        const field = $("[data-ingredients-input]");
        if (field && field.value.trim()) addIngredient(field.value);
      }
      const input = $("[data-text-input]") || $("[data-texte-demande]");
      if (input && !APP.selectedSpecies) {
        const found = resolveSpeciesFromValue(input.value);
        if (found) APP.selectedSpecies = found;
      }
      startMicState("processing");
      window.setTimeout(() => {
        genererRation();
        startMicState("success");
        window.setTimeout(() => startMicState(""), 900);
      }, 650);
    });
  }

  function bindMicButton() {
    const button = $("[data-mic-button]") || $(".btn-mic");
    if (!button) return;
    button.addEventListener("click", () => {
      startMicState("listening");
      toast("Écoute vocale activée", "info", 1600);
      setAyaMood("joy", "Parle-moi de tes animaux.");
      window.setTimeout(() => {
        startMicState("processing");
      }, 1200);
      window.setTimeout(() => {
        startMicState("success");
        toast("Voix traitée avec succès", "success", 1600);
      }, 2400);
    });
  }

  /* ---------------------------------------------------------
     Lecture vocale et partage
     --------------------------------------------------------- */

  function lireRationVocalement(texte = "") {
    const content = safeString(
      texte || APP.lastRation?.title || "Votre ration est prête.",
    );
    if (!("speechSynthesis" in window)) {
      toast("Lecture vocale non disponible sur cet appareil.", "warning", 2200);
      return;
    }

    const utterance = new SpeechSynthesisUtterance(content);
    utterance.lang = APP.selectedLanguage === "en" ? "en-US" : "fr-FR";
    utterance.rate = 1;
    utterance.pitch = 1;
    utterance.onstart = () => startMicState("processing");
    utterance.onend = () => startMicState("success");
    speechSynthesis.cancel();
    speechSynthesis.speak(utterance);
  }

  function telechargerPDF(data = APP.lastRation) {
    if (!data) {
      toast("Aucune ration à exporter.", "warning", 1800);
      return;
    }
    if (!window.jspdf || !window.jspdf.jsPDF) {
      toast("Export PDF indisponible pour le moment.", "warning", 2200);
      return;
    }

    const doc = new window.jspdf.jsPDF();
    doc.setFontSize(18);
    doc.text("FeedFormula AI — Ration", 14, 18);
    doc.setFontSize(12);
    doc.text(`Espèce : ${data.speciesLabel}`, 14, 32);
    doc.text(`Stade : ${data.stage}`, 14, 40);
    doc.text(`Objectif : ${data.objective}`, 14, 48);
    doc.text(`Coût/kg : ${formatFCFA(data.costKg)}`, 14, 56);
    doc.text(`Coût 7 jours : ${formatFCFA(data.cost7Days)}`, 14, 64);

    let y = 80;
    doc.text("Composition", 14, y);
    y += 8;
    data.composition.forEach((item) => {
      doc.text(`- ${item.label} : ${item.value}`, 18, y);
      y += 8;
    });

    y += 4;
    doc.text("Ingrédients utilisés", 14, y);
    y += 8;
    data.ingredientsUsed.forEach((item) => {
      doc.text(`- ${item}`, 18, y);
      y += 8;
    });

    doc.save(`ration-feedformula-${Date.now()}.pdf`);
    toast("PDF téléchargé", "success", 1800);
  }

  function partagerWhatsApp(data = APP.lastRation) {
    if (!data) {
      toast("Aucune ration à partager.", "warning", 1800);
      return;
    }
    const message = [
      "FeedFormula AI",
      `${data.speciesLabel} — ${data.stage}`,
      `Coût/kg : ${formatFCFA(data.costKg)}`,
      `Coût 7 jours : ${formatFCFA(data.cost7Days)}`,
      `Composition : ${data.composition.map((item) => `${item.label} ${item.value}`).join(", ")}`,
    ].join("%0A");

    const url = `https://wa.me/?text=${message}`;
    window.open(url, "_blank", "noopener,noreferrer");
  }

  function bindResultActions(data) {
    const speak = $("[data-speak-ration]");
    const pdf = $("[data-pdf-ration]");
    const whatsapp = $("[data-whatsapp-ration]");
    const save = $("[data-save-history]");

    if (speak)
      speak.onclick = () =>
        lireRationVocalement(data?.title || APP.lastRation?.title || "");
    if (pdf) pdf.onclick = () => telechargerPDF(data);
    if (whatsapp) whatsapp.onclick = () => partagerWhatsApp(data);
    if (save) {
      save.onclick = () => {
        saveCurrentRationToHistory(data || APP.lastRation);
        toast("Ration sauvegardée dans l’historique", "success", 1800);
      };
    }
  }

  /* ---------------------------------------------------------
     Historique des rations / cache hors ligne
     --------------------------------------------------------- */

  function renderOfflineCache() {
    const list =
      $("[data-offline-rations-list]") ||
      $(".offline-rations-list") ||
      $(".cache-list");
    if (!list) return;
    const items = (APP.rationHistory || []).slice(0, 5);

    if (!items.length) {
      list.innerHTML =
        '<li class="offline-rations-item">Aucune ration enregistrée.</li>';
      return;
    }

    list.innerHTML = items
      .map(
        (item, index) => `
      <li class="offline-rations-item">
        <div class="history-top">
          <strong>${escapeHtml(item.espece)}</strong>
          <span>${formatDateFr(item.date)}</span>
        </div>
        <div class="history-meta">
          ${escapeHtml(item.stade)} • ${formatFCFA(item.cout_fcfa_kg)} / kg • ${escapeHtml(item.objectifs || "Équilibre")}
        </div>
        <button type="button" class="btn btn-small btn-review" data-cache-ration-index="${index}">Revoir</button>
      </li>
    `,
      )
      .join("");

    allByData("cache-ration-index").forEach((btn) => {
      btn.addEventListener("click", () => {
        const index = Number(btn.dataset.cacheRationIndex || 0);
        const item = APP.rationHistory[index];
        if (!item) return;
        APP.lastRation = {
          speciesLabel: item.espece,
          stage: item.stade,
          objective: item.objectifs || "equilibre",
          composition: item.composition || [],
          costKg: item.cout_fcfa_kg,
          cost7Days: item.cout_7_jours,
          dailyKg: 0.1,
          estimatedSaving: 0,
          title: item.ration,
          rationale: [`Historique : ${item.espece}`, `Stade : ${item.stade}`],
          ingredientsUsed: item.ingredients || [],
          score: 0,
          nutritionScore: 0,
        };
        afficherResultat(APP.lastRation);
        toast("Ration chargée depuis l’historique", "info", 1800);
      });
    });
  }

  function renderRationHistoryBlock() {
    const list =
      $("[data-ration-history]") || $(".history-list") || $(".ration-history");
    if (!list) return;
    const items = (APP.rationHistory || []).slice(0, 5);

    if (!items.length) {
      list.innerHTML =
        '<div class="empty-note">Aucune ration enregistrée pour le moment.</div>';
      return;
    }

    list.innerHTML = items
      .map(
        (item, index) => `
      <article class="history-item">
        <div class="history-top">
          <div>
            <strong>${escapeHtml(item.espece)}</strong>
            <div class="history-meta">${formatDateFr(item.date)} • ${escapeHtml(item.stade)}</div>
          </div>
          <strong>${formatFCFA(item.cout_fcfa_kg)}</strong>
        </div>
        <div class="history-meta">Coût 7 jours : ${formatFCFA(item.cout_7_jours)} • ${escapeHtml(item.objectifs || "Équilibre")}</div>
        <button type="button" class="btn btn-small btn-review" data-history-ration-index="${index}">Revoir</button>
      </article>
    `,
      )
      .join("");

    allByData("history-ration-index").forEach((btn) => {
      btn.addEventListener("click", () => {
        const item =
          APP.rationHistory[Number(btn.dataset.historyRationIndex || 0)];
        if (!item) return;
        APP.lastRation = {
          speciesLabel: item.espece,
          stage: item.stade,
          objective: item.objectifs || "equilibre",
          composition: item.composition || [],
          costKg: item.cout_fcfa_kg,
          cost7Days: item.cout_7_jours,
          dailyKg: 0.1,
          estimatedSaving: 0,
          title: item.ration,
          rationale: [`Historique : ${item.espece}`, `Stade : ${item.stade}`],
          ingredientsUsed: item.ingredients || [],
          score: 0,
          nutritionScore: 0,
        };
        afficherResultat(APP.lastRation);
        toast("Ration chargée", "info", 1600);
      });
    });
  }

  function afficherEtatOffline() {
    document.body.classList.add("offline");
    const banner = $("[data-offline-banner]") || $(".offline-banner");
    if (banner) banner.classList.remove("hidden");
    setAyaMood(
      "sad",
      "Tu es hors ligne, mais ton historique reste disponible.",
    );
    renderOfflineCache();
    toast("Mode hors ligne activé", "warning", 2000);
  }

  function masquerEtatOffline() {
    document.body.classList.remove("offline");
    const banner = $("[data-offline-banner]") || $(".offline-banner");
    if (banner) banner.classList.add("hidden");
    setAyaMood("joy", "Connexion rétablie !");
    toast("Connexion rétablie", "success", 1600);
  }

  function handleOnlineState() {
    APP.online = navigator.onLine;
    if (APP.online) {
      masquerEtatOffline();
    } else {
      afficherEtatOffline();
    }
  }

  /* ---------------------------------------------------------
     VetScan : analyse médicale simplifiée
     --------------------------------------------------------- */

  function initVetScan() {
    const photoInput = $("[data-photo-input]");
    const preview =
      $("[data-photo-preview]") || $(".photo-preview") || $(".animal-preview");
    const photoBtn = $("[data-photo-button]") || $(".btn-photo");
    const analyzeBtn = $("[data-analyse-button]") || $(".btn-analyse");
    const symptomsInput =
      $("[data-symptoms-input]") || $("[data-vet-symptoms]");
    const voiceBtn = $("[data-vet-mic]");
    const speciesSelect = $("[data-vet-species]");
    const resultZone = $("[data-vet-result]");
    const confidenceEl = $("[data-confidence-score]");
    const diagList = $("[data-diagnostic-list]");
    const protocolList = $("[data-protocol-list]");
    const decisionBox = $("[data-decision-box]");
    const historyList = $("[data-vet-history]");

    const uploadPreview = (file) => {
      if (!preview || !file) return;
      const reader = new FileReader();
      reader.onload = () => {
        preview.innerHTML = `<img src="${reader.result}" alt="Prévisualisation de l’animal">`;
      };
      reader.readAsDataURL(file);
    };

    if (photoBtn && photoInput) {
      photoBtn.addEventListener("click", () => photoInput.click());
    }
    if (photoInput) {
      photoInput.addEventListener("change", () =>
        uploadPreview(photoInput.files?.[0]),
      );
    }

    if (voiceBtn) {
      voiceBtn.addEventListener("click", () => {
        startMicState("listening");
        toast("Décrivez les symptômes à voix haute.", "info", 1800);
        window.setTimeout(() => startMicState("processing"), 1200);
      });
    }

    if (analyzeBtn) {
      analyzeBtn.addEventListener("click", () => {
        const species = speciesSelect?.value || "animal";
        const symptoms = safeString(symptomsInput?.value || "");
        const { confidence, urgent, diagnostics, protocol, decision } =
          analyzeVetCase(species, symptoms);

        if (resultZone) resultZone.classList.remove("hidden");
        if (confidenceEl) confidenceEl.textContent = `${confidence}%`;
        if (diagList) {
          diagList.innerHTML = diagnostics
            .map(
              (diag) => `
            <div class="diagnostic-item">
              <div class="line">
                <span>${escapeHtml(diag.label)}</span>
                <strong>${diag.probability}%</strong>
              </div>
              <div class="probability-bar"><span style="width:${diag.probability}%"></span></div>
            </div>
          `,
            )
            .join("");
        }
        if (protocolList) {
          protocolList.innerHTML = protocol
            .map(
              (step, idx) => `
            <div class="protocol-step">
              <strong>Étape ${idx + 1}</strong> — ${escapeHtml(step)}
            </div>
          `,
            )
            .join("");
        }
        if (decisionBox) {
          decisionBox.className = `decision-box ${urgent ? "urgent" : "safe"}`;
          decisionBox.textContent = decision;
        }

        const record = {
          date: new Date().toISOString(),
          species,
          confidence,
          urgent,
          diagnosis: diagnostics[0]?.label || "Cas non déterminé",
        };
        APP.vetHistory = [record, ...(APP.vetHistory || [])].slice(0, 20);
        setJSON(STORAGE_KEYS.vetHistory, APP.vetHistory);
        renderVetHistory(historyList);
        awardPoints(20, "Diagnostic VetScan effectué");
        saveAppState();

        if (urgent) {
          toast("Urgence vétérinaire détectée", "error", 2400);
          const findVetBtn = $("[data-find-vet]");
          if (findVetBtn) findVetBtn.classList.remove("hidden");
        } else {
          toast("Soins autonomes possibles", "success", 2200);
        }
      });
    }

    renderVetHistory(historyList);
  }

  function analyzeVetCase(species, symptoms) {
    const t = safeString(symptoms).toLowerCase();
    let confidence = 72;
    let urgent = false;
    const diagnostics = [];
    const protocol = [];

    if (t.includes("fièvre") || t.includes("fievre")) {
      diagnostics.push({ label: "Fièvre infectieuse", probability: 91 });
      confidence += 10;
      urgent = true;
    } else {
      diagnostics.push({ label: "Trouble léger", probability: 67 });
    }

    if (t.includes("diarr") || t.includes("selles")) {
      diagnostics.push({ label: "Trouble digestif", probability: 84 });
      confidence += 4;
      protocol.push("Donner de l’eau propre en continu.");
      protocol.push("Réduire les aliments trop gras pendant 24 heures.");
    } else {
      diagnostics.push({ label: "Stress ou fatigue", probability: 58 });
    }

    if (t.includes("bless") || t.includes("plaie") || t.includes("boite")) {
      diagnostics.push({ label: "Traumatisme ou boiterie", probability: 79 });
      confidence += 3;
      protocol.push("Isoler l’animal pour éviter le stress.");
      protocol.push("Nettoyer la zone touchée avec précaution.");
    }

    if (t.includes("déshydrat") || t.includes("deshydrat")) {
      diagnostics[0] = { label: "Déshydratation sévère", probability: 93 };
      confidence += 15;
      urgent = true;
      protocol.unshift("Fournir immédiatement de l’eau et des électrolytes.");
    }

    if (protocol.length === 0) {
      protocol.push("Observer l’animal 12 à 24 heures.");
      protocol.push("Vérifier l’accès à l’eau, l’aliment et l’abri.");
      protocol.push("Contacter un professionnel si les signes persistent.");
    }

    confidence = clamp(confidence, 50, 98);

    const decision = urgent
      ? "⚠️ URGENCE VÉTÉRINAIRE"
      : "✅ Soins autonomes possibles";

    return {
      confidence,
      urgent,
      diagnostics: diagnostics.slice(0, 3),
      protocol: protocol.slice(0, 4),
      decision,
      species,
    };
  }

  function renderVetHistory(historyList) {
    const list = historyList || $("[data-vet-history]") || $(".history-list");
    if (!list) return;
    const items = (APP.vetHistory || []).slice(0, 5);

    if (!items.length) {
      list.innerHTML =
        '<div class="empty-note">Aucun diagnostic enregistré.</div>';
      return;
    }

    list.innerHTML = items
      .map(
        (item) => `
      <article class="history-item">
        <div class="history-top">
          <div>
            <strong>${escapeHtml(item.species)}</strong>
            <div class="history-meta">${formatDateFr(item.date)}</div>
          </div>
          <strong>${item.confidence}%</strong>
        </div>
        <div class="history-meta">${escapeHtml(item.diagnosis)}</div>
      </article>
    `,
      )
      .join("");
  }

  /* ---------------------------------------------------------
     ReproTrack : calendrier et tableau de bord
     --------------------------------------------------------- */

  function initReproTrack() {
    const calendar = $("[data-repro-calendar]");
    const list = $("[data-repro-list]");
    const dashboard = $("[data-repro-dashboard]");
    const button = $("[data-repro-event-button]");
    const modalType = $("[data-repro-event-type]");

    renderReproCalendar(calendar);
    renderReproList(list);
    renderReproDashboard(dashboard);

    if (button && modalType) {
      button.addEventListener("click", () => {
        const type = modalType.value || "Saillie";
        APP.reproHistory.unshift({
          id: uid("evt"),
          status: type,
          nextDays: 0,
          species: "Animal",
          event: type,
        });
        APP.reproHistory = APP.reproHistory.slice(0, 30);
        setJSON(STORAGE_KEYS.reproHistory, APP.reproHistory);
        renderReproList(list);
        renderReproDashboard(dashboard);
        toast("Événement enregistré", "success", 1700);
        awardPoints(10, "Événement ReproTrack enregistré");
      });
    }
  }

  function renderReproCalendar(calendar) {
    const el = calendar || $("[data-repro-calendar]");
    if (!el) return;

    const now = new Date();
    const year = now.getFullYear();
    const month = now.getMonth();
    const firstDay = new Date(year, month, 1).getDay();
    const totalDays = new Date(year, month + 1, 0).getDate();

    const heatDays = new Set([3, 8, 12, 19, 26]);
    const aiDays = new Set([5, 14, 22]);
    const birthDays = new Set([10, 28]);

    const labels = ["D", "L", "M", "M", "J", "V", "S"];
    const cells = labels.map(
      (d) => `<div class="day-cell"><strong>${d}</strong></div>`,
    );

    for (let i = 0; i < firstDay; i += 1) {
      cells.push('<div class="day-cell muted"></div>');
    }

    for (let day = 1; day <= totalDays; day += 1) {
      let cls = "day-cell";
      if (heatDays.has(day)) cls += " heat";
      if (aiDays.has(day)) cls += " ai";
      if (birthDays.has(day)) cls += " birth";
      cells.push(`<div class="${cls}"><strong>${day}</strong></div>`);
    }

    el.innerHTML = `<div class="calendar-grid">${cells.join("")}</div>`;
  }

  function renderReproList(list) {
    const el = list || $("[data-repro-list]");
    if (!el) return;
    const items = (APP.reproHistory || []).slice(0, 5);

    el.innerHTML = items
      .map(
        (item) => `
      <article class="follow-item">
        <div class="follow-item-top">
          <div>
            <strong>${escapeHtml(item.id)} • ${escapeHtml(item.species)}</strong>
            <div class="history-meta">${escapeHtml(item.event)}</div>
          </div>
          <span class="status-pill ${statusClass(item.status)}">${escapeHtml(item.status)}</span>
        </div>
        <div class="history-meta">${item.nextDays} jours avant prochain événement</div>
      </article>
    `,
      )
      .join("");
  }

  function renderReproDashboard(dashboard) {
    const el = dashboard || $("[data-repro-dashboard]");
    if (!el) return;
    const fertilityRate = 76;
    const interval = 412;
    const birthsThisMonth = 9;

    el.innerHTML = `
      <div class="metric-box">
        <strong>${fertilityRate}%</strong>
        <span>Taux gestation global</span>
      </div>
      <div class="metric-box">
        <strong>${interval}</strong>
        <span>Intervalle vêlage-vêlage moyen</span>
      </div>
      <div class="metric-box">
        <strong>${birthsThisMonth}</strong>
        <span>Mises-bas ce mois</span>
      </div>
    `;
  }

  function statusClass(value) {
    const t = safeString(value).toLowerCase();
    if (t.includes("gest")) return "pregnant";
    if (t.includes("chaleur")) return "heat";
    return "empty";
  }

  /* ---------------------------------------------------------
     Classement : onglets, podium, rangs
     --------------------------------------------------------- */

  function makeLeagueDataset(scope) {
    const base =
      scope === "national" ? 9800 : scope === "departement" ? 3400 : 800;
    const names = [
      "Awa K.",
      "Mamadou S.",
      "Fatou B.",
      "Kossi D.",
      "Binta N.",
      "Idrissa T.",
      "Aïcha M.",
      "Noël G.",
      "Basile P.",
      "Sonia L.",
      "Abdou R.",
      "Nadine H.",
      "Tariq I.",
      "Gisèle O.",
      "Célestin K.",
      "Hélène M.",
      "Koffi A.",
      "Patricia N.",
      "Yao S.",
      "Mireille D.",
      "Sékou B.",
      "Judith T.",
      "Rachid O.",
      "Inès F.",
      "Blaise N.",
    ];

    return names
      .map((name, index) => ({
        id: `u-${scope}-${index + 1}`,
        name,
        avatar: "",
        level: [
          "🌱 Semence",
          "🌿 Pousse",
          "🌾 Tige",
          "🌼 Floraison",
          "🍀 Récolte",
        ][index % 5],
        points:
          base +
          (names.length - index) *
            (scope === "national" ? 420 : scope === "departement" ? 180 : 65),
        rank: index + 1,
      }))
      .sort((a, b) => b.points - a.points);
  }

  function initClassement() {
    const tabs = allByData("league-tab").concat($all(".tab"));
    const podium = $("[data-podium]");
    const list = $("[data-rank-list]");
    const zone = $("[data-zone-indicator]");
    const countdown = $("[data-season-countdown]");

    tabs.forEach((tab) => {
      tab.addEventListener("click", () => {
        const scope = tab.dataset.scope || tab.dataset.tab || "commune";
        tabs.forEach((t) => t.classList.remove("active", "is-active"));
        tab.classList.add("active", "is-active");
        renderLeagueScope(scope, podium, list, zone);
      });
    });

    renderLeagueScope("commune", podium, list, zone);
    initSeasonCountdown(countdown);
  }

  function renderLeagueScope(scope, podium, list, zone) {
    const data =
      APP.league?.[scope] || DEFAULT_LEAGUE[scope] || DEFAULT_LEAGUE.commune;
    renderPodium(data, podium);
    renderRankingList(data, list);
    renderLeagueZone(data, zone);
  }

  function renderPodium(data, podium) {
    const el = podium || $("[data-podium]") || $(".podium");
    if (!el) return;
    const top3 = data.slice(0, 3);

    el.innerHTML = `
      <div class="podium-item rank-2">
        <div class="medal">🥈</div>
        <div class="name">${escapeHtml(top3[1]?.name || "—")}</div>
        <div class="meta">${formatNumberFr(top3[1]?.points || 0)} pts</div>
      </div>
      <div class="podium-item rank-1">
        <div class="medal">🥇</div>
        <div class="name">${escapeHtml(top3[0]?.name || "—")}</div>
        <div class="meta">${formatNumberFr(top3[0]?.points || 0)} pts</div>
      </div>
      <div class="podium-item rank-3">
        <div class="medal">🥉</div>
        <div class="name">${escapeHtml(top3[2]?.name || "—")}</div>
        <div class="meta">${formatNumberFr(top3[2]?.points || 0)} pts</div>
      </div>
    `;
  }

  function renderRankingList(data, list) {
    const el = list || $("[data-rank-list]") || $(".rank-list-card");
    if (!el) return;
    const currentUser = safeString(
      APP.profile?.name || DEFAULT_PROFILE.name,
    ).toLowerCase();

    el.innerHTML = data
      .slice(3, 50)
      .map((item, index) => {
        const current = item.name.toLowerCase() === currentUser;
        return `
        <div class="row rank-row ${current ? "current-user" : ""}">
          <div class="rank">#${index + 4}</div>
          <div class="user">
            <div class="name">${escapeHtml(item.name)}</div>
            <div class="sub">${escapeHtml(item.level)}</div>
          </div>
          <div class="score">
            <div class="pts">${formatNumberFr(item.points)} pts</div>
            <div class="lvl">${escapeHtml(item.level)}</div>
          </div>
        </div>
      `;
      })
      .join("");
  }

  function renderLeagueZone(data, zone) {
    const el = zone || $("[data-zone-indicator]") || $(".zone-indicator");
    if (!el) return;
    const user =
      data.find(
        (item) =>
          item.name.toLowerCase() ===
          safeString(APP.profile?.name || DEFAULT_PROFILE.name).toLowerCase(),
      ) || data[6];
    const rank = user?.rank || 7;
    const total = data.length;
    const upThreshold = 5;
    const downThreshold = Math.max(40, total - 10);

    let htmlContent = "";
    if (rank <= upThreshold) {
      htmlContent = '<div class="pill up">⬆️ Tu es en zone montée</div>';
    } else if (rank >= downThreshold) {
      htmlContent = '<div class="pill down">⬇️ Tu es en zone descente</div>';
    } else {
      htmlContent = '<div class="pill neutral">➡️ Tu es en zone neutre</div>';
    }
    htmlContent += `<div class="muted">Rang actuel : #${rank} / ${total}</div>`;
    el.innerHTML = htmlContent;
  }

  function initSeasonCountdown(target) {
    const el = target || $("[data-season-countdown]") || $(".countdown");
    if (!el) return;
    const seasonEnd = new Date();
    seasonEnd.setDate(seasonEnd.getDate() + 14);
    seasonEnd.setHours(23, 59, 59, 999);

    function tick() {
      const diff = Math.max(0, seasonEnd.getTime() - Date.now());
      const days = Math.floor(diff / 86400000);
      const hours = Math.floor((diff % 86400000) / 3600000);
      const minutes = Math.floor((diff % 3600000) / 60000);
      const seconds = Math.floor((diff % 60000) / 1000);
      el.textContent = `${days}j ${hours}h ${minutes}m ${seconds}s`;
    }

    tick();
    window.setInterval(tick, 1000);
  }

  /* ---------------------------------------------------------
     Profil : avatar, statistiques, trophées
     --------------------------------------------------------- */

  function initProfil() {
    const avatarImg = $("[data-profile-avatar]");
    const avatarFallback = $("[data-avatar-fallback]");
    const nameEl = $("[data-profile-name]");
    const regionEl = $("[data-profile-region]");
    const joinedEl = $("[data-profile-joined]");
    const levelBadge = $("[data-profile-level-badge]");
    const xpFill = $("[data-profile-xp-fill]");
    const xpMeta = $("[data-profile-xp-meta]");
    const statsMap = {
      rations: $("[data-stat-rations]"),
      savingsFcfa: $("[data-stat-savings]"),
      diagnosedAnimals: $("[data-stat-diagnosed]"),
      streak: $("[data-stat-streak]"),
      trophies: $("[data-stat-trophies]"),
      daysUsed: $("[data-stat-days]"),
    };
    const streakCurrent = $("[data-streak-current]");
    const streakBest = $("[data-streak-best]");
    const rescueSeeds = $("[data-rescue-seeds]");
    const trophyGrid = $("[data-trophy-grid]");
    const rankItems = {
      commune: $("[data-rank-commune]"),
      departement: $("[data-rank-departement]"),
      national: $("[data-rank-national]"),
    };
    const goldBalance = $("[data-gold-balance]");
    const shopButton = $("[data-shop-button]");
    const shopPanel = $("[data-shop-panel]");

    const profile = APP.profile || DEFAULT_PROFILE;

    if (avatarImg) {
      if (profile.avatar) {
        avatarImg.src = profile.avatar;
        avatarImg.classList.remove("hidden");
      } else {
        avatarImg.classList.add("hidden");
      }
    }
    if (avatarFallback) {
      avatarFallback.textContent = initialsFromName(profile.name);
      if (profile.avatar) {
        avatarFallback.classList.add("hidden");
      } else {
        avatarFallback.classList.remove("hidden");
      }
    }

    if (nameEl) nameEl.textContent = profile.name;
    if (regionEl)
      regionEl.textContent = `${profile.region} • ${profile.commune}`;
    if (joinedEl)
      joinedEl.textContent = `Inscrit le ${formatDateFr(profile.joinedAt)}`;
    if (levelBadge) levelBadge.textContent = profile.levelName;

    const pct = clamp((profile.points / profile.nextLevelPoints) * 100, 0, 100);
    if (xpFill) xpFill.style.width = `${pct}%`;
    if (xpMeta)
      xpMeta.textContent = `${formatNumberFr(profile.points)} / ${formatNumberFr(profile.nextLevelPoints)} pts`;

    if (statsMap.rations)
      statsMap.rations.textContent = formatNumberFr(profile.stats.rations);
    if (statsMap.savingsFcfa)
      statsMap.savingsFcfa.textContent = formatFCFA(profile.stats.savingsFcfa);
    if (statsMap.diagnosedAnimals)
      statsMap.diagnosedAnimals.textContent = formatNumberFr(
        profile.stats.diagnosedAnimals,
      );
    if (statsMap.streak)
      statsMap.streak.textContent = `${formatNumberFr(profile.stats.streak)} j`;
    if (statsMap.trophies)
      statsMap.trophies.textContent = formatNumberFr(profile.stats.trophies);
    if (statsMap.daysUsed)
      statsMap.daysUsed.textContent = formatNumberFr(profile.stats.daysUsed);

    if (streakCurrent)
      streakCurrent.textContent = `🔥 ${profile.stats.streak} jours d'affilée !`;
    if (streakBest)
      streakBest.textContent = `Meilleure série : ${profile.bestStreak} jours`;
    if (rescueSeeds)
      rescueSeeds.textContent = `Graines de Secours disponibles : ${profile.rescueSeeds}`;

    if (rankItems.commune)
      rankItems.commune.textContent = `#${profile.classement.commune.rank} / ${profile.classement.commune.total}`;
    if (rankItems.departement)
      rankItems.departement.textContent = `#${profile.classement.departement.rank} / ${profile.classement.departement.total}`;
    if (rankItems.national)
      rankItems.national.textContent = `#${profile.classement.national.rank} / ${profile.classement.national.total}`;

    if (goldBalance) goldBalance.textContent = formatNumberFr(profile.points);

    if (trophyGrid) {
      trophyGrid.innerHTML = PROFILE_TROPHIES.map(
        (trophy) => `
        <button type="button" class="trophy ${trophy.unlocked ? "unlocked" : "locked"}" data-trophy-name="${escapeHtml(trophy.name)}" data-trophy-condition="${escapeHtml(trophy.condition)}">
          <div class="icon">${trophy.unlocked ? trophy.icon : "🔒"}</div>
          <div class="name">${escapeHtml(trophy.name)}</div>
        </button>
      `,
      ).join("");

      allByData("trophy-name").forEach((btn) => {
        btn.addEventListener("click", () => {
          const name = btn.dataset.trophyName || "";
          const condition = btn.dataset.trophyCondition || "";
          showPopup(`${name}`, condition);
        });
      });
    }

    if (shopButton && shopPanel) {
      shopButton.addEventListener("click", () => {
        shopPanel.classList.toggle("hidden");
        if (!shopPanel.innerHTML.trim()) {
          shopPanel.innerHTML = `
            <div class="history-item">
              <strong>Récompenses</strong>
              <div class="history-meta">Carte de confiance • 100 🌟</div>
            </div>
            <div class="history-item">
              <strong>Conseil premium</strong>
              <div class="history-meta">200 🌟</div>
            </div>
            <div class="history-item">
              <strong>Rappel intelligent</strong>
              <div class="history-meta">350 🌟</div>
            </div>
          `;
        }
      });
    }
  }

  function showPopup(title, message) {
    const backdrop = document.createElement("div");
    backdrop.className = "popup-backdrop";
    const popup = document.createElement("div");
    popup.className = "popup";
    popup.innerHTML = `
      <div class="popup-title">${escapeHtml(title)}</div>
      <p class="section-subtitle">${escapeHtml(message)}</p>
      <button type="button" class="btn btn-primary btn-wide" data-close-popup>Fermer</button>
    `;
    document.body.appendChild(backdrop);
    document.body.appendChild(popup);

    function close() {
      backdrop.remove();
      popup.remove();
    }

    backdrop.addEventListener("click", close);
    $("[data-close-popup]", popup)?.addEventListener("click", close);
  }

  /* ---------------------------------------------------------
     Modules : filtres et cartes
     --------------------------------------------------------- */

  function initModulesPage() {
    const filterButtons = allByData("module-filter").concat(
      $all(".filter-chip, .filter-pill"),
    );
    const cards = allByData("module-card").concat($all(".module-card"));

    if (filterButtons.length) {
      filterButtons.forEach((button) => {
        button.addEventListener("click", () => {
          const filter =
            button.dataset.filter || button.dataset.value || "Tous";
          filterButtons.forEach((b) =>
            b.classList.remove("active", "is-active"),
          );
          button.classList.add("active", "is-active");

          cards.forEach((card) => {
            const category =
              card.dataset.category || card.getAttribute("data-category") || "";
            const show =
              filter === "Tous" ||
              category.toLowerCase() === filter.toLowerCase();
            card.style.display = show ? "" : "none";
          });
        });
      });
    }

    cards.forEach((card) => {
      const action = card.querySelector("[data-module-action]");
      if (action) {
        action.addEventListener("click", () => {
          const target = card.dataset.target || action.dataset.target || "";
          if (target) {
            window.location.href = `${target}.html`;
          } else {
            toast("Module à venir", "info", 1500);
          }
        });
      }
    });
  }

  /* ---------------------------------------------------------
     FarmAcademy : catalogue, leçon et quiz
     --------------------------------------------------------- */

  function initFarmAcademy() {
    const courseCards = allByData("course-card").concat($all(".course-card"));
    const coursePanel = $("[data-course-panel]");
    const lessonPanel = $("[data-lesson-panel]");
    const nextBtn = $("[data-lesson-next]");
    const prevBtn = $("[data-lesson-prev]");
    const quizButtons = allByData("quiz-option").concat($all(".quiz-option"));
    const lessonIndexEl = $("[data-lesson-index]");

    if (courseCards.length) {
      courseCards.forEach((card) => {
        card.addEventListener("click", () => {
          if (!coursePanel || !lessonPanel) return;
          const courseId =
            card.dataset.courseId || card.dataset.id || "volailles";
          openLesson(courseId, coursePanel, lessonPanel, lessonIndexEl);
        });
      });
    }

    let lessonStep = 0;
    const currentLesson = APP.academy.lesson;

    function renderLesson(step) {
      if (!lessonPanel) return;
      lessonPanel.innerHTML = `
        <div class="lesson-view">
          <h3>${escapeHtml(currentLesson.title)}</h3>
          <div class="lesson-content">
            ${currentLesson.paragraphs.map((p) => `<p>${escapeHtml(p)}</p>`).join("")}
          </div>
          <div class="quiz-box">
            <strong>Quiz ${step + 1}/${currentLesson.quiz.length}</strong>
            <p>${escapeHtml(currentLesson.quiz[step].question)}</p>
            <div class="quiz-options">
              ${currentLesson.quiz[step].answers
                .map(
                  (answer, index) => `
                <button type="button" class="quiz-option" data-quiz-choice="${index}">${escapeHtml(answer)}</button>
              `,
                )
                .join("")}
            </div>
            <div class="muted">Réponds correctement pour gagner des points.</div>
          </div>
        </div>
      `;

      $all("[data-quiz-choice]", lessonPanel).forEach((btn) => {
        btn.addEventListener("click", () => {
          const choice = Number(btn.dataset.quizChoice || 0);
          const correct = currentLesson.quiz[step].correct;
          if (choice === correct) {
            awardPoints(20, "Bonne réponse au quiz");
            toast("Bonne réponse !", "success", 1600);
          } else {
            toast("Réponse incorrecte", "warning", 1500);
          }
        });
      });

      if (lessonIndexEl) {
        lessonIndexEl.textContent = `${step + 1}`;
      }
    }

    function openLesson(courseId, coursePanel, lessonPanel, indexEl) {
      coursePanel.classList.add("hidden");
      lessonPanel.classList.remove("hidden");
      lessonStep = 0;
      renderLesson(lessonStep);
      if (indexEl) indexEl.textContent = `${lessonStep + 1}`;
      if (nextBtn) nextBtn.disabled = false;
      if (prevBtn) prevBtn.disabled = true;
      toast(`Leçon ouverte : ${courseId}`, "info", 1600);
    }

    if (nextBtn) {
      nextBtn.addEventListener("click", () => {
        if (lessonStep < currentLesson.quiz.length - 1) {
          lessonStep += 1;
          renderLesson(lessonStep);
          if (prevBtn) prevBtn.disabled = false;
          if (lessonIndexEl) lessonIndexEl.textContent = `${lessonStep + 1}`;
        } else {
          awardPoints(20, "Leçon terminée");
          toast("Leçon terminée", "success", 1800);
        }
      });
    }

    if (prevBtn) {
      prevBtn.addEventListener("click", () => {
        if (lessonStep > 0) {
          lessonStep -= 1;
          renderLesson(lessonStep);
          if (lessonIndexEl) lessonIndexEl.textContent = `${lessonStep + 1}`;
        }
      });
    }
  }

  /* ---------------------------------------------------------
     Bind générique pour boutons d'actions
     --------------------------------------------------------- */

  function bindGeneralActions() {
    allByData("speak").forEach((btn) => {
      btn.addEventListener("click", () =>
        lireRationVocalement(APP.lastRation?.title || ""),
      );
    });

    allByData("pdf").forEach((btn) => {
      btn.addEventListener("click", () => telechargerPDF(APP.lastRation));
    });

    allByData("whatsapp").forEach((btn) => {
      btn.addEventListener("click", () => partagerWhatsApp(APP.lastRation));
    });

    allByData("save-history").forEach((btn) => {
      btn.addEventListener("click", () => {
        if (APP.lastRation) {
          saveCurrentRationToHistory(APP.lastRation);
          toast("Sauvegarde effectuée", "success", 1600);
        }
      });
    });
  }

  /* ---------------------------------------------------------
     Mode offline + cache
     --------------------------------------------------------- */

  function bindOfflineListeners() {
    window.addEventListener("online", handleOnlineState);
    window.addEventListener("offline", handleOnlineState);
  }

  /* ---------------------------------------------------------
     Raccourcis pour pages dédiées
     --------------------------------------------------------- */

  function initNutriCorePage() {
    initSpeciesGrid();
    initIngredients();
    initAnimalsSlider();
    initDailyChallenge();
    bindMicButton();
    bindGenerateButton();
    bindGeneralActions();
    renderRationHistoryBlock();
    renderOfflineCache();
  }

  function initIndexPage() {
    initSplashScreen();
    initLanguageSelector();
    initSpeciesGrid();
    initIngredients();
    initAnimalsSlider();
    initDailyChallenge();
    initWaveCanvas();
    bindMicButton();
    bindGenerateButton();
    bindGeneralActions();
    renderOfflineCache();
    updateLevelBlock();
  }

  function updateLevelBlock() {
    updateXpUI();
  }

  /* ---------------------------------------------------------
     Bootstrap
     --------------------------------------------------------- */

  function bootstrap() {
    loadAppState();
    handleOnlineState();
    bindOfflineListeners();
    initBottomNavigation();
    initLanguageSelector();
    updateXpUI();
    bindGeneralActions();

    const page = APP.currentPage || detectPage();

    if (page === "index") {
      initIndexPage();
    } else if (page === "nutricore") {
      initNutriCorePage();
    } else if (page === "vetscan") {
      initVetScan();
    } else if (page === "reprotrack") {
      initReproTrack();
    } else if (page === "profil") {
      initProfil();
    } else if (page === "classement") {
      initClassement();
    } else if (page === "modules") {
      initModulesPage();
    } else if (page === "farmacademy") {
      initFarmAcademy();
    }

    // Composants globaux supplémentaires
    initSplashScreen();
    initMicFallbacks();
    renderRationHistoryBlock();
    renderOfflineCache();
    updateLanguageUI(APP.selectedLanguage || "fr");

    // Lecture de la zone Aya si présente
    const ayaMessage =
      $("[data-aya-bubble]") || $(".aya-message") || $(".aya-points-bubble");
    if (ayaMessage && !ayaMessage.textContent.trim()) {
      ayaMessage.textContent = APP.ayaMessage;
    }
  }

  function initMicFallbacks() {
    const textareas = $all("textarea");
    textareas.forEach((area) => {
      if (!area.placeholder) {
        area.placeholder =
          LOCALIZED_HINTS[APP.selectedLanguage] || LOCALIZED_HINTS.fr;
      }
      area.addEventListener("input", () => {
        const detected = detectLanguageFromText(area.value);
        if (
          detected &&
          detected !== APP.selectedLanguage &&
          area.dataset.langAware === "1"
        ) {
          APP.selectedLanguage = detected;
          updateLanguageUI(detected);
          saveAppState();
        }
      });
    });
  }

  /* ---------------------------------------------------------
     Écoute du DOM
     --------------------------------------------------------- */

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bootstrap);
  } else {
    bootstrap();
  }

  /* ---------------------------------------------------------
     Exposition minimale pour le HTML inline éventuel
     --------------------------------------------------------- */

  window.FeedFormulaAI = {
    genererRation,
    lireRationVocalement,
    telechargerPDF,
    partagerWhatsApp,
    awardPoints,
    setAyaMood,
    toast,
  };

  // Exposition globale des fonctions demandées
  window.genererRation = genererRation;
  window.lireRationVocalement = lireRationVocalement;
  window.telechargerPDF = telechargerPDF;
  window.partagerWhatsApp = partagerWhatsApp;
})();
