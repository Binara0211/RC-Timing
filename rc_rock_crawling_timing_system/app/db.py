from __future__ import annotations

import csv
import sqlite3
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterator
from zoneinfo import ZoneInfo


SCHEMA = """
CREATE TABLE IF NOT EXISTS customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    phone TEXT,
    created_at_ms INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_customers_phone ON customers(phone);

CREATE TABLE IF NOT EXISTS cars (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    marker_id INTEGER NOT NULL UNIQUE,
    active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    car_id INTEGER NOT NULL REFERENCES cars(id),
    duration_sec INTEGER NOT NULL,
    status TEXT NOT NULL,
    prepared_at_ms INTEGER NOT NULL,
    start_at_ms INTEGER,
    end_at_ms INTEGER,
    finished_at_ms INTEGER,
    current_lap_start_ms INTEGER,
    lap_count INTEGER NOT NULL DEFAULT 0,
    best_lap_ms INTEGER,
    last_lap_ms INTEGER,
    finish_reason TEXT,
    created_by TEXT NOT NULL DEFAULT 'operator'
);
CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status);
CREATE INDEX IF NOT EXISTS idx_sessions_start ON sessions(start_at_ms);
CREATE INDEX IF NOT EXISTS idx_sessions_car ON sessions(car_id);

CREATE TABLE IF NOT EXISTS laps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES sessions(id),
    lap_no INTEGER NOT NULL,
    start_at_ms INTEGER NOT NULL,
    finish_at_ms INTEGER NOT NULL,
    lap_ms INTEGER NOT NULL,
    valid INTEGER NOT NULL DEFAULT 1,
    source TEXT NOT NULL DEFAULT 'camera'
);
CREATE INDEX IF NOT EXISTS idx_laps_session ON laps(session_id);
CREATE INDEX IF NOT EXISTS idx_laps_finish ON laps(finish_at_ms);
CREATE INDEX IF NOT EXISTS idx_laps_time ON laps(lap_ms);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    at_ms INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    marker_id INTEGER,
    car_id INTEGER,
    session_id INTEGER,
    source TEXT NOT NULL,
    detail TEXT
);
CREATE INDEX IF NOT EXISTS idx_events_at ON events(at_ms);

CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


class Database:
    def __init__(self, path: Path, timezone: str = "Asia/Colombo"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.tz = ZoneInfo(timezone)
        self._write_lock = threading.RLock()
        self.initialize()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=10000")
        return conn

    @contextmanager
    def tx(self) -> Iterator[sqlite3.Connection]:
        with self._write_lock:
            conn = self._connect()
            try:
                conn.execute("BEGIN IMMEDIATE")
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

    def initialize(self) -> None:
        conn = self._connect()
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=FULL")
            conn.executescript(SCHEMA)
            conn.commit()
            for marker_id in range(1, 8):
                conn.execute(
                    "INSERT OR IGNORE INTO cars(name, marker_id, active) VALUES (?, ?, 1)",
                    (f"RC-{marker_id}", marker_id),
                )
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def now_ms() -> int:
        return int(time.time() * 1000)

    def get_or_create_customer(self, conn: sqlite3.Connection, name: str, phone: str | None, now_ms: int) -> int:
        name = " ".join(name.split()).strip()
        phone = (phone or "").strip() or None
        if phone:
            row = conn.execute("SELECT id FROM customers WHERE phone=? ORDER BY id DESC LIMIT 1", (phone,)).fetchone()
            if row:
                conn.execute("UPDATE customers SET name=? WHERE id=?", (name, row["id"]))
                return int(row["id"])
        cur = conn.execute(
            "INSERT INTO customers(name, phone, created_at_ms) VALUES (?, ?, ?)",
            (name, phone, now_ms),
        )
        return int(cur.lastrowid)

    def list_cars(self) -> list[dict[str, Any]]:
        conn = self._connect()
        try:
            return [dict(r) for r in conn.execute("SELECT * FROM cars WHERE active=1 ORDER BY marker_id")]
        finally:
            conn.close()

    def prepare_session(self, customer_name: str, phone: str | None, car_id: int, duration_sec: int, created_by="operator") -> dict[str, Any]:
        now = self.now_ms()
        if not customer_name.strip():
            raise ValueError("Customer name is required")
        if duration_sec < 60 or duration_sec > 7200:
            raise ValueError("Session duration must be between 1 and 120 minutes")
        with self.tx() as conn:
            car = conn.execute("SELECT * FROM cars WHERE id=? AND active=1", (car_id,)).fetchone()
            if not car:
                raise ValueError("Car not found")
            existing = conn.execute(
                "SELECT id FROM sessions WHERE car_id=? AND status IN ('prepared','running') LIMIT 1", (car_id,)
            ).fetchone()
            if existing:
                raise ValueError("This car already has an active/prepared session")
            customer_id = self.get_or_create_customer(conn, customer_name, phone, now)
            cur = conn.execute(
                """INSERT INTO sessions(customer_id, car_id, duration_sec, status, prepared_at_ms, created_by)
                   VALUES (?, ?, ?, 'prepared', ?, ?)""",
                (customer_id, car_id, duration_sec, now, created_by),
            )
            sid = int(cur.lastrowid)
            self._log_event_conn(conn, now, "SESSION_PREPARED", car["marker_id"], car_id, sid, created_by, customer_name)
        return self.get_session(sid)

    def get_session(self, session_id: int) -> dict[str, Any]:
        conn = self._connect()
        try:
            row = conn.execute(
                """SELECT s.*, c.name AS customer_name, c.phone, car.name AS car_name, car.marker_id
                   FROM sessions s JOIN customers c ON c.id=s.customer_id JOIN cars car ON car.id=s.car_id
                   WHERE s.id=?""",
                (session_id,),
            ).fetchone()
            if not row:
                raise ValueError("Session not found")
            return dict(row)
        finally:
            conn.close()

    def get_active_session_by_marker(self, marker_id: int) -> dict[str, Any] | None:
        conn = self._connect()
        try:
            row = conn.execute(
                """SELECT s.*, c.name AS customer_name, c.phone, car.name AS car_name, car.marker_id
                   FROM sessions s JOIN customers c ON c.id=s.customer_id JOIN cars car ON car.id=s.car_id
                   WHERE car.marker_id=? AND s.status IN ('prepared','running') ORDER BY s.id DESC LIMIT 1""",
                (marker_id,),
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_live_sessions(self) -> list[dict[str, Any]]:
        conn = self._connect()
        try:
            rows = conn.execute(
                """SELECT s.*, c.name AS customer_name, c.phone, car.name AS car_name, car.marker_id
                   FROM sessions s JOIN customers c ON c.id=s.customer_id JOIN cars car ON car.id=s.car_id
                   WHERE s.status IN ('prepared','running') ORDER BY car.marker_id"""
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def start_session_and_lap(self, session_id: int, at_ms: int, source: str) -> None:
        with self.tx() as conn:
            row = conn.execute(
                """SELECT s.*, car.marker_id FROM sessions s JOIN cars car ON car.id=s.car_id WHERE s.id=?""",
                (session_id,),
            ).fetchone()
            if not row or row["status"] != "prepared":
                return
            end_at = at_ms + int(row["duration_sec"]) * 1000
            conn.execute(
                """UPDATE sessions SET status='running', start_at_ms=?, end_at_ms=?, current_lap_start_ms=? WHERE id=?""",
                (at_ms, end_at, at_ms, session_id),
            )
            self._log_event_conn(conn, at_ms, "SESSION_STARTED", row["marker_id"], row["car_id"], session_id, source, None)
            self._log_event_conn(conn, at_ms, "LAP_STARTED", row["marker_id"], row["car_id"], session_id, source, "lap=1")

    def start_lap(self, session_id: int, at_ms: int, source: str) -> bool:
        with self.tx() as conn:
            row = conn.execute(
                """SELECT s.*, car.marker_id FROM sessions s JOIN cars car ON car.id=s.car_id WHERE s.id=?""", (session_id,)
            ).fetchone()
            if not row or row["status"] != "running" or row["current_lap_start_ms"] is not None:
                return False
            if row["end_at_ms"] is not None and at_ms >= row["end_at_ms"]:
                return False
            conn.execute("UPDATE sessions SET current_lap_start_ms=? WHERE id=?", (at_ms, session_id))
            self._log_event_conn(
                conn, at_ms, "LAP_STARTED", row["marker_id"], row["car_id"], session_id, source, f"lap={int(row['lap_count'])+1}"
            )
            return True

    def finish_lap(self, session_id: int, at_ms: int, source: str, min_lap_ms: int, allow_after_expiry: bool) -> dict[str, Any] | None:
        with self.tx() as conn:
            row = conn.execute(
                """SELECT s.*, car.marker_id FROM sessions s JOIN cars car ON car.id=s.car_id WHERE s.id=?""", (session_id,)
            ).fetchone()
            if not row or row["status"] != "running" or row["current_lap_start_ms"] is None:
                return None
            if not allow_after_expiry and row["end_at_ms"] is not None and at_ms > row["end_at_ms"]:
                self._log_event_conn(conn, at_ms, "FINISH_REJECTED_TIME_EXPIRED", row["marker_id"], row["car_id"], session_id, source, None)
                return None
            lap_ms = at_ms - int(row["current_lap_start_ms"])
            if lap_ms < min_lap_ms:
                self._log_event_conn(conn, at_ms, "FINISH_REJECTED_TOO_FAST", row["marker_id"], row["car_id"], session_id, source, f"lap_ms={lap_ms}")
                return None
            lap_no = int(row["lap_count"]) + 1
            conn.execute(
                """INSERT INTO laps(session_id, lap_no, start_at_ms, finish_at_ms, lap_ms, valid, source)
                   VALUES (?, ?, ?, ?, ?, 1, ?)""",
                (session_id, lap_no, row["current_lap_start_ms"], at_ms, lap_ms, source),
            )
            best = lap_ms if row["best_lap_ms"] is None else min(int(row["best_lap_ms"]), lap_ms)
            conn.execute(
                """UPDATE sessions SET lap_count=?, best_lap_ms=?, last_lap_ms=?, current_lap_start_ms=NULL WHERE id=?""",
                (lap_no, best, lap_ms, session_id),
            )
            self._log_event_conn(conn, at_ms, "LAP_FINISHED", row["marker_id"], row["car_id"], session_id, source, f"lap={lap_no};lap_ms={lap_ms}")
            return {"lap_no": lap_no, "lap_ms": lap_ms, "best_lap_ms": best}

    def finish_session(self, session_id: int, reason: str, source="system", at_ms: int | None = None) -> None:
        at_ms = at_ms or self.now_ms()
        with self.tx() as conn:
            row = conn.execute(
                """SELECT s.*, car.marker_id FROM sessions s JOIN cars car ON car.id=s.car_id WHERE s.id=?""", (session_id,)
            ).fetchone()
            if not row or row["status"] not in ("prepared", "running"):
                return
            status = "finished" if reason != "cancelled" else "cancelled"
            conn.execute(
                "UPDATE sessions SET status=?, finished_at_ms=?, finish_reason=?, current_lap_start_ms=NULL WHERE id=?",
                (status, at_ms, reason, session_id),
            )
            self._log_event_conn(conn, at_ms, "SESSION_FINISHED" if status == "finished" else "SESSION_CANCELLED", row["marker_id"], row["car_id"], session_id, source, reason)

    def expire_sessions(self, now_ms: int | None = None) -> int:
        now_ms = now_ms or self.now_ms()
        conn = self._connect()
        try:
            ids = [r[0] for r in conn.execute(
                "SELECT id FROM sessions WHERE status='running' AND end_at_ms IS NOT NULL AND end_at_ms<=?", (now_ms,)
            ).fetchall()]
        finally:
            conn.close()
        for sid in ids:
            self.finish_session(int(sid), "time_expired", "system", now_ms)
        return len(ids)

    def recover(self) -> dict[str, int]:
        now = self.now_ms()
        expired = self.expire_sessions(now)
        conn = self._connect()
        try:
            running = conn.execute("SELECT COUNT(*) FROM sessions WHERE status='running'").fetchone()[0]
            prepared = conn.execute("SELECT COUNT(*) FROM sessions WHERE status='prepared'").fetchone()[0]
        finally:
            conn.close()
        return {"expired": int(expired), "running": int(running), "prepared": int(prepared)}

    def _period_start_ms(self, period: str, now_ms: int | None = None) -> int:
        now = datetime.fromtimestamp((now_ms or self.now_ms()) / 1000, tz=self.tz)
        if period == "today":
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == "week":
            start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == "month":
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        elif period == "all":
            return 0
        else:
            raise ValueError("period must be today, week, month or all")
        return int(start.timestamp() * 1000)

    def leaderboard_fastest(self, period: str, limit: int = 10) -> list[dict[str, Any]]:
        start = self._period_start_ms(period)
        conn = self._connect()
        try:
            rows = conn.execute(
                """SELECT c.name AS customer_name, car.name AS car_name, car.marker_id, l.lap_ms, l.finish_at_ms, s.id AS session_id
                   FROM laps l JOIN sessions s ON s.id=l.session_id JOIN customers c ON c.id=s.customer_id JOIN cars car ON car.id=s.car_id
                   WHERE l.valid=1 AND l.finish_at_ms>=?
                   ORDER BY l.lap_ms ASC, l.finish_at_ms ASC LIMIT ?""",
                (start, limit),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def leaderboard_laps(self, period: str, limit: int = 10) -> list[dict[str, Any]]:
        start = self._period_start_ms(period)
        conn = self._connect()
        try:
            rows = conn.execute(
                """SELECT c.name AS customer_name, car.name AS car_name, car.marker_id, s.lap_count, s.best_lap_ms, s.start_at_ms, s.id AS session_id
                   FROM sessions s JOIN customers c ON c.id=s.customer_id JOIN cars car ON car.id=s.car_id
                   WHERE s.start_at_ms IS NOT NULL AND s.start_at_ms>=?
                   ORDER BY s.lap_count DESC, COALESCE(s.best_lap_ms, 999999999) ASC, s.start_at_ms ASC LIMIT ?""",
                (start, limit),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def recent_finished(self, limit=20) -> list[dict[str, Any]]:
        conn = self._connect()
        try:
            rows = conn.execute(
                """SELECT s.*, c.name AS customer_name, car.name AS car_name, car.marker_id
                   FROM sessions s JOIN customers c ON c.id=s.customer_id JOIN cars car ON car.id=s.car_id
                   WHERE s.status IN ('finished','cancelled') ORDER BY s.finished_at_ms DESC LIMIT ?""", (limit,)
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def backup_to(self, destination: Path) -> Path:
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        src = self._connect()
        dst = sqlite3.connect(destination)
        try:
            src.backup(dst)
            dst.commit()
        finally:
            dst.close()
            src.close()
        return destination

    def integrity_check(self) -> str:
        conn = self._connect()
        try:
            return str(conn.execute("PRAGMA integrity_check").fetchone()[0])
        finally:
            conn.close()

    def export_day_csv(self, export_dir: Path, now_ms: int | None = None) -> tuple[Path, Path]:
        export_dir = Path(export_dir)
        export_dir.mkdir(parents=True, exist_ok=True)
        start = self._period_start_ms("today", now_ms)
        dt = datetime.fromtimestamp((now_ms or self.now_ms()) / 1000, tz=self.tz)
        end = int((dt.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)).timestamp() * 1000)
        stamp = dt.strftime("%Y-%m-%d")
        sessions_path = export_dir / f"sessions_{stamp}.csv"
        laps_path = export_dir / f"laps_{stamp}.csv"
        conn = self._connect()
        try:
            sessions = conn.execute(
                """SELECT s.id, c.name customer_name, c.phone, car.name car_name, car.marker_id,
                          s.status, s.duration_sec, s.prepared_at_ms, s.start_at_ms, s.end_at_ms,
                          s.finished_at_ms, s.lap_count, s.best_lap_ms, s.last_lap_ms, s.finish_reason
                   FROM sessions s JOIN customers c ON c.id=s.customer_id JOIN cars car ON car.id=s.car_id
                   WHERE s.prepared_at_ms>=? AND s.prepared_at_ms<? ORDER BY s.id""", (start, end)
            ).fetchall()
            laps = conn.execute(
                """SELECT l.id, l.session_id, c.name customer_name, car.name car_name, car.marker_id,
                          l.lap_no, l.start_at_ms, l.finish_at_ms, l.lap_ms, l.source
                   FROM laps l JOIN sessions s ON s.id=l.session_id JOIN customers c ON c.id=s.customer_id JOIN cars car ON car.id=s.car_id
                   WHERE l.finish_at_ms>=? AND l.finish_at_ms<? ORDER BY l.id""", (start, end)
            ).fetchall()
        finally:
            conn.close()
        self._write_csv(sessions_path, sessions)
        self._write_csv(laps_path, laps)
        return sessions_path, laps_path

    @staticmethod
    def _write_csv(path: Path, rows: list[sqlite3.Row]) -> None:
        with path.open("w", newline="", encoding="utf-8-sig") as f:
            if not rows:
                f.write("")
                return
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            for row in rows:
                writer.writerow(dict(row))

    def _log_event_conn(self, conn: sqlite3.Connection, at_ms: int, event_type: str, marker_id, car_id, session_id, source: str, detail: str | None) -> None:
        conn.execute(
            "INSERT INTO events(at_ms,event_type,marker_id,car_id,session_id,source,detail) VALUES (?,?,?,?,?,?,?)",
            (at_ms, event_type, marker_id, car_id, session_id, source, detail),
        )

    def log_event(self, event_type: str, source: str, detail: str | None = None, marker_id=None, car_id=None, session_id=None, at_ms=None) -> None:
        with self.tx() as conn:
            self._log_event_conn(conn, at_ms or self.now_ms(), event_type, marker_id, car_id, session_id, source, detail)
