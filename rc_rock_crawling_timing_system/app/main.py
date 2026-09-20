from __future__ import annotations

import json
import shutil
import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .camera import CameraDetector
from .config import AppConfig, ROOT
from .db import Database
from .timing import TimingEngine

config = AppConfig()
cfg = config.get()
DATA_DIR = ROOT / "data"
BACKUP_DIR = ROOT / "backups"
EXPORT_DIR = ROOT / "exports"
LOG_DIR = ROOT / "logs"
DB_PATH = DATA_DIR / "rc_timing.db"
for p in (DATA_DIR, BACKUP_DIR, EXPORT_DIR, LOG_DIR):
    p.mkdir(parents=True, exist_ok=True)

db = Database(DB_PATH, cfg.get("timezone", "Asia/Colombo"))
timing = TimingEngine(db, cfg.get("min_lap_seconds", 5.0), cfg.get("allow_finish_after_time_expired", False))

def camera_provider(role: str):
    def provider():
        full = config.get()
        c = dict(full["camera"])
        finish_source = c.get("finish_source", None)
        dual = finish_source is not None and finish_source != c.get("source")
        if dual and role == "start":
            c["finish_roi"] = []
        elif dual and role == "finish":
            c["source"] = finish_source
            c["start_roi"] = []
        return {**full, "camera": c}
    return provider

camera_start = CameraDetector(camera_provider("start"), timing.handle_gate)
_finish_source = cfg.get("camera", {}).get("finish_source", None)
_dual_camera = _finish_source is not None and _finish_source != cfg.get("camera", {}).get("source")
camera_finish = CameraDetector(camera_provider("finish"), timing.handle_gate) if _dual_camera else None
stop_services = threading.Event()
last_backup: dict = {"at_ms": None, "path": None, "secondary": None, "error": None}


def perform_backup() -> dict:
    global last_backup
    try:
        now = datetime.now()
        stamp = now.strftime("%Y%m%d_%H%M%S")
        dest = BACKUP_DIR / f"rc_timing_{stamp}.db"
        db.backup_to(dest)
        secondary = None
        bcfg = config.get().get("backup", {})
        secondary_dir = str(bcfg.get("secondary_directory", "")).strip()
        if secondary_dir:
            sec_dir = Path(secondary_dir)
            if sec_dir.exists():
                sec = sec_dir / dest.name
                sec.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(dest, sec)
                secondary = str(sec)
        # retention
        keep_days = int(bcfg.get("keep_days", 45))
        cutoff = time.time() - keep_days * 86400
        for old in BACKUP_DIR.glob("rc_timing_*.db"):
            if old.stat().st_mtime < cutoff:
                old.unlink(missing_ok=True)
        last_backup = {"at_ms": db.now_ms(), "path": str(dest), "secondary": secondary, "error": None}
        return last_backup
    except Exception as e:
        last_backup = {"at_ms": db.now_ms(), "path": None, "secondary": None, "error": repr(e)}
        return last_backup


def housekeeping_loop():
    last_b = 0.0
    while not stop_services.wait(0.5):
        try:
            db.expire_sessions()
            interval = max(5, int(config.get().get("backup", {}).get("interval_minutes", 60))) * 60
            if time.monotonic() - last_b >= interval:
                perform_backup()
                last_b = time.monotonic()
        except Exception as e:
            db.log_event("HOUSEKEEPING_ERROR", "system", repr(e))


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.recover()
    perform_backup()
    camera_start.start()
    if camera_finish:
        camera_finish.start()
    stop_services.clear()
    worker = threading.Thread(target=housekeeping_loop, name="housekeeping", daemon=True)
    worker.start()
    yield
    stop_services.set()
    camera_start.stop()
    if camera_finish:
        camera_finish.stop()
    perform_backup()


app = FastAPI(title="RC Rock Crawling Timing System", docs_url=None, redoc_url=None, lifespan=lifespan)

@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
        "script-src 'self' 'unsafe-inline'; connect-src 'self'; object-src 'none'; "
        "base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
    )
    if request.url.path.startswith("/api/") or request.url.path in {"/", "/operator", "/tv", "/settings"}:
        response.headers["Cache-Control"] = "no-store"
    return response
app.mount("/static", StaticFiles(directory=ROOT / "app" / "static"), name="static")
app.mount("/exports", StaticFiles(directory=EXPORT_DIR), name="exports")


def page(name: str) -> HTMLResponse:
    p = ROOT / "app" / "templates" / name
    return HTMLResponse(p.read_text(encoding="utf-8"))


@app.get("/", response_class=HTMLResponse)
def root():
    return page("operator.html")


@app.get("/operator", response_class=HTMLResponse)
def operator():
    return page("operator.html")


@app.get("/tv", response_class=HTMLResponse)
def tv():
    return page("tv.html")


@app.get("/settings", response_class=HTMLResponse)
def settings():
    return page("settings.html")


class PrepareRequest(BaseModel):
    customer_name: str = Field(min_length=1, max_length=80)
    phone: str | None = Field(default=None, max_length=30)
    car_id: int = Field(ge=1)
    duration_minutes: int = Field(default=15, ge=1, le=120)


