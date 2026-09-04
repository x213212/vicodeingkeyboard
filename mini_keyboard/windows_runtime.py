from __future__ import annotations

import ctypes
import queue
import sys
import threading
import time
from ctypes import wintypes
from typing import Callable

from .macro_store import MacroStore, TEXT_TRIGGER_TARGETS, TRIGGER_TARGETS


WH_KEYBOARD_LL = 13
HC_ACTION = 0
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105
WM_QUIT = 0x0012
LLKHF_INJECTED = 0x10
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
INPUT_KEYBOARD = 1
VK_VOLUME_DOWN = 0xAE
VK_VOLUME_UP = 0xAF
VK_VOLUME_MUTE = 0xAD
VK_RETURN = 0x0D


if sys.platform == "win32":
    ULONG_PTR = wintypes.WPARAM

    class KBDLLHOOKSTRUCT(ctypes.Structure):
        _fields_ = [
            ("vkCode", wintypes.DWORD),
            ("scanCode", wintypes.DWORD),
            ("flags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", ULONG_PTR),
        ]

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [
            ("wVk", wintypes.WORD),
            ("wScan", wintypes.WORD),
            ("dwFlags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", ULONG_PTR),
        ]

    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [
            ("dx", wintypes.LONG),
            ("dy", wintypes.LONG),
            ("mouseData", wintypes.DWORD),
            ("dwFlags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", ULONG_PTR),
        ]

    class HARDWAREINPUT(ctypes.Structure):
        _fields_ = [
            ("uMsg", wintypes.DWORD),
            ("wParamL", wintypes.WORD),
            ("wParamH", wintypes.WORD),
        ]

    class INPUT_UNION(ctypes.Union):
        _fields_ = [
            ("ki", KEYBDINPUT),
            ("mi", MOUSEINPUT),
            ("hi", HARDWAREINPUT),
        ]

    class INPUT(ctypes.Structure):
        _anonymous_ = ("union",)
        _fields_ = [("type", wintypes.DWORD), ("union", INPUT_UNION)]

    HOOKPROC = ctypes.WINFUNCTYPE(
        ctypes.c_ssize_t,
        ctypes.c_int,
        wintypes.WPARAM,
        wintypes.LPARAM,
    )


