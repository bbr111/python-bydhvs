"""Sanity checks for the synthetic frame helpers."""

import unittest

from bydhvs import BYDHVS

from frames import exception_response, read_response, write_response


class TestFrameHelpers(unittest.TestCase):
    """The helpers must build frames the library accepts."""

    def test_frames_pass_check(self):
        battery = BYDHVS("127.0.0.1")
        self.assertTrue(battery._check_packet(read_response(bytes(10))))
        self.assertTrue(battery._check_packet(write_response()))

    def test_exception_frame(self):
        battery = BYDHVS("127.0.0.1")
        request = bytes.fromhex("010300000066c5e0")
        self.assertTrue(
            battery._is_modbus_exception_response(exception_response(), request)
        )


if __name__ == "__main__":
    unittest.main()
