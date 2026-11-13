"""End-to-end poll() tests against the simulated battery."""

import unittest

from bydhvs import BYDHVS

from fake_battery import EXPECTED_SEQUENCE, SERIAL, FakeBattery


class PollTestCase(unittest.IsolatedAsyncioTestCase):
    """Starts a FakeBattery and a BYDHVS client with short timeouts."""

    async def asyncSetUp(self):
        self.fake = FakeBattery()
        await self.fake.start()
        self.battery = BYDHVS("127.0.0.1", self.fake.port)
        # Keep the tests fast: no 4 s measurement wait, short timeouts.
        self.battery.SLEEP_TIME = 0
        self.battery.READ_TIMEOUT = 0.3
        self.battery.CONNECT_TIMEOUT = 1

    async def asyncTearDown(self):
        await self.fake.stop()


class TestPollSuccess(PollTestCase):

    async def test_full_poll(self):
        await self.battery.poll()
        data = self.battery.get_data()

        self.assertEqual(self.fake.received, EXPECTED_SEQUENCE)
        self.assertEqual(data["serial_number"], SERIAL)
        self.assertEqual(data["bmu_firmware"], "V3.27-B")
        self.assertEqual(data["bms_firmware"], "V3.31-B")
        self.assertEqual(data["towers"], 1)
        self.assertEqual(data["modules"], 3)
        self.assertEqual(data["battery_type_string"], "HVS")
        self.assertEqual(data["soc"], 87)
        self.assertEqual(data["current"], -5.2)
        self.assertEqual(data["charge_total"], 1234.5)
        self.assertEqual(data["number_of_cells"], 96)
        self.assertEqual(data["number_of_temperatures"], 36)

        tower = data["tower_attributes"][0]
        self.assertEqual(len(tower["cell_voltages"]), 96)
        self.assertEqual(tower["cell_voltages"][:3], [3300, 3301, 3302])
        self.assertEqual(tower["cell_voltages"][-1], 3395)
        self.assertEqual(len(tower["cell_temperatures"]), 36)
        self.assertEqual(tower["balancing_count"], 2)
        self.assertEqual(tower["state_string"], "Cells Imbalance")


class TestStartMeasureRequest(unittest.TestCase):
    """The 'start measurement' write exists for towers 1-3 only."""

    def test_towers(self):
        battery = BYDHVS("127.0.0.1")
        for tower, name in enumerate(
            ("start_measure_box_1", "start_measure_box_2",
             "start_measure_box_3")
        ):
            battery.current_tower = tower
            self.assertEqual(
                battery._start_measure_request(), battery._requests[name]
            )
        battery.current_tower = 3
        self.assertIsNone(battery._start_measure_request())


if __name__ == "__main__":
    unittest.main()
