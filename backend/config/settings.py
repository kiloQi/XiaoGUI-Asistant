import os
from dotenv import load_dotenv

current_dir = os.path.dirname(os.path.abspath(__file__))

root_dir = os.path.dirname(os.path.dirname(current_dir))

env_path = os.path.join(root_dir, ".env")

load_dotenv(dotenv_path=env_path, override=True)

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_MODEL_NAME = os.getenv("DEEPSEEK_MODEL_NAME",)
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL")

AMAP_WEATHER_KEY = os.getenv("AMAP_WEATHER_KEY", "a77d88e47400085190ed7d026002f905")

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "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")