class WindowsMacroRuntime:
    """Low-level Windows hook for text triggers and accelerated volume."""

    def __init__(
        self,
        store: MacroStore,
        status_callback: Callable[[str], None] | None = None,
    ) -> None:
        self.store = store
        self.status_callback = status_callback
        self.paused = False
        self._hook = None
        self._hook_proc = None
        self._hook_thread: threading.Thread | None = None
        self._worker_thread: threading.Thread | None = None
        self._hook_thread_id = 0
        self._stop = threading.Event()
        self._tasks: queue.Queue[tuple[str, object]] = queue.Queue()
        self._last_volume: dict[int, float] = {}
        self._knob_lock = threading.Lock()
        self._knob_timer: threading.Timer | None = None
        self._last_knob_press = 0.0
        self._knob_key_down = False
        self._muted_by_knob = False

    @property
    def running(self) -> bool:
        return self._hook is not None and not self._stop.is_set()

    def start(self) -> None:
        if sys.platform != "win32":
            raise RuntimeError("文字巨集常駐功能目前只支援 Windows")
        if self._hook_thread and self._hook_thread.is_alive():
            return
        self._stop.clear()
        self._worker_thread = threading.Thread(target=self._worker_loop, name="macro-worker", daemon=True)
        self._hook_thread = threading.Thread(target=self._hook_loop, name="keyboard-hook", daemon=True)
        self._worker_thread.start()
        self._hook_thread.start()

    def stop(self) -> None:
        self._stop.set()
        with self._knob_lock:
            if self._knob_timer:
                self._knob_timer.cancel()
                self._knob_timer = None
        self._tasks.put(("stop", None))
        if self._hook_thread_id:
            ctypes.windll.user32.PostThreadMessageW(self._hook_thread_id, WM_QUIT, 0, 0)
        if self._hook_thread:
            self._hook_thread.join(timeout=2)
        if self._worker_thread:
            self._worker_thread.join(timeout=2)

    def _hook_loop(self) -> None:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD]
        user32.SetWindowsHookExW.restype = wintypes.HHOOK
        user32.CallNextHookEx.argtypes = [wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
        user32.CallNextHookEx.restype = ctypes.c_ssize_t
        user32.UnhookWindowsHookEx.argtypes = [wintypes.HHOOK]
        user32.UnhookWindowsHookEx.restype = wintypes.BOOL
        self._hook_thread_id = kernel32.GetCurrentThreadId()
        trigger_vks = {TRIGGER_TARGETS[label][1] for label in TEXT_TRIGGER_TARGETS}

        def callback(code: int, message: int, data_pointer: int) -> int:
            if code == HC_ACTION:
                data = ctypes.cast(data_pointer, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
                vk_code = int(data.vkCode)
                injected = bool(data.flags & LLKHF_INJECTED)
                is_down = message in (WM_KEYDOWN, WM_SYSKEYDOWN)
                is_up = message in (WM_KEYUP, WM_SYSKEYUP)

                if not injected and vk_code == VK_VOLUME_MUTE:
                    if not self.paused and is_down and not self._knob_key_down:
                        self._knob_key_down = True
                        self._register_knob_press()
                    elif is_up:
                        self._knob_key_down = False
                    if not self.paused and (is_down or is_up):
                        return 1

                if not injected and vk_code in trigger_vks:
                    if not self.paused and is_down:
                        found = self.store.by_vk(vk_code)
                        if found:
                            label, text = found
                            if text:
                                self._tasks.put(("text", (label, text)))
                    if not self.paused and (is_down or is_up):
                        return 1

                if not injected and vk_code in (VK_VOLUME_DOWN, VK_VOLUME_UP):
                    if not self.paused and is_down:
                        self._tasks.put(("volume", vk_code))
                    if not self.paused and (is_down or is_up):
                        return 1

            return user32.CallNextHookEx(self._hook, code, message, data_pointer)

        self._hook_proc = HOOKPROC(callback)
        self._hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL, self._hook_proc, None, 0)
        if not self._hook:
            self._notify("背景鍵盤監聽啟動失敗")
            return
        self._notify("文字巨集常駐中")
        message = wintypes.MSG()
        while not self._stop.is_set() and user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(message))
            user32.DispatchMessageW(ctypes.byref(message))
        if self._hook:
            user32.UnhookWindowsHookEx(self._hook)
        self._hook = None

    def _worker_loop(self) -> None:
        while not self._stop.is_set():
            try:
                kind, value = self._tasks.get(timeout=0.5)
            except queue.Empty:
                continue
            if kind == "stop":
                return
            if kind == "text":
                label, text = value  # type: ignore[misc]
                time.sleep(0.035)
                self._send_unicode(str(text))
                time.sleep(0.025)
                self._send_virtual_key(VK_RETURN)
                self._notify(f"{label}：已輸入文字並按 Enter")
            elif kind == "volume":
                self._restore_knob_volume()
                self._send_accelerated_volume(int(value))
            elif kind == "knob_single":
                if not self._muted_by_knob:
                    self._send_virtual_key(VK_VOLUME_MUTE)
                    self._muted_by_knob = True
                self._notify("旋鈕：已靜音（保留原音量）")
            elif kind == "knob_double":
                self._restore_knob_volume()

    def _register_knob_press(self) -> None:
        now = time.monotonic()
        with self._knob_lock:
            if self._knob_timer and now - self._last_knob_press <= 0.36:
                self._knob_timer.cancel()
                self._knob_timer = None
                self._last_knob_press = 0.0
                self._tasks.put(("knob_double", None))
                return
            if self._knob_timer:
                self._knob_timer.cancel()
                self._tasks.put(("knob_single", None))
            self._last_knob_press = now
            self._knob_timer = threading.Timer(0.36, self._commit_knob_single)
            self._knob_timer.daemon = True
            self._knob_timer.start()

    def _commit_knob_single(self) -> None:
        with self._knob_lock:
            self._knob_timer = None
            self._last_knob_press = 0.0
        if not self._stop.is_set():
            self._tasks.put(("knob_single", None))

    def _restore_knob_volume(self) -> None:
        if self._muted_by_knob:
            self._send_virtual_key(VK_VOLUME_MUTE)
            self._muted_by_knob = False
            time.sleep(0.025)
            self._notify("旋鈕：已恢復靜音前音量")

    def _send_unicode(self, text: str) -> None:
        if not text:
            return
        units = [
            int.from_bytes(encoded[index:index + 2], "little")
            for encoded in (text.encode("utf-16-le"),)
            for index in range(0, len(encoded), 2)
        ]
        events: list[INPUT] = []
        for unit in units:
            events.append(INPUT(type=INPUT_KEYBOARD, ki=KEYBDINPUT(0, unit, KEYEVENTF_UNICODE, 0, 0)))
            events.append(INPUT(type=INPUT_KEYBOARD, ki=KEYBDINPUT(0, unit, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, 0, 0)))
        array_type = INPUT * len(events)
        event_array = array_type(*events)
        user32 = ctypes.windll.user32
        user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
        user32.SendInput.restype = wintypes.UINT
        sent = user32.SendInput(len(events), event_array, ctypes.sizeof(INPUT))
        if sent != len(events):
            self._notify("文字輸入未完整送出")

    def _send_accelerated_volume(self, vk_code: int) -> None:
        now = time.monotonic()
        elapsed = now - self._last_volume.get(vk_code, 0.0)
        self._last_volume[vk_code] = now
        if elapsed < 0.075:
            steps = 5
        elif elapsed < 0.14:
            steps = 3
        elif elapsed < 0.28:
            steps = 2
        else:
            steps = 1
        user32 = ctypes.windll.user32
        for _ in range(steps):
            self._send_virtual_key(vk_code)

    @staticmethod
    def _send_virtual_key(vk_code: int) -> None:
        user32 = ctypes.windll.user32
        user32.keybd_event(vk_code, 0, 0, 0)
        user32.keybd_event(vk_code, 0, KEYEVENTF_KEYUP, 0)

    def _notify(self, message: str) -> None:
        if self.status_callback:
            try:
                self.status_callback(message)
            except Exception:
                pass
