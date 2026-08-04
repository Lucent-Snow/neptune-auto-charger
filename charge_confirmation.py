"""使用同一个 msgflag 轮询确认充电启动结果。"""

import asyncio
from typing import Callable, Optional


# 与 Neptune 网页端普通充电设备的确认节奏保持一致：初始请求之后，
# 每 6 秒确认一次，最多确认 15 次（连同初始请求最多 16 次 beginCharge）。
CONFIRMATION_INTERVAL_SECONDS = 6
MAX_CONFIRMATION_ATTEMPTS = 15


async def confirm_charge(
    session,
    url: str,
    params: dict,
    headers: dict,
    max_attempts: int = MAX_CONFIRMATION_ATTEMPTS,
    interval: int = CONFIRMATION_INTERVAL_SECONDS,
    sleep=asyncio.sleep,
    on_result: Optional[Callable[[int, dict], None]] = None,
) -> dict:
    """等待设备响应，并重复发送带相同 msgflag 的确认请求。"""
    last_result = {"success": False, "msg": "未执行充电确认请求"}

    for attempt in range(1, max_attempts + 1):
        await sleep(interval)

        async with session.post(url, data=params, headers=headers) as resp:
            last_result = await resp.json()

        if on_result is not None:
            on_result(attempt, last_result)

        if last_result.get("success"):
            return last_result

    return last_result
