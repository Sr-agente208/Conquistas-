"""Painel web local: abrir no navegador e usar, no estilo do Zunder.

O painel roda na sua máquina, escuta só em localhost por padrão e **nunca pede
sua senha**: o login abre o site oficial da Microsoft num navegador controlado
pelo Playwright, na própria máquina, e guarda apenas os cookies da sessão.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import threading
import uuid
import webbrowser
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from typing import Any
from urllib.parse import urlparse

from . import __version__
from .config import Config
from .utils import iso_now

log = logging.getLogger(__name__)

MAX_LOG_LINES = 400
MAX_BODY_BYTES = 8 * 1024
LOOPBACK = {"127.0.0.1", "localhost", "::1", "0.0.0.0"}


class BusyError(RuntimeError):
    """Já existe uma execução em andamento."""


# --------------------------------------------------------------------------- #
# tarefas em segundo plano
# --------------------------------------------------------------------------- #
@dataclass
class Job:
    id: str
    kind: str
    status: str = "running"
    started_at: str = field(default_factory=iso_now)
    finished_at: str | None = None
    logs: list[dict[str, str]] = field(default_factory=list)
    result: dict[str, Any] | None = None
    error: str | None = None

    def add_log(self, message: str, level: str = "INFO") -> None:
        self.logs.append({"at": iso_now(), "level": level, "message": message})
        if len(self.logs) > MAX_LOG_LINES:
            del self.logs[: len(self.logs) - MAX_LOG_LINES]

    def snapshot(self, limit: int = 150) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "status": self.status,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "logs": self.logs[-limit:],
            "result": self.result,
            "error": self.error,
        }


class _JobLogHandler(logging.Handler):
    """Leva as mensagens de log da automação para a tela do painel."""

    def __init__(self, job: Job) -> None:
        super().__init__()
        self.job = job
        self.setFormatter(logging.Formatter("%(message)s"))

    def emit(self, record: logging.LogRecord) -> None:
        # log nunca deve derrubar a execução
        with contextlib.suppress(Exception):
            self.job.add_log(self.format(record), record.levelname)


class JobManager:
    """Serializa login/execução e expõe o estado para o painel."""

    def __init__(
        self,
        cfg: Config,
        *,
        executor: Callable[..., Any] | None = None,
        login_fn: Callable[..., Any] | None = None,
    ) -> None:
        self.cfg = cfg
        self._executor = executor
        self._login_fn = login_fn
        self._lock = threading.Lock()
        self._job: Job | None = None

    # -- leitura -----------------------------------------------------------
    def busy(self) -> bool:
        with self._lock:
            return bool(self._job and self._job.status == "running")

    def current(self) -> dict[str, Any] | None:
        with self._lock:
            return self._job.snapshot() if self._job else None

    def dashboard(self) -> dict[str, Any]:
        from .storage import Store

        with Store(self.cfg.storage.database) as store:
            latest = store.latest_points()
            summary = store.today_summary()
            runs = store.recent_runs(5)

        state = self.cfg.browser.storage_state
        session = {"exists": state.exists()}
        if state.exists():
            session["updated_at"] = iso_now()  # placeholder substituído abaixo
            try:
                from datetime import datetime

                session["updated_at"] = (
                    datetime.fromtimestamp(state.stat().st_mtime)
                    .astimezone()
                    .isoformat(timespec="seconds")
                )
            except OSError:  # pragma: no cover - arquivo sumiu no meio
                pass

        return {
            "version": __version__,
            "points": {"value": latest[0], "at": latest[1]} if latest else None,
            "today": summary,
            "history": [
                {
                    "started_at": run.started_at,
                    "status": run.status,
                    "points_before": run.points_before,
                    "points_after": run.points_after,
                    "pc": run.pc_searches,
                    "mobile": run.mobile_searches,
                    "daily_done": run.daily_done,
                    "daily_total": run.daily_total,
                }
                for run in runs
            ],
            "session": session,
            "targets": {"pc": self.cfg.searches.pc, "mobile": self.cfg.searches.mobile},
            "job": self.current(),
        }

    # -- ações -------------------------------------------------------------
    def start_run(self, options: dict[str, Any] | None = None) -> dict[str, Any]:
        options = options or {}
        only = str(options.get("only", "all"))
        if only not in ("all", "searches", "daily"):
            raise ValueError("Parâmetro 'only' inválido.")
        job = self._new_job("run")
        opts = {
            "only": only,
            "pc": options.get("pc"),
            "mobile": options.get("mobile"),
            "dry_run": bool(options.get("dry_run")),
        }
        self._spawn(job, lambda: self._run(opts))
        return job.snapshot()

    def start_login(self, options: dict[str, Any] | None = None) -> dict[str, Any]:
        options = options or {}
        timeout = int(options.get("timeout", 300))
        job = self._new_job("login")
        self._spawn(job, lambda: self._login(timeout))
        return job.snapshot()

    # -- interno -----------------------------------------------------------
    def _new_job(self, kind: str) -> Job:
        with self._lock:
            if self._job and self._job.status == "running":
                raise BusyError("Já existe uma execução em andamento.")
            job = Job(id=uuid.uuid4().hex[:8], kind=kind)
            self._job = job
        return job

    def _spawn(self, job: Job, fn: Callable[[], Any]) -> None:
        threading.Thread(target=self._work, args=(job, fn), daemon=True).start()

    def _work(self, job: Job, fn: Callable[[], Any]) -> None:
        handler = _JobLogHandler(job)
        logger = logging.getLogger("conquistas")
        logger.addHandler(handler)
        job.add_log("Iniciando " + ("login" if job.kind == "login" else "execução") + "…")
        try:
            job.result = fn()
            job.status = "ok"
            job.add_log("Concluído com sucesso.")
        except Exception as exc:
            job.status = "error"
            job.error = str(exc) or exc.__class__.__name__
            job.add_log(job.error, "ERROR")
            if job.kind == "run":
                log.exception("Falha na execução")
        finally:
            job.finished_at = iso_now()
            logger.removeHandler(handler)

    def _run(self, options: dict[str, Any]) -> dict[str, Any]:
        from .runner import execute, result_to_dict

        if self._executor is not None:
            return self._executor(self.cfg, **options)
        result = execute(
            self.cfg,
            only=options["only"],
            pc=options.get("pc"),
            mobile=options.get("mobile"),
            dry_run=options.get("dry_run", False),
        )
        return result_to_dict(result)

    def _login(self, timeout: int) -> dict[str, Any]:
        if self._login_fn is not None:
            return self._login_fn(self.cfg, timeout)

        from .auth import login
        from .browser import Session

        cfg = replace(self.cfg, browser=replace(self.cfg.browser, headless=False))
        with Session(cfg) as session:
            ok = login(session, cfg, timeout_s=timeout)
        if not ok:
            raise RuntimeError(
                "Login não concluído (tempo esgotado ou janela fechada). Tente de novo."
            )
        return {"ok": True}


# --------------------------------------------------------------------------- #
# HTTP
# --------------------------------------------------------------------------- #
def _panel_html() -> str:
    return resources.files("conquistas").joinpath("web", "panel.html").read_text(encoding="utf-8")


def make_handler(
    manager: JobManager, panel: str, allowed_hosts: set[str]
) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = f"Conquistas/{__version__}"

        def log_message(self, fmt: str, *args: Any) -> None:  # silencia o padrão
            log.debug("%s - %s", self.address_string(), fmt % args)

        # -- helpers ---------------------------------------------------
        def _send(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def _json(self, data: Any, status: int = HTTPStatus.OK) -> None:
            payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self._send(status, payload, "application/json; charset=utf-8")

        def _error(self, status: int, message: str) -> None:
            self._json({"error": message}, status)

        def _origin_ok(self) -> bool:
            origin = self.headers.get("Origin")
            if not origin:
                return True
            host = urlparse(origin).hostname or ""
            return host in allowed_hosts

        def _guard_post(self) -> bool:
            if self.headers.get("X-Conquistas") != "1":
                self._error(HTTPStatus.FORBIDDEN, "Cabeçalho X-Conquistas ausente.")
                return False
            if not self._origin_ok():
                self._error(HTTPStatus.FORBIDDEN, "Origem não permitida.")
                return False
            return True

        def _read_json(self) -> dict[str, Any]:
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                return {}
            if length <= 0:
                return {}
            if length > MAX_BODY_BYTES:
                raise ValueError("Corpo grande demais.")
            raw = self.rfile.read(length)
            try:
                data = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ValueError("JSON inválido.") from exc
            return data if isinstance(data, dict) else {}

        # -- rotas -----------------------------------------------------
        def do_HEAD(self) -> None:  # noqa: N802
            self.do_GET()

        def do_GET(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            if path in ("/", "/index.html"):
                self._send(HTTPStatus.OK, panel.encode("utf-8"), "text/html; charset=utf-8")
                return
            if path == "/api/state":
                self._json(manager.dashboard())
                return
            if path == "/api/job":
                self._json({"job": manager.current()})
                return
            if path == "/healthz":
                self._json({"ok": True, "version": __version__})
                return
            self._error(HTTPStatus.NOT_FOUND, "Rota não encontrada.")

        def do_POST(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            if path not in ("/api/run", "/api/login"):
                self._error(HTTPStatus.NOT_FOUND, "Rota não encontrada.")
                return
            if not self._guard_post():
                return
            try:
                options = self._read_json()
            except ValueError as exc:
                self._error(HTTPStatus.BAD_REQUEST, str(exc))
                return

            try:
                if path == "/api/run":
                    job = manager.start_run(options)
                else:
                    job = manager.start_login(options)
            except BusyError as exc:
                self._error(HTTPStatus.CONFLICT, str(exc))
                return
            except (TypeError, ValueError) as exc:
                self._error(HTTPStatus.BAD_REQUEST, str(exc))
                return
            self._json({"job": job}, HTTPStatus.ACCEPTED)

    return Handler


def create_server(
    cfg: Config,
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
    manager: JobManager | None = None,
    panel: str | None = None,
) -> ThreadingHTTPServer:
    manager = manager or JobManager(cfg)
    text = panel if panel is not None else _panel_html()
    allowed = set(LOOPBACK) | {host}
    handler = make_handler(manager, text, allowed)
    server = ThreadingHTTPServer((host, port), handler)
    server.daemon_threads = True
    return server


def serve(
    cfg: Config, *, host: str = "127.0.0.1", port: int = 8765, open_browser: bool = True
) -> int:
    """Sobe o painel e bloqueia até Ctrl+C."""
    if host not in LOOPBACK and os.environ.get("CONQUISTAS_ALLOW_PUBLIC") != "1":
        raise SystemExit(
            "Recusado: expor o painel na rede permite que outras máquinas disparem execuções "
            "na sua conta. Use uma porta local ou defina CONQUISTAS_ALLOW_PUBLIC=1 se souber o "
            "que está fazendo."
        )

    server = create_server(cfg, host=host, port=port)
    shown_host = "127.0.0.1" if host in ("0.0.0.0", "::") else host
    url = f"http://{shown_host}:{server.server_address[1]}/"
    print(f"Painel do Conquistas em {url}")
    print("Deixe esta janela aberta. Ctrl+C encerra.\n")

    if open_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nEncerrando painel…")
    finally:
        server.shutdown()
        server.server_close()
    return 0
