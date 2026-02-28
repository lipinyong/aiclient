"""
Shell 技能的可执行工具：仅在启用 shell 技能时由 agent 加载并调用。
支持 Windows（PowerShell / CMD）与 Linux/macOS（bash）本地命令执行。
生成的脚本统一写入并运行于项目根下的 data/temp 目录。
"""

import logging
import platform
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

IS_WINDOWS = platform.system() == "Windows"


def _ensure_script_temp_dir(project_root: Optional[str] = None) -> Path:
    root = Path(project_root).resolve() if project_root else Path.cwd()
    temp_dir = root / "data" / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    return temp_dir


def run_script(
    script_content: str,
    script_name: Optional[str] = None,
    timeout: int = 60,
    project_root: Optional[str] = None,
) -> Dict[str, Any]:
    """
    将脚本内容写入 data/temp 目录并执行，便于统一清理。
    - script_content: 脚本正文（PowerShell 或 bash）。
    - script_name: 可选文件名，如 myscript.ps1；不传则自动生成 script_<时间戳>.ps1/.sh。
    """
    if not (script_content or "").strip():
        return {"success": False, "error": "脚本内容为空", "script_path": None}
    temp_dir = _ensure_script_temp_dir(project_root)
    ext = ".ps1" if IS_WINDOWS else ".sh"
    if script_name:
        if not script_name.endswith((".ps1", ".sh")):
            script_name = script_name.rstrip(". ") + ext
    else:
        script_name = f"script_{int(time.time())}{ext}"
    script_path = temp_dir / script_name
    try:
        script_path.write_text(script_content.strip(), encoding="utf-8")
    except Exception as e:
        logger.exception("写入脚本失败")
        return {"success": False, "error": str(e), "script_path": str(script_path)}
    if IS_WINDOWS:
        run_cmd = f'& "{script_path}"'
        argv = ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", run_cmd]
    else:
        argv = ["/bin/bash", str(script_path)]
    try:
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(temp_dir),
            encoding="utf-8",
            errors="replace",
        )
        return {
            "success": proc.returncode == 0,
            "return_code": proc.returncode,
            "stdout": proc.stdout or "",
            "stderr": proc.stderr or "",
            "command": f"run_script({script_name})",
            "script_path": str(script_path),
            "platform": platform.system(),
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "脚本执行超时", "script_path": str(script_path), "platform": platform.system()}
    except Exception as e:
        logger.exception("脚本执行失败")
        return {"success": False, "error": str(e), "script_path": str(script_path), "platform": platform.system()}


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
    if name == "run_script":
        return run_script(
            script_content=arguments.get("script_content", ""),
            script_name=arguments.get("script_name"),
            timeout=int(arguments.get("timeout", 60)),
            project_root=arguments.get("project_root"),
        )
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
            "name": "run_script",
            "description": "将脚本内容写入项目 data/temp 目录并执行（PowerShell 或 bash）。用于需要生成并运行脚本时，禁止在当前目录或用户目录下创建脚本；脚本统一放在 data/temp 便于后期清理。",
            "parameters": {
                "type": "object",
                "properties": {
                    "script_content": {"type": "string", "description": "脚本正文。Windows 下为 PowerShell，Linux/macOS 下为 bash。"},
                    "script_name": {"type": "string", "description": "可选。文件名如 myscript.ps1；不传则自动生成 script_<时间戳>.ps1 或 .sh。"},
                    "timeout": {"type": "integer", "description": "超时秒数", "default": 60},
                    "project_root": {"type": "string", "description": "可选。项目根目录，不传则使用当前工作目录。"},
                },
                "required": ["script_content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_shell",
            "description": "在本地执行一条 shell 命令，返回标准输出和错误。Windows 下使用 PowerShell（可指定 shell_type 为 cmd 使用 CMD），Linux/macOS 下使用 bash。用于单条命令、目录列表、进程查看等；若需生成并执行脚本文件，请使用 run_script 将脚本写入 data/temp 后执行。",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "要执行的命令。Windows 下为 PowerShell 或 CMD 语法，Linux/macOS 下为 bash 语法。"},
                    "timeout": {"type": "integer", "description": "超时秒数", "default": 60},
                    "cwd": {"type": "string", "description": "工作目录（可选）；生成脚本时不得使用当前目录，应使用 run_script 写入 data/temp。"},
                    "shell_type": {"type": "string", "description": "auto=按系统自动选择；Windows 下可用 powershell 或 cmd；Linux/macOS 下使用 bash", "default": "auto"},
                },
                "required": ["command"],
            },
        },
    },
]
