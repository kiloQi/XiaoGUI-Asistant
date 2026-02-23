from datetime import datetime
from . import mcp

@mcp.tool()
def get_current_time():
     return f"当前时间为{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"