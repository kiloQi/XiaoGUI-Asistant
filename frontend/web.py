import requests
import streamlit as st

st.title("文档上传测试")

BACKEND_URL = "http://127.0.0.1:8000/upload"

#添加文件上传组件
uploaded_file=st.file_uploader("请选择要上传的文件(支持TXT,PDF,Word,Excel)",
                               type=["txt","pdf","docx","doc","xlsx","xls","csv","md"])
if uploaded_file is not None:
    st.write(f"✅ 已上传文件：**{uploaded_file.name}**")
    st.write(f"📦 文件大小：{uploaded_file.size / 1024:.2f} KB")

    # ✅ 智能预览：只有文本文件才显示内容
    file_type = uploaded_file.name.split('.')[-1].lower()
    text_types = ['txt', 'csv', 'md', 'py', 'json']

    if file_type in text_types:
        try:
            content = uploaded_file.read().decode("utf-8")
            st.text_area(label="📝 文件内容预览", value=content, height=300)
            # 重置指针，方便后续上传
            uploaded_file.seek(0)
        except UnicodeDecodeError:
            st.warning("⚠️ 该文件包含特殊编码，无法直接预览文本，但可以直接上传。")
            uploaded_file.seek(0)
    else:
        st.info(f"📄 这是一个 **.{file_type}** 文件，无法直接预览文本内容，但可以正常上传到后端。")
        # 重置指针
        uploaded_file.seek(0)

    # 发送文件到后端
    st.divider()
    st.subheader("📤 发送到后端")

    if st.button("确认上传到后端"):
        try:
            # 重新读取文件（因为上面已经 read 过了）
            uploaded_file.seek(0)

            response = requests.post(
                BACKEND_URL,
                files={"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
            )

            if response.status_code == 200:
                result = response.json()
                if result.get("status") == "success":
                    st.success(f"✅ {result['message']}")
                    st.info(f"📁 保存路径：{result['saved_path']}")
                else:
                    st.error(f"❌ 后端返回错误：{result.get('message')}")
            else:
                st.error(f"❌ 请求失败：{response.status_code} - {response.text}")
        except Exception as e:
            st.error(f"❌ 连接后端失败：{str(e)}")
            st.warning("💡 请确保后端服务已启动：python -m uvicorn backend.main:app --reload")

