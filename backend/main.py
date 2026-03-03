import asyncio
from datetime import datetime
import logging
import os
from fastapi import FastAPI, UploadFile, File,HTTPException
from starlette.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastmcp import FastMCP
import json
from backend.agents.workflow import build_workflow
from contextlib import asynccontextmanager

mcp = FastMCP("XiaoGui-Assistant")

# 在这里统一导入工具，确保主程序启动时自动加载
from backend.tools import (web_search_tool,
                    calc_tool,
                    weather_tool,
                    time_tool,
                    image_recognition_tool,
                    export_chat_tool,
                    file_parsing_tool)


#全局变量定义
workflow_app=None
#创建logs目录
os.makedirs("logs", exist_ok=True)

#配置日志
logging.basicConfig(
    level=logging.INFO,
format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
handlers=[
    logging.FileHandler('logs/app.log', encoding="utf-8"),
    logging.StreamHandler()     #把结果输出到控制台

])
logger = logging.getLogger(__name__)   #后面用来记录日志的对象

@asynccontextmanager
async def lifespan(app: FastAPI):      #生命周期函数
    global workflow_app
    logger.info("正在初始化 LangGraph 工作流和大模型...")
    try:
        workflow_app = await build_workflow()
        logger.info("✅ 工作流初始化成功！")
    except Exception as e:
        logger.error(f"❌ 工作流初始化失败: {e}")
        logger.error("请检查网络连接。")
        raise

    yield
    logger.info("服务器正在关闭...")
