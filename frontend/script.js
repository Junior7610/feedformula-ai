/* =========================================================
   FeedFormula AI — script.js
   ---------------------------------------------------------
   Logique partagée pour :
   - écran de démarrage
   - navigation et états visuels
   - NutriCore / accueil
   - VetScan
   - ReproTrack
   - Profil / trophées / boutique
   - Classement
   - FarmAcademy
   - cache local et mode hors ligne
   ========================================================= */

/* -----------------------------
   Constantes et stockage local
   ----------------------------- */
const STORAGE_KEYS = {
  app: 'feedformula_app_state_v1',
  rations: 'feedformula_rations_history_v1',
  diagnostics: 'feedformula_diagnostics_history_v1',
  repro: 'feedformula_repro_state_v1',
  profile: 'feedformula_profile_state_v1',
  academy: 'feedformula_academy_state_v1',
  language: 'feedformula_language_v1',
  cache: 'feedformula_offline_cache_v1'
};

const DEFAULT_INGREDIENTS = [
  'maïs',
  'soja',
  'tourteau de coton',
  'son de blé',
  'manioc',
  'premix',
  'coquille',
  'huile végétale',
  'drêche',
  'farine de poisson'
];

const INGREDIENT_LIBRARY = {
  maïs: { cost: 185, protein: 9, energy: 8, color: '#F9A825' },
  soja: { cost: 520, protein: 44, energy: 7, color: '#2E7D32' },
  'tourteau de coton': { cost: 275, protein: 28, energy: 6, color: '#81C784' },
  'son de blé': { cost: 140, protein: 14, energy: 5, color: '#A5D6A7' },
  manioc: { cost: 160, protein: 4, energy: 8, color: '#FDD835' },
  premix: { cost: 900, protein: 0, energy: 0, color: '#FFD54F' },
  coquille: { cost: 75, protein: 0, energy: 0, color: '#FFF8E1' },
  'huile végétale': { cost: 780, protein: 0, energy: 9, color: '#FFEE58' },
  drêche: { cost: 120, protein: 18, energy: 4, color: '#C5E1A5' },
  'farine de poisson': { cost: 980, protein: 60, energy: 6, color: '#AED581' }
};

const SPECIES_STAGES = {
  'poulet-chair': ['Démarrage', 'Croissance', 'Finition'],
  'poule-pondeuse': ['Pré-ponte', 'Ponte active', 'Fin de ponte'],
  pintade: ['Démarrage', 'Développement', 'Engraissement'],
  'vache-laitiere': ['Tarissement', 'Lactation début', 'Lactation avancée'],
  mouton: ['Agneau', 'Croissance', 'Finition'],
  chevre: ['Chevreau', 'Croissance', 'Lactation'],
  porc: ['Post-sevrage', 'Croissance', 'Finition'],
  tilapia: ['Alevin', 'Grossissement', 'Finition']
};

const OBJECTIVE_PRESETS = {
  equilibre: { label: 'Équilibre', proteinBoost: 1, costBias: 1, energyBias: 1 },
  economique: { label: 'Économique', proteinBoost: 0.9, costBias: 0.85, energyBias: 1.05 },
  proteines: { label: 'Riche protéines', proteinBoost: 1.15, costBias: 1.05, energyBias: 0.95 }
};

const TROPHIES = [
  { id: 't1', emoji: '🌱', name: 'Première ration', condition: 'Générer une ration pour la première fois.', unlocked: true },
  { id: 't2', emoji: '⚡', name: 'Défi quotidien', condition: 'Terminer 3 défis du jour.', unlocked: true },
  { id: 't3', emoji: '🩺', name: 'Soigneur', condition: 'Réaliser 5 diagnostics VetScan.', unlocked: true },
  { id: 't4', emoji: '📘', name: 'Apprenant', condition: 'Finir 1 module FarmAcademy.', unlocked: true },
  { id: 't5', emoji: '🔥', name: 'Série en feu', condition: 'Maintenir une série de 7 jours.', unlocked: true },
  { id: 't6', emoji: '🏆', name: 'Champion local', condition: 'Atteindre le top 10 communal.', unlocked: false },
  { id: 't7', emoji: '💰', name: 'Optimisateur', condition: 'Réduire le coût de ration de 15%.', unlocked: false },
  { id: 't8', emoji: '📷', name: 'Œil de lynx', condition: 'Analyser 3 photos animales.', unlocked: true },
  { id: 't9', emoji: '🧠', name: 'Stratège', condition: 'Compléter 5 quiz FarmAcademy.', unlocked: false },
  { id: 't10', emoji: '🌍', name: 'Polyglotte', condition: 'Changer de langue 5 fois.', unlocked: false },
  { id: 't11', emoji: '📈', name: 'Progression', condition: 'Passer niveau 3.', unlocked: false },
  { id: 't12', emoji: '🚀', name: 'Impulsion', condition: 'Gagner 500 🌟.', unlocked: true },
  { id: 't13', emoji: '🐔', name: 'Poulayer', condition: 'Préparer 3 rations pour volailles.', unlocked: false },
  { id: 't14', emoji: '🐄', name: 'Bovin expert', condition: 'Préparer 3 rations pour bovins.', unlocked: false },
  { id: 't15', emoji: '🐑', name: 'Rumination', condition: 'Préparer 3 rations pour petits ruminants.', unlocked: false },
  { id: 't16', emoji: '🐟', name: 'Aquaculture', condition: 'Préparer 3 rations pour poissons.', unlocked: false },
  { id: 't17', emoji: '📦', name: 'Organisé', condition: 'Sauvegarder 10 rations.', unlocked: false },
  { id: 't18', emoji: '🧾', name: 'Comptable', condition: 'Consulter 5 historiques.', unlocked: false },
  { id: 't19', emoji: '💪', name: 'Protéiné', condition: 'Atteindre 30% de protéines.', unlocked: false },
  { id: 't20', emoji: '🥇', name: 'Numéro 1', condition: 'Atteindre le rang national 1.', unlocked: false },
  { id: 't21', emoji: '📅', name: 'Ponctuel', condition: 'Utiliser l’app 14 jours d’affilée.', unlocked: true },
  { id: 't22', emoji: '🧪', name: 'Formulateur', condition: 'Tester 10 ingrédients.', unlocked: true },
  { id: 't23', emoji: '🛡️', name: 'Prévention', condition: 'Lancer 3 diagnostics sans urgence.', unlocked: true },
  { id: 't24', emoji: '🎯', name: 'Ciblé', condition: 'Choisir 3 objectifs différents.', unlocked: true },
  { id: 't25', emoji: '🌾', name: 'Agrovision', condition: 'Visiter 8 modules.', unlocked: false },
  { id: 't26', emoji: '📣', name: 'Communautaire', condition: 'Partager 5 fois sur WhatsApp.', unlocked: false },
  { id: 't27', emoji: '🗺️', name: 'Local hero', condition: 'Être top 3 communal.', unlocked: false },
  { id: 't28', emoji: '🎓', name: 'Diplômé', condition: 'Terminer FarmAcademy.', unlocked: false },
  { id: 't29', emoji: '💎', name: 'Elite', condition: 'Obtenir 2000 🌟.', unlocked: false },
  { id: 't30', emoji: '✨', name: 'Légende', condition: 'Débloquer tous les niveaux de base.', unlocked: false }
];

const SHOP_REWARDS = [
  { name: 'Astuces premium', cost: 120, desc: 'Conseils enrichis sur les rations.' },
  { name: 'Analyse prioritaire', cost: 180, desc: 'Diagnostic plus détaillé.' },
  { name: 'Pack d’images', cost: 100, desc: 'Images éducatives supplémentaires.' },
  { name: 'Boost de série', cost: 220, desc: 'Rattrapage d’une journée manquée.' }
];

const MODULES_FILTERS = {
  all: 'all',
  sante: 'sante',
  finance: 'finance',
  formation: 'formation'
};

/* -----------------------------
   État global de l’application
   ----------------------------- */
const state = {
  page: '',
  language: 'fr',
  selectedSpecies: '',
  selectedStage: '',
  objective: 'equilibre',
  ingredients: [],
  animalCount: 50,
  lastRation: null,
  currentChart: null,
  micState: 'repos',
  levelPoints: 0,
  level: 1,
  profile: {
    name: 'Léonel Togbe',
    region: 'Atlantique',
    memberSince: '12/06/2025',
    points: 480,
    stars: 480,
    streak: 12,
    bestStreak: 18,
    seedReserves: 4,
    savedRations: 28,
    totalSavings: 245000,
    diagnosedAnimals: 31,
    daysUsed: 67,
    trophies: 9
  }
};

