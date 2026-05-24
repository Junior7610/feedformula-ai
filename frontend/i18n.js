/* =========================================================
   FeedFormula AI — Moteur i18n global premium
   Objectif : rendre toutes les pages et contenus dynamiques
   traduisibles dans les langues supportées, avec fallback IA.
   ========================================================= */

(function () {
  "use strict";

  const STORAGE_KEY = "feedformula_language_v3";
  const LEGACY_STORAGE_KEY = "feedformula_language_v1";
  const DEFAULT_LANG = "fr";
  const AUTO_CACHE_PREFIX = "feedformula_i18n_auto_";
  const MAX_BATCH_SIZE = 80;
  const MAX_TEXT_LENGTH = 220;
  const ALIASES = {
    yo: "yor",
    yoruba: "yor",
    baa: "fon",
    bba: "fon",
    adj: "fon",
    adja: "fon",
    gen: "fon",
    gej: "fon",
    yom: "fon",
    ddn: "den",
    hau: "ha",
    ful: "ff",
    swa: "sw",
    aka: "twi",
    ibo: "ig",
    orm: "om",
    som: "so",
    zul: "zu",
    xho: "xh",
    sot: "st",
    lug: "lg",
    kin: "rw",
  };

  const cache = new Map();
  const autoTranslationCache = new Map();
  let baseDictionary = null;
  let observerReady = false;
  let debounceTimer = null;
  let autoTranslateTimer = null;
  let autoTranslateInFlight = false;
  let languageSwitcherReady = false;

  function normalizeLang(lang) {
    const clean = String(lang || DEFAULT_LANG)
      .trim()
      .toLowerCase();
    return ALIASES[clean] || clean || DEFAULT_LANG;
  }

  function getStoredLanguage() {
    try {
      return normalizeLang(
        localStorage.getItem(STORAGE_KEY) ||
          localStorage.getItem(LEGACY_STORAGE_KEY) ||
          document.documentElement.lang ||
          DEFAULT_LANG,
      );
    } catch (error) {
      return DEFAULT_LANG;
    }
  }

  function setStoredLanguage(lang) {
    const normalized = normalizeLang(lang);
    try {
      localStorage.setItem(STORAGE_KEY, normalized);
      localStorage.setItem(LEGACY_STORAGE_KEY, normalized);
    } catch (error) {
      // Stockage indisponible : l'interface reste utilisable.
    }
    return normalized;
  }

  function apiUrl(path) {
    if (!path.startsWith("/")) return path;
    return path;
  }

  function i18nUrl(lang) {
    const normalized = normalizeLang(lang);
    const prefix =
      window.location.pathname.includes("/app/") ||
      window.location.pathname.endsWith("/app")
        ? "/app"
        : "";
    return `${prefix}/i18n/${normalized}.json`;
  }

  async function fetchDictionary(lang) {
    const normalized = normalizeLang(lang);
    if (cache.has(normalized)) return cache.get(normalized);

    const candidates = [i18nUrl(normalized)];
    if (normalized !== DEFAULT_LANG) candidates.push(i18nUrl(DEFAULT_LANG));

    for (const url of candidates) {
      try {
        const response = await fetch(url, { cache: "no-cache" });
        if (!response.ok) continue;
        const payload = await response.json();
        cache.set(normalized, payload);
        return payload;
      } catch (error) {
        // On essaie le candidat suivant.
      }
    }

    const fallback = window.FEEDFORMULA_I18N_FALLBACK || {
      meta: {},
      translations: {},
    };
    cache.set(normalized, fallback);
    return fallback;
  }

  function getTranslations(dictionary) {
    return dictionary && typeof dictionary.translations === "object"
      ? dictionary.translations
      : {};
  }

  function normalizeText(value) {
    return String(value || "")
      .replace(/\s+/g, " ")
      .trim();
  }

  function shouldSkipElement(element) {
    if (!element) return true;
    return [
      "SCRIPT",
      "STYLE",
      "NOSCRIPT",
      "TEXTAREA",
      "INPUT",
      "SELECT",
      "OPTION",
      "CANVAS",
      "SVG",
      "PRE",
      "CODE",
      "KBD",
      "SAMP",
    ].includes(element.tagName);
  }

  function isTranslatableText(text) {
    const t = normalizeText(text);
    if (!t) return false;
    if (t.length > MAX_TEXT_LENGTH) return false;
    if (/^[\d\s.,:%+\-/()]+$/.test(t)) return false;
    if (/^[\p{Emoji_Presentation}\p{Extended_Pictographic}\s]+$/u.test(t)) {
      return false;
    }
    return /[A-Za-zÀ-ÿ]/.test(t);
  }

  function rememberOriginal(element, value, attr = "i18nOriginal") {
    const normalized = normalizeText(value);
    if (!normalized) return "";
    if (!element.dataset[attr]) element.dataset[attr] = normalized;
    return element.dataset[attr];
  }

  function translateExactOrPartial(source, translations) {
    if (!source) return source;
    if (translations[source]) return translations[source];

    let translated = source;
    Object.entries(translations)
      .sort((a, b) => b[0].length - a[0].length)
      .forEach(([from, to]) => {
        if (from && translated.includes(from)) {
          translated = translated.split(from).join(String(to));
        }
      });
    return translated;
  }

  function getAutoCache(lang) {
    const normalized = normalizeLang(lang);
    if (autoTranslationCache.has(normalized))
      return autoTranslationCache.get(normalized);
    let payload = {};
    try {
      payload = JSON.parse(
        localStorage.getItem(AUTO_CACHE_PREFIX + normalized) || "{}",
      );
    } catch (error) {
      payload = {};
    }
    if (!payload || typeof payload !== "object") payload = {};
    autoTranslationCache.set(normalized, payload);
    return payload;
  }

  function saveAutoCache(lang, map) {
    const normalized = normalizeLang(lang);
    try {
      localStorage.setItem(AUTO_CACHE_PREFIX + normalized, JSON.stringify(map));
    } catch (error) {
      // Le cache est un bonus : on ignore si quota dépassé.
    }
  }

  function mergedTranslations(dictionaryTranslations, lang) {
    if (normalizeLang(lang) === DEFAULT_LANG)
      return dictionaryTranslations || {};
    return {
      ...(dictionaryTranslations || {}),
      ...getAutoCache(lang),
    };
  }

  function translateTextNodes(root, translations, lang) {
    if (!root) return;
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
      acceptNode(node) {
        const parent = node.parentElement;
        if (!parent || shouldSkipElement(parent))
          return NodeFilter.FILTER_REJECT;
        if (!normalizeText(node.textContent)) return NodeFilter.FILTER_REJECT;
        return NodeFilter.FILTER_ACCEPT;
      },
    });

    const nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);

    nodes.forEach((node) => {
      const parent = node.parentElement;
      if (!parent) return;
      const current = normalizeText(node.textContent);
      const original = rememberOriginal(parent, current);
      if (!original) return;
      const next =
        normalizeLang(lang) === DEFAULT_LANG
          ? original
          : translateExactOrPartial(original, translations);
      if (next && next !== current) {
        node.textContent = node.textContent.replace(current, next);
      }
    });
  }

  function translateAttributes(root, translations, lang) {
    if (!root || !root.querySelectorAll) return;
    const attrs = [
      ["placeholder", "i18nPlaceholderOriginal"],
      ["aria-label", "i18nAriaOriginal"],
      ["title", "i18nTitleOriginal"],
      ["alt", "i18nAltOriginal"],
    ];

    attrs.forEach(([attr, dataKey]) => {
      root.querySelectorAll(`[${attr}]`).forEach((element) => {
        const current = element.getAttribute(attr) || "";
        const original = rememberOriginal(element, current, dataKey);
        if (!original) return;
        const next =
          normalizeLang(lang) === DEFAULT_LANG
            ? original
            : translateExactOrPartial(original, translations);
        if (next && next !== current) element.setAttribute(attr, next);
      });
    });

    root.querySelectorAll("option").forEach((option) => {
      const current = normalizeText(option.textContent);
      const original = rememberOriginal(option, current);
      if (!original) return;
      const next =
        normalizeLang(lang) === DEFAULT_LANG
          ? original
          : translateExactOrPartial(original, translations);
      if (next && next !== current) option.textContent = next;
    });
  }

  function markStaticI18n(root = document.body) {
    if (!root || !root.querySelectorAll) return;
    root
      .querySelectorAll(
        "h1, h2, h3, h4, p, span, strong, button, a, label, summary, small, li, th, td, div.module-name, div.module-desc, div.badge, div.tag",
      )
      .forEach((element) => {
        if (shouldSkipElement(element)) return;
        const text = normalizeText(element.textContent);
        if (!isTranslatableText(text)) return;
        if (!element.dataset.i18n) {
          element.dataset.i18n = text
            .toLowerCase()
            .replace(/[^a-z0-9À-ÿ]+/gi, ".")
            .replace(/^\.|\.$/g, "")
            .slice(0, 80);
        }
        if (!element.dataset.i18nOriginal) element.dataset.i18nOriginal = text;
      });
  }

  function collectMissingTexts(root, translations, lang) {
    const normalized = normalizeLang(lang);
    if (normalized === DEFAULT_LANG || !root || !root.querySelectorAll)
      return [];
    const known = translations || {};
    const texts = new Set();

    root.querySelectorAll("[data-i18n-original]").forEach((element) => {
      const original = normalizeText(element.dataset.i18nOriginal || "");
      if (isTranslatableText(original) && !known[original]) texts.add(original);
    });

    [
      "i18nPlaceholderOriginal",
      "i18nAriaOriginal",
      "i18nTitleOriginal",
      "i18nAltOriginal",
    ].forEach((key) => {
      root
        .querySelectorAll(
          `[data-${key.replace(/[A-Z]/g, (m) => "-" + m.toLowerCase())}]`,
        )
        .forEach((element) => {
          const original = normalizeText(element.dataset[key] || "");
          if (isTranslatableText(original) && !known[original])
            texts.add(original);
        });
    });

    return Array.from(texts).slice(0, MAX_BATCH_SIZE);
  }

  async function requestTranslations(textes, lang) {
    if (!textes.length) return [];
    try {
      const response = await fetch(apiUrl("/traduire-texte"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          textes,
          langue_cible: normalizeLang(lang),
          langue_source: DEFAULT_LANG,
        }),
      });
      if (!response.ok) return [];
      const payload = await response.json();
      return Array.isArray(payload.textes_traduits)
        ? payload.textes_traduits
        : [];
    } catch (error) {
      return [];
    }
  }

  async function autoTranslateMissing(root, lang, dictionaryTranslations) {
    const normalized = normalizeLang(lang);
    if (normalized === DEFAULT_LANG || autoTranslateInFlight) return;
    const translations = mergedTranslations(dictionaryTranslations, normalized);
    const missing = collectMissingTexts(root, translations, normalized);
    if (!missing.length) return;

    autoTranslateInFlight = true;
    const translated = await requestTranslations(missing, normalized);
    autoTranslateInFlight = false;
    if (!translated.length) return;

    const autoCache = getAutoCache(normalized);
    missing.forEach((source, index) => {
      const target = normalizeText(translated[index] || "");
      if (target && target !== source) autoCache[source] = target;
    });
    saveAutoCache(normalized, autoCache);

    const nextTranslations = mergedTranslations(
      dictionaryTranslations,
      normalized,
    );
    translateTextNodes(root, nextTranslations, normalized);
    translateAttributes(root, nextTranslations, normalized);
  }

  async function applyLanguage(
    lang = getStoredLanguage(),
    root = document.body,
  ) {
    const normalized = setStoredLanguage(lang);
    if (!baseDictionary) baseDictionary = await fetchDictionary(DEFAULT_LANG);
    const dictionary =
      normalized === DEFAULT_LANG
        ? baseDictionary
        : await fetchDictionary(normalized);
    const dictionaryTranslations = getTranslations(dictionary);
    const translations = mergedTranslations(dictionaryTranslations, normalized);

    document.documentElement.lang = normalized;
    document.body &&
      document.body.setAttribute("data-current-lang", normalized);

    markStaticI18n(root);
    translateTextNodes(root, translations, normalized);
    translateAttributes(root, translations, normalized);
    syncLanguageControls(normalized);

    if (normalized !== DEFAULT_LANG) {
      window.clearTimeout(autoTranslateTimer);
      autoTranslateTimer = window.setTimeout(
        () => autoTranslateMissing(root, normalized, dictionaryTranslations),
        180,
      );
    }

    document.dispatchEvent(
      new CustomEvent("feedformula:languagechanged", {
        detail: { lang: normalized },
      }),
    );
  }

  function syncLanguageControls(lang) {
    document
      .querySelectorAll("[data-language-select], .language-select")
      .forEach((select) => {
        if (select.value !== lang) select.value = lang;
      });
    document
      .querySelectorAll("[data-lang], [data-lang-button]")
      .forEach((button) => {
        const code = normalizeLang(
          button.dataset.lang || button.dataset.value || "",
        );
        const active = code === lang;
        button.classList.toggle("active", active);
        button.setAttribute("aria-pressed", active ? "true" : "false");
      });
  }

  async function loadSupportedLanguages() {
    try {
      const response = await fetch(apiUrl("/langues"), { cache: "no-cache" });
      if (!response.ok) throw new Error("langues indisponibles");
      const payload = await response.json();
      const langues = Array.isArray(payload.langues) ? payload.langues : [];
      return langues.map((item) => ({
        code: normalizeLang(item.code_iso || item.code || "fr"),
        label: item.nom_local || item.nom_francais || item.code_iso || "Langue",
        region: item.region_benin || item.pays_principal || "Afrique",
      }));
    } catch (error) {
      return [
        { code: "fr", label: "Français", region: "National" },
        { code: "en", label: "English", region: "Africa" },
        { code: "fon", label: "Fɔngbè", region: "Bénin" },
        { code: "yor", label: "Yorùbá", region: "Bénin/Nigeria" },
        { code: "ha", label: "Hausa", region: "West Africa" },
        { code: "sw", label: "Kiswahili", region: "East Africa" },
      ];
    }
  }

  async function injectLanguageSwitcher() {
    if (languageSwitcherReady || !document.body) return;
    languageSwitcherReady = true;
    const current = getStoredLanguage();
    const langues = await loadSupportedLanguages();

    const host = document.createElement("section");
    host.id = "ff-global-language-switcher";
    host.setAttribute("aria-label", "Sélecteur global de langue");
    host.innerHTML = `
      <style>
        #ff-global-language-switcher {
          position: fixed;
          right: 12px;
          bottom: 78px;
          z-index: 99999;
          display: flex;
          gap: 8px;
          align-items: center;
          padding: 8px;
          border-radius: 999px;
          background: rgba(255,255,255,.96);
          border: 1px solid rgba(27,94,32,.18);
          box-shadow: 0 12px 36px rgba(0,0,0,.16);
          font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        }
        #ff-global-language-switcher label { font-size: 12px; font-weight: 800; color: #1B5E20; }
        #ff-global-language-switcher select {
          max-width: 210px;
          border: 1px solid #dce8d9;
          border-radius: 999px;
          padding: 8px 10px;
          background: #fff;
          font-size: 13px;
        }
        @media (max-width: 760px) {
          #ff-global-language-switcher { left: 10px; right: 10px; bottom: 72px; justify-content: center; }
          #ff-global-language-switcher select { max-width: 72vw; }
        }
      </style>
      <label for="ffLanguageSelect">🌍 Langue</label>
      <select id="ffLanguageSelect" class="language-select" data-language-select aria-label="Choisir la langue de l'interface">
        ${langues
          .map(
            (lang) =>
              `<option value="${lang.code}" ${lang.code === current ? "selected" : ""}>${lang.label} · ${lang.region}</option>`,
          )
          .join("")}
      </select>`;
    document.body.appendChild(host);
    syncLanguageControls(current);
  }

  function bindControls() {
    document.addEventListener("change", (event) => {
      const target = event.target;
      if (
        !target ||
        !target.matches ||
        !target.matches("[data-language-select], .language-select")
      ) {
        return;
      }
      applyLanguage(target.value || DEFAULT_LANG);
    });

    document.addEventListener("click", (event) => {
      const button =
        event.target && event.target.closest
          ? event.target.closest("[data-lang], [data-lang-button]")
          : null;
      if (!button) return;
      applyLanguage(
        button.dataset.lang || button.dataset.value || DEFAULT_LANG,
      );
    });
  }

  function observeDynamicContent() {
    if (
      observerReady ||
      !document.body ||
      typeof MutationObserver === "undefined"
    )
      return;
    observerReady = true;
    const observer = new MutationObserver((mutations) => {
      if (!mutations.some((mutation) => mutation.addedNodes.length)) return;
      window.clearTimeout(debounceTimer);
      debounceTimer = window.setTimeout(
        () => applyLanguage(getStoredLanguage()),
        160,
      );
    });
    observer.observe(document.body, { childList: true, subtree: true });
  }

  function boot() {
    bindControls();
    observeDynamicContent();
    injectLanguageSwitcher().finally(() => applyLanguage(getStoredLanguage()));
  }

  window.FeedFormulaI18n = {
    applyLanguage,
    getStoredLanguage,
    normalizeLang,
    markStaticI18n,
    autoTranslateMissing,
    injectLanguageSwitcher,
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
