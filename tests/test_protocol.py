import unittest

from qr65_protocol import build_packet, build_set_color


class BuildPacketTest(unittest.TestCase):
    def test_empty_payload_has_header_length_and_checksum(self):
        # 0xAA + 0xEC + 0x61 + 0 + 0 = 503 -> 503 & 0xFF = 0xF7
        self.assertEqual(build_packet(0x61, b"").hex(" "), "aa ec 61 00 00 f7")

    def test_length_is_big_endian_two_bytes(self):
        pkt = build_packet(0x10, bytes(300))
        self.assertEqual(pkt[3:5], bytes([0x01, 0x2C]))
        self.assertEqual(len(pkt), 5 + 300 + 1)


class BuildSetColorTest(unittest.TestCase):
    def test_matches_bytes_proven_to_work_on_the_speaker(self):
        # Same layout the original bridge sent: [0x00, slot 7 (static), R, G, B, brightness, 0xFF]
        self.assertEqual(build_set_color(255, 0, 0, 100).hex(" "),
                         "aa ec 6b 00 07 00 07 ff 00 00 64 ff 71")

    def test_rgb_is_clamped_not_wrapped(self):
        pkt = build_set_color(300, -5, 128, 100)
        self.assertEqual(list(pkt[7:10]), [255, 0, 128])

    def test_brightness_is_clamped_to_0_100(self):
        self.assertEqual(build_set_color(1, 2, 3, 150)[10], 100)
        self.assertEqual(build_set_color(1, 2, 3, -1)[10], 0)


if __name__ == "__main__":
    unittest.main()
