from __future__ import annotations

import pytest

from conquistas import __version__
from conquistas.cli import build_parser, main


def test_version_flag(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_help_flag(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "login" in out and "doctor" in out


def test_parser_requires_subcommand():
    with pytest.raises(SystemExit):
        build_parser().parse_args([])


def test_invalid_config_returns_2(tmp_path, capsys):
    bad = tmp_path / "bad.toml"
    bad.write_text("[searches]\npc = 999\n", encoding="utf-8")
    assert main(["-c", str(bad), "status"]) == 2
    assert "erro de configuração" in capsys.readouterr().err


def test_status_without_data(tmp_path, capsys):
    cfg = tmp_path / "ok.toml"
    cfg.write_text(
        f'[storage]\ndatabase = "{(tmp_path / "db.sqlite3").as_posix()}"\n'
        f'[logging]\nfile = "{(tmp_path / "log.txt").as_posix()}"\n',
        encoding="utf-8",
    )
    assert main(["-c", str(cfg), "status"]) == 0
    assert "situação atual" in capsys.readouterr().out


def test_dry_run_searches_without_browser(tmp_path, capsys):
    cfg = tmp_path / "ok.toml"
    cfg.write_text(
        f'[storage]\ndatabase = "{(tmp_path / "db.sqlite3").as_posix()}"\n'
        f'[logging]\nfile = "{(tmp_path / "log.txt").as_posix()}"\n',
        encoding="utf-8",
    )
    code = main(
        [
            "-c",
            str(cfg),
            "run",
            "--dry-run",
            "--only",
            "searches",
            "--pc",
            "3",
            "--mobile",
            "0",
            "--seed",
            "1",
        ]
    )
    assert code == 0
    out = capsys.readouterr().out
    assert "[pc 01/03]" in out
    assert "mobile" not in out
