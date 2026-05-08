#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"

FONT_LINK = (
    '<link href="https://fonts.googleapis.com/css2?'
    'family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&'
    'family=Space+Grotesk:wght@400;500;600;700&'
    'family=JetBrains+Mono:wght@400;500&display=swap" '
    'rel="stylesheet" />'
)
STYLE_LINK = '<link rel="stylesheet" href="style.css" />'

STYLE_REPLACEMENTS = {
    'font-family: var(--font-base);': 'font-family: var(--font-primary);',
    'font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;': 'font-family: var(--font-primary);',
    'font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;': 'font-family: var(--font-primary);',
}

NEW_ROOT = """:root {
    /* Polices */
    --font-primary: 'Plus Jakarta Sans', sans-serif;
    --font-display: 'Space Grotesk', sans-serif;
    --font-mono: 'JetBrains Mono', monospace;

    /* Échelle typographique */
    --text-xs: 0.75rem;
    --text-sm: 0.875rem;
    --text-base: 1rem;
    --text-lg: 1.125rem;
    --text-xl: 1.25rem;
    --text-2xl: 1.5rem;
    --text-3xl: 1.875rem;
    --text-4xl: 2.25rem;
    --text-5xl: 3rem;

    /* Graisses */
    --font-light: 300;
    --font-regular: 400;
    --font-medium: 500;
    --font-semibold: 600;
    --font-bold: 700;
    --font-extrabold: 800;

    /* Interlignes */
    --leading-tight: 1.25;
    --leading-normal: 1.5;
    --leading-relaxed: 1.75;

    /* Espacement lettres */
    --tracking-tight: -0.025em;
    --tracking-normal: 0em;
    --tracking-wide: 0.025em;
    --tracking-wider: 0.05em;
    --tracking-widest: 0.1em;

    /* Verts principaux */
    --green-950: #052e16;
    --green-900: #14532d;
    --green-800: #166534;
    --green-700: #15803d;
    --green-600: #16a34a;
    --green-500: #22c55e;
    --green-400: #4ade80;
    --green-100: #dcfce7;
    --green-50: #f0fdf4;

    /* Or principaux */
    --gold-900: #713f12;
    --gold-700: #a16207;
    --gold-500: #eab308;
    --gold-400: #facc15;
    --gold-300: #fde047;
    --gold-100: #fef9c3;
    --gold-50: #fefce8;

    /* Brand colors */
    --brand-primary: #1B5E20;
    --brand-secondary: #2E7D32;
    --brand-accent: #F9A825;
    --brand-accent-dark: #F57F17;

    /* Neutres */
    --gray-950: #030712;
    --gray-900: #111827;
    --gray-800: #1f2937;
    --gray-700: #374151;
    --gray-600: #4b5563;
    --gray-500: #6b7280;
    --gray-400: #9ca3af;
    --gray-300: #d1d5db;
    --gray-200: #e5e7eb;
    --gray-100: #f3f4f6;
    --gray-50: #f9fafb;

    /* Sémantiques */
    --color-success: #16a34a;
    --color-warning: #d97706;
    --color-error: #dc2626;
    --color-info: #2563eb;

    /* Surfaces */
    --surface-primary: #ffffff;
    --surface-secondary: #f9fafb;
    --surface-tertiary: #f3f4f6;
    --surface-inverse: #1B5E20;

    /* Textes */
    --text-primary: #111827;
    --text-secondary: #4b5563;
    --text-tertiary: #9ca3af;
    --text-inverse: #ffffff;
    --text-brand: #1B5E20;
    --text-accent: #F9A825;

    /* Alias historiques conservés */
    --color-green: var(--brand-primary);
    --color-green-dark: #15461a;
    --color-green-soft: #e8f5e9;
    --color-green-soft-2: #dff2e1;
    --color-gold: #f9a825;
    --color-gold-soft: #fff4cc;
    --color-gold-soft-2: #fff9e6;
    --color-white: #ffffff;
    --color-danger: #e53935;
    --color-danger-soft: #ffebee;
    --color-danger-dark: #c62828;
    --color-academy: #0d47a1;
    --color-academy-soft: #eaf2ff;
    --color-repro: #c2185b;
    --color-repro-soft: #fce4ec;
    --color-text: var(--text-primary);
    --color-text-muted: rgba(17, 24, 39, 0.72);
    --color-text-inverse: #ffffff;
    --color-border: rgba(27, 94, 32, 0.14);
    --color-border-strong: rgba(27, 94, 32, 0.22);
    --color-shadow: rgba(27, 94, 32, 0.12);
    --color-shadow-strong: rgba(27, 94, 32, 0.22);
    --color-overlay: rgba(11, 29, 13, 0.55);

    /* Rayons */
    --radius-sm: 0.375rem;
    --radius-md: 0.5rem;
    --radius-lg: 0.75rem;
    --radius-xl: 1rem;
    --radius-2xl: 1.5rem;
    --radius-full: 9999px;
    --radius-xs: var(--radius-sm);
    --radius-round: var(--radius-full);

    /* Espacements */
    --space-1: 0.25rem;
    --space-2: 0.5rem;
    --space-3: 0.75rem;
    --space-4: 1rem;
    --space-5: 1.25rem;
    --space-6: 1.5rem;
    --space-8: 2rem;
    --space-10: 2.5rem;
    --space-12: 3rem;
    --space-16: 4rem;
    --space-20: 5rem;
    --space-7: 1.75rem;

    /* Tailles minimales */
    --touch-min: 48px;
    --header-height: 72px;
    --bottom-nav-height: 76px;
    --container-max: 1120px;

    /* Ombres */
    --shadow-sm: 0 1px 2px 0 rgb(0 0 0 / 0.05);
    --shadow-md: 0 4px 6px -1px rgb(0 0 0 / 0.1);
    --shadow-lg: 0 10px 15px -3px rgb(0 0 0 / 0.1);
    --shadow-xl: 0 20px 25px -5px rgb(0 0 0 / 0.1);
    --shadow-brand: 0 4px 14px 0 rgb(27 94 32 / 0.3);
    --shadow-gold: 0 4px 14px 0 rgb(249 168 37 / 0.3);
    --shadow-soft: 0 10px 30px var(--color-shadow);
    --shadow-medium: 0 14px 38px var(--color-shadow-strong);
    --shadow-card: 0 8px 24px rgba(27, 94, 32, 0.1);

    /* Animations */
    --transition-fast: 160ms ease;
    --transition-base: 240ms ease;
    --transition-slow: 360ms ease;

    /* Z-index */
    --z-splash: 9999;
    --z-header: 300;
    --z-bottom-nav: 280;
    --z-aya: 260;
    --z-modal: 1200;
}
"""

