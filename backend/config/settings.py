from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # === DeepSeek 配置 ===
    deepseek_api_key: str  # 这里定义字段
    deepseek_model: str = "deepseek-chat" # DeepSeek 模型名
    deepseek_base_url: str = "https://api.deepseek.com/v1" # DeepSeek 的兼容 OpenAI 接口地址

    class Config:
        env_file = ".env"  # 确保这里指向根目录下的 .env
        env_file_encoding = 'utf-8'

# 实例化设置,可以在其他文件中调用这个实例的属性
settings = Settings()