from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum


class ActionKind(IntEnum):
    NONE = 0
    KEYBOARD = 1
    CONSUMER = 2
    MOUSE = 3
    DELAY = 5
    LED = 8


@dataclass(frozen=True)
class KeyStroke:
    modifier: int
    usage: int

    def __post_init__(self) -> None:
        if not 0 <= self.modifier <= 0xFF:
            raise ValueError("modifier 必須介於 0 到 255")
        if not 0 <= self.usage <= 0xFF:
            raise ValueError("usage 必須介於 0 到 255")


@dataclass
class Assignment:
    target: int
    layer: int = 1
    kind: ActionKind = ActionKind.NONE
    strokes: list[KeyStroke] = field(default_factory=list)
    consumer_usage: int = 0
    mouse_data: tuple[int, int, int, int, int] = (0, 0, 0, 0, 0)
    delay_ms: int = 0
    led_mode: int = 0
    led_color: int = 1

    def validate(self) -> None:
        if not 1 <= self.target <= 0xFF:
            raise ValueError("必須先選擇有效的實體按鍵或旋鈕")
        if self.layer not in (1, 2, 3):
            raise ValueError("層級只能是 1、2 或 3")
        if len(self.strokes) > 18:
            raise ValueError("新版協定最多支援 18 組按鍵；舊版最多 5 組")
        if self.kind == ActionKind.KEYBOARD and not self.strokes:
            raise ValueError("請至少加入一組鍵盤按鍵")
        if self.kind == ActionKind.CONSUMER and not 0 <= self.consumer_usage <= 0xFFFF:
            raise ValueError("多媒體 usage 超出範圍")
        if self.kind == ActionKind.DELAY and not 0 <= self.delay_ms <= 6000:
            raise ValueError("延遲必須介於 0 到 6000 ms")
        if self.kind == ActionKind.LED:
            if not 0 <= self.led_mode <= 5:
                raise ValueError("LED 模式必須介於 0 到 5")
            if not 1 <= self.led_color <= 7:
                raise ValueError("LED 顏色必須介於 1 到 7")

