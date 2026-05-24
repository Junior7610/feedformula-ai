from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "frontend"

DEFAULT_DESCRIPTION = (
    "FeedFormula AI génère la ration parfaite pour vos animaux en 30 secondes. "
    "50 langues africaines. 8 modules IA. Gratuit pour les éleveurs béninois."
)
DEFAULT_KEYWORDS = (
    "élevage bénin, nutrition animale, IA agricole, fon, poulet, vache, ration animale"
)
DEFAULT_OG_TITLE = "FeedFormula AI — L IA au service de l élevage africain"
DEFAULT_OG_DESCRIPTION = "Formulez la ration parfaite de vos animaux en 30 secondes. En fon, yoruba, français et 47 autres langues africaines."
DEFAULT_TWITTER_TITLE = "FeedFormula AI — Nutrition Animale IA"
DEFAULT_TWITTER_DESCRIPTION = "L intelligence africaine au service de vos animaux."
DEFAULT_CANONICAL = "https://feedformula-ai.vercel.app/app/"
DEFAULT_THEME_COLOR = "#1B5E20"

FONT_LINK = (
    '<link href="https://fonts.googleapis.com/css2?'
    "family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&"
    "family=Space+Grotesk:wght@400;500;600;700&"
    'family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet" />'
)

CANONICAL_TAGS = [
    '<meta name="theme-color" content="#1B5E20" />',
    '<meta name="apple-mobile-web-app-capable" content="yes" />',
    '<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent" />',
    '<meta name="apple-mobile-web-app-title" content="FeedFormula AI" />',
    '<meta name="mobile-web-app-capable" content="yes" />',
    '<meta name="application-name" content="FeedFormula AI" />',
    '<link rel="manifest" href="/app/manifest.json" />',
    '<link rel="apple-touch-icon" href="/assets/branding/logo_principal_hd.png" />',
    '<link rel="preconnect" href="https://fonts.googleapis.com" />',
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />',
    '<link rel="preload" href="/assets/branding/logo_principal_hd.png" as="image" />',
    '<link rel="preload" href="/app/style.css" as="style" />',
    FONT_LINK,
    '<meta name="description" content="{description}" />',
    '<meta name="keywords" content="{keywords}" />',
    '<meta name="author" content="Leonel TOGBE" />',
    '<meta name="robots" content="index, follow" />',
    '<link rel="canonical" href="{canonical}" />',
    '<meta property="og:type" content="website" />',
    '<meta property="og:url" content="https://feedformula-ai.vercel.app" />',
    '<meta property="og:title" content="{og_title}" />',
    '<meta property="og:description" content="{og_description}" />',
    '<meta property="og:image" content="https://feedformula-ai.vercel.app/assets/branding/hero_image_accueil.png" />',
    '<meta property="og:image:width" content="1200" />',
    '<meta property="og:image:height" content="630" />',
    '<meta property="og:locale" content="fr_BJ" />',
    '<meta property="og:site_name" content="FeedFormula AI" />',
    '<meta name="twitter:card" content="summary_large_image" />',
    '<meta name="twitter:title" content="{twitter_title}" />',
    '<meta name="twitter:description" content="{twitter_description}" />',
    '<meta name="twitter:image" content="https://feedformula-ai.vercel.app/assets/branding/hero_image_accueil.png" />',
]