/* -----------------------------
   Utilitaires génériques
   ----------------------------- */
function qs(selector, root = document) {
  return root.querySelector(selector);
}

function qsa(selector, root = document) {
  return Array.from(root.querySelectorAll(selector));
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function formatNumber(value) {
  return new Intl.NumberFormat('fr-FR').format(Math.round(value));
}

function loadJSON(key, fallback) {
  try {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : fallback;
  } catch {
    return fallback;
  }
}

function saveJSON(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // Rien à faire si le stockage est indisponible
  }
}

function toast(message, tone = 'success') {
  const container = ensureToastContainer();
  const item = document.createElement('div');
  item.className = `toast toast--${tone}`;
  item.textContent = message;
  container.appendChild(item);
  requestAnimationFrame(() => item.classList.add('is-visible'));
  setTimeout(() => {
    item.classList.remove('is-visible');
    setTimeout(() => item.remove(), 300);
  }, 2600);
}

function ensureToastContainer() {
  let container = qs('#toastContainer');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toastContainer';
    container.className = 'toast-container';
    document.body.appendChild(container);
  }
  return container;
}

function getDateLabel(date = new Date()) {
  return date.toLocaleDateString('fr-FR', {
    day: '2-digit',
    month: 'short',
    year: 'numeric'
  });
}

function getTimeLabel(date = new Date()) {
  return date.toLocaleTimeString('fr-FR', {
    hour: '2-digit',
    minute: '2-digit'
  });
}

function todayKey() {
  return new Date().toISOString().slice(0, 10);
}

/* -----------------------------
   Gestion du niveau et des points
   ----------------------------- */
function computeLevel(points) {
  const thresholds = [0, 100, 250, 500, 1000, 2000, 4000];
  let level = 1;
  for (let i = 0; i < thresholds.length; i += 1) {
    if (points >= thresholds[i]) level = i + 1;
  }
  return level;
}

function nextLevelThreshold(points) {
  const thresholds = [100, 250, 500, 1000, 2000, 4000, 8000];
  return thresholds.find((t) => points < t) || 8000;
}

function levelName(level) {
  const names = ['Semence', 'Tige', 'Fleur', 'Épi', 'Récolte', 'Maître', 'Légende'];
  return names[level - 1] || 'Légende';
}

function updateLevelUI() {
  const points = state.profile.points || 0;
  const level = computeLevel(points);
  const next = nextLevelThreshold(points);
  const currentName = levelName(level);
  const progress = next > points ? ((points - (level === 1 ? 0 : [0, 100, 250, 500, 1000, 2000, 4000][level - 1])) / (next - (level === 1 ? 0 : [0, 100, 250, 500, 1000, 2000, 4000][level - 1]))) * 100 : 100;
  const safeProgress = clamp(progress || 0, 0, 100);

  const levelLabel = qs('#levelLabel');
  const levelPoints = qs('#levelPoints');
  const levelProgress = qs('#levelProgress');

  if (levelLabel) levelLabel.textContent = `Niveau ${level} — ${currentName} 🌱`;
  if (levelPoints) levelPoints.textContent = `${formatNumber(points)} / ${formatNumber(next)} pts → Niveau ${level + 1}`;
  if (levelProgress) levelProgress.style.width = `${safeProgress}%`;

  const profileBadge = qs('#profileLevelBadge');
  const profileProgress = qs('#profileProgress');
  const profilePoints = qs('#profilePoints');
  const profileNext = qs('#profileNextLevel');

  if (profileBadge) profileBadge.textContent = `🌾 ${currentName}`;
  if (profileProgress) profileProgress.style.width = `${safeProgress}%`;
  if (profilePoints) profilePoints.textContent = `${formatNumber(points)} / ${formatNumber(next)} pts`;
  if (profileNext) profileNext.textContent = `Niveau suivant : ${levelName(level + 1)}`;
}

function addPoints(amount, reason = 'action') {
  state.profile.points = (state.profile.points || 0) + amount;
  state.profile.stars = (state.profile.stars || 0) + amount;
  state.level = computeLevel(state.profile.points);
  state.levelPoints = state.profile.points;
  saveProfileState();
  updateLevelUI();
  animatePoints(amount);
  updateAya(`+${amount} 🌟 pour ${reason} !`);
}

function animatePoints(amount) {
  const bubble = qs('#ayaBubble');
  if (bubble) {
    bubble.classList.remove('pulse');
    void bubble.offsetWidth;
    bubble.classList.add('pulse');
  }
  if (amount >= 20) {
    document.body.classList.add('celebrate');
    setTimeout(() => document.body.classList.remove('celebrate'), 700);
  }
}

/* -----------------------------
   Données de profil / cache
   ----------------------------- */
function loadProfileState() {
  const stored = loadJSON(STORAGE_KEYS.profile, null);
  if (stored) {
    state.profile = { ...state.profile, ...stored };
  }
  state.ingredients = loadJSON(STORAGE_KEYS.app, {}).ingredients || [];
  state.objective = loadJSON(STORAGE_KEYS.app, {}).objective || 'equilibre';
  state.selectedSpecies = loadJSON(STORAGE_KEYS.app, {}).selectedSpecies || '';
  state.selectedStage = loadJSON(STORAGE_KEYS.app, {}).selectedStage || '';
  state.animalCount = loadJSON(STORAGE_KEYS.app, {}).animalCount || 50;
  state.language = localStorage.getItem(STORAGE_KEYS.language) || 'fr';
}

function saveProfileState() {
  saveJSON(STORAGE_KEYS.profile, state.profile);
  saveJSON(STORAGE_KEYS.app, {
    ingredients: state.ingredients,
    objective: state.objective,
    selectedSpecies: state.selectedSpecies,
    selectedStage: state.selectedStage,
    animalCount: state.animalCount
  });
  localStorage.setItem(STORAGE_KEYS.language, state.language);
}

function loadRationHistory() {
  return loadJSON(STORAGE_KEYS.rations, []);
}

function saveRationHistory(history) {
  saveJSON(STORAGE_KEYS.rations, history.slice(0, 5));
}

function loadDiagnosticHistory() {
  return loadJSON(STORAGE_KEYS.diagnostics, []);
}

function saveDiagnosticHistory(history) {
  saveJSON(STORAGE_KEYS.diagnostics, history.slice(0, 5));
}

/* -----------------------------
   Splash screen
   ----------------------------- */
function initSplashScreen() {
  const splash = qs('#splashScreen');
  if (!splash) return;
  setTimeout(() => {
    splash.classList.add('is-hidden');
    setTimeout(() => splash.remove(), 500);
  }, 2000);
}

/* -----------------------------
   Navigation et liens actifs
   ----------------------------- */
function initNavigation() {
  const page = document.body.dataset.page || inferPageFromPath();
  state.page = page;

  qsa('.bottom-nav__item').forEach((link) => {
    const href = link.getAttribute('href') || '';
    const isActive =
      (page === 'accueil' && href.includes('index.html')) ||
      (page === 'modules' && href.includes('modules.html')) ||
      (page === 'nutricore' && href.includes('nutricore.html')) ||
      (page === 'vetscan' && href.includes('vetscan.html')) ||
      (page === 'reprotrack' && href.includes('reprotrack.html')) ||
      (page === 'profil' && href.includes('profil.html')) ||
      (page === 'classement' && href.includes('classement.html')) ||
      (page === 'farmacademy' && href.includes('farmacademy.html'));
    link.classList.toggle('is-active', isActive);
  });
}

function inferPageFromPath() {
  const path = location.pathname.toLowerCase();
  if (path.includes('modules')) return 'modules';
  if (path.includes('nutricore')) return 'nutricore';
  if (path.includes('vetscan')) return 'vetscan';
  if (path.includes('reprotrack')) return 'reprotrack';
  if (path.includes('profil')) return 'profil';
  if (path.includes('classement')) return 'classement';
  if (path.includes('farmacademy')) return 'farmacademy';
  return 'accueil';
}

/* -----------------------------
   Aya — messages contextuels
   ----------------------------- */
function updateAya(message) {
  const bubble = qs('#ayaBubble');
  if (bubble) bubble.textContent = message;
}

