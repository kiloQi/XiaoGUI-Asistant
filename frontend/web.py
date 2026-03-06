import streamlit as st
import requests
import json
import uuid
from datetime import datetime
import time


# ==============================================================================
# 1. 页面基础配置
# ==============================================================================
st.set_page_config(
    page_title="小桂助手",
    page_icon="logo.png",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# ==============================================================================
# 2. 注入自定义 CSS (保持你的极简黑白风格)
# ==============================================================================
st.markdown("""
<style>
    /* --- 全局重置 --- */
    .stApp {
        background-color: #ffffff;
        color: #000000;
        font-family: 'Georgia', 'Times New Roman', serif;
    }

    /* --- 隐藏侧边栏和页脚 --- */
    #MainMenu, footer, header, .stDeployButton {
        visibility: hidden;
        display: none;
    }

    /* --- 标题区域设计 --- */
    .custom-header {
        padding: 40px 0 20px 0;
        border-bottom: 2px solid #000;
        margin-bottom: 30px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        flex-wrap: wrap;
        gap: 15px;
    }
    .main-title {
        font-size: 36px;
        font-weight: 900;
        letter-spacing: -1.5px;
        margin: 0;
        font-family: 'Helvetica Neue', Arial, sans-serif;
        text-transform: uppercase;
    }

    /* --- 导出按钮特殊样式 --- */
    .export-btn button {
        background: #fff;
        color: #000;
        border: 1px solid #000;
        border-radius: 0;
        padding: 8px 16px;
        font-weight: 700;
        text-transform: uppercase;
        font-size: 10px;
        letter-spacing: 1px;
        font-family: 'Helvetica Neue', Arial, sans-serif;
        transition: all 0.2s ease;
        cursor: pointer;
        white-space: nowrap;
    }
    .export-btn button:hover {
        background: #000;
        color: #fff;
        transform: translateY(-2px);
        box-shadow: 2px 2px 0px #000;
    }

    /* --- 聊天消息容器 --- */
    .stChatMessage {
        background: transparent !important;
        border: 1px solid #000;
        border-radius: 0 !important;
        padding: 20px !important;
        margin: 20px 0 !important;
        box-shadow: none !important;
    }

    /* --- 彻底隐藏头像 --- */
    .stChatMessage .stAvatar {
        display: none !important;
        width: 0 !important;
        height: 0 !important;
        visibility: hidden !important;
        margin: 0 !important;
        padding: 0 !important;
    }

    /* --- 消息内容排版 --- */
    .stChatMessage .stMarkdown {
        font-size: 16px;
        line-height: 1.8;
        color: #000;
        font-weight: 400;
        padding-left: 0 !important;
        margin-left: 0 !important;
        max-width: 100%;
    }

    /* 用户消息加粗 */
    .stChatMessage[data-testid="stChatMessage"]:nth-child(odd) .stMarkdown {
        font-weight: 700;
        font-family: 'Helvetica Neue', Arial, sans-serif;
        font-size: 16px;
    }

    /* --- 隐藏时间戳 --- */
    .stChatMessage .stMetadata {
        display: none !important;
        visibility: hidden !important;
        height: 0 !important;
        font-size: 0 !important;
    }

    /* --- 上传区域设计 --- */
    .upload-wrapper {
        margin-bottom: 20px;
        padding: 0; 
    }

    .stFileUploader label {
        font-family: 'Helvetica Neue', Arial, sans-serif;
        font-size: 12px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 1px;
        color: #000;
        margin-bottom: 5px;
    }
    .stFileUploader div[data-testid="stFileDropzone"] {
        border: 1px solid #ccc !important;
        background: #fff !important;
        border-radius: 0 !important;
        padding: 10px !important;
        min-height: 60px;
        display: flex;
        align-items: center;
        justify-content: center;
    }
    .stFileUploader div[data-testid="stFileDropzone"]:hover {
        background: #f9f9f9 !important;
        border-color: #000 !important;
    }

    /* --- 输入框区域设计 --- */
    .stChatInputContainer {
        border-top: 2px solid #000;
        padding-top: 20px;
        margin-top: 20px;
    }

    .stChatInputTextArea textarea {
        border: 1px solid #ccc;
        background: #fff;
        color: #000;
        font-size: 16px;
        font-family: 'Georgia', serif;
        resize: none;
        box-shadow: none !important;
        padding: 15px;
        line-height: 1.6;
        border-radius: 0 !important;
    }
    .stChatInputTextArea textarea:focus {
        outline: none;
        border-color: #000 !important;
        box-shadow: none !important;
    }
</style>
""", unsafe_allow_html=True)


# ==============================================================================
# 3. 辅助功能：导出逻辑
# ==============================================================================
def format_chat_history():
    """将聊天记录格式化为文本"""
    if not st.session_state.get("messages", []):
        return "暂无聊天记录。"

    history_text = f"小桂助手聊天记录\n生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    history_text += "=" * 40 + "\n\n"

    for msg in st.session_state.messages:
        role = "用户" if msg["role"] == "user" else "助手"
        content = msg["content"]
        history_text += f"[{role}]:\n{content}\n\n"
        history_text += "-" * 20 + "\n\n"

    return history_text


# ==============================================================================
# 4. 后端通信逻辑
# ==============================================================================
def get_thread_id():
    if "thread_id" not in st.session_state:
        st.session_state.thread_id = str(uuid.uuid4())
    return st.session_state.thread_id


def upload_file_to_backend(file):
    """上传文件到后端"""
    url = "http://localhost:8000/upload_and_parse"
    try:
        files = {"file": (file.name, file.getvalue(), file.type)}
        response = requests.post(url, files=files, timeout=120)
        if response.status_code == 200:
            return True, response.json().get("message", "上传成功")
        else:
            return False, f"上传失败：{response.text}"
    except Exception as e:
        return False, f"连接错误：{str(e)}"


def stream_response(message):
    """流式获取后端响应（含历史记录清洗）"""

    # --- 🚑 紧急修复：清洗残缺的 tool_calls 历史 ---
    # 如果 session_state 里有 messages，检查是否有未闭合的 tool_calls
    if "messages" in st.session_state:
        clean_messages = []
        i = 0
        while i < len(st.session_state.messages):
            msg = st.session_state.messages[i]

            # 如果这条消息有 tool_calls
            if msg.get("role") == "assistant" and "tool_calls" in msg:
                # 检查下一条是不是 tool 类型的回复
                if i + 1 < len(st.session_state.messages) and st.session_state.messages[i + 1].get("role") == "tool":
                    # 正常：保留这两条
                    clean_messages.append(msg)
                    clean_messages.append(st.session_state.messages[i + 1])
                    i += 2
                else:
                    # ❌ 异常：有 tool_calls 但没有后续 tool 回复 -> 丢弃这条 assistant 消息
                    # 防止发送给后端导致 400 错误
                    print(f"⚠️ 检测到残缺的 tool_calls 消息，已自动丢弃：{msg.get('content', '')[:20]}...")
                    i += 1
            else:
                # 普通消息，直接保留
                clean_messages.append(msg)
                i += 1

        # 更新清洗后的历史
        st.session_state.messages = clean_messages
    # ------------------------------------------------

    url = "http://localhost:8000/chat"

    # 注意：这里发送给后端的 payload 可能包含了 history
    # 如果你的后端是自己维护 history，那上面这段清洗主要在本地防错
    # 如果后端依赖前端传 history，你可能需要把 clean_messages 也传过去

    payload = {
        "message": message,
        "config": {"thread_id": get_thread_id()}
    }

    try:
        with requests.post(url, json=payload, stream=True, timeout=180) as r:
            r.raise_for_status()  # 这里会抛出 400 错误
            for line in r.iter_lines(decode_unicode=True):
                if line:
                    line = line.strip()
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break
                        try:
                            data = json.loads(data_str)
                            chunk = data.get("content", "")
                            if chunk and isinstance(chunk, str):
                                yield chunk
                        except json.JSONDecodeError:
                            continue
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 400:
            yield "❌ **对话上下文出错**：检测到历史记录中有未完成的工具调用。\n\n建议：\n1. 点击左上角刷新页面重新开始对话。\n2. 或者联系开发者修复后端逻辑。"
        else:
            yield f"❌ 请求失败：{str(e)}"
    except requests.exceptions.ConnectionError:
        yield "❌ 无法连接后端 (端口 8000)。请确认后端已启动。"
    except Exception as e:
        yield f"❌ 错误：{str(e)}"
# ==============================================================================
# 5. 主界面渲染
# ==============================================================================

# --- 初始化状态锁 (防止并发冲突) ---
if "is_learning" not in st.session_state:
    st.session_state.is_learning = False
if "current_file_name" not in st.session_state:
    st.session_state.current_file_name = None
if "messages" not in st.session_state:
    st.session_state.messages = []

# --- 顶部标题 + 导出按钮 ---
col_title, col_btn = st.columns([3, 1])

with col_title:
    st.markdown('<div class="main-title">小桂助手</div>', unsafe_allow_html=True)

with col_btn:
    chat_data = format_chat_history()
    file_name = f"chat_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    st.download_button(
        label="导出会话记录",
        data=chat_data,
        file_name=file_name,
        mime="text/plain",
        key="download_chat",
        help="下载当前对话记录为 TXT 文件"
    )

