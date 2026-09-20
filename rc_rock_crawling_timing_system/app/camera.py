from __future__ import annotations

import platform
import threading
import time
from dataclasses import dataclass
from typing import Callable

import cv2
import numpy as np


@dataclass
class GateState:
    inside_count: int = 0
    outside_count: int = 0
    latched: bool = False
    first_inside_ms: int | None = None


class CameraDetector:
    def __init__(self, config_provider: Callable[[], dict], gate_callback: Callable[..., dict]):
        self.config_provider = config_provider
        self.gate_callback = gate_callback
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None
        self.frame_lock = threading.RLock()
        self.latest_frame = None
        self.latest_annotated = None
        self.camera_ok = False
        self.last_error = ""
        self.measured_fps = 0.0
        self.seen_markers: dict[int, float] = {}
        self._states: dict[tuple[int, str], GateState] = {}
        self._cap = None

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._run, name="camera-detector", daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=3)
        if self._cap is not None:
            try:
                self._cap.release()
            except Exception:
                pass

    def _open_camera(self, cfg: dict):
        source = cfg.get("source", 0)
        backend = str(cfg.get("backend", "auto")).lower()
        api = cv2.CAP_ANY
        if isinstance(source, int) and platform.system() == "Windows":
            if backend in ("auto", "dshow"):
                api = cv2.CAP_DSHOW
            elif backend == "msmf":
                api = cv2.CAP_MSMF
        cap = cv2.VideoCapture(source, api) if isinstance(source, int) else cv2.VideoCapture(source)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, int(cfg.get("width", 1920)))
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, int(cfg.get("height", 1080)))
        cap.set(cv2.CAP_PROP_FPS, int(cfg.get("fps", 30)))
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        return cap

    @staticmethod
    def _inside_polygon(point: tuple[float, float], roi: list[list[float]]) -> bool:
        poly = np.array(roi, dtype=np.float32)
        return cv2.pointPolygonTest(poly, point, False) >= 0

    def _update_gate(self, marker_id: int, gate: str, inside: bool, enter_frames: int, release_frames: int, frame_at_ms: int):
        key = (marker_id, gate)
        st = self._states.setdefault(key, GateState())
        if inside:
            if st.inside_count == 0:
                st.first_inside_ms = frame_at_ms
            st.inside_count += 1
            st.outside_count = 0
            if not st.latched and st.inside_count >= enter_frames:
                st.latched = True
                try:
                    # Confirm using multiple frames, but timestamp the first confirmed-entry frame.
                    self.gate_callback(marker_id, gate, "camera", st.first_inside_ms or frame_at_ms)
                except Exception as e:
                    self.last_error = f"gate callback: {e}"
        else:
            st.outside_count += 1
            st.inside_count = 0
            st.first_inside_ms = None
            if st.latched and st.outside_count >= release_frames:
                st.latched = False

    def _run(self):
        frame_counter = 0
        t0 = time.perf_counter()
        detector = None
        last_dict_name = None
        while not self.stop_event.is_set():
            try:
                cfg = self.config_provider()["camera"]
                if self._cap is None or not self._cap.isOpened():
                    self._cap = self._open_camera(cfg)
                    if not self._cap.isOpened():
                        self.camera_ok = False
                        self.last_error = "Unable to open camera. Check USB connection / camera index."
                        time.sleep(1.0)
                        continue

                dict_name = cfg.get("marker_dictionary", "DICT_4X4_50")
                if detector is None or dict_name != last_dict_name:
                    dict_code = getattr(cv2.aruco, dict_name, cv2.aruco.DICT_4X4_50)
                    dictionary = cv2.aruco.getPredefinedDictionary(dict_code)
                    params = cv2.aruco.DetectorParameters()
                    params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
                    detector = cv2.aruco.ArucoDetector(dictionary, params)
                    last_dict_name = dict_name

                ok, frame = self._cap.read()
                if not ok or frame is None:
                    self.camera_ok = False
                    self.last_error = "Camera frame read failed; reconnecting."
                    self._cap.release()
                    self._cap = None
                    time.sleep(0.25)
                    continue
                self.camera_ok = True
                self.last_error = ""
                h, w = frame.shape[:2]
                proc_w = int(cfg.get("processing_width", 1280))
                if w > proc_w:
                    scale = proc_w / w
                    proc = cv2.resize(frame, (proc_w, int(h * scale)), interpolation=cv2.INTER_AREA)
                else:
                    proc = frame
                ph, pw = proc.shape[:2]
                gray = cv2.cvtColor(proc, cv2.COLOR_BGR2GRAY)
                corners, ids, _ = detector.detectMarkers(gray)
                allowed = set(int(x) for x in cfg.get("allowed_marker_ids", []))
                detected_positions: dict[int, tuple[float, float]] = {}
                draw_corners, draw_ids = [], []
                if ids is not None:
                    for c, id_arr in zip(corners, ids):
                        marker_id = int(id_arr[0])
                        pts = c.reshape(-1, 2)
                        perimeter = float(cv2.arcLength(pts.astype(np.float32), True))
                        if allowed and marker_id not in allowed:
                            continue
                        if perimeter < float(cfg.get("min_marker_perimeter_px", 55)):
                            continue
                        cx, cy = pts.mean(axis=0)
                        detected_positions[marker_id] = (float(cx / pw), float(cy / ph))
                        self.seen_markers[marker_id] = time.time()
                        draw_corners.append(c)
                        draw_ids.append([marker_id])

                enter_frames = int(cfg.get("enter_frames", 2))
                release_frames = int(cfg.get("release_frames", 4))
                frame_at_ms = int(time.time() * 1000)
                for marker_id in allowed:
                    pos = detected_positions.get(marker_id)
                    for gate, key in (("START", "start_roi"), ("FINISH", "finish_roi")):
                        roi = cfg.get(key, [])
                        inside = bool(pos and roi and self._inside_polygon(pos, roi))
                        self._update_gate(marker_id, gate, inside, enter_frames, release_frames, frame_at_ms)

                annotated = frame.copy()
                if draw_corners:
                    # Scale detected marker corners back to full-frame coordinates for display.
                    if proc is not frame:
                        sx, sy = w / pw, h / ph
                        scaled = [c.copy() for c in draw_corners]
                        for c in scaled:
                            c[:, :, 0] *= sx
                            c[:, :, 1] *= sy
                        cv2.aruco.drawDetectedMarkers(annotated, scaled, np.array(draw_ids, dtype=np.int32))
                    else:
                        cv2.aruco.drawDetectedMarkers(annotated, draw_corners, np.array(draw_ids, dtype=np.int32))
                for gate, key, color in (("START", "start_roi", (0, 220, 100)), ("FINISH", "finish_roi", (0, 150, 255))):
                    roi = cfg.get(key, [])
                    if len(roi) >= 3:
                        pts = np.array([[[int(x*w), int(y*h)] for x, y in roi]], dtype=np.int32)
                        cv2.polylines(annotated, pts, True, color, 3)
                        x0, y0 = pts[0][0]
                        cv2.putText(annotated, gate, (int(x0), max(30, int(y0)-8)), cv2.FONT_HERSHEY_SIMPLEX, 0.9, color, 2, cv2.LINE_AA)

                with self.frame_lock:
                    self.latest_frame = frame
                    self.latest_annotated = annotated

                frame_counter += 1
                elapsed = time.perf_counter() - t0
                if elapsed >= 1.0:
                    self.measured_fps = frame_counter / elapsed
                    frame_counter = 0
                    t0 = time.perf_counter()
            except Exception as e:
                self.camera_ok = False
                self.last_error = repr(e)
                time.sleep(0.5)

    def get_jpeg(self, annotated=True) -> bytes | None:
        with self.frame_lock:
            frame = self.latest_annotated if annotated else self.latest_frame
            if frame is None:
                return None
            ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
            return bytes(buf) if ok else None

    def health(self) -> dict:
        now = time.time()
        recent = sorted([mid for mid, ts in self.seen_markers.items() if now - ts < 5.0])
        return {
            "camera_ok": self.camera_ok,
            "camera_fps": round(self.measured_fps, 1),
            "camera_error": self.last_error,
            "seen_marker_ids_last_5s": recent,
        }
