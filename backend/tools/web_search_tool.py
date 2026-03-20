def web_search(query: str) -> str:

    print(f"正在搜索：{query} ...")

    try:
        # 在这里直接初始化客户端，不再依赖 self
        from tavily import TavilyClient
        import os

        api_key = os.getenv("TAVILY_API_KEY")
        if not api_key:
            return "⚠️ 错误：未找到 TAVILY_API_KEY 环境变量，请配置后重试。"

        tavily_client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

        response = tavily_client.search(
            query=query,
            search_depth="advanced",
            max_results=5,
            include_answer=False,
            include_raw_content=False
        )

        results = response.get('results', [])
        if not results:
            return f" 关于【{query}】未找到相关结果，请尝试更换关键词。"

        lines = []

        if response.get('answer'):
            summary = response['answer'][:300] + ("..." if len(response['answer']) > 300 else "")
            lines.append(f" **智能摘要**: {summary}\n")

        lines.append(f" **搜索结果** (共 {len(results)} 条):\n")

        for i, result in enumerate(results):
            title = result.get('title', '无标题')
            content = result.get('content', '无摘要')
            url = result.get('url', '#')

            safe_content = content.replace('$', '').replace('\n', ' ')
            safe_title = title.replace('$', '')

            # 限制每条内容的长度
            if len(safe_content) > 150:
                safe_content = safe_content[:150] + "..."

            lines.append(f"**{i + 1}. {safe_title}**\n- {safe_content}\n- [链接]({url})\n")

        # 拼接所有行
        final_text = "\n".join(lines)

        #如果总长度超过 2000 字，强制截断
        if len(final_text) > 2000:
            final_text = final_text[:2000] + "\n\n*(内容过长，已自动截断)*"

        return final_text

    except Exception as e:
        error_msg = f"⚠️ 搜索服务异常：{str(e)[:100]}"
        print(f"搜索出错详情：{e}")
        return error_msg