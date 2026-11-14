"""Tower warning flags (bytes 59-60 of packet 5) must decode bit by bit."""

import unittest

from frames import read_response

from bydhvs import BYDHVS

# Packet 5 is a read response with 130 data bytes (0x41 registers).
PACKET5_DATA_LEN = 130


def _packet5(high: int, low: int) -> bytes:
    """Return packet 5 with the given warning bytes 59 (high) and 60 (low)."""
    frame = bytearray(read_response(bytes(PACKET5_DATA_LEN)))
    frame[59] = high
    frame[60] = low
    return bytes(frame)  # CRC is not checked by the parser itself


def _parse(high: int, low: int) -> dict:
    battery = BYDHVS("127.0.0.1")
    battery.tower_attributes = [{"cell_voltages": [], "cell_temperatures": []}]
    battery._parse_packet5(_packet5(high, low))
    return battery.tower_attributes[0]


class TestTowerState(unittest.TestCase):
    """Each bit of the 16-bit register maps to one warning text."""

    def test_no_warning(self):
        tower = _parse(0, 0)
        self.assertEqual(tower["state_code"], 0)
        self.assertEqual(tower["state"], "0000")
        self.assertEqual(tower["state_string"], "No Error")

    def test_low_byte_bit(self):
        """Bit 4 (byte 60 = 0x10) is 'Cells Imbalance'."""
        tower = _parse(0x00, 0x10)
        self.assertEqual(tower["state_code"], 0x0010)
        self.assertEqual(tower["state"], "0010")
        self.assertEqual(tower["state_string"], "Cells Imbalance")

    def test_high_byte_bit(self):
        """Bit 8 (byte 59 = 0x01) is the discharge low temperature warning.

        The old decimal concatenation turned this into "10" and reported
        'Battery Under Voltage; Cells UnderVoltage' instead.
        """
        tower = _parse(0x01, 0x00)
        self.assertEqual(tower["state_code"], 0x0100)
        self.assertEqual(tower["state"], "0100")
        self.assertEqual(
            tower["state_string"], "DisCharging Low Temperature(Cells)"
        )

    def test_highest_bit(self):
        """Bit 15 (byte 59 = 0x80) is the last entry of the list."""
        tower = _parse(0x80, 0x00)
        self.assertEqual(tower["state_string"], "AirSwitch Abnormal")

    def test_multiple_bits(self):
        tower = _parse(0x02, 0x01)  # bits 9 and 0
        self.assertEqual(
            tower["state_string"],
            "Battery Over Voltage; Charging OverCurrent(Cells)",
        )


if __name__ == "__main__":
    unittest.main()
