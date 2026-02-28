from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.checkpoint.memory import MemorySaver
from typing import TypedDict, Annotated, List, Optional
import operator
from langgraph.graph import StateGraph,END
import os
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import PyPDFLoader,Docx2txtLoader,TextLoader
from langchain_core.embeddings import Embeddings

load_dotenv()
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

#初始化大模型
llm=ChatOpenAI(
    model=os.getenv("DEEPSEEK_MODEL_NAME","deepseek-chat"),
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url=os.getenv("DEEPSEEK_BASE_URL","https://api.deepseek.com"),
    temperature=0.8,
    streaming=True      #开启流式输出
)


# 适配器类
class FlagEmbeddingAdapter(Embeddings):

    def __init__(self, model_path: str):
        from FlagEmbedding import FlagModel
        import numpy as np

        print(f"适配器正在加载模型：{model_path} ...")

        self.flag_model = FlagModel(
            model_name_or_path=model_path,
            query_instruction_for_retrieval="为这个句子生成表示以用于检索：",
            use_fp16=False
        )
        self.np = np
        print(f"✅ 模型加载成功！类型：{type(self.flag_model)}")

    def _normalize(self, embeddings):
        if isinstance(embeddings, list):
            embeddings = self.np.array(embeddings)
        norm = self.np.linalg.norm(embeddings, ord=2, axis=1, keepdims=True)
        # 防止除以 0
        norm = self.np.where(norm == 0, 1, norm)
        return (embeddings / norm).tolist()

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        try:
            raw_embeddings = self.flag_model.encode_documents(texts)
        except AttributeError:
            raw_embeddings = self.flag_model.encode(texts)

        return self._normalize(raw_embeddings)

    def embed_query(self, text: str) -> List[float]:
        try:
            raw_embeddings = self.flag_model.encode_queries([text])
        except AttributeError:
            raw_embeddings = self.flag_model.encode([text])

        normalized = self._normalize(raw_embeddings)
        return normalized[0]
#定义RAGAgent
class RAGAgent:
    def __init__(self):
        print("正在初始化 RAG 引擎")
        os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
        local_model_path = r"D:/XiaoGui-Assistant/bge-small-zh-v1.5"
        self.embedding_model = None
        self.vectorstore = None
        try:
            self.embedding_model = FlagEmbeddingAdapter(local_model_path)

            print("嵌入模型加载成功（通过适配器）")

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
class AgentState(TypedDict):#typedstate是定义数据结构
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


# 定义检索节点
def rag_retrieval_node(state: AgentState):
    user_msg = state["messages"][-1]

    #闲聊关键词列表
    chit_chat_keywords = [
        "你是谁", "你好", "hello", "hi", "谢谢", "感谢", "再见",
        "拜拜", "叫什么", "身份", "测试", "在吗", "吃了吗",
        "天气", "名字", "介绍下自己", "你能做什么"
    ]

    # 检查用户消息是否包含闲聊关键词
    if any(keyword in user_msg for keyword in chit_chat_keywords) or len(user_msg) < 4:
        print(f"检测到闲聊或短消息：'{user_msg}'，跳过检索。")
        return {"context": ""}

    # 原来的上传指令判断
    if (user_msg.startswith("上传") or user_msg.startswith("学习")) and len(user_msg) < 10:
        print("检测到上传指令，跳过检索。")
        return {"context": ""}

    # --- 下面是正常地检索逻辑 ---
    print(f"\n正在思考：'{user_msg}'，去知识库找找线索...")

    relevant_docs = rag_agent.search(user_msg)
    # 把找到的几段话拼成一个大字符串
    context_str = "\n---\n".join(relevant_docs)

    if relevant_docs:
        print(f"✅ 找到了 {len(relevant_docs)} 条线索！")
        return {"context": context_str}
    else:
        print("⚠️ 知识库里没有相关线索。")
        return {"context": ""}
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
    workflow.add_node("retriever", rag_retrieval_node)
    workflow.add_node("chat", chat_node)

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
    #memory = SqliteSaver.from_conn_string("sqlite:///memory.db")
    memory=MemorySaver()
    # 5. 编译并返回应用
    app = workflow.compile(checkpointer=memory)
    return app


