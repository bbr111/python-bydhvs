"""Responses must be read as complete frames, however TCP splits them."""

import asyncio
import unittest

from frames import exception_response, read_response, write_response

from bydhvs import BYDHVS


def _reader_with(*chunks: bytes, eof: bool = True) -> asyncio.StreamReader:
    """Return a StreamReader that already holds the given bytes."""
    reader = asyncio.StreamReader()
    for chunk in chunks:
        reader.feed_data(chunk)
    if eof:
        reader.feed_eof()
    return reader


class TestReceiveFrame(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.battery = BYDHVS("127.0.0.1")
        self.battery.READ_TIMEOUT = 0.2

    async def test_read_frame_in_pieces(self):
        """A 135-byte cell packet arriving in 3 pieces is one frame."""
        frame = read_response(bytes(range(130)))
        reader = asyncio.StreamReader()
        self.battery._reader = reader

        async def feed():
            for start in (0, 2, 70):
                end = {0: 2, 2: 70, 70: len(frame)}[start]
                reader.feed_data(frame[start:end])
                await asyncio.sleep(0.01)

        feeder = asyncio.create_task(feed())
        data = await self.battery._receive_response()
        await feeder
        self.assertEqual(data, frame)
        self.assertTrue(self.battery._check_packet(data))

    async def test_two_frames_are_separated(self):
        """Two frames in one TCP segment are returned one by one."""
        first = read_response(bytes(4))
        second = write_response()
        self.battery._reader = _reader_with(first + second)
        self.assertEqual(await self.battery._receive_response(), first)
        self.assertEqual(await self.battery._receive_response(), second)

    async def test_exception_frame(self):
        frame = exception_response(16, 4)
        self.battery._reader = _reader_with(frame)
        self.assertEqual(await self.battery._receive_response(), frame)

    async def test_connection_closed_mid_frame(self):
        frame = read_response(bytes(50))
        self.battery._reader = _reader_with(frame[:20])
        self.assertIsNone(await self.battery._receive_response())

    async def test_incomplete_frame_times_out(self):
        frame = read_response(bytes(50))
        self.battery._reader = _reader_with(frame[:20], eof=False)
        self.assertIsNone(await self.battery._receive_response())

    async def test_unknown_function_code(self):
        """Unknown layout: only the header is returned and rejected."""
        self.battery._reader = _reader_with(bytes([1, 0x42, 7, 0, 0]))
        data = await self.battery._receive_response()
        self.assertEqual(data, bytes([1, 0x42, 7]))
        self.assertFalse(self.battery._check_packet(data))


if __name__ == "__main__":
    unittest.main()
