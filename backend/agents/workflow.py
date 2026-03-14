from typing import TypedDict, Annotated, List, Optional
import operator
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader, TextLoader
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_core.messages import BaseMessage, AIMessage, ToolMessage, HumanMessage, SystemMessage
import os
import sys

# 将项目根目录加入系统路径
project_root = r"D:/XiaoGui-Assistant"

if project_root not in sys.path:
    sys.path.insert(0, project_root)
    print(f"✅ 已强制添加项目根目录到路径：{project_root}")

load_dotenv()
tool_list = []

try:
    # 导入普通函数工具
    from backend.tools.file_parsing_tool import parse_file
    from backend.tools.calc_tool import calculate
    from backend.tools.time_tool import get_current_time
    from backend.tools.weather_tool import get_weather
    from backend.tools.web_search_tool import web_search
    from backend.tools.export_chat_tool import save_messages_to_markdown

    # 导入图片识别工具
    from backend.tools.image_recognition_tool import analyze_image


    recognize_image_func = analyze_image

    # 组建工具列表
    tool_list = [
        parse_file,
        calculate,
        recognize_image_func,
        web_search,
        get_weather,
        get_current_time,
        save_messages_to_markdown
    ]
    print(f"✅ 成功加载 {len(tool_list)} 个工具")

except Exception as e:
    print(f"⚠️ 警告：工具导入失败，请检查路径。错误信息：{e}")
    import traceback
    #traceback.print_exc() 是 Python 中用于打印异常堆栈信息的函数。
    traceback.print_exc()

# 2. 初始化大模型
llm = ChatOpenAI(
    model=os.getenv("DEEPSEEK_MODEL_NAME", "deepseek-chat"),
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
    temperature=0.8,
    streaming=True
)

# 绑定工具
llm_with_tools = llm.bind_tools(tool_list)


