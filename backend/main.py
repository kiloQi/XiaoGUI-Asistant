import logging
import os
from fastapi import FastAPI
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



