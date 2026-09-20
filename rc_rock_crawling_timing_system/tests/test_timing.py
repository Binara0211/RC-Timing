from pathlib import Path
from tempfile import TemporaryDirectory

from app.db import Database
from app.timing import TimingEngine


def setup():
    td = TemporaryDirectory()
    db = Database(Path(td.name) / "test.db")
    car = db.list_cars()[0]
    s = db.prepare_session("Test Driver", None, car["id"], 900)
    return td, db, car, s


def test_valid_start_finish_sequence():
    td, db, car, s = setup()
    try:
        engine = TimingEngine(db, min_lap_seconds=5)
        assert engine.handle_gate(car["marker_id"], "FINISH", at_ms=1000)["reason"] == "waiting_for_start"
        assert engine.handle_gate(car["marker_id"], "START", at_ms=10_000)["action"] == "session_started"
        # Too-fast finish is rejected.
        assert engine.handle_gate(car["marker_id"], "FINISH", at_ms=12_000)["ok"] is False
        # Valid finish counts lap 1.
        r = engine.handle_gate(car["marker_id"], "FINISH", at_ms=18_500)
        assert r["ok"] is True and r["lap"]["lap_no"] == 1 and r["lap"]["lap_ms"] == 8500
        # Duplicate finish cannot create another lap.
        assert engine.handle_gate(car["marker_id"], "FINISH", at_ms=20_000)["ok"] is False
        engine.handle_gate(car["marker_id"], "START", at_ms=30_000)
        r2 = engine.handle_gate(car["marker_id"], "FINISH", at_ms=39_000)
        assert r2["lap"]["lap_no"] == 2
        final = db.get_session(s["id"])
        assert final["lap_count"] == 2
        assert final["best_lap_ms"] == 8500
    finally:
        td.cleanup()


def test_time_expiry_blocks_new_result():
    td = TemporaryDirectory()
    try:
        db = Database(Path(td.name) / "test.db")
        car = db.list_cars()[0]
        s = db.prepare_session("Timer Test", None, car["id"], 60)
        engine = TimingEngine(db, min_lap_seconds=1, allow_finish_after_expiry=False)
        engine.handle_gate(car["marker_id"], "START", at_ms=100_000)
        # After exact end time (160000), next event closes the session.
        r = engine.handle_gate(car["marker_id"], "FINISH", at_ms=161_000)
        assert r["reason"] == "time_expired"
        assert db.get_session(s["id"])["status"] == "finished"
    finally:
        td.cleanup()