st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)

# --- 渲染历史消息 ---
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# --- 布局调整：上传组件旁置 ---
col_upload, col_space = st.columns([3, 7])

with col_upload:
    # 如果正在学习中，禁用上传器视觉反馈（可选）
    uploaded_file = st.file_uploader(
        "上传文档/图片",
        type=['pdf', 'docx', 'txt', 'png', 'jpg', 'jpeg'],
        key="uploader",
        help="支持 PDF, Word, TXT, PNG, JPG",
        disabled=st.session_state.is_learning  # 🔒 学习中禁止上传
    )

    if uploaded_file is not None:
        # 检查是否是同一个文件重复触发
        if st.session_state.get("last_uploaded_file") != uploaded_file.name:
            if st.session_state.is_learning:
                st.warning(f"️ 正在学习：{st.session_state.current_file_name}，请稍候...")
            else:
                # 🔒 加锁
                st.session_state.is_learning = True
                st.session_state.current_file_name = uploaded_file.name

                with st.spinner("解析中..."):
                    success, message = upload_file_to_backend(uploaded_file)
                    if success:
                        st.success(f"✅ {message}")
                        st.session_state.last_uploaded_file = uploaded_file.name
                    else:
                        st.error(f"❌ {message}")

                    # 🔓 解锁
                    st.session_state.is_learning = False
                    st.session_state.current_file_name = None
                    # 强制刷新以清除上传状态
                    st.rerun()

