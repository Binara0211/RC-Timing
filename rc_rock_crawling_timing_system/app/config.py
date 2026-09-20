from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "config.json"


class AppConfig:
    def __init__(self, path: Path = CONFIG_PATH):
        self.path = Path(path)
        self._lock = threading.RLock()
        self._data: dict[str, Any] = {}
        self.reload()

    def reload(self) -> dict[str, Any]:
        with self._lock:
            with self.path.open("r", encoding="utf-8") as f:
                self._data = json.load(f)
            return json.loads(json.dumps(self._data))

    def get(self) -> dict[str, Any]:
        with self._lock:
            return json.loads(json.dumps(self._data))

    def update_camera_rois(self, start_roi=None, finish_roi=None) -> dict[str, Any]:
        with self._lock:
            if start_roi is not None:
                self._data["camera"]["start_roi"] = start_roi
            if finish_roi is not None:
                self._data["camera"]["finish_roi"] = finish_roi
            tmp = self.path.with_suffix(".json.tmp")
            with tmp.open("w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2)
                f.flush()
            tmp.replace(self.path)
            return json.loads(json.dumps(self._data))
