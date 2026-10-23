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


def _balancing_packet(flags: bytes, fill: int = 0x0C) -> bytes:
    """Return a dummy packet 5/12 with the given balancing flag bytes."""
    packet = bytearray(_packet(fill))
    packet[17:17 + len(flags)] = flags
    return bytes(packet)


class TestBalancingStatus(unittest.TestCase):
    """Balancing status must cover exactly the number of cells."""

    def _battery(self, num_cells: int) -> BYDHVS:
        battery = BYDHVS("127.0.0.1")
        battery.hvs_num_cells = num_cells
        battery.hvs_num_temps = 60
        battery.tower_attributes = [
            {"cell_voltages": [], "cell_temperatures": []}
        ]
        return battery

    def test_128_cells(self):
        """<= 128 cells: 32 hex chars from packet 5, no second pass."""
        first = bytes([0x80] + [0] * 14 + [0x01])  # cells 1 and 128
        battery = self._battery(128)
        battery._parse_packet5(_balancing_packet(first))
        for parser in (battery._parse_packet6, battery._parse_packet7,
                       battery._parse_packet8):
            parser(_packet(0x0C))
        tower = battery.tower_attributes[0]
        self.assertEqual(tower["balancing_status"], first.hex())
        self.assertEqual(len(tower["balancing_status"]), 32)
        self.assertEqual(tower["balancing_count"], 2)
        self.assertEqual(len(tower["cell_voltages"]), 128)

    def test_160_cells(self):
        """5 HVS modules: 40 hex chars (160 bits), count over all cells."""
        first = bytes([0xFF] + [0] * 15)  # cells 1-8
        # Second pass: cells 129 and 160; bytes beyond cell 160 are ignored.
        second = bytes([0x80, 0, 0, 0x01] + [0xFF] * 12)
        battery = self._battery(160)
        battery._parse_packet5(_balancing_packet(first))
        for parser in (battery._parse_packet6, battery._parse_packet7,
                       battery._parse_packet8):
            parser(_packet(0x0C))
        battery._parse_packet12(_balancing_packet(second))
        battery._parse_packet13(_packet(0x0C))
        tower = battery.tower_attributes[0]
        self.assertEqual(len(tower["balancing_status"]), 40)
        self.assertEqual(
            tower["balancing_status"], first.hex() + "80000001"
        )
        self.assertEqual(tower["balancing_count"], 10)
        self.assertEqual(len(tower["cell_voltages"]), 160)

    def test_packet12_without_packet5(self):
        """Without first-pass data, second-pass flags are not appended."""
        battery = self._battery(160)
        battery._parse_packet12(_balancing_packet(bytes([0xFF] * 16)))
        self.assertNotIn("balancing_status", battery.tower_attributes[0])


if __name__ == "__main__":
    unittest.main()
