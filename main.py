"""
Neptune 自动充电脚本

功能：
1. 检测昨天 24 点因断电结束的充电记录
2. 如果存在，自动在同一设备/端口恢复充电
3. 按余额最大化充电，最长 480 分钟
4. 支持重试：失败后 10 分钟重试，最多 3 次

用法：
    python main.py

VPS 定时任务：
    5 6 * * * cd /path/to/auto-charger && python3 main.py >> charge.log 2>&1
"""

import argparse
import aiohttp
import asyncio
import sys
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
from enum import Enum

from charge_confirmation import (
    CONFIRMATION_INTERVAL_SECONDS,
    MAX_CONFIRMATION_ATTEMPTS,
    confirm_charge,
)
from charge_request import build_charge_params
from ports import is_port_free
from config import (
    OPEN_ID,
    AREA_ID,
    EMPLOYEE_ID,
    MAX_CHARGE_TIME,
    BASE_URL,
    POWER_OFF_WINDOW_START_HOUR,
    POWER_OFF_WINDOW_START_MINUTE,
    POWER_OFF_WINDOW_END_HOUR,
    POWER_OFF_WINDOW_END_MINUTE,
    POWER_OFF_END_TYPE,
    validate_config,
)

# 重试配置
MAX_RETRIES = 3          # 最大重试次数
RETRY_INTERVAL = 10 * 60  # 重试间隔（秒）= 10 分钟

# 时区：北京时间 UTC+8
TZ_BEIJING = timezone(timedelta(hours=8))

# HTTP 请求头
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 16) AppleWebKit/537.36 Chrome/142.0 Mobile Safari/537.36 MicroMessenger/8.0",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Origin": BASE_URL,
    "Referer": f"{BASE_URL}/wx/indexn.html?openId={OPEN_ID}&areaid={AREA_ID}",
    "Accept": "*/*",
}


class ChargeResult(Enum):
    """充电结果"""
    SUCCESS = "success"           # 成功
    NO_RECORD = "no_record"       # 无断电记录（不需要重试）
    PORT_BUSY = "port_busy"       # 端口被占用（需要重试）
    ERROR = "error"               # 其他错误（需要重试）
    DRY_RUN = "dry_run"           # 仅预览，不启动充电


def log(message: str):
    """带时间戳的日志"""
    now = datetime.now(TZ_BEIJING).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] {message}")


async def get_user_info(session: aiohttp.ClientSession) -> Optional[dict]:
    """获取用户信息"""
    url = f"{BASE_URL}/wxn/getUserInfo"
    data = {"openId": OPEN_ID, "areaId": AREA_ID}
    async with session.post(url, data=data, headers=HEADERS) as resp:
        result = await resp.json()
        if result.get("success"):
            return result.get("obj")
    return None


async def get_charge_log(session: aiohttp.ClientSession, term: str) -> list:
    """获取指定月份的充电历史记录"""
    url = f"{BASE_URL}/wxn/getChargeLog"
    data = {"employeeid": EMPLOYEE_ID, "term": term}
    async with session.post(url, data=data, headers=HEADERS) as resp:
        result = await resp.json()
        if result.get("success"):
            return result.get("obj", [])
    return []


async def get_device_info(session: aiohttp.ClientSession, devaddress: str) -> Optional[dict]:
    """获取设备信息"""
    url = f"{BASE_URL}/wxn/getDeviceInfo"
    data = {"areaId": AREA_ID, "devaddress": devaddress}
    async with session.post(url, data=data, headers=HEADERS) as resp:
        result = await resp.json()
        if result.get("success"):
            return result.get("obj")
    return None


