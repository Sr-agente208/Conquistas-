#!/usr/bin/env python3
"""Gera uma versão em arquivo único da página (CSS, JS e dados embutidos).

Útil para abrir direto no celular (file://) ou guardar offline, sem servidor e
sem GitHub Pages.

Uso:
    python scripts/build_standalone.py
    # → docs/projetos-offline.html

Rode de novo depois de alterar index.html, styles.css, app.js ou os dados.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
OUTPUT = DOCS / "projetos-offline.html"


def inline(index_html: str, docs: Path) -> str:
    css = (docs / "styles.css").read_text(encoding="utf-8")
    data_js = (docs / "data" / "repos.js").read_text(encoding="utf-8")
    app_js = (docs / "app.js").read_text(encoding="utf-8")

    replacements = [
        ('<link rel="stylesheet" href="styles.css" />', f"<style>\n{css}\n</style>"),
        ('<script src="data/repos.js"></script>', f"<script>\n{data_js}\n</script>"),
        ('<script src="app.js"></script>', f"<script>\n{app_js}\n</script>"),
    ]
    html = index_html
    for old, new in replacements:
        if old not in html:
            raise SystemExit(f"Trecho não encontrado em index.html: {old}")
        html = html.replace(old, new, 1)

    banner = (
        "<!-- Versão em arquivo único, gerada por scripts/build_standalone.py.\n"
        "     Abra este arquivo direto no navegador: não precisa de servidor. -->\n"
    )
    return banner + html


def main() -> int:
    index = DOCS / "index.html"
    if not index.exists():
        print(f"index.html não encontrado em {DOCS}", file=sys.stderr)
        return 1

    html = inline(index.read_text(encoding="utf-8"), DOCS)
    OUTPUT.write_text(html, encoding="utf-8")

    size_kb = OUTPUT.stat().st_size / 1024
    print(f"Gerado {OUTPUT.relative_to(ROOT)} ({size_kb:.0f} KB, tudo embutido)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
