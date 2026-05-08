#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"

SEO_TITLE = "FeedFormula AI — Nutrition Animale IA | Bénin"
SEO_DESCRIPTION = (
    "FeedFormula AI génère la ration parfaite pour vos animaux en 30 secondes. "
    "50 langues africaines. 8 modules IA. Gratuit pour les éleveurs béninois."
)
SEO_KEYWORDS = "élevage bénin, nutrition animale, IA agricole, fon, poulet, vache, ration animale"
SEO_AUTHOR = "Leonel TOGBE"
SEO_CANONICAL = "https://feedformula-ai.vercel.app/app/"
SEO_OG_URL = "https://feedformula-ai.vercel.app"
SEO_OG_TITLE = "FeedFormula AI — L IA au service de l élevage africain"
SEO_OG_DESCRIPTION = (
    "Formulez la ration parfaite de vos animaux en 30 secondes. "
    "En fon, yoruba, français et 47 autres langues africaines."
)
SEO_IMAGE = "https://feedformula-ai.vercel.app/assets/branding/hero_image_accueil.png"

TITLE_RE = re.compile(r"<title>.*?</title>", re.I | re.S)
DESCRIPTION_RE = re.compile(r'<meta\s+name="description"\s+content="[^"]*"\s*/?>', re.I | re.S)
SEO_BLOCK = f'''<meta name="keywords" content="{SEO_KEYWORDS}" />
        <meta name="author" content="{SEO_AUTHOR}" />
        <meta name="robots" content="index, follow" />
        <link rel="canonical" href="{SEO_CANONICAL}" />
        <meta property="og:type" content="website" />
        <meta property="og:url" content="{SEO_OG_URL}" />
        <meta property="og:title" content="{SEO_OG_TITLE}" />
        <meta property="og:description" content="{SEO_OG_DESCRIPTION}" />
        <meta property="og:image" content="{SEO_IMAGE}" />
        <meta property="og:image:width" content="1200" />
        <meta property="og:image:height" content="630" />
        <meta property="og:locale" content="fr_BJ" />
        <meta property="og:site_name" content="FeedFormula AI" />
        <meta name="twitter:card" content="summary_large_image" />
        <meta name="twitter:title" content="FeedFormula AI — Nutrition Animale IA" />
        <meta name="twitter:description" content="L intelligence africaine au service de vos animaux." />
        <meta name="twitter:image" content="{SEO_IMAGE}" />'''


def update_html(text: str) -> str:
    text = TITLE_RE.sub(f"<title>{SEO_TITLE}</title>", text, count=1)

    if DESCRIPTION_RE.search(text):
        text = DESCRIPTION_RE.sub(
            f'<meta name="description" content="{SEO_DESCRIPTION}" />',
            text,
            count=1,
        )
    else:
        title_match = TITLE_RE.search(text)
        if title_match:
            insert_at = title_match.end()
            text = (
                text[:insert_at]
                + f'\n        <meta name="description" content="{SEO_DESCRIPTION}" />'
                + text[insert_at:]
            )

    if 'og:site_name' not in text:
        title_match = TITLE_RE.search(text)
        if title_match:
            insert_at = title_match.end()
            text = text[:insert_at] + "\n        " + SEO_BLOCK + text[insert_at:]

    return text


def main() -> None:
    for path in sorted(FRONTEND.glob("*.html")):
        text = path.read_text(encoding="utf-8")
        updated = update_html(text)
        if updated != text:
            path.write_text(updated, encoding="utf-8")


if __name__ == "__main__":
    main()
