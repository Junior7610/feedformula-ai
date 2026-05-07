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
      const explicitSrc = img.dataset.assetSrc || img.getAttribute("data-asset-src");
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
    const exists = Array.from(document.head.querySelectorAll("link[rel='preload']")).some(
      (link) => link.getAttribute("href") === resolved
    );
    if (exists) return resolved;

    const link = document.createElement("link");
    link.rel = "preload";
    link.href = resolved;
    link.as = as;
    document.head.appendChild(link);
    return resolved;
  }

  function register(root = document) {
    applyLazyLoading(root);

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
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => register());
  } else {
    register();
  }
})();
