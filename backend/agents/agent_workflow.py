#经过ai润色的版本，去掉了大量重复代码
import os
import sys
import time
from typing import TypedDict, Dict, Optional, Any, List
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.config.settings import (
    DEEPSEEK_API_KEY,
    DEEPSEEK_MODEL_NAME,
    DEEPSEEK_BASE_URL,
    AMAP_WEATHER_KEY,
    TAVILY_API_KEY
)
from langchain_openai import ChatOpenAI
from langchain_core.prompts import (
    ChatPromptTemplate,
    MessagesPlaceholder,
    SystemMessagePromptTemplate,
    HumanMessagePromptTemplate
)
from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.tools import Tool, tool
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableSequence
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.graph import StateGraph, START, END
from backend.tools.calc_tool import ExpressionCalculator
from backend.tools.file_parsing_tool import FileParser
from backend.tools.image_recognition import DeepSeekImageRecognizer
from backend.tools.time_tool import CurrentTimeTool
from backend.tools.weather_tool import WeatherQueryTool
from backend.tools.web_search_tool import TavilyWebSearcher

#这些是必要的全局变量，我让ai帮我去掉太多重复代码的
class Config:
    AGENT_NAME = "小桂助手"
    MAX_MEMORY_LEN = 10
    STREAM_DELAY = 0.03
    AGENT_CONFIG = {
        "chunk_size": 500,
        "chunk_overlap": 50,
        "max_search_results": 5
    }

calc_tool = ExpressionCalculator()
file_tool = FileParser(
    chunk_size=Config.AGENT_CONFIG["chunk_size"],
    chunk_overlap=Config.AGENT_CONFIG["chunk_overlap"]
)
image_tool = DeepSeekImageRecognizer()
time_tool = CurrentTimeTool()
weather_tool = WeatherQueryTool()
search_tool = TavilyWebSearcher()

#这里进行了格式化处理
@tool
def calculator(expression: str) -> str:
    """
    数学计算工具
    """
    return calc_tool.calculate(expression)

@tool
def current_time() -> str:
    """
    获取当前时间工具
    """
    return time_tool.get_current_time()

@tool
def weather_query(city_name: str) -> str:
    """
    天气查询工具
    """
    result = weather_tool.get_weather(city_name)
    return result["answer"] if result.get("success") else result["error"]

@tool
def web_search(query: str) -> str:
    """
    网页搜索工具
    """
    result = search_tool.web_search(query)
    return result["answer"] if result.get("success") else result["error"]

@tool
def image_recognize(image_path: str, question: str = "请描述这张图片的内容") -> str:
    """
    图片识别工具
    """
    result = image_tool.recognize_image(image_path, question)
    return result["answer"] if result.get("success") else result["error"]

@tool
def file_parse(file_path: str) -> str:
    """
    文件解析工具
    """
    result = file_tool.parse_file(file_path)
    if result["status"] == "success":
        return f"文件解析成功：文件名【{result['filename']}】，共{result['chunk_count']}个文本块，全文预览：{result['full_text'][:500]}..."
    else:
        return f"文件解析失败：{result['messages']}"

ALL_TOOLS = [calculator, current_time, weather_query, web_search, image_recognize, file_parse]

system_prompt = SystemMessagePromptTemplate.from_template("""
你是{agent_name}，一个智能助手，严格按照以下规则工作：
1. 优先使用提供的工具解决用户问题，工具调用后必须基于工具结果回答
2. 工具列表：
   - calculator：数学计算，输入表达式即可
   - current_time：获取当前时间，无需参数
   - weather_query：查询城市天气，输入城市名
   - web_search：网页搜索，输入关键词
   - image_recognize：图片识别，输入图片路径
   - file_parse：文件解析，输入文件路径
3. 回答要简洁易懂，工具调用结果要清晰展示
4. 不需要工具时，直接友好回答用户问题
""")

human_prompt = HumanMessagePromptTemplate.from_template("{user_input}")

prompt_template = ChatPromptTemplate.from_messages([
    system_prompt,
    MessagesPlaceholder(variable_name="chat_history"),
    human_prompt,
    MessagesPlaceholder(variable_name="agent_scratchpad")
])

class AgentState(TypedDict):
    """扩展状态"""
    user_id: str
    user_input: str
    chat_history: List[Any]
    tool_calls: List[Dict]
    tool_results: Dict[str, str]
    agent_response: str
    need_tool: bool
    current_node: str

