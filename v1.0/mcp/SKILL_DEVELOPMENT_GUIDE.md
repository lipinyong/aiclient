# Skill 开发指南

## 概述

Skill 是 MCP（Model Context Protocol）服务的基本单元，每个 skill 都是一个独立的 Python 模块，提供一组相关的工具函数。系统会自动发现和加载 mcp 目录下的所有 skill。

## 目录结构

```
F:\code\aiclient\mcp\
├── __init__.py          # 空文件，标识为 Python 包
├── common.py            # 通用工具 skill
├── git.py               # GitLab 集成 skill
├── mysql.py             # MySQL 数据库 skill
├── example.py           # 示例 skill（新创建）
├── file_manager.py      # 文件管理 skill（新创建）
└── SKILL_DEVELOPMENT_GUIDE.md  # 本指南
```

## Skill 基本结构

每个 skill 文件应包含以下部分：

### 1. 导入依赖

```python
import logging
import asyncio
from typing import Dict, Any, List

logger = logging.getLogger(__name__)
```

### 2. 工具函数定义

所有工具函数都应该是异步函数，返回 `Dict[str, Any]` 类型：

```python
async def my_tool_function(param1: str, param2: int = 10) -> Dict[str, Any]:
    """
    函数说明文档
    """
    try:
        # 函数逻辑
        result = f"处理 {param1} 和 {param2}"
        
        logger.info(f"函数被调用: param1={param1}, param2={param2}")
        
        return {
            "success": True,
            "result": result,
            "data": {
                "param1": param1,
                "param2": param2
            }
        }
    except Exception as e:
        logger.error(f"函数执行失败: {e}")
        return {
            "success": False,
            "error": str(e)
        }
```

### 3. 工具定义函数

定义 AI 可以调用的工具接口：

```python
def get_tool_definitions() -> List[Dict[str, Any]]:
    """
    获取工具定义，用于AI调用
    """
    return [
        {
            "type": "function",
            "function": {
                "name": "my_tool_function",  # 必须与注册的函数名一致
                "description": "函数功能描述",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "param1": {
                            "type": "string",
                            "description": "参数1的描述"
                        },
                        "param2": {
                            "type": "integer",
                            "description": "参数2的描述，默认值10",
                            "default": 10
                        }
                    },
                    "required": ["param1"]  # 必填参数
                }
            }
        }
    ]
```

### 4. 工具注册函数

注册所有工具函数：

```python
def register_tools() -> Dict[str, Any]:
    """
    注册所有工具函数
    """
    return {
        "my_tool_function": my_tool_function,
        "get_tool_definitions": get_tool_definitions
    }

TOOLS = register_tools()
```

## 最佳实践

### 1. 错误处理
- 使用 try-except 包装所有逻辑
- 返回统一的错误格式：`{"success": False, "error": "错误信息"}`
- 使用 logger 记录错误信息

### 2. 日志记录
- 使用 `logger.info()` 记录正常操作
- 使用 `logger.error()` 记录错误
- 包含足够的上下文信息

### 3. 参数验证
- 在函数开始时验证参数
- 提供清晰的错误信息
- 设置合理的默认值

### 4. 返回值格式
- 成功时返回：`{"success": True, "data": {...}}`
- 包含操作结果和相关信息
- 保持数据结构一致

## 示例 Skill

### 简单示例 (example.py)
包含三个基本功能：
1. `example_hello` - 问候功能
2. `example_calculate` - 数学计算
3. `example_get_system_info` - 获取系统信息

### 实用示例 (file_manager.py)
包含六个文件管理功能：
1. `file_manager_list_files` - 列出文件
2. `file_manager_get_file_info` - 获取文件信息
3. `file_manager_search_files` - 搜索文件
4. `file_manager_create_directory` - 创建目录
5. `file_manager_copy_file` - 复制文件
6. `file_manager_get_disk_usage` - 获取磁盘使用情况

## 测试 Skill

### 方法1：直接测试
```python
# 在 Python 交互环境中测试
import sys
sys.path.append('F:\\code\\aiclient')
from mcp.example import example_hello

import asyncio
result = asyncio.run(example_hello("测试"))
print(result)
```

### 方法2：通过系统加载测试
1. 确保 skill 文件在 `mcp` 目录下
2. 重启应用或等待热重载（默认2秒间隔）
3. 系统会自动发现和加载新 skill

## 热重载功能

系统支持热重载，当 skill 文件被修改时：
- 自动检测文件变化
- 自动重新加载 skill
- 无需重启应用

热重载间隔：2秒（可在配置中调整）

## 常见问题

### 1. Skill 未加载
- 检查文件是否在 `mcp` 目录下
- 检查文件名是否以 `.py` 结尾
- 检查文件是否包含 `register_tools()` 函数

### 2. 工具不可用
- 检查 `get_tool_definitions()` 返回的工具定义
- 确保工具名称与注册的函数名一致
- 检查参数定义是否正确

### 3. 导入错误
- 确保所有依赖包已安装
- 检查导入语句是否正确
- 避免循环导入

## 下一步

1. 参考 `example.py` 创建简单的 skill
2. 参考 `file_manager.py` 创建实用的 skill
3. 测试 skill 功能
4. 集成到应用中

## 更多资源

- 查看现有 skill 的源代码
- 参考 Python 异步编程文档
- 学习 FastAPI 和 MCP 协议