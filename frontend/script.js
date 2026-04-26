/* =========================================================
   FeedFormula AI — script.js (refonte UX)
   ---------------------------------------------------------
   Ce script implémente :
   1) Aya flottante + humeurs (joie / célébration / triste)
   2) Génération avec streaming perçu (SSE), texte progressif,
      spinner + typing + barre de progression
   3) Célébration post-génération (+10 🌟, pluie d’étoiles,
      animation progression niveau)
   4) Sélecteur d’espèces en cartes cliquables
   5) Microphone amélioré (enregistrement + transcription backend)
   6) Zone résultat premium (table composition + coût + performances)
   7) Mode offline avec cache local des 3 dernières rations
   ========================================================= */

/* ------------------------------
   Configuration API
   ------------------------------ */
const API_BASE_URL = "http://localhost:8000";
const API_TIMEOUT_MS = 45000;
const CACHE_KEY = "feedformula_last_rations_v1";

/* ------------------------------
   État global front
   ------------------------------ */
const appState = {
  pointsTotal: 1245,
  niveauActuel: 4,
  langueDetectee: "fr",
  derniereReponse: null,
  texteStream: "",
  mediaRecorder: null,
  chunksAudio: [],
  enregistrementEnCours: false,
  loadingProgressTimer: null,
  loadingTypingTimer: null,
};

/* ------------------------------
   Références DOM
   ------------------------------ */
const els = {
  btnGenerer: null,
  btnMic: null,
  texteDemande: null,
  espece: null,
  stade: null,

  loadingZone: null,
  loadingTyping: null,
  loadingProgressFill: null,
  loadingProgressText: null,

  resultatZone: null,
  resultContent: null,
  coutBig: null,
  coutDetails: null,
  performancesContent: null,

  btnPartagerWhatsApp: null,
  btnTelechargerPDF: null,

  xpFill: null,
  xpValue: null,
  levelBadge: null,

  challengeCountdown: null,

  celebrationLayer: null,
  ayaMascotte: null,
  ayaPointsBubble: null,

  offlineBanner: null,
  offlineCachePanel: null,
  offlineRationsList: null,

  speciesGrid: null,
};

function getEl(id) {
  return document.getElementById(id);
}

/* ------------------------------
   Helpers généraux
   ------------------------------ */
function safeText(v) {
  return String(v ?? "").trim();
}

function formatFCFA(value) {
  const n = Number(value || 0);
  return `${new Intl.NumberFormat("fr-FR").format(Math.round(n))} FCFA`;
}

