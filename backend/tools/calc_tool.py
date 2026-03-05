from backend.main import mcp
@mcp.tool()
def calculate(expression:str):
    try:
        result=eval(expression)
        return  str(result)
    except :
        return "表达式错误，请重新输入"



