"""Warning/error texts must be correct and fit a sensor state."""

import unittest

from bydhvs import BYDHVS

from frames import read_response

# Packet 1 is a read response with 50 data bytes (0x19 registers).
PACKET1_DATA_LEN = 50


class TestFlagsToText(unittest.TestCase):

    def setUp(self):
        self.battery = BYDHVS("127.0.0.1")

    def test_no_flags(self):
        self.assertEqual(
            self.battery._flags_to_text(0, self.battery._errors), "No Error"
        )

    def test_single_and_multiple_flags(self):
        errors = self.battery._errors
        self.assertEqual(self.battery._flags_to_text(0b1, errors), errors[0])
        self.assertEqual(
            self.battery._flags_to_text(0b101, errors),
            f"{errors[0]}; {errors[2]}",
        )

    def test_all_flags_are_cut_to_255(self):
        """All 16 texts together are longer than 255 characters."""
        for names in (self.battery._errors, self.battery._stat_tower):
            with self.subTest(names=names[0]):
                text = self.battery._flags_to_text(0xFFFF, names)
                self.assertEqual(len(text), BYDHVS.MAX_TEXT_LENGTH)
                self.assertTrue(text.endswith("..."))
                self.assertTrue(text.startswith(names[0]))

    def test_packet1_error_string(self):
        """Error register (bytes 29-30) set to bit 15 = signed -32768."""
        frame = bytearray(read_response(bytes(PACKET1_DATA_LEN)))
        frame[29], frame[30] = 0x80, 0x00
        self.battery._parse_packet1(bytes(frame))
        self.assertEqual(self.battery.hvs_error, -32768)
        self.assertEqual(
            self.battery.hvs_error_string, self.battery._errors[15]
        )


if __name__ == "__main__":
    unittest.main()
