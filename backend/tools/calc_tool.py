from . import mcp

_CALC_TOOL_REGISTERED = False

class ExpressionCalculator:
    """
    表达式计算器类
    """
    def __init__(self):
        pass

    def calculate(self, expression: str) -> str:
        """
        计算数学表达式的结果
        """
        if not expression or expression.strip() == "":
            return "表达式不能为空，请输入有效的数学表达式"

        try:
            result = eval(expression)
            return str(result)
        except SyntaxError:
            return "表达式语法错误，请检查格式（如括号是否配对、运算符是否正确）"
        except ZeroDivisionError:
            return "表达式错误：除数不能为0"
        except NameError:
            return "表达式错误：包含未定义的变量，请只输入数字和运算符"
        except Exception as e:
            return f"计算失败：{str(e)}"

calc_instance = ExpressionCalculator()

calc_instance.calculate = mcp.tool(
    name="calculator",
    description="数学计算工具，用于计算字符串形式的数学表达式，支持加减乘除等基本运算"
)(calc_instance.calculate)


def register_calc_tool():
    """注册计算器工具（确保只注册一次）"""
    global _CALC_TOOL_REGISTERED
    if not _CALC_TOOL_REGISTERED:
        try:
            mcp.add_tool(calc_instance.calculate)
            _CALC_TOOL_REGISTERED = True
        except Exception as e:
            _CALC_TOOL_REGISTERED = True


register_calc_tool()

def get_calculator_tool():
    """获取绑定好的计算器工具方法"""
    return calc_instance.calculate