# 3. RAG 引擎
class RAGAgent:
    def __init__(self):
        print("正在初始化 RAG 引擎...")
        self.embedding_model = None
        self.vectorstore = None
        self._init_embedding()

    def _init_embedding(self):
        try:
            local_model_path = r"D:/XiaoGui-Assistant/bge-small-zh-v1.5"
            if not os.path.exists(local_model_path):
                print(f"⚠️ 本地模型不存在，尝试使用在线模型：BAAI/bge-small-zh-v1.5")
                model_name = "BAAI/bge-small-zh-v1.5"
            else:
                model_name = local_model_path

            self.embedding_model = HuggingFaceEmbeddings(
                model_name=model_name,
                model_kwargs={'device': 'cpu'},
                # (向量归一化)：含义：把计算出来的向量（一串数字）的长度强行压缩到 1（单位向量）。
                # 这能大幅提高 FAISS 检索的速度和准确性，避免因向量长度差异导致的评分偏差。
                encode_kwargs={'normalize_embeddings': True}

            )
            print("✅ 嵌入模型加载成功")
        except Exception as e:
            print(f"❌ 嵌入模型加载失败：{e}")
            self.embedding_model = None

    def parse_file(self, file_path: str):
        """文档解析函数"""
        if not os.path.exists(file_path):
            print(f"❌ 文件不存在：{file_path}")
            return []

        ext = os.path.splitext(file_path)[1].lower()   #获取文件后缀名，并转化为小写
        loader = None

        try:
            # 1. 根据扩展名选择加载器
            if ext == ".txt":
                #尝试多种编码，中文 Windows 系统生成的 TXT 文件常用 GBK 编码
                encodings = ['utf-8', 'gbk', 'gb2312', 'latin-1']
                for enc in encodings:
                    try:
                        loader = TextLoader(file_path, encoding=enc)
                        print(f"✅ 使用 {enc} 编码加载 TXT 成功")
                        break

                        #“如果在读取或处理当前文件时发生了
                        # 编码错误（UnicodeDecodeError）或任何其他意外错误（Exception），
                        # 直接跳过这个文件，继续处理下一个文件，不要中断整个程序。”
                    except (UnicodeDecodeError, Exception):
                        continue

                if loader is None:
                    raise ValueError("无法识别的文本编码")

            elif ext == ".pdf":
                loader = PyPDFLoader(file_path)

            elif ext in [".docx", ".doc"]:
                loader = Docx2txtLoader(file_path)

            # 图片处理逻辑
            elif ext in [".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp"]:
                try:
                    print(f"检测到图片，正在调用豆包视觉模型进行视觉分析：{os.path.basename(file_path)}")

                    description = recognize_image_func(file_path)


                    if description and isinstance(description, str):

                        if description.startswith("错误") or description.startswith("配置错误"):
                            print(f"❌ 图片分析失败：{description}")
                            return []

                        print(f"✅ 图片分析成功，生成了 {len(description)} 字符的描述。")
                        # 将描述作为一个单独的文档片段返回
                        return [description]
                    else:
                        print("⚠️ 图片分析返回为空或格式不对。")
                        return []

                except Exception as img_err:
                    print(f" 图片处理过程异常：{str(img_err)}")
                    import traceback
                    traceback.print_exc()
                    return []

            else:
                print(f"❌ 不支持的文件格式：{ext}")
                return []

            # 2. 提取文字 (针对 TXT, PDF, DOCX)
            documents = []
            if ext == ".txt" and hasattr(loader, 'load'):
                documents = loader.load()
            elif ext in [".pdf", ".docx", ".doc"]:
                documents = loader.load()

            if not documents:
                return []

            # 3. 文本切分
            from langchain_text_splitters import RecursiveCharacterTextSplitter

            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=500,
                chunk_overlap=50,
                length_function=len,  #使用 Python 内置的 len() 函数来计算长度。
                separators=["\n\n", "\n", " ", ""]
                #先试着按双换行符（段落）切分,
                # 如果某段落太长，再试着按单换行符（行）切分。
                # 如果某一行还太长，再试着按空格（单词）切分。
                # 如果连单词都太长了（比如一串超长的乱码或 URL），那就只能强制按字符切断
            )

            chunks = text_splitter.split_documents(documents)

            # 4. 返回纯文本列表
            chunk_texts = [chunk.page_content.strip() for chunk in chunks if chunk.page_content.strip()]

            print(f" 解析成功：{os.path.basename(file_path)} -> {len(chunk_texts)} 个片段")
            return chunk_texts

        except Exception as e:
            print(f" 解析文件失败：{file_path} | 错误：{str(e)}")
            import traceback
            traceback.print_exc()
            return []

    def add_documents(self, texts: List[str]):
        if not texts or self.embedding_model is None:
            return False
        try:
            print(f" 正在计算 {len(texts)} 条文本的向量...")
            all_vectors = self.embedding_model.embed_documents(texts)   #.embed_documents(texts):这是批量处理的方法。
            # len(all_vectors[0])获取第一个向量的长度。含义：向量的维度是多少。

            print(f" 向量计算完成：{len(all_vectors)} x {len(all_vectors[0])}")
            #输出是：成功将A个文本片段转换成了B维的向量。

            #为每一段文本准备了一个空的字典 {} 作为“元数据”。
            # 虽然代码里目前是空字典，但 FAISS 强制要求传入这个参数。
            # 现在的空字典是为未来的混合检索或元数据过滤打下架构基础。
            metadatas = [{} for _ in texts]

            #zip(texts, all_vectors) 的作用就是把这两个列表一一对应地捆起来。
            # text_embeddings 参数，格式必须是 [(文本，向量), (文本，向量), ...]。
            text_embedding_pairs = list(zip(texts, all_vectors))

            if self.vectorstore is None:
                self.vectorstore = FAISS.from_embeddings(
                    text_embeddings=text_embedding_pairs,
                    embedding=self.embedding_model,
                    metadatas=metadatas
                )
                print("✅ 首次创建向量数据库成功！")
            else:
                self.vectorstore.add_embeddings(
                    text_embeddings=text_embedding_pairs,
                    metadatas=metadatas
                )
                print("✅ 追加数据到向量数据库成功！")
            return True
        except Exception as e:
            print(f"❌ 知识库存入失败：{e}")
            import traceback
            traceback.print_exc()
            return False

    def search(self, query: str) -> List[str]:
        """用户问一个问题，系统从知识库里找出最相关的 3 段话。"""
        if self.embedding_model is None or self.vectorstore is None:
            return []
        try:
            docs = self.vectorstore.similarity_search(query, k=3)
            return [doc.page_content for doc in docs]
        except Exception as e:
            print(f"❌ 检索失败：{e}")
            return []


