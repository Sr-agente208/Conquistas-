from __future__ import annotations

from pathlib import Path

import pytest

from conquistas.config import ConfigError, load_config


def test_defaults_when_no_file(tmp_path, monkeypatch):
    monkeypatch.delenv("CONQUISTAS_CONFIG", raising=False)
    monkeypatch.chdir(tmp_path)
    cfg = load_config()
    assert cfg.path is None
    assert cfg.searches.pc == 30
    assert cfg.searches.mobile == 20
    assert cfg.browser.headless is False
    assert cfg.account.locale == "pt-BR"
    assert cfg.storage.database == (tmp_path / "data/conquistas.sqlite3")


def test_loads_values_and_resolves_paths(tmp_path):
    config = tmp_path / "conquistas.toml"
    config.write_text(
        """
[account]
locale = "pt-BR"
timezone = "America/Sao_Paulo"

[browser]
headless = true
channel = "chrome"
storage_state = "sessao/estado.json"

[searches]
pc = 25
mobile = 15
min_delay_s = 2.5
max_delay_s = 5.0

[daily]
enabled = false

[storage]
database = "banco.sqlite3"
""",
        encoding="utf-8",
    )
    cfg = load_config(config)
    assert cfg.browser.headless is True
    assert cfg.browser.channel == "chrome"
    assert cfg.browser.storage_state == (tmp_path / "sessao/estado.json").resolve()
    assert cfg.searches.pc == 25
    assert cfg.daily.enabled is False
    assert cfg.storage.database == (tmp_path / "banco.sqlite3").resolve()


def test_empty_channel_becomes_none(tmp_path):
    config = tmp_path / "c.toml"
    config.write_text('[browser]\nchannel = ""\n', encoding="utf-8")
    assert load_config(config).browser.channel is None


def test_unknown_section(tmp_path):
    config = tmp_path / "c.toml"
    config.write_text("[buscas]\npc = 5\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="desconhecida"):
        load_config(config)


def test_unknown_key(tmp_path):
    config = tmp_path / "c.toml"
    config.write_text("[searches]\npc = 5\nfoo = 1\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="foo"):
        load_config(config)


def test_wrong_type(tmp_path):
    config = tmp_path / "c.toml"
    config.write_text('[browser]\nheadless = "sim"\n', encoding="utf-8")
    with pytest.raises(ConfigError, match="headless"):
        load_config(config)


def test_delay_validation(tmp_path):
    config = tmp_path / "c.toml"
    config.write_text("[searches]\nmin_delay_s = 9.0\nmax_delay_s = 3.0\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="max_delay_s"):
        load_config(config)


def test_invalid_toml(tmp_path):
    config = tmp_path / "c.toml"
    config.write_text("[searches\npc = 3\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="TOML inválido"):
        load_config(config)


def test_missing_file(tmp_path):
    with pytest.raises(ConfigError, match="não encontrado"):
        load_config(tmp_path / "nao-existe.toml")


def test_env_override(tmp_path, monkeypatch):
    monkeypatch.delenv("CONQUISTAS_CONFIG", raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CONQUISTAS_HEADLESS", "true")
    monkeypatch.setenv("CONQUISTAS_DB", "custom/db.sqlite3")
    cfg = load_config()
    assert cfg.browser.headless is True
    assert cfg.storage.database == (tmp_path / "custom/db.sqlite3")


def test_env_config_path(tmp_path, monkeypatch):
    config = Path(tmp_path / "outro.toml")
    config.write_text("[searches]\npc = 7\n", encoding="utf-8")
    monkeypatch.setenv("CONQUISTAS_CONFIG", str(config))
    assert load_config().searches.pc == 7
