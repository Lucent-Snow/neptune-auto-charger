"""
Neptune 充电桩 - 实际充电测试
设备: 50559141
端口: 12
"""

import aiohttp
import asyncio
import os
import sys

from dotenv import load_dotenv
from charge_confirmation import (
    CONFIRMATION_INTERVAL_SECONDS,
    MAX_CONFIRMATION_ATTEMPTS,
    confirm_charge,
)
from charge_request import build_charge_params
from ports import get_port_status

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

# ============ 配置 ============
load_dotenv()

OPEN_ID = os.getenv("NEPTUNE_OPEN_ID")
_area_id_raw = os.getenv("NEPTUNE_AREA_ID")
AREA_ID = int(_area_id_raw) if _area_id_raw else None

if not OPEN_ID or AREA_ID is None:
    raise RuntimeError(
        "缺少 .env 配置：请在 .env 中设置 NEPTUNE_OPEN_ID 与 NEPTUNE_AREA_ID（参考 .env.example）"
    )
DEV_ADDRESS = "50559141"  # 目标设备
TARGET_PORT = "12"  # 目标物理端口（Neptune 端口号从 1 开始）

BASE_URL = "http://www.szlzxn.cn"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 16; 24117RK2CC Build/BP2A.250605.031.A3; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/142.0.7444.173 Mobile Safari/537.36 XWEB/1420113 MMWEBSDK/20250904 MMWEBID/7686 MicroMessenger/8.0.65.2960(0x28004153) WeChat/arm64 Weixin NetType/5G Language/zh_CN ABI/arm64",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Origin": "http://www.szlzxn.cn",
    "Referer": f"http://www.szlzxn.cn/wx/indexn.html?openId={OPEN_ID}&areaid={AREA_ID}",
    "Accept": "*/*",
}


async def get_user_info(session: aiohttp.ClientSession) -> dict | None:
    """获取用户信息"""
    url = f"{BASE_URL}/wxn/getUserInfo"
    data = {"openId": OPEN_ID, "areaId": AREA_ID}
    async with session.post(url, data=data, headers=HEADERS) as resp:
        result = await resp.json()
        if result.get("success"):
            return result.get("obj")
    return None


async def get_device_info(session: aiohttp.ClientSession, devaddress: str) -> dict | None:
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
    beforemoney: int,
    device_info: dict,
    charge_money: int = 100,  # 默认 1 元
) -> dict:
    """启动充电"""
    url = f"{BASE_URL}/wxn/beginCharge"
    params = build_charge_params(
        devaddress,
        port,
        beforemoney,
        device_info,
        AREA_ID,
        OPEN_ID,
        charge_money=charge_money,
    )

    # 第一次调用 - 获取 msgflag
    print("\n[步骤1] 发送初始请求...")
    async with session.post(url, data=params, headers=HEADERS) as resp:
        result1 = await resp.json()
        print(f"响应: {result1}")

    if not result1.get("success"):
        return {"success": False, "msg": f"第一步失败: {result1.get('msg')}", "step": 1}

    msgflag = result1.get("obj")
    if not msgflag:
        return {"success": False, "msg": "未获取到 msgflag", "step": 1}

    print(f"✓ 获取到 msgflag: {msgflag}")

    # 后续调用 - 使用同一个 msgflag 等待设备响应
    print("\n[步骤2] 发送确认请求...")
    params["msgflag"] = msgflag

    def print_confirmation(attempt: int, result: dict):
        print(
            f"确认 {attempt}/{MAX_CONFIRMATION_ATTEMPTS} "
            f"（间隔 {CONFIRMATION_INTERVAL_SECONDS} 秒）: {result}"
        )

    return await confirm_charge(
        session,
        url,
        params,
        HEADERS,
        on_result=print_confirmation,
    )


async def main():
    print("=" * 60)
    print("Neptune 充电桩 - 实际充电测试")
    print("=" * 60)
    print(f"设备地址: {DEV_ADDRESS}")
    print(f"目标端口: {TARGET_PORT}")
    print()

    timeout = aiohttp.ClientTimeout(total=10)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        # 1. 获取用户信息
        print("[1] 获取用户信息...")
        user_info = await get_user_info(session)
        if not user_info:
            print("✗ 获取用户信息失败")
            return

        balance = user_info.get("readyaccountmoney", 0)
        print(f"✓ 用户: {user_info.get('employeeid')}")
        print(f"✓ 当前余额: {balance / 100:.2f} 元")

        if balance < 100:
            print("✗ 余额不足 1 元，无法充电")
            return

        # 2. 获取设备信息
        print(f"\n[2] 获取设备 {DEV_ADDRESS} 信息...")
        device_info = await get_device_info(session, DEV_ADDRESS)
        if not device_info:
            print("✗ 获取设备信息失败")
            return

        portstatur = device_info.get("portstatur", "")
        print(f"✓ 设备名称: {device_info.get('devdescript')}")
        print(f"✓ 工作时间: {device_info.get('workTime')}")
        print(f"✓ 端口状态: {portstatur}")
        print(f"  端口数量: {len(portstatur)}")

        # 显示每个端口状态
        print("\n  端口详情:")
        for i, status in enumerate(portstatur, start=1):
            status_text = {"0": "空闲", "1": "使用中", "3": "故障"}.get(status, "未知")
            marker = " <-- 目标" if str(i) == str(int(TARGET_PORT)) else ""
            print(f"    端口 {i:02d}: {status} ({status_text}){marker}")

        # 3. 检查目标端口状态
        port_status = get_port_status(portstatur, TARGET_PORT)
        if port_status is None:
            print(f"\n✗ 端口 {TARGET_PORT} 不存在（设备只有 {len(portstatur)} 个端口）")
            return

        if port_status != "0":
            status_text = {"1": "使用中", "3": "故障"}.get(port_status, "未知")
            print(f"\n✗ 端口 {TARGET_PORT} 当前状态: {status_text}，无法充电")
            return

        print(f"\n✓ 端口 {TARGET_PORT} 空闲，可以充电")

        # 4. 确认充电
        print("\n" + "!" * 60)
        print("即将开始充电！")
        print(f"  设备: {DEV_ADDRESS}")
        print(f"  端口: {TARGET_PORT}")
        print(f"  金额: 1.00 元")
        print("!" * 60)

        confirm = input("\n确认开始充电? (输入 yes 确认): ")
        if confirm.lower() != "yes":
            print("已取消")
            return

        # 5. 开始充电
        print("\n[3] 开始充电...")
        result = await begin_charge(
            session,
            DEV_ADDRESS,
            TARGET_PORT,
            balance,
            device_info,
            charge_money=100,  # 1 元
        )

        if result.get("success"):
            print("\n" + "=" * 60)
            print("✓ 充电启动成功！")
            print(f"  消息: {result.get('msg')}")
            print("=" * 60)
        else:
            print(f"\n✗ 充电失败: {result.get('msg')}")


if __name__ == "__main__":
    asyncio.run(main())
