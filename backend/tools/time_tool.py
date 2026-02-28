import time

from . import mcp

_TIME_TOOL_REGISTERED = False

class CurrentTimeTool:
    """
    当前时间工具类
    用于获取格式化的当前系统时间
    """
    def get_current_time(self) -> str:
        """
        获取当前系统时间，返回格式化字符串
        """
        current_time = time.localtime()
        formatted_time = time.strftime("%Y-%m-%d %H:%M:%S", current_time)
        return f"当前系统时间：{formatted_time}"

time_tool_instance = CurrentTimeTool()

time_tool_instance.get_current_time = mcp.tool(
    name="current_time",
    description="获取当前时间工具，无需参数，返回格式化的当前系统时间（YYYY-MM-DD HH:MM:SS）",
)(time_tool_instance.get_current_time)


def register_time_tool():
    """注册时间工具（确保只注册一次）"""
    global _TIME_TOOL_REGISTERED
    if not _TIME_TOOL_REGISTERED:
        try:
            mcp.add_tool(time_tool_instance.get_current_time)
            _TIME_TOOL_REGISTERED = True
        except Exception as e:
            _TIME_TOOL_REGISTERED = True


register_time_tool()

def get_time_tool():
    """获取绑定好的时间工具方法"""
    return time_tool_instance.get_current_time