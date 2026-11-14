"""Exercise the complete second pass and multiple HVS towers."""

import unittest

from fake_battery import FakeBattery
from bydhvs import BYDHVS


class TestMultiTowerPoll(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.fake = FakeBattery(towers=2, modules=5)
        await self.fake.start()
        self.battery = BYDHVS("127.0.0.1", self.fake.port)
        self.battery.SLEEP_TIME = 0
        self.battery.READ_TIMEOUT = 0.5
        self.battery.CONNECT_TIMEOUT = 1

    async def asyncTearDown(self):
        await self.fake.stop()

    async def test_two_towers_five_modules(self):
        await self.battery.poll()
        data = self.battery.get_data()
        self.assertEqual(data["towers"], 2)
        self.assertEqual(data["modules"], 5)
        self.assertEqual(data["number_of_cells"], 160)
        self.assertEqual(data["number_of_temperatures"], 60)

        first = [
            "read_serial_number",
            "read_status_information",
            "read_battery_info",
        ]
        for tower in (1, 2):
            start = "start_measure_box_{}".format(tower)
            first.extend([
                start,
                "read_measurement_status",
            ])
            first.extend(["read_cell_volt_temp"] * 4)
            first.extend([
                "switch_pass",
                start,
                "read_measurement_status",
            ])
            first.extend(["read_cell_volt_temp"] * 2)
        self.assertEqual(self.fake.received, first)

        for tower in data["tower_attributes"]:
            self.assertEqual(len(tower["cell_voltages"]), 160)
            self.assertEqual(len(tower["cell_temperatures"]), 60)
            self.assertEqual(tower["cell_voltages"][0], 3300)
            self.assertEqual(tower["cell_voltages"][-1], 3459)
            self.assertEqual(len(tower["balancing_status"]), 40)
            self.assertEqual(tower["balancing_count"], 4)


if __name__ == "__main__":
    unittest.main()
