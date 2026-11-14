"""End-to-end poll() tests against the simulated battery."""

import asyncio
import unittest

from fake_battery import EXPECTED_SEQUENCE, SERIAL, FakeBattery

from bydhvs import (
    BYDHVS,
    BYDHVSConnectionError,
    BYDHVSError,
    BYDHVSProtocolError,
    BYDHVSTimeoutError,
)


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

    async def test_split_answers(self):
        """Answers arriving in 20-byte chunks are still read correctly."""
        for name in ("read_serial_number", "read_cell_volt_temp"):
            self.fake.add_fault(name, "split")
        await self.battery.poll()
        self.assertEqual(self.fake.received, EXPECTED_SEQUENCE)
        tower = self.battery.get_data()["tower_attributes"][0]
        self.assertEqual(len(tower["cell_voltages"]), 96)


class TestRetry(PollTestCase):
    """Only reads that return the same data twice are repeated."""

    async def test_lost_status_answer_is_retried(self):
        self.fake.add_fault("read_status_information", "drop")
        await self.battery.poll()
        expected = list(EXPECTED_SEQUENCE)
        expected.insert(2, "read_status_information")  # sent twice
        self.assertEqual(self.fake.received, expected)
        self.assertEqual(self.battery.get_data()["soc"], 87)

    async def test_broken_crc_is_retried(self):
        self.fake.add_fault("read_serial_number", "corrupt")
        await self.battery.poll()
        self.assertEqual(self.fake.received[:2], ["read_serial_number"] * 2)
        self.assertEqual(self.battery.get_data()["serial_number"], SERIAL)

    async def test_retry_only_once(self):
        for _ in range(2):
            self.fake.add_fault("read_battery_info", "drop")
        with self.assertRaises(BYDHVSTimeoutError):
            await self.battery.poll()
        self.assertEqual(
            self.fake.received,
            EXPECTED_SEQUENCE[:2] + ["read_battery_info"] * 2,
        )

    async def test_cell_data_read_is_not_retried(self):
        """A repeated cell read would return the next packet."""
        self.fake.add_fault("read_cell_volt_temp", "drop")
        with self.assertRaises(BYDHVSTimeoutError):
            await self.battery.poll()
        self.assertEqual(self.fake.received, EXPECTED_SEQUENCE[:6])

    async def test_write_is_not_retried(self):
        self.fake.add_fault("start_measure_box_1", "drop")
        with self.assertRaises(BYDHVSTimeoutError):
            await self.battery.poll()
        self.assertEqual(self.fake.received, EXPECTED_SEQUENCE[:4])


class TestPollErrors(PollTestCase):
    """poll() must raise if it could not read all data."""

    async def test_timeout(self):
        self.fake.add_fault("read_cell_volt_temp", "drop")
        with self.assertRaises(BYDHVSTimeoutError) as ctx:
            await self.battery.poll()
        self.assertIn("state 7", str(ctx.exception))

    async def test_broken_cell_packet(self):
        self.fake.add_fault("read_cell_volt_temp", "corrupt")
        with self.assertRaises(BYDHVSProtocolError):
            await self.battery.poll()

    async def test_modbus_exception(self):
        self.fake.add_fault("start_measure_box_1", "exception")
        with self.assertRaises(BYDHVSProtocolError):
            await self.battery.poll()

    async def test_protocol_error_is_connection_error(self):
        """Existing 'except BYDHVSConnectionError' code still catches it."""
        self.fake.add_fault("read_cell_volt_temp", "corrupt")
        with self.assertRaises(BYDHVSConnectionError):
            await self.battery.poll()

    async def test_connection_refused(self):
        await self.fake.stop()
        with self.assertRaises(BYDHVSConnectionError):
            await self.battery.poll()
        await self.fake.start()  # for asyncTearDown

    async def test_next_poll_works_after_error(self):
        self.fake.add_fault("read_cell_volt_temp", "drop")
        with self.assertRaises(BYDHVSTimeoutError):
            await self.battery.poll()
        await self.battery.poll()
        tower = self.battery.get_data()["tower_attributes"][0]
        self.assertEqual(len(tower["cell_voltages"]), 96)

    async def test_concurrent_poll_is_rejected(self):
        first = asyncio.create_task(self.battery.poll())
        await asyncio.sleep(0)  # let the first poll start
        with self.assertRaises(BYDHVSError):
            await self.battery.poll()
        await first  # the first poll is not disturbed
        self.assertEqual(self.fake.received, EXPECTED_SEQUENCE)


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
