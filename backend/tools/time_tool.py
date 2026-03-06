from datetime import datetime


def get_current_time():
     return f"当前时间为{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

