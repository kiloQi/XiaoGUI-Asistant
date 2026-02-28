import streamlit as st
import requests
import json
import os
import time

# 配置区域
BACKEND_URL = "http://127.0.0.1:8000"
UPLOAD_URL = f"{BACKEND_URL}/upload_and_parse"
CHAT_URL = f"{BACKEND_URL}/chat"
st.set_page_config(
    page_title="小桂助手 - AI 智能体",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 初始化会话状态
if "messages" not in st.session_state:
    st.session_state.messages = []
if "current_file_path" not in st.session_state:
    st.session_state.current_file_path = None
if "rag_status" not in st.session_state:
    st.session_state.rag_status = "未加载文档"

import uuid
if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())

# CSS (美化界面)
st.markdown("""
<style>
    .stChatMessage {padding: 10px;}
    .status-badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.85em;
        font-weight: bold;
        margin-bottom: 10px;
    }
    .status-thinking {background-color: #fff3cd; color: #856404;}
    .status-searching {background-color: #d1ecf1; color: #0c5460;}
    .status-tool {background-color: #d4edda; color: #155724;}
</style>
""", unsafe_allow_html=True)

# 侧边栏：文件上传与 RAG
with st.sidebar:
    st.header("📂 知识库管理")
    st.markdown("上传 PDF/TXT/Word 文档，让小桂学习后再回答。")

    uploaded_file = st.file_uploader(
        "选择文件",
        type=["txt", "pdf", "docx", "doc", "md"],
        help="支持 txt, pdf, docx 等格式"
    )

    if uploaded_file is not None:
        # 显示文件信息
        st.info(f"📄 **{uploaded_file.name}**\n大小：{uploaded_file.size / 1024:.2f} KB")

        if st.button(" 上传并解析到知识库", type="primary"):
            with st.spinner("⏳ 正在上传并解析文档..."):
                try:
                    files = {"file": (uploaded_file.name, uploaded_file.getvalue())}
                    response = requests.post(UPLOAD_URL, files=files, timeout=60)

                    if response.status_code == 200:
                        result = response.json()
                        if result.get("status") == "success":
                            st.success("✅ 文档解析成功！已存入向量库。")
                            # 保存文件路径，以便在聊天工作流中使用
                            st.session_state.current_file_path = result.get("saved_path")
                            st.session_state.rag_status = f"已加载：{uploaded_file.name}"

                            # 自动添加一条系统消息提示用户
                            st.session_state.messages.append({
                                "role": "assistant",
                                "content": f"我已经学习了《{uploaded_file.name}》，你可以问我关于它的内容了！（共解析 {result['parse_data']['chunk_count']} 个片段）"
                            })
                        else:
                            st.error(f"❌ 解析失败：{result.get('message')}")
                    else:
                        st.error(f"❌ 服务器错误：{response.status_code}")
                except Exception as e:
                    st.error(f"❌ 连接失败：{str(e)}\n请确保后端 main.py 已启动。")

    st.divider()
    st.markdown(f"**当前状态**: {st.session_state.rag_status}")
    if st.session_state.current_file_path:
        st.code(st.session_state.current_file_path, language="text")

    if st.button("🗑 清空对话历史"):
        st.session_state.messages = []
        st.rerun()

#主界面：聊天对话框
st.title("🤖 小桂助手")
st.markdown("基于 LangGraph + FastAPI + Streamlit | 支持 RAG 检索与工具调用")

# 显示历史消息
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# 聊天输入框
if prompt := st.chat_input("请输入问题，或上传文件让我学习..."):
    # 1. 显示用户消息
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # 2. 准备发送给后端的数据
    payload = {
        "message": prompt,
        "file_path": st.session_state.current_file_path ,     # 如果有文件，传过去
        "config": {
            "configurable": {
                "thread_id": st.session_state.thread_id
            }
        }
    }

    # 3. 调用后端并流式显示
    with st.chat_message("assistant"):
        status_placeholder = st.empty()        # 用于显示动态状态
        response_placeholder = st.empty()      # 用于显示打字机效果

        full_response = ""

        # 模拟状态更新
        if "计算" in prompt or "时间" in prompt:
            status_placeholder.markdown('<span class="status-badge status-tool">🛠 正在调用工具...</span>',
                                        unsafe_allow_html=True)
        elif st.session_state.current_file_path:
            status_placeholder.markdown('<span class="status-badge status-searching">🔍 正在检索知识库...</span>',
                                        unsafe_allow_html=True)
        else:
            status_placeholder.markdown('<span class="status-badge status-thinking"> 正在思考...</span>',
                                        unsafe_allow_html=True)

        try:
            # 尝试请求流式接口 /chat
            response = requests.post(CHAT_URL, json=payload, stream=True, timeout=30)

            if response.status_code == 200:
                for line in response.iter_lines():
                    if line:
                        decoded_line = line.decode("utf-8")
                        if decoded_line.startswith("data: "):
                            data = json.loads(decoded_line[6:])
                            token = data.get("token", "")
                            full_response += token
                            response_placeholder.markdown(full_response + "▌")
            else:
                # 如果后端返回非 200，直接显示错误
                full_response = f"⚠️ 后端响应异常：{response.status_code}"
                response_placeholder.markdown(full_response)

        except requests.exceptions.ConnectionError:
            time.sleep(1)
            if "计算" in prompt:
                full_response = "🛠️ [模拟] 正在调用计算器工具...\n结果是：..."
            elif st.session_state.current_file_path:
                full_response = "🔍 [模拟] 已在知识库中检索到相关内容...\n根据文档，《" + os.path.basename(
                    st.session_state.current_file_path) + "》中提到..."
            else:
                full_response = f"小桂收到：'{prompt}'。\n(提示：请确保后端 main.py 中实现了 /chat 接口以支持真实流式对话)"

            response_placeholder.markdown(full_response)

        finally:
            status_placeholder.empty()
            # 保存最终回复
            st.session_state.messages.append({"role": "assistant", "content": full_response})

#底部说明
st.markdown("---")
st.caption(" 提示：上传文件后，请在对话框中输入与该文件相关的问题，系统将自动触发 RAG 检索。")