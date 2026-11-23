"""Buscas no Bing (cota de PC e de celular)."""

from __future__ import annotations

import contextlib
import logging
import random
import time

from ..auth import read_points_in_context
from ..browser import DESKTOP, Device, Session, device_by_name
from ..config import Config
from ..human import Pacer, random_scroll, type_text
from ..selectors import BING_HOME
from ..utils import search_url
from ..words_ptbr import generate_queries
from . import TaskResult

log = logging.getLogger(__name__)


def _perform_search(page, query: str, cfg: Config, rng: random.Random) -> None:
    """Digita a consulta na caixa do Bing (com fallback para URL direta)."""
    typed = False
    try:
        page.goto(BING_HOME, wait_until="domcontentloaded")
        box = page.locator("#sb_form_q").first
        if box.count() and box.is_visible():
            box.click()
            if cfg.searches.human_typing:
                type_text(page.keyboard, query, rng)
            else:
                box.fill(query)
            page.keyboard.press("Enter")
            page.wait_for_selector("#b_results", timeout=15_000)
            typed = True
    except Exception:
        log.debug("Busca por digitação falhou; usando URL direta", exc_info=True)

    if not typed:
        page.goto(
            search_url(query, cfg.searches.query_language),
            wait_until="domcontentloaded",
        )
        try:
            page.wait_for_selector("#b_results", timeout=10_000)
        except Exception:
            log.debug("Resultados não detectados para %r", query)

    random_scroll(page, rng, moves=rng.randint(1, 3))


def run(
    session: Session,
    cfg: Config,
    device_name: str = "pc",
    limit: int | None = None,
    *,
    dry_run: bool = False,
    rng: random.Random | None = None,
) -> TaskResult:
    """Executa até `limit` buscas no dispositivo indicado."""
    rng = rng or random.Random()
    device: Device = device_by_name(device_name)
    default_target = cfg.searches.pc if device is DESKTOP else cfg.searches.mobile
    target = default_target if limit is None else max(0, limit)
    name = f"buscas:{device.name}"
    result = TaskResult(name=name, target=target)

    if target == 0:
        log.info("[%s] cota configurada como 0; nada a fazer.", name)
        return result

    queries = generate_queries(target, rng)
    if dry_run:
        for index, query in enumerate(queries, 1):
            log.info("[dry-run] %s %02d/%02d: %s", name, index, target, query)
        result.notes = "dry-run"
        return result

    pacer = Pacer.from_config(cfg.searches, rng)
    ctx = session.new_context(device)
    page = None
    last_points: int | None = None
    stalled = 0
    try:
        page = ctx.new_page()
        baseline = read_points_in_context(ctx)
        last_points = baseline
        if baseline is not None:
            log.info("[%s] saldo inicial: %s pontos", name, baseline)

        for index, query in enumerate(queries, 1):
            try:
                _perform_search(page, query, cfg, rng)
                result.performed += 1
                log.info("[%s] %02d/%02d: %s", name, index, target, query)
            except Exception:
                log.warning("[%s] busca %02d falhou; seguindo", name, index, exc_info=True)

            if index % cfg.searches.check_every == 0 and index < target:
                current = read_points_in_context(ctx)
                if current is not None and last_points is not None:
                    if current <= last_points:
                        stalled += 1
                        log.info(
                            "[%s] saldo sem avanço (%s -> %s), checagem %d/%d",
                            name,
                            last_points,
                            current,
                            stalled,
                            cfg.searches.max_stalled_checks,
                        )
                    else:
                        stalled = 0
                    last_points = current
                    if stalled >= cfg.searches.max_stalled_checks:
                        result.stopped_early = True
                        result.notes = "cota diária já cumprida"
                        log.info("[%s] cota parece cumprida; encerrando.", name)
                        break

            if index < target:
                pacer.wait()

        final = read_points_in_context(ctx)
        if final is not None and baseline is not None:
            result.points_gained = max(0, final - baseline)
        log.info(
            "[%s] %d/%d buscas concluídas%s",
            name,
            result.performed,
            target,
            f" (+{result.points_gained} pts)" if result.points_gained else "",
        )
        return result
    finally:
        with contextlib.suppress(Exception):
            ctx.close()


def run_both(
    session: Session,
    cfg: Config,
    pc: int | None = None,
    mobile: int | None = None,
    *,
    dry_run: bool = False,
    rng: random.Random | None = None,
) -> list[TaskResult]:
    """Executa PC e celular em sequência, com pausa entre os dois."""
    rng = rng or random.Random()
    results = [run(session, cfg, "pc", pc, dry_run=dry_run, rng=rng)]
    if results[0].performed and not results[0].stopped_early:
        time.sleep(rng.uniform(8, 15))
    results.append(run(session, cfg, "mobile", mobile, dry_run=dry_run, rng=rng))
    return results
