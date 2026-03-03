import os
import requests
from typing import Dict,Any

from . import mcp
@mcp.tool()
def get_weather(city_name:str) -> Dict[str,Any]:
    """
    查询指定城市的实时天气
    :param city_name: 城市名，如 '北京', '上海'
    :return: 天气信息字典
    """

    #1.查找城市代码（adcode）
    geo_url="https://restapi.amap.com/v3/config/district"
    geo_params={
        "keyword":city_name,
        "subdistrict":0,
        "key":{os.getenv("AMAP_WEATHER_KEY")},

    }
    try:
         #请求城市代码
         geo_response = requests.get(geo_url,params=geo_params)
         geo_data = geo_response.json()
         if geo_data.get("status")==1 and geo_data.get("district"):
             adcode=geo_data["district"][0]["adcode"]
             city_name_real=geo_data["district"][0]["name"]   #标准化后的城市名

         else:
             return {"success":False,"error":f"找不到城市：{city_name}"}

#2.查天气
         weather_url="https://restapi.amap.com/v3/weather/weatherInfo"
         weather_params={
            "key":{os.getenv("AMAP_WEATHER_KEY")},
            "city":city_name,
            "extensions":"base"            # base返回实时天气，all返回预报
        }
         weather_response = requests.get(weather_url,params=weather_params)
         weather_data = weather_response.json()

         if weather_data.get("status")==1 and weather_data.get("lives"):
            live=weather_data["lives"][0]
            result_text = (
                f"城市：{city_name_real}\n"
                f"天气：{live['weather']}\n"
                f"温度：{live['temperature']}°C\n"
                f"风向：{live['winddirection']}风 {live['windpower']}级\n"
                f"湿度：{live['humidity']}%\n"
                f"发布时间：{live['reporttime']}"
            )
            return {"success": True, "answer": result_text}
         else:
            return {"success": False, "error": "获取天气数据失败，可能该城市无数据"}

    except Exception as e:
                 return {"success": False, "error": f"程序出错：{str(e)}"}



