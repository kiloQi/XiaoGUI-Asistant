import os
from typing import Dict, Optional

from langchain_community.document_loaders import TextLoader, PyPDFLoader, Docx2txtLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

from . import mcp

_FILE_PARSE_TOOL_REGISTERED = False

class FileParser:
    """
    支持解析TXT、PDF、DOCX/DOC格式文件，提取全文并切分为指定大小的文本块
    """
    SUPPORTED_FORMATS = {
        ".txt": TextLoader,
        ".pdf": PyPDFLoader,
        ".docx": Docx2txtLoader,
        ".doc": Docx2txtLoader
    }

    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50):
        """
        初始化文件解析器
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.text_splitter = self._init_text_splitter()

    def _init_text_splitter(self) -> RecursiveCharacterTextSplitter:
        """初始化文本切分器"""
        return RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", " ", ""]
        )

    def _get_loader(self, file_path: str) -> Optional[object]:
        """根据文件扩展名获取对应的加载器"""
        ext = os.path.splitext(file_path)[1].lower()
        loader_class = self.SUPPORTED_FORMATS.get(ext)

        if not loader_class:
            return None

        if ext == ".txt":
            return loader_class(file_path, encoding="utf-8")
        else:
            return loader_class(file_path)

    def parse_file(self, file_path: str) -> Dict:
        """
        解析指定文件，提取全文并切分文本块
        """
        # 1. 校验文件路径
        if not isinstance(file_path, str) or not file_path.strip():
            return {"status": "error", "messages": "文件路径不能为空"}

        file_path = file_path.strip()
        if not os.path.exists(file_path):
            return {"status": "error", "messages": f"文件不存在：{file_path}"}

        # 2. 获取文件加载器
        loader = self._get_loader(file_path)
        if not loader:
            ext = os.path.splitext(file_path)[1].lower()
            return {"status": "error", "messages": f"不支持的文件格式：{ext}"}

        try:
            # 3. 加载并提取全文
            documents = loader.load()
            full_text = "\n".join([doc.page_content for doc in documents])

            # 4. 切分文本块
            chunks = self.text_splitter.split_documents(documents)
            chunk_texts = [chunk.page_content for chunk in chunks]

            return {
                "status": "success",
                "full_text": full_text,
                "chunks": chunk_texts,
                "filename": os.path.basename(file_path),
                "chunk_count": len(chunk_texts)
            }

        except Exception as e:
            return {"status": "error", "messages": f"文件解析失败：{str(e)}"}


default_file_parser = FileParser(chunk_size=500, chunk_overlap=50)

default_file_parser.parse_file = mcp.tool(
    name="file_parse",
    description="文件解析工具，支持解析TXT、PDF、DOCX/DOC格式文件，提取全文并切分为指定大小的文本块",
)(default_file_parser.parse_file)


# 注册到mcp,是他发挥fastmcp一样的功能
def register_file_parse_tool():
    """注册文件解析工具（确保只注册一次）"""
    global _FILE_PARSE_TOOL_REGISTERED
    if not _FILE_PARSE_TOOL_REGISTERED:
        try:
            mcp.add_tool(default_file_parser.parse_file)
            _FILE_PARSE_TOOL_REGISTERED = True
        except Exception as e:
            _FILE_PARSE_TOOL_REGISTERED = True


register_file_parse_tool()


def get_file_parser_tool(chunk_size: int = 500, chunk_overlap: int = 50):
    """获取文件解析工具实例"""
    custom_parser = FileParser(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    custom_parser.parse_file = mcp.tool(
        name="file_parse",
        description="文件解析工具，支持解析TXT、PDF、DOCX/DOC格式文件，提取全文并切分为指定大小的文本块",
        parameters={
            "file_path": {
                "type": "string",
                "description": "文件的绝对路径字符串（如D:/test.pdf、C:/docs/报告.txt）",
                "required": True
            }
        }
    )(custom_parser.parse_file)
    mcp.add_tool(custom_parser.parse_file)
    return custom_parser
