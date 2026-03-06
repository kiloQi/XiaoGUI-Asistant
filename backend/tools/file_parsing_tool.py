import os
import logging
from typing import List
from langchain_community.document_loaders import (TextLoader, PyPDFLoader, Docx2txtLoader)
from langchain_text_splitters import RecursiveCharacterTextSplitter

logger = logging.getLogger(__name__)


def parse_file(file_path: str) -> List[str]:
    """
    文档解析函数
    返回：List[str] (切分后的文本片段列表)
    """

    if not os.path.exists(file_path):
        logger.error(f"❌ 文件不存在：{file_path}")
        return []

    ext = os.path.splitext(file_path)[1].lower()
    loader = None

    try:
        # 1. 根据扩展名选择加载器
        if ext == ".txt":
            # 尝试多种编码，防止中文乱码报错
            encodings = ['utf-8', 'gbk', 'gb2312', 'latin-1']
            for enc in encodings:
                try:
                    loader = TextLoader(file_path, encoding=enc)
                    logger.info(f"✅ 使用 {enc} 编码加载 TXT 成功")
                    break
                except UnicodeDecodeError:
                    continue
            if loader is None:
                raise ValueError("无法识别的文本编码")

        elif ext == ".pdf":
            loader = PyPDFLoader(file_path)

        elif ext in [".docx", ".doc"]:
            loader = Docx2txtLoader(file_path)

        elif ext in [".jpg", ".jpeg", ".png", ".bmp"]:
            # 【临时方案】图片暂不解析，返回空列表，避免报错
            # 如果需要 OCR，需安装 pytesseract 并在此处添加逻辑
            logger.warning(f"⚠️ 图片文件暂不支持 OCR 解析：{file_path}")
            return []

        else:
            logger.error(f"❌ 不支持的文件格式：{ext}")
            return []

        # 2. 提取文字
        documents = loader.load()

        if not documents:
            logger.warning(f"⚠️ 文件内容为空：{file_path}")
            return []

        # 3. 文本切分
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=50,
            length_function=len,
            separators=["\n\n", "\n", " ", ""]
        )

        chunks = text_splitter.split_documents(documents)

        # 4. 提取纯文本内容并返回列表
        chunk_texts = [chunk.page_content.strip() for chunk in chunks if chunk.page_content.strip()]

        logger.info(f" 解析成功：{os.path.basename(file_path)} -> {len(chunk_texts)} 个片段")
        return chunk_texts

    except Exception as e:
        logger.error(f" 解析文件失败：{file_path} | 错误：{str(e)}", exc_info=True)
        # 出错时返回空列表，而不是抛出异常或返回字典
        return []








