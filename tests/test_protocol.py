import unittest

from mini_keyboard.constants import CONSUMER_USAGES, DEVICE_PROFILES
from mini_keyboard.models import ActionKind, Assignment, KeyStroke
from mini_keyboard.protocol import UnsupportedProtocolError, encode_assignment


class Protocol2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.profile = DEVICE_PROFILES[0x8840]

    def test_keyboard_packet_matches_decompiled_layout(self) -> None:
        assignment = Assignment(
            target=7,
            layer=2,
            kind=ActionKind.KEYBOARD,
            strokes=[KeyStroke(0x03, 0x04), KeyStroke(0, 0x28)],
        )
        packets = encode_assignment(assignment, self.profile, 3)
        self.assertEqual(len(packets), 1)
        payload = packets[0].payload
        self.assertEqual(payload[:4], bytes((0xFE, 7, 2, 1)))
        self.assertEqual(payload[9], 2)
        self.assertEqual(payload[10:14], bytes((0x03, 0x04, 0, 0x28)))
        self.assertEqual(len(packets[0].wire_bytes), 65)

    def test_led_packet_uses_special_target(self) -> None:
        assignment = Assignment(
            target=1,
            layer=3,
            kind=ActionKind.LED,
            led_mode=5,
            led_color=7,
        )
        payload = encode_assignment(assignment, self.profile, 3)[0].payload
        self.assertEqual(payload[1], 0xB0)
        self.assertEqual(payload[10], 3)
        self.assertEqual(payload[11], 0x75)

    def test_delay_is_little_endian(self) -> None:
        assignment = Assignment(target=1, kind=ActionKind.DELAY, delay_ms=1000)
        payload = encode_assignment(assignment, self.profile, 3)[0].payload
        self.assertEqual(payload[4:6], bytes((0xE8, 0x03)))

    def test_new_rotary_media_uses_shifted_layout(self) -> None:
        assignment = Assignment(
            target=4,
            kind=ActionKind.CONSUMER,
            consumer_usage=CONSUMER_USAGES["播放 / 暫停"],
        )
        payload = encode_assignment(assignment, self.profile, 3)[0].payload
        self.assertEqual(payload[10:13], bytes((0xCD, 0, 0)))
        self.assertEqual(payload[9], 0)

    def test_regular_protocol2_media_uses_original_data5_slot(self) -> None:
        assignment = Assignment(
            target=4,
            kind=ActionKind.CONSUMER,
            consumer_usage=CONSUMER_USAGES["播放 / 暫停"],
        )
        payload = encode_assignment(assignment, DEVICE_PROFILES[0x8830], 3)[0].payload
        self.assertEqual(payload[10:13], bytes((0, 0xCD, 0)))
        self.assertEqual(payload[9], 1)

    def test_mouse_group_count_matches_original_scan(self) -> None:
        click = Assignment(
            target=1,
            kind=ActionKind.MOUSE,
            mouse_data=(0, 1, 0, 0, 0),
        )
        wheel = Assignment(
            target=1,
            kind=ActionKind.MOUSE,
            mouse_data=(0, 0, 0, 0, 1),
        )
        self.assertEqual(encode_assignment(click, self.profile, 3)[0].payload[9], 1)
        self.assertEqual(encode_assignment(wheel, self.profile, 3)[0].payload[9], 3)


class Protocol1Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.profile = DEVICE_PROFILES[0x8890]

    def test_keyboard_sequence_and_flash_commit(self) -> None:
        assignment = Assignment(
            target=2,
            layer=1,
            kind=ActionKind.KEYBOARD,
            strokes=[KeyStroke(1, 4)],
        )
        packets = encode_assignment(assignment, self.profile, 3)
        self.assertEqual(len(packets), 4)
        self.assertEqual(packets[0].payload[:2], bytes((0xA1, 1)))
        self.assertEqual(packets[1].payload[:6], bytes((2, 0x11, 1, 0, 1, 0)))
        self.assertEqual(packets[2].payload[:6], bytes((2, 0x11, 1, 1, 1, 4)))
        self.assertEqual(packets[3].payload[:2], bytes((0xAA, 0xAA)))

    def test_report_zero_media_bitfield(self) -> None:
        assignment = Assignment(
            target=3,
            kind=ActionKind.CONSUMER,
            consumer_usage=CONSUMER_USAGES["音量增加"],
        )
        packets = encode_assignment(assignment, self.profile, 0)
        self.assertEqual(packets[0].payload[:4], bytes((3, 2, 2, 0)))

    def test_old_protocol_rejects_delay(self) -> None:
        assignment = Assignment(target=1, kind=ActionKind.DELAY, delay_ms=100)
        with self.assertRaises(UnsupportedProtocolError):
            encode_assignment(assignment, self.profile, 3)


if __name__ == "__main__":
    unittest.main()
