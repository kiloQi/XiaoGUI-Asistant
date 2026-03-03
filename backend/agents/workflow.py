from langgraph.checkpoint.sqlite import SqliteSaver

# TypedDict: 用来定义一个“记事本”的格式
# Annotated: “自动追加消息”
# Sequence: 表示这是一个列表
from typing import TypedDict, Annotated, List, Optional

import operator
from langgraph.graph import StateGraph,END
import os
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import PyPDFLoader,Docx2txtLoader,TextLoader

# BaseMessage: 所有消息的基类,ToolMessage: 工具运行完后返回的结果
from langchain_core.messages import BaseMessage,AIMessage,ToolMessage,HumanMessage

#导入工具
try:
    from backend.tools.file_parsing_tool import parse_file
    from backend.tools.calc_tool import calculate
    from backend.tools.image_recognition import recognize_image
    from backend.tools.time_tool import get_current_time
    from backend.tools.weather_tool import get_weather
    from backend.tools.web_search_tool import web_search
    tool_list = [parse_file,
                 calculate,
                 recognize_image,
                 web_search,
                 get_weather,
                 get_current_time]




except Exception as e:
    print(f"警告：工具导入失败，请检查路径。错误信息：{e}")
    tools_list = []  # 如果导入失败，先给个空列表，防止程序崩溃

load_dotenv()

#初始化大模型
llm=ChatOpenAI(
    model=os.getenv("DEEPSEEK_MODEL_NAME","deepseek-chat"),
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url=os.getenv("DEEPSEEK_BASE_URL","https://api.deepseek.com"),
    temperature=0.8,
    streaming=True      #开启流式输出
)
#绑定工具
llm_with_tools=llm.bind_tools(tools_list)


#定义智能体状态
class AgentState(TypedDict):
    messages:Annotated[List[BaseMessage],operator.add]   #Annotated[..., add_messages] ：当有新消息进来时，自动把它添加到列表末尾，不覆盖旧消息


#定义思考节点
def chat_think_node(state: AgentState):
    """
    智能体的大脑
    输入：当前的状态（包含所有历史对话）。
    输出：AI 思考后的结果。

    """
    messages=state["messages"]  #拿出全部对话历史
    response=llm_with_tools.invoke(messages)

    # LangGraph 会自动把这条新消息追加到 state["messages"] 里
    return {"messages":response}

#定义工具执行节点
def tools_node(state: AgentState):
    """
    检查上一步 AI 是不是想调用工具。如果是，它就真的去跑代码，然后把结果记下来。
    """
    messages=state["messages"]
    last_msg=messages[-1]
    results=[]  # 用来存工具运行的结果
    #检查 AI 是否发起了工具调用
    if hasattr(last_msg,"tool_calls") and last_msg.tool_calls:

# 遍历每一个工具调用请求（有时候 AI 会一次性调用多个工具）
        for tool_call in last_msg.tool_calls:
            tool_name=tool_call["name"]
            tool_args=tool_call["args"]
            tool_call_id=tool_call["id"]

            # 在工具列表里找对应的函数,名字 -> 函数对象
            tool_map={tool_name:tool for tool in tools_list}
            selected_tool=tool_map[tool_name]

            if selected_tool:
                try:
                    observation=selected_tool.invoke(tool_args)
                    results.append(ToolMessage(
                        content=str(observation),
                        name=tool_name,
                        tool_id=tool_call_id
                    ))


                except Exception as e:
                    error_msg = f"工具 '{tool_name}' 执行出错：{str(e)}"
                    results.append(ToolMessage(
                        content=error_msg,
                        name=tool_name,
                        tool_call_id=tool_call_id
                    ))

            else:
                # AI 想调用的工具找不到
                results.append(ToolMessage(
                    content=f"错误：找不到名为 '{tool_name}' 的工具",
                    name=tool_name,
                    tool_call_id=tool_call_id
                ))
    # 返回所有工具的运行结果,把这些结果追加到 state["messages"] 里
    return {"messsages":results}

#定义执行逻辑
def should_continue(state: AgentState):
    """
    - 如果 AI 说“我要调用工具”，就指挥去“tools_node”干活。
    - 如果 AI 说“我没别的事了，直接回答吧”，就指挥“结束 (END)”。
    """
    messages=state["messages"]
    last_msg=messages[-1]
    # 判断最后一条消息里有没有工具调用请求
    if hasattr(last_msg,"tool_calls") and last_msg.tool_calls:
        # 有请求 -> 去工具节点
        return "tools"
        # 没请求 -> 任务完成，结束
    else:
        return "END"







