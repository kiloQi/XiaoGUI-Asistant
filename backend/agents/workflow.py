import json
from typing import TypedDict, Annotated, List, Optional
import operator
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
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


# 2. 初始化大模型
llm = ChatOpenAI(
    model=os.getenv("DEEPSEEK_MODEL_NAME", "deepseek-chat"),
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
    temperature=0.8,
    streaming=True
)


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
                    from backend.tools.image_recognition_tool import analyze_image as recognize_image_func
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
    #List[BaseMessage]：这是一个列表，
    # 里面存着所有的对话消息（用户说的、AI 说的、系统提示词）。
    messages: Annotated[List[BaseMessage], operator.add]
    context: str

    #Optional[str]：表示这个文件路径可能有，也可能没有（可以是 None）。
    #它起到了一个开关的作用，告诉工作流：“这一轮用户带了文件，需要特殊处理”。
    uploaded_file: Optional[str]

    #用于记录循环次数，防止死循环
    iteration_count: int


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


def sanitize_tool_outputs(state: AgentState):
    messages = state["messages"]
    cleaned_messages = []

    for msg in messages:
        if hasattr(msg, 'type') and msg.type == 'tool':
            content = msg.content
            tool_name = getattr(msg, 'name', 'Unknown Tool')
            print(f"成功执行工具: {tool_name}")


            final_content = ""
            if isinstance(content, str):
                try:
                    # 尝试解析是否为 MCP 格式的列表
                    data = json.loads(content)
                    if isinstance(data, list) and len(data) > 0:
                        # 提取第一个 text 块的内容
                        if 'text' in data[0]:
                            final_content = data[0]['text']
                        else:
                            final_content = content  # 原样保留
                    else:
                        final_content = content
                except json.JSONDecodeError:
                    final_content = content
            else:
                # 非字符串强制转
                final_content = json.dumps(content, ensure_ascii=False) if isinstance(content, (list, dict)) else str(
                    content)
            preview = final_content[:200] + "..." if len(final_content) > 200 else final_content
            print(f"  [返回结果预览]:\n{preview}")

            # 重建消息
            cleaned_messages.append(
                ToolMessage(
                    content=final_content,  # 使用清洗后的纯文本
                    name=getattr(msg, 'name', None),
                    tool_call_id=getattr(msg, 'tool_call_id', None),
                    status=getattr(msg, 'status', 'success')
                )
            )
        else:
            cleaned_messages.append(msg)

    return {"messages": cleaned_messages}


def retriever_node(state: AgentState):
    """检索节点：根据用户问题检索知识库"""
    messages = state["messages"]
    if not messages:
        return {"context": ""}

    # 获取用户最后一条消息
    last_msg = messages[-1]
    if isinstance(last_msg, HumanMessage):  #校验最后一条消息是否为 HumanMessage，避免了在 AI 回复或系统内部流转时触发无效的检索操作
        query = last_msg.content
        context_docs = rag_agent.search(query)
        context_str = "\n\n".join(context_docs) if context_docs else ""
        if context_str:
            print(f" 检索到 {len(context_docs)} 条相关知识")
        return {"context": context_str}
    return {"context": ""}