NEW_BODY = """body {
    margin: 0;
    min-height: 100vh;
    font-family: var(--font-primary);
    color: var(--text-primary);
    background:
        radial-gradient(
            circle at top,
            rgba(249, 168, 37, 0.1),
            transparent 30%
        ),
        linear-gradient(180deg, #fbfffb 0%, #f6fbf6 45%, #eef7ef 100%);
    font-size: var(--text-base);
    line-height: var(--leading-relaxed);
    -webkit-font-smoothing: antialiased;
    text-rendering: optimizeLegibility;
}
"""

NEW_TYPO = """h1 {
    font-family: var(--font-display);
    font-size: var(--text-4xl);
    font-weight: var(--font-bold);
    letter-spacing: var(--tracking-tight);
    line-height: var(--leading-tight);
}

h2 {
    font-family: var(--font-display);
    font-size: var(--text-3xl);
    font-weight: var(--font-semibold);
    line-height: var(--leading-tight);
}

h3 {
    font-family: var(--font-primary);
    font-size: var(--text-xl);
    font-weight: var(--font-semibold);
    line-height: var(--leading-normal);
}

p,
body {
    font-family: var(--font-primary);
    font-size: var(--text-base);
    font-weight: var(--font-regular);
    line-height: var(--leading-relaxed);
}

.mono,
code,
.ration-text {
    font-family: var(--font-mono);
    font-size: var(--text-sm);
}

.label {
    font-size: var(--text-xs);
    font-weight: var(--font-semibold);
    letter-spacing: var(--tracking-widest);
    text-transform: uppercase;
}
"""

ROOT_ROOT_RE = re.compile(
    r'^:root\s*\{.*?^\}\n\n/\* =========================================================\n   Base\n   ========================================================= \*/',
    re.S | re.M,
)

TYPO_INSERT_RE = re.compile(r'\}\n\nimg,\nsvg,\ncanvas \{', re.M)


