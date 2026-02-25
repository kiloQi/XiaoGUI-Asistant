import  os
from langchain_community.document_loaders import (TextLoader,
                                                  PyPDFLoader,
                                                  Docx2txtLoader)
from langchain_text_splitters import RecursiveCharacterTextSplitter

def parse_file(file_path:str):
    """文档解析函数"""

    if not os.path.exists(file_path):
        return {"status":"error","messages":f"文件不存在{file_path}："}

    ext = os.path.splitext(file_path)[1].lower()

    loader=None

    try:

        if ext == ".txt":
            loader=TextLoader(file_path,encoding="utf-8")
        elif ext == ".pdf":
            loader=PyPDFLoader(file_path,)
        elif ext in [".docx",".doc"]:
            loader=Docx2txtLoader(file_path)

        else:
            return {"status":"error","messages":f"不支持文件格式：{ext}"}

        #提取文字
        documents=loader.load()     #读取文件里面的内容
        full_text="\n".join([doc.page_content  for doc in documents])

        #文本切分
        text_splitter=RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=50,
            length_function=len,
            separator=["\n\n","\n", " ","" ]
        )
        chunks=text_splitter.split_documents(documents)

        #   这个列表将来就是要存入数据库，让大模型去检索的“知识碎片”。
        chunk_texts=[chunk.page_content for chunk in chunks]

        return {"status":"success",
                "full_text":full_text,
                "chunks":chunk_texts,
                "filename":os.path.basename(file_path),
                "chunk_count":len(chunk_texts)}

    except Exception as e:
        return {"status":"error","messages":str(e)}








