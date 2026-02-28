"""
SSH 技能的可执行工具：仅在启用 ssh 技能时由 agent 加载并调用。
提供 ssh_run：在指定主机上执行命令并返回结果。
"""

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def run_ssh(
    host: str,
    user: str,
    command: str,
    password: Optional[str] = None,
    port: int = 22,
    timeout: int = 30,
) -> Dict[str, Any]:
    """
    在远程主机上执行一条命令，返回 stdout、stderr 和 return_code。
    使用 paramiko，支持密码或密钥认证。
    """
    try:
        import paramiko
    except ImportError:
        return {"success": False, "error": "未安装 paramiko，请执行: pip install paramiko"}
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        connect_kw: Dict[str, Any] = {
            "hostname": host,
            "port": port,
            "username": user,
            "timeout": timeout,
        }
        if password:
            connect_kw["password"] = password
        client.connect(**connect_kw)
        stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        code = stdout.channel.recv_exit_status()
        client.close()
        return {
            "success": code == 0,
            "return_code": code,
            "stdout": out,
            "stderr": err,
            "host": host,
            "command": command,
        }
    except Exception as e:
        logger.exception("SSH 执行失败")
        return {"success": False, "error": str(e), "host": host, "command": command}


def execute_tool(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """供 agent 调用的统一入口：根据工具名执行并返回结果。"""
    if name == "ssh_run":
        return run_ssh(
            host=arguments.get("host", ""),
            user=arguments.get("user", ""),
            command=arguments.get("command", ""),
            password=arguments.get("password"),
            port=int(arguments.get("port", 22)),
            timeout=int(arguments.get("timeout", 30)),
        )
    return {"error": f"未知工具: {name}"}


# OpenAI 工具定义，仅在启用 ssh 技能时注入
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "ssh_run",
            "description": "在指定 SSH 主机上执行一条命令。用于连接远程、执行命令、采集系统信息（如 uptime、free、df、top 等）并进行分析。用户提供主机、账号、密码时，应直接调用本工具执行并依据返回结果作答。",
            "parameters": {
                "type": "object",
                "properties": {
                    "host": {"type": "string", "description": "远程主机 IP 或域名"},
                    "user": {"type": "string", "description": "登录用户名"},
                    "password": {"type": "string", "description": "登录密码（若为密钥认证可留空）"},
                    "command": {"type": "string", "description": "要在远程执行的命令，如 uptime、free -m、df -h、top -bn1 等"},
                    "port": {"type": "integer", "description": "SSH 端口", "default": 22},
                    "timeout": {"type": "integer", "description": "超时秒数", "default": 30},
                },
                "required": ["host", "user", "command"],
            },
        },
    },
]
