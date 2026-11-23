"""Ponto de entrada da CLI `conquistas`."""

from __future__ import annotations

import argparse
import logging
import random
import sys
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

from . import __version__
from .config import Config, ConfigError, load_config

log = logging.getLogger("conquistas")

EXAMPLES = """\
exemplos:
  conquistas login                     # 1ª vez: faz login manual e salva a sessão
  conquistas run                       # buscas de PC + celular + tarefas diárias
  conquistas run --only searches --pc 10
  conquistas run --only daily --dry-run
  conquistas serve                     # painel web local (abrir e usar, estilo Zunder)
  conquistas status                    # saldo e resumo do dia
  conquistas report --days 14          # histórico de ganhos
  conquistas doctor                    # diagnóstico do ambiente
"""


# --------------------------------------------------------------------------- #
# infraestrutura
# --------------------------------------------------------------------------- #
def _setup_logging(cfg: Config, verbose: bool) -> None:
    level = "DEBUG" if verbose else cfg.logging.level.upper()
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    try:
        cfg.logging.file.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(cfg.logging.file, encoding="utf-8"))
    except OSError as exc:  # disco cheio/permissão
        print(f"aviso: sem log em arquivo ({exc}).", file=sys.stderr)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
        handlers=handlers,
        force=True,
    )
    logging.getLogger("asyncio").setLevel("WARNING")


def _fmt_points(value: int | None) -> str:
    return "—" if value is None else f"{value:,}".replace(",", ".")


def _fmt_moment(iso: str | None) -> str:
    if not iso:
        return "—"
    try:
        return datetime.fromisoformat(iso).strftime("%d/%m/%Y %H:%M")
    except ValueError:
        return iso


