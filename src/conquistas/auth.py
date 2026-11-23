"""Login assistido e leitura do saldo de pontos."""

from __future__ import annotations

import contextlib
import logging
import time

from .browser import DESKTOP, Device, Session
from .config import Config
from .selectors import POINTS_COUNTER, REWARDS_HOME, SIGNED_IN
from .utils import format_points, parse_points

log = logging.getLogger(__name__)


def _first_visible(page, selectors: tuple[str, ...], timeout_ms: int = 1500):
    for selector in selectors:
        try:
            locator = page.locator(selector).first
            if locator.count() and locator.is_visible(timeout=timeout_ms):
                return locator
        except Exception:
            continue
    return None


def is_signed_in(page) -> bool:
    """Heurística: elementos da conta visíveis ou URL já no dashboard."""
    if _first_visible(page, SIGNED_IN) is not None:
        return True
    return "/dashboard" in page.url or "/earn" in page.url


def read_points_from_page(page) -> int | None:
    locator = _first_visible(page, POINTS_COUNTER, timeout_ms=2500)
    if locator is None:
        return None
    try:
        text = locator.inner_text()
    except Exception:
        return None
    value = parse_points(text)
    if value is not None:
        log.debug("Saldo lido: %s (%r)", value, text)
    return value


def read_points_in_context(context, url: str = REWARDS_HOME) -> int | None:
    """Abre uma aba temporária no dashboard e lê o saldo."""
    try:
        page = context.new_page()
    except Exception:
        return None
    try:
        page.goto(url, wait_until="domcontentloaded")
        for _ in range(2):
            points = read_points_from_page(page)
            if points is not None:
                return points
            time.sleep(1.2)
        return None
    except Exception:
        log.debug("Falha ao ler pontos no contexto", exc_info=True)
        return None
    finally:
        with contextlib.suppress(Exception):
            page.close()


def read_points(session: Session, device: Device = DESKTOP, *, goto: bool = True) -> int | None:
    """Abre uma aba no dashboard e devolve o saldo atual (ou None)."""
    ctx = session.new_context(device)
    try:
        return read_points_in_context(ctx, REWARDS_HOME if goto else "about:blank")
    finally:
        with contextlib.suppress(Exception):
            ctx.close()


def ensure_signed_in(session: Session, cfg: Config) -> bool:
    """Confere a sessão salva; não faz login automático."""
    points = read_points(session)
    if points is None:
        log.error(
            "Sessão inválida ou expirada. Rode `conquistas login` para entrar "
            "manualmente e salvar a sessão."
        )
        return False
    log.info("Sessão válida. Saldo atual: %s pontos.", format_points(points))
    return True


def login(session: Session, cfg: Config, timeout_s: int = 300) -> bool:
    """Abre o navegador para login manual e salva o estado ao detectar sucesso."""
    ctx = session.new_context(DESKTOP, load_state=False)
    page = ctx.new_page()
    try:
        page.goto(REWARDS_HOME, wait_until="domcontentloaded")
        print(
            "\n"
            "============================================================\n"
            " Faça login na janela do navegador (e-mail, senha, 2FA).\n"
            " O Conquistas espera até detectar a conta conectada.\n"
            f" Tempo limite: {timeout_s}s — feche a janela para cancelar.\n"
            "============================================================\n",
            flush=True,
        )
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            if is_signed_in(page) or read_points_from_page(page) is not None:
                time.sleep(2.0)  # deixa os cookies assentarem
                session.save_state(ctx)
                points = read_points_from_page(page)
                if points is not None:
                    print(f"Login concluído. Saldo atual: {format_points(points)} pontos.")
                else:
                    print("Login concluído e sessão salva.")
                return True
            time.sleep(2.0)
        log.error("Tempo esgotado sem detectar login. Nada foi salvo.")
        return False
    finally:
        with contextlib.suppress(Exception):
            ctx.close()
