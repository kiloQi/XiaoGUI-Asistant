import logging
import os
from fastapi import FastAPI

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