function formatSeconds(value) {
  const n = Number(value || 0);
  return `${n.toFixed(2)} s`;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function nowIso() {
  return new Date().toISOString();
}

function shortDate(iso) {
  try {
    return new Date(iso).toLocaleString("fr-FR");
  } catch {
    return iso;
  }
}

/* ------------------------------
   Toast simple
   ------------------------------ */
function toast(message, type = "info") {
  let box = document.getElementById("ffToast");
  if (!box) {
    box = document.createElement("div");
    box.id = "ffToast";
    box.style.position = "fixed";
    box.style.left = "50%";
    box.style.bottom = "100px";
    box.style.transform = "translateX(-50%)";
    box.style.maxWidth = "92%";
    box.style.padding = "12px 14px";
    box.style.borderRadius = "12px";
    box.style.fontSize = "16px";
    box.style.fontWeight = "700";
    box.style.zIndex = "9999";
    box.style.opacity = "0";
    box.style.transition = "opacity 220ms ease, transform 220ms ease";
    box.style.pointerEvents = "none";
    box.style.backdropFilter = "blur(2px)";
    box.style.boxShadow = "0 10px 26px rgba(0,0,0,0.2)";
    document.body.appendChild(box);
  }

  const colors = {
    info: { bg: "#1B5E20", fg: "#FFFFFF" },
    success: { bg: "#2E7D32", fg: "#FFFFFF" },
    warning: { bg: "#F9A825", fg: "#1D1D1D" },
    error: { bg: "#B3261E", fg: "#FFFFFF" },
  };

  const c = colors[type] || colors.info;
  box.style.background = c.bg;
  box.style.color = c.fg;
  box.textContent = message;
  box.style.opacity = "1";
  box.style.transform = "translateX(-50%) translateY(0)";

  clearTimeout(box._timer);
  box._timer = setTimeout(() => {
    box.style.opacity = "0";
    box.style.transform = "translateX(-50%) translateY(10px)";
  }, 3000);
}

/* ------------------------------
   Aya (humeurs + animations)
   ------------------------------ */
const AYA_IMAGES = {
  joie: "../assets/aya_joie.png",
  celebration: "../assets/aya_celebration.png",
  triste: "../assets/aya_triste.png",
};

function setAyaMood(mood) {
  if (!els.ayaMascotte) return;
  const src = AYA_IMAGES[mood] || AYA_IMAGES.joie;
  els.ayaMascotte.src = src;
}

function showAyaPointsBubble(text = "+10 🌟") {
  if (!els.ayaPointsBubble) return;
  els.ayaPointsBubble.textContent = text;
  els.ayaPointsBubble.classList.remove("hidden", "is-show");
  // Force reflow pour relancer animation
  void els.ayaPointsBubble.offsetWidth;
  els.ayaPointsBubble.classList.add("is-show");

  setTimeout(() => {
    els.ayaPointsBubble.classList.remove("is-show");
    els.ayaPointsBubble.classList.add("hidden");
  }, 1000);
}

function celebrerGeneration(points = 10) {
  // Célébration plus sobre pour une DA professionnelle.
  setAyaMood("celebration");
  showAyaPointsBubble(`+${points} 🌟`);
  declencherPluieEtoiles(1200);

  // Retour Aya joyeuse rapidement pour limiter l'effet "fantaisie".
  setTimeout(() => {
    if (navigator.onLine) setAyaMood("joie");
  }, 1300);
}

/* ------------------------------
   Pluie d’étoiles (1.5s)
   ------------------------------ */
function declencherPluieEtoiles(durationMs = 1200) {
  if (!els.celebrationLayer) return;

  const layer = els.celebrationLayer;
  layer.innerHTML = "";
  layer.classList.add("is-active");

  // Effet volontairement réduit pour rester professionnel.
  const total = 22;
  for (let i = 0; i < total; i += 1) {
    const star = document.createElement("span");
    star.className = "star";
    star.style.left = `${Math.random() * 100}%`;
    star.style.animationDelay = `${Math.random() * 180}ms`;
    star.style.animationDuration = `${700 + Math.random() * 500}ms`;
    layer.appendChild(star);
  }

  setTimeout(() => {
    layer.classList.remove("is-active");
    layer.innerHTML = "";
  }, durationMs);
}

/* ------------------------------
   Barre de progression niveau
   ------------------------------ */
function getNiveauFromPoints(pointsTotal) {
  const levels = [
    { n: 1, seuil: 0 },
    { n: 2, seuil: 150 },
    { n: 3, seuil: 350 },
    { n: 4, seuil: 700 },
    { n: 5, seuil: 1200 },
    { n: 6, seuil: 1900 },
    { n: 7, seuil: 2800 },
    { n: 8, seuil: 4000 },
    { n: 9, seuil: 5500 },
    { n: 10, seuil: 7500 },
  ];

  let current = levels[0];
  let next = null;

  for (let i = 0; i < levels.length; i += 1) {
    if (pointsTotal >= levels[i].seuil) {
      current = levels[i];
      next = levels[i + 1] || null;
    }
  }
  return { current, next };
}

function updateXpUI(pointsToAdd = 0) {
  appState.pointsTotal += Number(pointsToAdd || 0);

  const { current, next } = getNiveauFromPoints(appState.pointsTotal);
  const oldLevel = appState.niveauActuel;
  appState.niveauActuel = current.n;

  const base = current.seuil;
  const top = next ? next.seuil : base + 1000;
  const pct = Math.max(
    0,
    Math.min(
      100,
      ((appState.pointsTotal - base) / Math.max(1, top - base)) * 100,
    ),
  );

  if (els.xpFill) {
    els.xpFill.style.width = `${pct.toFixed(1)}%`;
  }
  if (els.xpValue) {
    els.xpValue.textContent = `${Math.round(pct)}%`;
  }
  if (els.levelBadge) {
    els.levelBadge.textContent = `Niveau ${appState.niveauActuel}`;
  }

  if (appState.niveauActuel > oldLevel) {
    toast(`🎉 Niveau ${appState.niveauActuel} atteint !`, "success");
    declencherPluieEtoiles(1500);
  }
}

/* ------------------------------
   Mode offline + cache local
   ------------------------------ */
function readCacheRations() {
  try {
    const raw = localStorage.getItem(CACHE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function saveCacheRation(item) {
  const current = readCacheRations();
  const updated = [item, ...current].slice(0, 3);
  localStorage.setItem(CACHE_KEY, JSON.stringify(updated));
}

function renderOfflineCache() {
  if (!els.offlineRationsList) return;
  const items = readCacheRations();

  if (!items.length) {
    els.offlineRationsList.innerHTML = `<li class="muted">Aucune ration en cache pour le moment.</li>`;
    return;
  }

  els.offlineRationsList.innerHTML = items
    .map((it, idx) => {
      const resume = escapeHtml((it.ration || "").slice(0, 180));
      return `
        <li>
          <strong>${escapeHtml(it.espece || "Espèce")}</strong> — ${escapeHtml(it.stade || "Stade")}
          <br />
          <small class="muted">${escapeHtml(shortDate(it.date || nowIso()))}</small>
          <p style="margin:6px 0 0;">${resume}${(it.ration || "").length > 180 ? "..." : ""}</p>
          <button type="button" class="btn-cache-open" data-cache-index="${idx}"
            style="margin-top:6px;min-height:48px;padding:0 10px;border-radius:999px;background:#1B5E20;color:#fff;font-weight:700;">
            Ouvrir cette ration
          </button>
        </li>
      `;
    })
    .join("");
}

function afficherEtatOffline() {
  if (els.offlineBanner) {
    els.offlineBanner.hidden = false;
    els.offlineBanner.textContent =
      "FeedFormula AI est hors ligne. Vos 3 dernières rations sont disponibles.";
  }
  if (els.offlineCachePanel) {
    els.offlineCachePanel.classList.remove("hidden");
  }
  document.body.classList.add("offline");
  setAyaMood("triste");
  renderOfflineCache();
}

function masquerEtatOffline() {
  if (els.offlineBanner) {
    els.offlineBanner.hidden = true;
  }
  if (els.offlineCachePanel) {
    els.offlineCachePanel.classList.add("hidden");
  }
  document.body.classList.remove("offline");
  setAyaMood("joie");
}

/* ------------------------------
   Détection ingrédients / langue
   ------------------------------ */
function extraireNombreAnimaux(texte) {
  const t = safeText(texte).toLowerCase();
  const m = t.match(/\b(\d{1,6})\b/);
  if (!m) return 1;
  const n = Number(m[1]);
  return Number.isFinite(n) && n > 0 ? n : 1;
}

function extraireIngredients(texte) {
  const t = safeText(texte).toLowerCase();
  const detected = [];

  const map = [
    { re: /\bma[iï]s\b|\bagbado\b/g, v: "maïs" },
    {
      re: /\bsoja\b|\bsoybean\b|\btourteau\s+de\s+soja\b/g,
      v: "tourteau_soja",
    },
    {
      re: /\bfarine\s+de\s+poisson\b|\bfish\s+meal\b|\bj[ɔo]kp[ɔo]\b/g,
      v: "farine_poisson",
    },
    { re: /\bson\s+de\s+bl[eé]\b/g, v: "son_ble" },
    { re: /\bson\s+de\s+riz\b/g, v: "son_riz" },
    { re: /\bmanioc\b|\bcossette(s)?\b/g, v: "manioc" },
    { re: /\btourteau\s+de\s+coton\b/g, v: "tourteau_coton" },
    {
      re: /\btourteau\s+d['’]arachide\b|\barachide\b/g,
      v: "tourteau_arachide",
    },
    { re: /\bcoquille(s)?\s+d['’]hu[iî]tre\b/g, v: "coquille_huitre" },
  ];

  map.forEach((x) => {
    if (x.re.test(t)) detected.push(x.v);
  });

  return [...new Set(detected)];
}

function detecterLangueLocaleSimple(texte) {
  const t = safeText(texte).toLowerCase();
  if (!t) return "fr";
  if (/[ɖɔɛ]/.test(t) || /\bnɔ\b|\bkpo\b/.test(t)) return "fon";
  if (/[ẹọṣ]/.test(t) || /\bmo\b|\bni\b|\bati\b/.test(t)) return "yor";
  if (/\bi have\b|\bfeed\b|\bbroiler\b/.test(t)) return "en";
  return "fr";
}

/* ------------------------------
   Sélecteur espèces (cartes)
   ------------------------------ */
function initSpeciesCards() {
  if (!els.speciesGrid || !els.espece) return;

  const cards = els.speciesGrid.querySelectorAll(".species-card");
  cards.forEach((card) => {
    card.addEventListener("click", () => {
      const value = safeText(card.dataset.espece);
      if (!value) return;

      cards.forEach((c) => c.classList.remove("is-active"));
      card.classList.add("is-active");
      els.espece.value = value;
    });
  });

  // Sélection par défaut si vide.
  if (!els.espece.value && cards.length) {
    cards[0].click();
  }
}

/* ------------------------------
   Timer défi quotidien
   ------------------------------ */
function initCountdown() {
  if (!els.challengeCountdown) return;
  let seconds = 24 * 60 * 60 - 1;

  const format = (s) => {
    const h = String(Math.floor(s / 3600)).padStart(2, "0");
    const m = String(Math.floor((s % 3600) / 60)).padStart(2, "0");
    const sec = String(s % 60).padStart(2, "0");
    return `${h}:${m}:${sec}`;
  };

  els.challengeCountdown.textContent = format(seconds);

  setInterval(() => {
    seconds = seconds <= 0 ? 24 * 60 * 60 - 1 : seconds - 1;
    els.challengeCountdown.textContent = format(seconds);
  }, 1000);
}

/* ------------------------------
   Loading overlay amélioré
   ------------------------------ */
function ensureLoadingPreviewBox() {
  let box = document.getElementById("loadingStreamPreview");
  if (box) return box;

  const parent = els.loadingZone?.querySelector(".loading-overlay-inner");
  if (!parent) return null;

  box = document.createElement("div");
  box.id = "loadingStreamPreview";
  box.style.marginTop = "10px";
  box.style.padding = "10px";
  box.style.border = "1px solid #e3ece5";
  box.style.borderRadius = "10px";
  box.style.background = "#f8fff9";
  box.style.maxHeight = "140px";
  box.style.overflow = "auto";
  box.style.fontSize = "14px";
  box.style.textAlign = "left";
  box.style.whiteSpace = "pre-wrap";
  box.style.color = "#1B5E20";

  parent.appendChild(box);
  return box;
}

function startLoadingAnimation() {
  if (!els.loadingZone) return;
  els.loadingZone.hidden = false;

  // Typing animé lettre par lettre.
  const phrase = "Aya cherche la meilleure ration...";
  let i = 0;
  if (els.loadingTyping) els.loadingTyping.textContent = "";

  clearInterval(appState.loadingTypingTimer);
  appState.loadingTypingTimer = setInterval(() => {
    if (!els.loadingTyping) return;
    i += 1;
    els.loadingTyping.textContent = phrase.slice(0, i);
    if (i >= phrase.length) i = 0;
  }, 80);

  // Progression automatique perçue (0 -> 92%).
  let p = 0;
  if (els.loadingProgressFill) els.loadingProgressFill.style.width = "0%";
  if (els.loadingProgressText) els.loadingProgressText.textContent = "0%";

  clearInterval(appState.loadingProgressTimer);
  appState.loadingProgressTimer = setInterval(() => {
    if (p < 92) {
      p += Math.random() * 4.5;
    } else {
      p += Math.random() * 0.3;
    }
    p = Math.min(95, p);

    if (els.loadingProgressFill) {
      els.loadingProgressFill.style.width = `${p.toFixed(1)}%`;
    }
    if (els.loadingProgressText) {
      els.loadingProgressText.textContent = `${Math.round(p)}%`;
    }
  }, 220);

  // Prépare la preview de streaming.
  appState.texteStream = "";
  const preview = ensureLoadingPreviewBox();
  if (preview) preview.textContent = "";
}

function stopLoadingAnimation(forceDone = true) {
  clearInterval(appState.loadingTypingTimer);
  clearInterval(appState.loadingProgressTimer);

  if (forceDone) {
    if (els.loadingProgressFill) els.loadingProgressFill.style.width = "100%";
    if (els.loadingProgressText) els.loadingProgressText.textContent = "100%";
  }

  setTimeout(() => {
    if (els.loadingZone) els.loadingZone.hidden = true;
    const preview = document.getElementById("loadingStreamPreview");
    if (preview) preview.textContent = "";
  }, 240);
}

/* ------------------------------
   Réseau: timeout fetch
   ------------------------------ */
async function fetchAvecTimeout(url, options = {}, timeoutMs = API_TIMEOUT_MS) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...options, signal: controller.signal });
  } finally {
    clearTimeout(timer);
  }
}

/* ------------------------------
   Parsing SSE (POST streaming)
   ------------------------------ */
function parseSSEBlocks(buffer) {
  const chunks = buffer.split("\n\n");
  const complete = chunks.slice(0, -1);
  const remain = chunks[chunks.length - 1];

  const events = complete
    .map((block) =>
      block
        .split("\n")
        .filter((line) => line.startsWith("data:"))
        .map((line) => line.replace(/^data:\s?/, ""))
        .join("\n"),
    )
    .filter(Boolean);

  return { events, remain };
}

async function lireFluxRation(response, onChunk) {
  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";
  let finalPayload = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });

    const { events, remain } = parseSSEBlocks(buffer);
    buffer = remain;

    for (const raw of events) {
      let payload;
      try {
        payload = JSON.parse(raw);
      } catch {
        continue;
      }

      if (payload.type === "chunk") {
        const txt = String(payload.text || "");
        onChunk(txt);
      } else if (payload.type === "final") {
        finalPayload = payload.data || null;
      } else if (payload.type === "error") {
        throw new Error(payload.detail || "Erreur streaming inconnue");
      }
    }
  }

  return finalPayload;
}

