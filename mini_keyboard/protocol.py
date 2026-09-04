from __future__ import annotations

from dataclasses import dataclass

from .constants import CONSUMER_USAGES, DeviceProfile
from .models import ActionKind, Assignment


REPORT_DATA_LENGTH = 64


class UnsupportedProtocolError(ValueError):
    pass


@dataclass(frozen=True)
class Packet:
    report_id: int
    payload: bytes
    description: str

    def __post_init__(self) -> None:
        if len(self.payload) != REPORT_DATA_LENGTH:
            raise ValueError("HID payload 必須正好是 64 bytes")

    @property
    def wire_bytes(self) -> bytes:
        return bytes((self.report_id,)) + self.payload

    def hex(self) -> str:
        return " ".join(f"{value:02X}" for value in self.wire_bytes)


def _empty_payload() -> bytearray:
    return bytearray(REPORT_DATA_LENGTH)


def _packet(report_id: int, payload: bytearray, description: str) -> Packet:
    return Packet(report_id, bytes(payload), description)


def encode_assignment(
    assignment: Assignment,
    profile: DeviceProfile,
    report_id: int,
) -> list[Packet]:
    assignment.validate()
    if report_id not in (0, 2, 3):
        raise ValueError("Report ID 只允許 0、2 或 3")
    if profile.protocol == 2:
        return _encode_protocol_2(assignment, profile, report_id)
    return _encode_protocol_1(assignment, report_id)


def _protocol_2_group_count(payload: bytearray) -> int:
    # 忠實重現原版 Download_Click：第一組只檢查第二 byte，
    # 後續組則檢查該組任一 byte，最後保留最末非零組編號。
    group_count = 1 if payload[11] != 0 else 0
    for group in range(2, 19):
        offset = 10 + (group - 1) * 2
        if payload[offset] != 0 or payload[offset + 1] != 0:
            group_count = group
    return group_count


def _encode_protocol_2(
    assignment: Assignment,
    profile: DeviceProfile,
    report_id: int,
) -> list[Packet]:
    payload = _empty_payload()
    payload[0] = 0xFE
    payload[1] = assignment.target
    payload[2] = assignment.layer
    payload[3] = int(assignment.kind)

    if assignment.kind == ActionKind.KEYBOARD:
        for index, stroke in enumerate(assignment.strokes):
            offset = 10 + index * 2
            payload[offset] = stroke.modifier
            payload[offset + 1] = stroke.usage
    elif assignment.kind == ActionKind.CONSUMER:
        low_value, high_value = _old_consumer_pair(assignment.consumer_usage, report_id)
        if profile.new_rotary_map:
            payload[10] = low_value
            payload[11] = high_value
        else:
            payload[11] = low_value
            payload[12] = high_value
    elif assignment.kind == ActionKind.MOUSE:
        modifier, buttons, x_value, y_value, wheel = assignment.mouse_data
        if profile.new_rotary_map:
            payload[10] = modifier
            payload[11] = buttons
            payload[12] = x_value
            payload[13] = y_value
            payload[14] = wheel
        else:
            payload[11] = buttons
            payload[12] = x_value
            payload[13] = y_value
            payload[14] = wheel
            payload[16] = modifier
    elif assignment.kind == ActionKind.DELAY:
        payload[4] = assignment.delay_ms & 0xFF
        payload[5] = (assignment.delay_ms >> 8) & 0xFF
    elif assignment.kind == ActionKind.LED:
        payload[1] = 0xB0
        payload[10] = assignment.layer
        payload[11] = (assignment.led_color << 4) | assignment.led_mode

    payload[9] = _protocol_2_group_count(payload)

    return [_packet(report_id, payload, "寫入設定（新版協定）")]