async def begin_charge(
    session: aiohttp.ClientSession,
    devaddress: str,
    port: str,
    money: int,
    device_info: dict,
) -> dict:
    """启动充电（两步调用）"""
    url = f"{BASE_URL}/wxn/beginCharge"
    params = build_charge_params(
        devaddress,
        port,
        money,
        device_info,
        AREA_ID,
        OPEN_ID,
    )

    # 第一次调用 - 获取 msgflag
    async with session.post(url, data=params, headers=HEADERS) as resp:
        result1 = await resp.json()

    if not result1.get("success"):
        return {"success": False, "msg": f"第一步失败: {result1.get('msg')}"}

    msgflag = result1.get("obj")
    if not msgflag:
        return {"success": False, "msg": "未获取到 msgflag"}

    # 后续调用 - 使用同一个 msgflag 等待设备响应
    params["msgflag"] = msgflag
    log(
        f"已获取启动凭据，将每 {CONFIRMATION_INTERVAL_SECONDS} 秒确认一次，"
        f"最多 {MAX_CONFIRMATION_ATTEMPTS} 次"
    )

    def log_confirmation(attempt: int, result: dict):
        if result.get("success"):
            log(f"设备确认第 {attempt}/{MAX_CONFIRMATION_ATTEMPTS} 次成功")
        else:
            log(
                f"设备确认第 {attempt}/{MAX_CONFIRMATION_ATTEMPTS} 次未成功: "
                f"{result.get('msg', '未知错误')}"
            )

    return await confirm_charge(
        session,
        url,
        params,
        HEADERS,
        on_result=log_confirmation,
    )


def find_power_off_record(logs: list) -> Optional[dict]:
    """
    查找断电记录

    条件：
    1. endtype = 39（断电结束）
    2. 结束时间在【昨天 23:45 - 今天 00:15】之间
    3. 必须是昨天/今天的记录，不能是更早的
    """
    now = datetime.now(TZ_BEIJING)
    today = now.date()
    yesterday = today - timedelta(days=1)

    # 构造精确的时间窗口（包含日期）
    window_start = datetime(
        yesterday.year, yesterday.month, yesterday.day,
        POWER_OFF_WINDOW_START_HOUR, POWER_OFF_WINDOW_START_MINUTE,
        tzinfo=TZ_BEIJING
    )
    window_end = datetime(
        today.year, today.month, today.day,
        POWER_OFF_WINDOW_END_HOUR, POWER_OFF_WINDOW_END_MINUTE,
        tzinfo=TZ_BEIJING
    )

    log(f"检测时间窗口: {window_start.strftime('%Y-%m-%d %H:%M')} ~ {window_end.strftime('%Y-%m-%d %H:%M')}")

    for record in logs:
        endtype = record.get("endtype")
        enddt = record.get("enddt")

        if endtype != POWER_OFF_END_TYPE:
            continue

        if enddt is None:
            continue

        # enddt 是毫秒时间戳
        end_time = datetime.fromtimestamp(enddt / 1000, tz=TZ_BEIJING)

        # 关键检查：结束时间必须在精确的时间窗口内（包含日期）
        if window_start <= end_time <= window_end:
            log(f"找到断电记录: 设备={record.get('devaddress')}, 端口={record.get('devport')}, 结束时间={end_time.strftime('%Y-%m-%d %H:%M:%S')}")
            return record

    return None


