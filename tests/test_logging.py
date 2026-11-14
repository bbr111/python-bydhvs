"""Expected errors must not be logged with a traceback."""

import logging

from test_poll import PollTestCase

from bydhvs import BYDHVSTimeoutError


class TestPollLogging(PollTestCase):

    async def test_no_traceback_for_timeout(self):
        self.fake.add_fault("read_cell_volt_temp", "drop")
        with (
            self.assertLogs("bydhvs", level=logging.DEBUG) as logs,
            self.assertRaises(BYDHVSTimeoutError),
        ):
            await self.battery.poll()
        self.assertFalse(any(r.exc_info for r in logs.records))
        self.assertNotIn(
            "Error during polling", "\n".join(logs.output)
        )