/* ------------------------------
   Affichage résultat premium
   ------------------------------ */
function renderCompositionTable(composition) {
  const rows = Object.entries(composition || {})
    .map(([ingredient, kg]) => {
      const qte = Number(kg || 0);
      return `
        <tr>
          <td>${escapeHtml(ingredient)}</td>
          <td>${qte.toFixed(2)} kg</td>
          <td>${qte.toFixed(2)}%</td>
        </tr>
      `;
    })
    .join("");

  return `
    <table class="composition-table">
      <thead>
        <tr>
          <th>Ingrédient</th>
          <th>Quantité</th>
          <th>%</th>
        </tr>
      </thead>
      <tbody>
        ${rows || `<tr><td colspan="3" class="muted">Composition indisponible</td></tr>`}
      </tbody>
    </table>
  `;
}

function extractSection(text, title) {
  const t = String(text || "");
  if (!t) return "";

  const rx = new RegExp(
    `${title}[\\s\\S]*?\\n([^]*?)(?:\\n━━━━━━━━|\\n💡|\\n⚠️|$)`,
    "i",
  );
  const m = t.match(rx);
  return m ? m[1].trim() : "";
}

function afficherResultat(data, streamedText = "") {
  if (!els.resultatZone || !els.resultContent) return;

  const composition = data?.composition || {};
  const rationTexte = safeText(data?.ration || streamedText);

  // Composition = tableau clair.
  els.resultContent.innerHTML = renderCompositionTable(composition);

  // Coût mis en avant.
  if (els.coutBig) {
    els.coutBig.textContent = formatFCFA(data?.cout_fcfa_kg || 0);
  }
  if (els.coutDetails) {
    els.coutDetails.textContent = `7 jours: ${formatFCFA(data?.cout_7_jours || 0)} • Temps: ${formatSeconds(data?.temps_generation_secondes || 0)}`;
  }

  // Performance + points d’attention + conseils.
  const perf = extractSection(rationTexte, "📈 PERFORMANCES ATTENDUES");
  const attention = extractSection(rationTexte, "⚠️ POINTS D'ATTENTION");
  const conseils = extractSection(rationTexte, "💡 CONSEILS PRATIQUES");

  const perfHtml = `
    <p><strong>Performance:</strong> ${escapeHtml(perf || "Voir recommandations générées par Aya.")}</p>
    <p><strong>Points d'attention:</strong> ${escapeHtml(attention || "Surveiller la transition alimentaire et l’équilibre minéral.")}</p>
    <p><strong>Conseils:</strong><br>${escapeHtml(conseils || "Hydratation continue, contrôle des stocks, suivi consommation.")}</p>
  `;
  if (els.performancesContent) {
    els.performancesContent.innerHTML = perfHtml.replace(/\n/g, "<br>");
  }

  els.resultatZone.classList.remove("hidden");
}

