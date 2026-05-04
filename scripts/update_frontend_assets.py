#!/usr/bin/env python3
"""Met à jour les HTML du frontend vers style.min.css/script.min.js et ajoute lazy loading."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"


def update_html(text: str) -> str:
    text = text.replace('href="style.css"', 'href="style.min.css"')
    text = text.replace("href='style.css'", "href='style.min.css'")
    text = text.replace('src="script.js"', 'src="script.min.js"')
    text = text.replace("src='script.js'", "src='script.min.js'")
    text = text.replace("./sw.js", "./service_worker.js")

    def repl(match: re.Match[str]) -> str:
        tag = match.group(0)
        if "${" in tag:
            return tag
        if "loading=" not in tag:
            tag = tag[:-1] + ' loading="lazy"'
        if "width=" not in tag:
            tag = tag[:-1] + ' width="960"'
        if "height=" not in tag:
            tag = tag[:-1] + ' height="640"'
        return tag

    return re.sub(r"<img\b[^>]*>", repl, text)


def main() -> None:
    for path in FRONTEND.glob("*.html"):
        content = path.read_text(encoding="utf-8")
        updated = update_html(content)
        if updated != content:
            path.write_text(updated, encoding="utf-8")


if __name__ == "__main__":
    main()
