import unittest

from ports import get_port_status, is_port_free


class PortStatusTest(unittest.TestCase):
    def test_first_physical_port_uses_first_character(self):
        self.assertEqual(get_port_status("100000000000", 1), "1")

    def test_twelfth_physical_port_uses_last_character(self):
        self.assertEqual(get_port_status("000000000001", "12"), "1")

    def test_twelfth_port_is_free_when_last_character_is_zero(self):
        self.assertTrue(is_port_free("000000000000", "12"))

    def test_zero_and_out_of_range_ports_are_invalid(self):
        self.assertIsNone(get_port_status("000000000000", 0))
        self.assertIsNone(get_port_status("000000000000", 13))

    def test_invalid_port_value_is_not_free(self):
        self.assertFalse(is_port_free("000000000000", "invalid"))


if __name__ == "__main__":
    unittest.main()