function masquerResultat() {
  if (!els.resultatZone) return;
  els.resultatZone.classList.add("hidden");
}

/* ------------------------------
   Cache ration (3 dernières)
   ------------------------------ */
function cacheCurrentRation(data, especeLabel, stadeLabel) {
  const item = {
    date: nowIso(),
    espece: especeLabel,
    stade: stadeLabel,
    ration: safeText(data?.ration || ""),
    composition: data?.composition || {},
    cout_fcfa_kg: Number(data?.cout_fcfa_kg || 0),
    cout_7_jours: Number(data?.cout_7_jours || 0),
    langue: safeText(data?.langue_detectee || "fr"),
  };
  saveCacheRation(item);
}

function bindOfflineCacheActions() {
  if (!els.offlineRationsList) return;

  els.offlineRationsList.addEventListener("click", (event) => {
    const btn = event.target.closest(".btn-cache-open");
    if (!btn) return;

    const idx = Number(btn.dataset.cacheIndex);
    const items = readCacheRations();
    const item = items[idx];
    if (!item) return;

    const data = {
      ration: item.ration,
      composition: item.composition,
      cout_fcfa_kg: item.cout_fcfa_kg,
      cout_7_jours: item.cout_7_jours,
      langue_detectee: item.langue,
      points_gagnes: 0,
      temps_generation_secondes: 0,
    };

    afficherResultat(data, item.ration);
    toast("Ration hors ligne ouverte.", "info");
  });
}

