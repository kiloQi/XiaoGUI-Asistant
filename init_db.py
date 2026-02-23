#初始化数据库，已成功创建memory。db和conversations表
import  sqlite3
import os

def create_memory_db():
    conn = sqlite3.connect('memory.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS conversations  (
    id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    ai_response INTEGER NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()
    print("memory.db创建成功")

def create_deepseek_agent_db():
    conn = sqlite3.connect('deepseek_agent.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS agent_logs  (
    id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    action TEXT NOT NULL,
    result TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()
    print("deepseek_agent.db创建成功")


def create_users_db():
    conn = sqlite3.connect('memory.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users  (
    id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT UNIQUE NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()
    print("users.db创建成功")

if __name__ == '__main__':
    create_memory_db()
    create_deepseek_agent_db()
    create_users_db()
    print("所有数据库初始化成功")