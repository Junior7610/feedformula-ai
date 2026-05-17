/* =========================================================
   FeedFormula AI — Moteur i18n global
   Objectif : traduire toutes les pages avec des dictionnaires JSON,
   en conservant un fallback automatique pour les anciens textes en dur.
   ========================================================= */

(function () {
  "use strict";

  const STORAGE_KEY = "feedformula_language_v3";
  const DEFAULT_LANG = "fr";
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
  };

  const cache = new Map();
  let baseDictionary = null;
  let observerReady = false;
  let debounceTimer = null;

  function normalizeLang(lang) {
    const clean = String(lang || DEFAULT_LANG).trim().toLowerCase();
    return ALIASES[clean] || clean || DEFAULT_LANG;
  }

  function getStoredLanguage() {
    try {
      return normalizeLang(localStorage.getItem(STORAGE_KEY) || document.documentElement.lang || DEFAULT_LANG);
    } catch (error) {
      return DEFAULT_LANG;
    }
  }

  function setStoredLanguage(lang) {
    const normalized = normalizeLang(lang);
    try {
      localStorage.setItem(STORAGE_KEY, normalized);
      localStorage.setItem("feedformula_language_v1", normalized);
    } catch (error) {
      // Stockage indisponible : l'interface reste utilisable.
    }
    return normalized;
  }

  function i18nUrl(lang) {
    const normalized = normalizeLang(lang);
    const prefix = window.location.pathname.includes("/app/") || window.location.pathname.endsWith("/app") ? "/app" : "";
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

    const fallback = window.FEEDFORMULA_I18N_FALLBACK || { meta: {}, translations: {} };
    cache.set(normalized, fallback);
    return fallback;
  }

  function getTranslations(dictionary) {
    return dictionary && typeof dictionary.translations === "object" ? dictionary.translations : {};
  }

  function normalizeText(value) {
    return String(value || "").replace(/\s+/g, " ").trim();
  }

  function shouldSkipElement(element) {
    if (!element) return true;
    return ["SCRIPT", "STYLE", "NOSCRIPT", "TEXTAREA", "INPUT", "SELECT", "OPTION", "CANVAS", "SVG"].includes(element.tagName);
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

  function translateTextNodes(root, translations, lang) {
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
      acceptNode(node) {
        const parent = node.parentElement;
        if (!parent || shouldSkipElement(parent)) return NodeFilter.FILTER_REJECT;
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
      const next = lang === DEFAULT_LANG ? original : translateExactOrPartial(original, translations);
      if (next && next !== current) node.textContent = node.textContent.replace(current, next);
    });
  }

  function translateAttributes(root, translations, lang) {
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
        const next = lang === DEFAULT_LANG ? original : translateExactOrPartial(original, translations);
        if (next && next !== current) element.setAttribute(attr, next);
      });
    });

    root.querySelectorAll("option").forEach((option) => {
      const current = normalizeText(option.textContent);
      const original = rememberOriginal(option, current);
      if (!original) return;
      const next = lang === DEFAULT_LANG ? original : translateExactOrPartial(original, translations);
      if (next && next !== current) option.textContent = next;
    });
  }

  function markStaticI18n(root = document.body) {
    if (!root) return;
    root.querySelectorAll("h1, h2, h3, p, span, strong, button, a, label, summary, small, div.module-name, div.module-desc").forEach((element) => {
      if (shouldSkipElement(element)) return;
      const text = normalizeText(element.textContent);
      if (!text || text.length > 180) return;
      if (!element.dataset.i18n) {
        element.dataset.i18n = text.toLowerCase().replace(/[^a-z0-9À-ÿ]+/gi, ".").replace(/^\.|\.$/g, "").slice(0, 80);
      }
      if (!element.dataset.i18nOriginal) element.dataset.i18nOriginal = text;
    });
  }

  async function applyLanguage(lang = getStoredLanguage(), root = document.body) {
    const normalized = setStoredLanguage(lang);
    if (!baseDictionary) baseDictionary = await fetchDictionary(DEFAULT_LANG);
    const dictionary = normalized === DEFAULT_LANG ? baseDictionary : await fetchDictionary(normalized);
    const translations = getTranslations(dictionary);

    document.documentElement.lang = normalized;
    document.body && document.body.setAttribute("data-current-lang", normalized);

    markStaticI18n(root);
    translateTextNodes(root, translations, normalized);
    translateAttributes(root, translations, normalized);

    document.dispatchEvent(new CustomEvent("feedformula:languagechanged", { detail: { lang: normalized } }));
  }

  function bindControls() {
    document.addEventListener("change", (event) => {
      const target = event.target;
      if (!target || !target.matches || !target.matches("[data-language-select], .language-select")) return;
      applyLanguage(target.value || DEFAULT_LANG);
    });

    document.addEventListener("click", (event) => {
      const button = event.target && event.target.closest ? event.target.closest("[data-lang], [data-lang-button]") : null;
      if (!button) return;
      applyLanguage(button.dataset.lang || button.dataset.value || DEFAULT_LANG);
    });
  }

  function observeDynamicContent() {
    if (observerReady || !document.body || typeof MutationObserver === "undefined") return;
    observerReady = true;
    const observer = new MutationObserver((mutations) => {
      if (!mutations.some((mutation) => mutation.addedNodes.length)) return;
      window.clearTimeout(debounceTimer);
      debounceTimer = window.setTimeout(() => applyLanguage(getStoredLanguage()), 120);
    });
    observer.observe(document.body, { childList: true, subtree: true });
  }

  function boot() {
    bindControls();
    observeDynamicContent();
    applyLanguage(getStoredLanguage());
  }

  window.FeedFormulaI18n = {
    applyLanguage,
    getStoredLanguage,
    normalizeLang,
    markStaticI18n,
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
