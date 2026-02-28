"""
Shell 技能的可执行工具：仅在启用 shell 技能时由 agent 加载并调用。
支持 Windows（PowerShell / CMD）与 Linux/macOS（bash）本地命令执行。
"""

import logging
import platform
import subprocess
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

IS_WINDOWS = platform.system() == "Windows"


def run_shell(
    command: str,
    timeout: int = 60,
    cwd: Optional[str] = None,
    shell_type: str = "auto",
) -> Dict[str, Any]:
    """
    在本地执行一条 shell 命令，支持 Windows 与 Linux。
    - shell_type: "auto"（按当前系统选 PowerShell/bash）、"powershell"、"cmd"、"bash"。
    - Windows 下 "auto"/"powershell" 使用 PowerShell；"cmd" 使用 cmd.exe。
    - Linux/macOS 下使用 bash -c。
    """
    try:
        if IS_WINDOWS:
            if shell_type == "cmd":
                argv = ["cmd.exe", "/c", command]
                use_shell = False
            else:
                # PowerShell（默认或显式指定 powershell）
                argv = ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command]
                use_shell = False
        else:
            # Linux / macOS：bash -c
            argv = ["/bin/bash", "-c", command]
            use_shell = False
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=use_shell,
            cwd=cwd,
            encoding="utf-8",
            errors="replace",
        )
        return {
            "success": proc.returncode == 0,
            "return_code": proc.returncode,
            "stdout": proc.stdout or "",
            "stderr": proc.stderr or "",
            "command": command,
            "platform": platform.system(),
            "shell_type": "powershell" if (IS_WINDOWS and shell_type != "cmd") else ("cmd" if (IS_WINDOWS and shell_type == "cmd") else "bash"),
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "命令执行超时", "command": command, "platform": platform.system()}
    except FileNotFoundError as e:
        return {"success": False, "error": f"未找到解释器: {e}", "command": command, "platform": platform.system()}
    except Exception as e:
        logger.exception("Shell 执行失败")
        return {"success": False, "error": str(e), "command": command, "platform": platform.system()}


def execute_tool(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """供 agent 调用的统一入口。"""
    if name == "run_shell":
        return run_shell(
            command=arguments.get("command", ""),
            timeout=int(arguments.get("timeout", 60)),
            cwd=arguments.get("cwd"),
            shell_type=(arguments.get("shell_type") or "auto").strip() or "auto",
        )
    return {"error": f"未知工具: {name}"}


# OpenAI 工具定义，仅在启用 shell 技能时注入
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "run_shell",
            "description": "在本地执行一条 shell 命令，返回标准输出和错误。Windows 下使用 PowerShell（可指定 shell_type 为 cmd 使用 CMD），Linux/macOS 下使用 bash。用于本地系统信息采集、目录列表、进程查看或脚本执行。",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "要执行的命令。Windows 下为 PowerShell 或 CMD 语法，Linux/macOS 下为 bash 语法。"},
                    "timeout": {"type": "integer", "description": "超时秒数", "default": 60},
                    "cwd": {"type": "string", "description": "工作目录（可选）"},
                    "shell_type": {"type": "string", "description": "auto=按系统自动选择；Windows 下可用 powershell 或 cmd；Linux/macOS 下使用 bash", "default": "auto"},
                },
                "required": ["command"],
            },
        },
    },
]
