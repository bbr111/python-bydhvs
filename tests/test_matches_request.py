"""A response must belong to the request it is taken for."""

import unittest

from frames import read_response, write_response

from bydhvs import BYDHVS


class TestMatchesRequest(unittest.TestCase):

    def setUp(self):
        self.battery = BYDHVS("127.0.0.1")
        self.requests = self.battery._requests

    def test_read_with_matching_length(self):
        # read_status_information asks for 0x19 registers = 50 bytes
        self.assertTrue(self.battery._matches_request(
            read_response(bytes(50)), self.requests["read_status_information"]
        ))

    def test_read_with_other_length(self):
        """The 204-byte serial packet is no answer to the status request."""
        self.assertFalse(self.battery._matches_request(
            read_response(bytes(204)),
            self.requests["read_status_information"],
        ))

    def test_write_answer_for_read_request(self):
        self.assertFalse(self.battery._matches_request(
            write_response(), self.requests["read_battery_info"]
        ))

    def test_write_confirmation(self):
        self.assertTrue(self.battery._matches_request(
            write_response(), self.requests["start_measure_box_1"]
        ))

    def test_all_poll_requests_match_fake_battery(self):
        """Register counts of the requests used by poll()."""
        sizes = {
            "read_serial_number": 0x66 * 2,
            "read_status_information": 0x19 * 2,
            "read_battery_info": 3 * 2,
            "read_measurement_status": 1 * 2,
            "read_cell_volt_temp": 0x41 * 2,
        }
        for name, size in sizes.items():
            with self.subTest(name=name):
                self.assertTrue(self.battery._matches_request(
                    read_response(bytes(size)), self.requests[name]
                ))


if __name__ == "__main__":
    unittest.main()
