from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory

from app.db import Database
from app.timing import TimingEngine


def test_seven_players_multi_lap_endurance():
    """Simulate maximum capacity: 7 simultaneous cars, 25 valid laps each."""
    with TemporaryDirectory() as td:
        db = Database(Path(td) / "endurance.db")
        cars = db.list_cars()
        engine = TimingEngine(db, min_lap_seconds=0.5)
        base = db.now_ms() - 600_000
        sessions = [db.prepare_session(f"Load Driver {i+1}", None, c["id"], 900) for i, c in enumerate(cars)]

        def run_car(i: int):
            marker = cars[i]["marker_id"]
            t = base + i * 25
            result = engine.handle_gate(marker, "START", at_ms=t)
            assert result["ok"]
            for lap_no in range(25):
                finish_t = t + 2000
                result = engine.handle_gate(marker, "FINISH", at_ms=finish_t)
                assert result["ok"]
                if lap_no < 24:
                    t = finish_t + 1000
                    result = engine.handle_gate(marker, "START", at_ms=t)
                    assert result["ok"]
            return True

        with ThreadPoolExecutor(max_workers=7) as ex:
            assert all(ex.map(run_car, range(7)))

        for s in sessions:
            final = db.get_session(s["id"])
            assert final["lap_count"] == 25
            assert final["best_lap_ms"] == 2000
        assert db.integrity_check() == "ok"
