"""Regression tests for reconnect, polling guard and diagnostics."""

import asyncio
from unittest.mock import patch

from frames import read_response
from test_poll import PollTestCase

from bydhvs import (
    BYDHVSConnectionError,
    BYDHVSError,
    BYDHVSProtocolError,
)


class TestCommunicationRegression(PollTestCase):

    async def test_late_reply_isolated_by_reconnect(self):
        """Late data on an old socket must never feed the next poll step."""
        self.fake.add_fault("read_status_information", "delay")
        await self.battery.poll()
        self.assertEqual(self.fake.received.count("read_status_information"), 2)
        self.assertEqual(self.battery.get_data()["soc"], 87)

    async def test_disconnect_is_connection_error(self):
        self.fake.add_fault("read_cell_volt_temp", "disconnect")
        with self.assertRaises(BYDHVSConnectionError) as ctx:
            await self.battery.poll()
        self.assertNotIsInstance(ctx.exception, BYDHVSProtocolError)

    async def test_wrong_write_ack_is_protocol_error(self):
        self.fake.add_fault("start_measure_box_1", "wrong_write_echo")
        with self.assertRaises(BYDHVSProtocolError):
            await self.battery.poll()

    async def test_invalid_serial_is_protocol_error(self):
        self.fake.add_fault("read_serial_number", "bad_serial")
        with self.assertRaises(BYDHVSProtocolError):
            await self.battery.poll()

    async def test_poll_guard_covers_socket_cleanup(self):
        original_close = self.battery._close
        closing = asyncio.Event()
        release = asyncio.Event()

        async def slow_close():
            closing.set()
            await release.wait()
            await original_close()

        with patch.object(self.battery, "_close", side_effect=slow_close):
            first = asyncio.create_task(self.battery.poll())
            try:
                await asyncio.wait_for(closing.wait(), 3)
                with self.assertRaisesRegex(BYDHVSError, "already running"):
                    await self.battery.poll()
            finally:
                release.set()
                await first
        self.assertFalse(self.battery._poll_running)


class TestCompleteWarningMessages(PollTestCase):

    async def test_full_warning_lists_preserved(self):
        await self.battery.poll()
        battery = self.battery
        errors = battery._errors
        names = battery._stat_tower
        # Build synthetic valid read frames with all 16 bits set.
        packet1 = bytearray(read_response(bytes(50)))
        packet1[29:31] = bytes([0xFF, 0xFF])
        battery._parse_packet1(bytes(packet1))
        self.assertEqual(battery.hvs_error_messages, errors)
        self.assertLessEqual(len(battery.hvs_error_string), 255)
        self.assertEqual(battery.get_data()["error_messages"], errors)

        packet5 = bytearray(read_response(bytes(130)))
        packet5[59:61] = bytes([0xFF, 0xFF])
        battery._parse_packet5(bytes(packet5))
        tower = battery.tower_attributes[0]
        self.assertEqual(tower["state_messages"], names)
        self.assertLessEqual(len(tower["state_string"]), 255)