/* ------------------------------
   Génération ration (streaming)
   ------------------------------ */
async function genererRation() {
  const texteDemande = safeText(els.texteDemande?.value);
  const espece = safeText(els.espece?.value);
  const stade = safeText(els.stade?.value);

  if (!espece || !stade) {
    toast("Choisis l'espèce et le stade avant de générer.", "warning");
    return;
  }

  const ingredients = extraireIngredients(texteDemande);
  if (ingredients.length < 2) {
    toast(
      "Indique au moins 2 ingrédients dans ton texte (ex: maïs, soja).",
      "warning",
    );
    return;
  }

  if (!navigator.onLine) {
    afficherEtatOffline();
    toast(
      "FeedFormula AI est hors ligne. Affichage du cache local.",
      "warning",
    );
    return;
  }

  // Passage Aya joyeuse avant génération.
  setAyaMood("joie");

  const payload = {
    espece,
    stade,
    ingredients_disponibles: ingredients,
    nombre_animaux: extraireNombreAnimaux(texteDemande),
    langue: detecterLangueLocaleSimple(texteDemande),
    objectif: "equilibre",
    stream: true,
  };

  try {
    if (els.btnGenerer) els.btnGenerer.disabled = true;
    startLoadingAnimation();
    masquerResultat();

    const response = await fetchAvecTimeout(`${API_BASE_URL}/generer-ration`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      let detail = `Erreur serveur (${response.status})`;
      try {
        const errJson = await response.json();
        detail = errJson?.detail || detail;
      } catch {
        // ignore
      }
      throw new Error(detail);
    }

    const contentType = safeText(
      response.headers.get("content-type"),
    ).toLowerCase();
    let finalData = null;

    // Conteneur de preview stream
    const preview = ensureLoadingPreviewBox();
    appState.texteStream = "";

    if (contentType.includes("text/event-stream")) {
      finalData = await lireFluxRation(response, (txt) => {
        appState.texteStream += txt;
        if (preview) preview.textContent = appState.texteStream;
      });
    } else {
      // Fallback JSON classique.
      finalData = await response.json();
      appState.texteStream = safeText(finalData?.ration || "");
      if (preview) preview.textContent = appState.texteStream;
    }

    if (!finalData || !safeText(finalData.ration)) {
      throw new Error("Réponse finale vide reçue du backend.");
    }

    appState.derniereReponse = finalData;
    appState.langueDetectee = safeText(finalData.langue_detectee || "fr");

    afficherResultat(finalData, appState.texteStream);

    // Stockage cache local (3 dernières rations).
    const especeLabel =
      document.querySelector(
        `.species-card[data-espece="${espece}"] .species-name`,
      )?.textContent || espece;
    const stadeLabel = stade;
    cacheCurrentRation(finalData, especeLabel, stadeLabel);

    // Actions résultat
    if (els.btnPartagerWhatsApp) {
      els.btnPartagerWhatsApp.onclick = () =>
        partagerWhatsApp(finalData.ration);
    }
    if (els.btnTelechargerPDF) {
      els.btnTelechargerPDF.onclick = () => telechargerPDF(finalData.ration);
    }

    // Gamification + célébration discrète.
    const points = Number(finalData.points_gagnes || 10);
    updateXpUI(points);
    celebrerGeneration(points);

    toast("Ration générée avec succès ✅", "success");
    toast(
      `Ration générée ✅ (${formatSeconds(finalData?.temps_generation_secondes || 0)})`,
      "success",
    );
  } catch (error) {
    // En cas d'erreur backend, on bascule en état offline assisté.
    afficherEtatOffline();

    if (error?.name === "AbortError") {
      toast("Délai dépassé: le serveur est lent. Essaie encore.", "error");
    } else {
      const cacheCount = readCacheRations().length;
      toast(
        `Impossible de générer la ration: ${error?.message || "Erreur inconnue"}${
          cacheCount ? ` • ${cacheCount} ration(s) en cache disponible(s)` : ""
        }`,
        "error",
      );
    }
  } finally {
    stopLoadingAnimation(true);
    if (els.btnGenerer) els.btnGenerer.disabled = false;
  }
}