async def try_charge(session: aiohttp.ClientSession, dry_run: bool = False) -> Tuple[ChargeResult, str]:
    """
    尝试充电

    Returns:
        (ChargeResult, message)
    """
    try:
        # 1. 获取用户信息
        log("获取用户信息...")
        user_info = await get_user_info(session)
        if not user_info:
            return ChargeResult.ERROR, "获取用户信息失败"

        balance = user_info.get("readyaccountmoney", 0)
        log(f"当前余额: {balance / 100:.2f} 元")

        if balance < 100:
            return ChargeResult.ERROR, "余额不足 1 元"

        # 2. 获取充电历史
        now = datetime.now(TZ_BEIJING)
        logs = []

        term_this = now.strftime("%Y%m")
        log(f"获取 {term_this} 充电历史...")
        logs.extend(await get_charge_log(session, term_this))

        if now.day <= 3:
            last_month = now.replace(day=1) - timedelta(days=1)
            term_last = last_month.strftime("%Y%m")
            log(f"获取 {term_last} 充电历史...")
            logs.extend(await get_charge_log(session, term_last))

        if not logs:
            return ChargeResult.NO_RECORD, "无充电历史记录"

        log(f"共获取 {len(logs)} 条充电记录")

        # 3. 查找断电记录
        log("检查断电记录...")
        record = find_power_off_record(logs)
        if not record:
            return ChargeResult.NO_RECORD, "未找到符合条件的断电记录"

        devaddress = str(record.get("devaddress"))
        port = record.get("devport")

        # 4. 获取设备信息
        log(f"获取设备 {devaddress} 信息...")
        device_info = await get_device_info(session, devaddress)
        if not device_info:
            return ChargeResult.ERROR, "获取设备信息失败"

        portstatur = device_info.get("portstatur", "")
        log(f"端口状态: {portstatur}")

        # 5. 检查端口是否空闲
        if not is_port_free(portstatur, port):
            return ChargeResult.PORT_BUSY, f"端口 {port} 非空闲（可能充电桩未开启）"

        log(f"端口 {port} 空闲，准备充电")

        if dry_run:
            params = build_charge_params(
                devaddress,
                port,
                balance,
                device_info,
                AREA_ID,
                OPEN_ID,
            )
            log("DRY RUN — 充电未启动")
            log(f"预览: 设备={params['devaddress']}, 物理端口={params['port']}")
            log(f"预览: money 请求选项={params['money']}")
            log(f"预览: 可用余额 / beforemoney={params['beforemoney']}")
            return ChargeResult.DRY_RUN, "DRY RUN — charging not started / 充电未启动"

        # 6. 启动充电
        log(f"启动充电: 设备={devaddress}, 端口={port}, 金额={balance / 100:.2f}元")
        result = await begin_charge(session, devaddress, port, balance, device_info)

        if result.get("success"):
            return ChargeResult.SUCCESS, f"设备={devaddress}, 端口={port}, 金额={balance / 100:.2f}元"
        else:
            return ChargeResult.ERROR, f"充电启动失败: {result.get('msg')}"

    except Exception as e:
        return ChargeResult.ERROR, f"发生异常: {str(e)}"


async def main(dry_run: bool = False):
    log("=" * 50)
    log("Neptune 自动充电脚本启动")
    if dry_run:
        log("DRY RUN — 仅评估一次，充电未启动")
    else:
        log(f"重试策略: 最多 {MAX_RETRIES} 次，间隔 {RETRY_INTERVAL // 60} 分钟")
    log("=" * 50)

    # 验证配置
    config_errors = validate_config()
    if config_errors:
        for err in config_errors:
            log(f"配置错误: {err}")
        log("请检查 .env 文件配置")
        return

    timeout = aiohttp.ClientTimeout(total=30)
    attempts = 1 if dry_run else MAX_RETRIES

    for attempt in range(1, attempts + 1):
        log(f"\n--- 第 {attempt}/{attempts} 次尝试 ---")

        async with aiohttp.ClientSession(timeout=timeout) as session:
            result, message = await try_charge(session, dry_run=dry_run)

        if result == ChargeResult.DRY_RUN:
            log(f"结果: {message}")
            return

        if result == ChargeResult.SUCCESS:
            log("=" * 50)
            log("充电启动成功！")
            log(f"  {message}")
            log(f"  最长时间: {MAX_CHARGE_TIME} 分钟")
            log("=" * 50)
            return

        elif result == ChargeResult.NO_RECORD:
            log(f"结果: {message}")
            log("无需恢复充电，退出")
            return

        elif result in (ChargeResult.PORT_BUSY, ChargeResult.ERROR):
            log(f"结果: {message}")

            if attempt < attempts:
                log(f"将在 {RETRY_INTERVAL // 60} 分钟后重试...")
                await asyncio.sleep(RETRY_INTERVAL)
            else:
                log("已达到最大重试次数，退出")

    log("=" * 50)
    log("所有重试均失败")
    log("=" * 50)


def parse_args():
    parser = argparse.ArgumentParser(description="Neptune 自动充电脚本")
    parser.add_argument(
        "-n",
        "--dry-run",
        action="store_true",
        help="评估并预览充电请求，但不启动充电",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    # 修复 Windows 终端编码
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")

    asyncio.run(main(dry_run=args.dry_run))
