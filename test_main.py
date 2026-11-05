import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

import main
from config import BASE_URL, POWER_OFF_WINDOW_END_MINUTE


def record_at(end_time: datetime) -> dict:
    return {
        "devaddress": "50559154",
        "devport": "1",
        "endtype": 39,
        "enddt": int(end_time.timestamp() * 1000),
    }


class FakeResponse:
    def __init__(self, payload: dict):
        self.payload = payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        return False

    async def json(self):
        return self.payload


class FakeSession:
    def __init__(self, device_infos):
        self.device_infos = list(device_infos)
        self.requests = []

    def post(self, url, data, headers):
        endpoint = url.rsplit("/", 1)[-1]
        self.requests.append((endpoint, dict(data)))

        if endpoint == "getUserInfo":
            return FakeResponse({"success": True, "obj": {"readyaccountmoney": 539}})

        if endpoint == "getChargeLog":
            return FakeResponse({"success": True, "obj": [record_at(datetime.now(main.TZ_BEIJING))]})

        if endpoint == "getDeviceInfo":
            return FakeResponse({"success": True, "obj": self.device_infos.pop(0)})

        if endpoint == "beginCharge":
            return FakeResponse({"success": False, "msg": "不应在端口状态变化后启动"})

        raise AssertionError(f"Unexpected endpoint: {endpoint}")


class PowerOffWindowTest(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 9, 21, 6, 7, tzinfo=main.TZ_BEIJING)

    def test_window_accepts_the_new_00_35_upper_boundary(self):
        end_time = datetime(2026, 9, 21, 0, 35, tzinfo=main.TZ_BEIJING)

        result = main.find_power_off_record([record_at(end_time)], now=self.now)

        self.assertIsNotNone(result)
        self.assertEqual(POWER_OFF_WINDOW_END_MINUTE, 35)

    def test_window_rejects_records_after_00_35(self):
        end_time = datetime(2026, 9, 21, 0, 36, tzinfo=main.TZ_BEIJING)

        result = main.find_power_off_record([record_at(end_time)], now=self.now)

        self.assertIsNone(result)

    def test_window_keeps_the_previous_day_23_45_lower_boundary(self):
        end_time = datetime(2026, 9, 20, 23, 45, tzinfo=main.TZ_BEIJING)

        result = main.find_power_off_record([record_at(end_time)], now=self.now)

        self.assertIsNotNone(result)


class PortRecheckTest(unittest.IsolatedAsyncioTestCase):
    async def test_does_not_start_charge_when_port_becomes_busy_before_start(self):
        session = FakeSession(
            [
                {"portstatur": "000000000000"},
                {"portstatur": "100000000000"},
            ]
        )
        record = record_at(datetime.now(main.TZ_BEIJING) - timedelta(minutes=5))

        with patch.object(main, "find_power_off_record", return_value=record):
            result, message = await main.try_charge(session)

        self.assertEqual(result, main.ChargeResult.PORT_BUSY)
        self.assertIn("非空闲", message)
        self.assertEqual(
            [endpoint for endpoint, _ in session.requests].count("getDeviceInfo"),
            2,
        )
        self.assertNotIn("beginCharge", [endpoint for endpoint, _ in session.requests])


class TransportSecurityTest(unittest.TestCase):
    def test_api_base_url_uses_https(self):
        self.assertTrue(BASE_URL.startswith("https://"))


if __name__ == "__main__":
    unittest.main()
