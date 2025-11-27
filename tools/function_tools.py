# tools/function_tools.py
from datetime import datetime
import pytz
from llama_index.core.tools import FunctionTool

def get_current_time(timezone: str = "Asia/Shanghai") -> str:
    """
    获取指定时区的当前时间。
    参数 timezone 必须是 IANA 标准格式，如 'Asia/Shanghai' 或 'America/New_York'。
    """
    try:
        # 处理可能传入的类似 'UTC+8' 的非标准写法 (增强健壮性)
        if "UTC" in timezone:
             return f"Current time: {datetime.now(pytz.utc).strftime('%Y-%m-%d %H:%M:%S')} (UTC)"
        
        tz = pytz.timezone(timezone)
        now = datetime.now(tz)
        return f"Current time in {timezone} is {now.strftime('%Y-%m-%d %H:%M:%S')}"
    except Exception as e:
        return f"Error getting time: {str(e)}"

# 创建 LlamaIndex 工具对象
get_time_tool = FunctionTool.from_defaults(
    fn=get_current_time,
    name="get_current_time",
    description="获取当前时间。当用户问'几点了'或涉及时间时使用。"
)
