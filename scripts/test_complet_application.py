#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test fonctionnel complet FeedFormula AI.

Objectif: couvrir backend, frontend statique, boutons, formulaires, micro,
liens, assets, sécurité, responsive et déploiement local via TestClient.
Le script génère docs/RAPPORT_TEST_COMPLET_FONCTIONNALITES.md.
"""

from __future__ import annotations

import ast
import json
import os
import re
import sys
import tempfile
import time
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
DOCS = ROOT / "docs"

os.environ["APP_ENV"] = "test"
os.environ["SKIP_DB_INIT"] = "1"
os.environ["SECRET_KEY"] = os.environ.get("SECRET_KEY") or "test-complet-secret"
os.environ["AFRI_API_KEY"] = ""
os.environ["FEDAPAY_SECRET_KEY"] = ""
os.environ["DATABASE_URL"] = f"sqlite:///{(Path(tempfile.gettempdir()) / 'feedformula_test_complet.db').as_posix()}"

for item in [ROOT, BACKEND, ROOT / "gamification"]:
    value = str(item)
    if value not in sys.path:
        sys.path.insert(0, value)

HTML_PAGES = [
    "index.html",
    "modules.html",
    "nutricore.html",
    "vetscan.html",
    "reprotrack.html",
    "profil.html",
    "classement.html",
    "farmacademy.html",
    "farmcast.html",
    "farmcommunity.html",
    "abonnement.html",
    "pasturemap.html",
    "farmmanager.html",
    "investisseurs.html",
    "offline.html",
    "floravet.html",
    "analytics.html",
]

CRITICAL_JS_FUNCTIONS = [
    "genererRation",
    "lireRationVocalement",
    "telechargerPDF",
    "partagerWhatsApp",
    "showToast",
    "afficherEtatVide",
    "changerLangue",
    "bindMicButton",
    "fetchJsonWithTimeout",
]

MIC_EXPECTATIONS = [
    ("index.html", "data-mic-button"),
    ("script.js", "SpeechRecognition"),
    ("script.js", "webkitSpeechRecognition"),
    ("script.js", "recognition.onerror"),
]

@dataclass
class Result:
    name: str
    ok: bool
    detail: str = ""
    severity: str = "info"
    duration: float = 0.0


@dataclass
class State:
    results: list[Result] = field(default_factory=list)

    def add(self, name: str, ok: bool, detail: str = "", severity: str = "info", duration: float = 0.0) -> None:
        self.results.append(Result(name, ok, detail, severity, duration))

    @property
    def failures(self) -> list[Result]:
        return [r for r in self.results if not r.ok]

    @property
    def critical_failures(self) -> list[Result]:
        return [r for r in self.failures if r.severity == "critical"]


STATE = State()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


class TagParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tags: list[tuple[str, dict[str, str]]] = []
        self.links: list[str] = []
        self.images: list[dict[str, str]] = []
        self.buttons: list[dict[str, str]] = []
        self.inputs: list[dict[str, str]] = []
        self.forms: list[dict[str, str]] = []
        self.scripts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        data = {k: (v or "") for k, v in attrs}
        self.tags.append((tag, data))
        if tag == "a" and data.get("href"):
            self.links.append(data["href"])
        elif tag == "img":
            self.images.append(data)
        elif tag == "button":
            self.buttons.append(data)
        elif tag in {"input", "textarea", "select"}:
            self.inputs.append(data)
        elif tag == "form":
            self.forms.append(data)
        elif tag == "script" and data.get("src"):
            self.scripts.append(data["src"])


def parse_html(path: Path) -> TagParser:
    parser = TagParser()
    parser.feed(read_text(path))
    return parser


def timed(name: str, fn, severity: str = "critical") -> Any:
    start = time.perf_counter()
    try:
        value = fn()
        STATE.add(name, True, "", severity, time.perf_counter() - start)
        return value
    except Exception as exc:
        STATE.add(name, False, str(exc), severity, time.perf_counter() - start)
        return None


def check_python_syntax() -> None:
    for folder in [BACKEND, ROOT / "gamification", ROOT / "scripts"]:
        for path in sorted(folder.glob("*.py")):
            try:
                ast.parse(read_text(path), filename=str(path))
                STATE.add(f"Syntaxe Python {path.relative_to(ROOT)}", True)
            except SyntaxError as exc:
                STATE.add(f"Syntaxe Python {path.relative_to(ROOT)}", False, str(exc), "critical")


def import_app():
    import database  # type: ignore
    database.Base.metadata.create_all(bind=database.engine)
    import main  # type: ignore
    return main.app, database


def call(client, method: str, url: str, **kwargs: Any) -> tuple[bool, str, Any, float]:
    start = time.perf_counter()
    response = getattr(client, method.lower())(url, **kwargs)
    duration = time.perf_counter() - start
    try:
        payload = response.json()
    except Exception:
        payload = response.text[:500]
    ok = 200 <= response.status_code < 300
    detail = f"HTTP {response.status_code} en {duration:.2f}s"
    if not ok:
        detail += f" | {str(payload)[:400]}"
    return ok, detail, payload, duration


def check_backend_endpoints() -> None:
    from fastapi.testclient import TestClient
    app, _database = import_app()
    client = TestClient(app)
    phone = "+22968" + str(int(time.time()) % 10_000_000).rjust(7, "0")
    user_id = f"qa_user_{int(time.time())}"

    # Crée d'abord un vrai utilisateur afin que les modules liés à users
    # (gamification, paiement, community, reprotrack) soient testés en conditions réalistes.
    ok_signup, detail_signup, signup_payload, signup_duration = call(
        client,
        "POST",
        "/auth/inscription",
        json={
            "telephone": phone,
            "prenom": "QA",
            "langue_preferee": "fr",
            "espece_principale": "poulet",
            "region": "Atlantique",
        },
    )
    STATE.add("Endpoint POST /auth/inscription", ok_signup, detail_signup, "critical", signup_duration)
    otp_code = signup_payload.get("otp_dev") or signup_payload.get("otp_pour_test") if isinstance(signup_payload, dict) else None
    if otp_code:
        ok_verify, detail_verify, verify_payload, verify_duration = call(
            client,
            "POST",
            "/auth/verifier-otp",
            json={"telephone": phone, "code_otp": otp_code},
        )
        STATE.add("Endpoint POST /auth/verifier-otp", ok_verify, detail_verify, "critical", verify_duration)
        if ok_verify and isinstance(verify_payload, dict):
            user_id = str(verify_payload.get("user", {}).get("id") or user_id)
            token = verify_payload.get("access_token")
            ok_profile, detail_profile, _profile_payload, profile_duration = call(
                client,
                "GET",
                "/auth/profil",
                headers={"Authorization": f"Bearer {token}"},
            )
            STATE.add("Endpoint GET /auth/profil avec JWT", ok_profile, detail_profile, "critical", profile_duration)

    endpoints: list[tuple[str, str, dict[str, Any], str]] = [
        ("GET", "/sante", {}, "critical"),
        ("GET", "/marche/prix", {}, "critical"),
        ("GET", "/marche/prix/mais", {}, "important"),
        ("POST", "/generer-ration", {"json": {"espece": "poulet_chair", "stade": "croissance", "ingredients_disponibles": ["maïs", "tourteau soja", "farine poisson"], "nombre_animaux": 50, "langue": "fr", "objectif": "equilibre"}}, "critical"),
        ("POST", "/vetscan/diagnostiquer", {"json": {"espece": "poulet", "symptomes": "toux diarrhée verte mortalité", "langue": "fr", "user_id": user_id}}, "critical"),
        ("POST", "/vetscan/analyser-photo", {"files": {"image": ("animal.jpg", b"fake-image", "image/jpeg")}, "data": {"espece": "poulet", "langue": "fr", "user_id": user_id}}, "important"),
        ("GET", "/vetscan/veterinaires/Atlantique", {}, "important"),
        ("GET", f"/vetscan/historique/{user_id}", {}, "important"),
        ("POST", "/reprotrack/evenement", {"json": {"user_id": user_id, "animal_id": "VACHE_QA_1", "espece": "vache", "type_evenement": "saillie", "date_evenement": "2026-01-10"}}, "critical"),
        ("GET", f"/reprotrack/calendrier/{user_id}", {}, "important"),
        ("GET", f"/reprotrack/alertes/{user_id}", {}, "important"),
        ("GET", f"/reprotrack/stats/{user_id}", {}, "important"),
        ("POST", "/pasturemap/analyser", {"json": {"user_id": user_id, "espece": "bovin", "nombre_animaux": 10, "superficie_hectares": 2, "nombre_paddocks": 4, "saison": "pluie", "langue": "fr", "parcelles": [{"nom": "A", "superficie_ha": 2}] }}, "important"),
        ("GET", f"/pasturemap/recommandations/{user_id}", {}, "important"),
        ("POST", "/farmmanager/evenement", {"json": {"texte": "Vache 47 traitée coût 8500", "user_id": user_id, "langue": "fr"}}, "critical"),
        ("GET", f"/farmmanager/evenements/{user_id}", {}, "important"),
        ("GET", f"/farmmanager/finances/tableau-bord/{user_id}", {}, "important"),
        ("GET", f"/farmmanager/ia/briefing-quotidien/{user_id}", {}, "important"),
        ("GET", f"/farmmanager/planning/semaine/{user_id}", {}, "important"),
        ("POST", "/farmmanager/planning/cycle-production", {"json": {"espece": "poulet_chair", "nombre_animaux": 100, "date_demarrage": "2026-06-01", "objectif_vente": "45 jours", "budget_disponible": 200000, "user_id": user_id}}, "important"),
        ("GET", f"/farmmanager/stocks/critiques/{user_id}", {}, "important"),
        ("POST", "/farmmanager/sanitaire/traitement", {"json": {"animaux_concernes": ["VACHE_001"], "maladie_suspectee": "mammite", "medicament": "antibiotique", "dose": "10 ml", "duree_jours": 3, "cout_fcfa": 8500, "user_id": user_id}}, "important"),
        ("GET", "/academy/formations", {}, "critical"),
        ("GET", "/academy/formation/alimentation_volailles", {}, "important"),
        ("GET", "/academy/lecon/alimentation_volailles/1", {}, "important"),
        ("POST", "/academy/quiz/soumettre", {"json": {"user_id": user_id, "formation_code": "alimentation_volailles", "numero": 1, "reponses": [0, 1, 2, 0, 3], "langue": "fr"}}, "important"),
        ("GET", f"/academy/progression/{user_id}", {}, "important"),
        ("POST", "/farmcast/creer", {"json": {"theme": "vaccination Newcastle volailles", "langue": "fr", "format_type": "whatsapp_audio", "public_cible": "éleveurs", "user_id": user_id}}, "important"),
        ("GET", f"/farmcast/contenus/{user_id}", {}, "important"),
        ("GET", "/community/posts", {}, "critical"),
        ("POST", "/community/posts", {"json": {"user_id": user_id, "titre": "Question santé", "contenu": "Mes poulets toussent", "type_post": "question", "espece_concernee": "poulet_chair", "langue": "fr"}}, "important"),
        ("GET", "/community/marche", {}, "important"),
        ("POST", "/community/marche", {"json": {"user_id": user_id, "type_annonce": "vente", "espece": "poulet_chair", "race": "Cobb", "quantite": 10, "prix_fcfa": 3500, "description": "Poulets prêts", "localisation": "Cotonou", "departement": "Atlantique"}}, "important"),
        ("POST", "/floravet/analyser-photo", {"files": {"image": ("moringa.jpg", b"fake-moringa", "image/jpeg")}, "data": {"espece_eleveur": "poulet_chair", "region_benin": "Atlantique", "langue": "fr", "user_id": user_id}}, "important"),
        ("GET", "/floravet/rechercher/moringa", {}, "important"),
        ("GET", "/floravet/region/Atlantique?espece=poulet_chair", {}, "important"),
        ("GET", "/floravet/bibliotheque", {}, "important"),
        ("POST", "/audio/synthese", {"json": {"texte": "Bonjour éleveur", "langue": "fr"}}, "important"),
        ("POST", "/audio/transcription", {"files": {"audio": ("audio.wav", b"RIFF0000WAVEfmt ", "audio/wav")}, "data": {"langue": "fr"}}, "important"),
        ("POST", "/audio/ration-vocale", {"json": {"ration_texte": "Ration test", "langue": "fr"}}, "important"),
        ("GET", "/audio/demo/fr", {}, "important"),
        ("POST", "/gamification/action", {"json": {"user_id": user_id, "action": "connexion_jour"}}, "important"),
        ("POST", "/gamification/action", {"json": {"user_id": user_id, "action": "generer_ration"}}, "important"),
        ("GET", f"/gamification/profil/{user_id}", {}, "important"),
        ("GET", "/gamification/classement", {}, "important"),
        ("GET", "/gamification/defis-du-jour", {}, "important"),
        ("POST", "/gamification/defi/completer", {"json": {"user_id": user_id, "defi_numero": 1}}, "important"),
        ("GET", f"/gamification/trophees/{user_id}", {}, "important"),
        ("GET", f"/gamification/ligue/{user_id}", {}, "important"),
        ("POST", "/auth/connexion", {"json": {"telephone": phone}}, "critical"),
        ("POST", "/paiement/creer", {"json": {"user_id": user_id, "abonnement": "standard", "duree": "mensuel", "telephone": "+22969990000", "prenom": "QA"}}, "important"),
        ("GET", f"/paiement/abonnement/{user_id}", {}, "important"),
        ("GET", f"/paiement/historique/{user_id}", {}, "important"),
        ("GET", f"/notifications/du-jour/{user_id}", {}, "important"),
        ("GET", "/notifications/messages-aya", {}, "important"),
        ("GET", "/analytics/stats", {"headers": {"X-Admin-Password": "feedformula-admin-demo"}}, "important"),
    ]

    for method, url, kwargs, severity in endpoints:
        ok, detail, payload, duration = call(client, method, url, **kwargs)
        STATE.add(f"Endpoint {method} {url}", ok, detail, severity, duration)


def check_frontend_static() -> None:
    existing_pages = {p.name for p in FRONTEND.glob("*.html")}
    for page in HTML_PAGES:
        path = FRONTEND / page
        if not path.exists():
            STATE.add(f"Page HTML présente {page}", False, "manquante", "critical")
            continue
        text = read_text(path)
        lower = text.lower()
        parser = parse_html(path)
        STATE.add(f"Page HTML présente {page}", True)
        STATE.add(f"DOCTYPE {page}", "<!doctype html" in lower, "", "important")
        STATE.add(f"Viewport {page}", "name=\"viewport\"" in lower and "width=device-width" in lower, "", "important")
        STATE.add(f"CSS global {page}", "style.css" in lower, "", "important")
        STATE.add(f"Manifest {page}", "manifest.json" in lower, "", "important")
        STATE.add(f"Pas de Lorem/TODO visible {page}", "lorem ipsum" not in lower and "todo" not in lower and "fixme" not in lower, "", "info")

        for href in parser.links:
            if href.startswith(("http", "mailto:", "tel:", "#", "javascript:")):
                continue
            clean_href = href.split("#", 1)[0].split("?", 1)[0]
            if clean_href.endswith(".html"):
                STATE.add(f"Lien interne {page} -> {clean_href}", clean_href in existing_pages, "", "important")

        for img in parser.images:
            alt_ok = "alt" in img
            src = img.get("src", "")
            src_clean = src.split("?", 1)[0]
            if src_clean.startswith(("http", "data:")) or not src_clean:
                exists = True
            else:
                target = (path.parent / src_clean).resolve() if not src_clean.startswith("/") else (ROOT / src_clean.lstrip("/")).resolve()
                exists = target.exists()
            STATE.add(f"Image alt {page}: {src[:50]}", alt_ok, "alt absent", "important")
            STATE.add(f"Image existe {page}: {src[:50]}", exists, "asset introuvable", "important")

        bad_buttons = []
        for button in parser.buttons:
            if not (button.get("id") or button.get("class") or button.get("aria-label") or button.get("data-module-action") or button.get("data-lang") or button.get("onclick")):
                bad_buttons.append(str(button)[:120])
        STATE.add(f"Boutons identifiables {page}", not bad_buttons, "; ".join(bad_buttons[:5]), "important")

        bad_inputs = []
        for inp in parser.inputs:
            if inp.get("type") == "hidden":
                continue
            if not (inp.get("id") or inp.get("aria-label") or inp.get("name")):
                bad_inputs.append(str(inp)[:120])
        STATE.add(f"Champs formulaires identifiables {page}", not bad_inputs, "; ".join(bad_inputs[:5]), "important")


def check_buttons_and_micro() -> None:
    index = read_text(FRONTEND / "index.html")
    script = read_text(FRONTEND / "script.js")
    api_bindings = read_text(FRONTEND / "api_bindings.js")
    combined = index + "\n" + script + "\n" + api_bindings

    expected_selectors = [
        ("Bouton génération", "id=\"btnGenerer\""),
        ("Bouton micro accueil", "data-mic-button"),
        ("Bouton écoute ration", "id=\"btnEcouterRation\""),
        ("Bouton PDF", "id=\"btnTelechargerPDF\""),
        ("Bouton WhatsApp", "id=\"btnPartagerWhatsApp\""),
        ("Bouton sauvegarde historique", "id=\"btnSauvegarderHistorique\""),
        ("Sélecteur langue", "data-language-select"),
        ("Grille espèces", "id=\"speciesGrid\""),
        ("Slider animaux", "id=\"nombreAnimaux\""),
    ]
    for label, needle in expected_selectors:
        STATE.add(label, needle in index, needle, "critical")

    for page, needle in MIC_EXPECTATIONS:
        source = read_text(FRONTEND / page)
        STATE.add(f"Micro: {needle} dans {page}", needle in source, "", "critical")

    for function_name in CRITICAL_JS_FUNCTIONS:
        if function_name == "changerLangue":
            found = any(name in combined for name in ["changerLangue", "applyLanguage", "updateLanguageUI", "data-language-select"])
        else:
            found = re.search(rf"function\s+{re.escape(function_name)}\b", script) or function_name in combined
        STATE.add(f"Fonction JS critique {function_name}", bool(found), "", "critical")

    fetch_calls = re.findall(r"fetch\s*\(", script + api_bindings + read_text(FRONTEND / "api.js"))
    STATE.add("Appels fetch présents", len(fetch_calls) > 0, f"{len(fetch_calls)} appels", "important")
    STATE.add("Timeout requêtes JS", "AbortController" in read_text(FRONTEND / "api.js") or "fetchJsonWithTimeout" in script, "", "important")
    STATE.add("Gestion erreurs micro", "recognition.onerror" in script and "reconnaissance vocale" in script.lower(), "", "critical")


def check_css_responsive() -> None:
    css = read_text(FRONTEND / "style.css")
    checks = [
        ("Variable vert officiel", "--brand-primary" in css and "#1b5e20" in css.lower()),
        ("Variable or officiel", "--brand-accent" in css and "#f9a825" in css.lower()),
        ("Media mobile", "640px" in css or "375px" in css),
        ("Media tablette", "768px" in css),
        ("Media desktop", "1024px" in css),
        ("Images fluides", "max-width: 100%" in css),
        ("Boutons tactiles", "min-height: 48px" in css),
        ("Bottom nav", ".bottom-nav" in css),
        ("Toast", ".toast" in css),
        ("Skeleton", ".skeleton" in css),
        ("Animations réduites possibles", "prefers-reduced-motion" in css),
    ]
    for name, ok in checks:
        STATE.add(f"CSS {name}", ok, "", "important")


def check_assets_security_pwa() -> None:
    required_assets = [
        "assets/branding_v2/logo_feedformula_v2.png",
        "assets/branding_v2/aya_officielle_v2.png",
        "assets/branding_v2/aya_celebration_v2.png",
        "assets/branding_v2/aya_triste_v2.png",
        "assets/branding_v2/aya_urgence_v2.png",
        "assets/branding_v2/splash_screen_v2.png",
        "assets/branding_v2/hero_aviculture_premium.png",
        "assets/branding_v2/hero_elevage_bovin_premium.png",
        "assets/branding_v2/icones_animaux_production.png",
    ]
    for rel in required_assets:
        STATE.add(f"Asset requis {rel}", (ROOT / rel).exists(), "", "important")

    frontend_sources = "\n".join(read_text(p) for p in list(FRONTEND.glob("*.html")) + list(FRONTEND.glob("*.js")))
    STATE.add("Aucun secret Afri frontend", "sk-afri-" not in frontend_sources, "", "critical")
    gitignore = read_text(ROOT / ".gitignore") if (ROOT / ".gitignore").exists() else ""
    STATE.add(".env ignoré par git", ".env" in gitignore, "", "critical")

    sw = read_text(FRONTEND / "service_worker.js") if (FRONTEND / "service_worker.js").exists() else ""
    STATE.add("Service worker cache versionné", "CACHE_VERSION" in sw and "feedformula-ai" in sw, "", "important")
    STATE.add("Service worker offline fallback", "offline" in sw.lower(), "", "important")


def check_database() -> None:
    _app, database = import_app()
    database.Base.metadata.create_all(bind=database.engine)
    tables = set(database.Base.metadata.tables.keys())
    required = {
        "users", "rations", "diagnostics_vetscan", "evenements_reproduction",
        "trophees_utilisateurs", "defis_quotidiens", "completions_defis",
        "prix_marche", "formations_completees", "posts", "commentaires",
        "annonces_marche", "analyses_floravet", "bibliotheque_plantes",
        "transactions_paiement", "evenements_farm", "lots_animaux", "animaux",
        "stocks_alimentaires",
    }
    for table in sorted(required):
        STATE.add(f"Table DB {table}", table in tables, "", "critical")


def write_report() -> None:
    DOCS.mkdir(exist_ok=True)
    total = len(STATE.results)
    failed = len(STATE.failures)
    critical = len(STATE.critical_failures)
    score = 100 if total == 0 else round((total - failed) / total * 100)
    by_severity = {
        "critical": [r for r in STATE.failures if r.severity == "critical"],
        "important": [r for r in STATE.failures if r.severity == "important"],
        "info": [r for r in STATE.failures if r.severity not in {"critical", "important"}],
    }

    slow = sorted([r for r in STATE.results if r.duration], key=lambda r: r.duration, reverse=True)[:20]
    lines = [
        "# 🧪 RAPPORT DE TEST COMPLET — FEEDFORMULA AI",
        "",
        "## Synthèse",
        f"- Score global: **{score}/100**",
        f"- Tests exécutés: **{total}**",
        f"- Échecs: **{failed}** dont critiques: **{critical}**",
        f"- Statut: **{'PRÊT' if critical == 0 else 'À CORRIGER'}**",
        "",
        "## Couverture testée",
        "- Backend FastAPI: santé, ration, VetScan, ReproTrack, PastureMap, FarmManager, Academy, FarmCast, Community, FloraVet, Audio, Gamification, Auth, Paiement, Marché, Notifications, Analytics.",
        "- Frontend statique: pages HTML, liens, images, boutons, champs, scripts, PWA, assets.",
        "- Interactions subtiles: micro, reconnaissance vocale, boutons PDF/WhatsApp/audio, langue, slider animaux, grille espèces, service worker, sécurité secrets.",
        "- Responsive: présence des media queries, tailles tactiles, nav mobile, images fluides.",
        "",
        "## Échecs critiques",
    ]
    lines.extend([f"- ❌ {r.name}: {r.detail}" for r in by_severity["critical"]] or ["- Aucun échec critique."])
    lines.extend(["", "## Échecs importants"])
    lines.extend([f"- ⚠️ {r.name}: {r.detail}" for r in by_severity["important"]] or ["- Aucun échec important."])
    lines.extend(["", "## Alertes informatives"])
    lines.extend([f"- ℹ️ {r.name}: {r.detail}" for r in by_severity["info"]] or ["- Aucune alerte informative."])
    lines.extend(["", "## Endpoints / actions les plus lents"])
    lines.extend([f"- {r.name}: {r.duration:.2f}s — {'OK' if r.ok else 'ÉCHEC'}" for r in slow] or ["- Aucun timing disponible."])
    lines.extend(["", "## Détail complet"])
    for r in STATE.results:
        icon = "✅" if r.ok else "❌"
        duration = f" ({r.duration:.2f}s)" if r.duration else ""
        detail = f" — {r.detail}" if r.detail else ""
        lines.append(f"- {icon} [{r.severity}] {r.name}{duration}{detail}")

    (DOCS / "RAPPORT_TEST_COMPLET_FONCTIONNALITES.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    steps = [
        ("Syntaxe Python", check_python_syntax),
        ("Base de données", check_database),
        ("Endpoints backend", check_backend_endpoints),
        ("Frontend statique", check_frontend_static),
        ("Boutons et micro", check_buttons_and_micro),
        ("CSS responsive", check_css_responsive),
        ("Assets / sécurité / PWA", check_assets_security_pwa),
    ]
    print("🧪 Test complet FeedFormula AI")
    for label, fn in steps:
        print(f"→ {label}")
        timed(f"Étape {label}", fn, "critical")
    write_report()
    print(f"Tests: {len(STATE.results)} | Échecs: {len(STATE.failures)} | Critiques: {len(STATE.critical_failures)}")
    print(f"Rapport: {DOCS / 'RAPPORT_TEST_COMPLET_FONCTIONNALITES.md'}")
    return 0 if not STATE.critical_failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
