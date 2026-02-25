import requests
import streamlit as st

# 页面配置
st.set_page_config(page_title="文档上传与解析", layout="wide")
st.title("📄 文档上传和智能解析")

BACKEND_URL = "http://127.0.0.1:8000/upload_and_parse"

# 添加文件上传组件
uploaded_file = st.file_uploader(
    "请选择要上传的文件 (支持 TXT, PDF, Word, Markdown, CSV)",
    type=["txt", "pdf", "docx", "doc", "xlsx", "xls", "csv", "md"]
)

if uploaded_file is not None:

    st.info(f"✅ 已选中文件：**{uploaded_file.name}**")
    st.write(f"📦 文件大小：{uploaded_file.size / 1024:.2f} KB")

    file_type = uploaded_file.name.split('.')[-1].lower()
    text_types = ['txt', 'csv', 'md', 'py', 'json']


    if file_type in text_types:
        try:
            content = uploaded_file.read().decode("utf-8")
            with st.expander(" 本地快速预览 (仅文本文件)", expanded=False):
                st.text_area(label="文件内容", value=content, height=200)
            uploaded_file.seek(0)  # 重置指针
        except UnicodeDecodeError:
            st.warning("⚠️ 该文件包含特殊编码，无法直接预览，但可上传解析。")
            uploaded_file.seek(0)
    else:
        st.info(f"📄 这是一个 **.{file_type}** 文件，需上传到后端解析。")
        uploaded_file.seek(0)

    st.divider()


    st.subheader(" 后端处理")

    if st.button(" 上传并开始解析", type="primary"):
        try:
            uploaded_file.seek(0)



            files = {"file": (uploaded_file.name, uploaded_file.getvalue())}

            with st.spinner('⏳ 正在上传并解析中，请稍候...'):
                response = requests.post(BACKEND_URL, files=files, timeout=60)

            if response.status_code == 200:
                result = response.json()

                if result.get("status") == "success":
                    st.success("✅ 解析成功！")


                    parse_data = result.get("parse_data", {})

                    # 显示基本信息
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("文件名", result.get("filename"))
                    with col2:
                        st.metric("切分块数", parse_data.get("chunk_count", 0))
                    with col3:
                        st.metric("文件大小", f"{result.get('file_size', 0) / 1024:.1f} KB")

                    st.markdown("### 📝 解析结果详情：")

                    # 选项卡展示：全文预览 vs 分块详情
                    tab1, tab2 = st.tabs([" 全文预览", " 分块详情 "])

                    with tab1:
                        full_text = parse_data.get("full_text_preview", "无预览内容")
                        st.text_area(
                            label="原文前 500 字预览",
                            value=full_text,
                            height=400,
                            key="preview_full"
                        )

                    with tab2:
                        chunks = parse_data.get("chunks", [])
                        if chunks:
                            for i, chunk in enumerate(chunks):
                                with st.expander(f"🔹 第 {i + 1} 块 ({len(chunk)} 字符)"):
                                    st.write(chunk)
                        else:
                            st.warning("未生成文本分块。")

                    # 下载按钮
                    st.download_button(
                        label="📥 下载完整解析文本",
                        data=parse_data.get("full_text_preview", "") + "\n...(更多内容见分块)",  # 这里简单处理，实际可拼接所有 chunks
                        file_name=f"{uploaded_file.name.split('.')[0]}_parsed.txt",
                        mime="text/plain"
                    )

                else:
                    # 后端返回业务错误 (如格式不支持)
                    st.error(f"❌ 解析失败：{result.get('message', '未知错误')}")

            else:
                # HTTP 请求错误 (如 500, 404)
                st.error(f"❌ 服务器响应异常：状态码 {response.status_code}")
                st.code(response.text)

        except requests.exceptions.ConnectionError:
            st.error(" 连接失败！无法连接到后端服务。")
            st.info(" 请检查：\n1. 后端 (main.py) 是否已启动？\n2. 端口是否为 8000？\n3. URL 是否正确？")
        except Exception as e:
            st.error(f"❌ 发生未知错误：{str(e)}")