function setAyaState(stateName) {
  const image = qs('.aya-widget__image');
  if (!image) return;
  const mapping = {
    joie: '../assets/aya_joie.png',
    celebration: '../assets/aya_celebration.png',
    triste: '../assets/aya_triste.png',
    animaux: '../assets/aya_avec_animaux.png'
  };
  image.src = mapping[stateName] || mapping.joie;
}

/* -----------------------------
   Langues
   ----------------------------- */
function initLanguageSwitcher() {
  const switcher = qs('#languageSwitcher');
  const panel = qs('#languagePanel');
  const moreBtn = qs('#languageMoreBtn');
  if (!switcher) return;

  const languages = [
    ['fr', 'Français'], ['fon', 'Fɔ̀ngbè'], ['yor', 'Yoruba'], ['den', 'Dendi'], ['en', 'English'],
    ['ha', 'Hausa'], ['sw', 'Swahili'], ['ig', 'Igbo'], ['ar', 'العربية'], ['pt', 'Português'],
    ['es', 'Español'], ['de', 'Deutsch'], ['it', 'Italiano'], ['nl', 'Nederlands'], ['ru', 'Русский'],
    ['tr', 'Türkçe'], ['hi', 'हिन्दी'], ['bn', 'বাংলা'], ['zh', '中文'], ['ja', '日本語'],
    ['ko', '한국어'], ['vi', 'Tiếng Việt'], ['ms', 'Bahasa Melayu'], ['id', 'Bahasa Indonesia'], ['th', 'ไทย'],
    ['km', 'ខ្មែរ'], ['lo', 'ລາວ'], ['zu', 'isiZulu'], ['xh', 'isiXhosa'], ['am', 'አማርኛ'],
    ['sn', 'Shona'], ['rw', 'Kinyarwanda'], ['mg', 'Malagasy'], ['so', 'Soomaali'], ['tn', 'Setswana'],
    ['yo', 'Yorùbá'], ['ff', 'Pulaar'], ['wo', 'Wolof'], ['st', 'Sesotho'], ['ti', 'Tigrinya'],
    ['ak', 'Akan'], ['ee', 'Eʋegbe'], ['ga', 'Gaeilge'], ['pl', 'Polski'], ['uk', 'Українська'],
    ['el', 'Ελληνικά'], ['cs', 'Čeština'], ['ro', 'Română'], ['fi', 'Suomi'], ['sv', 'Svenska']
  ];

  if (panel) {
    panel.innerHTML = languages
      .map(([code, label]) => `<button type="button" class="language-panel__item" data-lang="${code}">${label}</button>`)
      .join('');
  }

  const activateLanguage = (code) => {
    state.language = code;
    saveProfileState();
    qsa('.language-pill').forEach((btn) => {
      btn.classList.toggle('is-active', btn.dataset.lang === code);
    });
    qsa('.language-panel__item').forEach((btn) => {
      btn.classList.toggle('is-active', btn.dataset.lang === code);
    });
    updateAya(`Langue active : ${code.toUpperCase()}`);
  };

  qsa('.language-pill').forEach((btn) => {
    if (btn.dataset.lang === state.language) btn.classList.add('is-active');
    btn.addEventListener('click', () => {
      if (btn.dataset.lang) activateLanguage(btn.dataset.lang);
      if (panel) panel.hidden = true;
    });
  });

  if (panel) {
    qsa('.language-panel__item', panel).forEach((btn) => {
      if (btn.dataset.lang === state.language) btn.classList.add('is-active');
      btn.addEventListener('click', () => {
        activateLanguage(btn.dataset.lang || 'fr');
        panel.hidden = true;
      });
    });
  }

  if (moreBtn && panel) {
    moreBtn.addEventListener('click', () => {
      panel.hidden = !panel.hidden;
    });
  }

  activateLanguage(state.language);
}

/* -----------------------------
   Microphone / voix
   ----------------------------- */
let recognition = null;
let voiceAnimationId = null;

function initMicrophone() {
  const button = qs('#micButton');
  const status = qs('#micStatus');
  const canvas = qs('#voiceCanvas');
  const description = qs('#descriptionInput') || qs('#symptomsInput');
  if (!button && !canvas) return;

  const setState = (nextState) => {
    state.micState = nextState;
    if (button) {
      button.dataset.state = nextState;
      button.setAttribute('aria-pressed', String(nextState !== 'repos'));
    }
    if (status) {
      const labels = {
        repos: 'Repos',
        ecoute: 'Écoute en cours…',
        traitement: 'Traitement…',
        succes: 'Succès'
      };
      status.textContent = labels[nextState] || 'Repos';
    }
    updateAya(
      nextState === 'ecoute'
        ? 'Je vous écoute.'
        : nextState === 'traitement'
          ? 'Je traite votre voix.'
          : nextState === 'succes'
            ? 'Message compris !'
            : 'Mic au repos.'
    );
  };

  const stopRecognition = () => {
    try {
      recognition?.stop?.();
    } catch {
      // Rien
    }
  };

  const startRecognition = () => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      setState('succes');
      if (description) {
        description.value = `${description.value ? `${description.value}\n` : ''}Décrivez vos animaux et vos ingrédients...`;
      }
      setTimeout(() => setState('repos'), 1200);
      return;
    }

    recognition = new SpeechRecognition();
    recognition.lang = state.language === 'en' ? 'en-US' : 'fr-FR';
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;

    recognition.onstart = () => setState('ecoute');
    recognition.onresult = (event) => {
      const transcript = event.results[0][0].transcript;
      if (description) {
        description.value = `${description.value ? `${description.value}\n` : ''}${transcript}`;
      }
      setState('succes');
      setTimeout(() => setState('repos'), 1300);
    };
    recognition.onerror = () => {
      setState('repos');
      toast('Reconnaissance vocale indisponible.', 'warning');
    };
    recognition.onend = () => {
      if (state.micState !== 'succes') setState('repos');
    };

    recognition.start();
  };

  if (button) {
    button.addEventListener('click', () => {
      if (state.micState === 'ecoute') {
        stopRecognition();
        setState('repos');
        return;
      }
      setState('traitement');
      setTimeout(startRecognition, 350);
    });
  }

  if (canvas) {
    const ctx = canvas.getContext('2d');
    const draw = (tick) => {
      if (!ctx) return;
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      const bars = 20;
      const step = canvas.width / bars;
      for (let i = 0; i < bars; i += 1) {
        const phase = tick / 12 + i / 1.8;
        const base = state.micState === 'ecoute' ? 0.55 : state.micState === 'traitement' ? 0.35 : state.micState === 'succes' ? 0.75 : 0.18;
        const amp = Math.max(0.08, base + Math.sin(phase) * (state.micState === 'repos' ? 0.08 : 0.22));
        const height = amp * canvas.height * 0.7;
        const x = i * step + step * 0.18;
        const y = (canvas.height - height) / 2;
        ctx.fillStyle = i % 2 === 0 ? '#1B5E20' : '#F9A825';
        ctx.beginPath();
        roundRect(ctx, x, y, step * 0.45, height, 999);
        ctx.fill();
      }
      voiceAnimationId = requestAnimationFrame(() => draw(tick + 1));
    };
    cancelAnimationFrame(voiceAnimationId);
    draw(0);
  }
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

/* -----------------------------
   Espèces et stades
   ----------------------------- */
function initSpeciesAndStages() {
  const grid = qs('#speciesGrid');
  const stageSection = qs('#stageSection');
  const stageSelector = qs('#stageSelector');
  if (!grid) return;

  const setSpecies = (species) => {
    state.selectedSpecies = species;
    state.selectedStage = '';
    saveProfileState();
    qsa('.species-card', grid).forEach((card) => {
      card.classList.toggle('is-active', card.dataset.species === species);
    });
    renderStages();
    if (stageSection) stageSection.hidden = false;
    updateAya(`Espèce sélectionnée : ${formatSpeciesName(species)}`);
    setAyaState('animaux');
  };

  const speciesFromSaved = state.selectedSpecies || qsa('.species-card', grid)[0]?.dataset.species || '';
  if (speciesFromSaved) setSpecies(speciesFromSaved);

  qsa('.species-card', grid).forEach((card) => {
    card.addEventListener('click', () => setSpecies(card.dataset.species || ''));
  });

  function renderStages() {
    if (!stageSelector) return;
    const stages = SPECIES_STAGES[state.selectedSpecies] || [];
    stageSelector.innerHTML = stages
      .map(
        (stage) =>
          `<button type="button" class="stage-chip ${stage === state.selectedStage ? 'is-active' : ''}" data-stage="${stage}">${stage}</button>`
      )
      .join('');
    qsa('.stage-chip', stageSelector).forEach((chip) => {
      chip.addEventListener('click', () => {
        state.selectedStage = chip.dataset.stage || '';
        saveProfileState();
        renderStages();
        updateAya(`Stade choisi : ${state.selectedStage}`);
      });
    });
  }

  renderStages();
}

