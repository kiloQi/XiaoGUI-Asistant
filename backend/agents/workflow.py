from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from typing import TypedDict, Annotated, List, Optional
import operator
from langgraph.graph import StateGraph,END
import os
import asyncio

from streamlit import success

from backend.tools.file_parsing_tool import parse_file
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.document_loaders import PyPDFLoader,Docx2txtLoader,TextLoader


#定义RAGAgent
class RAGAgent:
    def __init__(self):

        print("正在初始化RAG引擎")

        try:
            self.embedding_model=HuggingFaceEmbeddings(
                model_name="BAAI/bge-small-zh-v1.5",    #支持中文的免费模型
                model_kwargs={'device':'cpu'},
                encode_kwargs={'normalize_embeddings':True}

            )
            print("嵌入模型加载成功")

        except Exception as e:
            print(f"⚠️ 模型加载失败 : {e}")
            print("💡 提示：请检查网络连接，或尝试手动下载模型到本地。")

            self.embedding_model=None

            #初始化一个空的向量数据库
            self.vectorstore:Optional[FAISS]=None

    def parse_file(self, file_path: str) -> List[str]:
            """
            读取文件内容，切成一段一段的文字。
            """
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

    def add_documents(self,texts:List[str]):
            """
            把文字存进向量数据库
            """
            if not texts or self.embedding_model is None:
                return False

            try:
                if self.vectorstore is None:
                    self.vectorstore=FAISS.from_texts(texts,self.embedding_model)

                else:
                    self.vectorstore.add_texts(texts)   #追加进去
                    print("已成功存进知识库")
                    return True
            except Exception as e:
                print(f"知识库存入失败：{e}")
                return False

    def search(self,query:str):
            """
            根据问题查找最相关的资料
            """
            if self.embedding_model is None or self.vectorstore   is None:
                return []
            try:
                docs=self.vectorstore.simlarity_search(query,k=3)
                return [doc.page_content for doc in docs]
            except Exception as e:
                print("检索失败：{e}")
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

#定义检索节点
def rag_retrieval_node(state: AgentState):

    user_msg=state["messages"][-1]
    # 如果用户是在说“上传文件”，那就不需要检索，直接跳过
    if "上传" in user_msg or "学习" in user_msg:
        return {"context": ""}

    print(f"\n  正在思考：'{user_msg}'，去知识库找找线索...")

    relevant_docs = rag_agent.search(user_msg)
    # 把找到的几段话拼成一个大字符串
    context_str = "\n\n--- 参考资料 ---\n".join(relevant_docs)
    if relevant_docs:
        print(f"找到了 {len(relevant_docs)} 条线索！")
        return {"context": context_str}

    else:
        print(" 知识库里没有相关线索。")
        return {"context": ""}

#定义聊天节点
def chat_node(state: AgentState):
    """模拟聊天节点，这里需要调用llm"""
    user_msg=state["messages"][-1]   #取最后一条消息（用户刚说的）

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







