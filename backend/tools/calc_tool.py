import ast
import operator
import math

# 定义允许的运算符映射
ALLOWED_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.USub: operator.neg,  # 负号
    ast.UAdd: operator.pos,  # 正号
}

# 定义允许的函数映射 (支持 sin, cos, tan, sqrt, log, pi, e 等)
ALLOWED_FUNCTIONS = {
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "sqrt": math.sqrt,
    "log": math.log,
    "log10": math.log10,
    "exp": math.exp,
    "abs": abs,
    "round": round,
    "pi": math.pi,
    "e": math.e,
}


def safe_eval(expr: str) -> float:
    """
    安全地计算数学表达式，不使用 eval()
    """
    try:
        # 1. 预处理：替换中文括号和空格
        expr = expr.replace("（", "(").replace("）", ")").replace(" ", "")

        # 2. 解析表达式为 AST (抽象语法树)
        node = ast.parse(expr, mode='eval').body

        def _eval(node):
            if isinstance(node, ast.Num):  # Python < 3.8
                return node.n
            elif isinstance(node, ast.Constant):  # Python >= 3.8
                if isinstance(node.value, (int, float)):
                    return node.value
                raise ValueError("只允许数字常量")
            elif isinstance(node, ast.BinOp):
                left = _eval(node.left)
                right = _eval(node.right)
                op_type = type(node.op)
                if op_type in ALLOWED_OPERATORS:
                    return ALLOWED_OPERATORS[op_type](left, right)
                else:
                    raise ValueError(f"不允许的运算符: {op_type}")
            elif isinstance(node, ast.UnaryOp):
                operand = _eval(node.operand)
                op_type = type(node.op)
                if op_type in ALLOWED_OPERATORS:
                    return ALLOWED_OPERATORS[op_type](operand)
                else:
                    raise ValueError(f"不允许的一元运算符: {op_type}")
            elif isinstance(node, ast.Call):
                func_name = node.func.id
                if func_name in ALLOWED_FUNCTIONS:
                    func = ALLOWED_FUNCTIONS[func_name]
                    args = [_eval(arg) for arg in node.args]
                    return func(*args)
                else:
                    raise ValueError(f"不允许的函数: {func_name}")
            elif isinstance(node, ast.Name):
                if node.id in ALLOWED_FUNCTIONS:
                    return ALLOWED_FUNCTIONS[node.id]
                else:
                    raise ValueError(f"不允许的变量: {node.id}")
            else:
                raise TypeError(f"不支持的表达式类型: {type(node)}")

        result = _eval(node)

        # 处理浮点数精度问题 (比如 0.1 + 0.2 = 0.30000000000000004)
        if isinstance(result, float):
            result = round(result, 10)
            # 如果是整数结果，转为 int 显示更清爽
            if result.is_integer():
                result = int(result)

        return result

    except Exception as e:
        raise ValueError(f"计算错误: {str(e)}")


def calculate(expression: str):
    """
    安全计算器工具
    """
    try:
        # 执行安全计算
        result = safe_eval(expression)

        return f"表达式 {expression} 的计算结果是 {result}。"

    except Exception as e:
        # 错误信息也要朴实
        return f"计算表达式 {expression} 时出错：{str(e)}"