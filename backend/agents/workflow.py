from langchain_core.tools import tool
from langgraph.graph import StateGraph,START,END


@tool

def time_tool():
    """获取当前时间"""
    from backend.tools.time_tool import get_current_time
    return get_current_time()

@tool
def calc_tool():
    """计算数学表达式"""
    from backend.tools.calc_tool import calculate
    return calculate("计算2+3")#需要传参

#定义状态
class AgentState:
    tools_used:list = []
    messages:list = []


#创建langgraph图
graph=StateGraph(AgentState)
def call_llm(state: AgentState):
    last_msg=state.messages[-1]

    #return部分是为了把后面消息列表追加到历史对话中
    if "时间" in last_msg or "几点" in last_msg or"time" in last_msg:
        return {"messages":state.messages+ [time_tool()]}
    elif "计算" in last_msg or"算" in last_msg:
        return {"messages":state.messages+ [calc_tool()]}
    else:
        return {"messages":state.messages+ ["你好我是小桂助手，可以帮你查时间和算数学题哦！"]}

graph.add_node("llm",call_llm)
graph.add_edge(START,"llm")
graph.add_edge("llm",END)

app=graph.compile()
