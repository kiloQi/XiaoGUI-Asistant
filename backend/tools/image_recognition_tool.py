import os
import base64
import logging
from typing import Optional
from openai import OpenAI
from dotenv import load_dotenv

# 加载 .env 环境变量
load_dotenv()

# 配置日志
logger = logging.getLogger(__name__)


def analyze_image(image_path: str) -> Optional[str]:
    """
    使用豆包视觉模型分析本地图片
    返回：成功时返回描述文本；失败时返回以'错误：'开头的字符串
    """
    # 1. 从环境变量获取配置
    api_key = os.getenv("DOUBAO_API_KEY")
    base_url = os.getenv("DOUBAO_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")
    model_name = os.getenv("DOUBAO_MODEL_NAME")

    # 基础校验
    if not api_key or not model_name:
        logger.error("❌ 错误：未找到 DOUBAO_API_KEY 或 DOUBAO_MODEL_NAME")
        return "错误：服务器配置缺失 (缺少 API Key 或模型名称)"

    logger.info(f" 正在调用豆包视觉模型：{model_name}")
    logger.info(f" 准备分析图片：{image_path}")

    # 2. 初始化客户端
    client = OpenAI(
        api_key=api_key,
        base_url=base_url,
        timeout=30.0  # 增加超时设置，防止网络卡死
    )

    # 3. 处理本地图片：转换为 Base64
    try:
        ext = os.path.splitext(image_path)[1].lower()

        # 映射扩展名到 MIME 类型
        mime_map = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.webp': 'image/webp',
            '.bmp': 'image/bmp'
        }

        mime_type = mime_map.get(ext, 'image/jpeg')  # 默认当作 jpeg

        with open(image_path, "rb") as image_file:
            base64_image = base64.b64encode(image_file.read()).decode('utf-8')

        # 构造 Data URI
        image_data_url = f"data:{mime_type};base64,{base64_image}"
        logger.debug(f"图片 MIME 类型识别为：{mime_type}")

    except FileNotFoundError:
        logger.error(f"❌ 文件未找到：{image_path}")
        return "错误：找不到指定的图片文件"
    except Exception as e:
        logger.error(f"❌ 图片读取失败：{str(e)}")
        return f"错误：图片读取失败 - {str(e)}"

    # 4. 调用 API
    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": image_data_url
                            },
                        },
                        {
                            "type": "text",
                            "text": "请详细描述这张图片的内容。如果图片中包含文字，请一并提取。"
                        },
                    ],
                }
            ],
            max_tokens=1024,
        )

        # 5. 返回结果
        if response.choices and len(response.choices) > 0:
            result = response.choices[0].message.content
            logger.info("✅ 图片分析成功")
            return result
        else:
            logger.warning("⚠️ API 返回为空")
            return "错误：API 返回内容为空"

    except Exception as e:
        error_msg = str(e)
        logger.error(f"❌ API 调用失败：{error_msg}")

        # 统一返回格式，确保主程序能识别为失败
        if "SSLEOFError" in error_msg or "EOF" in error_msg or "Connection" in error_msg:
            return "错误：网络连接失败 (可能是模型名称错误或网络不通)"
        elif "401" in error_msg or "Unauthorized" in error_msg:
            return "错误：API Key 无效或权限不足"
        elif "404" in error_msg:
            return "错误：模型不存在 (请检查 .env 中的模型名称)"
        elif "Rate limit" in error_msg or "429" in error_msg:
            return "错误：请求过于频繁，请稍后再试"
        else:
            return f"错误：API 调用异常 - {error_msg}"

