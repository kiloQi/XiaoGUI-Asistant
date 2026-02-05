from datetime import datetime
from http.client import responses

from fastapi import FastAPI
from pydantic import BaseModel

app=FastAPI()

class ChatRequest(BaseModel):
    message: str


@app.get("/chat")
async def chat(request: ChatRequest):
    if  "时间" in request.text:
        response= f"现在是{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    elif "计算" in request.text:
        result=eval(request.text.replace("计算"," "))#将计算字样移除，保留其余部分作为待计算的表达式
        response=f"结果是{result}"

    else:
        response="你好呀，我是小桂助手"

    return {"response":response}







