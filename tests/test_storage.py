from __future__ import annotations

from conquistas.storage import Store


def test_points_roundtrip(tmp_path):
    with Store(tmp_path / "db.sqlite3") as store:
        store.record_points(1200)
        store.record_points(1250)
        latest = store.latest_points()
        assert latest is not None
        assert latest[0] == 1250


def test_run_lifecycle_and_summary(tmp_path):
    with Store(tmp_path / "db.sqlite3") as store:
        run_id = store.start_run()
        store.finish_run(
            run_id,
            points_before=1000,
            points_after=1150,
            pc_searches=30,
            mobile_searches=20,
            daily_done=3,
            daily_total=5,
        )
        runs = store.recent_runs()
        assert len(runs) == 1
        run = runs[0]
        assert run.id == run_id
        assert run.status == "ok"
        assert run.points_after - run.points_before == 150

        summary = store.today_summary()
        assert summary["runs"] == 1
        assert summary["pc"] == 30
        assert summary["mobile"] == 20
        assert summary["daily_done"] == 3


def test_summary_without_data(tmp_path):
    with Store(tmp_path / "db.sqlite3") as store:
        summary = store.today_summary()
        assert summary["runs"] == 0
        assert summary["gained"] is None
        assert store.latest_points() is None


def test_points_series(tmp_path):
    with Store(tmp_path / "db.sqlite3") as store:
        store.record_points(10)
        store.record_points(30)
        series = store.points_series(7)
        assert len(series) == 1
        day, first, last = series[0]
        assert (first, last) == (10, 30)


def test_reopen_existing_database(tmp_path):
    path = tmp_path / "db.sqlite3"
    with Store(path) as store:
        store.record_points(99)
    with Store(path) as store:
        assert store.latest_points()[0] == 99
