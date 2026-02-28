import os
#加载.env文件
from dotenv import load_dotenv

load_dotenv()

DEEPSEEK_API_KEY=os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_MODEL_NAME=os.getenv("DEEPSEEK_MODEL_NAME","deepseek_chat")
DEEPSEEK_BASE_URL=os.getenv("DEEPSEEK_BASE_URL")

if not DEEPSEEK_API_KEY:
    raise ValueError("未找到DEEPSEEK_API_KEY，请检查.env配置")