rag_agent = RAGAgent()


# 4. 定义工作流状态
class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]
    context: str
    uploaded_file: Optional[str]


# 5. 定义节点

def file_upload_node(state: AgentState):
    """文件上传与入库节点"""
    file_path = state.get("uploaded_file")
    if not file_path or not os.path.exists(file_path):
        return {"messages": [], "context": ""}

    print(f"\n📂 正在处理文件：{file_path} ...")
    try:
        texts = rag_agent.parse_file(file_path)
        if not texts:
            # 区分是图片还是其他文件，给出更友好的提示
            ext = os.path.splitext(file_path)[1].lower()
            if ext in [".jpg", ".jpeg", ".png", ".bmp"]:
                msg = "⚠️ 图片解析未返回有效内容，可能是 API 调用失败或图片过于模糊。"
            else:
                msg = "❌ 文件解析失败，可能是格式不支持或文件为空。"
            return {"messages": [AIMessage(content=msg)]}

        success = rag_agent.add_documents(texts)
        if success:
            filename = os.path.basename(file_path)
            file_type = "图片" if os.path.splitext(filename)[1].lower() in [".jpg", ".jpeg", ".png", ".bmp"] else "文件"
            return {"messages": [AIMessage(content=f"✅ {file_type}《{filename}》已学习完毕！你可以问我关于它的内容了。")]}
        else:
            return {"messages": [AIMessage(content="❌ 知识库存储失败。")]}
    except Exception as e:
        return {"messages": [AIMessage(content=f"❌ 发生错误：{str(e)}")]}


def retriever_node(state: AgentState):
    """检索节点：根据用户问题检索知识库"""
    messages = state["messages"]
    if not messages:
        return {"context": ""}

    # 获取用户最后一条消息
    last_msg = messages[-1]
    if isinstance(last_msg, HumanMessage):
        query = last_msg.content
        context_docs = rag_agent.search(query)
        context_str = "\n\n".join(context_docs) if context_docs else ""
        if context_str:
            print(f" 检索到 {len(context_docs)} 条相关知识")
        return {"context": context_str}
    return {"context": ""}


def chat_think_node(state: AgentState):
    """思考节点：调用 LLM (带工具)"""
    messages = state["messages"]
    context = state.get("context", "")

    if context:
        system_prompt = f"""你是一个智能对话助手“小桂”。

【最高优先级指令】：
1. **必须使用参考资料**：下方的【参考资料】包含了最新的实时信息（如新闻、冲突、天气等）。你**必须**基于这些资料回答用户问题。
2. **严禁否认工具**：既然你已经看到了【参考资料】，说明工具调用**已经成功**。**绝对禁止**回答“搜索失败”、“无法获取最新信息”或“网络错误”等话术。
3. **处理冲突**：如果【参考资料】的内容与你训练数据中的旧知识冲突，**必须以【参考资料】为准**。
4. **图片内容**：参考资料中可能包含对图片的文字描述，请将其视为图片内容的真实反映。

【参考资料】（这是真实且最新的信息）：
{context}

请根据以上资料，直接、清晰地回答用户问题。
"""
    else:
        system_prompt = """你是一个智能助手小桂，请用友好的中文回答用户问题。
如果需要计算、查天气、搜网页或识别图片，请调用相应工具。
注意：如果调用了工具并获得了结果，必须在回答中体现这些结果，不要假装没看到。"""

    # 在消息列表前插入 System Message
    # 注意：LangGraph 中，SystemMessage 通常放在列表最前面
    full_messages = [SystemMessage(content=system_prompt)] + messages

    try:
        response = llm_with_tools.invoke(full_messages)
        # LangGraph 会自动通过 Annotated 把 response 追加到 messages
        return {"messages": [response]}
    except Exception as e:
        error_msg = f"大模型调用失败：{str(e)}"
        print(error_msg)
        # 这里返回错误消息，让工作流继续，而不是直接崩溃
        return {"messages": [AIMessage(content=error_msg)]}
