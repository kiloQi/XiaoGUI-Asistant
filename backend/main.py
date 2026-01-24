# main.py
from backend.tools.llm_tool import ask_deepseek

if __name__ == "__main__":
    print("🚀 开始测试 XiaoGui Assistant...")

    # 1. 先简单测试一下配置是否加载成功 (可选)
    # 注意：如果 main.py 和 .env 不在同级，可能会读不到，但只要 tools 能读到就行
    # from backend.config.settings import settings
    # print(f"当前模型: {settings.DEEPSEEK_MODEL}")

    # 2. 调用模型提问
    user_question = "请用中文解释一下什么是递归？"
    print(f"\n👤 提问: {user_question}")

    answer = ask_deepseek(user_question)
    print(f"\n🤖 DeepSeek 回答: {answer}")