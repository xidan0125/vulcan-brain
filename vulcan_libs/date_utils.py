"""
日期时间工具函数 - 支持自定义日报时间边界

默认配置：7AM-7AM (UTC+8)
- 每天7:00 AM生成日报
- 统计范围：前一天7:00 AM 到 今天 7:00 AM
"""

from datetime import datetime, timedelta
from typing import Tuple

# 日报时间边界 (24小时制)
DAILY_REPORT_HOUR = 7


def get_report_time_range(report_date: datetime) -> Tuple[datetime, datetime]:
    """
    获取日报的时间范围 (7AM to 7AM)
    
    Args:
        report_date: 日报日期 (e.g. 2025-12-17)
        
    Returns:
        (start, end): 时间范围
        - start: report_date 当天 7:00 AM
        - end: report_date + 1天 7:00 AM
        
    Example:
        report_date = 2025-12-17
        返回: (2025-12-17 07:00:00, 2025-12-18 07:00:00)
    """
    start = report_date.replace(hour=DAILY_REPORT_HOUR, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    return start, end


def get_report_date_for_now() -> datetime:
    """
    根据当前时间计算应该生成哪天的日报
    
    逻辑:
    - 如果现在是 7:00 AM 或之后，生成昨天的日报 (昨天7AM到今天7AM)
    - 如果现在是 7:00 AM 之前，生成前天的日报 (前天7AM到昨天7AM)
    
    Example:
        现在是 2025-12-18 07:30 → 生成 2025-12-17 的日报
        现在是 2025-12-18 06:30 → 生成 2025-12-16 的日报
    """
    now = datetime.now()
    
    if now.hour >= DAILY_REPORT_HOUR:
        # 7点后，生成昨天的日报
        return (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        # 7点前，生成前天的日报
        return (now - timedelta(days=2)).replace(hour=0, minute=0, second=0, microsecond=0)


def get_midnight_time_range(date: datetime) -> Tuple[datetime, datetime]:
    """
    传统的 00:00-23:59 时间范围 (向后兼容)
    """
    start = date.replace(hour=0, minute=0, second=0, microsecond=0)
    end = date.replace(hour=23, minute=59, second=59, microsecond=999999)
    return start, end
