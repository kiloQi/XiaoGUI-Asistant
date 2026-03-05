import base64
import os
from typing import Dict, Any

import requests

from backend.main import mcp

_IMAGE_RECOGNIZE_TOOL_REGISTERED = False

class DeepSeekImageRecognizer:
    """
    使用DeepSeek-VL模型进行图片识别的类
    """

    def recognize_image(self, image_path: str, question: str = "请描述这张图片的内容") -> Dict[str, Any]:
        """
        使用DeepSeek-VL模型进行图片识别
        """
        # 1.读取图片并转base64
        try:
            with open(image_path, "rb") as f:
                image_data = base64.b64encode(f.read()).decode("utf-8")

                # 判断图片后缀，DeepSeek支持jpeg,png等
                # 默认当作是jpeg，如果是png可以改成mime类型
                mime_type = "image/jpeg"
                if image_path.lower().endswith(".png"):
                    mime_type = "image/png"

        except FileNotFoundError:
            return {"success": False, "error": "找不到图片文件，请检查路径"}

        # 2.构造请求头
        headers = {
            "Authorization": f"Bearer {os.getenv('DEEPSEEK_API_KEY')}",
            "Content-Type": f"application/json",
        }

        # 3.构造请求体
        payload = {
            "model": "deepseek-vl",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        # 图片部分
                        {
                            "type": "image_url",
                            "image_url": {
                                "type": f"data:{mime_type};base64,{image_data}",
                            }
                        },

                        # 文字问题部分
                        {
                            "type": "text",
                            "text": question
                        }
                    ]
                }
            ],
            "max_tokens": 1024
        }

        # 4.发送请求(DeepSeek 的接口地址)
        url = "https://api.deepseek.com/v1/chat/completions"

        try:
            response = requests.post(url, headers=headers, json=payload)
            if response.status_code == 200:
                result = response.json()
                # 提取回答内容
                answer = result["choices"][0]["message"]["content"]
                return {"success": True, "answer": answer}
            else:
                error_msg = response.text
                return {"success": False, "error": error_msg}

        except Exception as e:
            return {"success": False, "error": f"程序异常{str(e)}"}


image_recognizer_instance = DeepSeekImageRecognizer()

image_recognizer_instance.recognize_image = mcp.tool(
    name="image_recognize",  # 和LangChain中工具名完全一致
    description="图片识别工具，使用DeepSeek-VL模型识别图片内容，支持自定义识别问题",
)(image_recognizer_instance.recognize_image)


# 注册到mcp,是他发挥fastmcp一样的功能
def register_image_recognize_tool():
    """注册图片识别工具（确保只注册一次）"""
    global _IMAGE_RECOGNIZE_TOOL_REGISTERED
    if not _IMAGE_RECOGNIZE_TOOL_REGISTERED:
        try:
            mcp.add_tool(image_recognizer_instance.recognize_image)
            _IMAGE_RECOGNIZE_TOOL_REGISTERED = True
        except Exception as e:
            _IMAGE_RECOGNIZE_TOOL_REGISTERED = True


register_image_recognize_tool()


def get_image_recognizer_tool():
    """获取图片识别工具实例"""
    return image_recognizer_instance
