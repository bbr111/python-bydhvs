"""Sanity checks for the synthetic frame helpers."""

import unittest

from frames import exception_response, read_response, write_response

from bydhvs import BYDHVS


class TestFrameHelpers(unittest.TestCase):
    """The helpers must build frames the library accepts."""

    def test_frames_pass_check(self):
        """Verify generated response frames pass packet validation."""
        battery = BYDHVS("127.0.0.1")
        # pylint: disable=protected-access
        self.assertTrue(battery._check_packet(read_response(bytes(10))))
        self.assertTrue(battery._check_packet(write_response()))
        # pylint: enable=protected-access

    def test_exception_frame(self):
        """Verify exception frames are recognized for the matching request."""
        battery = BYDHVS("127.0.0.1")
        request = bytes.fromhex("010300000066c5e0")
        # pylint: disable=protected-access
        self.assertTrue(
            battery._is_modbus_exception_response(
                exception_response(), request
            )
        )
        # pylint: enable=protected-access


if __name__ == "__main__":
    unittest.main()
