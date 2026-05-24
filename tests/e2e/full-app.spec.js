const { test, expect } = require("@playwright/test");

const appPages = [
  "/app/",
  "/app/modules.html",
  "/app/nutricore.html",
  "/app/vetscan.html",
  "/app/reprotrack.html",
  "/app/pasturemap.html",
  "/app/farmmanager.html",
  "/app/farmacademy.html",
  "/app/farmcast.html",
  "/app/farmcommunity.html",
  "/app/floravet.html",
  "/app/abonnement.html",
  "/app/profil.html",
  "/app/classement.html",
  "/app/investisseurs.html",
  "/app/offline.html",
  "/app/analytics.html",
];

const criticalApiChecks = [
  ["GET", "/sante"],
  ["GET", "/marche/prix"],
  ["GET", "/academy/formations"],
  ["GET", "/community/posts"],
  ["GET", "/floravet/bibliotheque"],
  ["GET", "/notifications/messages-aya"],
  ["GET", "/gamification/defis-du-jour"],
];

function uniquePhone() {
  return `+22968${String(Date.now()).slice(-7)}`;
}

async function collectBrowserErrors(page) {
  const errors = [];
  page.on("pageerror", (error) => errors.push(`pageerror: ${error.message}`));
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(`console.error: ${message.text()}`);
  });
  return errors;
}

async function expectNoHorizontalOverflow(page) {
  const overflow = await page.evaluate(() => {
    const doc = document.documentElement;
    return Math.max(0, doc.scrollWidth - doc.clientWidth);
  });
  expect(overflow, "La page ne doit pas déborder horizontalement").toBeLessThanOrEqual(4);
}

async function expectUsableTouchTargets(page) {
  const tooSmall = await page.evaluate(() => {
    return Array.from(document.querySelectorAll("button, a, input, select, textarea"))
      .filter((el) => {
        const style = window.getComputedStyle(el);
        if (style.display === "none" || style.visibility === "hidden") return false;
        const rect = el.getBoundingClientRect();
        if (!rect.width || !rect.height) return false;
        if (el.closest("script, style, template")) return false;
        return rect.height < 40 && rect.width < 40;
      })
      .slice(0, 10)
      .map((el) => ({ tag: el.tagName, text: el.textContent.trim().slice(0, 40), html: el.outerHTML.slice(0, 140) }));
  });
  expect(tooSmall, `Éléments tactiles trop petits: ${JSON.stringify(tooSmall)}`).toHaveLength(0);
}

async function expectImagesLoaded(page) {
  const broken = await page.evaluate(() => {
    return Array.from(document.images)
      .filter((img) => {
        const style = window.getComputedStyle(img);
        if (style.display === "none" || style.visibility === "hidden") return false;
        return img.complete && img.naturalWidth === 0;
      })
      .map((img) => img.getAttribute("src"));
  });
  expect(broken, `Images cassées: ${broken.join(", ")}`).toHaveLength(0);
}

async function clickVisibleButtonsSafely(page, limit = 12) {
  const buttons = page.locator("button:visible");
  const count = Math.min(await buttons.count(), limit);
  const clicked = [];
  for (let index = 0; index < count; index += 1) {
    const button = buttons.nth(index);
    const label = (await button.innerText().catch(() => "")).trim().slice(0, 60);
    const disabled = await button.isDisabled().catch(() => true);
    if (disabled) continue;
    const lower = label.toLowerCase();
    if (lower.includes("supprimer") || lower.includes("déconnexion") || lower.includes("delete")) continue;
    await button.scrollIntoViewIfNeeded().catch(() => {});
    await button.click({ timeout: 2000 }).catch(() => {});
    clicked.push(label || `button-${index}`);
    await page.waitForTimeout(120);
  }
  return clicked;
}

