"""Tests for cell voltage/temperature packet parsing."""
# pylint: disable=protected-access

import unittest

from bydhvs import BYDHVS

# 0x41 registers -> 130 data bytes + 3 header + 2 CRC
PACKET_LEN = 135


def _packet(fill: int) -> bytes:
    """Return a dummy response packet filled with a non-zero byte."""
    return bytes([1, 3, 130]) + bytes([fill]) * (PACKET_LEN - 5) + b"\x00\x00"


def _parse(num_cells: int, num_temps: int) -> dict:
    """Run packets 5-8 through the parser and return the tower data."""
    battery = BYDHVS("127.0.0.1")
    battery.hvs_num_cells = num_cells
    battery.hvs_num_temps = num_temps
    battery.tower_attributes = [{"cell_voltages": [], "cell_temperatures": []}]
    battery._parse_packet5(_packet(0x0C))
    battery._parse_packet6(_packet(0x0C))
    battery._parse_packet7(_packet(20))
    battery._parse_packet8(_packet(99))
    return battery.tower_attributes[0]


class TestParsePackets(unittest.TestCase):
    """Packet parsing must never yield more values than configured."""

    def test_temperature_counts(self):
        """8/16/24/30 temps (<= 30) must not pull garbage from packet 8."""
        for num_temps in (0, 8, 12, 16, 24, 30):
            with self.subTest(num_temps=num_temps):
                tower = _parse(32, num_temps)
                self.assertEqual(len(tower["cell_temperatures"]), num_temps)
                self.assertNotIn(99, tower["cell_temperatures"])

    def test_temperature_counts_above_30(self):
        """More than 30 temps are continued from packet 8."""
        tower = _parse(128, 48)
        temps = tower["cell_temperatures"]
        self.assertEqual(len(temps), 48)
        self.assertEqual(temps[:30], [20] * 30)
        self.assertEqual(temps[30:], [99] * 18)

    def test_cell_voltage_counts(self):
        """Cell voltage lists match the configured cell count."""
        for num_cells in (16, 32, 64, 80, 128):
            with self.subTest(num_cells=num_cells):
                tower = _parse(num_cells, 8)
                self.assertEqual(len(tower["cell_voltages"]), num_cells)

    def test_packet13_small_system(self):
        """Packet 13 adds nothing when there are <= 144 cells."""
        battery = BYDHVS("127.0.0.1")
        battery.hvs_num_cells = 128
        battery.tower_attributes = [
            {"cell_voltages": [], "cell_temperatures": []}
        ]
        battery._parse_packet13(_packet(0x0C))
        self.assertEqual(battery.tower_attributes[0]["cell_voltages"], [])


if __name__ == "__main__":
    unittest.main()
