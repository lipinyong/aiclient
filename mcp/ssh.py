"""SSH MCP 服务"""
import logging
from typing import Dict, Any
from module.ssh_manager import ssh_manager

logger = logging.getLogger(__name__)

ALLOWED_COMMANDS = [
    "ls", "cat", "head", "tail", "grep", "find", "du", "df",
    "ps", "top", "free", "uptime", "uname", "hostname", "whoami","kill",
    "date", "systemctl", "service", "docker", "docker-compose",
    "docker ps", "docker images", "docker run", "docker stop", "docker start",
    "docker rm", "docker rmi", "docker build", "docker pull", "docker-compose up",
    "netstat", "ss", "ip addr", "ifconfig", "ping", "curl", "wget",
    "apt-get", "apt", "yum", "dnf", "pacman", "zypper", "apt-cache",
    "yum list", "dnf list", "pacman -Ss", "zypper search",
    "pip", "pip3", "npm", "yarn", "cargo", "nginx"
]


def is_command_allowed(command: str) -> bool:
    """检查命令是否在白名单中"""
    cmd = command.strip().split()[0] if command.strip() else ""
    for allowed in ALLOWED_COMMANDS:
        if cmd.startswith(allowed.split()[0]):
            return True
    return False


async def ssh_list_hosts() -> Dict[str, Any]:
    """列出所有 SSH 主机"""
    return {
        "success": True,
        "hosts": ssh_manager.list_hosts()
    }


async def ssh_add_host(alias: str, host: str, port: int = 22, 
                       username: str = "root", password: str = None,
                       key_file: str = None, name: str = None) -> Dict[str, Any]:
    """添加 SSH 主机"""
    if not alias or not host:
        return {"success": False, "error": "alias 和 host 是必需的"}
    
    ssh_manager.add_host(
        alias=alias,
        host=host,
        port=port,
        username=username,
        password=password,
        key_file=key_file,
        name=name
    )
    
    return {"success": True, "message": f"主机 {alias} 添加成功"}


async def ssh_remove_host(alias: str) -> Dict[str, Any]:
    """移除 SSH 主机"""
    if not alias:
        return {"success": False, "error": "alias 是必需的"}
    
    ssh_manager.remove_host(alias)
    return {"success": True, "message": f"主机 {alias} 已移除"}


async def ssh_execute(alias: str, command: str) -> Dict[str, Any]:
    """在指定主机执行命令（仅限白名单命令）"""
    if not alias or not command:
        return {"success": False, "error": "alias 和 command 是必需的"}
    
    if not is_command_allowed(command):
        return {
            "success": False,
            "error": f"命令不在白名单中: {command}。仅支持: {', '.join(ALLOWED_COMMANDS[:10])}..."
        }
    
    result = ssh_manager.execute(alias, command)
    return result


async def ssh_get_metrics(alias: str) -> Dict[str, Any]:
    """获取主机系统指标"""
    if not alias:
        return {"success": False, "error": "alias 是必需的"}
    
    metrics = ssh_manager.get_metrics(alias)
    if "error" in metrics:
        return {"success": False, **metrics}
    
    return {"success": True, "metrics": metrics}


async def ssh_get_system_info(alias: str) -> Dict[str, Any]:
    """获取主机系统信息"""
    if not alias:
        return {"success": False, "error": "alias 是必需的"}
    
    info = ssh_manager.get_system_info(alias)
    if "error" in info:
        return {"success": False, **info}
    
    return {"success": True, "info": info}


def register_tools() -> Dict[str, Any]:
    return {
        "list_hosts": ssh_list_hosts,
        "add_host": ssh_add_host,
        "remove_host": ssh_remove_host,
        "execute": ssh_execute,
        "get_metrics": ssh_get_metrics,
        "get_system_info": ssh_get_system_info
    }


def get_tool_definitions() -> list:
    """获取工具定义"""
    return [
        {
            "type": "function",
            "function": {
                "name": "ssh_list_hosts",
                "description": "列出所有已配置的 SSH 主机",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "ssh_add_host",
                "description": "添加 SSH 主机",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "alias": {"type": "string", "description": "主机别名"},
                        "host": {"type": "string", "description": "主机地址"},
                        "port": {"type": "integer", "description": "SSH 端口，默认 22"},
                        "username": {"type": "string", "description": "用户名，默认 root"},
                        "password": {"type": "string", "description": "密码"},
                        "key_file": {"type": "string", "description": "SSH 密钥文件路径"},
                        "name": {"type": "string", "description": "显示名称"}
                    },
                    "required": ["alias", "host"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "ssh_execute",
                "description": "在指定 SSH 主机上执行白名单命令（ls, cat, df, ps, top 等系统查询命令）",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "alias": {"type": "string", "description": "主机别名"},
                        "command": {"type": "string", "description": "要执行的命令（仅支持白名单命令）"}
                    },
                    "required": ["alias", "command"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "ssh_get_metrics",
                "description": "获取主机系统指标（CPU、内存、磁盘、网络）",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "alias": {"type": "string", "description": "主机别名"}
                    },
                    "required": ["alias"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "ssh_get_system_info",
                "description": "获取主机系统信息（主机名、操作系统、内核等）",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "alias": {"type": "string", "description": "主机别名"}
                    },
                    "required": ["alias"]
                }
            }
        }
    ]


TOOLS = register_tools()
