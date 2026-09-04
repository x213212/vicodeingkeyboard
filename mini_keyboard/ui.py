from __future__ import annotations

import sys
import threading
import time
import ctypes
from ctypes import wintypes
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QCloseEvent, QIcon, QLinearGradient, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QSystemTrayIcon,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .app_settings import AppSettings
from .autorun import is_enabled as autorun_is_enabled
from .autorun import set_enabled as set_autorun_enabled
from .constants import (
    CONSUMER_USAGES,
    DEVICE_PROFILES,
    KEY_CODES,
    LED_COLORS,
    LED_MODES,
    MODIFIERS,
    MOUSE_ACTIONS,
    DeviceProfile,
)
from .device import (
    DeviceConnectionError,
    DeviceInfo,
    HidUnavailableError,
    KeyboardDevice,
    SimulatedKeyboard,
    discover_devices,
)
from .macro_store import MacroStore, TEXT_TRIGGER_TARGETS, TRIGGER_TARGETS, TRIGGER_USAGES
from .models import ActionKind, Assignment, KeyStroke
from .protocol import UnsupportedProtocolError, encode_assignment, preview_packets
from .windows_runtime import WindowsMacroRuntime


STYLE = """
* {
    font-family: "Microsoft JhengHei UI";
    font-size: 10pt;
    color: #e8edf4;
}
QMainWindow, QWidget#root { background: #0b1017; }
QFrame#topBar, QFrame#connectionCard, QFrame#hardwareCard,
QFrame#functionCard, QFrame#previewCard {
    background: #131b25;
    border: 1px solid #243141;
    border-radius: 16px;
}
QLabel#title { font-size: 23pt; font-weight: 700; color: #f7fafc; }
QLabel#subtitle { color: #7f8c9d; font-size: 10pt; }
QLabel#sectionTitle { font-size: 12pt; font-weight: 700; color: #f7fafc; }
QLabel#eyebrow { color: #65e0c2; font-size: 9pt; font-weight: 700; }
QLabel#muted { color: #8290a2; }
QLabel#statusGood {
    background: #15362f;
    color: #76e5c9;
    border: 1px solid #245f52;
    border-radius: 11px;
    padding: 5px 12px;
    font-weight: 700;
}
QPushButton {
    background: #1b2633;
    border: 1px solid #2d3c4e;
    border-radius: 9px;
    padding: 8px 13px;
    color: #e8edf4;
}
QPushButton:hover { background: #233244; border-color: #40556c; }
QPushButton:pressed { background: #101821; }
QPushButton:disabled { color: #556170; background: #141b24; border-color: #202b38; }
QPushButton#primary {
    background: #59d6b7;
    color: #07120f;
    border-color: #59d6b7;
    font-weight: 800;
    padding: 10px 18px;
}
QPushButton#primary:hover { background: #72e4c7; }
QPushButton#danger { color: #ff9c9c; }
QPushButton#target {
    min-height: 52px;
    background: #182331;
    font-weight: 700;
}
QPushButton#target:checked {
    background: #163a34;
    color: #75e5c9;
    border: 2px solid #52cbb0;
}
QPushButton#layer {
    padding: 7px 16px;
    background: transparent;
}
QPushButton#layer:checked {
    background: #26394a;
    color: #71dec4;
    border-color: #49715f;
}
QPushButton#macroCard {
    text-align: left;
    min-height: 74px;
    background: #17212d;
    padding: 12px 15px;
    font-size: 10pt;
}
QPushButton#macroCard:hover { background: #1d2c3b; border-color: #4c6d80; }
QComboBox, QSpinBox, QListWidget, QPlainTextEdit {
    background: #0f161f;
    border: 1px solid #2a394a;
    border-radius: 8px;
    padding: 7px;
    selection-background-color: #287563;
}
QComboBox::drop-down { border: none; width: 28px; }
QComboBox QAbstractItemView {
    background: #17212c;
    border: 1px solid #304155;
    selection-background-color: #276653;
}
QCheckBox { spacing: 8px; }
QCheckBox::indicator {
    width: 18px; height: 18px;
    background: #0f161f;
    border: 1px solid #3b4b5e;
    border-radius: 5px;
}
QCheckBox::indicator:checked { background: #59d6b7; border-color: #59d6b7; }
QTabWidget::pane { border: none; background: transparent; }
QTabBar::tab {
    background: transparent;
    color: #8190a3;
    padding: 10px 14px;
    margin-right: 3px;
    border-bottom: 2px solid transparent;
}
QTabBar::tab:selected { color: #70e1c5; border-bottom-color: #59d6b7; }
QTabBar::tab:hover { color: #dce4ed; }
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical { background: #101720; width: 9px; }
QScrollBar::handle:vertical { background: #324154; border-radius: 4px; min-height: 24px; }
QToolTip { background: #1c2734; color: white; border: 1px solid #3d5268; padding: 6px; }
"""


