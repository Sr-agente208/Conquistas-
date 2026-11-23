"""Utilitários pequenos e sem dependências externas."""

from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import quote_plus

_POINTS_RE = re.compile(r"\d{1,3}(?:[.,\u00a0\s]\d{3})+|\d+")


def parse_points(text: str | None) -> int | None:
    """Extrai um valor inteiro de pontos, tolerando separadores pt-BR e en-US.

    >>> parse_points("1.234")
    1234
    >>> parse_points("12,345 pontos")
    12345
    >>> parse_points("sem número")
    """
    if not text:
        return None
    match = _POINTS_RE.search(text)
    if match is None:
        return None
    digits = re.sub(r"\D", "", match.group(0))
    return int(digits) if digits else None


def format_points(value: int | None) -> str:
    """Formata pontos no padrão brasileiro (1.234)."""
    if value is None:
        return "—"
    return f"{value:,}".replace(",", ".")


def now_local() -> datetime:
    return datetime.now().astimezone()


def iso_now() -> str:
    return now_local().isoformat(timespec="seconds")


def today_str() -> str:
    return now_local().date().isoformat()


def search_url(query: str, language: str = "pt-BR") -> str:
    lang, _, region = language.replace("_", "-").partition("-")
    market = (region or "BR").upper()
    return (
        f"https://www.bing.com/search?q={quote_plus(query)}"
        f"&setlang={language}&cc={market}&form=QBLH&mkt={lang.lower()}-{market}"
    )
