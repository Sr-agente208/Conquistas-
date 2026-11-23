from __future__ import annotations

import http.client
import json
import threading
import time

import pytest

from conquistas.config import load_config
from conquistas.runner import ExecutionResult, result_to_dict
from conquistas.server import JobManager, _panel_html, create_server
from conquistas.tasks import TaskResult


def write_config(tmp_path):
    cfg_path = tmp_path / "conquistas.toml"
    cfg_path.write_text(
        f"""
[storage]
database = "{(tmp_path / "db.sqlite3").as_posix()}"

[logging]
file = "{(tmp_path / "log.txt").as_posix()}"

[browser]
storage_state = "{(tmp_path / "state.json").as_posix()}"

[searches]
pc = 30
mobile = 20
""",
        encoding="utf-8",
    )
    return load_config(cfg_path)


def fake_execute(cfg, **options):
    return {
        "points_before": 100,
        "points_after": 130,
        "gained": 30,
        "tasks": [{"name": "buscas:desktop", "performed": 10, "target": 30}],
        "options": options,
    }


@pytest.fixture
def panel(tmp_path):
    cfg = write_config(tmp_path)
    manager = JobManager(
        cfg,
        executor=fake_execute,
        login_fn=lambda cfg, timeout: {"ok": True},
    )
    server = create_server(cfg, port=0, manager=manager)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield cfg, manager, server.server_address[1]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def request(port, method, path, body=None, headers=None):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    data = json.dumps(body).encode("utf-8") if body is not None else None
    conn.request(method, path, body=data, headers=headers or {})
    response = conn.getresponse()
    raw = response.read()
    result = (response.status, dict(response.getheaders()), raw)
    conn.close()
    return result


def wait_job(port, timeout=3.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        status, _, raw = request(port, "GET", "/api/job")
        job = json.loads(raw)["job"]
        if job and job["status"] != "running":
            return job
        time.sleep(0.05)
    raise AssertionError("job não terminou a tempo")


def test_panel_page_is_served(panel):
    _, _, port = panel
    status, headers, raw = request(port, "GET", "/")
    assert status == 200
    assert headers["Content-Type"].startswith("text/html")
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert b"Conquistas" in raw
    assert b"/api/state" in raw


def test_panel_has_no_external_assets():
    html = _panel_html()
    assert "http://" not in html and "https://" not in html
    assert "<script src=" not in html and "<link" not in html


def test_state_endpoint(panel):
    _, _, port = panel
    status, _, raw = request(port, "GET", "/api/state")
    assert status == 200
    data = json.loads(raw)
    assert data["targets"] == {"pc": 30, "mobile": 20}
    assert data["version"]
    assert data["session"] == {"exists": False}
    assert data["job"] is None


def test_healthz(panel):
    _, _, port = panel
    status, _, raw = request(port, "GET", "/healthz")
    assert status == 200
    assert json.loads(raw)["ok"] is True


def test_unknown_route_returns_404(panel):
    _, _, port = panel
    status, _, raw = request(port, "GET", "/nao-existe")
    assert status == 404
    assert "error" in json.loads(raw)


def test_post_without_header_is_forbidden(panel):
    _, _, port = panel
    status, _, _ = request(port, "POST", "/api/run", {})
    assert status == 403


def test_post_with_foreign_origin_is_forbidden(panel):
    _, _, port = panel
    status, _, _ = request(
        port,
        "POST",
        "/api/run",
        {},
        headers={"X-Conquistas": "1", "Origin": "https://evil.example"},
    )
    assert status == 403


def test_run_job_completes(panel):
    _, _, port = panel
    status, _, raw = request(
        port,
        "POST",
        "/api/run",
        {"only": "searches", "pc": 5, "mobile": 0},
        headers={"X-Conquistas": "1", "Content-Type": "application/json"},
    )
    assert status == 202
    job = json.loads(raw)["job"]
    assert job["status"] in ("running", "ok")

    finished = wait_job(port)
    assert finished["status"] == "ok"
    assert finished["result"]["gained"] == 30
    assert finished["result"]["options"] == {
        "only": "searches",
        "pc": 5,
        "mobile": 0,
        "dry_run": False,
    }
    assert any("Concluído" in line["message"] for line in finished["logs"])


def test_login_job_completes(panel):
    _, _, port = panel
    status, _, raw = request(port, "POST", "/api/login", {}, headers={"X-Conquistas": "1"})
    assert status == 202
    finished = wait_job(port)
    assert finished["kind"] == "login"
    assert finished["status"] == "ok"
    assert finished["result"] == {"ok": True}


def test_invalid_only_returns_400(panel):
    _, _, port = panel
    status, _, raw = request(
        port,
        "POST",
        "/api/run",
        {"only": "tudo"},
        headers={"X-Conquistas": "1"},
    )
    assert status == 400
    assert "only" in json.loads(raw)["error"]


def test_invalid_json_returns_400(panel):
    _, _, port = panel
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    conn.request(
        "POST",
        "/api/run",
        body=b"{isso nao e json",
        headers={"X-Conquistas": "1"},
    )
    response = conn.getresponse()
    assert response.status == 400
    response.read()
    conn.close()


def test_busy_returns_409(tmp_path):
    cfg = write_config(tmp_path)
    manager = JobManager(cfg, executor=lambda cfg, **opts: time.sleep(0.4) or {"gained": 0})
    server = create_server(cfg, port=0, manager=manager)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    try:
        first, _, _ = request(port, "POST", "/api/run", {}, headers={"X-Conquistas": "1"})
        second, _, raw = request(port, "POST", "/api/run", {}, headers={"X-Conquistas": "1"})
        assert first == 202
        assert second == 409
        assert "andamento" in json.loads(raw)["error"]
        wait_job(port)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_head_request_has_no_body(panel):
    _, _, port = panel
    status, _, raw = request(port, "HEAD", "/")
    assert status == 200
    assert raw == b""


def test_execution_result_helpers():
    result = ExecutionResult(
        points_before=10,
        points_after=45,
        results=[TaskResult(name="diario", performed=2, target=4)],
    )
    assert result.gained == 35
    payload = result_to_dict(result)
    assert payload["gained"] == 35
    assert payload["tasks"][0]["name"] == "diario"
    assert result.by_name("diario").performed == 2
    assert result.by_name("nada") is None


def test_dashboard_reflects_saved_session(tmp_path):
    cfg = write_config(tmp_path)
    state = cfg.browser.storage_state
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text("{}", encoding="utf-8")
    manager = JobManager(cfg)
    data = manager.dashboard()
    assert data["session"]["exists"] is True
    assert data["session"]["updated_at"]
