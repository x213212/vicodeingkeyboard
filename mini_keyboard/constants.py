from __future__ import annotations

from dataclasses import dataclass


VENDOR_ID = 0x1189


@dataclass(frozen=True)
class DeviceProfile:
    product_id: int
    name: str
    protocol: int
    interface_number: int
    new_rotary_map: bool = False


DEVICE_PROFILES: dict[int, DeviceProfile] = {
    0x8890: DeviceProfile(0x8890, "MINI KeyBoard（舊協定）", 1, 1),
    0x8830: DeviceProfile(0x8830, "MINI KeyBoard 0x8830", 2, 0),
    0x8831: DeviceProfile(0x8831, "MINI KeyBoard 0x8831", 2, 0),
    0x8832: DeviceProfile(0x8832, "MINI KeyBoard 0x8832", 2, 0),
    0x8833: DeviceProfile(0x8833, "MINI KeyBoard 0x8833", 2, 0),
    0x8834: DeviceProfile(0x8834, "MINI KeyBoard 0x8834", 2, 0),
    0x8840: DeviceProfile(0x8840, "MINI KeyBoard 0x8840", 2, 0, True),
    0x8810: DeviceProfile(0x8810, "MINI KeyBoard 0x8810", 2, 0),
}


# USB HID Usage IDs.  These values are taken from the decompiled BasicKeys.cs.
KEY_CODES: dict[str, int] = {
    **{chr(ord("A") + index): 0x04 + index for index in range(26)},
    "1 / !": 0x1E,
    "2 / @": 0x1F,
    "3 / #": 0x20,
    "4 / $": 0x21,
    "5 / %": 0x22,
    "6 / ^": 0x23,
    "7 / &": 0x24,
    "8 / *": 0x25,
    "9 / (": 0x26,
    "0 / )": 0x27,
    "Enter": 0x28,
    "Esc": 0x29,
    "Backspace": 0x2A,
    "Tab": 0x2B,
    "Space": 0x2C,
    "- / _": 0x2D,
    "= / +": 0x2E,
    "[ / {": 0x2F,
    "] / }": 0x30,
    "\\ / |": 0x31,
    "; / :": 0x33,
    "' / \"": 0x34,
    "` / ~": 0x35,
    ", / <": 0x36,
    ". / >": 0x37,
    "/ / ?": 0x38,
    "Caps Lock": 0x39,
    **{f"F{index}": 0x39 + index for index in range(1, 13)},
    "Print Screen": 0x46,
    "Scroll Lock": 0x47,
    "Pause": 0x48,
    "Insert": 0x49,
    "Home": 0x4A,
    "Page Up": 0x4B,
    "Delete": 0x4C,
    "End": 0x4D,
    "Page Down": 0x4E,
    "Right": 0x4F,
    "Left": 0x50,
    "Down": 0x51,
    "Up": 0x52,
    "Num Lock": 0x53,
    "Numpad /": 0x54,
    "Numpad *": 0x55,
    "Numpad -": 0x56,
    "Numpad +": 0x57,
    "Numpad Enter": 0x58,
    **{f"Numpad {index}": 0x62 if index == 0 else 0x58 + index for index in range(10)},
    "Numpad .": 0x63,
    "Menu": 0x65,
}


MODIFIERS: dict[str, int] = {
    "左 Ctrl": 0x01,
    "左 Shift": 0x02,
    "左 Alt": 0x04,
    "左 Win": 0x08,
    "右 Ctrl": 0x10,
    "右 Shift": 0x20,
    "右 Alt": 0x40,
    "右 Win": 0x80,
}


CONSUMER_USAGES: dict[str, int] = {
    "播放 / 暫停": 0xCD,
    "上一首": 0xB6,
    "下一首": 0xB5,
    "靜音": 0xE2,
    "音量增加": 0xE9,
    "音量減少": 0xEA,
}


MOUSE_ACTIONS: dict[str, tuple[int, int, int, int, int]] = {
    # modifier, buttons, x, y, wheel
    "滑鼠左鍵": (0, 1, 0, 0, 0),
    "滑鼠中鍵": (0, 4, 0, 0, 0),
    "滑鼠右鍵": (0, 2, 0, 0, 0),
    "滾輪向上": (0, 0, 0, 0, 1),
    "滾輪向下": (0, 0, 0, 0, 0xFF),
    "Ctrl + 滾輪向上": (1, 0, 0, 0, 1),
    "Ctrl + 滾輪向下": (1, 0, 0, 0, 0xFF),
    "Shift + 滾輪向上": (2, 0, 0, 0, 1),
    "Shift + 滾輪向下": (2, 0, 0, 0, 0xFF),
    "Alt + 滾輪向上": (4, 0, 0, 0, 1),
    "Alt + 滾輪向下": (4, 0, 0, 0, 0xFF),
}


LED_MODES = {
    "模式 0": 0,
    "模式 1": 1,
    "模式 2": 2,
    "模式 3": 3,
    "模式 4": 4,
    "模式 5": 5,
}


LED_COLORS = {
    "紅色": 1,
    "橙色": 2,
    "黃色": 3,
    "綠色": 4,
    "青色": 5,
    "藍色": 6,
    "紫色": 7,
}


def rotary_targets(profile: DeviceProfile) -> list[tuple[str, int]]:
    start = 16 if profile.new_rotary_map else 13
    labels = (
        "K1 左轉", "K1 按下", "K1 右轉",
        "K2 左轉", "K2 按下", "K2 右轉",
        "K3 左轉", "K3 按下", "K3 右轉",
    )
    return [(label, start + index) for index, label in enumerate(labels)]

