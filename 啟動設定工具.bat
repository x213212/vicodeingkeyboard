@echo off
chcp 65001 >nul
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo 正在建立獨立 Python 環境...
    python -m venv .venv
    if errorlevel 1 goto :error
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 goto :error
)

start "MINI KeyBoard Python" ".venv\Scripts\pythonw.exe" run.py
exit /b 0

:error
echo.
echo 安裝或啟動失敗，請確認已安裝 Python 3.11 或更新版本。
pause
exit /b 1