REPLACEMENTS = [
    (
        re.compile(r'<meta\s+name="theme-color"\s+content="[^"]*"\s*/>', re.I | re.S),
        CANONICAL_TAGS[0],
    ),
    (
        re.compile(
            r'<meta\s+name="apple-mobile-web-app-capable"\s+content="[^"]*"\s*/>',
            re.I | re.S,
        ),
        CANONICAL_TAGS[1],
    ),
    (
        re.compile(
            r'<meta\s+name="apple-mobile-web-app-status-bar-style"\s+content="[^"]*"\s*/>',
            re.I | re.S,
        ),
        CANONICAL_TAGS[2],
    ),
    (
        re.compile(
            r'<meta\s+name="apple-mobile-web-app-title"\s+content="[^"]*"\s*/>',
            re.I | re.S,
        ),
        CANONICAL_TAGS[3],
    ),
    (
        re.compile(
            r'<meta\s+name="mobile-web-app-capable"\s+content="[^"]*"\s*/>', re.I | re.S
        ),
        CANONICAL_TAGS[4],
    ),
    (
        re.compile(
            r'<meta\s+name="application-name"\s+content="[^"]*"\s*/>', re.I | re.S
        ),
        CANONICAL_TAGS[5],
    ),
    (
        re.compile(r'<link\s+rel="manifest"\s+href="[^"]*"\s*/>', re.I | re.S),
        CANONICAL_TAGS[6],
    ),
    (
        re.compile(r'<link\s+rel="apple-touch-icon"\s+href="[^"]*"\s*/>', re.I | re.S),
        CANONICAL_TAGS[7],
    ),
    (
        re.compile(
            r'<link\s+rel="preconnect"\s+href="https://fonts\.googleapis\.com"\s*/>',
            re.I | re.S,
        ),
        CANONICAL_TAGS[8],
    ),
    (
        re.compile(
            r'<link\s+rel="preconnect"\s+href="https://fonts\.gstatic\.com"\s+crossorigin\s*/>',
            re.I | re.S,
        ),
        CANONICAL_TAGS[9],
    ),
    (
        re.compile(
            r'<link\s+rel="preload"\s+href="/assets/branding/logo_principal_hd\.png"\s+as="image"\s*/>',
            re.I | re.S,
        ),
        CANONICAL_TAGS[10],
    ),
    (
        re.compile(
            r'<link\s+rel="preload"\s+href="/app/style\.css"\s+as="style"\s*/>',
            re.I | re.S,
        ),
        CANONICAL_TAGS[11],
    ),
    (
        re.compile(
            r'<link\s+href="https://fonts\.googleapis\.com/css2\?family=Plus\+Jakarta\+Sans:wght@300;400;500;600;700;800&family=Space\+Grotesk:wght@400;500;600;700&family=JetBrains\+Mono:wght@400;500&display=swap"\s+rel="stylesheet"\s*/>',
            re.I | re.S,
        ),
        FONT_LINK,
    ),
    (
        re.compile(
            r'<link\s+rel="stylesheet"\s+href="https://fonts\.googleapis\.com/css2\?family=Plus\+Jakarta\+Sans:wght@300;400;500;600;700;800&family=Space\+Grotesk:wght@400;500;600;700&family=JetBrains\+Mono:wght@400;500&display=swap"\s*/>',
            re.I | re.S,
        ),
        FONT_LINK,
    ),
]

EXACT_DEDUP_KEYS = {
    tag.format(
        description=DEFAULT_DESCRIPTION,
        keywords=DEFAULT_KEYWORDS,
        canonical=DEFAULT_CANONICAL,
        og_title=DEFAULT_OG_TITLE,
        og_description=DEFAULT_OG_DESCRIPTION,
        twitter_title=DEFAULT_TWITTER_TITLE,
        twitter_description=DEFAULT_TWITTER_DESCRIPTION,
    )
    for tag in CANONICAL_TAGS
}

INDEX_DUPLICATE_BLOCK = """                        <button
                            class="lang-item"
                            type="button"
                            data-lang="am"
                            data-lang-button
                        >
                            Amharic
                        </button>
"""


