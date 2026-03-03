from fastmcp import FastMCP

# 1. 创建全局唯一的 MCP 实例
mcp = FastMCP("XiaoGui-Assistant")

# 在这里统一导入工具，确保主程序启动时自动加载

from .tools import web_search_tool, calc_tool, weather_tool, time_tool, image_recognition_tool, export_chat_tool, file_parsing_tool