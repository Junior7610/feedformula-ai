#!/usr/bin/env python3
"""Minifie frontend/style.css et frontend/script.js."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"


def minify_css(source: str) -> str:
    source = re.sub(r"/\*.*?\*/", "", source, flags=re.S)
    source = re.sub(r"\s+", " ", source)
    source = re.sub(r"\s*([{}:;,>])\s*", r"\1", source)
    source = re.sub(r";}", "}", source)
    return source.strip()


def minify_js(source: str) -> str:
    source = re.sub(r"/\*.*?\*/", "", source, flags=re.S)
    source = re.sub(r"//.*?$", "", source, flags=re.M)
    source = re.sub(r"\s+", " ", source)
    source = re.sub(r"\s*([{}:;,=+\-*/()<>])\s*", r"\1", source)
    return source.strip()


def main() -> None:
    css_path = FRONTEND / "style.css"
    js_path = FRONTEND / "script.js"
    style_min = FRONTEND / "style.min.css"
    script_min = FRONTEND / "script.min.js"

    if css_path.exists():
        style_min.write_text(
            minify_css(css_path.read_text(encoding="utf-8")), encoding="utf-8"
        )
    if js_path.exists():
        script_min.write_text(
            minify_js(js_path.read_text(encoding="utf-8")), encoding="utf-8"
        )


if __name__ == "__main__":
    main()