app=FastAPI(title="XiaoGui Assistant",version="1.0",lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.get("/")
def read_root():
    logger.info("访问了根路径")
    return {"message": "欢迎使用小桂助手"}

@app.post("/call_tool")
def call_tool(tool_name:str,params:dict={}):
    """
    动态调用已注册的fastmcp工具
    :param tool_name:工具名称
    :param params:参数字典，如{“expression”：“2+3”}
    :return:工具执行结果
    """
    try:
        result=mcp.call_tool(tool_name,params)
        return {"success":True,"result":result}
    except Exception as e:
        logger.error(f"调用工具{tool_name}失败:{e}")
        return {"success":False,"error":e}


@app.post("/upload_and_parse")
async def upload_file(file: UploadFile = File(...)):
    """上传和解析文件"""
    try:
        logger.info(f"收到上传文件：{file.filename}")

        # 1. 保存文件
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_filename = f"{timestamp}_{file.filename}"
        save_path = os.path.join(UPLOAD_DIR, safe_filename)

        content = await file.read()
        with open(save_path, "wb") as f:
            f.write(content)
        logger.info(f"📄文件已保存：{save_path} (大小：{len(content)} bytes)")

        # 2. 解析文件 (TXT 直接读，其他调用工具)
        texts = []
        file_ext = os.path.splitext(file.filename)[1].lower()

        if file_ext in ['.txt', '.md']:
            try:
                with open(save_path, 'r', encoding='utf-8', errors='ignore') as f:
                    text_content = f.read()
                lines = [line.strip() for line in text_content.split('\n') if line.strip()]
                if not lines:
                    raise ValueError("文件内容为空")
                texts = lines
                logger.info(f"📄 [TXT/MD] 从磁盘读取成功，共 {len(texts)} 行")
            except Exception as e:
                logger.error(f"❌ 读取文件失败：{e}")
                raise HTTPException(status_code=400, detail=f"文件读取失败：{str(e)}")
        elif file_ext in ['.pdf', '.docx', '.doc']:
            from backend.tools.file_parsing_tool import parse_file
            try:
                logger.info(f"正在调用 parse_file 解析 {file_ext} ...")
                result = parse_file(str(save_path))

                if isinstance(result, list):
                    texts = result
                elif isinstance(result, str):
                    texts = [result]
                elif isinstance(result, dict):
                    if result.get("status") == "error":
                        msg = result.get("message") or "解析器内部发生未知错误"
                        raise ValueError(f"解析器报错：{msg}")
                    texts = result.get("chunks", []) or ([result["full_text"]] if result.get("full_text") else [])
                else:
                    raise TypeError(f"parse_file 返回了不支持的类型：{type(result)}")

                if not texts:
                    raise ValueError("解析结果为空")
                logger.info(f"📄 [{file_ext}] 工具解析成功，共 {len(texts)} 段")

            except ImportError as ie:
                raise HTTPException(status_code=400,
                                    detail=f"缺少解析库：{str(ie)}. 请运行: pip install pdfplumber docx2txt")
            except Exception as parse_err:
                logger.error(f"❌ {file_ext} 解析失败详情:", exc_info=True)
                raise HTTPException(status_code=400, detail=f"{file_ext} 解析失败：{str(parse_err)}")
        else:
            raise HTTPException(status_code=400, detail=f"暂不支持的文件格式：{file_ext}")

        # 3.存入向量库 (分批处理，防止内存爆炸)
        from backend.agents.workflow import rag_agent

        if rag_agent.embedding_model is None:
            raise HTTPException(status_code=500, detail="❌ 嵌入模型未加载")

        if rag_agent.vectorstore is None:
            logger.info("向量库尚未初始化，将在存入第一批数据时自动创建...")

        # 开始分批存入
        batch_size = 100  # 每次只存 100 条
        total_count = len(texts)
        logger.info(f"开始分批存入向量库，共 {total_count} 条，每批 {batch_size} 条...")
        from langchain_community.vectorstores import FAISS
        from langchain_core.documents import Document
        logger.info("正在手动计算所有文本的向量...")
        try:
            # 1. 显式调用适配器的 embed_documents
            all_vectors = rag_agent.embedding_model.embed_documents(texts)
            logger.info(f"✅ 向量计算完成：{len(all_vectors)} 个向量，维度 {len(all_vectors[0])}")
        except Exception as calc_err:
            logger.error(f"❌ 向量计算失败：{calc_err}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"向量计算失败：{str(calc_err)}")

        # 2. 准备元数据
        metadatas = [{"source": safe_filename, "index": i} for i in range(len(texts))]

        # 3. 构建或追加
        if rag_agent.vectorstore is None:
            # 第一次：使用 from_embeddings (接收算好的向量)
            # 格式要求：List[Tuple[str, List[float]]]
            text_embedding_pairs = list(zip(texts, all_vectors))

            rag_agent.vectorstore = FAISS.from_embeddings(
                text_embeddings=text_embedding_pairs,
                embedding=rag_agent.embedding_model,
                metadatas=metadatas
            )
            logger.info("向量库首次创建成功！")
        else:
            # 已有库：使用 add_embeddings 追加
            text_embedding_pairs = list(zip(texts, all_vectors))

            rag_agent.vectorstore.add_embeddings(
                text_embeddings=text_embedding_pairs,
                metadatas=metadatas
            )
            logger.info("向量库追加成功！")

        logger.info(f"✅ 完美！所有数据已入库。")

        return {
            "status": "success",
            "message": f"✅ 文件《{file.filename}》已学习完毕！共解析 {total_count} 个片段。",
            "saved_path": str(save_path),
            "filename": safe_filename,
            "parse_data": {
                "chunk_count": total_count,
                "preview": texts[0][:100] + "..." if texts else ""
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"错误捕获：{e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
@app.post("/chat")
async def chat(request: dict):
    # 1. 初始化检查
    if not workflow_app:
        raise HTTPException(status_code=503, detail="服务器正在初始化中，请稍后重试")

    # 2. 提取数据
    user_msg = request.get("message", "")
    file_path = request.get("file_path", "")
    config = request.get("config", {})

    logger.info(f"收到信息：{user_msg}")

    # 3. 构造状态 (LangGraph 的 messages 必须是列表)
    initial_state = {
        "messages": [user_msg],
        "context": "",
        "uploaded_file": file_path
    }

    # 4. 定义生成器函数
    async def generate():
        try:
            #传入 config (包含 thread_id)
            response = await workflow_app.ainvoke(initial_state, config=config)

            # 提取 AI 的回答
            final_messages = response.get("messages", [])

            if final_messages:
                # 获取最后一条消息（AI 的回复）
                ai_response = final_messages[-1]

                # 逐字输出
                for char in ai_response:
                    yield f"data: {json.dumps({'token': char})}\n\n"
                    await asyncio.sleep(0.02)
            else:
                yield f"data: {json.dumps({'token': '❌ 未生成任何回复'})}\n\n"

        except Exception as e:
            logger.error(f"流式处理出错：{e}")
            # 错误也要通过流返回给前端，方便调试
            yield f"data: {json.dumps({'token': f'❌ 发生错误：{str(e)}'})}\n\n"

    # 5. 返回流式响应
    return StreamingResponse(generate(), media_type="text/event-stream")
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

