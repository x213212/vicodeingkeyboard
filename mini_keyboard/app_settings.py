from __future__ import annotations

import json
from pathlib import Path
from threading import RLock
from typing import Any


DEFAULTS: dict[str, Any] = {
    "simulation": True,
    "layer": 1,
    "target": 1,
    "profile_pid": 0x8840,
    "last_tab": 0,
    "notifications": False,
    "window_width": 1240,
    "window_height": 820,
}


class AppSettings:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or Path(__file__).resolve().parent.parent / "設定檔.json"
        self._lock = RLock()
        self._values = dict(DEFAULTS)
        self.load()

    def load(self) -> None:
        with self._lock:
            if not self.path.exists():
                return
            try:
                raw = json.loads(self.path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                return
            if isinstance(raw, dict):
                for key in DEFAULTS:
                    if key in raw:
                        self._values[key] = raw[key]

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return self._values.get(key, default)

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._values[key] = value
            self.save()

    def update(self, **values: Any) -> None:
        with self._lock:
            self._values.update(values)
            self.save()

    def save(self) -> None:
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(self._values, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(self.path)
