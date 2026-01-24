import openai
from backend.config.settings import settings  # 从父级目录的 config 导入 settings

# 初始化客户端
# DeepSeek 兼容 OpenAI 的格式
client = openai.OpenAI(
    api_key=settings.deepseek_api_key,      # 从 settings 取密钥
    base_url=settings.deepseek_base_url

)

def ask_deepseek(question: str) -> str:
    """
    调用 DeepSeek 模型解答问题
    """
    try:
        response = client.chat.completions.create(
            model=settings.deepseek_model,  # 从 settings 取模型名
            messages=[
                {"role": "system", "content": "你是一个乐于助人的 AI 助手。"},
                {"role": "user", "content": question}
            ]
        )
        # 返回模型的回答文本
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"调用模型时出错：{str(e)}"