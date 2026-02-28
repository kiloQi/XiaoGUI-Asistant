import os
from typing import Dict, Any

import requests

from . import mcp

_WEATHER_TOOL_REGISTERED = False

class WeatherQueryTool:
    """高德地图天气查询工具类"""
    def get_weather(self, city_name: str) -> Dict[str, Any]:
        """
        查询指定城市的实时天气
        """
        geo_url = "https://restapi.amap.com/v3/config/district"
        geo_params = {
            "keyword": city_name,
            "subdistrict": 0,
            "key": os.getenv("AMAP_WEATHER_KEY"),
        }

        try:
            geo_response = requests.get(geo_url, params=geo_params)
            geo_data = geo_response.json()

            if geo_data.get("status") == "1" and geo_data.get("district"):
                adcode = geo_data["district"][0]["adcode"]
                city_name_real = geo_data["district"][0]["name"]
            else:
                return {"success": False, "error": f"找不到城市：{city_name}"}

            weather_url = "https://restapi.amap.com/v3/weather/weatherInfo"
            weather_params = {
                "key": os.getenv("AMAP_WEATHER_KEY"),
                "city": adcode,
                "extensions": "base"
            }

            weather_response = requests.get(weather_url, params=weather_params)
            weather_data = weather_response.json()

            if weather_data.get("status") == "1" and weather_data.get("lives"):
                live = weather_data["lives"][0]
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


weather_tool_instance = WeatherQueryTool()

weather_tool_instance.get_weather = mcp.tool(
    name="weather_query",
    description="天气查询工具，查询指定城市的实时天气信息",
)(weather_tool_instance.get_weather)


def register_weather_query_tool():
    """注册天气查询工具（确保只注册一次）"""
    global _WEATHER_TOOL_REGISTERED
    if not _WEATHER_TOOL_REGISTERED:
        try:
            mcp.add_tool(weather_tool_instance.get_weather)
            _WEATHER_TOOL_REGISTERED = True
        except Exception as e:
            _WEATHER_TOOL_REGISTERED = True


register_weather_query_tool()


def get_weather_tool():
    """获取绑定好的天气工具方法"""
    return weather_tool_instance.get_weather
