"""Sessão de navegador: Chromium via Playwright, perfis desktop/mobile."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import Config

log = logging.getLogger(__name__)

DESKTOP_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
MOBILE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1"
)


@dataclass(frozen=True)
class Device:
    name: str
    user_agent: str
    viewport: dict[str, int] = field(default_factory=lambda: {"width": 1366, "height": 768})
    is_mobile: bool = False
    has_touch: bool = False
    device_scale_factor: float = 1.0


DESKTOP = Device("desktop", DESKTOP_UA)
MOBILE = Device("mobile", MOBILE_UA, {"width": 390, "height": 844}, True, True, 3.0)

DEVICES = {"pc": DESKTOP, "desktop": DESKTOP, "mobile": MOBILE, "celular": MOBILE}


def device_by_name(name: str) -> Device:
    try:
        return DEVICES[name.lower()]
    except KeyError as exc:
        raise ValueError(f"Dispositivo desconhecido: {name!r} (use 'pc' ou 'mobile').") from exc


class Session:
    """Encapsula Playwright; abre contextos que compartilham a sessão salva."""

    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self._playwright: Any = None
        self._browser: Any = None

    # -- ciclo de vida -----------------------------------------------------
    def __enter__(self) -> Session:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:  # pragma: no cover - depende do ambiente
            raise RuntimeError(
                "Playwright não instalado. Rode: pip install -e . && playwright install chromium"
            ) from exc

        self._playwright = sync_playwright().start()
        launch_kwargs: dict[str, Any] = {
            "headless": self.cfg.browser.headless,
            "slow_mo": self.cfg.browser.slow_mo_ms,
            "args": ["--disable-blink-features=AutomationControlled"],
        }
        if self.cfg.browser.channel:
            launch_kwargs["channel"] = self.cfg.browser.channel
        try:
            self._browser = self._playwright.chromium.launch(**launch_kwargs)
        except Exception:
            self._playwright.stop()
            raise
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        if self._browser is not None:
            try:
                self._browser.close()
            except Exception:  # pragma: no cover
                log.debug("Falha ao fechar navegador", exc_info=True)
            self._browser = None
        if self._playwright is not None:
            try:
                self._playwright.stop()
            except Exception:  # pragma: no cover
                log.debug("Falha ao encerrar Playwright", exc_info=True)
            self._playwright = None

    # -- contextos ---------------------------------------------------------
    @property
    def storage_state_path(self) -> Path:
        return Path(self.cfg.browser.storage_state)

    def has_saved_session(self) -> bool:
        path = self.storage_state_path
        return path.exists() and path.stat().st_size > 0

    def new_context(self, device: Device = DESKTOP, *, load_state: bool = True) -> Any:
        if self._browser is None:
            raise RuntimeError("Session não iniciada; use `with Session(cfg) as s:`.")
        state = None
        if load_state and self.has_saved_session():
            state = str(self.storage_state_path)
        ctx = self._browser.new_context(
            user_agent=device.user_agent,
            viewport=device.viewport,
            locale=self.cfg.account.locale,
            timezone_id=self.cfg.account.timezone,
            is_mobile=device.is_mobile,
            has_touch=device.has_touch,
            device_scale_factor=device.device_scale_factor,
            storage_state=state,
            extra_http_headers={
                "Accept-Language": f"{self.cfg.account.locale},pt;q=0.9,en;q=0.8",
            },
        )
        ctx.set_default_timeout(self.cfg.browser.timeout_ms)
        ctx.set_default_navigation_timeout(self.cfg.browser.timeout_ms)
        return ctx

    def save_state(self, context: Any) -> Path:
        path = self.storage_state_path
        path.parent.mkdir(parents=True, exist_ok=True)
        state = context.storage_state()
        path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        try:
            os.chmod(path, 0o600)
        except OSError:  # pragma: no cover - Windows/FS sem suporte
            log.debug("Não foi possível ajustar permissões de %s", path)
        log.info("Sessão salva em %s", path)
        return path