/* ------------------------------
   Microphone + transcription
   ------------------------------ */
async function enregistrerVoix() {
  // Toggle stop si déjà en écoute.
  if (appState.enregistrementEnCours && appState.mediaRecorder) {
    appState.mediaRecorder.stop();
    return;
  }

  if (!navigator.mediaDevices?.getUserMedia) {
    toast("Microphone non supporté sur ce navigateur.", "error");
    return;
  }

  if (!navigator.onLine) {
    toast("Mode hors ligne: transcription indisponible.", "warning");
    return;
  }

  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

    appState.chunksAudio = [];
    appState.mediaRecorder = new MediaRecorder(stream, {
      mimeType: "audio/webm",
    });

    appState.mediaRecorder.onstart = () => {
      appState.enregistrementEnCours = true;
      els.btnMic?.classList.add("is-listening");
      toast("Écoute en cours... Appuie à nouveau pour arrêter.", "info");
    };

    appState.mediaRecorder.ondataavailable = (event) => {
      if (event.data && event.data.size > 0)
        appState.chunksAudio.push(event.data);
    };

    appState.mediaRecorder.onstop = async () => {
      appState.enregistrementEnCours = false;
      els.btnMic?.classList.remove("is-listening");
      stream.getTracks().forEach((track) => track.stop());

      if (!appState.chunksAudio.length) {
        toast("Aucun audio capturé.", "warning");
        return;
      }

      try {
        startLoadingAnimation();

        const blob = new Blob(appState.chunksAudio, { type: "audio/webm" });
        const formData = new FormData();
        formData.append("audio", blob, "voix_eleveur.webm");
        formData.append("langue", "auto");

        const response = await fetchAvecTimeout(
          `${API_BASE_URL}/transcrire-audio`,
          {
            method: "POST",
            body: formData,
          },
        );

        if (!response.ok) {
          let detail = `Erreur transcription (${response.status})`;
          try {
            const errJson = await response.json();
            detail = errJson?.detail || detail;
          } catch {
            // ignore
          }
          throw new Error(detail);
        }

        const data = await response.json();
        const texte = safeText(data?.texte);
        const langue = safeText(
          data?.langue_detectee || detecterLangueLocaleSimple(texte),
        );

        if (els.texteDemande) els.texteDemande.value = texte;
        appState.langueDetectee = langue;

        // Badge langue détectée dynamique.
        let badge = document.getElementById("langueDetecteeBadge");
        if (!badge && els.texteDemande?.parentElement) {
          badge = document.createElement("p");
          badge.id = "langueDetecteeBadge";
          badge.style.margin = "6px 0 0";
          badge.style.fontWeight = "700";
          badge.style.color = "#1B5E20";
          els.texteDemande.parentElement.appendChild(badge);
        }
        if (badge) badge.textContent = `Langue détectée: ${langue}`;

        toast("Transcription réussie ✅", "success");
      } catch (e) {
        toast(
          `Transcription impossible: ${e?.message || "Erreur inconnue"}`,
          "error",
        );
      } finally {
        stopLoadingAnimation(true);
      }
    };

    appState.mediaRecorder.start();
  } catch {
    toast("Autorisation micro refusée ou indisponible.", "error");
  }
}

