"""Persistência local (SQLite): execuções e histórico de pontos."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .utils import iso_now, today_str

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at     TEXT    NOT NULL,
    finished_at    TEXT,
    status         TEXT    NOT NULL DEFAULT 'running',
    points_before  INTEGER,
    points_after   INTEGER,
    pc_searches    INTEGER NOT NULL DEFAULT 0,
    mobile_searches INTEGER NOT NULL DEFAULT 0,
    daily_done     INTEGER NOT NULL DEFAULT 0,
    daily_total    INTEGER NOT NULL DEFAULT 0,
    notes          TEXT
);

CREATE TABLE IF NOT EXISTS points_snapshots (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    captured_at TEXT    NOT NULL,
    points      INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_snapshots_captured ON points_snapshots(captured_at);
CREATE INDEX IF NOT EXISTS idx_runs_started ON runs(started_at);
"""


@dataclass(frozen=True)
class RunRow:
    id: int
    started_at: str
    finished_at: str | None
    status: str
    points_before: int | None
    points_after: int | None
    pc_searches: int
    mobile_searches: int
    daily_done: int
    daily_total: int
    notes: str | None


class Store:
    """Fachada fina sobre o SQLite; uso típico com `with`."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    # -- ciclo de vida -----------------------------------------------------
    def __enter__(self) -> Store:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        try:
            self._conn.commit()
        finally:
            self._conn.close()

    # -- execuções ---------------------------------------------------------
    def start_run(self) -> int:
        cur = self._conn.execute(
            "INSERT INTO runs (started_at, status) VALUES (?, 'running')", (iso_now(),)
        )
        self._conn.commit()
        return int(cur.lastrowid)

    def finish_run(
        self,
        run_id: int,
        *,
        points_before: int | None = None,
        points_after: int | None = None,
        pc_searches: int = 0,
        mobile_searches: int = 0,
        daily_done: int = 0,
        daily_total: int = 0,
        status: str = "ok",
        notes: str | None = None,
    ) -> None:
        self._conn.execute(
            """
            UPDATE runs SET finished_at = ?, status = ?, points_before = ?, points_after = ?,
                            pc_searches = ?, mobile_searches = ?, daily_done = ?,
                            daily_total = ?, notes = ?
            WHERE id = ?
            """,
            (
                iso_now(),
                status,
                points_before,
                points_after,
                pc_searches,
                mobile_searches,
                daily_done,
                daily_total,
                notes,
                run_id,
            ),
        )
        self._conn.commit()

    # -- pontos ------------------------------------------------------------
    def record_points(self, points: int) -> None:
        self._conn.execute(
            "INSERT INTO points_snapshots (captured_at, points) VALUES (?, ?)",
            (iso_now(), int(points)),
        )
        self._conn.commit()

    def latest_points(self) -> tuple[int, str] | None:
        row = self._conn.execute(
            "SELECT points, captured_at FROM points_snapshots ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return (int(row["points"]), str(row["captured_at"])) if row else None

    def points_on(self, day: str) -> list[tuple[str, int]]:
        rows = self._conn.execute(
            "SELECT captured_at, points FROM points_snapshots "
            "WHERE substr(captured_at, 1, 10) = ? ORDER BY id",
            (day,),
        ).fetchall()
        return [(str(r["captured_at"]), int(r["points"])) for r in rows]

    def points_series(self, days: int = 14) -> list[tuple[str, int, int]]:
        """Para cada dia: (dia, primeiro valor, último valor)."""
        rows = self._conn.execute(
            """
            SELECT substr(captured_at, 1, 10) AS day,
                   MIN(id) AS first_id,
                   MAX(id) AS last_id
            FROM points_snapshots
            GROUP BY day
            ORDER BY day DESC
            LIMIT ?
            """,
            (days,),
        ).fetchall()
        series: list[tuple[str, int, int]] = []
        for row in rows:
            first = self._conn.execute(
                "SELECT points FROM points_snapshots WHERE id = ?", (row["first_id"],)
            ).fetchone()
            last = self._conn.execute(
                "SELECT points FROM points_snapshots WHERE id = ?", (row["last_id"],)
            ).fetchone()
            if first and last:
                series.append((str(row["day"]), int(first["points"]), int(last["points"])))
        return series

    # -- consultas ---------------------------------------------------------
    def recent_runs(self, limit: int = 10) -> list[RunRow]:
        rows = self._conn.execute(
            "SELECT * FROM runs ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [RunRow(**dict(row)) for row in rows]

    def today_summary(self) -> dict[str, Any]:
        day = today_str()
        row = self._conn.execute(
            """
            SELECT COUNT(*)                        AS runs,
                   COALESCE(SUM(pc_searches), 0)   AS pc,
                   COALESCE(SUM(mobile_searches),0) AS mobile,
                   COALESCE(SUM(daily_done), 0)    AS daily_done,
                   COALESCE(SUM(daily_total), 0)   AS daily_total
            FROM runs
            WHERE substr(started_at, 1, 10) = ?
            """,
            (day,),
        ).fetchone()
        points = self.points_on(day)
        gained = (points[-1][1] - points[0][1]) if len(points) >= 2 else None
        return {
            "day": day,
            "runs": int(row["runs"]) if row else 0,
            "pc": int(row["pc"]) if row else 0,
            "mobile": int(row["mobile"]) if row else 0,
            "daily_done": int(row["daily_done"]) if row else 0,
            "daily_total": int(row["daily_total"]) if row else 0,
            "points_first": points[0][1] if points else None,
            "points_last": points[-1][1] if points else None,
            "gained": gained,
        }
