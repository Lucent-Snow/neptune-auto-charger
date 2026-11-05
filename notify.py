"""钉钉机器人通知（加签模式，与 zju-autosign 使用同一套签名逻辑）。"""

import base64
import hashlib
import hmac
import time
import urllib.parse
from typing import Optional

import aiohttp

from config import DINGTALK_SECRET, DINGTALK_WEBHOOK, MAX_CHARGE_TIME


def build_signed_url(
    webhook: str,
    secret: str,
    timestamp: Optional[int] = None,
) -> str:
    """生成加签后的钉钉 webhook 地址。

    算法：sign = base64(HMAC-SHA256(secret, "{timestamp}\\n{secret}"))，再对
    timestamp 与 sign 做 URL encode 追加到 webhook 上。secret 为空时原样返回。
    """
    if not webhook:
        return ""
    if not secret:
        return webhook

    ts = timestamp if timestamp is not None else int(time.time() * 1000)
    string_to_sign = f"{ts}\n{secret}"
    hmac_code = hmac.new(
        secret.encode("utf-8"),
        string_to_sign.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()
    sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
    return f"{webhook}&timestamp={ts}&sign={sign}"


async def send_markdown(
    session: aiohttp.ClientSession,
    title: str,
    text: str,
) -> bool:
    """推送 markdown 消息，返回是否成功（未配置 webhook 视为跳过，返回 False）。"""
    if not DINGTALK_WEBHOOK:
        return False

    url = build_signed_url(DINGTALK_WEBHOOK, DINGTALK_SECRET)
    payload = {"msgtype": "markdown", "markdown": {"title": title, "text": text}}
    try:
        async with session.post(url, json=payload) as resp:
            data = await resp.json()
            return data.get("errcode") == 0
    except Exception:
        return False


async def notify_result(session: aiohttp.ClientSession, success: bool, message: str) -> bool:
    """把最终充电结果推送到钉钉；标题与签到机器人区分开。"""
    if not DINGTALK_WEBHOOK:
        return False

    if success:
        title = "Neptune 续充成功"
        text = (
            f"### {title}\n\n"
            f"- {message}\n"
            f"- 最长充电时长 {MAX_CHARGE_TIME} 分钟"
        )
    else:
        title = "Neptune 续充失败"
        text = (
            f"### {title}\n\n"
            f"- {message}\n"
            f"- 多次重试仍失败，请尽快手动处理"
        )
    return await send_markdown(session, title, text)
