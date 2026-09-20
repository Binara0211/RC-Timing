from __future__ import annotations

import threading
import time
from typing import Callable

from .db import Database


class TimingEngine:
    def __init__(self, db: Database, min_lap_seconds: float = 5.0, allow_finish_after_expiry: bool = False, now_fn: Callable[[], int] | None = None):
        self.db = db
        self.min_lap_ms = int(min_lap_seconds * 1000)
        self.allow_finish_after_expiry = allow_finish_after_expiry
        self.now_fn = now_fn or (lambda: int(time.time() * 1000))
        self._lock = threading.RLock()

    def handle_gate(self, marker_id: int, gate: str, source: str = "camera", at_ms: int | None = None) -> dict:
        gate = gate.upper().strip()
        if gate not in {"START", "FINISH"}:
            raise ValueError("gate must be START or FINISH")
        at_ms = at_ms or self.now_fn()
        with self._lock:
            session = self.db.get_active_session_by_marker(marker_id)
            if not session:
                self.db.log_event("GATE_NO_ACTIVE_SESSION", source, gate, marker_id=marker_id, at_ms=at_ms)
                return {"ok": False, "reason": "no_active_session"}

            if session["status"] == "prepared":
                if gate != "START":
                    self.db.log_event("FINISH_IGNORED_WAITING_START", source, None, marker_id=marker_id, car_id=session["car_id"], session_id=session["id"], at_ms=at_ms)
                    return {"ok": False, "reason": "waiting_for_start"}
                self.db.start_session_and_lap(session["id"], at_ms, source)
                return {"ok": True, "action": "session_started", "session_id": session["id"]}

            if session["end_at_ms"] is not None and at_ms >= session["end_at_ms"] and not self.allow_finish_after_expiry:
                self.db.finish_session(session["id"], "time_expired", "system", at_ms)
                return {"ok": False, "reason": "time_expired"}

            if gate == "START":
                started = self.db.start_lap(session["id"], at_ms, source)
                return {"ok": started, "action": "lap_started" if started else "start_ignored", "session_id": session["id"]}

            result = self.db.finish_lap(session["id"], at_ms, source, self.min_lap_ms, self.allow_finish_after_expiry)
            return {"ok": bool(result), "action": "lap_finished" if result else "finish_ignored", "session_id": session["id"], "lap": result}