#定义RAGAgent
class RAGAgent:
    def __init__(self):
        print("正在初始化 RAG 引擎")
        os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
        local_model_path = r"D:/XiaoGui-Assistant/bge-small-zh-v1.5"
        self.embedding_model = None
        self.vectorstore = None
        try:
            # self.embedding_model = FlagEmbeddingAdapter(local_model_path)

            print("嵌入模型加载成功")

        except Exception as e:
            print(f"⚠️ 模型加载失败 : {e}")
            print("提示：请检查网络连接，或尝试手动下载模型到本地。")
            self.embedding_model = None
            self.vectorstore: Optional[FAISS] = None

    def parse_file(self, file_path: str) -> List[str]:
            if not os.path.exists(file_path):
                return []

            ext = os.path.splitext(file_path)[1].lower()
            loader = None


            if ext == '.pdf':
                loader = PyPDFLoader(file_path)
            elif ext == '.txt':
                loader = TextLoader(file_path, encoding='utf-8')
            elif ext in ['.docx', '.doc']:
                loader = Docx2txtLoader(file_path)
            else:
                print(f"❌ 不支持的文件类型: {ext}")
                return []

            try:
                documents = loader.load()
                # 把每一页的内容提取出来，变成一个字符串列表
                texts = [doc.page_content for doc in documents if doc.page_content.strip()]
                print(f"📄 文件解析完成，共提取 {len(texts)} 段文字。")
                return texts
            except Exception as e:
                print(f"❌ 文件解析出错: {e}")
                return []

    def add_documents(self, texts: List[str]):
        if not texts or self.embedding_model is None:
            return False

        try:
            print(f"⚡ 正在计算 {len(texts)} 条文本的向量...")
            all_vectors = self.embedding_model.embed_documents(texts)
            print(f"✅ 向量计算完成：{len(all_vectors)} x {len(all_vectors[0])}")

            metadatas = [{} for _ in texts]

            if self.vectorstore is None:
                text_embedding_pairs = list(zip(texts, all_vectors))
                self.vectorstore = FAISS.from_embeddings(
                    text_embeddings=text_embedding_pairs,
                    embedding=self.embedding_model,
                    metadatas=metadatas
                )
                print("首次创建向量数据库成功！")
            else:
                text_embedding_pairs = list(zip(texts, all_vectors))
                self.vectorstore.add_embeddings(
                    text_embeddings=text_embedding_pairs,
                    metadatas=metadatas
                )
                print("➕ 追加数据到向量数据库成功！")

            print("✅ 已成功存进知识库")
            return True

        except Exception as e:
            print(f"❌ 知识库存入失败：{e}")
            import traceback
            traceback.print_exc()
            return False

    def search(self, query: str):
        if self.embedding_model is None or self.vectorstore is None:
            return []
        try:
            docs = self.vectorstore.similarity_search(query, k=3)
            return [doc.page_content for doc in docs]
        except Exception as e:
            print(f"❌ 检索失败：{e}")
            return []

rag_agent=RAGAgent()


#定义工作流状态
class AgentState(TypedDict):                      #typedstate是定义数据结构
    messages:Annotated[List[str],operator.add]    #聊天消息记录：自动把新消息加到后面
    context:str                                   #检索到的参考资料
    uploaded_file:Optional[str]                   #用户上传的文件路径



#定义文件上传节点
def file_upload_node(state: AgentState):
    file_path=state["uploaded_file"]
    #如果没有文件路径，或者文件不存在，直接跳过
    if not file_path or not os.path.exists(file_path):
        return {"messages":[],"context":""}


    print(f"\n📂正在处理文件: {file_path} ...")
    try:
        #解析文字
        texts=rag_agent.parse_file(file_path)

        if not texts:
            return {"messages":["❌ 文件解析失败，可能是格式不支持或文件为空。"],"context":""}

        #存入知识库
        success=rag_agent.add_documents(texts)

        if success:
            filename=os.path.basename(file_path)
            return {"messages": [f"✅ 文件《{filename}》已学习完毕！你可以问我关于它的内容了。"]}
        else:
            return {"messages": ["❌ 知识库存储失败。"]}

    except Exception as e:
        return {
            "messages":[f"❌ 发生错误：{str(e)}"],
            "context":"",
            "upload_status":"error"
        }


#定义聊天节点
def chat_node(state: AgentState):
    """调用DeepSeek模型进行回复"""
    user_msg=state["messages"][-1]   #取最后一条消息（用户刚说的）
    context=state.get("context","")

    if context:
        system_prompt=f"""你是一个智能对话助手“小桂”。
请根据以下【参考资料】回答用户问题。如果参考资料没有答案，请用你自己的知识回答，但要说明资料没提到

【参考资料】：{context}
"""
    else:
        system_prompt="""你是一个智能助手小桂，请用友好的中文回答用户问题"""

    try:
        messages=[
            ("system",system_prompt),
            ("human",user_msg)
        ]

        response=llm.invoke(messages)
        ai_content=response.content
        print(f" 小桂回复: {ai_content[:50]}...")
        return {"messages":[ai_content]}
    except Exception as e:
        error_msg=f"大模型调用失败：str{e}"
        print(error_msg)
        return {"messages":[error_msg]}



async def build_workflow():
    # 1. 创建图表，定义状态结构
    workflow = StateGraph(AgentState)

    # 2. 添加三个节点
    workflow.add_node("uploader", file_upload_node)
    workflow.add_node("agent",chat_think_node )
    workflow.add_node("tools", tools_node)

    # 3. 设定工作流程顺序
    # 入口：看看有没有文件要处理
    workflow.set_entry_point("uploader")
    # 处理完文件后， 去检索资料
    workflow.add_edge("uploader", "retriever")
    # 检索完资料后，生成回答
    workflow.add_edge("retriever", "chat")
    # 回答完后，结束流程
    workflow.add_edge("chat", END)

    # 4. 配置“记忆”
    # 使用 SQLite 保存聊天历史
    memory = SqliteSaver.from_conn_string("sqlite:///memory.db")
    # memory=MemorySaver()
    # 5. 编译并返回应用
    app = workflow.compile(checkpointer=memory)
    return app


