import logging
import asyncio
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

async def example_hello(name: str = "World") -> Dict[str, Any]:
    """
    示例函数：向指定名称问好
    """
    try:
        message = f"Hello, {name}!"
        logger.info(f"示例函数被调用，参数: name={name}")
        
        return {
            "success": True,
            "message": message,
            "data": {
                "name": name,
                "greeting": message
            }
        }
    except Exception as e:
        logger.error(f"示例函数执行失败: {e}")
        return {
            "success": False,
            "error": str(e)
        }

async def example_calculate(operation: str, a: float, b: float) -> Dict[str, Any]:
    """
    示例函数：执行简单的数学运算
    """
    try:
        result = None
        operation = operation.lower()
        
        if operation == "add":
            result = a + b
            operation_name = "加法"
        elif operation == "subtract":
            result = a - b
            operation_name = "减法"
        elif operation == "multiply":
            result = a * b
            operation_name = "乘法"
        elif operation == "divide":
            if b == 0:
                return {
                    "success": False,
                    "error": "除数不能为零"
                }
            result = a / b
            operation_name = "除法"
        else:
            return {
                "success": False,
                "error": f"不支持的操作: {operation}"
            }
        
        logger.info(f"计算函数被调用: {operation_name} {a} 和 {b}")
        
        return {
            "success": True,
            "operation": operation_name,
            "a": a,
            "b": b,
            "result": result,
            "expression": f"{a} {operation_name} {b} = {result}"
        }
    except Exception as e:
        logger.error(f"计算函数执行失败: {e}")
        return {
            "success": False,
            "error": str(e)
        }

async def example_get_system_info() -> Dict[str, Any]:
    """
    示例函数：获取系统信息
    """
    try:
        import platform
        import datetime
        
        system_info = {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "python_version": platform.python_version(),
            "current_time": datetime.datetime.now().isoformat()
        }
        
        logger.info("获取系统信息函数被调用")
        
        return {
            "success": True,
            "system_info": system_info
        }
    except Exception as e:
        logger.error(f"获取系统信息失败: {e}")
        return {
            "success": False,
            "error": str(e)
        }

def get_tool_definitions() -> List[Dict[str, Any]]:
    """
    获取工具定义，用于AI调用
    """
    return [
        {
            "type": "function",
            "function": {
                "name": "example_hello",
                "description": "示例函数：向指定名称问好",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "名称，默认为'World'"
                        }
                    },
                    "required": []
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "example_calculate",
                "description": "示例函数：执行简单的数学运算（加法、减法、乘法、除法）",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "operation": {
                            "type": "string",
                            "description": "操作类型：add（加法）、subtract（减法）、multiply（乘法）、divide（除法）",
                            "enum": ["add", "subtract", "multiply", "divide"]
                        },
                        "a": {
                            "type": "number",
                            "description": "第一个数字"
                        },
                        "b": {
                            "type": "number",
                            "description": "第二个数字"
                        }
                    },
                    "required": ["operation", "a", "b"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "example_get_system_info",
                "description": "示例函数：获取系统信息（操作系统、Python版本、当前时间等）",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            }
        }
    ]

def register_tools() -> Dict[str, Any]:
    """
    注册所有工具函数
    """
    return {
        "example_hello": example_hello,
        "example_calculate": example_calculate,
        "example_get_system_info": example_get_system_info,
        "get_tool_definitions": get_tool_definitions
    }

TOOLS = register_tools()