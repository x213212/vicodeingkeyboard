from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .constants import DEVICE_PROFILES, VENDOR_ID, DeviceProfile
from .protocol import Packet


class HidUnavailableError(RuntimeError):
    pass


class DeviceConnectionError(RuntimeError):
    pass


@dataclass(frozen=True)
class DeviceInfo:
    path: bytes
    product_id: int
    product_string: str
    serial_number: str
    interface_number: int
    profile: DeviceProfile

    @property
    def display_name(self) -> str:
        product = self.product_string or self.profile.name
        serial = f" · {self.serial_number}" if self.serial_number else ""
        return f"{product} [VID 1189 / PID {self.product_id:04X}]{serial}"


def _load_hid() -> Any:
    try:
        import hid  # type: ignore
    except ImportError as exc:
        raise HidUnavailableError(
            "尚未安裝 hidapi。請執行：python -m pip install -r requirements.txt"
        ) from exc
    return hid


def _matches_interface(raw: dict[str, Any], profile: DeviceProfile) -> bool:
    interface_number = int(raw.get("interface_number", -1))
    if interface_number >= 0:
        return interface_number == profile.interface_number
    path = raw.get("path", b"")
    path_text = path.decode(errors="ignore") if isinstance(path, bytes) else str(path)
    expected = f"mi_{profile.interface_number:02d}"
    return expected in path_text.lower() or "mi_" not in path_text.lower()


def discover_devices() -> list[DeviceInfo]:
    hid = _load_hid()
    results: list[DeviceInfo] = []
    for raw in hid.enumerate(VENDOR_ID, 0):
        product_id = int(raw.get("product_id", 0))
        profile = DEVICE_PROFILES.get(product_id)
        if profile is None or not _matches_interface(raw, profile):
            continue
        path = raw.get("path", b"")
        if isinstance(path, str):
            path = path.encode()
        results.append(
            DeviceInfo(
                path=path,
                product_id=product_id,
                product_string=str(raw.get("product_string") or ""),
                serial_number=str(raw.get("serial_number") or ""),
                interface_number=int(raw.get("interface_number", -1)),
                profile=profile,
            )
        )
    return results


class KeyboardDevice:
    def __init__(self) -> None:
        self.info: DeviceInfo | None = None
        self._handle: Any = None
        self.report_id: int = 3

    @property
    def connected(self) -> bool:
        return self._handle is not None and self.info is not None

    def connect(self, info: DeviceInfo) -> int:
        self.close()
        hid = _load_hid()
        try:
            handle = hid.device()
            handle.open_path(info.path)
            handle.set_nonblocking(1)
        except Exception as exc:
            raise DeviceConnectionError(f"無法開啟 HID 裝置：{exc}") from exc
        self._handle = handle
        self.info = info
        self.report_id = self._probe_report_id()
        return self.report_id

    def _probe_report_id(self) -> int:
        # 與原程式 KeyBoardVersion_Check() 相同，依序嘗試 3、0、2。
        for report_id in (3, 0, 2):
            try:
                written = self._handle.write(bytes((report_id,)) + bytes(64))
                if written:
                    return report_id
            except Exception:
                continue
        raise DeviceConnectionError("裝置已開啟，但 Report ID 3、0、2 都無法寫入")

    def write_packets(self, packets: list[Packet]) -> None:
        if not self.connected:
            raise DeviceConnectionError("尚未連接鍵盤")
        for packet in packets:
            try:
                written = self._handle.write(packet.wire_bytes)
            except Exception as exc:
                raise DeviceConnectionError(f"HID 寫入失敗：{exc}") from exc
            if not written:
                raise DeviceConnectionError("HID 寫入回傳 0 bytes")

    def close(self) -> None:
        if self._handle is not None:
            try:
                self._handle.close()
            except Exception:
                pass
        self._handle = None
        self.info = None


class SimulatedKeyboard:
    def __init__(self, profile: DeviceProfile | None = None) -> None:
        self.profile = profile or DEVICE_PROFILES[0x8840]
        self.report_id = 3
        self.history: list[Packet] = []

    @property
    def connected(self) -> bool:
        return True

    def write_packets(self, packets: list[Packet]) -> None:
        self.history.extend(packets)

    def close(self) -> None:
        self.history.clear()