class Bridge(QObject):
    status = Signal(str)
    initialized = Signal(int)
    initialize_error = Signal(str)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("MINI KeyBoard Studio")
        self.setMinimumSize(1040, 700)
        self.app_icon = self._make_icon()
        self.setWindowIcon(self.app_icon)
        self.settings = AppSettings()
        self.resize(
            int(self.settings.get("window_width", 1240)),
            int(self.settings.get("window_height", 820)),
        )

        self.store = MacroStore()
        self.bridge = Bridge()
        self.bridge.status.connect(self._set_status)
        self.bridge.initialized.connect(self._initialization_finished)
        self.bridge.initialize_error.connect(self._initialization_failed)
        self.runtime = WindowsMacroRuntime(self.store, self.bridge.status.emit)
        self.real_device = KeyboardDevice()
        self.simulated_device = SimulatedKeyboard()
        self.discovered: list[DeviceInfo] = []
        self.target = int(self.settings.get("target", 1))
        self.layer = int(self.settings.get("layer", 1))
        self.macro_strokes: list[KeyStroke] = []
        self.target_buttons: dict[int, QPushButton] = {}
        self.macro_cards: dict[str, QPushButton] = {}
        self.tray_macro_actions: dict[str, Any] = {}
        self._quitting = False

        self._resize_save_timer = QTimer(self)
        self._resize_save_timer.setSingleShot(True)
        self._resize_save_timer.timeout.connect(self._save_window_size)

        self._build_ui()
        self._build_tray()
        self._load_ui_state()
        self._refresh_macro_cards()
        self._refresh_preview()
        self.runtime.start()

    @property
    def active_profile(self) -> DeviceProfile:
        if not self.simulation_check.isChecked() and self.real_device.info is not None:
            return self.real_device.info.profile
        return DEVICE_PROFILES[int(self.profile_combo.currentData())]

    @property
    def active_report_id(self) -> int:
        return 3 if self.simulation_check.isChecked() else self.real_device.report_id

    def _build_ui(self) -> None:
        root = QWidget(objectName="root")
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(22, 20, 22, 18)
        outer.setSpacing(13)

        top = QFrame(objectName="topBar")
        top_layout = QHBoxLayout(top)
        top_layout.setContentsMargins(20, 15, 20, 15)
        brand = QVBoxLayout()
        title = QLabel("MINI KeyBoard Studio", objectName="title")
        subtitle = QLabel("6 鍵 · 1 旋鈕　｜　文字巨集、音量加速與 HID 設定", objectName="subtitle")
        brand.addWidget(title)
        brand.addWidget(subtitle)
        top_layout.addLayout(brand, 1)
        self.status_label = QLabel("正在啟動…", objectName="statusGood")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        top_layout.addWidget(self.status_label)
        outer.addWidget(top)

        connection = QFrame(objectName="connectionCard")
        connection_layout = QHBoxLayout(connection)
        connection_layout.setContentsMargins(17, 12, 17, 12)
        connection_layout.setSpacing(9)
        connection_layout.addWidget(QLabel("裝置", objectName="eyebrow"))
        self.device_combo = QComboBox()
        self.device_combo.setMinimumWidth(300)
        connection_layout.addWidget(self.device_combo, 1)
        scan_button = QPushButton("掃描")
        scan_button.clicked.connect(self._scan_devices)
        connection_layout.addWidget(scan_button)
        connect_button = QPushButton("連接")
        connect_button.clicked.connect(self._connect_device)
        connection_layout.addWidget(connect_button)
        disconnect_button = QPushButton("中斷")
        disconnect_button.clicked.connect(self._disconnect_device)
        connection_layout.addWidget(disconnect_button)
        self.simulation_check = QCheckBox("模擬模式")
        self.simulation_check.toggled.connect(self._simulation_changed)
        connection_layout.addWidget(self.simulation_check)
        self.autorun_check = QCheckBox("開機自動啟動")
        self.autorun_check.toggled.connect(self._autorun_changed)
        connection_layout.addWidget(self.autorun_check)
        self.notifications_check = QCheckBox("顯示系統通知")
        self.notifications_check.toggled.connect(self._notifications_changed)
        connection_layout.addWidget(self.notifications_check)
        self.profile_combo = QComboBox()
        for pid, profile in DEVICE_PROFILES.items():
            self.profile_combo.addItem(f"PID {pid:04X}", pid)
        self.profile_combo.setMaximumWidth(115)
        self.profile_combo.currentIndexChanged.connect(self._profile_changed)
        connection_layout.addWidget(self.profile_combo)
        outer.addWidget(connection)

        body = QHBoxLayout()
        body.setSpacing(13)
        outer.addLayout(body, 1)
        body.addWidget(self._build_hardware_card(), 4)
        body.addWidget(self._build_function_card(), 7)

    def _build_hardware_card(self) -> QFrame:
        card = QFrame(objectName="hardwareCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(17, 17, 17, 17)
        layout.setSpacing(12)
        layout.addWidget(QLabel("硬體配置", objectName="eyebrow"))
        layout.addWidget(QLabel("選擇實體按鍵", objectName="sectionTitle"))

        layer_row = QHBoxLayout()
        layer_row.setSpacing(6)
        self.layer_buttons: dict[int, QPushButton] = {}
        for layer in (1, 2, 3):
            button = QPushButton(f"第 {layer} 層", objectName="layer")
            button.setCheckable(True)
            button.clicked.connect(lambda _checked=False, value=layer: self._select_layer(value))
            layer_row.addWidget(button)
            self.layer_buttons[layer] = button
        layout.addLayout(layer_row)

        key_grid = QGridLayout()
        key_grid.setSpacing(8)
        for number in range(1, 7):
            button = QPushButton(f"KEY {number}", objectName="target")
            button.setCheckable(True)
            button.clicked.connect(lambda _checked=False, value=number: self._select_target(value))
            key_grid.addWidget(button, (number - 1) // 3, (number - 1) % 3)
            self.target_buttons[number] = button
        layout.addLayout(key_grid)

        layout.addWidget(QLabel("旋鈕", objectName="sectionTitle"))
        knob_row = QHBoxLayout()
        knob_row.setSpacing(8)
        for label, target in (("↶  左轉", 16), ("●  按下", 17), ("右轉  ↷", 18)):
            button = QPushButton(label, objectName="target")
            button.setCheckable(True)
            button.clicked.connect(lambda _checked=False, value=target: self._select_target(value))
            knob_row.addWidget(button)
            self.target_buttons[target] = button
        layout.addLayout(knob_row)

        self.selected_label = QLabel("", objectName="statusGood")
        layout.addWidget(self.selected_label)
        note = QLabel(
            "旋鈕左轉＝音量減少，右轉＝音量增加。\n快速旋轉時，背景程式會自動加速。",
            objectName="muted",
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        layout.addStretch(1)
        initialize = QPushButton("寫入文字觸發配置", objectName="primary")
        initialize.setToolTip("把 KEY 1～6 與旋鈕按下配置成背景文字觸發鍵")
        initialize.clicked.connect(self._initialize_text_triggers)
        self.initialize_button = initialize
        layout.addWidget(initialize)
        return card

    def _build_function_card(self) -> QFrame:
        card = QFrame(objectName="functionCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(17, 17, 17, 15)
        layout.setSpacing(10)
        layout.addWidget(QLabel("功能設定", objectName="eyebrow"))
        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_text_tab(), "快速文字")
        self.tabs.addTab(self._build_keyboard_tab(), "基本／組合鍵")
        self.tabs.addTab(self._build_simple_combo_tab("多媒體功能", CONSUMER_USAGES, "consumer_combo"), "多媒體")
        self.tabs.addTab(self._build_simple_combo_tab("滑鼠功能", MOUSE_ACTIONS, "mouse_combo"), "滑鼠")
        self.tabs.addTab(self._build_led_tab(), "RGB / LED")
        self.tabs.addTab(self._build_delay_tab(), "延遲")
        self.tabs.addTab(self._build_disabled_tab(), "停用")
        layout.addWidget(self.tabs, 1)

        preview_card = QFrame(objectName="previewCard")
        preview_layout = QVBoxLayout(preview_card)
        preview_layout.setContentsMargins(12, 10, 12, 10)
        preview_head = QHBoxLayout()
        preview_head.addWidget(QLabel("HID 封包預覽", objectName="sectionTitle"))
        preview_head.addStretch(1)
        preview_head.addWidget(QLabel("前 24 bytes · 寫入前可核對", objectName="muted"))
        preview_layout.addLayout(preview_head)
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setMaximumHeight(104)
        self.preview.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        preview_layout.addWidget(self.preview)
        layout.addWidget(preview_card)

        action_row = QHBoxLayout()
        self.clear_button = QPushButton("清除此按鍵", objectName="danger")
        self.clear_button.clicked.connect(self._clear_target)
        action_row.addWidget(self.clear_button)
        action_row.addStretch(1)
        refresh = QPushButton("更新預覽")
        refresh.clicked.connect(self._refresh_preview)
        action_row.addWidget(refresh)
        self.apply_button = QPushButton("套用到鍵盤", objectName="primary")
        self.apply_button.clicked.connect(self._apply_assignment)
        action_row.addWidget(self.apply_button)
        layout.addLayout(action_row)
        self.tabs.currentChanged.connect(self._tab_changed)
        return card

    def _build_text_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(4, 12, 4, 8)
        heading = QLabel("點一下卡片，輸入文字後立即自動保存", objectName="sectionTitle")
        layout.addWidget(heading)
        detail = QLabel(
            "六顆按鍵會輸入保存內容並自動按 Enter；旋鈕按一下靜音、按兩下還原。",
            objectName="muted",
        )
        detail.setWordWrap(True)
        layout.addWidget(detail)
        grid = QGridLayout()
        grid.setSpacing(8)
        for index, label in enumerate(TEXT_TRIGGER_TARGETS):
            card = QPushButton(objectName="macroCard")
            card.clicked.connect(lambda _checked=False, value=label: self._edit_text_macro(value))
            grid.addWidget(card, index // 2, index % 2)
            self.macro_cards[label] = card
        layout.addLayout(grid)
        layout.addStretch(1)
        return page

    def _build_keyboard_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(4, 12, 4, 8)
        top = QHBoxLayout()
        top.addWidget(QLabel("按鍵"))
        self.key_combo = QComboBox()
        self.key_combo.addItems(KEY_CODES.keys())
        self.key_combo.currentIndexChanged.connect(self._refresh_preview)
        top.addWidget(self.key_combo, 1)
        add = QPushButton("加入巨集")
        add.clicked.connect(self._add_stroke)
        top.addWidget(add)
        layout.addLayout(top)

        modifiers = QGridLayout()
        self.modifier_checks: dict[str, QCheckBox] = {}
        for index, name in enumerate(MODIFIERS):
            check = QCheckBox(name)
            modifiers.addWidget(check, index // 4, index % 4)
            self.modifier_checks[name] = check
        layout.addLayout(modifiers)
        self.macro_list = QListWidget()
        self.macro_list.setMinimumHeight(100)
        layout.addWidget(self.macro_list)
        row = QHBoxLayout()
        row.addWidget(QLabel("單鍵也要先加入一次；新版最多 18 組。", objectName="muted"))
        row.addStretch(1)
        remove = QPushButton("移除選取")
        remove.clicked.connect(self._remove_stroke)
        row.addWidget(remove)
        clear = QPushButton("清空")
        clear.clicked.connect(self._clear_strokes)
        row.addWidget(clear)
        layout.addLayout(row)
        return page

    def _build_simple_combo_tab(self, title: str, values: dict[str, Any], attribute: str) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(4, 16, 4, 8)
        layout.addWidget(QLabel(title, objectName="sectionTitle"))
        combo = QComboBox()
        combo.addItems(values.keys())
        combo.currentIndexChanged.connect(self._refresh_preview)
        setattr(self, attribute, combo)
        layout.addWidget(combo)
        layout.addStretch(1)
        return page

    def _build_led_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(4, 16, 4, 8)
        layout.addWidget(QLabel("目前層的燈效", objectName="sectionTitle"))
        row = QHBoxLayout()
        self.led_mode_combo = QComboBox()
        self.led_mode_combo.addItems(LED_MODES.keys())
        self.led_mode_combo.currentIndexChanged.connect(self._refresh_preview)
        row.addWidget(self.led_mode_combo)
        self.led_color_combo = QComboBox()
        self.led_color_combo.addItems(LED_COLORS.keys())
        self.led_color_combo.currentIndexChanged.connect(self._refresh_preview)
        row.addWidget(self.led_color_combo)
        layout.addLayout(row)
        layout.addWidget(QLabel("舊協定只使用模式；新版同時支援七種顏色。", objectName="muted"))
        layout.addStretch(1)
        return page

    def _build_delay_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(4, 16, 4, 8)
        layout.addWidget(QLabel("巨集延遲（新版協定）", objectName="sectionTitle"))
        self.delay_spin = QSpinBox()
        self.delay_spin.setRange(0, 6000)
        self.delay_spin.setValue(100)
        self.delay_spin.setSuffix(" ms")
        self.delay_spin.valueChanged.connect(self._refresh_preview)
        layout.addWidget(self.delay_spin)
        layout.addStretch(1)
        return page

    def _build_disabled_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(4, 16, 4, 8)
        layout.addWidget(QLabel("停用目前選取的按鍵或旋鈕動作", objectName="sectionTitle"))
        layout.addWidget(QLabel("按「套用到鍵盤」後才會寫入。", objectName="muted"))
        layout.addStretch(1)
        return page

    def _build_tray(self) -> None:
        self.tray = QSystemTrayIcon(self.app_icon, self)
        self.tray.setToolTip("MINI KeyBoard 文字巨集")
        menu = QMenu()
        text_menu = menu.addMenu("設定文字")
        for label in TEXT_TRIGGER_TARGETS:
            action = text_menu.addAction(label)
            action.triggered.connect(lambda _checked=False, value=label: self._edit_text_macro(value))
            self.tray_macro_actions[label] = action
        menu.addSeparator()
        menu.addAction("開啟完整設定", self._show_window)
        menu.addAction("重新寫入文字觸發鍵", self._initialize_text_triggers)
        self.pause_action = menu.addAction("暫停文字巨集與音量加速")
        self.pause_action.setCheckable(True)
        self.pause_action.toggled.connect(self._toggle_pause)
        self.autorun_action = menu.addAction("開機自動啟動")
        self.autorun_action.setCheckable(True)
        self.autorun_action.toggled.connect(self._tray_autorun_changed)
        self.notifications_action = menu.addAction("顯示系統通知")
        self.notifications_action.setCheckable(True)
        self.notifications_action.toggled.connect(self._tray_notifications_changed)
        menu.addSeparator()
        menu.addAction("結束", self._quit)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._tray_activated)
        self.tray.show()

    def _make_icon(self) -> QIcon:
        """建立在 16px 工作列也清楚的六鍵＋旋鈕多尺寸圖示。"""
        icon = QIcon()
        for size in (16, 20, 24, 32, 48, 64, 128, 256):
            pixmap = QPixmap(size, size)
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            scale = size / 64.0
            body = QRectF(3.5 * scale, 3.5 * scale, 57 * scale, 57 * scale)
            gradient = QLinearGradient(body.topLeft(), body.bottomRight())
            gradient.setColorAt(0.0, QColor("#8b5cf6"))
            gradient.setColorAt(0.52, QColor("#5158e8"))
            gradient.setColorAt(1.0, QColor("#187bbf"))
            painter.setBrush(gradient)
            painter.setPen(QPen(QColor("#c9f7ff"), max(1.0, 2.2 * scale)))
            painter.drawEllipse(body)

            # 左側六顆亮鍵，刻意採純白以便在深色及淺色工作列上辨認。
            key_size = max(1.7, 6.4 * scale)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#ffffff"))
            for row_y in (22, 35):
                for column_x in (14, 24, 34):
                    painter.drawEllipse(QRectF(column_x * scale, row_y * scale, key_size, key_size))

            # 大型青色旋鈕是新版圖示的主要識別特徵。
            knob = QRectF(42 * scale, 24 * scale, 14 * scale, 14 * scale)
            painter.setBrush(QColor("#10243e"))
            painter.setPen(QPen(QColor("#7fffe5"), max(1.0, 2.2 * scale)))
            painter.drawEllipse(knob)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#ffffff"))
            painter.drawEllipse(QRectF(47.2 * scale, 29.2 * scale, 3.6 * scale, 3.6 * scale))
            painter.end()
            icon.addPixmap(pixmap)
        return icon

    def _apply_windows_taskbar_icon(self) -> None:
        """強制工作列使用程式圖示，不沿用 pythonw.exe 的蛇形圖示。"""
        if sys.platform != "win32":
            return
        icon_path = Path(__file__).resolve().parent.parent / "mini_keyboard.ico"
        if not icon_path.exists():
            self.app_icon.pixmap(256, 256).save(str(icon_path), "ICO")

        user32 = ctypes.windll.user32
        user32.LoadImageW.argtypes = [
            wintypes.HINSTANCE,
            wintypes.LPCWSTR,
            wintypes.UINT,
            ctypes.c_int,
            ctypes.c_int,
            wintypes.UINT,
        ]
        user32.LoadImageW.restype = wintypes.HANDLE
        user32.SendMessageW.argtypes = [
            wintypes.HWND,
            wintypes.UINT,
            wintypes.WPARAM,
            wintypes.LPARAM,
        ]
        user32.SendMessageW.restype = wintypes.LPARAM
        load_from_file = 0x0010
        image_icon = 1
        hwnd = wintypes.HWND(int(self.winId()))
        big_icon = user32.LoadImageW(None, str(icon_path), image_icon, 64, 64, load_from_file)
        small_icon = user32.LoadImageW(None, str(icon_path), image_icon, 20, 20, load_from_file)
        if big_icon:
            user32.SendMessageW(hwnd, 0x0080, 1, int(big_icon))
        if small_icon:
            user32.SendMessageW(hwnd, 0x0080, 0, int(small_icon))
        self._native_icon_handles = (big_icon, small_icon)

    def _load_ui_state(self) -> None:
        self.simulation_check.blockSignals(True)
        self.simulation_check.setChecked(bool(self.settings.get("simulation", True)))
        self.simulation_check.blockSignals(False)
        pid = int(self.settings.get("profile_pid", 0x8840))
        index = self.profile_combo.findData(pid)
        self.profile_combo.setCurrentIndex(max(0, index))
        self.autorun_check.blockSignals(True)
        self.autorun_check.setChecked(autorun_is_enabled())
        self.autorun_check.blockSignals(False)
        self.autorun_action.blockSignals(True)
        self.autorun_action.setChecked(autorun_is_enabled())
        self.autorun_action.blockSignals(False)
        notifications = bool(self.settings.get("notifications", False))
        self.notifications_check.blockSignals(True)
        self.notifications_check.setChecked(notifications)
        self.notifications_check.blockSignals(False)
        self.notifications_action.blockSignals(True)
        self.notifications_action.setChecked(notifications)
        self.notifications_action.blockSignals(False)
        self.tabs.setCurrentIndex(max(0, min(6, int(self.settings.get("last_tab", 0)))))
        self._select_layer(self.layer)
        self._select_target(self.target if self.target in self.target_buttons else 1)
        self._simulation_changed(self.simulation_check.isChecked())

    def _set_status(self, message: str) -> None:
        self.status_label.setText(message)

    def _simulation_changed(self, checked: bool) -> None:
        self.settings.set("simulation", checked)
        self.profile_combo.setEnabled(checked)
        self._set_status("模擬模式 · 不寫入 USB" if checked else "實機模式 · 請掃描並連接")
        self._refresh_preview()

    def _profile_changed(self) -> None:
        if self.profile_combo.currentData() is None:
            return
        pid = int(self.profile_combo.currentData())
        self.settings.set("profile_pid", pid)
        self.simulated_device.profile = DEVICE_PROFILES[pid]
        self._refresh_preview()

    def _autorun_changed(self, checked: bool) -> None:
        try:
            set_autorun_enabled(checked)
        except Exception as exc:
            QMessageBox.critical(self, "設定失敗", str(exc))
            return
        self.autorun_action.blockSignals(True)
        self.autorun_action.setChecked(checked)
        self.autorun_action.blockSignals(False)
        self._set_status("已啟用開機自動啟動" if checked else "已關閉開機自動啟動")

    def _tray_autorun_changed(self, checked: bool) -> None:
        self.autorun_check.setChecked(checked)

    def _notifications_changed(self, checked: bool) -> None:
        self.settings.set("notifications", checked)
        self.notifications_action.blockSignals(True)
        self.notifications_action.setChecked(checked)
        self.notifications_action.blockSignals(False)
        self._set_status("已開啟系統通知" if checked else "已關閉系統通知")

    def _tray_notifications_changed(self, checked: bool) -> None:
        self.notifications_check.setChecked(checked)

    def _notify(self, message: str, duration: int = 1800) -> None:
        if bool(self.settings.get("notifications", False)):
            self.tray.showMessage(
                "MINI KeyBoard",
                message,
                QSystemTrayIcon.MessageIcon.Information,
                duration,
            )

    def _scan_devices(self) -> None:
        try:
            self.discovered = discover_devices()
        except HidUnavailableError as exc:
            QMessageBox.critical(self, "缺少 HID 套件", str(exc))
            return
        except Exception as exc:
            QMessageBox.critical(self, "掃描失敗", str(exc))
            return
        self.device_combo.clear()
        for info in self.discovered:
            self.device_combo.addItem(info.display_name, info)
        self._set_status(f"找到 {len(self.discovered)} 個支援裝置" if self.discovered else "沒有找到支援裝置")

    def _connect_device(self) -> None:
        if self.simulation_check.isChecked():
            self._set_status("目前是模擬模式")
            return
        if not self.discovered:
            self._scan_devices()
        info = self.device_combo.currentData()
        if not isinstance(info, DeviceInfo):
            QMessageBox.warning(self, "尚未選擇", "請先掃描並選擇鍵盤。")
            return
        try:
            report_id = self.real_device.connect(info)
        except Exception as exc:
            QMessageBox.critical(self, "連接失敗", str(exc))
            return
        self._set_status(f"已連接 PID {info.product_id:04X} · Report ID {report_id}")
        self._refresh_preview()

    def _disconnect_device(self) -> None:
        self.real_device.close()
        self._set_status("已中斷裝置")

    def _select_layer(self, layer: int) -> None:
        self.layer = layer
        for value, button in self.layer_buttons.items():
            button.setChecked(value == layer)
        self.settings.set("layer", layer)
        self._refresh_selected_label()
        self._refresh_preview()

    def _select_target(self, target: int) -> None:
        self.target = target
        for value, button in self.target_buttons.items():
            button.setChecked(value == target)
        self.settings.set("target", target)
        self._refresh_selected_label()
        self._refresh_preview()

    def _target_name(self) -> str:
        if 1 <= self.target <= 6:
            return f"KEY {self.target}"
        return {16: "旋鈕左轉", 17: "旋鈕按下", 18: "旋鈕右轉"}.get(self.target, f"代碼 {self.target}")

    def _refresh_selected_label(self) -> None:
        self.selected_label.setText(f"已選擇　{self._target_name()}　·　第 {self.layer} 層")

    def _tab_changed(self, index: int) -> None:
        self.settings.set("last_tab", index)
        is_text = index == 0
        self.apply_button.setEnabled(not is_text)
        self.clear_button.setEnabled(not is_text)
        self._refresh_preview()

    def _modifier_mask(self) -> int:
        mask = 0
        for name, check in self.modifier_checks.items():
            if check.isChecked():
                mask |= MODIFIERS[name]
        return mask

    def _add_stroke(self) -> None:
        if len(self.macro_strokes) >= 18:
            QMessageBox.warning(self, "已達上限", "新版協定最多 18 組；舊版最多 5 組。")
            return
        stroke = KeyStroke(self._modifier_mask(), KEY_CODES[self.key_combo.currentText()])
        self.macro_strokes.append(stroke)
        names = [name for name, bit in MODIFIERS.items() if stroke.modifier & bit]
        prefix = " + ".join(names)
        item = QListWidgetItem(f"{prefix + ' + ' if prefix else ''}{self.key_combo.currentText()}")
        self.macro_list.addItem(item)
        self._refresh_preview()

    def _remove_stroke(self) -> None:
        row = self.macro_list.currentRow()
        if row >= 0:
            self.macro_list.takeItem(row)
            self.macro_strokes.pop(row)
            self._refresh_preview()

    def _clear_strokes(self) -> None:
        self.macro_strokes.clear()
        self.macro_list.clear()
        self._refresh_preview()

    def _build_assignment(self, force_none: bool = False) -> Assignment:
        tab = self.tabs.currentIndex()
        kind_by_tab = {
            1: ActionKind.KEYBOARD,
            2: ActionKind.CONSUMER,
            3: ActionKind.MOUSE,
            4: ActionKind.LED,
            5: ActionKind.DELAY,
            6: ActionKind.NONE,
        }
        if force_none:
            kind = ActionKind.NONE
        elif tab == 0:
            raise ValueError("快速文字由背景選單保存，不需要產生 HID 封包")
        else:
            kind = kind_by_tab[tab]
        assignment = Assignment(target=self.target, layer=self.layer, kind=kind)
        if kind == ActionKind.KEYBOARD:
            assignment.strokes = list(self.macro_strokes)
        elif kind == ActionKind.CONSUMER:
            assignment.consumer_usage = CONSUMER_USAGES[self.consumer_combo.currentText()]
        elif kind == ActionKind.MOUSE:
            assignment.mouse_data = MOUSE_ACTIONS[self.mouse_combo.currentText()]
        elif kind == ActionKind.LED:
            assignment.target = 0xB0
            assignment.led_mode = LED_MODES[self.led_mode_combo.currentText()]
            assignment.led_color = LED_COLORS[self.led_color_combo.currentText()]
        elif kind == ActionKind.DELAY:
            assignment.delay_ms = self.delay_spin.value()
        return assignment

    def _encode_current(self, force_none: bool = False):
        assignment = self._build_assignment(force_none)
        packets = encode_assignment(assignment, self.active_profile, self.active_report_id)
        return assignment, packets

    def _refresh_preview(self) -> None:
        if not hasattr(self, "preview"):
            return
        if self.tabs.currentIndex() == 0:
            text = self.store.get(self._target_name().replace("旋鈕", "K1 ")) if self.target in (1, 2, 3, 4, 5, 6, 17) else ""
            content = "快速文字設定會立即保存，不直接送 HID 封包。\n"
            content += f"目前內容：{text}" if text else "請點上方文字卡片進行設定。"
        else:
            try:
                _assignment, packets = self._encode_current()
                content = preview_packets(packets)
            except Exception as exc:
                content = f"尚不能產生封包：{exc}"
        self.preview.setPlainText(content)

    def _apply_assignment(self) -> None:
        try:
            assignment, packets = self._encode_current()
        except Exception as exc:
            QMessageBox.warning(self, "設定不完整", str(exc))
            return
        if self.simulation_check.isChecked():
            self.simulated_device.write_packets(packets)
            QMessageBox.information(self, "模擬完成", preview_packets(packets))
            self._set_status(f"模擬完成 · {len(packets)} 個封包，未寫入 USB")
            return
        if not self.real_device.connected:
            QMessageBox.warning(self, "尚未連接", "請先掃描並連接鍵盤。")
            return
        answer = QMessageBox.question(
            self,
            "確認寫入",
            f"即將寫入 {self._target_name()}、第 {assignment.layer} 層，共 {len(packets)} 個封包。\n確定繼續？",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.real_device.write_packets(packets)
        except Exception as exc:
            QMessageBox.critical(self, "寫入失敗", str(exc))
            return
        self._set_status(f"寫入成功 · {self._target_name()} · 第 {assignment.layer} 層")

    def _clear_target(self) -> None:
        try:
            _assignment, packets = self._encode_current(force_none=True)
        except Exception as exc:
            QMessageBox.warning(self, "無法清除", str(exc))
            return
        if self.simulation_check.isChecked():
            self.simulated_device.write_packets(packets)
            self._set_status("模擬清除完成 · 未寫入 USB")
            return
        if not self.real_device.connected:
            QMessageBox.warning(self, "尚未連接", "請先連接鍵盤。")
            return
        try:
            self.real_device.write_packets(packets)
        except Exception as exc:
            QMessageBox.critical(self, "清除失敗", str(exc))
            return
        self._set_status("按鍵設定已清除")

    def _edit_text_macro(self, label: str) -> None:
        current = self.store.get(label)
        text, accepted = QInputDialog.getMultiLineText(
            self,
            f"設定 {label}",
            f"按下 {label} 時要輸入的文字：\n完成後會自動按 Enter。",
            current,
        )
        if not accepted:
            return
        self.store.set(label, text)
        self._refresh_macro_cards()
        self._set_status(f"{label} 已自動保存")
        self._notify(f"{label} 已保存")

    def _refresh_macro_cards(self) -> None:
        for label, card in self.macro_cards.items():
            text = self.store.get(label).replace("\r", " ").replace("\n", " ↵ ")
            summary = text[:34] + ("…" if len(text) > 34 else "")
            card.setText(f"{label}\n{summary if summary else '尚未設定 · 點此輸入文字'}")
            action = self.tray_macro_actions.get(label)
            if action is not None:
                short = text[:18] + ("…" if len(text) > 18 else "")
                action.setText(f"{label}　{short}" if short else f"{label}　（尚未設定）")
        self._refresh_preview()

    def _initialize_text_triggers(self) -> None:
        self.initialize_button.setEnabled(False)
        self._set_status("正在寫入 6 顆文字鍵與旋鈕配置…")

        def worker() -> None:
            device = KeyboardDevice()
            try:
                devices = [item for item in discover_devices() if item.product_id == 0x8840]
                if len(devices) != 1:
                    raise DeviceConnectionError(f"預期一台 PID 8840，實際找到 {len(devices)} 台")
                info = devices[0]
                report_id = device.connect(info)
                for label, (target, _vk_code) in TRIGGER_TARGETS.items():
                    assignment = Assignment(
                        target=target,
                        layer=1,
                        kind=ActionKind.KEYBOARD,
                        strokes=[KeyStroke(0, TRIGGER_USAGES[label])],
                    )
                    device.write_packets(encode_assignment(assignment, info.profile, report_id))
                    time.sleep(0.06)
                for target, usage in (
                    (16, CONSUMER_USAGES["音量減少"]),
                    (17, CONSUMER_USAGES["靜音"]),
                    (18, CONSUMER_USAGES["音量增加"]),
                ):
                    assignment = Assignment(
                        target=target,
                        layer=1,
                        kind=ActionKind.CONSUMER,
                        consumer_usage=usage,
                    )
                    device.write_packets(encode_assignment(assignment, info.profile, report_id))
                    time.sleep(0.06)
                self.bridge.initialized.emit(report_id)
            except Exception as exc:
                self.bridge.initialize_error.emit(str(exc))
            finally:
                device.close()

        threading.Thread(target=worker, name="trigger-initializer", daemon=True).start()

    def _initialization_finished(self, report_id: int) -> None:
        self.initialize_button.setEnabled(True)
        self._set_status(f"文字觸發配置完成 · Report ID {report_id}")
        self._notify("6 顆按鍵與旋鈕按下已完成配置。", 2200)

    def _initialization_failed(self, message: str) -> None:
        self.initialize_button.setEnabled(True)
        self._set_status("文字觸發配置失敗")
        QMessageBox.critical(self, "初始化失敗", message)

    def _toggle_pause(self, paused: bool) -> None:
        self.runtime.paused = paused
        self._set_status("文字巨集與音量加速已暫停" if paused else "文字巨集與音量加速常駐中")

    def _tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            self._show_window()

    def _show_window(self) -> None:
        self.showNormal()
        self._apply_windows_taskbar_icon()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._quitting:
            event.accept()
            return
        self.hide()
        self._notify("程式已縮到右下角通知區，仍在背景執行。", 1600)
        event.ignore()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._resize_save_timer.start(350)

    def _save_window_size(self) -> None:
        self.settings.update(window_width=self.width(), window_height=self.height())

    def _quit(self) -> None:
        self._quitting = True
        self._save_window_size()
        self.real_device.close()
        self.runtime.stop()
        self.tray.hide()
        QApplication.instance().quit()


def _acquire_single_instance() -> int | None:
    """只保留一份常駐程式；再次啟動時直接喚回原視窗。"""
    if sys.platform != "win32":
        return 1
    kernel32 = ctypes.windll.kernel32
    kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    handle = kernel32.CreateMutexW(None, False, "Local\\MINI-KeyBoard-Python-Qt-Instance")
    if kernel32.GetLastError() != 183:
        return int(handle)

    user32 = ctypes.windll.user32
    hwnd = user32.FindWindowW(None, "MINI KeyBoard Studio")
    if hwnd:
        user32.ShowWindow(hwnd, 9)
        user32.SetForegroundWindow(hwnd)
    if handle:
        kernel32.CloseHandle(handle)
    return None


def main() -> None:
    instance_handle = _acquire_single_instance()
    if instance_handle is None:
        return
    if sys.platform == "win32":
        # 固定且新版的 App ID，避免 Windows 工作列沿用 pythonw 或舊圖示快取。
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "LocalOpenTools.MINIKeyBoard.Studio.IconV3"
        )
    app = QApplication(sys.argv)
    app.setApplicationName("MINI KeyBoard Studio")
    app.setOrganizationName("Local Open Tools")
    app.setQuitOnLastWindowClosed(False)
    app.setStyleSheet(STYLE)
    window = MainWindow()
    window._instance_handle = instance_handle
    app.setWindowIcon(window.app_icon)
    # 預設縮到下方工作列；使用者點一下工作列圖示即可展開。
    window.winId()
    window._apply_windows_taskbar_icon()
    if "--tray" in sys.argv or "--minimized" in sys.argv:
        window.hide()
        QTimer.singleShot(
            900,
            lambda: window._notify("文字巨集與音量加速已在背景啟動。"),
        )
    else:
        window.show()
    app.exec()
