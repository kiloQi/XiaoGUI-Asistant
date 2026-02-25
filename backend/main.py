from datetime import datetime
import logging
import os
from fastapi import FastAPI, UploadFile, File,HTTPException
from starlette.middleware.cors import CORSMiddleware
from pathlib import Path
from backend.tools import mcp
from backend.tools.file_parsing_tool import parse_file
import shutil

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
logger = logging.getLogger(__name__)  #是你后面用来记录日志的对象


app=FastAPI(title="XiaoGui Assistant",version="1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境建议指定具体域名
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
    """接受上传的文件并解析"""
    try:
        logger.info(f"收到上传文件:{file.filename}")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_filename = f"{timestamp}_{file.filename}"
        save_path = os.path.join(UPLOAD_DIR, safe_filename)

        #读取并保存文件
        content=await file.read()
        with open(save_path,"wb") as f:
            f.write(content)

        logger.info(f"文件保存成功:{save_path}")

        parse_result=parse_file(str(save_path))

        if parse_result.get("status")=="error":
            logger.warning(f"文件保存成功但解析失败: {parse_result.get('message')}")

            return {
                "status":"success",
                "message":f"文件{file.filename}上传成功,但解析失败{parse_result.get('message')}：",
                "prase_status":"failed",
                "file_size":len(content)
        }

        logger.info(f"解析成功！共分为{parse_result.get('chunk_count')}块")
        return {
            "status": "success",
            "message": f"文件 {file.filename} 上传并解析成功",
            "saved_path": str(save_path),
            "file_size": len(content),
            "filename": safe_filename,
            "parse_data": {
                "full_text_preview": parse_result.get("full_text")[:500] + "...",
                "chunk_count": parse_result.get("chunk_count"),
                "chunks": parse_result.get("chunks")
            }
        }

    except Exception as e:
        logger.error(f"上传或解析过程中发生错误:{str(e)}")
        raise HTTPException(status_code=400,detail=str(e))
