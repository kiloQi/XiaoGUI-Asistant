from typing import List, Optional, Dict, Any
from fastmcp import FastMCP

mcp = FastMCP("XiaoGui-Tool")

from backend.tools.file_parsing_tool import parse_file as parse_file_impl
from backend.tools.calc_tool import calculate as calculate_impl
from backend.tools.time_tool import get_current_time as get_current_time_impl
# from backend.tools.weather_tool import get_weather as get_weather_impl
from backend.tools.web_search_tool import web_search as web_search_impl
from backend.tools.export_chat_tool import save_messages_to_markdown as save_messages_impl
from backend.tools.image_recognition_tool import analyze_image as analyze_image_impl

@mcp.tool()
def save_messages_to_markdown(messages,file_name:str="chat_log")->str:
    """
        将聊天记录导出为 Markdown 文件。

        Args:
            messages: 聊天消息列表 (List of Message objects)
            file_name: 文件名前缀 (可选，默认为 chat_log)

        Returns:
            str: 操作结果描述（包含成功提示和文件路径，或错误信息）
        """
    result = save_messages_impl(messages, file_name)
    return result

@mcp.tool()
def calculate(expression:str):
    """
        执行数学表达式计算。
        支持加减乘除、括号、幂运算等基础数学运算。
        当用户询问数学题、需要计算数值或验证算式时使用。

        Args:
            expression: 数学表达式字符串 (例如："12 + 5 * 3", "(100 - 20) / 4")

        Returns:
            str: 计算结果字符串。
        """
    result =calculate_impl(expression)
    return result

@mcp.tool()
def parse_file(file_path: str) -> List[str]:
    """
        解析本地文档文件，提取文本内容并切分为片段。
        支持读取 txt, pdf, docx, md 等常见格式。
        适用于用户需要让 AI 阅读、总结或分析上传的本地文件时使用。

        Args:
            file_path: 本地文件的绝对路径或相对路径。

        Returns:
            List[str]: 解析后的文本片段列表，每个元素是一段文本。
        """
    result = parse_file_impl(file_path)
    return result

@mcp.tool()
def analyze_image(image_path: str) -> Optional[str]:
    """
       分析本地图篇内容，识别图中的物体、文字、场景或描述图篇内容。
       适用于用户上传了图片并询问“这是什么”、“图里有什么”或需要提取图中文字的场景。

       Args:
           image_path: 本地图片文件的路径。

       Returns:
           Optional[str]: 图片的分析描述文本。如果分析失败返回 None。
       """

    result = analyze_image_impl(image_path)
    return result

@mcp.tool()
def get_current_time():
    """
        获取当前的系统日期和时间。
        当用户询问“现在几点了”、“今天星期几”或需要基于当前时间进行推理时使用。

        Returns:
            str: 格式化的当前时间字符串 (例如："2026-03-14 星期六 17:06")。
        """
    result = get_current_time_impl()
    return result

# @mcp.tool()
# def get_weather(city_name:str) -> Dict[str,Any]:
#     """
#     查询指定城市的实时天气状况。
#     包含温度、天气现象 (晴/雨/雪)、湿度、风向等信息。
#     当用户询问“某地天气怎么样”、“明天要不要带伞”时使用。
#
#     Args:
#         city_name: 城市名称 (例如："北京", "Shanghai", "纽约")。
#
#     Returns:
#         Dict[str, Any]: 包含天气详细信息的字典 (如 temperature, condition, humidity 等)。
#     """
#     result = get_weather_impl(city_name)
#     return result

@mcp.tool()
def web_search(query: str) -> str:
    """
        在互联网上搜索最新的新闻、知识、数据或特定问题的答案。
        当用户询问实时新闻、最新技术动态、或者模型训练数据截止之后的知识时使用。

        Args:
            query: 搜索关键词或具体问题。

        Returns:
            str: 搜索结果的摘要或关键信息片段。
        """
    result =web_search_impl(query)
    return result


print("正在启动 XiaoGui-Assistant MCP Server...")
mcp.run()