def _table(headers: list[str], rows: list[list[str]]) -> str:
    widths = [len(h) for h in headers]
    for row in rows:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(cell))
    lines = ["  ".join(h.ljust(widths[i]) for i, h in enumerate(headers))]
    lines.append("  ".join("-" * w for w in widths))
    for row in rows:
        lines.append("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)))
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# comandos
# --------------------------------------------------------------------------- #
def cmd_login(args: argparse.Namespace, cfg: Config) -> int:
    from .auth import read_points
    from .browser import Session
    from .storage import Store

    cfg = replace(cfg, browser=replace(cfg.browser, headless=False))
    with Session(cfg) as session:
        from .auth import login

        if not login(session, cfg, timeout_s=args.timeout):
            return 1
        points = read_points(session)
    if points is not None:
        with Store(cfg.storage.database) as store:
            store.record_points(points)
        print(f"Saldo registrado: {_fmt_points(points)} pontos.")
    return 0


def cmd_run(args: argparse.Namespace, cfg: Config) -> int:
    headless = cfg.browser.headless
    if args.headless:
        headless = True
    if args.headed:
        headless = False
    cfg = replace(cfg, browser=replace(cfg.browser, headless=headless))

    rng = random.Random(args.seed) if args.seed is not None else random.Random()
    pc_target = args.pc if args.pc is not None else cfg.searches.pc
    mobile_target = args.mobile if args.mobile is not None else cfg.searches.mobile

    # Simulação sem navegador: só lista as consultas que seriam feitas.
    if args.dry_run and args.only == "searches":
        from .words_ptbr import generate_queries

        for name, total in (("pc", pc_target), ("mobile", mobile_target)):
            for index, query in enumerate(generate_queries(total, rng), 1):
                print(f"[{name} {index:02d}/{total:02d}] {query}")
        return 0

    from .runner import SessionExpired, execute

    if not cfg.browser.storage_state.exists():
        print(
            "Sessão não encontrada. Rode `conquistas login` antes de executar.",
            file=sys.stderr,
        )
        return 2

    try:
        result = execute(
            cfg,
            only=args.only,
            pc=args.pc,
            mobile=args.mobile,
            dry_run=args.dry_run,
            rng=rng,
        )
    except SessionExpired as exc:
        print(f"{exc} Rode `conquistas login` e tente de novo.", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\nInterrompido pelo usuário.", file=sys.stderr)
        return 130
    except Exception as exc:
        log.exception("Falha durante a execução")
        print(f"Falha: {exc}", file=sys.stderr)
        return 1

    _print_run_summary(result)
    return 0


def cmd_serve(args: argparse.Namespace, cfg: Config) -> int:
    from .server import serve

    if args.headless:
        cfg = replace(cfg, browser=replace(cfg.browser, headless=True))
    return serve(cfg, host=args.host, port=args.port, open_browser=not args.no_browser)


def _print_run_summary(result: Any) -> None:
    print()
    print("Resumo da execução")
    print("=" * 46)
    results = result.results
    if results:
        rows = [
            [
                r.name,
                f"{r.performed}/{r.target}" if r.target else str(r.performed),
                "sim" if r.stopped_early else "",
                r.notes or "",
            ]
            for r in results
        ]
        print(_table(["tarefa", "feito", "parou antes", "observação"], rows))
    else:
        print("Nenhuma tarefa habilitada na configuração.")
    print("-" * 46)
    print(
        f"Saldo antes: {_fmt_points(result.points_before)}   depois: {_fmt_points(result.points_after)}"
    )
    if result.gained is not None:
        print(f"Ganho nesta execução: +{_fmt_points(result.gained)} pontos")
    print()


def cmd_status(args: argparse.Namespace, cfg: Config) -> int:
    from .storage import Store

    with Store(cfg.storage.database) as store:
        latest = store.latest_points()
        summary = store.today_summary()
        runs = store.recent_runs(5)

    print()
    print("Conquistas — situação atual")
    print("=" * 46)
    if latest is None:
        print("Nenhum dado registrado ainda. Rode `conquistas run`.")
        return 0
    points, captured = latest
    print(f"Saldo mais recente : {_fmt_points(points)} pts ({_fmt_moment(captured)})")
    line = (
        f"Hoje ({summary['day']})     : PC {summary['pc']} busca(s), "
        f"celular {summary['mobile']}, diário {summary['daily_done']}/{summary['daily_total']}"
    )
    print(line)
    if summary["gained"] is not None:
        print(f"Ganho de hoje      : +{_fmt_points(summary['gained'])} pts")
    if runs:
        print()
        rows = [
            [
                _fmt_moment(run.started_at),
                run.status,
                f"+{_fmt_points((run.points_after or 0) - (run.points_before or 0))}"
                if run.points_before is not None and run.points_after is not None
                else "—",
                f"{run.pc_searches}/{run.mobile_searches}",
                f"{run.daily_done}/{run.daily_total}",
            ]
            for run in runs
        ]
        print(_table(["quando", "status", "ganho", "pc/mob", "diario"], rows))
    print()
    return 0


def cmd_report(args: argparse.Namespace, cfg: Config) -> int:
    from .storage import Store

    with Store(cfg.storage.database) as store:
        series = store.points_series(args.days)

    if not series:
        print("Sem histórico suficiente. Rode `conquistas run` algumas vezes.")
        return 0

    rows = []
    total = 0
    for day, first, last in reversed(series):
        delta = last - first
        total += max(delta, 0)
        rows.append(
            [
                datetime.fromisoformat(day).strftime("%d/%m/%Y"),
                _fmt_points(first),
                _fmt_points(last),
                f"+{_fmt_points(delta)}",
            ]
        )
    print()
    print(_table(["dia", "início", "fim", "ganho"], rows))
    print(f"\nGanho acumulado no período: +{_fmt_points(total)} pontos")
    print()
    return 0


def cmd_doctor(args: argparse.Namespace, cfg: Config) -> int:

    from .storage import Store

    failures = 0

    def line(symbol: str, label: str, detail: str) -> None:
        print(f" {symbol} {label:<22} {detail}")

    def ok(label: str, detail: str = "") -> None:
        line("✔", label, detail)

    def warn(label: str, detail: str = "") -> None:
        line("!", label, detail)

    def fail(label: str, detail: str = "") -> None:
        nonlocal failures
        failures += 1
        line("✘", label, detail)

    print("\nDiagnóstico do Conquistas\n" + "=" * 60)

    version = sys.version_info
    (ok if version >= (3, 11) else fail)(
        "Python", f"{version.major}.{version.minor}.{version.micro} (requer >= 3.11)"
    )

    if cfg.path:
        ok("Configuração", str(cfg.path))
    else:
        warn("Configuração", "usando padrões (crie conquistas.toml)")

    try:
        import playwright  # noqa: F401

        ok("Pacote Playwright", "importável")
    except ImportError:
        fail("Pacote Playwright", "instale com `pip install -e .`")
        playwright = None  # type: ignore[assignment]

    if playwright is not None:
        try:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=True)
                browser.close()
            ok("Chromium", "navegador disponível")
        except Exception as exc:
            fail(
                "Chromium", f"{str(exc).splitlines()[0][:90]} — rode `playwright install chromium`"
            )

    state = cfg.browser.storage_state
    if state.exists() and state.stat().st_size > 0:
        age_days = (datetime.now(UTC).timestamp() - state.stat().st_mtime) / 86_400
        detail = f"{state} ({age_days:.0f} dia(s) de idade)"
        (warn if age_days > 25 else ok)("Sessão salva", detail)
    else:
        warn("Sessão salva", "ausente — rode `conquistas login`")

    try:
        with Store(cfg.storage.database) as store:
            store.latest_points()
        ok("Banco local", str(cfg.storage.database))
    except Exception as exc:
        fail("Banco local", f"{exc}")

    print("=" * 60)
    if failures:
        print(f"{failures} problema(s) encontrado(s).\n")
        return 1
    print("Tudo pronto.\n")
    return 0


# --------------------------------------------------------------------------- #
# parser
# --------------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="conquistas",
        description="Automação local das buscas e tarefas diárias do Microsoft Rewards.",
        epilog=EXAMPLES,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("-c", "--config", help="caminho do arquivo TOML de configuração")
    parser.add_argument("-v", "--verbose", action="store_true", help="log detalhado (DEBUG)")

    sub = parser.add_subparsers(dest="command", required=True)

    login = sub.add_parser("login", help="faz login manual e salva a sessão do navegador")
    login.add_argument(
        "--timeout", type=int, default=300, help="segundos de espera pelo login (padrão: 300)"
    )
    login.set_defaults(func=cmd_login)

    run = sub.add_parser("run", help="executa as tarefas do dia")
    run.add_argument(
        "--only", choices=["all", "searches", "daily"], default="all", help="limita o que executar"
    )
    run.add_argument("--pc", type=int, help="sobrescreve a cota de buscas no PC")
    run.add_argument("--mobile", type=int, help="sobrescreve a cota de buscas no celular")
    run.add_argument("--dry-run", action="store_true", help="simula sem executar as ações")
    run.add_argument("--headless", action="store_true", help="força execução sem janela")
    run.add_argument("--headed", action="store_true", help="força janela visível")
    run.add_argument("--seed", type=int, help="semente aleatória (reprodutibilidade)")
    run.set_defaults(func=cmd_run)

    serve = sub.add_parser("serve", help="abre o painel web local no navegador")
    serve.add_argument("--host", default="127.0.0.1", help="endereço de escuta (padrão: 127.0.0.1)")
    serve.add_argument("--port", type=int, default=8765, help="porta (padrão: 8765)")
    serve.add_argument(
        "--no-browser", action="store_true", help="não abrir o navegador automaticamente"
    )
    serve.add_argument(
        "--headless", action="store_true", help="executar sem mostrar a janela do navegador"
    )
    serve.set_defaults(func=cmd_serve)

    status = sub.add_parser("status", help="mostra saldo e resumo do dia")
    status.set_defaults(func=cmd_status)

    report = sub.add_parser("report", help="histórico de ganhos por dia")
    report.add_argument("--days", type=int, default=14, help="quantidade de dias (padrão: 14)")
    report.set_defaults(func=cmd_report)

    doctor = sub.add_parser("doctor", help="verifica o ambiente e a sessão")
    doctor.set_defaults(func=cmd_doctor)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        cfg = load_config(args.config)
    except ConfigError as exc:
        print(f"erro de configuração: {exc}", file=sys.stderr)
        return 2
    _setup_logging(cfg, args.verbose)
    log.debug("Configuração carregada de %s", cfg.path or "(padrões)")
    return int(args.func(args, cfg))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
