const { test, expect } = require("@playwright/test");

const pages = [
  { path: "/app/", title: /FeedFormula|Nutrition/i },
  { path: "/app/modules.html", title: /FeedFormula|Nutrition/i },
  { path: "/app/nutricore.html", title: /FeedFormula|Nutrition/i },
  { path: "/app/vetscan.html", title: /FeedFormula|Nutrition/i },
  { path: "/app/reprotrack.html", title: /FeedFormula|Nutrition/i },
  { path: "/app/farmmanager.html", title: /FeedFormula|Nutrition/i },
  { path: "/app/farmacademy.html", title: /FeedFormula|Nutrition/i },
  { path: "/app/farmcast.html", title: /FeedFormula|Nutrition/i },
  { path: "/app/farmcommunity.html", title: /FeedFormula|Nutrition/i },
  { path: "/app/abonnement.html", title: /FeedFormula|Nutrition/i },
  { path: "/app/profil.html", title: /FeedFormula|Nutrition/i },
  { path: "/app/classement.html", title: /FeedFormula|Nutrition/i },
];

async function expectNoHorizontalOverflow(page) {
  const overflow = await page.evaluate(() => {
    const doc = document.documentElement;
    return Math.max(0, doc.scrollWidth - doc.clientWidth);
  });
  expect(overflow).toBeLessThanOrEqual(4);
}

test.describe("FeedFormula AI — QA mobile mondiale", () => {
  for (const item of pages) {
    test(`${item.path} charge sans débordement horizontal`, async ({ page }) => {
      await page.goto(item.path, { waitUntil: "domcontentloaded" });
      await expect(page).toHaveTitle(item.title);
      await expect(page.locator("body")).toBeVisible();
      await expectNoHorizontalOverflow(page);
      const tappableTooSmall = await page.evaluate(() => {
        return Array.from(document.querySelectorAll("button, a, input, select, textarea"))
          .filter((el) => {
            const rect = el.getBoundingClientRect();
            if (!rect.width || !rect.height) return false;
            if (el.closest("script, style")) return false;
            return rect.height < 40 && rect.width < 40;
          })
          .slice(0, 5)
          .map((el) => el.outerHTML.slice(0, 120));
      });
      expect(tappableTooSmall, `Éléments tactiles trop petits: ${tappableTooSmall.join(" | ")}`).toHaveLength(0);
    });
  }

  test("les 8 modules sont navigables depuis la grille", async ({ page }) => {
    await page.goto("/app/modules.html", { waitUntil: "domcontentloaded" });
    const targets = [
      "nutricore",
      "vetscan",
      "reprotrack",
      "farmacademy",
      "pasturemap",
      "farmmanager",
      "farmcast",
      "farmcommunity",
    ];
    for (const target of targets) {
      await expect(page.locator(`[data-module-action][data-target="${target}"]`)).toBeVisible();
    }
  });

  test("le changement de langue traduit les sections clés", async ({ page }) => {
    await page.goto("/app/", { waitUntil: "domcontentloaded" });
    const select = page.locator("[data-language-select], .language-select").first();
    await expect(select).toBeVisible();
    await select.selectOption("en");
    await expect(page.locator("body")).toContainText(/Choose your language|Generate my ration|Talk to FeedFormula/i);
    await select.selectOption("fon");
    await expect(page.locator("body")).toContainText(/Sɔ́n|núɖuɖu|gbè|Mɔdul/i);
  });

  test("NutriCore génère une ration ou utilise le fallback affichable", async ({ page }) => {
    await page.goto("/app/nutricore.html", { waitUntil: "domcontentloaded" });
    const body = page.locator("body");
    await expect(body).toContainText(/NutriCore|ration|Générer/i);
    const button = page.locator("[data-generate-ration], .btn-generate, #btnGenerer, text=/Générer/i").first();
    if (await button.count()) {
      await button.click();
      await expect(body).toContainText(/ration|FCFA|Coût|Composition/i, { timeout: 20000 });
    }
  });

  test("endpoints métier critiques répondent", async ({ request }) => {
    await expect((await request.get("/sante")).status()).toBe(200);
    await expect((await request.get("/marche/prix")).status()).toBe(200);
    await expect((await request.get("/academy/formations")).status()).toBe(200);
    await expect((await request.get("/community/posts")).status()).toBe(200);
    await expect((await request.get("/gamification/defis-du-jour")).status()).toBe(200);
    const ration = await request.post("/generer-ration", {
      data: {
        espece: "poulet_chair",
        stade: "croissance",
        ingredients_disponibles: ["mais", "tourteau_soja"],
        nombre_animaux: 50,
        langue: "fr",
        objectif: "equilibre",
      },
    });
    await expect(ration.status()).toBe(200);
    const payload = await ration.json();
    expect(payload.ration).toContain("FCFA");
  });
});