function formatSpeciesName(code) {
  const map = {
    'poulet-chair': 'Poulet chair',
    'poule-pondeuse': 'Poule pondeuse',
    pintade: 'Pintade',
    'vache-laitiere': 'Vache laitière',
    mouton: 'Mouton',
    chevre: 'Chèvre',
    porc: 'Porc',
    tilapia: 'Tilapia'
  };
  return map[code] || code;
}

/* -----------------------------
   Ingrédients : suggestions + tags
   ----------------------------- */
function initIngredients() {
  const input = qs('#ingredientInput');
  const suggestions = qs('#ingredientSuggestions');
  const tags = qs('#ingredientTags');
  if (!input || !tags) return;

  const renderTags = () => {
    tags.innerHTML = state.ingredients
      .map((ing) => `<button type="button" class="ingredient-tag" data-ingredient="${ing}">${ing} ×</button>`)
      .join('');
    qsa('.ingredient-tag', tags).forEach((tag) => {
      tag.addEventListener('click', () => {
        const ingredient = tag.dataset.ingredient;
        state.ingredients = state.ingredients.filter((item) => item !== ingredient);
        saveProfileState();
        renderTags();
        updateAya(`Ingrédient retiré : ${ingredient}`);
      });
    });
  };

  const renderSuggestions = (value) => {
    if (!suggestions) return;
    const query = value.trim().toLowerCase();
    const candidates = DEFAULT_INGREDIENTS.filter((item) => item.toLowerCase().includes(query)).slice(0, 6);
    suggestions.innerHTML = candidates
      .map((item) => `<button type="button" class="suggestion-pill" data-ingredient="${item}">${item}</button>`)
      .join('');
    qsa('.suggestion-pill', suggestions).forEach((btn) => {
      btn.addEventListener('click', () => addIngredient(btn.dataset.ingredient || ''));
    });
  };

  const addIngredient = (ingredient) => {
    const clean = ingredient.trim().toLowerCase();
    if (!clean) return;
    const canonical = DEFAULT_INGREDIENTS.find((item) => item.toLowerCase() === clean) || ingredient.trim();
    if (!state.ingredients.includes(canonical)) {
      state.ingredients.push(canonical);
      saveProfileState();
      renderTags();
      updateAya(`Ingrédient ajouté : ${canonical}`);
    }
    input.value = '';
    if (suggestions) suggestions.innerHTML = '';
  };

  input.addEventListener('input', () => renderSuggestions(input.value));
  input.addEventListener('keydown', (event) => {
    if (event.key === 'Enter') {
      event.preventDefault();
      const value = input.value.split(',')[0];
      addIngredient(value);
    }
  });

  document.addEventListener('click', (event) => {
    if (!suggestions || !event.target) return;
    if (!suggestions.contains(event.target) && event.target !== input) {
      suggestions.innerHTML = '';
    }
  });

  renderTags();
}

function initSlider() {
  const slider = qs('#animalCountSlider');
  const value = qs('#animalCountValue');
  if (!slider || !value) return;
  slider.value = String(state.animalCount || 50);
  value.textContent = slider.value;
  slider.addEventListener('input', () => {
    state.animalCount = Number(slider.value);
    value.textContent = slider.value;
    saveProfileState();
  });
}

/* -----------------------------
   Objectif de ration
   ----------------------------- */
function initObjectiveButtons() {
  const buttons = qsa('.objective-option');
  if (!buttons.length) return;

  const setObjective = (objective) => {
    state.objective = objective;
    saveProfileState();
    buttons.forEach((btn) => btn.classList.toggle('is-active', btn.dataset.objective === objective));
    updateAya(`Objectif choisi : ${OBJECTIVE_PRESETS[objective]?.label || objective}`);
  };

  buttons.forEach((btn) => {
    btn.addEventListener('click', () => setObjective(btn.dataset.objective || 'equilibre'));
    btn.classList.toggle('is-active', btn.dataset.objective === state.objective);
  });
}

/* -----------------------------
   Défi du jour
   ----------------------------- */
function initDailyChallenge() {
  const countdown = qs('#dailyCountdown');
  if (!countdown) return;

  const updateCountdown = () => {
    const now = new Date();
    const end = new Date();
    end.setHours(23, 59, 59, 999);
    const diff = Math.max(0, end - now);
    const hours = String(Math.floor(diff / 3600000)).padStart(2, '0');
    const minutes = String(Math.floor((diff % 3600000) / 60000)).padStart(2, '0');
    const seconds = String(Math.floor((diff % 60000) / 1000)).padStart(2, '0');
    countdown.textContent = `${hours}:${minutes}:${seconds}`;
  };

  updateCountdown();
  setInterval(updateCountdown, 1000);
}

/* -----------------------------
   Génération de ration
   ----------------------------- */
function getSelectedIngredientLibrary() {
  const ingredients = state.ingredients.length ? state.ingredients : ['maïs', 'soja', 'son de blé', 'premix'];
  return ingredients.map((name, index) => {
    const lib = INGREDIENT_LIBRARY[name.toLowerCase()] || {
      cost: 200 + index * 30,
      protein: 10 + index * 2,
      energy: 5 + index,
      color: ['#1B5E20', '#2E7D32', '#F9A825', '#A5D6A7'][index % 4]
    };
    return { name, ...lib };
  });
}

function buildRation() {
  const items = getSelectedIngredientLibrary();
  const objective = OBJECTIVE_PRESETS[state.objective] || OBJECTIVE_PRESETS.equilibre;
  const species = formatSpeciesName(state.selectedSpecies || 'espèce');
  const stage = state.selectedStage || 'stade non précisé';
  const totalShare = 100;
  const count = state.animalCount || 50;

  const shares = items.map((item, index) => {
    const base = 100 / items.length;
    const bias = objective.costBias + (index === 0 ? 0.08 : 0);
    const proteinFactor = objective.proteinBoost + item.protein / 100;
    return base * bias * proteinFactor;
  });

  const shareSum = shares.reduce((a, b) => a + b, 0) || 1;
  const normalized = shares.map((value) => Math.round((value / shareSum) * totalShare));
  const diff = totalShare - normalized.reduce((a, b) => a + b, 0);
  if (normalized.length) normalized[0] += diff;

  const composition = items.map((item, index) => ({
    name: item.name,
    share: clamp(normalized[index] || 0, 0, 100),
    cost: item.cost,
    protein: item.protein,
    color: item.color
  }));

  const costPerKg = composition.reduce((sum, item) => sum + item.cost * (item.share / 100), 0) * objective.costBias;
  const protein = composition.reduce((sum, item) => sum + item.protein * (item.share / 100), 0) * objective.proteinBoost;
  const totalKg = Math.max(1, Math.round((count * 0.12) / 10) * 10);
  const totalCost = Math.round(costPerKg * totalKg * 100 / 1000 * 10);
  const costPerAnimal = Math.round(totalCost / count);

  return {
    species,
    stage,
    objective: objective.label,
    count,
    totalKg,
    totalCost,
    costPerAnimal,
    protein: clamp(protein, 0, 60),
    composition,
    steps: [
      `Peser ${composition.map((item) => `${item.share}% ${item.name}`).join(', ')}.`,
      `Mélanger soigneusement pendant 8 à 10 minutes.`,
      `Distribuer ${Math.round(totalKg / count * 1000)} g par animal et par jour.`
    ]
  };
}

function formatRationText(ration) {
  const lines = [];
  lines.push(`━━━ RATION ${ration.species.toUpperCase()} ━━━`);
  lines.push(`Stade : ${ration.stage}`);
  lines.push(`Objectif : ${ration.objective}`);
  lines.push(`Animaux : ${ration.count}`);
  lines.push(`Coût total : ${formatNumber(ration.totalCost)} FCFA`);
  lines.push(`Coût / animal : ${formatNumber(ration.costPerAnimal)} FCFA`);
  lines.push(`Protéines estimées : ${ration.protein.toFixed(1)}%`);
  lines.push('Composition :');
  ration.composition.forEach((item) => {
    lines.push(`- ${item.name} : ${item.share}%`);
  });
  lines.push('━━━');
  return lines.join('\n');
}

