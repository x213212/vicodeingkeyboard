# MINI KeyBoard Studio

A local-only desktop app (Python + PySide6) that configures a **MINI KeyBoard**
macro pad, built by reverse-engineering the vendor C# tool's HID protocol — the
original `MINI KeyBoard.exe` is never launched.

- 6 programmable keys, a rotary encoder (turn left / press / turn right), 3 layers
- **Two HID protocol variants** recovered from the vendor tool and reimplemented
  from scratch (legacy PID `0x8890` on interface 1; newer `0x8830` / `0x8840` on interface 0)
- **Simulation mode is the default** — nothing is written over USB until you opt in
- Every HID write shows a 64-byte packet preview and asks for confirmation
- Text macros typed via Windows Unicode input: no clipboard, no network, no telemetry,
  no kernel driver

![Qt 介面](qt_preview.png)

## Protocol

The vendor tool speaks 64-byte HID output reports. `mini_keyboard/protocol.py`
rebuilds both encodings it uses:

| | Protocol 1 (legacy) | Protocol 2 |
|---|---|---|
| Example PID | `0x8890` | `0x8830`, `0x8840` |
| HID interface | 1 | 0 |
| Payload | fixed header + key/modifier pairs | grouped, variable group count |

`tests/test_protocol.py` pins the encoder against known-good byte sequences, so a
refactor cannot silently change what gets written to the hardware.

## Install & run

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe run.py
```

Or double-click `啟動設定工具.bat`.

Requires Windows for the volume/auto-start integration (`windows_runtime.py`);
the protocol layer itself is platform independent.

---

# 繁體中文說明

## MINI KeyBoard Studio（Qt 版）

這是一套完全本機執行的 Python / PySide6 鍵盤設定工具，根據原廠 C# 程式的 HID 協定重新實作，不需要啟動原始 `MINI KeyBoard.exe`。

## 目前硬體

- USB VID：`0x1189`
- 實機 PID：`0x8840`
- 6 顆可設定按鍵
- 1 顆旋鈕：左轉、按下、右轉
- 三層設定

## 快速文字

Qt 主畫面的「快速文字」頁，以及右下角綠色鍵盤圖示的「設定文字」選單，都可設定：

- `KEY 1`～`KEY 6`
文字按「儲存」後立即寫入 `文字巨集.json`。按下 KEY 1～6 時，背景程式會在目前游標位置輸入保存內容，接著自動按一次 `Enter`。

旋鈕按一下會靜音並保留當時音量；快速按兩下，或向任一方向轉動，會先恢復靜音前音量。轉動仍套用動態音量加速。

文字使用 Windows Unicode 輸入，不使用剪貼簿、不連網、不上傳。

## 旋鈕音量

- 左轉：音量減少
- 右轉：音量增加
- 慢轉：每格 1 次
- 快速旋轉：依速度提高到每格 2、3 或 5 次

動態加速需要程式在右下角常駐。結束程式後仍保留鍵盤原生的一格音量調整。

## 自動保存

- `文字巨集.json`：KEY 1～6 的文字
- `設定檔.json`：上次分層、按鍵、模擬模式、機型、頁面及視窗大小

所有變更都會立即自動保存，不需要另外按「總儲存」。

## 開機啟動

Qt 畫面中的「開機自動啟動」預設已開啟。登入 Windows 後會以 `--tray` 模式安靜常駐，不跳出主視窗。可隨時由主畫面或右下角選單關閉。

## 執行

直接雙擊 `啟動設定工具.bat`，或：

```powershell
cd D:\MINI-KeyBoard-Python
.\.venv\Scripts\python.exe run.py
```

第一次從全新環境安裝：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## 安全設計

- 預設模擬模式不寫入 USB。
- 實機模式只列出已知的 VID/PID 與正確 HID 介面。
- 寫入進階 HID 設定前會顯示封包預覽並再次確認。
- 不含網路、遙測、自動下載、外部命令或系統層驅動。


## 授權

本專案程式碼以 MIT 授權釋出，見 [LICENSE](LICENSE)。

HID 協定是從原廠工具的行為觀察還原後**重新實作**的，未包含原廠任何程式碼或韌體。
`MINI KeyBoard` 與相關商標屬其各自持有人；本專案與原廠無關聯、未經其背書。

## 免責聲明

實機模式會寫入鍵盤的設定記憶體。雖然寫入前一律顯示封包預覽並要求確認，
仍請自行承擔風險——本專案作者不對硬體損壞負責。
