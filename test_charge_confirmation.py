import unittest

from charge_confirmation import confirm_charge


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        return False

    async def json(self):
        return self.payload


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def post(self, url, data, headers):
        self.requests.append((url, dict(data), headers))
        return FakeResponse(self.responses.pop(0))


class ChargeConfirmationTest(unittest.IsolatedAsyncioTestCase):
    async def test_retries_with_same_msgflag_until_third_confirmation_succeeds(self):
        session = FakeSession([
            {"success": False, "msg": "设备无响应"},
            {"success": False, "msg": "设备无响应"},
            {"success": True, "msg": "启动成功"},
        ])
        sleeps = []

        async def fake_sleep(seconds):
            sleeps.append(seconds)

        result = await confirm_charge(
            session,
            "/wxn/beginCharge",
            {"port": "12", "msgflag": "same-msgflag"},
            {},
            max_attempts=5,
            interval=6,
            sleep=fake_sleep,
        )

        self.assertTrue(result["success"])
        self.assertEqual(len(session.requests), 3)
        self.assertEqual(sleeps, [6, 6, 6])
        self.assertEqual(
            [request[1]["msgflag"] for request in session.requests],
            ["same-msgflag", "same-msgflag", "same-msgflag"],
        )

    async def test_stops_after_configured_confirmation_limit(self):
        session = FakeSession([
            {"success": False, "msg": "设备无响应"},
            {"success": False, "msg": "仍无响应"},
        ])

        async def fake_sleep(_seconds):
            return None

        result = await confirm_charge(
            session,
            "/wxn/beginCharge",
            {"msgflag": "same-msgflag"},
            {},
            max_attempts=2,
            sleep=fake_sleep,
        )

        self.assertFalse(result["success"])
        self.assertEqual(result["msg"], "仍无响应")
        self.assertEqual(len(session.requests), 2)


if __name__ == "__main__":
    unittest.main()