function renderRationChart(ration) {
  const canvas = qs('#compositionChart');
  if (!canvas) return;

  const labels = ration.composition.map((item) => item.name);
  const data = ration.composition.map((item) => item.share);
  const colors = ration.composition.map((item) => item.color);

  if (window.Chart) {
    if (state.currentChart) {
      state.currentChart.destroy();
    }
    state.currentChart = new Chart(canvas, {
      type: 'doughnut',
      data: {
        labels,
        datasets: [
          {
            data,
            backgroundColor: colors,
            borderColor: '#FFFFFF',
            borderWidth: 2
          }
        ]
      },
      options: {
        responsive: true,
        plugins: {
          legend: {
            position: 'bottom',
            labels: {
              boxWidth: 12,
              usePointStyle: true
            }
          }
        }
      }
    });
  }
}

function renderRationResult(ration) {
  const resultSection = qs('#resultSection');
  const rationText = qs('#rationText');
  const rationCost = qs('#rationCost');
  const rationVolume = qs('#rationVolume');
  const rationProtein = qs('#rationProtein');
  const rationSteps = qs('#rationSteps');

  if (resultSection) {
    resultSection.hidden = false;
    resultSection.classList.add('slide-in');
    setTimeout(() => resultSection.classList.remove('slide-in'), 700);
  }

  if (rationText) rationText.textContent = formatRationText(ration);
  if (rationCost) rationCost.textContent = `${formatNumber(ration.totalCost)} FCFA`;
  if (rationVolume) rationVolume.textContent = `${formatNumber(ration.totalKg)} kg`;
  if (rationProtein) rationProtein.textContent = `${ration.protein.toFixed(1)}%`;

  if (rationSteps) {
    rationSteps.innerHTML = ration.steps
      .map((step, index) => `<div class="ration-step"><strong>${index + 1}.</strong><span>${step}</span></div>`)
      .join('');
  }

  renderRationChart(ration);
  updateAya('Ration prête. Vous pouvez l’écouter, l’exporter ou la partager.');
  setAyaState('celebration');
}

function storeRation(ration) {
  const history = loadRationHistory();
  history.unshift({
    date: new Date().toISOString(),
    species: ration.species,
    stage: ration.stage,
    cost: ration.totalCost,
    text: formatRationText(ration),
    composition: ration.composition
  });
  saveRationHistory(history);
  saveOfflineCache({ lastRation: history[0], rations: history });
  renderRationHistory();
}

function renderRationHistory() {
  const list = qs('#rationHistory');
  if (!list) return;
  const history = loadRationHistory();
  list.innerHTML = history
    .slice(0, 5)
    .map(
      (item, index) => `
        <article class="history-item">
          <div>
            <strong>${getDateLabel(new Date(item.date))}</strong>
            <p>${item.species} · ${item.cost} FCFA</p>
          </div>
          <button type="button" class="secondary-action history-item__btn" data-index="${index}">Revoir</button>
        </article>
      `
    )
    .join('');

  qsa('.history-item__btn', list).forEach((btn) => {
    btn.addEventListener('click', () => {
      const item = history[Number(btn.dataset.index || 0)];
      if (!item) return;
      const ration = {
        species: item.species,
        stage: item.stage,
        objective: OBJECTIVE_PRESETS[state.objective]?.label || 'Équilibre',
        count: state.animalCount,
        totalKg: 60,
        totalCost: item.cost,
        costPerAnimal: Math.round(item.cost / Math.max(1, state.animalCount)),
        protein: 22,
        composition: item.composition || [],
        steps: ['Ration chargée depuis l’historique.']
      };
      renderRationResult(ration);
      updateAya('Ration relue depuis l’historique.');
    });
  });
}

function saveOfflineCache(extra = {}) {
  const payload = {
    lastPage: state.page,
    profile: state.profile,
    app: {
      ingredients: state.ingredients,
      objective: state.objective,
      selectedSpecies: state.selectedSpecies,
      selectedStage: state.selectedStage,
      animalCount: state.animalCount
    },
    ...extra
  };
  saveJSON(STORAGE_KEYS.cache, payload);
}

function loadOfflineCache() {
  return loadJSON(STORAGE_KEYS.cache, null);
}

function genererRation() {
  const ration = buildRation();
  state.lastRation = ration;
  renderRationResult(ration);
  storeRation(ration);
  addPoints(10, 'la génération de votre ration');
  saveOfflineCache({ lastRation: ration });
  return ration;
}

function lireRationVocalement(text = '') {
  const synth = window.speechSynthesis;
  if (!synth) {
    toast('La synthèse vocale n’est pas disponible.', 'warning');
    return;
  }
  const utterance = new SpeechSynthesisUtterance(text || qs('#rationText')?.textContent || '');
  utterance.lang = state.language === 'en' ? 'en-US' : 'fr-FR';
  utterance.rate = 0.95;
  synth.cancel();
  synth.speak(utterance);
  updateAya('Je lis la ration à voix haute.');
}

function telechargerPDF() {
  const ration = state.lastRation;
  if (!ration) {
    toast('Aucune ration à exporter.', 'warning');
    return;
  }

  const jsPDFClass = window.jspdf?.jsPDF || window.jsPDF;
  if (!jsPDFClass) {
    toast('Export PDF indisponible.', 'warning');
    return;
  }

  const doc = new jsPDFClass();
  doc.setFontSize(18);
  doc.text('FeedFormula AI - Ration', 14, 18);
  doc.setFontSize(11);
  const lines = formatRationText(ration).split('\n');
  doc.text(lines, 14, 30);
  doc.save(`ration-${todayKey()}.pdf`);
  updateAya('PDF téléchargé avec succès.');
  addPoints(2, 'l’export PDF');
}

function partagerWhatsApp() {
  const text = state.lastRation ? formatRationText(state.lastRation) : 'Découvrez FeedFormula AI.';
  const url = `https://wa.me/?text=${encodeURIComponent(text)}`;
  window.open(url, '_blank', 'noopener,noreferrer');
  addPoints(2, 'le partage WhatsApp');
}

/* -----------------------------
   Boutons d’action de ration
   ----------------------------- */
function initRationActions() {
  const generateButton = qs('#generateButton');
  const speakButton = qs('#speakButton');
  const pdfButton = qs('#pdfButton');
  const whatsappButton = qs('#whatsappButton');
  const saveHistoryButton = qs('#saveHistoryButton');

  if (generateButton) generateButton.addEventListener('click', genererRation);
  if (speakButton) speakButton.addEventListener('click', () => lireRationVocalement());
  if (pdfButton) pdfButton.addEventListener('click', telechargerPDF);
  if (whatsappButton) whatsappButton.addEventListener('click', partagerWhatsApp);
  if (saveHistoryButton) {
    saveHistoryButton.addEventListener('click', () => {
      if (state.lastRation) {
        storeRation(state.lastRation);
        toast('Ration enregistrée dans l’historique.');
      }
    });
  }
}

/* -----------------------------
   Modules
   ----------------------------- */
function initModulesPage() {
  const buttons = qsa('.filter-pill[data-filter]');
  const cards = qsa('.module-card');
  if (!buttons.length || !cards.length) return;

  buttons.forEach((btn) => {
    btn.addEventListener('click', () => {
      buttons.forEach((item) => item.classList.toggle('is-active', item === btn));
      const filter = btn.dataset.filter || 'all';
      cards.forEach((card) => {
        const categories = (card.dataset.category || '').split(' ');
        card.hidden = filter !== 'all' && !categories.includes(filter);
      });
    });
  });
}

/* -----------------------------
   VetScan
   ----------------------------- */
