from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory

from app.db import Database
from app.timing import TimingEngine


def test_seven_simultaneous_cars_complete_laps_without_db_lock_errors():
    with TemporaryDirectory() as td:
        db = Database(Path(td) / "main.db")
        cars = db.list_cars()
        engine = TimingEngine(db, min_lap_seconds=1)
        base = db.now_ms() - 30_000
        sessions = [db.prepare_session(f"Driver {i+1}", None, c["id"], 900) for i, c in enumerate(cars)]

        def run_one(i):
            marker = cars[i]["marker_id"]
            t = base + i * 100
            engine.handle_gate(marker, "START", at_ms=t)
            return engine.handle_gate(marker, "FINISH", at_ms=t + 5000 + i * 100)

        with ThreadPoolExecutor(max_workers=7) as ex:
            results = list(ex.map(run_one, range(7)))
        assert all(r["ok"] for r in results)
        assert all(db.get_session(s["id"])["lap_count"] == 1 for s in sessions)
        assert db.integrity_check() == "ok"