# --- 处理用户输入 (最终稳定版) ---
if st.session_state.is_learning:
    st.warning(f"📚 正在学习文件：**{st.session_state.current_file_name}**\n\n请先等待文件解析完成后再提问。")
    st.stop()

if prompt := st.chat_input("向小桂提问"):
    # 1. 显示用户消息
    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    # 2. 助手回复区域
    with st.chat_message("assistant"):
        # 【关键修改 1】创建一个唯一的、稳定的占位符
        response_placeholder = st.empty()

        full_response = ""

        # 【关键修改 2】设置最小渲染间隔 (秒)，防止 DOM 操作过快崩溃
        # 0.05 秒 = 50 毫秒，人眼感觉是流畅的，但给浏览器留了喘息时间
        MIN_RENDER_INTERVAL = 0.05
        last_render_time = 0

        try:
            for chunk in stream_response(prompt):
                if chunk:
                    full_response += chunk

                    current_time = time.time()

                    # 【关键修改 3】只有距离上次渲染超过间隔，才更新 UI
                    if current_time - last_render_time > MIN_RENDER_INTERVAL:
                        # 使用 replace 确保光标始终在最后，且内容完整
                        response_placeholder.markdown(full_response + "▌")
                        last_render_time = current_time

            # 循环结束，确保最后一段（不足间隔的部分）也被渲染，并去掉光标
            response_placeholder.markdown(full_response)

        except Exception as e:
            # 出错时也要把已有的内容显示出来，并提示错误
            error_msg = f"\n\n*(⚠️ 连接中断：{str(e)})*"
            response_placeholder.markdown(full_response + error_msg)
            print(f"Stream error: {e}")

    # 3. 保存历史
    st.session_state.messages.append({"role": "assistant", "content": full_response})