function initVetScanPage() {
  const photoInput = qs('#photoInput');
  const photoButton = qs('#photoButton');
  const photoPreview = qs('#photoPreview');
  const analyzePhotoButton = qs('#analyzePhotoButton');
  const micButton = qs('#vetscanMicButton');
  const symptomsInput = qs('#symptomsInput');
  const speciesSelect = qs('#vetscanSpecies');
  const diagnoseButton = qs('#diagnoseButton');
  const result = qs('#vetscanResult');
  const confidence = qs('#confidenceScore');
  const diagnosisList = qs('#diagnosisList');
  const protocol = qs('#careProtocol');
  const decision = qs('#decisionBanner');
  const findVetButton = qs('#findVetButton');
  const historyList = qs('#diagnosisHistory');

  if (!diagnoseButton) return;

  if (photoButton && photoInput) {
    photoButton.addEventListener('click', () => photoInput.click());
    photoInput.addEventListener('change', () => {
      const file = photoInput.files?.[0];
      if (file && photoPreview) {
        photoPreview.src = URL.createObjectURL(file);
        photoPreview.classList.add('is-visible');
        updateAya('Photo prête pour l’analyse.');
      }
    });
  }

  if (analyzePhotoButton) {
    analyzePhotoButton.addEventListener('click', () => {
      toast('Photo analysée localement.');
      updateAya('Je prépare l’analyse de la photo.');
    });
  }

  if (micButton) {
    micButton.addEventListener('click', () => {
      updateAya('Décrivez les symptômes oralement.');
      toast('Fonction micro activée.');
    });
  }

  const diagnose = () => {
    const symptoms = (symptomsInput?.value || '').toLowerCase();
    const species = speciesSelect?.value || 'général';
    const urgentWords = ['sang', 'mort', 'difficulté', 'respiration', 'convulsion', 'paralysie', 'urgence'];
    const warningWords = ['fièvre', 'diarrhée', 'boiter', 'gonfle', 'abattu', 'toux', 'plaie', 'perte'];

    const urgentScore = urgentWords.reduce((acc, word) => acc + (symptoms.includes(word) ? 1 : 0), 0);
    const warningScore = warningWords.reduce((acc, word) => acc + (symptoms.includes(word) ? 1 : 0), 0);

    const isUrgent = urgentScore >= 2 || (warningScore >= 3 && species !== 'tilapia');
    const score = clamp(95 - urgentScore * 15 - warningScore * 6, 42, 99);
    const items = isUrgent
      ? [
          { label: 'Infection sévère', prob: 46 },
          { label: 'Déshydratation', prob: 31 },
          { label: 'Complication respiratoire', prob: 23 }
        ]
      : [
          { label: 'Trouble digestif léger', prob: 42 },
          { label: 'Stress thermique', prob: 33 },
          { label: 'Carence alimentaire', prob: 25 }
        ];

    if (result) result.hidden = false;
    if (confidence) confidence.textContent = `${score}%`;

    if (diagnosisList) {
      diagnosisList.innerHTML = items
        .map(
          (item) => `
            <div class="probability-item">
              <div class="probability-item__header">
                <strong>${item.label}</strong>
                <span>${item.prob}%</span>
              </div>
              <div class="progress-track"><span class="progress-track__bar" style="width:${item.prob}%"></span></div>
            </div>
          `
        )
        .join('');
    }

    if (protocol) {
      protocol.innerHTML = isUrgent
        ? [
            'Isoler immédiatement l’animal.',
            'Limiter les déplacements et apporter de l’eau propre.',
            'Contacter un vétérinaire dans les plus brefs délais.'
          ]
            .map((step) => `<li>${step}</li>`)
            .join('')
        : [
            'Nettoyer le box ou l’enclos.',
            'Administrer de l’eau fraîche et surveiller l’alimentation.',
            'Recontrôler dans 12 heures.'
          ]
            .map((step) => `<li>${step}</li>`)
            .join('');
    }

    if (decision) {
      decision.className = `decision-banner ${isUrgent ? 'decision-banner--danger' : 'decision-banner--ok'}`;
      decision.textContent = isUrgent ? '⚠️ URGENCE VÉTÉRINAIRE' : '✅ Soins autonomes possibles';
    }

    if (findVetButton) findVetButton.hidden = !isUrgent;

    const history = loadDiagnosticHistory();
    history.unshift({
      date: new Date().toISOString(),
      species,
      symptoms,
      score,
      urgent: isUrgent
    });
    saveDiagnosticHistory(history);
    renderDiagnosticHistory();

    addPoints(20, 'le diagnostic VetScan');
    updateAya(isUrgent ? 'Vérifiez rapidement l’animal.' : 'Un soin autonome semble possible.');
  };

  diagnoseButton.addEventListener('click', diagnose);
  if (findVetButton) {
    findVetButton.addEventListener('click', () => {
      window.open('https://www.google.com/maps/search/veterinaire', '_blank', 'noopener,noreferrer');
    });
  }

  renderDiagnosticHistory();
}

function renderDiagnosticHistory() {
  const historyList = qs('#diagnosisHistory');
  if (!historyList) return;
  const history = loadDiagnosticHistory();
  historyList.innerHTML = history.slice(0, 5).map((item) => `
    <article class="history-item">
      <div>
        <strong>${getDateLabel(new Date(item.date))}</strong>
        <p>${item.species} · ${item.score}%</p>
      </div>
      <span class="status-badge ${item.urgent ? 'status-badge--danger' : 'status-badge--ok'}">${item.urgent ? 'Urgent' : 'OK'}</span>
    </article>
  `).join('');
}

/* -----------------------------
   ReproTrack
   ----------------------------- */
function initReproTrackPage() {
  const calendar = qs('#reproCalendar');
  const monthLabel = qs('#calendarMonthLabel');
  const trackedAnimals = qs('#trackedAnimals');
  const eventType = qs('#eventType');
  const eventAnimal = qs('#eventAnimal');
  const saveEventButton = qs('#saveEventButton');
  const fertilityRate = qs('#fertilityRate');
  const calvingInterval = qs('#calvingInterval');
  const birthsThisMonth = qs('#birthsThisMonth');
  if (!calendar) return;

  const stateRepro = loadJSON(STORAGE_KEYS.repro, {
    events: [],
    animals: [
      { name: 'Vache 014', status: 'Gestante', nextEventDays: 18 },
      { name: 'Vache 022', status: 'En chaleur', nextEventDays: 3 },
      { name: 'Chèvre 08', status: 'Vide', nextEventDays: 26 },
      { name: 'Mouton 17', status: 'Gestante', nextEventDays: 44 }
    ]
  });

  const saveRepro = () => saveJSON(STORAGE_KEYS.repro, stateRepro);

  const renderCalendar = () => {
    const now = new Date();
    monthLabel.textContent = now.toLocaleDateString('fr-FR', { month: 'long', year: 'numeric' });
    const first = new Date(now.getFullYear(), now.getMonth(), 1);
    const daysInMonth = new Date(now.getFullYear(), now.getMonth() + 1, 0).getDate();
    const startDay = first.getDay() || 7;

    const heatDays = [3, 12, 18, 24];
    const inseminationDays = [5, 15, 26];
    const birthDays = [9, 21, 29];

    const cells = [];
    for (let i = 1; i < startDay; i += 1) {
      cells.push('<div class="calendar-day calendar-day--empty"></div>');
    }
    for (let day = 1; day <= daysInMonth; day += 1) {
      let cls = 'calendar-day';
      if (heatDays.includes(day)) cls += ' calendar-day--heat';
      if (inseminationDays.includes(day)) cls += ' calendar-day--insemination';
      if (birthDays.includes(day)) cls += ' calendar-day--birth';
      cells.push(`<div class="${cls}"><strong>${day}</strong></div>`);
    }
    calendar.innerHTML = cells.join('');
  };

  const renderAnimals = () => {
    if (!trackedAnimals) return;
    trackedAnimals.innerHTML = stateRepro.animals.map((animal) => `
      <article class="tracked-item">
        <div>
          <strong>${animal.name}</strong>
          <p>Statut : ${animal.status}</p>
        </div>
        <span class="tracked-item__days">${animal.nextEventDays} j</span>
      </article>
    `).join('');
  };

  const renderStats = () => {
    if (fertilityRate) fertilityRate.textContent = '74%';
    if (calvingInterval) calvingInterval.textContent = '380 jours';
    if (birthsThisMonth) birthsThisMonth.textContent = '6';
  };

  const addEvent = () => {
    const type = eventType?.value || 'saillie';
    const animal = (eventAnimal?.value || '').trim() || 'Animal inconnu';
    stateRepro.events.unshift({ type, animal, date: new Date().toISOString() });
    stateRepro.events = stateRepro.events.slice(0, 30);
    if (eventAnimal) eventAnimal.value = '';
    saveRepro();
    toast('Événement enregistré.');
    updateAya(`Événement ajouté pour ${animal}.`);
    addPoints(5, 'un événement reproduction');
    renderAnimals();
    renderCalendar();
  };

  if (saveEventButton) saveEventButton.addEventListener('click', addEvent);

  renderCalendar();
  renderAnimals();
  renderStats();
}

