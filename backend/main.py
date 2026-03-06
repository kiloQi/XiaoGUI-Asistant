from datetime import datetime
import logging
import os
import sys
from fastapi import FastAPI, UploadFile, File, HTTPException
from starlette.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import json
from contextlib import asynccontextmanager
from langchain_core.messages import HumanMessage

# 从 workflow.py 导入
from backend.agents.workflow import build_workflow, rag_agent

workflow_app = None

os.makedirs("logs", exist_ok=True)
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler('logs/app.log', encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app:FastAPI):
    global workflow_app
    if 'sqlite3' in sys.modules:
        logger.error("  sqlite3 已加载")
    else:
        logger.info("✅ sqlite3 未加载")

    logger.info(" 初始化 LangGraph...")
    try:
        from langgraph.checkpoint.memory import MemorySaver
        saver = MemorySaver()
        graph_builder = await build_workflow()
        workflow_app = graph_builder.compile(checkpointer=saver)
        logger.info("✅ 服务启动成功 (支持流式输出)")
        yield
    except Exception as e:
        logger.error(f"❌ 初始化失败：{e}", exc_info=True)
        raise


app = FastAPI(title="XiaoGui Assistant", version="1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"],
                   allow_headers=["*"])


@app.get("/")
def read_root():
    return {"status": "running"}


@app.post("/upload_and_parse")
async def upload_and_parse(file: UploadFile = File(...)):
    logger.info(f" 收到上传请求：文件名={file.filename}, 类型={file.content_type}")

    try:
        # 1. 保存文件
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # 清理文件名中的非法字符
        safe_name = "".join(c for c in file.filename if c.isalnum() or c in ('.', '_', '-'))
        save_filename = f"{timestamp}_{safe_name}"
        save_path = os.path.join(UPLOAD_DIR, save_filename)

        logger.info(f" 正在保存文件到：{save_path}")

        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="文件内容为空")

        with open(save_path, "wb") as f:
            f.write(content)

        logger.info(f"✅ 文件保存成功，大小：{len(content)} bytes")

        # 2. 检查模型
        if rag_agent.embedding_model is None:
            logger.error("❌ Embedding 模型未加载")
            raise HTTPException(status_code=500, detail="Embedding 模型未加载，请检查后端启动日志")

        # 3. 解析文件
        logger.info(f" 开始解析文件：{save_filename}")
        try:
            texts = rag_agent.parse_file(save_path)
        except Exception as parse_err:
            logger.error(f"❌ 解析过程出错：{parse_err}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"解析失败：{str(parse_err)}")

        if not texts:
            logger.warning("⚠️ 解析结果为空")
            # 不报错，但提示用户
            return {
                "status": "warning",
                "message": f"⚠️ 文件《{file.filename}》已接收，但未提取到有效文本（可能是扫描件或加密PDF）",
                "chunk_count": 0
            }

        # 4. 存入向量库
        logger.info(f" 正在入库 {len(texts)} 个片段...")
        success = rag_agent.add_documents(texts)

        if not success:
            raise HTTPException(status_code=500, detail="向量库入库失败")

        logger.info(f" 处理完成：{file.filename}")
        return {
            "status": "success",
            "message": f"✅ 文件《{file.filename}》已学习完毕！共解析 {len(texts)} 段",
            "chunk_count": len(texts)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f" 上传处理总异常：{e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/chat")
async def chat(request: dict):
    if not workflow_app:
        raise HTTPException(status_code=503, detail="服务未就绪")

    user_msg_text = request.get("message", "")
    thread_id = request.get("config", {}).get("thread_id", "default")

    if not user_msg_text:
        raise HTTPException(status_code=400, detail="消息不能为空")

    logger.info(f" 收到消息：{user_msg_text[:30]}... (Thread: {thread_id})")

    initial_state = {
        "messages": [HumanMessage(content=user_msg_text)],
        "context": "",
        "uploaded_file": None
    }
    config = {"configurable": {"thread_id": thread_id}}

    async def generate():
        try:
            async for event in workflow_app.astream_events(
                    initial_state,
                    config=config,
                    version="v2"
            ):
                kind = event.get("event")

                if kind == "on_chat_model_stream":
                    chunk = event.get("data", {}).get("chunk")
                    event.get("metadata", {})

                    if not chunk or not hasattr(chunk, "content"):
                        continue

                    content = chunk.content

                    if not isinstance(content, str):
                        continue

                    content = content.strip()
                    if not content:
                        continue

                    if "Action Input" in content or ("{" in content and "action" in content.lower()):
                        continue

                    if content.startswith("Thought:") and len(content) < 60:
                        continue

                    try:
                        data = json.dumps({"content": content}, ensure_ascii=False)
                        yield f"data: {data}\n\n"
                    except Exception as json_err:
                        logger.warning(f"JSON 序列化跳过: {json_err}")
                        continue

            yield "data: [DONE]\n\n"
            logger.info("✅ 流式输出正常结束")

        except Exception as e:
            logger.error(f" 流式生成异常：{e}", exc_info=True)
            # 发送友好的错误信息，而不是让前端猜
            err_content = f"❌ 生成中断：{str(e)}"
            try:
                data = json.dumps({"content": err_content}, ensure_ascii=False)
                yield f"data: {data}\n\n"
            except:
                pass
            finally:
                yield "data: [DONE]\n\n"

    # 设置正确的 Header，防止浏览器缓存或截断
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # 针对 Nginx 代理的情况
        }
    )
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)