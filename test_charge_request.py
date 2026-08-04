import unittest

from charge_request import build_charge_params


class ChargeRequestTest(unittest.TestCase):
    def test_uses_charge_option_without_overwriting_account_balance(self):
        params = build_charge_params(
            devaddress="50959115",
            port="12",
            beforemoney=539,
            device_info={},
            area_id=6,
            open_id="test-open-id",
        )

        self.assertEqual(params["money"], 7)
        self.assertEqual(params["beforemoney"], 539)

    def test_keeps_physical_port_number_unchanged(self):
        params = build_charge_params(
            devaddress="50959115",
            port="12",
            beforemoney=539,
            device_info={},
            area_id=6,
            open_id="test-open-id",
        )

        self.assertEqual(params["port"], "12")

    def test_allows_explicit_charge_money_for_manual_test(self):
        params = build_charge_params(
            devaddress="50959115",
            port="12",
            beforemoney=539,
            device_info={},
            area_id=6,
            open_id="test-open-id",
            charge_money=100,
        )

        self.assertEqual(params["money"], 100)


if __name__ == "__main__":
    unittest.main()
