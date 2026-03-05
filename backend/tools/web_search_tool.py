import os
from typing import Dict, Any

from tavily import TavilyClient

from backend.main import mcp

_WEB_SEARCH_TOOL_REGISTERED = False

class TavilyWebSearcher:
    """基于Tavily API的网页搜索工具类"""
    def __init__(self):
        """初始化Tavily客户端"""
        self.tavily = TavilyClient(api_key=os.environ.get("TAILY_API_KEY"))

    # 移除类内装饰器，改为实例化后装饰
    def web_search(self, query: str) -> Dict[str, Any]:
        """
        搜索函数。
        """
        print(f"正在搜索：{query} ...")

        try:
            # 调用 Tavily 去搜索
            response = self.tavily.search(
                query=query,
                search_depth="advanced",
                max_results=5,
                include_answer=True,
                include_raw_content=False
            )

            if not response.get('results'):
                return {"success": False, "error": "没搜到结果。"}

            # 拼接结果
            final_answer = ""
            if response.get('answer'):
                final_answer += f"**智能摘要**: {response['answer']}\n\n"

            final_answer += f"关于【{query}】的详细搜索结果：\n\n"

            for i, result in enumerate(response['results']):
                title = result.get('title', '无标题')
                content = result.get('content', '无摘要')
                url = result.get('url', '无链接')

                final_answer += f"{i + 1}. **{title}**\n   {content}\n   🔗 [来源]({url})\n\n"

            return {"success": True, "answer": final_answer}

        except Exception as e:
            return {"success": False, "error": f"搜索出错了：{str(e)}"}


search_tool_instance = TavilyWebSearcher()

search_tool_instance.web_search = mcp.tool(
    name="web_search",
    description="网页搜索工具，基于Tavily API搜索指定关键词的网络信息，返回智能摘要和详细结果",
)(search_tool_instance.web_search)


def register_web_search_tool():
    """注册网页搜索工具（确保只注册一次）"""
    global _WEB_SEARCH_TOOL_REGISTERED
    if not _WEB_SEARCH_TOOL_REGISTERED:
        try:
            mcp.add_tool(search_tool_instance.web_search)
            _WEB_SEARCH_TOOL_REGISTERED = True
        except Exception as e:
            _WEB_SEARCH_TOOL_REGISTERED = True


register_web_search_tool()


def get_search_tool():
    """获取绑定好的网页搜索工具方法"""
    return search_tool_instance.web_search
