/* =========================================================
   FeedFormula AI — Gestionnaire d’assets et runtime frontend
   Rôle strict : chemins médias, lazy-loading, préchargement et base API.
   L’i18n est désormais isolé dans frontend/i18n.js.
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
    if (value.startsWith("/assets/")) return value;
    if (value.startsWith("../assets/") || value.startsWith("./assets/")) {
      return value;
    }
    if (value.startsWith("assets/")) {
      return `../${value}`;
    }
    return `${ASSET_ROOT}${value.replace(/^\.?\/?/, "")}`;
  }

  function ensureApiBase() {
    const host = window.location.hostname || "";
    const isLocalHost =
      host === "localhost" || host === "127.0.0.1" || host === "0.0.0.0";

    // Vercel expose aussi les endpoints FastAPI à la racine via `/(.*)`.
    // Les modules appellent donc `/generer-ration`, `/vetscan/...`, etc.
    const runtimeBase = isLocalHost ? "http://127.0.0.1:8000" : "/";

    if (!window.API_BASE || !safeString(window.API_BASE).trim()) {
      window.API_BASE = runtimeBase;
    }
    if (!window.FEEDFORMULA_API_BASE_URL) {
      window.FEEDFORMULA_API_BASE_URL = window.API_BASE;
    }
    if (!window.__FEEDFORMULA_API_BASE_URL__) {
      window.__FEEDFORMULA_API_BASE_URL__ = window.API_BASE;
    }
  }

  function applyLazyLoading(root = document) {
    const images = Array.from(root.querySelectorAll("img"));
    images.forEach((img) => {
      if (!img.getAttribute("loading")) img.setAttribute("loading", "lazy");
      if (!img.getAttribute("decoding")) img.setAttribute("decoding", "async");

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

  function observeImages() {
    if (!document.body || document.body.dataset.assetsObserverReady) return;
    if (typeof MutationObserver === "undefined") return;

    const observer = new MutationObserver((mutations) => {
      mutations.forEach((mutation) => {
        mutation.addedNodes.forEach((node) => {
          if (node.nodeType !== 1) return;
          if (node.matches && node.matches("img"))
            applyLazyLoading(node.parentNode || document);
          if (node.querySelectorAll) applyLazyLoading(node);
        });
      });
    });
    observer.observe(document.body, { childList: true, subtree: true });
    document.body.dataset.assetsObserverReady = "1";
  }

  function register(root = document) {
    ensureApiBase();
    applyLazyLoading(root);
    observeImages();

    [
      "logo_feedformula_minimal.png",
      "logo_principal.png",
      "aya_joie.png",
      "splash_screen.png",
    ].forEach((asset) => preloadAsset(asset, "image"));
  }

  window.FFAssets = {
    asset: normalizeAssetName,
    applyLazyLoading,
    preloadAsset,
    register,
    ensureApiBase,
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => register());
  } else {
    register();
  }
})();
