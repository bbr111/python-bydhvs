"""A read timeout must be handled, on every supported Python version."""

import asyncio
import unittest

from bydhvs import BYDHVS


class _SilentReader:
    """Stream reader that never delivers data."""

    async def read(self, _size):
        await asyncio.sleep(10)
        return b""

    async def readexactly(self, _size):
        await asyncio.sleep(10)
        return b""


class TestReceiveTimeout(unittest.IsolatedAsyncioTestCase):

    async def test_timeout_returns_none(self):
        battery = BYDHVS("127.0.0.1")
        battery.READ_TIMEOUT = 0.05
        battery._reader = _SilentReader()
        self.assertIsNone(await battery._receive_response())


if __name__ == "__main__":
    unittest.main()
