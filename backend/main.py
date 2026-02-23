from datetime import datetime
import logging
import os
from fastapi import FastAPI, UploadFile, File
from starlette.middleware.cors import CORSMiddleware

from backend.tools import mcp
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



@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """接受上传的文件并保存"""
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

        return {
            "status":"success",
            "message":f"文件{file.filename}上传成功",
            "saved_path":save_path,
            "file_size":len(content)
        }

    except Exception as e:
        logger.error(f"上传失败：{str(e)}")
        return {
            "status":"error",
            "message":str(e)
        }
