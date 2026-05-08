#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / 'frontend'

VIEWPORT_RE = re.compile(r'<meta\s+name="viewport"[^>]*>', re.I)
THEME_RE = re.compile(r'<meta\s+name="theme-color"[^>]*>', re.I)
TITLE_RE = re.compile(r'<title>.*?</title>', re.I | re.S)
PRECONNECT_BLOCK = '''        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
        <link rel="preload" href="/assets/branding/logo_principal_hd.png" as="image" />
        <link rel="preload" href="/app/style.css" as="style" />
'''

META_BLOCK = '''<meta charset="UTF-8" />
        <meta
            name="viewport"
            content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover"
        />
        <meta name="theme-color" content="#1B5E20" />
        <meta
            name="apple-mobile-web-app-capable"
            content="yes"
        />
        <meta
            name="apple-mobile-web-app-status-bar-style"
            content="black-translucent"
        />
        <meta
            name="apple-mobile-web-app-title"
            content="FeedFormula AI"
        />
        <meta name="mobile-web-app-capable" content="yes" />
        <meta name="application-name" content="FeedFormula AI" />
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
        <link rel="preload" href="/assets/branding/logo_principal_hd.png" as="image" />
        <link rel="preload" href="/app/style.css" as="style" />
        <link rel="manifest" href="/app/manifest.json" />
        <link
            rel="apple-touch-icon"
            href="/assets/branding/logo_principal_hd.png"
        />'''


def update_html(text: str) -> str:
    text = VIEWPORT_RE.sub(
        '<meta\n            name="viewport"\n            content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover"\n        />',
        text,
        count=1,
    )

    if 'apple-mobile-web-app-capable' not in text:
        theme_match = THEME_RE.search(text)
        if theme_match:
            insert_at = theme_match.end()
            text = text[:insert_at] + '\n        <meta\n            name="apple-mobile-web-app-capable"\n            content="yes"\n        />\n        <meta\n            name="apple-mobile-web-app-status-bar-style"\n            content="black-translucent"\n        />\n        <meta\n            name="apple-mobile-web-app-title"\n            content="FeedFormula AI"\n        />\n        <meta name="mobile-web-app-capable" content="yes" />\n        <meta name="application-name" content="FeedFormula AI" />\n        <link rel="manifest" href="/app/manifest.json" />\n        <link\n            rel="apple-touch-icon"\n            href="/assets/branding/logo_principal_hd.png"\n        />' + text[insert_at:]
        else:
            title_match = TITLE_RE.search(text)
            if title_match:
                insert_at = title_match.end()
                text = text[:insert_at] + '\n        <meta\n            name="apple-mobile-web-app-capable"\n            content="yes"\n        />\n        <meta\n            name="apple-mobile-web-app-status-bar-style"\n            content="black-translucent"\n        />\n        <meta\n            name="apple-mobile-web-app-title"\n            content="FeedFormula AI"\n        />\n        <meta name="mobile-web-app-capable" content="yes" />\n        <meta name="application-name" content="FeedFormula AI" />\n        <link rel="manifest" href="/app/manifest.json" />\n        <link\n            rel="apple-touch-icon"\n            href="/assets/branding/logo_principal_hd.png"\n        />' + text[insert_at:]

    return text


def main() -> None:
    for path in sorted(FRONTEND.glob('*.html')):
        text = path.read_text(encoding='utf-8')
        updated = update_html(text)
        if updated != text:
            path.write_text(updated, encoding='utf-8')


if __name__ == '__main__':
    main()
