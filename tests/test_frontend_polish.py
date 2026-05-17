from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"

HTML_HEAD_MARKERS = [
    '<meta charset="UTF-8"',
    "maximum-scale=1.0",
    "user-scalable=no",
    "viewport-fit=cover",
    '<meta name="theme-color" content="#1B5E20"',
    'name="apple-mobile-web-app-capable"',
    'name="apple-mobile-web-app-status-bar-style"',
    'name="apple-mobile-web-app-title"',
    'name="mobile-web-app-capable"',
    'name="application-name"',
    'rel="manifest" href="/app/manifest.json"',
    'rel="apple-touch-icon"',
    'rel="preconnect" href="https://fonts.googleapis.com"',
    'rel="preconnect" href="https://fonts.gstatic.com" crossorigin',
    'rel="preload" href="/assets/branding/logo_principal_hd.png" as="image"',
    'rel="preload" href="/app/style.css" as="style"',
    "FeedFormula AI — Nutrition Animale IA | Bénin",
    'name="description"',
    'name="keywords"',
    'name="author" content="Leonel TOGBE"',
    'name="robots" content="index, follow"',
    'rel="canonical" href="https://feedformula-ai.vercel.app/app/"',
    'property="og:type" content="website"',
    'property="og:title"',
    'property="og:image"',
    'name="twitter:card" content="summary_large_image"',
    'name="twitter:image"',
    "Plus+Jakarta+Sans:wght@300;400;500;600;700;800",
    "Space+Grotesk:wght@400;500;600;700",
    "JetBrains+Mono:wght@400;500",
]

CSS_MARKERS = [
    "--font-primary",
    "--font-display",
    "--font-mono",
    "--green-950",
    "--gold-900",
    "--brand-primary",
    "--space-20",
    "--radius-2xl",
    "--shadow-brand",
    ".btn-primary:hover",
    ".card-brand",
    ".input:focus",
    ".badge-gold",
    ".progress-bar",
    ".bottom-nav",
    ".header-title",
    "@media (min-width: 640px)",
    "@media (min-width: 1024px)",
    "@keyframes fadeIn",
    "@keyframes fadeInUp",
    "@keyframes starRain",
    "@keyframes micPulse",
    "@keyframes ayaOscille",
    ".animate-fadeInUp",
    ".skeleton",
    ".page-transition-enter",
    ":focus-visible",
    "::-webkit-scrollbar-thumb",
    ".touchable:active",
    "@media (prefers-color-scheme: dark)",
    "body.dark",
    ".toast-container",
    ".pull-refresh-indicator",
    ".infinite-scroll-indicator",
    ".line-clamp-3",
]

JS_MARKERS = [
    "function showToast",
    "function vibrer",
    "function confirmerAction",
    "function afficherEtatVide",
    "function filtrerListe",
    "function setupInfiniteScroll",
    "function copierTexte",
    "function setupPullToRefresh",
    "function toggleDarkMode",
    "localStorage.setItem(STORAGE_KEYS.theme",
    "window.showToast = showToast",
    "window.toggleDarkMode = toggleDarkMode",
    "applyAccessibilityEnhancements",
]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def normalize_html(text: str) -> str:
    """Compacte les espaces pour accepter les attributs HTML multi-lignes."""
    return " ".join(text.split())


def test_all_html_pages_have_pwa_seo_and_premium_fonts() -> None:
    html_files = sorted(FRONTEND.glob("*.html"))
    assert html_files, "Aucune page HTML trouvée dans frontend/."

    failures: dict[str, list[str]] = {}
    for html_file in html_files:
        content = normalize_html(read_text(html_file))
        missing = [
            marker
            for marker in HTML_HEAD_MARKERS
            if normalize_html(marker) not in content
        ]
        if missing:
            failures[html_file.name] = missing

    assert not failures, "Pages HTML sans head PWA/SEO/polices complet: " + repr(
        failures
    )


def test_manifest_is_valid_for_vercel_app_path() -> None:
    manifest_path = FRONTEND / "manifest.json"
    manifest = json.loads(read_text(manifest_path))

    assert manifest["name"] == "FeedFormula AI"
    assert manifest["short_name"] == "FeedFormula"
    assert manifest["start_url"] == "/app/"
    assert manifest["display"] == "standalone"
    assert manifest["background_color"] == "#1B5E20"
    assert manifest["theme_color"] == "#1B5E20"
    assert manifest["orientation"] == "portrait"
    assert manifest["lang"] == "fr"
    assert {icon["sizes"] for icon in manifest["icons"]} == {"192x192", "512x512"}
    assert all(
        icon["src"] == "/assets/branding/logo_principal_hd.png"
        for icon in manifest["icons"]
    )


def test_style_css_contains_design_system_responsive_animations_and_dark_mode() -> None:
    css = read_text(FRONTEND / "style.css")
    missing = [marker for marker in CSS_MARKERS if marker not in css]
    assert not missing, "Marqueurs CSS polish manquants: " + repr(missing)


def test_script_js_contains_requested_ux_helpers_and_exports() -> None:
    script = read_text(FRONTEND / "script.js")
    missing = [marker for marker in JS_MARKERS if marker not in script]
    assert not missing, "Marqueurs JS UX manquants: " + repr(missing)


def test_vercel_routes_expose_frontend_under_app_and_static_assets() -> None:
    config = json.loads(read_text(ROOT / "vercel.json"))
    routes = config.get("routes", [])
    route_pairs = {(route.get("src"), route.get("dest")) for route in routes}

    assert ("/app", "/frontend/index.html") in route_pairs
    assert ("/app/", "/frontend/index.html") in route_pairs
    assert ("/app/(.*)", "/frontend/$1") in route_pairs
    assert ("/assets/(.*)", "/assets/$1") in route_pairs
    assert ("/api/(.*)", "/backend/main.py") in route_pairs


def test_deployment_uses_source_bundles_not_stale_minified_assets() -> None:
    stale_refs: dict[str, list[str]] = {}
    for html_file in sorted(FRONTEND.glob("*.html")):
        content = read_text(html_file)
        refs = [ref for ref in ("script.min.js", "style.min.css") if ref in content]
        if refs:
            stale_refs[html_file.name] = refs

    assert not stale_refs, "Références minifiées obsolètes détectées: " + repr(
        stale_refs
    )
