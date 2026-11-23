"""Conjunto diário e atividades extras (melhor esforço, EXPERIMENTAL).

O HTML do Microsoft Rewards muda com frequência e os quizzes variam de
estrutura. Esta tarefa tenta abrir cada cartão e avançar pelas respostas;
ela registra o que conseguiu e nunca falha a execução inteira por causa de
um cartão.
"""

from __future__ import annotations

import contextlib
import logging
import random
import time
from typing import Any

from ..browser import Session
from ..config import Config
from ..selectors import (
    ADVANCE_BUTTONS,
    ADVANCE_TEXT,
    DAILY_CARD_LINKS,
    QUIZ_OPTIONS,
    REWARDS_DASHBOARD,
    THANKS_TEXT,
)
from . import TaskResult

log = logging.getLogger(__name__)

_MAX_FRAMES = 4


def _scopes(page) -> list[Any]:
    scopes: list[Any] = [page]
    with contextlib.suppress(Exception):
        scopes.extend(page.frames[1:_MAX_FRAMES])
    return scopes


def _click_first(page, selectors: tuple[str, ...], *, per_selector: int = 3) -> bool:
    for scope in _scopes(page):
        for selector in selectors:
            try:
                locator = scope.locator(selector)
                count = min(locator.count(), per_selector)
            except Exception:
                continue
            for index in range(count):
                try:
                    element = locator.nth(index)
                    if element.is_visible() and element.is_enabled():
                        element.click(timeout=3_000)
                        return True
                except Exception:
                    continue
    return False


def _click_advance(page) -> bool:
    if _click_first(page, ADVANCE_BUTTONS):
        return True
    for scope in _scopes(page):
        try:
            button = scope.get_by_role("button", name=ADVANCE_TEXT).first
            if button.count() and button.is_visible():
                button.click(timeout=3_000)
                return True
        except Exception:
            continue
        try:
            link = scope.get_by_role("link", name=ADVANCE_TEXT).first
            if link.count() and link.is_visible():
                link.click(timeout=3_000)
                return True
        except Exception:
            continue
    return False


def _already_done(page) -> bool:
    try:
        text = page.inner_text("body", timeout=2_000)
    except Exception:
        return False
    return bool(THANKS_TEXT.search(text))


def _collect_cards(page, limit: int) -> list[tuple[str, str]]:
    """Coleta (título, URL) dos cartões visíveis, sem duplicatas."""
    cards: list[tuple[str, str]] = []
    seen: set[str] = set()
    for selector in DAILY_CARD_LINKS:
        try:
            locator = page.locator(selector)
            total = min(locator.count(), 80)
        except Exception:
            continue
        for index in range(total):
            try:
                element = locator.nth(index)
                href = element.get_attribute("href") or ""
                title = " ".join((element.inner_text() or "").split())[:80]
            except Exception:
                continue
            if not href.startswith("http"):
                continue
            key = href.split("?")[0].rstrip("/")
            if key in seen:
                continue
            seen.add(key)
            cards.append((title or href, href))
            if len(cards) >= limit:
                return cards
    return cards


def complete_card(context, url: str, cfg: Config, rng: random.Random) -> bool:
    """Abre um cartão e tenta concluir o quiz/atividade. Retorna sucesso provável."""
    try:
        page = context.new_page()
    except Exception:
        return False
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=cfg.browser.timeout_ms)
        page.wait_for_timeout(int(rng.uniform(1_200, 2_400)))
        if _already_done(page):
            return True
        for _ in range(cfg.daily.max_steps_per_card):
            clicked_option = _click_first(page, QUIZ_OPTIONS)
            advanced = _click_advance(page)
            if not clicked_option and not advanced:
                break
            page.wait_for_timeout(int(rng.uniform(700, 1_900)))
            if _already_done(page):
                return True
        return True
    except Exception:
        log.debug("Cartão falhou: %s", url, exc_info=True)
        return False
    finally:
        with contextlib.suppress(Exception):
            page.close()


def run(
    session: Session,
    cfg: Config,
    *,
    dry_run: bool = False,
    rng: random.Random | None = None,
) -> TaskResult:
    from ..browser import DESKTOP

    rng = rng or random.Random()
    result = TaskResult(name="diario")
    ctx = session.new_context(DESKTOP)
    try:
        page = ctx.new_page()
        page.goto(REWARDS_DASHBOARD, wait_until="domcontentloaded")
        try:
            page.wait_for_selector("#daily-sets, #more-activities, mee-card", timeout=15_000)
        except Exception:
            log.debug("Cartões não apareceram no tempo esperado")

        cards = _collect_cards(page, cfg.daily.max_cards)
        result.target = len(cards)
        log.info("%d cartão(ões) encontrados no dashboard.", len(cards))

        if dry_run:
            for title, url in cards:
                log.info("[dry-run] cartão: %s -> %s", title, url)
            result.notes = "dry-run"
            return result

        for position, (title, url) in enumerate(cards, 1):
            log.info("(%d/%d) abrindo cartão: %s", position, len(cards), title)
            if complete_card(ctx, url, cfg, rng):
                result.performed += 1
            time.sleep(rng.uniform(1.5, 3.5))

        log.info("Atividades abertas: %d/%d", result.performed, result.target)
        return result
    finally:
        with contextlib.suppress(Exception):
            ctx.close()