async def build_workflow(tools=None):
    current_llm = llm
    tool_node = None

    if tools:
        print(f"✅ [MCP] 成功注入 {len(tools)} 个工具！")
        current_llm = llm.bind_tools(tools)
        tool_node = ToolNode(tools)
    else:
        print("⚠️ 警告：未传入工具。")



    def chat_think_node(state: AgentState):
        messages = state["messages"]
        context = state.get("context", "")

        # 1. 构建 System Prompt
        if context:
            system_prompt = f"""你是一个智能对话助手“小桂”。
            【最高优先级指令】：
            .1. **单次搜索原则**：针对同一个用户问题，你**最多只能调用一次** `web_search` 工具。
.            2. **禁止连环搜**：一旦你收到了 `tool_result` (工具返回结果)，无论你觉得信息是否完美，**必须立即停止调用工具**，并基于现有结果组织语言回答用户。
.            3.**禁止解释过程**：如果你决定调用工具，**直接输出工具调用 JSON**，严禁说“让我查一下”、“我正在搜索”等废话。
.            4.**资料优先**：下方的【参考资料】是最新真理。如果资料里没有详细细节，**直接告诉用户“目前公开资料仅显示...”**，绝不允许为了补充细节而发起第二次搜索！
             5. **静默执行**：如果你决定调用工具，**请直接生成工具调用请求**，严禁输出任何解释性文字（如“让我查一下”）。
             6. **必须使用参考资料**：下方的【参考资料】包含了最新的实时信息。你**必须**基于这些资料回答。
             7. **处理冲突**：如果【参考资料】的内容与你训练数据中的旧知识冲突，**必须以【参考资料】为准**。
             8. **【铁律】一旦你调用了工具并获得了结果（即消息历史中包含 ToolMessage），你必须立即根据结果组织语言回答用户，严禁再次调用任何工具！**
             9. **【禁止套娃】**：如果你已经针对同一个问题调用过 `web_search` 且获得了结果，**绝对不允许**再次调用 `web_search`。哪怕你觉得信息不够，也必须基于现有结果进行推理和回答，或者承认信息有限。

            【参考资料】（这是真实且最新的信息）：
            {context}

            请根据以上资料，直接、清晰地回答用户问题。如果需要工具，请直接调用，不要废话。
            """
        else:
            system_prompt = """你是一个智能助手小桂，请用友好的中文回答用户问题。
        【铁律】如果你调用了工具（如计算器、搜索、天气等）并获得了结果，**必须立即停止调用工具**，直接使用结果回答用户！严禁对同一个问题进行重复的工具调用！
        如果需要计算、查天气、搜网页或识别图片，请调用相应工具。
        注意：如果调用了工具并获得了结果，必须在回答中体现这些结果。"""

        clean_payload = []

        # 添加 System Message
        clean_payload.append({"role": "system", "content": system_prompt})

        for i, msg in enumerate(messages):
            role = "assistant"
            if isinstance(msg, HumanMessage):
                role = "user"
            elif isinstance(msg, ToolMessage):
                role = "tool"
            elif isinstance(msg, AIMessage):
                role = "assistant"
            else:

                role = "user"

            raw_content = msg.content if hasattr(msg, 'content') else ""

            # 强制确保 content 是字符串
            if not isinstance(raw_content, str):
                if isinstance(raw_content, (list, dict, tuple)):
                    final_content = json.dumps(raw_content, ensure_ascii=False)
                else:
                    final_content = str(raw_content)
            else:
                final_content = raw_content

            # 构建纯净字典
            msg_dict = {"role": role, "content": final_content}

            # 特殊处理：如果是 ToolMessage，必须包含 tool_call_id
            if role == "tool":
                tool_call_id = getattr(msg, 'tool_call_id', None)
                if not tool_call_id:

                    tool_call_id = f"fake_call_{i}"
                msg_dict["tool_call_id"] = tool_call_id

                # 注意：DeepSeek/Qwen 等通常不需要 tool_message 的 name 字段，但加上也无妨
                if hasattr(msg, 'name') and msg.name:
                    msg_dict["name"] = msg.name

            # 特殊处理：如果是 AI Message 且有 tool_calls，需要保留
            if role == "assistant" and isinstance(msg, AIMessage) and hasattr(msg, 'tool_calls') and msg.tool_calls:
                # 保留 tool_calls 结构，但也要确保里面的参数是干净的
                # 通常 tool_calls 本身就是 dict 列表，可以直接用
                msg_dict["tool_calls"] = msg.tool_calls

            clean_payload.append(msg_dict)


        # 调用 LLM
        try:
            response = current_llm.invoke(clean_payload)
            return {"messages": [response]}
        except Exception as e:
            error_msg = f"大模型调用失败：{str(e)}"
            print(error_msg)

            return {"messages": [AIMessage(content=error_msg)]}

    def should_continue(state: AgentState):
        messages = state["messages"]

        # 1. 基础数量限制
        if len(messages) > 30:
            print("检测到可能的死循环，强制结束对话。")
            return "END"

        last_message = messages[-1]

        # 2. 如果没有工具调用，直接结束
        if not (isinstance(last_message, AIMessage) and last_message.tool_calls):
            return "END"

        # 3.防重复调用检测 (防死循环核心)
        # 检查过去 5 条消息中，是否已经出现过同样的工具调用
        recent_messages = messages[-6:-1]
        current_tool_name = last_message.tool_calls[0]['name']

        tool_call_count = 0
        for msg in recent_messages:
            if isinstance(msg, AIMessage) and msg.tool_calls:
                for call in msg.tool_calls:
                    if call['name'] == current_tool_name:
                        tool_call_count += 1

        # 如果最近几轮里，同一个工具已经被调用了 2 次及以上，强制停止！
        if tool_call_count >= 2:
            print(f"⚠️ 检测到重复调用工具 [{current_tool_name}] 已达 {tool_call_count + 1} 次，强制终止以防止死循环！")
            return "END"

        return "tools"

    # 3. 构建图
    workflow = StateGraph(AgentState)

    # 注册节点
    workflow.add_node("uploader", file_upload_node)
    workflow.add_node("retriever", retriever_node)
    workflow.add_node("agent", chat_think_node)

    if tool_node:
        workflow.add_node("tools", tool_node)
        workflow.add_node("sanitize_tools", sanitize_tool_outputs)

    # 入口逻辑
    def entry_pass(state: AgentState):
        return {}

    workflow.add_node("entry", entry_pass)
    workflow.set_entry_point("entry")

    def route_decision(state: AgentState):
        if state.get("uploaded_file"):
            return "uploader"
        else:
            return "retriever"

    #条件分支 (conditional_edges)
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
    if tool_node:
        workflow.add_edge("tools", "sanitize_tools")
        workflow.add_edge("sanitize_tools", "agent")
    else:
        # 如果没有工具，直接结束
        workflow.add_edge("agent", END)

    print("✅ LangGraph 工作流编译完成！")
    return workflow