def normalize_head(text: str, file_name: str) -> str:
    head_match = re.search(r"(<head[^>]*>)(.*?)(</head>)", text, flags=re.I | re.S)
    if not head_match:
        return text

    head_open, head_content, head_close = head_match.groups()
    body = head_content

    # Normalise le viewport et le title pour satisfaire les contrôles PWA/SEO stricts.
    viewport_tag = '<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover" />'
    if re.search(r'<meta\s+name="viewport"[^>]*>', body, flags=re.I | re.S):
        body = re.sub(r'<meta\s+name="viewport"[^>]*>', viewport_tag, body, count=1, flags=re.I | re.S)
    else:
        body = viewport_tag + "\n" + body

    title_tag = '<title>FeedFormula AI — Nutrition Animale IA | Bénin</title>'
    if re.search(r'<title>.*?</title>', body, flags=re.I | re.S):
        body = re.sub(r'<title>.*?</title>', title_tag, body, count=1, flags=re.I | re.S)
    else:
        body = title_tag + "\n" + body

    # Supprime les doublons exacts des tags normalisés
    for pattern, replacement in REPLACEMENTS:
        body = pattern.sub(replacement, body)

    # Ajoute les métadonnées manquantes à la fin du head sans écraser les valeurs spécifiques.
    additions = []
    if 'name="theme-color"' not in body.lower():
        additions.append(CANONICAL_TAGS[0])
    if 'name="apple-mobile-web-app-capable"' not in body.lower():
        additions.append(CANONICAL_TAGS[1])
    if 'name="apple-mobile-web-app-status-bar-style"' not in body.lower():
        additions.append(CANONICAL_TAGS[2])
    if 'name="apple-mobile-web-app-title"' not in body.lower():
        additions.append(CANONICAL_TAGS[3])
    if 'name="mobile-web-app-capable"' not in body.lower():
        additions.append(CANONICAL_TAGS[4])
    if 'name="application-name"' not in body.lower():
        additions.append(CANONICAL_TAGS[5])
    if 'rel="manifest"' not in body.lower():
        additions.append(CANONICAL_TAGS[6])
    if 'rel="apple-touch-icon"' not in body.lower():
        additions.append(CANONICAL_TAGS[7])
    if "fonts.googleapis.com" not in body.lower():
        additions.extend([CANONICAL_TAGS[8], CANONICAL_TAGS[9], FONT_LINK])
    if (
        'rel="preload" href="/assets/branding/logo_principal_hd.png" as="image"'
        not in body.lower()
    ):
        additions.append(CANONICAL_TAGS[10])
    if 'rel="preload" href="/app/style.css" as="style"' not in body.lower():
        additions.append(CANONICAL_TAGS[11])
    if 'name="description"' not in body.lower():
        additions.append(CANONICAL_TAGS[13].format(description=DEFAULT_DESCRIPTION))
    if 'name="keywords"' not in body.lower():
        additions.append(CANONICAL_TAGS[14].format(keywords=DEFAULT_KEYWORDS))
    if 'name="author"' not in body.lower():
        additions.append(CANONICAL_TAGS[15])
    if 'name="robots"' not in body.lower():
        additions.append(CANONICAL_TAGS[16])
    if 'rel="canonical"' not in body.lower():
        additions.append(CANONICAL_TAGS[17].format(canonical=DEFAULT_CANONICAL))
    if 'property="og:type"' not in body.lower():
        additions.append(CANONICAL_TAGS[18])
    if 'property="og:url"' not in body.lower():
        additions.append(CANONICAL_TAGS[19])
    if 'property="og:title"' not in body.lower():
        additions.append(CANONICAL_TAGS[20].format(og_title=DEFAULT_OG_TITLE))
    if 'property="og:description"' not in body.lower():
        additions.append(
            CANONICAL_TAGS[21].format(og_description=DEFAULT_OG_DESCRIPTION)
        )
    if 'property="og:image"' not in body.lower():
        additions.append(CANONICAL_TAGS[22])
    if 'property="og:image:width"' not in body.lower():
        additions.append(CANONICAL_TAGS[23])
    if 'property="og:image:height"' not in body.lower():
        additions.append(CANONICAL_TAGS[24])
    if 'property="og:locale"' not in body.lower():
        additions.append(CANONICAL_TAGS[25])
    if 'property="og:site_name"' not in body.lower():
        additions.append(CANONICAL_TAGS[26])
    if 'name="twitter:card"' not in body.lower():
        additions.append(CANONICAL_TAGS[27])
    if 'name="twitter:title"' not in body.lower():
        additions.append(CANONICAL_TAGS[28].format(twitter_title=DEFAULT_TWITTER_TITLE))
    if 'name="twitter:description"' not in body.lower():
        additions.append(
            CANONICAL_TAGS[29].format(twitter_description=DEFAULT_TWITTER_DESCRIPTION)
        )
    if 'name="twitter:image"' not in body.lower():
        additions.append(CANONICAL_TAGS[30])

    if additions:
        body = body.rstrip() + "\n" + "\n".join(additions) + "\n"

    # Dédoublonnage léger des lignes exactes normalisées.
    seen = set()
    normalized_lines = []
    for line in body.splitlines():
        key = line.strip()
        if key in seen and key in EXACT_DEDUP_KEYS:
            continue
        if key in EXACT_DEDUP_KEYS:
            seen.add(key)
        normalized_lines.append(line)

    body = re.sub(r"\n{3,}", "\n\n", "\n".join(normalized_lines))

    # Nettoyage spécifique de l’index : un seul bouton Amharic en liste complète.
    if file_name == "index.html":
        body = body.replace(INDEX_DUPLICATE_BLOCK, "", 1)

    return (
        text[: head_match.start()]
        + head_open
        + body
        + head_close
        + text[head_match.end() :]
    )


def main() -> None:
    changed = []
    for path in sorted(ROOT.glob("*.html")):
        original = path.read_text(encoding="utf-8")
        updated = normalize_head(original, path.name)
        if updated != original:
            path.write_text(updated, encoding="utf-8")
            changed.append(path.name)

    if changed:
        print("Updated:")
        for item in changed:
            print(f"- {item}")
    else:
        print("No HTML changes needed.")


if __name__ == "__main__":
    main()