/* -----------------------------
   Profil / trophées / boutique
   ----------------------------- */
function initProfilPage() {
  const avatar = qs('#profileAvatar');
  const name = qs('#profileName');
  const region = qs('#profileRegion');
  const memberSince = qs('#profileMemberSince');
  const trophyGrid = qs('#trophyGrid');
  const shopButton = qs('#shopButton');
  const trophyModal = qs('#trophyModal');
  const shopModal = qs('#shopModal');
  const modalTitle = qs('#modalTitle');
  const modalCondition = qs('#modalCondition');
  const closeModalButton = qs('#closeModalButton');
  const closeShopButton = qs('#closeShopButton');
  const shopList = qs('#shopList');

  const p = state.profile;
  if (avatar) avatar.textContent = initialsFromName(p.name);
  if (name) name.textContent = p.name;
  if (region) region.textContent = `Région : ${p.region}`;
  if (memberSince) memberSince.textContent = `Inscription : ${p.memberSince}`;
  const goldSeeds = qs('#goldSeeds');
  if (goldSeeds) goldSeeds.textContent = `🌟 ${formatNumber(p.stars)}`;

  if (trophyGrid) {
    trophyGrid.innerHTML = TROPHIES.map((trophy) => `
      <button type="button" class="trophy-card ${trophy.unlocked ? 'is-unlocked' : 'is-locked'}" data-trophy="${trophy.id}">
        <span class="trophy-card__emoji">${trophy.unlocked ? trophy.emoji : '◻️'}</span>
        <span class="trophy-card__name">${trophy.name}</span>
      </button>
    `).join('');

    qsa('.trophy-card', trophyGrid).forEach((btn) => {
      btn.addEventListener('click', () => {
        const trophy = TROPHIES.find((item) => item.id === btn.dataset.trophy);
        if (!trophy || !trophyModal || !modalTitle || !modalCondition) return;
        modalTitle.textContent = `${trophy.emoji} ${trophy.name}`;
        modalCondition.textContent = trophy.condition;
        trophyModal.hidden = false;
      });
    });
  }

  if (shopButton && shopModal && shopList) {
    shopButton.addEventListener('click', () => {
      shopList.innerHTML = SHOP_REWARDS.map((reward) => `
        <article class="shop-item">
          <div>
            <strong>${reward.name}</strong>
            <p>${reward.desc}</p>
          </div>
          <span>${reward.cost} 🌟</span>
        </article>
      `).join('');
      shopModal.hidden = false;
    });
  }

  if (closeModalButton && trophyModal) {
    closeModalButton.addEventListener('click', () => (trophyModal.hidden = true));
    trophyModal.addEventListener('click', (event) => {
      if (event.target === trophyModal) trophyModal.hidden = true;
    });
  }

  if (closeShopButton && shopModal) {
    closeShopButton.addEventListener('click', () => (shopModal.hidden = true));
    shopModal.addEventListener('click', (event) => {
      if (event.target === shopModal) shopModal.hidden = true;
    });
  }
}

function initialsFromName(name) {
  return name
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() || '')
    .join('');
}

/* -----------------------------
   Classement
   ----------------------------- */
function initClassementPage() {
  const tabs = qsa('[data-board]');
  const podium = qs('#podium');
  const rankingList = qs('#rankingList');
  const countdown = qs('#seasonCountdown');
  const leagueStatus = qs('#leagueStatus');
  const improveButton = qs('.primary-action--link');
  if (!podium || !rankingList || !tabs.length) return;

  const boards = {
    commune: buildBoard('Commune', 12),
    departement: buildBoard('Département', 25),
    national: buildBoard('National', 50)
  };

  let activeBoard = 'commune';

  const renderCountdown = () => {
    const now = new Date();
    const end = new Date();
    end.setMonth(end.getMonth() + 1);
    end.setDate(1);
    end.setHours(0, 0, 0, 0);
    const diff = Math.max(0, end - now);
    const days = Math.floor(diff / 86400000);
    const hours = String(Math.floor((diff % 86400000) / 3600000)).padStart(2, '0');
    const minutes = String(Math.floor((diff % 3600000) / 60000)).padStart(2, '0');
    const seconds = String(Math.floor((diff % 60000) / 1000)).padStart(2, '0');
    if (countdown) countdown.textContent = `${days}j ${hours}:${minutes}:${seconds}`;
  };

  const renderBoard = () => {
    const board = boards[activeBoard];
    podium.innerHTML = `
      <article class="podium-card podium-card--second">
        <span>🥈</span>
        <strong>${board[1].name}</strong>
        <p>${formatNumber(board[1].points)} pts</p>
      </article>
      <article class="podium-card podium-card--first">
        <span>🥇</span>
        <strong>${board[0].name}</strong>
        <p>${formatNumber(board[0].points)} pts</p>
      </article>
      <article class="podium-card podium-card--third">
        <span>🥉</span>
        <strong>${board[2].name}</strong>
        <p>${formatNumber(board[2].points)} pts</p>
      </article>
    `;

    rankingList.innerHTML = board.slice(3).map((row) => `
      <article class="ranking-row ${row.me ? 'is-me' : ''}">
        <strong>#${row.rank}</strong>
        <div class="ranking-row__avatar">${initialsFromName(row.name)}</div>
        <div class="ranking-row__meta">
          <strong>${row.name}</strong>
          <span>Niveau ${row.level}</span>
        </div>
        <span class="ranking-row__points">${formatNumber(row.points)} pts</span>
      </article>
    `).join('');

    const me = board.find((row) => row.me) || board[10];
    if (leagueStatus) {
      const zone = me.rank <= 3 ? 'monte' : me.rank <= 10 ? 'neutre' : 'descente';
      leagueStatus.className = `league-status league-status--${zone}`;
      leagueStatus.textContent =
        zone === 'monte'
          ? '⬆️ Tu es en zone montée'
          : zone === 'descente'
            ? '⬇️ Tu es en zone descente'
            : '➡️ Tu es en zone neutre';
    }

    if (improveButton) {
      improveButton.href = './nutricore.html';
    }
  };

  tabs.forEach((tab) => {
    tab.addEventListener('click', () => {
      tabs.forEach((item) => item.classList.toggle('is-active', item === tab));
      activeBoard = tab.dataset.board || 'commune';
      renderBoard();
    });
  });

  renderCountdown();
  setInterval(renderCountdown, 1000);
  renderBoard();
}

function buildBoard(kind, size) {
  const rows = [];
  const myName = state.profile.name;
  for (let i = 1; i <= size; i += 1) {
    rows.push({
      rank: i,
      name: i === 7 && kind === 'Commune' ? myName : `${kind} Éleveur ${i}`,
      points: 5000 - i * (kind === 'National' ? 58 : kind === 'Département' ? 42 : 35),
      level: Math.max(1, 1 + Math.floor((size - i) / 6)),
      me: i === 7 && kind === 'Commune'
    });
  }
  return rows;
}

/* -----------------------------
   FarmAcademy
   ----------------------------- */
