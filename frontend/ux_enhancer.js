/* FeedFormula AI — UX enhancer global
   Mobile-first, aération, mode nuit, repères visuels et navigation rapide.
*/
(function () {
  "use strict";

  const THEME_KEY = "feedformula_theme_v2";
  const PAGE_EXPERIENCE = {
    index: {
      title: "Tout commence ici",
      image: "../assets/illustration_accueil.png",
      shortcuts: [
        ["🌾 Générer une ration", "#rationForm"],
        ["🐔 Choisir espèce", "#speciesGrid"],
        ["💳 Voir offres", "#subscriptionTitle"],
      ],
    },
    modules: {
      title: "Choisissez votre outil",
      image: "../assets/carte_modules.png",
      shortcuts: [
        ["🌿 FloraVet", "floravet.html"],
        ["🧠 FarmManager", "farmmanager.html"],
        ["🎓 FarmAcademy", "farmacademy.html"],
      ],
    },
    nutricore: {
      title: "Formulez sans stress",
      image: "../assets/hero_poulets.png",
      shortcuts: [
        ["🐔 Espèces", "#speciesGrid"],
        ["🌽 Ingrédients", "#ingredientsTitle"],
        ["📊 Résultat", "#resultatZone"],
      ],
    },
    vetscan: {
      title: "Santé animale claire",
      image: "../assets/aya_avec_animaux.png",
      shortcuts: [
        ["📷 Photo", "#photoInput"],
        ["📝 Symptômes", "#symptomsInput"],
        ["🌿 FloraVet", "floravet.html"],
      ],
    },
    reprotrack: {
      title: "Reproduction maîtrisée",
      image: "../assets/hero_bovins.png",
      shortcuts: [
        ["➕ Événement", "#events"],
        ["🐾 Profils", "#species"],
        ["📈 Performance", "#performance"],
      ],
    },
    farmacademy: {
      title: "Apprendre à élever de A à Z",
      image: "../assets/aya_celebration.png",
      shortcuts: [
        ["🐾 Espèce", "#speciesStrip"],
        ["🎓 Catalogue", "#catalogue"],
        ["✅ Plan d'action", "#planAction"],
      ],
    },
    farmcast: {
      title: "Votre studio de contenu",
      image: "../assets/demo_image_3.png",
      shortcuts: [
        ["✨ Créer", "#create"],
        ["🎬 Storyboard", "#storyboardPanel"],
        ["📱 Multicanal", "#platformPanel"],
      ],
    },
    farmcommunity: {
      title: "Entraide agricole fiable",
      image: "../assets/carte_afrique_impact.png",
      shortcuts: [
        ["🏠 Fil", "#feedPanel"],
        ["🛒 Marché", "#marketPanel"],
        ["✨ Question", "#assistantPanel"],
      ],
    },
    farmmanager: {
      title: "Votre ferme sous contrôle",
      image: "../assets/aya_avec_animaux.png",
      shortcuts: [
        ["🏠 Dashboard", "#dashboard"],
        ["🐄 Animaux", "#animals"],
        ["🎙️ Vocal", "#voiceText"],
      ],
    },
    floravet: {
      title: "Plantes utiles, risques évités",
      image: "../assets/hero_petits_ruminants.png",
      shortcuts: [
        ["📷 Analyser", "#analyse"],
        ["📚 Bibliothèque", "#library"],
        ["🚨 Toxiques", "#regional"],
      ],
    },
    pasturemap: {
      title: "Pâturages plus intelligents",
      image: "../assets/carte_afrique_animaux.png",
      shortcuts: [
        ["🛰️ Carte", "#map"],
        ["🌿 Pâturage", "#pasture"],
        ["📊 Analyse", "#analysis"],
      ],
    },
    profil: {
      title: "Votre progression",
      image: "../assets/banniere_niveaux.png",
      shortcuts: [
        ["🏆 Niveau", "#level"],
        ["👤 Profil", "#profile"],
        ["🌍 Langue", "#ffLanguageSelect"],
      ],
    },
    abonnement: {
      title: "Choisissez votre puissance",
      image: "../assets/offres_commerciales.png",
      shortcuts: [
        ["💳 Offres", "#plans"],
        ["✅ Comparatif", "#features"],
        ["📱 Paiement", "#payment"],
      ],
    },
  };

  const ICON_RULES = [
    [/dashboard|tableau|accueil|statut|résumé|resume/i, "🏠"],
    [/animal|animaux|espèce|espece|troupeau|lot/i, "🐄"],
    [/finance|coût|cout|marge|prix|revenu|dépense|depense|rentabil/i, "💰"],
    [/planning|calendrier|agenda|tâche|tache|semaine|mois/i, "📅"],
    [/stock|aliment|ingrédient|ingredient|ration|nutrition/i, "📦"],
    [
      /santé|sante|maladie|vaccin|traitement|sanitaire|vétérinaire|veterinaire/i,
      "🩺",
    ],
    [/repro|chaleur|saillie|mise-bas|gestation|ponte|éclosion|eclosion/i, "🐣"],
    [/formation|academy|leçon|lecon|quiz|certificat|apprendre/i, "🎓"],
    [/plante|floravet|botanique|toxicité|toxicite|fourrage/i, "🌿"],
    [
      /community|communauté|communaute|marché|marche|post|expert|question/i,
      "🤝",
    ],
    [/cast|audio|vidéo|video|script|contenu|storyboard|campagne/i, "🎙️"],
    [/rapport|pdf|document|historique|analyse/i, "📊"],
  ];

  function qs(selector, root = document) {
    return root.querySelector(selector);
  }

  function qsa(selector, root = document) {
    return Array.from(root.querySelectorAll(selector));
  }

  function clean(text) {
    return String(text || "")
      .replace(/\s+/g, " ")
      .trim();
  }

  function iconFor(text) {
    const value = clean(text);
    const match = ICON_RULES.find(([regex]) => regex.test(value));
    return match ? match[1] : "✨";
  }

  function currentPageKey() {
    const explicit =
      document.body && document.body.dataset
        ? document.body.dataset.i18nPage || document.body.dataset.page
        : "";
    if (explicit)
      return String(explicit)
        .replace(/\.html$/i, "")
        .toLowerCase();
    const file = (
      window.location.pathname.split("/").pop() || "index.html"
    ).replace(/\.html$/i, "");
    return file || "index";
  }

  function pageExperience() {
    return PAGE_EXPERIENCE[currentPageKey()] || null;
  }

  function getTheme() {
    try {
      const stored = localStorage.getItem(THEME_KEY);
      if (stored) return stored;
    } catch (error) {
      // ignore
    }
    return window.matchMedia &&
      window.matchMedia("(prefers-color-scheme: dark)").matches
      ? "dark"
      : "light";
  }

  function setTheme(theme) {
    const normalized = theme === "dark" ? "dark" : "light";
    document.documentElement.dataset.theme = normalized;
    document.body &&
      document.body.classList.toggle("ff-dark", normalized === "dark");
    try {
      localStorage.setItem(THEME_KEY, normalized);
    } catch (error) {
      // ignore
    }
    const btn = qs("#ffThemeToggle");
    if (btn) btn.textContent = normalized === "dark" ? "☀️ Jour" : "🌙 Nuit";
  }

  function isSimpleHome() {
    return document.body && document.body.classList.contains("simple-home");
  }

  function addHeadingIcons() {
    if (isSimpleHome()) return;
    qsa("h1, h2, h3").forEach((heading) => {
      if (heading.dataset.ffIconReady === "1") return;
      const text = clean(heading.textContent);
      if (
        !text ||
        /^[\p{Emoji_Presentation}\p{Extended_Pictographic}]/u.test(text)
      )
        return;
      const icon = iconFor(text);
      heading.dataset.ffIconReady = "1";
      heading.innerHTML = `<span class="ff-heading-icon" aria-hidden="true">${icon}</span> ${heading.innerHTML}`;
    });
  }

  function enhanceSections() {
    qsa(
      "main > section, .app > section, .wrap > section, section.card",
    ).forEach((section) => {
      if (section.dataset.ffUxSection === "1") return;
      section.dataset.ffUxSection = "1";
      section.classList.add("ff-section-shell");
      const title = qs("h1,h2,h3", section);
      if (title) {
        const type = clean(title.textContent).toLowerCase().slice(0, 80);
        section.dataset.ffSectionTitle = type;
      }
    });

    qsa(".card, article, details").forEach((card) => {
      if (card.dataset.ffUxCard === "1") return;
      card.dataset.ffUxCard = "1";
      card.classList.add("ff-ux-card");
    });
  }

  function addIllustrationSlots() {
    if (isSimpleHome()) return;
    qsa(
      ".module-card, .formation-card, .plant-card, .animal-card, .profile-card, .metric",
    ).forEach((card) => {
      if (card.dataset.ffIllustrated === "1") return;
      card.dataset.ffIllustrated = "1";
      const title = clean(
        (qs("h1,h2,h3,h4,.module-name", card) || card).textContent,
      );
      card.style.setProperty("--ff-card-emoji", `"${iconFor(title)}"`);
      card.classList.add("ff-illustrated-card");
    });
  }

  function injectPageExperienceBanner() {
    if (isSimpleHome()) return;
    if (qs("#ffPageExperience")) return;
    const config = pageExperience();
    if (!config) return;
    const anchor = qs("main, .app, .wrap, .page-shell");
    if (!anchor) return;
    const firstTitle = qs("h1");
    const subtitle = firstTitle
      ? clean(firstTitle.textContent).slice(0, 120)
      : "FeedFormula AI";
    const banner = document.createElement("section");
    banner.id = "ffPageExperience";
    banner.className = "ff-page-experience ff-section-shell";
    banner.innerHTML = `
      <div class="ff-page-experience__copy">
        <span class="ff-page-kicker">${iconFor(config.title)} Expérience simplifiée</span>
        <h2>${config.title}</h2>
        <p>${subtitle}</p>
        <div class="ff-page-shortcuts">
          ${(config.shortcuts || [])
            .map(([label, href]) => `<a href="${href}">${label}</a>`)
            .join("")}
        </div>
      </div>
      <div class="ff-page-experience__visual" aria-hidden="true">
        <img src="${config.image}" alt="" loading="lazy" />
      </div>
    `;
    if (anchor.firstElementChild) {
      anchor.insertBefore(banner, anchor.firstElementChild.nextSibling);
    } else {
      anchor.appendChild(banner);
    }
  }

  function buildQuickNav() {
    if (isSimpleHome()) return;
    if (qs("#ffQuickNav")) return;
    const headings = qsa("main h2, .app h2, .wrap h2")
      .filter((h) => clean(h.textContent).length > 2)
      .slice(0, 8);
    if (headings.length < 3) return;

    headings.forEach((h, index) => {
      if (!h.id) h.id = `section-${index + 1}`;
    });

    const nav = document.createElement("nav");
    nav.id = "ffQuickNav";
    nav.className = "ff-quick-nav";
    nav.setAttribute("aria-label", "Navigation rapide de la page");
    nav.innerHTML = headings
      .map(
        (h) =>
          `<a href="#${h.id}">${iconFor(h.textContent)} ${clean(h.textContent).slice(0, 34)}</a>`,
      )
      .join("");

    const anchor = qs("main, .app, .wrap");
    if (anchor && anchor.firstElementChild) {
      anchor.insertBefore(nav, anchor.firstElementChild.nextSibling);
    }
  }

  function injectUxDock() {
    if (isSimpleHome()) return;
    if (qs("#ffUxDock")) return;
    const dock = document.createElement("div");
    dock.id = "ffUxDock";
    dock.className = "ff-ux-dock";
    dock.innerHTML = `
      <button id="ffThemeToggle" type="button" aria-label="Basculer le mode nuit">🌙 Nuit</button>
      <button id="ffTopButton" type="button" aria-label="Retour en haut">↑ Haut</button>
    `;
    document.body.appendChild(dock);
    qs("#ffThemeToggle").addEventListener("click", () => {
      setTheme(
        document.documentElement.dataset.theme === "dark" ? "light" : "dark",
      );
    });
    qs("#ffTopButton").addEventListener("click", () =>
      window.scrollTo({ top: 0, behavior: "smooth" }),
    );
  }

  function improveForms() {
    qsa("button, .btn, input, select, textarea, a").forEach((el) => {
      el.classList.add("ff-touch-target");
    });
    qsa("input, textarea, select").forEach((el) => {
      if (!el.getAttribute("aria-label")) {
        const label = el.closest("label");
        const text = label
          ? clean(label.textContent).replace(clean(el.value), "")
          : el.placeholder;
        if (text) el.setAttribute("aria-label", text.slice(0, 80));
      }
    });
  }

  function enhanceDynamic() {
    document.body.classList.add("ff-ux-ready");
    addHeadingIcons();
    enhanceSections();
    injectPageExperienceBanner();
    addIllustrationSlots();
    buildQuickNav();
    improveForms();
  }

  function observe() {
    if (!document.body || typeof MutationObserver === "undefined") return;
    let timer = null;
    const observer = new MutationObserver(() => {
      window.clearTimeout(timer);
      timer = window.setTimeout(enhanceDynamic, 180);
    });
    observer.observe(document.body, { childList: true, subtree: true });
  }

  function boot() {
    setTheme(getTheme());
    injectUxDock();
    enhanceDynamic();
    observe();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