class ManualEvent(BaseModel):
    marker_id: int = Field(ge=1, le=999)
    gate: Literal["START", "FINISH"]


class RoiRequest(BaseModel):
    start_roi: list[list[float]] | None = None
    finish_roi: list[list[float]] | None = None


@app.get("/api/config")
def get_config():
    return config.get()


@app.get("/api/cars")
def cars():
    return db.list_cars()


@app.post("/api/sessions")
def create_session(req: PrepareRequest):
    try:
        return db.prepare_session(req.customer_name, req.phone, req.car_id, req.duration_minutes * 60)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/sessions/{session_id}/cancel")
def cancel_session(session_id: int):
    try:
        db.finish_session(session_id, "cancelled", "operator")
        return {"ok": True}
    except Exception as e:
        raise HTTPException(400, str(e))


@app.post("/api/sessions/{session_id}/finish")
def finish_session(session_id: int):
    try:
        db.finish_session(session_id, "operator_finished", "operator")
        return {"ok": True}
    except Exception as e:
        raise HTTPException(400, str(e))


@app.post("/api/manual-event")
def manual_event(req: ManualEvent):
    allowed = set(config.get().get("camera", {}).get("allowed_marker_ids", []))
    if req.marker_id not in allowed:
        raise HTTPException(400, "Unknown or disabled marker ID")
    try:
        return timing.handle_gate(req.marker_id, req.gate, "manual")
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/api/live")
def live():
    now = db.now_ms()
    sessions = db.list_live_sessions()
    for s in sessions:
        if s["status"] == "running" and s["end_at_ms"]:
            s["remaining_ms"] = max(0, int(s["end_at_ms"]) - now)
            if s["current_lap_start_ms"]:
                s["current_lap_ms"] = max(0, now - int(s["current_lap_start_ms"]))
            else:
                s["current_lap_ms"] = None
        else:
            s["remaining_ms"] = int(s["duration_sec"]) * 1000
            s["current_lap_ms"] = None
    return {"now_ms": now, "sessions": sessions}


@app.get("/api/leaderboard")
def leaderboard(period: Literal["today", "week", "month", "all"] = "today", limit: int = Query(default=10, ge=1, le=100)):
    try:
        return {
            "period": period,
            "fastest": db.leaderboard_fastest(period, limit),
            "most_laps": db.leaderboard_laps(period, limit),
        }
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/api/recent")
def recent(limit: int = Query(default=20, ge=1, le=100)):
    return db.recent_finished(limit)


@app.get("/api/health")
def health():
    start_h = camera_start.health()
    finish_h = camera_finish.health() if camera_finish else start_h
    integrity = db.integrity_check()
    seen = sorted(set(start_h.get("seen_marker_ids_last_5s", [])) | set(finish_h.get("seen_marker_ids_last_5s", [])))
    return {
        "camera_ok": bool(start_h.get("camera_ok")) and bool(finish_h.get("camera_ok")),
        "camera_fps": start_h.get("camera_fps"),
        "camera_error": start_h.get("camera_error") or finish_h.get("camera_error"),
        "seen_marker_ids_last_5s": seen,
        "dual_camera": bool(camera_finish),
        "start_camera": start_h,
        "finish_camera": finish_h,
        "db_ok": integrity == "ok",
        "db_integrity": integrity,
        "last_backup": last_backup,
        "server_time_ms": db.now_ms(),
        "version": "2.0.0"
    }


@app.post("/api/backup")
def backup():
    result = perform_backup()
    if result.get("error"):
        return JSONResponse(result, status_code=500)
    return result


@app.post("/api/day-close")
def day_close():
    sessions_csv, laps_csv = db.export_day_csv(EXPORT_DIR)
    backup_result = perform_backup()
    return {
        "ok": not bool(backup_result.get("error")),
        "sessions_csv": f"/exports/{sessions_csv.name}",
        "laps_csv": f"/exports/{laps_csv.name}",
        "backup": backup_result,
    }


@app.post("/api/config/rois")
def save_rois(req: RoiRequest):
    def valid(poly):
        return poly is None or (3 <= len(poly) <= 12 and all(len(p) == 2 and 0 <= p[0] <= 1 and 0 <= p[1] <= 1 for p in poly))
    if not valid(req.start_roi) or not valid(req.finish_roi):
        raise HTTPException(400, "Each ROI must contain 3-12 normalized [x,y] points between 0 and 1")
    return config.update_camera_rois(req.start_roi, req.finish_roi)


def _camera_stream_response(detector: CameraDetector):
    def gen():
        while True:
            jpg = detector.get_jpeg(annotated=True)
            if jpg:
                yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpg + b"\r\n"
            time.sleep(0.08)
    return StreamingResponse(gen(), media_type="multipart/x-mixed-replace; boundary=frame")


@app.get("/camera.mjpg")
def camera_stream():
    return _camera_stream_response(camera_start)


@app.get("/camera/{which}.mjpg")
def camera_stream_named(which: str):
    if which == "start":
        return _camera_stream_response(camera_start)
    if which == "finish":
        return _camera_stream_response(camera_finish or camera_start)
    raise HTTPException(404, "Camera view not found")
