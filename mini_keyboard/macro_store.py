from __future__ import annotations

import json
from pathlib import Path
from threading import RLock


TRIGGER_TARGETS: dict[str, tuple[int, int]] = {
    # label: (device target, Windows virtual-key code)
    **{f"KEY {number}": (number, 0x7B + number) for number in range(1, 7)},
}

# 旋鈕按下保留為內部觸發鍵，文字輸入選單只顯示六顆實體按鍵。
TEXT_TRIGGER_TARGETS = tuple(f"KEY {number}" for number in range(1, 7))


TRIGGER_USAGES: dict[str, int] = {
    **{f"KEY {number}": 0x67 + number for number in range(1, 7)},  # F13..F18
}


class MacroStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or Path(__file__).resolve().parent.parent / "文字巨集.json"
        self._lock = RLock()
        self._values: dict[str, str] = {label: "" for label in TRIGGER_TARGETS}
        self.load()

    def load(self) -> None:
        with self._lock:
            if not self.path.exists():
                return
            try:
                raw = json.loads(self.path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                return
            if not isinstance(raw, dict):
                return
            for label in self._values:
                value = raw.get(label, "")
                if isinstance(value, str):
                    self._values[label] = value

    def save(self) -> None:
        with self._lock:
            temporary = self.path.with_suffix(".tmp")
            temporary.write_text(
                json.dumps(self._values, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            temporary.replace(self.path)

    def get(self, label: str) -> str:
        with self._lock:
            return self._values.get(label, "")

    def set(self, label: str, text: str) -> None:
        if label not in self._values:
            raise KeyError(label)
        with self._lock:
            self._values[label] = text
            self.save()

    def by_vk(self, vk_code: int) -> tuple[str, str] | None:
        with self._lock:
            for label, (_target, target_vk) in TRIGGER_TARGETS.items():
                if target_vk == vk_code:
                    return label, self._values[label]
        return None

    def snapshot(self) -> dict[str, str]:
        with self._lock:
            return dict(self._values)
