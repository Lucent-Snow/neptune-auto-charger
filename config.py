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
# employeeId 延迟解析：留空或非数字时不崩溃，交给 validate_config 报错
EMPLOYEE_ID_RAW = os.getenv("NEPTUNE_EMPLOYEE_ID", "").strip()
try:
    EMPLOYEE_ID = int(EMPLOYEE_ID_RAW)
except ValueError:
    EMPLOYEE_ID = 0

# 钉钉通知（可选；留空 webhook 即关闭通知）
DINGTALK_WEBHOOK = os.getenv("DINGTALK_WEBHOOK", "").strip()
DINGTALK_SECRET = os.getenv("DINGTALK_SECRET", "").strip()

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
    if not EMPLOYEE_ID_RAW:
        errors.append("NEPTUNE_EMPLOYEE_ID 未配置")
    elif EMPLOYEE_ID == 0:
        errors.append("NEPTUNE_EMPLOYEE_ID 不是有效数字")
    return errors
