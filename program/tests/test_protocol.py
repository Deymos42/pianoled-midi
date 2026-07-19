import unittest

from piano_led import protocol
from piano_led.serial_transport import CMD_SET_RANGES, SerialLedClient, make_frame


class ProtocolTests(unittest.TestCase):
    def test_encodes_commands(self):
        self.assertEqual(protocol.set_led(5, 1, 2, 3), b"\x01\x05\x01\x02\x03")
        self.assertEqual(protocol.set_range(5, 3, 1, 2, 3), b"\x08\x05\x03\x01\x02\x03")
        self.assertEqual(protocol.show_range(5, 3, 1, 2, 3), b"\x0a\x05\x03\x01\x02\x03")
        self.assertEqual(protocol.start_sweep(1, 2, 3, 50), b"\x0b\x01\x02\x03\x00\x32")
        self.assertEqual(protocol.stop_animation(), b"\x0c")
        self.assertEqual(protocol.start_rainbow(50), b"\x0d\x00\x32")
        self.assertEqual(protocol.set_brightness(128), b"\x0e\x80")
        self.assertEqual(protocol.set_led_count(198), b"\x14\xc6")
        self.assertEqual(protocol.start_center_wave(12), b"\x15\x00\x0c")
        self.assertEqual(protocol.start_note_wave(20, 1, 2, 3), b"\x16\x14\x01\x02\x03")
        self.assertEqual(protocol.start_note_wave(20, 1, 2, 3, 25), b"\x16\x14\x01\x02\x03\x00\x19")
        self.assertEqual(protocol.start_note_fade(20, 3, 1, 2, 3, 700), b"\x17\x14\x03\x01\x02\x03\x02\xbc")
        self.assertEqual(protocol.begin_realtime_session(1), b"\x10\x00\x01")
        self.assertEqual(protocol.show_range_realtime(1, 2, 3, 4, 5, 6, 7), b"\x11\x00\x01\x00\x02\x03\x04\x05\x06\x07")
        self.assertEqual(protocol.set_ranges_realtime(1, 2, ((3, 4, 5, 6, 7),)), b"\x13\x00\x01\x00\x02\x03\x04\x05\x06\x07")
        self.assertEqual(protocol.set_frame(((1, 2, 3), (4, 5, 6))), b"\x09\x01\x02\x03\x04\x05\x06")
        self.assertEqual(protocol.clear(), b"\x02")
        self.assertEqual(protocol.fill(1, 2, 3), b"\x03\x01\x02\x03")

    def test_rejects_out_of_range_bytes(self):
        with self.assertRaises(ValueError):
            protocol.fill(256, 0, 0)

    def test_encodes_serial_frame(self):
        self.assertEqual(make_frame(CMD_SET_RANGES, b"\x01\x02\xff\xff\xff"), b"\xa5\x21\x05\x01\x02\xff\xff\xff\x26")

    def test_serial_color_order_is_configurable(self):
        client = SerialLedClient.__new__(SerialLedClient)
        client.set_color_order("BRG")
        self.assertEqual(client._to_strip_color(255, 0, 0), (0, 255, 0))
        client.set_color_order("RGB")
        self.assertEqual(client._to_strip_color(255, 0, 0), (255, 0, 0))

    def test_parses_info(self):
        response = bytes((7, 1, 0, 195, 96)) + b"pianoled"
        self.assertEqual(protocol.parse_info(response).led_count, 195)


if __name__ == "__main__":
    unittest.main()
