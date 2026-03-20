from datetime import datetime

def get_current_time():
    """获取当时的实时时间"""
    return f"当前时间为{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

