"""Leitura e validação da configuração TOML."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any, get_type_hints

ENV_CONFIG = "CONQUISTAS_CONFIG"
DEFAULT_CONFIG_NAME = "conquistas.toml"

_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


class ConfigError(ValueError):
    """Configuração inválida ou ilegível."""


@dataclass(frozen=True)
class AccountConfig:
    locale: str = "pt-BR"
    timezone: str = "America/Sao_Paulo"


@dataclass(frozen=True)
class BrowserConfig:
    headless: bool = False
    slow_mo_ms: int = 0
    channel: str | None = None
    timeout_ms: int = 45_000
    storage_state: Path = Path("data/session/storage_state.json")


@dataclass(frozen=True)
class SearchConfig:
    enabled: bool = True
    pc: int = 30
    mobile: int = 20
    min_delay_s: float = 4.0
    max_delay_s: float = 9.0
    check_every: int = 5
    max_stalled_checks: int = 3
    human_typing: bool = True
    query_language: str = "pt-BR"


@dataclass(frozen=True)
class DailyConfig:
    enabled: bool = True
    max_cards: int = 12
    max_steps_per_card: int = 15
    per_card_timeout_s: float = 25.0


@dataclass(frozen=True)
class StorageConfig:
    database: Path = Path("data/conquistas.sqlite3")


@dataclass(frozen=True)
class LoggingConfig:
    level: str = "INFO"
    file: Path = Path("data/logs/conquistas.log")


@dataclass(frozen=True)
class Config:
    base_dir: Path = field(default_factory=Path.cwd)
    path: Path | None = None
    account: AccountConfig = field(default_factory=AccountConfig)
    browser: BrowserConfig = field(default_factory=BrowserConfig)
    searches: SearchConfig = field(default_factory=SearchConfig)
    daily: DailyConfig = field(default_factory=DailyConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)


_SECTIONS = {
    "account": AccountConfig,
    "browser": BrowserConfig,
    "searches": SearchConfig,
    "daily": DailyConfig,
    "storage": StorageConfig,
    "logging": LoggingConfig,
}


def _build_section(section: str, data: Any, base_dir: Path) -> Any:
    cls = _SECTIONS[section]
    if not isinstance(data, dict):
        raise ConfigError(f"[{section}] deve ser uma tabela TOML, recebido {type(data).__name__}.")

    known = {f.name: f for f in fields(cls)}
    unknown = sorted(set(data) - set(known))
    if unknown:
        raise ConfigError(
            f"Chave(s) desconhecida(s) em [{section}]: {', '.join(unknown)}. "
            f"Chaves válidas: {', '.join(sorted(known))}."
        )

    hints = get_type_hints(cls)
    values: dict[str, Any] = {}
    for name, raw in data.items():
        target = hints[name]
        try:
            if target in (int, float) and isinstance(raw, bool):
                raise ConfigError(f"[{section}].{name} espera número, não booleano.")
            if target is bool:
                if not isinstance(raw, bool):
                    raise ConfigError(f"[{section}].{name} espera true/false.")
                values[name] = raw
            elif target is int:
                values[name] = int(raw)
            elif target is float:
                values[name] = float(raw)
            elif target is str:
                values[name] = str(raw)
            elif target == (str | None) or str(target).endswith("| None"):
                values[name] = None if raw in (None, "") else str(raw)
            elif target is Path:
                values[name] = _resolve_path(base_dir, str(raw))
            else:  # pragma: no cover - proteção contra novos campos
                values[name] = raw
        except (TypeError, ValueError) as exc:
            raise ConfigError(f"Valor inválido em [{section}].{name}: {raw!r} ({exc}).") from exc
    return cls(**values)


def _resolve_path(base_dir: Path, raw: str) -> Path:
    path = Path(raw).expanduser()
    return path if path.is_absolute() else (base_dir / path).resolve()


def _defaults(base_dir: Path) -> Config:
    cfg = Config(base_dir=base_dir)
    return Config(
        base_dir=base_dir,
        path=None,
        account=cfg.account,
        browser=BrowserConfig(
            storage_state=_resolve_path(base_dir, str(cfg.browser.storage_state))
        ),
        searches=cfg.searches,
        daily=cfg.daily,
        storage=StorageConfig(database=_resolve_path(base_dir, str(cfg.storage.database))),
        logging=LoggingConfig(file=_resolve_path(base_dir, str(cfg.logging.file))),
    )


def _discover(explicit: str | os.PathLike[str] | None) -> Path | None:
    if explicit:
        return Path(explicit).expanduser().resolve()
    if env := os.environ.get(ENV_CONFIG):
        return Path(env).expanduser().resolve()
    candidate = Path.cwd() / DEFAULT_CONFIG_NAME
    return candidate.resolve() if candidate.exists() else None


def load_config(path: str | os.PathLike[str] | None = None) -> Config:
    """Carrega a configuração, aplicando padrões para o que não for informado."""
    config_path = _discover(path)
    if config_path is None:
        return _apply_env(_defaults(Path.cwd()))

    if not config_path.exists():
        raise ConfigError(f"Arquivo de configuração não encontrado: {config_path}")
    try:
        raw = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"TOML inválido em {config_path}: {exc}") from exc

    base_dir = config_path.parent
    defaults = _defaults(base_dir)

    unknown = sorted(set(raw) - set(_SECTIONS))
    if unknown:
        raise ConfigError(
            f"Seção(ões) desconhecida(s): {', '.join(unknown)}. "
            f"Seções válidas: {', '.join(sorted(_SECTIONS))}."
        )

    sections = {
        name: _build_section(name, raw[name], base_dir) if name in raw else getattr(defaults, name)
        for name in _SECTIONS
    }
    cfg = Config(base_dir=base_dir, path=config_path, **sections)
    _validate(cfg)
    return _apply_env(cfg)


def _apply_env(cfg: Config) -> Config:
    """Pequenos atalhos por variável de ambiente, úteis em CI/cron."""
    headless = os.environ.get("CONQUISTAS_HEADLESS")
    state = os.environ.get("CONQUISTAS_STORAGE_STATE")
    db = os.environ.get("CONQUISTAS_DB")
    if headless is None and state is None and db is None:
        return cfg
    return Config(
        base_dir=cfg.base_dir,
        path=cfg.path,
        account=cfg.account,
        browser=BrowserConfig(
            **{
                **cfg.browser.__dict__,
                "headless": cfg.browser.headless
                if headless is None
                else headless.strip().lower() in {"1", "true", "yes", "on"},
                "storage_state": cfg.browser.storage_state
                if state is None
                else _resolve_path(cfg.base_dir, state),
            }
        ),
        searches=cfg.searches,
        daily=cfg.daily,
        storage=StorageConfig(
            database=cfg.storage.database if db is None else _resolve_path(cfg.base_dir, db)
        ),
        logging=cfg.logging,
    )


def _validate(cfg: Config) -> None:
    s = cfg.searches
    if not 0 <= s.pc <= 100:
        raise ConfigError("[searches].pc deve estar entre 0 e 100.")
    if not 0 <= s.mobile <= 100:
        raise ConfigError("[searches].mobile deve estar entre 0 e 100.")
    if s.min_delay_s < 1.0:
        raise ConfigError("[searches].min_delay_s deve ser >= 1.0 (evite rajadas).")
    if s.max_delay_s < s.min_delay_s:
        raise ConfigError("[searches].max_delay_s deve ser >= min_delay_s.")
    if s.check_every < 1:
        raise ConfigError("[searches].check_every deve ser >= 1.")
    if s.max_stalled_checks < 1:
        raise ConfigError("[searches].max_stalled_checks deve ser >= 1.")
    if cfg.daily.max_cards < 0 or cfg.daily.max_steps_per_card < 1:
        raise ConfigError("[daily] valores inválidos (max_cards >= 0, max_steps_per_card >= 1).")
    if cfg.logging.level.upper() not in _LOG_LEVELS:
        raise ConfigError(f"[logging].level inválido: {cfg.logging.level}.")
    if cfg.browser.timeout_ms < 5_000:
        raise ConfigError("[browser].timeout_ms deve ser >= 5000.")
