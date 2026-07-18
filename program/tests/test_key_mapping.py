import unittest

from piano_led.key_mapping import (
    KEY_LED_COUNTS, KEY_RANGES, MAPPED_LED_COUNT, build_key_ranges,
    format_key_led_counts, parse_key_led_counts, range_for_key,
)


class KeyMappingTests(unittest.TestCase):
    def test_mapping_is_contiguous(self):
        self.assertEqual(len(KEY_RANGES), 88)
        self.assertEqual(KEY_RANGES[0].led_start, 0)
        for left, right in zip(KEY_RANGES, KEY_RANGES[1:]):
            self.assertEqual(left.led_end, right.led_start)

    def test_given_counts_map_198_leds(self):
        self.assertEqual(MAPPED_LED_COUNT, 198)
        self.assertEqual(range_for_key(88).led_end, 198)

    def test_user_facing_format_round_trips(self):
        self.assertEqual(parse_key_led_counts(format_key_led_counts()), KEY_LED_COUNTS)

    def test_user_mapping_requires_all_leds(self):
        text = format_key_led_counts().replace("Tecla 1: 4", "Tecla 1: 3")
        with self.assertRaises(ValueError):
            parse_key_led_counts(text)

    def test_custom_key_and_led_totals_are_supported(self):
        text = "\n".join(("Tecla 1: 2", "Tecla 2: 3", "Tecla 3: 1"))
        counts = parse_key_led_counts(text, expected_led_count=6, key_count=3)
        self.assertEqual(build_key_ranges(counts)[-1].led_end, 6)