def inject_fonts_and_styles(html: str) -> str:
    if FONT_LINK not in html:
        stylesheet_positions = list(re.finditer(r'<link\s+rel="stylesheet"[^>]*>', html, re.I))
        if stylesheet_positions:
            first = stylesheet_positions[0]
            html = html[:first.start()] + FONT_LINK + '\n        ' + html[first.start():]
        else:
            title_match = re.search(r'</title>\s*', html, re.I)
            if title_match:
                html = html[:title_match.end()] + '\n        ' + FONT_LINK + html[title_match.end():]
            else:
                html = FONT_LINK + '\n' + html

    if STYLE_LINK not in html:
        style_min_match = re.search(r'<link\s+rel="stylesheet"\s+href="style\.min\.css"\s*/?>', html, re.I)
        if style_min_match:
            html = html[:style_min_match.start()] + STYLE_LINK + html[style_min_match.end():]
        else:
            stylesheet_positions = list(re.finditer(r'<link\s+rel="stylesheet"[^>]*>', html, re.I))
            if stylesheet_positions:
                last = stylesheet_positions[-1]
                html = html[:last.end()] + '\n        ' + STYLE_LINK + html[last.end():]
            else:
                title_match = re.search(r'</title>\s*', html, re.I)
                if title_match:
                    html = html[:title_match.end()] + '\n        ' + STYLE_LINK + html[title_match.end():]
                else:
                    html = STYLE_LINK + '\n' + html

    html = html.replace('font-family: Arial, sans-serif;', 'font-family: var(--font-primary);')
    html = html.replace('font-family: system-ui,-apple-system,Segoe UI,Roboto,sans-serif;', 'font-family: var(--font-primary);')
    html = html.replace('font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif;', 'font-family: var(--font-primary);')
    html = html.replace('font-family:\n                    system-ui,\n                    -apple-system,\n                    Segoe UI,\n                    Roboto,\n                    sans-serif;', 'font-family: var(--font-primary);')
    html = html.replace('font-family:\n                    system-ui,\n                    -apple-system,\n                    BlinkMacSystemFont,\n                    "Segoe UI",\n                    sans-serif;', 'font-family: var(--font-primary);')
    html = html.replace('font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;', 'font-family: var(--font-primary);')
    return html


def main() -> None:
    style_path = FRONTEND / 'style.css'
    style_text = style_path.read_text(encoding='utf-8')
    style_text = ROOT_ROOT_RE.sub(NEW_ROOT + '\n\n/* =========================================================\n   Base\n   ========================================================= */', style_text, count=1)
    if 'h1 {' not in style_text or '.label {' not in style_text:
        style_text = TYPO_INSERT_RE.sub('}\n\n' + NEW_TYPO + 'img,\nsvg,\ncanvas {', style_text, count=1)
    else:
        # Insert typography block just after the body block if it is missing.
        if 'font-family: var(--font-display);' not in style_text:
            style_text = TYPO_INSERT_RE.sub('}\n\n' + NEW_TYPO + 'img,\nsvg,\ncanvas {', style_text, count=1)
    if 'font-family: var(--font-primary);' not in style_text.split('img,\nsvg,\ncanvas {', 1)[0]:
        style_text = style_text.replace(NEW_BODY, NEW_BODY, 1)
    style_text = style_text.replace(
        'body {\n    margin: 0;\n    min-height: 100vh;\n    font-family: var(--font-base);\n    color: var(--color-text);',
        NEW_BODY.split('background:', 1)[0].rstrip() + '\n    background:',
        1,
    )
    style_text = style_text.replace('font-family: var(--font-base);', 'font-family: var(--font-primary);')
    style_text = style_text.replace('color: var(--color-text);', 'color: var(--text-primary);')
    style_text = style_text.replace('line-height: 1.5;', 'line-height: var(--leading-relaxed);')
    if 'h1 {' not in style_text:
        style_text = style_text.replace('img,\nsvg,\ncanvas {', NEW_TYPO + '\nimg,\nsvg,\ncanvas {', 1)
    style_path.write_text(style_text, encoding='utf-8')

    for html_path in sorted(FRONTEND.glob('*.html')):
        html = html_path.read_text(encoding='utf-8')
        html = inject_fonts_and_styles(html)
        html_path.write_text(html, encoding='utf-8')

    for sw_name in ('sw.js', 'service_worker.js'):
        sw_path = FRONTEND / sw_name
        if sw_path.exists():
            sw_text = sw_path.read_text(encoding='utf-8')
            sw_text = sw_text.replace('./style.min.css', './style.css')
            sw_text = sw_text.replace('"./style.min.css"', '"./style.css"')
            sw_text = sw_text.replace("'./style.min.css'", "'./style.css'")
            sw_path.write_text(sw_text, encoding='utf-8')

    print('Branding update completed.')


if __name__ == '__main__':
    main()