/* ------------------------------
   WhatsApp + PDF
   ------------------------------ */
function partagerWhatsApp(ration) {
  const txt = safeText(ration || appState.derniereReponse?.ration || "");
  if (!txt) {
    toast("Aucune ration à partager.", "warning");
    return;
  }

  const message = `🌾 FeedFormula AI — Ma ration\n\n${txt.slice(0, 1200)}${txt.length > 1200 ? "..." : ""}`;
  const url = `https://wa.me/?text=${encodeURIComponent(message)}`;
  window.open(url, "_blank", "noopener,noreferrer");
}

function telechargerPDF(ration) {
  const txt = safeText(ration || appState.derniereReponse?.ration || "");
  if (!txt) {
    toast("Aucune ration à exporter.", "warning");
    return;
  }

  if (!window.jspdf?.jsPDF) {
    toast("jsPDF non chargé.", "error");
    return;
  }

  try {
    const { jsPDF } = window.jspdf;
    const doc = new jsPDF();

    doc.setFont("helvetica", "bold");
    doc.setFontSize(14);
    doc.text("FeedFormula AI — Ration générée", 14, 18);

    doc.setFont("helvetica", "normal");
    doc.setFontSize(11);
    doc.text(`Date: ${new Date().toLocaleString("fr-FR")}`, 14, 26);

    const lines = doc.splitTextToSize(txt, 180);
    doc.text(lines, 14, 36);

    doc.save("ration_feedformula_ai.pdf");
    toast("PDF téléchargé ✅", "success");
  } catch (e) {
    toast(`Erreur PDF: ${e?.message || "inconnue"}`, "error");
  }
}