def tools_node(state: AgentState):
    """工具执行节点"""
    messages = state["messages"]
    last_msg = messages[-1]
    results = []

    if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
        # 构建工具映射表 (名字 -> 函数)
        tool_map = {}
        for t in tool_list:
            name = getattr(t, 'name', getattr(t, '__name__', ''))
            if name:
                tool_map[name] = t

        for tool_call in last_msg.tool_calls:
            name = tool_call["name"]
            args = tool_call["args"]
            tool_call_id = tool_call["id"]

            selected_tool = tool_map.get(name)

            if selected_tool:
                try:
                    # 统一调用方式：如果是字典参数则解包，否则直接传
                    if isinstance(args, dict):
                        observation = selected_tool(**args)
                    else:
                        observation = selected_tool(args)

                    results.append(ToolMessage(
                        content=str(observation),
                        name=name,
                        tool_call_id=tool_call_id
                    ))
                    print(f"🛠️ 工具 [{name}] 执行成功")
                except Exception as e:
                    error_content = f"工具 '{name}' 执行出错：{str(e)}"
                    results.append(ToolMessage(
                        content=error_content,
                        name=name,
                        tool_call_id=tool_call_id
                    ))
                    print(f"❌ 工具 [{name}] 执行失败：{e}")
            else:
                error_content = f"错误：找不到名为 '{name}' 的工具"
                results.append(ToolMessage(
                    content=error_content,
                    name=name,
                    tool_call_id=tool_call_id
                ))
                print(f"❌ 未找到工具：{name}")

    return {"messages": results}


def should_continue(state: AgentState) -> str:
    """是否下一步判断"""
    messages = state["messages"]
    last_msg = messages[-1]

    if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
        return "tools"
    else:
        return "END"


async def build_workflow():
    workflow = StateGraph(AgentState)

    # 1. 注册所有业务节点
    workflow.add_node("uploader", file_upload_node)
    workflow.add_node("retriever", retriever_node)
    workflow.add_node("agent", chat_think_node)
    workflow.add_node("tools", tools_node)

    # 2.创建一个“空”入口节点，只负责传递状态
    def pass_through(state: AgentState):
        return {}  # 返回空字典，不改变任何状态

    workflow.add_node("entry", pass_through)

    # 3. 设置入口点为 "entry"
    workflow.set_entry_point("entry")

    # 4. 从 "entry" 节点出发，根据条件跳转到不同节点
    def route_decision(state: AgentState):
        if state.get("uploaded_file"):
            return "uploader"
        else:
            return "retriever"

    workflow.add_conditional_edges(
        source="entry",
        path=route_decision,
        path_map={
            "uploader": "uploader",
            "retriever": "retriever"
        }
    )


    workflow.add_edge("uploader", "retriever")
    workflow.add_edge("retriever", "agent")

    workflow.add_conditional_edges(
        source="agent",
        path=should_continue,
        path_map={"tools": "tools", "END": END}
    )

    workflow.add_edge("tools", "agent")

    print("✅ LangGraph 工作流编译完成！")
    return workflow