def _old_consumer_pair(usage: int, report_id: int) -> tuple[int, int]:
    name_by_usage = {value: key for key, value in CONSUMER_USAGES.items()}
    try:
        name = name_by_usage[usage]
    except KeyError as exc:
        raise UnsupportedProtocolError("舊協定只支援原程式列出的六種多媒體功能") from exc

    report_0 = {
        "播放 / 暫停": (0x40, 0x00),
        "上一首": (0x80, 0x00),
        "下一首": (0x00, 0x01),
        "靜音": (0x04, 0x00),
        "音量增加": (0x02, 0x00),
        "音量減少": (0x01, 0x00),
    }
    report_2 = {
        "播放 / 暫停": (0x00, 0x04),
        "上一首": (0x00, 0x0B),
        "下一首": (0x00, 0x0A),
        "靜音": (0x00, 0x01),
        "音量增加": (0x40, 0x00),
        "音量減少": (0x80, 0x00),
    }
    if report_id == 0:
        return report_0[name]
    if report_id == 2:
        return report_2[name]
    return usage & 0xFF, (usage >> 8) & 0xFF


def _old_header(assignment: Assignment, report_id: int) -> int:
    if report_id == 0:
        return int(assignment.kind) & 0x0F
    return ((assignment.layer & 0x0F) << 4) | (int(assignment.kind) & 0x0F)


def _encode_protocol_1(assignment: Assignment, report_id: int) -> list[Packet]:
    if assignment.kind == ActionKind.DELAY:
        raise UnsupportedProtocolError("反編譯結果顯示延遲功能只支援新版協定")
    if assignment.kind == ActionKind.KEYBOARD and len(assignment.strokes) > 5:
        raise UnsupportedProtocolError("舊協定最多支援 5 組按鍵")

    packets: list[Packet] = []
    if report_id != 0:
        switch = _empty_payload()
        switch[0] = 0xA1
        switch[1] = assignment.layer
        packets.append(_packet(report_id, switch, "切換設定層"))

    payload = _empty_payload()
    payload[0] = assignment.target
    payload[1] = _old_header(assignment, report_id)

    if assignment.kind in (ActionKind.NONE, ActionKind.KEYBOARD):
        payload[2] = len(assignment.strokes)
        first_modifier = assignment.strokes[0].modifier if assignment.strokes else 0
        # 原程式先送 index 0（只有 modifier），再逐組送實際按鍵。
        for index in range(len(assignment.strokes) + 1):
            current = bytearray(payload)
            current[3] = index
            if index == 0:
                current[4] = first_modifier
                current[5] = 0
            else:
                stroke = assignment.strokes[index - 1]
                current[4] = stroke.modifier
                current[5] = stroke.usage
            packets.append(_packet(report_id, current, f"寫入鍵盤序列 {index}"))
    elif assignment.kind == ActionKind.CONSUMER:
        payload[2], payload[3] = _old_consumer_pair(assignment.consumer_usage, report_id)
        packets.append(_packet(report_id, payload, "寫入多媒體功能"))
    elif assignment.kind == ActionKind.MOUSE:
        modifier, buttons, x_value, y_value, wheel = assignment.mouse_data
        payload[2] = buttons
        payload[3] = x_value
        payload[4] = y_value
        payload[5] = wheel
        payload[6] = modifier
        packets.append(_packet(report_id, payload, "寫入滑鼠功能"))
    elif assignment.kind == ActionKind.LED:
        payload[0] = 0xB0
        payload[2] = assignment.led_mode
        packets.append(_packet(report_id, payload, "寫入 LED 模式"))

    commit = _empty_payload()
    commit[0] = 0xAA
    commit[1] = 0xA1 if assignment.kind == ActionKind.LED else 0xAA
    packets.append(_packet(report_id, commit, "儲存至鍵盤 Flash"))
    return packets


def preview_packets(packets: list[Packet], trim_after: int = 24) -> str:
    lines: list[str] = []
    for index, packet in enumerate(packets, 1):
        shown = packet.wire_bytes[:trim_after]
        suffix = " …" if trim_after < len(packet.wire_bytes) else ""
        hex_data = " ".join(f"{value:02X}" for value in shown) + suffix
        lines.append(f"{index}. {packet.description}\n   {hex_data}")
    return "\n".join(lines)
