import openai
from ..config.settings import settings  # 从父级目录的 config 导入 settings

# 初始化客户端
# DeepSeek 兼容 OpenAI 的格式
client = openai.OpenAI(
    api_key=settings.DEEPSEEK_API_KEY,      # 从 settings 取密钥
    base_url=settings.DEEPSEEK_BASE_URL    # 从 settings 取网址
)

def ask_deepseek(question: str) -> str:
    """
    调用 DeepSeek 模型解答问题
    """
    try:
        response = client.chat.completions.create(
            model=settings.DEEPSEEK_MODEL,  # 从 settings 取模型名
            messages=[
                {"role": "system", "content": "你是一个乐于助人的 AI 助手。"},
                {"role": "user", "content": question}
            ]
        )
        # 返回模型的回答文本
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"调用模型时出错：{str(e)}"