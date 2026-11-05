"""
Neptune 自动充电脚本配置
从 .env 文件加载用户配置
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# 加载 .env 文件
env_path = Path(__file__).parent / ".env"
load_dotenv(env_path)

# 用户认证信息（从 .env 读取）
OPEN_ID = os.getenv("NEPTUNE_OPEN_ID", "")
AREA_ID = int(os.getenv("NEPTUNE_AREA_ID", "6"))
EMPLOYEE_ID = int(os.getenv("NEPTUNE_EMPLOYEE_ID", "0"))

# 充电设置
MAX_CHARGE_TIME = 480  # 最大充电时长（分钟）

# API 配置
BASE_URL = "https://www.szlzxn.cn"

# 断电检测时间窗口
# 检测 23:45 - 00:35 之间的断电记录
POWER_OFF_WINDOW_START_HOUR = 23
POWER_OFF_WINDOW_START_MINUTE = 45
POWER_OFF_WINDOW_END_HOUR = 0
POWER_OFF_WINDOW_END_MINUTE = 35

# 断电结束类型
POWER_OFF_END_TYPE = 39


def validate_config():
    """验证配置是否完整"""
    errors = []
    if not OPEN_ID:
        errors.append("NEPTUNE_OPEN_ID 未配置")
    if not EMPLOYEE_ID:
        errors.append("NEPTUNE_EMPLOYEE_ID 未配置")
    return errors