def init_node(state: AgentState) -> AgentState:
    """初始化节点：初始化记忆、重置状态"""
    state["chat_history"] = []
    state["tool_calls"] = []
    state["tool_results"] = {}
    state["agent_response"] = ""
    state["need_tool"] = False
    state["current_node"] = "init_node"

    state["chat_history"].append(HumanMessage(content=state["user_input"]))

    print(f"初始化完成（用户ID：{state['user_id']}）")
    return state

def agent_node(state: AgentState) -> AgentState:
    """Agent节点：生成回答/手动解析工具调用指令"""
    state["current_node"] = "agent_node"

    llm = ChatOpenAI(
        model=DEEPSEEK_MODEL_NAME,
        openai_api_key=DEEPSEEK_API_KEY,
        openai_api_base=DEEPSEEK_BASE_URL,
        temperature=0.7,
        streaming=True,
        tags=["no-tracing"],
        metadata={"langchain_tracing": "disabled"}
    )
    llm_with_tools = llm.bind_tools(ALL_TOOLS)

    runnable = (
        RunnablePassthrough.assign(
            #这里老是报错，我就叫ai帮我改成了这样
            agent_name=lambda x: Config.AGENT_NAME,
            chat_history=lambda x: x["chat_history"],
            user_input=lambda x: x["user_input"],
            agent_scratchpad=lambda x: []
        )
        | prompt_template
        | llm_with_tools
    )

    try:
        response = runnable.invoke(state)
        state["tool_calls"] = []
        if hasattr(response, 'tool_calls') and response.tool_calls:
            for tool_call in response.tool_calls:
                state["tool_calls"].append({
                    "name": tool_call["name"],
                    "args": tool_call["args"],
                    "id": tool_call.get("id", "")
                })

        state["need_tool"] = len(state["tool_calls"]) > 0

        if not state["need_tool"]:
            state["agent_response"] = response.content if hasattr(response, 'content') else ""
            state["chat_history"].append(AIMessage(content=state["agent_response"]))

        print(f"🔍 Agent分析完成 - 需要工具：{state['need_tool']}")

    except Exception as e:
        state["agent_response"] = f"Agent节点出错：{str(e)}"
        state["need_tool"] = False

    return state

def tool_node(state: AgentState) -> AgentState:
    """工具节点：执行工具调用"""
    state["current_node"] = "tool_node"
    state["tool_results"] = {}

    if not state["tool_calls"]:
        state["need_tool"] = False
        print("无工具调用指令，跳过工具节点")
        return state

    # 执行所有工具调用
    for tool_call in state["tool_calls"]:
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]

        print(f"\n正在调用【{tool_name}】工具...")

        tool_map = {
            "calculator": calculator,
            "current_time": current_time,
            "weather_query": weather_query,
            "web_search": web_search,
            "image_recognize": image_recognize,
            "file_parse": file_parse
        }

        try:
            result = tool_map[tool_name].invoke(tool_args)
            state["tool_results"][tool_name] = str(result)

            tip = f"🔧 {tool_name} 工具调用成功！\n"
            for c in tip:
                print(c, end="", flush=True)
                time.sleep(Config.STREAM_DELAY)

        except Exception as e:
            state["tool_results"][tool_name] = f"工具执行失败：{str(e)}"

    for tool_name, result in state["tool_results"].items():
        state["chat_history"].append(ToolMessage(
            content=result,
            tool_call_id=tool_name
        ))

    return state

def response_node(state: AgentState) -> AgentState:
    """回答生成节点：生成最终回答可以流式输出"""
    state["current_node"] = "response_node"

    if state["tool_results"]:
        tool_result_prompt = "\n".join([
            f"【{tool_name}】：{result}"
            for tool_name, result in state["tool_results"].items()
        ])

        final_prompt = ChatPromptTemplate.from_messages([
            ("system", "基于以下工具调用结果，友好回答用户问题：\n{tool_results}"),
            ("user", "{user_input}")
        ])

        llm = ChatOpenAI(
            model=DEEPSEEK_MODEL_NAME,
            openai_api_key=DEEPSEEK_API_KEY,
            openai_api_base=DEEPSEEK_BASE_URL,
            temperature=0.7,
            streaming=True
        )

        final_runnable = final_prompt | llm | StrOutputParser()

        print(f"\n{Config.AGENT_NAME}：", end="", flush=True)
        final_response = ""

        for chunk in final_runnable.stream({
            "tool_results": tool_result_prompt,
            "user_input": state["user_input"]
        }):
            final_response += chunk
            for c in chunk:
                print(c, end="", flush=True)
                time.sleep(Config.STREAM_DELAY)

        state["agent_response"] = final_response

    else:
        print(f"\n{Config.AGENT_NAME}：", end="", flush=True)
        for c in state["agent_response"]:
            print(c, end="", flush=True)
            time.sleep(Config.STREAM_DELAY)

    state["chat_history"].append(AIMessage(content=state["agent_response"]))
    print("\n")

    return state

