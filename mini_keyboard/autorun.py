from __future__ import annotations

import subprocess
import sys
from pathlib import Path


APP_NAME = "MINIKeyBoardPython"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def _command() -> str:
    pythonw = Path(sys.executable).resolve()
    if pythonw.name.lower() == "python.exe":
        candidate = pythonw.with_name("pythonw.exe")
        if candidate.exists():
            pythonw = candidate
    run_script = Path(__file__).resolve().parent.parent / "run.py"
    return subprocess.list2cmdline((str(pythonw), str(run_script), "--tray"))


def is_enabled() -> bool:
    if sys.platform != "win32":
        return False
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            value, _value_type = winreg.QueryValueEx(key, APP_NAME)
        return str(value) == _command()
    except OSError:
        return False


def set_enabled(enabled: bool) -> None:
    if sys.platform != "win32":
        raise RuntimeError("開機自動啟動目前只支援 Windows")
    import winreg

    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
        if enabled:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, _command())
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass


def command() -> str:
    return _command()
