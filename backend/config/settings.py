from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).parent.parent.parent  # 这会指向 D:\XiaoGui-Assistant

class Settings(BaseSettings):
    deepseek_api_key: str
    deepseek_model: str
    deepseek_base_url: str = "https://api.deepseek.com/v1"

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",  # <--- 强制指定 .env 的绝对路径
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()