from pathlib import Path
from tempfile import TemporaryDirectory

from app.db import Database
from app.timing import TimingEngine


def test_backup_and_integrity():
    with TemporaryDirectory() as td:
        td = Path(td)
        db = Database(td / "main.db")
        assert db.integrity_check() == "ok"
        out = db.backup_to(td / "backup.db")
        assert out.exists() and out.stat().st_size > 0
        db2 = Database(out)
        assert db2.integrity_check() == "ok"


def test_leaderboard_order():
    with TemporaryDirectory() as td:
        db = Database(Path(td) / "main.db")
        cars = db.list_cars()
        e = TimingEngine(db, min_lap_seconds=1)
        for idx, duration in [(0, 8000), (1, 6000)]:
            s = db.prepare_session(f"Driver {idx+1}", None, cars[idx]["id"], 900)
            base = db.now_ms() - 100000 + idx * 20000
            e.handle_gate(cars[idx]["marker_id"], "START", at_ms=base)
            e.handle_gate(cars[idx]["marker_id"], "FINISH", at_ms=base + duration)
            db.finish_session(s["id"], "operator_finished", at_ms=base + duration + 1)
        fastest = db.leaderboard_fastest("today", 10)
        assert fastest[0]["customer_name"] == "Driver 2"
        assert fastest[0]["lap_ms"] == 6000
