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
from langchain_mcp_adapters.client import MultiServerMCPClient

# 从 workflow.py 导入
from backend.agents.workflow import build_workflow, rag_agent

workflow_app = None

os.makedirs("logs", exist_ok=True)
os.makedirs("uploads", exist_ok=True)

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
    logger.info("正在启动 XiaoGui (FastMCP 模式)...")

    mcp_tools = []
    try:

        mcp_script_path = r"D:\XiaoGui-Assistant\mcp_server.py"
        logger.info(f"正在连接 MCP Server: {mcp_script_path}")

        client = MultiServerMCPClient({
            "XiaoGuiTools": {
                "command": sys.executable,
                "args": [mcp_script_path],
                "transport": "stdio"
            }
        })

        mcp_tools = await client.get_tools()
        logger.info(f"✅ MCP 连接成功！获取到 {len(mcp_tools)} 个工具: {[t.name for t in mcp_tools]}")
    except Exception as e:
        logger.error(f"❌ MCP 连接失败: {e}")
        logger.warning("⚠️ 将以无工具模式运行")

    if 'sqlite3' in sys.modules:
        logger.info("  sqlite3 已加载")
    else:
        logger.info("✅ sqlite3 未加载")

    logger.info(" 初始化 LangGraph...")
    try:
        from langgraph.checkpoint.memory import MemorySaver
        saver = MemorySaver()
        graph_builder = await build_workflow(tools=mcp_tools)     #“异步启动”：用了 async/await，体现高性能。
        workflow_app = graph_builder.compile(checkpointer=saver)
        logger.info("✅ 服务启动成功 (支持流式输出)")
        yield
    except Exception as e:
        logger.error(f"❌ 初始化失败：{e}", exc_info=True)
        raise


app = FastAPI(title="XiaoGui Assistant", version="1.0", lifespan=lifespan)
#CORS 中间件，“允许任何来源访问我”，防止前端调不通后端。
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
        #加时间戳，防止两个人同时上传文件，后一个人把前一个人的覆盖，加上时间就独一无二了。
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # 清理文件名中的非法字符
        #只保留字母、数字、点和下划线，把其他奇怪字符全扔掉。防止路径遍历攻击。
        safe_name = "".join(c for c in file.filename if c.isalnum() or c in ('.', '_', '-'))
        save_filename = f"{timestamp}_{safe_name}"
        save_path = os.path.join("uploads", save_filename)

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
                "message": f"⚠️ 文件《{file.filename}》已接收，但未提取到有效文本",
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
    # 取数据：request.get(...) 的套娃写法
    user_msg_text = request.get("message", "")    #message：用户问了什么
    thread_id = request.get("config", {}).get("thread_id", "default")  #thread_id 藏在 config 里面，是二层嵌套的。

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
            #astream_events：这是 LangGraph 的神器。
            async for event in workflow_app.astream_events(
                    initial_state,
                    config=config,
                    version="v2"
            ):
                kind = event.get("event")
                #(if kind == ...)：工作流里会发生很多事（比如调用工具、检索数据库）。
                # 我们只关心 on_chat_model_stream，也就是大模型正在“说话”的时候。
                if kind == "on_chat_model_stream":
                    chunk = event.get("data", {}).get("chunk")
                    event.get("metadata", {})
                #一堆安全检查 (非空、是字符串等)
                    #hasattr(对象, "属性名") 是 Python 的一个内置函数，
                    # 意思是“这个对象身上有没有叫 content 的属性？”。
                    if not chunk or not hasattr(chunk, "content"):
                        continue

                    content = chunk.content

                    #判断 content 是不是字符串类型。
                    if not isinstance(content, str):
                        continue

                    content = content.strip()   #去掉字符串“两头”的空白字符，保留中间的内容。
                    if not content:
                        continue

                    #数据清洗：过滤了 Thought 和 Action Input，提升了用户体验，让前端展示更干净。
                    if "Action Input" in content or ("{" in content and "action" in content.lower()):
                        continue

                    if content.startswith("Thought:") and len(content) < 60:
                        continue

                    try:
                        data = json.dumps({"content": content}, ensure_ascii=False)  #ensure_ascii=False：别转码，直接保留中文字符。
                        #SSE 格式：data: {...}\n\n 是 Server-Sent Events (SSE) 的标准格式，
                        # 浏览器能自动识别这种格式并实时更新页面。
                        #（SSE 协议）：每一句话必须以 data: 开头。
                        #每一句话必须以两个换行符 \n\n 结尾。
                        #内容必须是标准的 JSON 格式，不能是乱码。

                        yield f"data: {data}\n\n"
                    except Exception as json_err:
                        logger.warning(f"JSON 序列化跳过: {json_err}")
                        continue

            yield "data: [DONE]\n\n"
            logger.info("✅ 流式输出正常结束")

        except Exception as e:
            logger.error(f" 流式生成异常：{e}", exc_info=True)
            # 发送友好的错误，即使在流式传输中途报错，也能给用户明确的反馈，而不是静默失败。
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
        media_type="text/event-stream",    #告诉浏览器：“别把这当成普通文本，这是实时事件流，请保持连接并实时渲染。”
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"      # 针对 Nginx 代理的情况，Nginx 默认会把数据攒够一大块再发给用户，这会破坏流式效果。
        }
    )
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)