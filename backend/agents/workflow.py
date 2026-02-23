from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from typing import TypedDict,Annotated,List
import operator
from langgraph.graph import StateGraph,END


#定义状态
class AgentState(TypedDict):#typedstate是定义数据结构
    messages:Annotated[List[str],operator.add]    #消息自动追加



#定义节点
def chat_node(state: AgentState):
    """模拟聊天节点，这里需要调用llm"""
    user_msg=state["messages"][-1]   #取最后一条消息（用户刚说的）

    # 🔥 简单记忆逻辑：如果问名字，从历史里找
    if "我叫什么" in user_msg or "名字" in user_msg:
        for msg in reversed(state["messages"][:-1]):  # 倒序查找历史
            if "我是" in msg:
                name = msg.split("我是")[1].strip()
                return {"messages": [f"你叫 {name} 呀！"]}

    ai_response=f"小桂收到：{user_msg}"

    return {"messages":[ai_response]}

#创建工作流
async def build_workflow():
    workflow=StateGraph(AgentState)
    workflow.add_node("chat",chat_node)
    workflow.set_entry_point("chat")
    workflow.add_edge("chat",END)


    memory=AsyncSqliteSaver.from_conn_string("sqlite:///memory.db")
    workflow.add_edge("chat",memory)
    app=workflow.compile(checkpointer=memory)
    return app


if __name__ == "__main__":
    async def main():
        print("=" * 50)
        print("🧠 小桂助手 - 记忆功能测试")
        print("=" * 50)

        # 创建工作流
        app = build_workflow()

        # 配置：thread_id 区分不同用户
        config = {"configurable": {"thread_id": "user_001"}}

        # 🗣️ 第一轮对话
        print("\n【第1轮】用户：你好，我是小明")
        result1 = app.invoke(
            {"messages": ["你好，我是小明"]},
            config=config
        )
        print(f"【第1轮】小桂：{result1['messages'][-1]}")

        # 🗣️ 第二轮对话
        print("\n【第2轮】用户：今天天气怎么样？")
        result2 = app.invoke(
            {"messages": ["今天天气怎么样？"]},
            config=config
        )
        print(f"【第2轮】小桂：{result2['messages'][-1]}")

        # 🗣️ 第三轮对话 - 测试记忆
        print("\n【第3轮】用户：我叫什么名字？")
        result3 = app.invoke(
            {"messages": ["我叫什么名字？"]},
            config=config
        )
        print(f"【第3轮】小桂：{result3['messages'][-1]}")

        print("\n" + "=" * 50)
        print("✅ 记忆功能测试完成！")
        print("=" * 50)







