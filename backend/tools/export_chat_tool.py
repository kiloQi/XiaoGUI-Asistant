#聊天记录保存工具

import os
import datetime


#定义导出文件夹的路径
EXPORT_DIR=r"D:\XiaoGui-Assistant\backend\exports"

#检查文件夹是否存在，不存在就创建一个
if not os.path.exists(EXPORT_DIR):
    os.makedirs(EXPORT_DIR)


def save_messages_to_markdown(messages,file_name:str="chat_log")->str:
    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")

    #拼凑最终文件名
    final_file_name=f"{file_name}_{timestamp}.md"

    #拼凑最终完整路径
    file_path=os.path.join(EXPORT_DIR,final_file_name)
    try:
        with open(file_path,"w",encoding="utf-8") as f:
            # 写入标题，# 文字 → 变成大标题
            f.write(f"#  小桂助手聊天记录\n\n")

            # 写入生成时间，**文字** → 变成加粗
            f.write(f"**生成时间**: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

            f.write("---\n\n")

            for message in messages:
                role="未知"
                avatar = "🤖"
                if hasattr(message,"type"):#检查一下 message 这个对象有没有 type 这个属性。
                    if message.type=="human":
                        role="用户"
                        avatar="👤"
                    elif message.type == "ai":
                        role = "小桂助手"
                        avatar = "🤖"

                    elif message.type == "tool":
                        role = "工具调用"
                        avatar = "🛠️"

                content=message.content
                # 写入角色标题 (### 表示三级标题)
                f.write(f"### {avatar} {role}\n\n")
                # 写入具体内容
                f.write(f"{content}\n\n")

                f.write("---\n\n")

            return f"✅ 导出成功！文件已保存至：{file_path}\n"
    except Exception as e:
        return f"❌ 导出失败：{str(e)}"