def route_router(state: AgentState) -> str:
    """路由函数：决定下一步执行哪个节点"""
    if state["need_tool"]:
        return "tool_node"
    else:
        return "response_node"

def build_workflow():
    """构建完整工作流"""
    workflow = StateGraph(AgentState)

    workflow.add_node("init_node", init_node)
    workflow.add_node("agent_node", agent_node)
    workflow.add_node("tool_node", tool_node)
    workflow.add_node("response_node", response_node)

    workflow.add_edge(START, "init_node")
    workflow.add_edge("init_node", "agent_node")
    workflow.add_conditional_edges(
        source="agent_node",
        path=route_router,
        path_map={
            "tool_node": "tool_node",
            "response_node": "response_node"
        }
    )
    workflow.add_edge("tool_node", "response_node")
    workflow.add_edge("response_node", END)

    return workflow.compile()



#这个是我让ai根据我优化后的代码生成的测试代码
# # ========== 内置测试代码（直接添加在源码末尾） ==========
# def run_builtin_tests():
#     """内置测试函数：自动执行测试用例 + 手动交互"""
#     # 构建工作流
#     workflow = build_workflow()
#
#     # 打印测试标题
#     print("=" * 80)
#     print(f"🚀 {Config.AGENT_NAME} 内置测试模式启动")
#     print("📋 自动测试用例将先执行，完成后进入手动交互模式")
#     print("=" * 80)
#
#     # ========== 第一步：自动执行测试用例 ==========
#     AUTO_TEST_CASES = [
#         ("基础对话（无需工具）", "你好，你叫什么名字？"),
#         ("计算器工具", "计算100 + 200 * 3 - 400 / 2"),
#         ("时间工具", "现在几点了？"),
#         ("天气工具", "查询北京的天气")
#     ]
#
#     # 预设用户ID
#     USER_ID = "test_user_20260303"
#
#     # 执行自动测试
#     for idx, (case_name, user_input) in enumerate(AUTO_TEST_CASES, 1):
#         print(f"\n{'=' * 60}")
#         print(f"🧪 自动测试用例 {idx}/{len(AUTO_TEST_CASES)}：{case_name}")
#         print(f"💬 用户输入：{user_input}")
#         print(f"{'=' * 60}")
#
#         # 调用工作流
#         workflow.invoke({
#             "user_id": USER_ID,
#             "user_input": user_input,
#             "chat_history": [],
#             "tool_calls": [],
#             "tool_results": {},
#             "agent_response": "",
#             "need_tool": False,
#             "current_node": ""
#         })
#         time.sleep(1)  # 测试间隔
#
#     # ========== 第二步：进入手动交互模式 ==========
#     print("\n" + "=" * 80)
#     print("🎉 自动测试完成，进入手动交互模式")
#     print("💡 输入测试指令（如：搜索2026世界杯、解析D:/test.pdf），输入「退出」结束")
#     print("=" * 80)
#
#     while True:
#         user_input = input("\n你：")
#         if user_input.lower() in ["退出", "q", "end", "exit"]:
#             print(f"{Config.AGENT_NAME}：再见啦～😘")
#             break
#
#         # 调用工作流处理手动输入
#         workflow.invoke({
#             "user_id": USER_ID,
#             "user_input": user_input,
#             "chat_history": [],
#             "tool_calls": [],
#             "tool_results": {},
#             "agent_response": "",
#             "need_tool": False,
#             "current_node": ""
#         })
#
#
# # ========== 启动测试 ==========
# if __name__ == "__main__":
#     # 运行内置测试
#     run_builtin_tests()