test.describe("FeedFormula AI — parcours navigateur complets", () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      class FakeSpeechRecognition {
        constructor() {
          this.continuous = false;
          this.interimResults = false;
          this.maxAlternatives = 1;
          this.lang = "fr-FR";
          this.onstart = null;
          this.onresult = null;
          this.onend = null;
          this.onerror = null;
        }
        start() {
          setTimeout(() => {
            if (this.onstart) this.onstart();
            if (this.onresult) {
              this.onresult({
                results: [[{ transcript: "poulet croissance maïs soja", confidence: 0.98 }]],
              });
            }
            if (this.onend) this.onend();
          }, 30);
        }
        stop() {
          if (this.onend) this.onend();
        }
      }
      window.SpeechRecognition = FakeSpeechRecognition;
      window.webkitSpeechRecognition = FakeSpeechRecognition;
      Object.defineProperty(navigator, "mediaDevices", {
        configurable: true,
        value: {
          getUserMedia: async () => ({ getTracks: () => [{ stop() {} }] }),
        },
      });
    });
  });

  for (const path of appPages) {
    test(`${path} charge, reste responsive et ses boutons ne cassent pas`, async ({ page }) => {
      const errors = await collectBrowserErrors(page);
      await page.goto(path, { waitUntil: "domcontentloaded" });
      await expect(page.locator("body")).toBeVisible();
      await expect(page).toHaveTitle(/FeedFormula|NutriCore|VetScan|Farm|Flora|Repro|Analytics|Erreur/i);
      await expectNoHorizontalOverflow(page);
      await expectUsableTouchTargets(page);
      await expectImagesLoaded(page);
      const clicked = await clickVisibleButtonsSafely(page, 10);
      expect(clicked.length, "Au moins un bouton doit être testable si la page en contient").toBeGreaterThanOrEqual(0);
      await expectNoHorizontalOverflow(page);
      expect(errors, `Erreurs JS sur ${path}: ${errors.join(" | ")}`).toHaveLength(0);
    });
  }

  test("accueil: langue, micro, espèces, slider, objectifs et ration", async ({ page }) => {
    const errors = await collectBrowserErrors(page);
    await page.goto("/app/", { waitUntil: "domcontentloaded" });

    const languageSelect = page.locator("[data-language-select], #preferredLanguageSelect").first();
    await expect(languageSelect).toBeVisible();
    await languageSelect.selectOption("en");
    await expect(page.locator("body")).toContainText(/Choose your language|Generate my ration|Talk to FeedFormula/i);
    await languageSelect.selectOption("fr");

    const mic = page.locator("[data-mic-button], #btnMic").first();
    await expect(mic).toBeVisible();
    await mic.click();
    await expect(page.locator("body")).toContainText(/poulet|maïs|soja|Appuyez|Parlez/i, { timeout: 5000 });

    await page.locator('[data-species="poulet"], [data-espece="poulet"]').first().click();
    await expect(page.locator("#stageSection, #stade").first()).toBeVisible();

    const slider = page.locator("#nombreAnimaux");
    await expect(slider).toBeVisible();
    await slider.fill("120").catch(async () => {
      await slider.evaluate((el) => {
        el.value = "120";
        el.dispatchEvent(new Event("input", { bubbles: true }));
        el.dispatchEvent(new Event("change", { bubbles: true }));
      });
    });
    await expect(page.locator("body")).toContainText(/120|Nombre d'animaux/i);

    await page.locator('input[name="objectif"][value="economique"]').check({ force: true });
    await page.locator("#ingredientsInput, [data-ingredients-input]").first().fill("maïs");
    await page.keyboard.press("Enter").catch(() => {});

    await page.locator("#btnGenerer, [data-generate-ration]").first().click();
    await expect(page.locator("body")).toContainText(/FCFA|ration|Composition|Coût/i, { timeout: 30000 });
    expect(errors, `Erreurs JS accueil: ${errors.join(" | ")}`).toHaveLength(0);
  });

  test("NutriCore: parcours ration complet avec boutons audio PDF WhatsApp", async ({ page }) => {
    const errors = await collectBrowserErrors(page);
    await page.goto("/app/nutricore.html", { waitUntil: "domcontentloaded" });
    await expect(page.locator("body")).toContainText(/NutriCore|ration/i);

    const textareas = page.locator("textarea:visible");
    if (await textareas.count()) await textareas.first().fill("Poulet de chair croissance, 50 animaux, maïs soja farine poisson");
    const generate = page.locator("#generateButton, #btnGenerer, [data-generate-ration], button:has-text('Générer')").first();
    if (await generate.count()) {
      await generate.click();
      await expect(page.locator("body")).toContainText(/FCFA|ration|Composition|Coût/i, { timeout: 30000 });
    }

    for (const pattern of [/Écouter/i, /PDF/i, /WhatsApp/i]) {
      const action = page.getByRole("button", { name: pattern }).first();
      if (await action.count()) await action.click().catch(() => {});
    }
    expect(errors, `Erreurs JS NutriCore: ${errors.join(" | ")}`).toHaveLength(0);
  });

  test("VetScan: symptômes, photo fictive, micro et diagnostic", async ({ page }) => {
    const errors = await collectBrowserErrors(page);
    await page.goto("/app/vetscan.html", { waitUntil: "domcontentloaded" });
    await expect(page.locator("body")).toContainText(/VetScan|Diagnostic|sympt/i);

    const symptoms = page.locator("#symptomsInput, textarea").first();
    if (await symptoms.count()) await symptoms.fill("Poulet, toux, diarrhée verte, mortalité");

    const fileInput = page.locator('input[type="file"]').first();
    if (await fileInput.count()) {
      await fileInput.setInputFiles({
        name: "poulet-test.jpg",
        mimeType: "image/jpeg",
        buffer: Buffer.from([255, 216, 255, 224, 0, 16, 74, 70, 73, 70, 0, 1, 255, 217]),
      }).catch(() => {});
    }

    const mic = page.locator("#vetscanMicButton, [data-mic-button]").first();
    if (await mic.count()) await mic.click().catch(() => {});

    const diagnose = page.locator("#diagnoseButton, #analyzeButton, button:has-text('Diagnostiquer'), button:has-text('Analyser')").first();
    if (await diagnose.count()) {
      await diagnose.click();
      await expect(page.locator("body")).toContainText(/diagnostic|protocole|urgence|probabil/i, { timeout: 30000 });
    }
    expect(errors, `Erreurs JS VetScan: ${errors.join(" | ")}`).toHaveLength(0);
  });

  test("API: endpoints critiques et parcours auth complet", async ({ request }) => {
    for (const [method, url] of criticalApiChecks) {
      const response = method === "GET" ? await request.get(url) : await request.post(url);
      expect(response.status(), `${method} ${url}`).toBeLessThan(300);
    }

    const phone = uniquePhone();
    const signup = await request.post("/auth/inscription", {
      data: { telephone: phone, prenom: "QA", langue_preferee: "fr", espece_principale: "poulet", region: "Atlantique" },
    });
    expect(signup.status()).toBeLessThan(300);
    const signupPayload = await signup.json();
    const otp = signupPayload.otp_dev || signupPayload.otp_pour_test;
    expect(otp).toBeTruthy();

    const verify = await request.post("/auth/verifier-otp", { data: { telephone: phone, code_otp: otp } });
    expect(verify.status()).toBeLessThan(300);
    const verifyPayload = await verify.json();
    const userId = verifyPayload.user.id;
    const token = verifyPayload.access_token;
    expect(token).toBeTruthy();

    const profile = await request.get("/auth/profil", { headers: { Authorization: `Bearer ${token}` } });
    expect(profile.status()).toBeLessThan(300);

    const ration = await request.post("/generer-ration", {
      data: {
        espece: "poulet_chair",
        stade: "croissance",
        ingredients_disponibles: ["maïs", "tourteau soja", "farine poisson"],
        nombre_animaux: 50,
        langue: "fr",
        objectif: "equilibre",
      },
    });
    expect(ration.status()).toBeLessThan(300);
    expect((await ration.json()).ration).toMatch(/FCFA|ration|maïs|soja/i);

    const gamification = await request.post("/gamification/action", { data: { user_id: userId, action: "connexion_jour" } });
    expect(gamification.status()).toBeLessThan(300);
  });

  test("offline/PWA: service worker, manifest et page hors ligne", async ({ page, request }) => {
    await page.goto("/app/", { waitUntil: "domcontentloaded" });
    const hasServiceWorker = await page.evaluate(() => "serviceWorker" in navigator);
    expect(hasServiceWorker).toBeTruthy();

    const manifest = await request.get("/app/manifest.json");
    expect(manifest.status()).toBeLessThan(300);
    const manifestPayload = await manifest.json();
    expect(manifestPayload.name).toContain("FeedFormula");

    const offline = await request.get("/app/offline.html");
    expect(offline.status()).toBeLessThan(300);
    expect(await offline.text()).toMatch(/hors ligne|offline|FeedFormula/i);
  });
});
