"""钉钉加签 URL 构造的单元测试。"""

import unittest

from notify import build_signed_url

# 预先用独立脚本算好的参考向量（secret="test-secret", ts=1700000000000）
EXPECTED_SIGN = "BYMqUCZnSqbfPf1GCfZftO7Rg2g6P%2BRp3%2F4%2BbLNtSGA%3D"


class BuildSignedUrlTest(unittest.TestCase):
    def test_sign_is_deterministic(self):
        url = build_signed_url(
            "https://oapi.dingtalk.com/robot/send?access_token=abc",
            "test-secret",
            timestamp=1700000000000,
        )
        self.assertEqual(
            url,
            "https://oapi.dingtalk.com/robot/send?access_token=abc"
            "&timestamp=1700000000000&sign=" + EXPECTED_SIGN,
        )

    def test_empty_secret_returns_webhook(self):
        self.assertEqual(
            build_signed_url("https://oapi.dingtalk.com/robot/send?access_token=abc", ""),
            "https://oapi.dingtalk.com/robot/send?access_token=abc",
        )

    def test_empty_webhook_returns_empty(self):
        self.assertEqual(build_signed_url("", "secret"), "")

    def test_sign_encodes_base64_padding(self):
        url = build_signed_url(
            "https://oapi.dingtalk.com/robot/send?access_token=abc",
            "test-secret",
            timestamp=1700000000000,
        )
        self.assertIn("sign=" + EXPECTED_SIGN, url)
        self.assertNotIn("+", url.split("sign=")[-1])
        self.assertNotIn("/", url.split("sign=")[-1])


if __name__ == "__main__":
    unittest.main()
