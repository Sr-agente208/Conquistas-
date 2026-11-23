from __future__ import annotations

import pytest

from conquistas.utils import format_points, parse_points, search_url


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("1.234", 1234),
        ("12,345 pontos", 12345),
        ("0", 0),
        ("Saldo: 4321", 4321),
        ("1 234 567", 1234567),
        ("sem número", None),
        ("", None),
        (None, None),
    ],
)
def test_parse_points(text, expected):
    assert parse_points(text) == expected


def test_parse_points_ignores_surrounding_text():
    assert parse_points("Você tem 2.345 pontos disponíveis") == 2345


def test_format_points():
    assert format_points(1234) == "1.234"
    assert format_points(0) == "0"
    assert format_points(None) == "—"


def test_search_url_encodes_query():
    url = search_url("receita de bolo", "pt-BR")
    assert "receita+de+bolo" in url
    assert "setlang=pt-BR" in url
    assert url.startswith("https://www.bing.com/search?q=")