function initFarmAcademyPage() {
  const catalog = qs('#academyCatalog');
  const lessonTitle = qs('#lessonTitle');
  const lessonContent = qs('#lessonContent');
  const lessonQuiz = qs('#lessonQuiz');
  const lessonProgress = qs('#lessonProgress');
  const prevButton = qs('#prevLessonButton');
  const nextButton = qs('#nextLessonButton');
  if (!catalog) return;

  const formations = [
    {
      id: 'volailles',
      title: 'Alimentation des volailles',
      icon: '🐔',
      level: 'Débutant',
      duration: '5 leçons',
      lessons: [
        { title: 'Base énergétique', content: 'Les volailles ont besoin d’une énergie stable et facilement digestible.', quiz: [{ q: 'Quel ingrédient apporte l’énergie ?', a: ['Maïs', 'Eau', 'Sel'], correct: 0 }] },
        { title: 'Protéines', content: 'Le soja et le poisson aident à développer la croissance.', quiz: [{ q: 'Source de protéines ?', a: ['Soja', 'Herbe', 'Sable'], correct: 0 }] }
      ]
    },
    {
      id: 'bovins',
      title: 'Santé bovine',
      icon: '🐄',
      level: 'Intermédiaire',
      duration: '4 leçons',
      lessons: [
        { title: 'Observation quotidienne', content: 'Un bovin doit être observé pour détecter tout changement de comportement.', quiz: [{ q: 'Que faut-il observer ?', a: ['Comportement', 'Téléphone', 'Chaussures'], correct: 0 }] }
      ]
    },
    {
      id: 'repro',
      title: 'Gestion reproduction',
      icon: '🩷',
      level: 'Intermédiaire',
      duration: '3 leçons',
      lessons: [
        { title: 'Cycle', content: 'Le suivi des cycles améliore la fertilité et le planning.', quiz: [{ q: 'La reproduction concerne ?', a: ['Cycles', 'Couleurs', 'Prix'], correct: 0 }] }
      ]
    },
    {
      id: 'finance',
      title: 'Finance agricole',
      icon: '💰',
      level: 'Débutant',
      duration: '3 leçons',
      lessons: [
        { title: 'Calcul des marges', content: 'La marge correspond au prix de vente moins les coûts.', quiz: [{ q: 'La marge est égale à ?', a: ['Vente - coût', 'Coût + impôt', 'Prix × 2'], correct: 0 }] }
      ]
    },
    {
      id: 'paturage',
      title: 'Pâturages durables',
      icon: '🌿',
      level: 'Avancé',
      duration: '3 leçons',
      lessons: [
        { title: 'Rotation', content: 'La rotation préserve les pâturages et réduit la pression sur le sol.', quiz: [{ q: 'La rotation sert à ?', a: ['Préserver', 'Casser', 'Vendre'], correct: 0 }] }
      ]
    }
  ];

  const academyState = loadJSON(STORAGE_KEYS.academy, { current: 0, completed: {} });
  let currentFormation = formations[0];
  let currentLessonIndex = 0;

  const renderCatalog = () => {
    catalog.innerHTML = formations.map((formation, index) => {
      const completed = academyState.completed[formation.id] || 0;
      const progress = Math.round((completed / formation.lessons.length) * 100);
      return `
        <article class="academy-card ${index === academyState.current ? 'is-active' : ''}" data-index="${index}">
          <div class="academy-card__icon">${formation.icon}</div>
          <div class="academy-card__body">
            <h3>${formation.title}</h3>
            <p>${formation.level} · ${formation.duration}</p>
            <div class="progress-track">
              <span class="progress-track__bar" style="width:${progress}%"></span>
            </div>
            <small>${completed} / ${formation.lessons.length} leçons complétées ${progress === 100 ? '· Certifié' : ''}</small>
          </div>
        </article>
      `;
    }).join('');

    qsa('.academy-card', catalog).forEach((card) => {
      card.addEventListener('click', () => {
        academyState.current = Number(card.dataset.index || 0);
        currentFormation = formations[academyState.current];
        currentLessonIndex = 0;
        saveJSON(STORAGE_KEYS.academy, academyState);
        renderCatalog();
        renderLesson();
      });
    });
  };

  const renderLesson = () => {
    const lesson = currentFormation.lessons[currentLessonIndex];
    if (!lesson) return;
    if (lessonTitle) lessonTitle.textContent = lesson.title;
    if (lessonContent) {
      lessonContent.innerHTML = `
        <p>${lesson.content}</p>
        <div class="lesson-image-placeholder">Image pédagogique</div>
      `;
    }
    if (lessonQuiz) {
      lessonQuiz.innerHTML = lesson.quiz.map((item, qIndex) => `
        <div class="quiz-card">
          <strong>${item.q}</strong>
          <div class="quiz-options">
            ${item.a.map((choice, cIndex) => `
              <button type="button" class="quiz-option" data-answer="${item.correct === cIndex ? 'true' : 'false'}" data-q="${qIndex}">${choice}</button>
            `).join('')}
          </div>
        </div>
      `).join('');

      qsa('.quiz-option', lessonQuiz).forEach((btn) => {
        btn.addEventListener('click', () => {
          const correct = btn.dataset.answer === 'true';
          if (correct) {
            addPoints(20, 'une bonne réponse');
            toast('Bonne réponse ! +20 🌟');
            academyState.completed[currentFormation.id] = Math.min(currentFormation.lessons.length, (academyState.completed[currentFormation.id] || 0) + 1);
            saveJSON(STORAGE_KEYS.academy, academyState);
          } else {
            toast('Réponse incorrecte, essayez encore.', 'warning');
          }
          renderCatalog();
          updateLessonProgress();
        });
      });
    }
    updateLessonProgress();
  };

  const updateLessonProgress = () => {
    if (lessonProgress) {
      lessonProgress.textContent = `${currentLessonIndex + 1} / ${currentFormation.lessons.length}`;
    }
  };

  if (prevButton) {
    prevButton.addEventListener('click', () => {
      currentLessonIndex = clamp(currentLessonIndex - 1, 0, currentFormation.lessons.length - 1);
      renderLesson();
    });
  }
  if (nextButton) {
    nextButton.addEventListener('click', () => {
      currentLessonIndex = clamp(currentLessonIndex + 1, 0, currentFormation.lessons.length - 1);
      renderLesson();
    });
  }

  currentFormation = formations[academyState.current] || formations[0];
  renderCatalog();
  renderLesson();
}

/* -----------------------------
   Filtres / comportements communs
   ----------------------------- */
function initCommonButtons() {
  const backButtons = qsa('.app-header__back');
  backButtons.forEach((btn) => {
    btn.addEventListener('click', (event) => {
      if (history.length > 1) return;
      event.preventDefault();
      location.href = './index.html';
    });
  });
}

function initGlobalOfflineMode() {
  const update = () => {
    if (!navigator.onLine) {
      document.body.classList.add('is-offline');
      updateAya('Mode hors ligne activé.');
    } else {
      document.body.classList.remove('is-offline');
      updateAya('Connexion rétablie.');
    }
  };

  window.addEventListener('online', update);
  window.addEventListener('offline', update);
  update();
}

function hydrateFromOfflineCache() {
  const cache = loadOfflineCache();
  if (!cache) return;
  if (cache.profile) state.profile = { ...state.profile, ...cache.profile };
  if (cache.app) {
    state.ingredients = cache.app.ingredients || state.ingredients;
    state.objective = cache.app.objective || state.objective;
    state.selectedSpecies = cache.app.selectedSpecies || state.selectedSpecies;
    state.selectedStage = cache.app.selectedStage || state.selectedStage;
    state.animalCount = cache.app.animalCount || state.animalCount;
  }
  if (cache.lastRation && !state.lastRation) state.lastRation = cache.lastRation;
}

function restoreLastRationUI() {
  if (!state.lastRation) return;
  if (qs('#resultSection')) {
    renderRationResult(state.lastRation);
  }
}

function initAutoSave() {
  window.addEventListener('beforeunload', () => {
    saveProfileState();
    saveOfflineCache({ lastRation: state.lastRation });
  });
}

/* -----------------------------
   Initialisation principale
   ----------------------------- */
function initApp() {
  loadProfileState();
  hydrateFromOfflineCache();
  initCommonButtons();
  initGlobalOfflineMode();
  initNavigation();
  initSplashScreen();
  initLanguageSwitcher();
  initDailyChallenge();
  initMicrophone();
  initSpeciesAndStages();
  initIngredients();
  initSlider();
  initObjectiveButtons();
  initRationActions();
  updateLevelUI();
  renderRationHistory();
  restoreLastRationUI();
  initAutoSave();

  switch (state.page) {
    case 'modules':
      initModulesPage();
      break;
    case 'nutricore':
    case 'accueil':
      // L'accueil et NutriCore partagent la même logique de ration
      break;
    case 'vetscan':
      initVetScanPage();
      break;
    case 'reprotrack':
      initReproTrackPage();
      break;
    case 'profil':
      initProfilPage();
      break;
    case 'classement':
      initClassementPage();
      break;
    case 'farmacademy':
      initFarmAcademyPage();
      break;
    default:
      break;
  }

  if (qs('#generateButton')) {
    updateAya('Prêt à générer votre ration.');
  }
  if (qs('#diagnoseButton')) {
    updateAya('Prêt pour un diagnostic rapide.');
  }
  if (qs('#academyCatalog')) {
    updateAya('Bienvenue dans FarmAcademy.');
  }
  if (qs('#reproCalendar')) {
    updateAya('Suivi reproduction prêt.');
  }
}

/* -----------------------------
   Démarrage
   ----------------------------- */
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initApp);
} else {
  initApp();
}
