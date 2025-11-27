# mcp_tools/core/time.py
"""
时间工具模块

接口:
- get_current_time() -> str: 获取当前时间 (HH:MM:SS)
- get_current_date() -> str: 获取当前日期 (YYYY-MM-DD)
- get_datetime_info() -> dict: 获取完整时间信息
"""

import pytz
from datetime import datetime
from typing import Dict, Any

TIMEZONE = pytz.timezone('Asia/Shanghai')


def get_current_time() -> str:
    """获取当前时间 (上海时区)"""
    now = datetime.now(TIMEZONE)
    return now.strftime('%H:%M:%S')


def get_current_date() -> str:
    """获取当前日期"""
    now = datetime.now(TIMEZONE)
    return now.strftime('%Y-%m-%d')


def get_datetime_info() -> Dict[str, Any]:
    """获取完整时间信息"""
    now = datetime.now(TIMEZONE)
    return {
        'datetime': now.strftime('%Y-%m-%d %H:%M:%S'),
        'date': now.strftime('%Y-%m-%d'),
        'time': now.strftime('%H:%M:%S'),
        'weekday': now.strftime('%A'),
        'weekday_cn': ['周一', '周二', '周三', '周四', '周五', '周六', '周日'][now.weekday()],
        'timezone': 'Asia/Shanghai',
        'timestamp': int(now.timestamp())
    }


# === 模块接口描述 (供 Agent 发现) ===
__module_info__ = {
    'name': 'time',
    'category': 'core',
    'description': '时间日期查询',
    'functions': [
        {'name': 'get_current_time', 'desc': '获取当前时间 HH:MM:SS'},
        {'name': 'get_current_date', 'desc': '获取当前日期 YYYY-MM-DD'},
        {'name': 'get_datetime_info', 'desc': '获取完整时间信息字典'},
    ]
}


if __name__ == '__main__':
    print(f'当前时间: {get_current_time()}')
    print(f'当前日期: {get_current_date()}')
    print(f'完整信息: {get_datetime_info()}')