/* ------------------------------
   Réseau online/offline
   ------------------------------ */
function handleOnlineState() {
  if (navigator.onLine) {
    masquerEtatOffline();
    toast("Connexion rétablie.", "success");
  } else {
    afficherEtatOffline();
    toast("Mode hors ligne activé.", "warning");
  }
}

/* ------------------------------
   Bind events
   ------------------------------ */
function bindEvents() {
  els.btnGenerer?.addEventListener("click", genererRation);
  els.btnMic?.addEventListener("click", enregistrerVoix);

  els.btnPartagerWhatsApp?.addEventListener("click", () => {
    partagerWhatsApp(appState.derniereReponse?.ration || "");
  });
  els.btnTelechargerPDF?.addEventListener("click", () => {
    telechargerPDF(appState.derniereReponse?.ration || "");
  });

  window.addEventListener("online", handleOnlineState);
  window.addEventListener("offline", handleOnlineState);

  bindOfflineCacheActions();
}

/* ------------------------------
   Init refs
   ------------------------------ */
function initRefs() {
  els.btnGenerer = getEl("btnGenerer");
  els.btnMic = getEl("btnMic");
  els.texteDemande = getEl("texteDemande");
  els.espece = getEl("espece");
  els.stade = getEl("stade");

  els.loadingZone = getEl("loadingZone");
  els.loadingTyping = getEl("loadingTyping");
  els.loadingProgressFill = getEl("loadingProgressFill");
  els.loadingProgressText = getEl("loadingProgressText");

  els.resultatZone = getEl("resultatZone");
  els.resultContent = getEl("resultContent");
  els.coutBig = getEl("coutBig");
  els.coutDetails = getEl("coutDetails");
  els.performancesContent = getEl("performancesContent");

  els.btnPartagerWhatsApp = getEl("btnPartagerWhatsApp");
  els.btnTelechargerPDF = getEl("btnTelechargerPDF");

  els.xpFill = getEl("xpFill");
  els.xpValue = getEl("xpValue");
  els.levelBadge = document.querySelector(".level-badge");

  els.challengeCountdown = getEl("countdown");

  els.celebrationLayer = getEl("celebrationLayer");
  els.ayaMascotte = getEl("ayaMascotte");
  els.ayaPointsBubble = getEl("ayaPointsBubble");

  els.offlineBanner = getEl("offlineBanner");
  els.offlineCachePanel = getEl("offlineCachePanel");
  els.offlineRationsList = getEl("offlineRationsList");

  els.speciesGrid = getEl("speciesGrid");
}

/* ------------------------------
   Bootstrap
   ------------------------------ */
function bootstrap() {
  initRefs();
  initSpeciesCards();
  initCountdown();
  bindEvents();

  // État initial UI
  if (navigator.onLine) {
    masquerEtatOffline();
  } else {
    afficherEtatOffline();
  }

  // Init progression actuelle
  updateXpUI(0);

  // Expose quelques fonctions pour debug manuel
  window.genererRation = genererRation;
  window.enregistrerVoix = enregistrerVoix;
  window.partagerWhatsApp = partagerWhatsApp;
  window.telechargerPDF = telechargerPDF;
}

document.addEventListener("DOMContentLoaded", bootstrap);
