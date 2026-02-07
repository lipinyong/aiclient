"""SSH 连接管理器"""
import paramiko
import threading
import logging
from typing import Dict, Any, Optional
from io import StringIO

logger = logging.getLogger(__name__)


class SSHConnection:
    """单个 SSH 连接"""
    
    def __init__(self, host: str, port: int = 22, username: str = "root",
                 password: Optional[str] = None, key_file: Optional[str] = None,
                 key_content: Optional[str] = None):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.key_file = key_file
        self.key_content = key_content
        self.client: Optional[paramiko.SSHClient] = None
        self._lock = threading.Lock()
    
    def connect(self) -> bool:
        """建立连接"""
        with self._lock:
            if self.client and self.client.get_transport() and self.client.get_transport().is_active():
                return True
            
            try:
                self.client = paramiko.SSHClient()
                self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                
                connect_kwargs = {
                    "hostname": self.host,
                    "port": self.port,
                    "username": self.username,
                    "timeout": 10
                }
                
                if self.key_content:
                    key = paramiko.RSAKey.from_private_key(StringIO(self.key_content))
                    connect_kwargs["pkey"] = key
                elif self.key_file:
                    connect_kwargs["key_filename"] = self.key_file
                elif self.password:
                    connect_kwargs["password"] = self.password
                
                self.client.connect(**connect_kwargs)
                logger.info(f"SSH 连接成功: {self.username}@{self.host}:{self.port}")
                return True
            except Exception as e:
                logger.error(f"SSH 连接失败: {self.host} - {e}")
                self.client = None
                return False
    
    def execute(self, command: str, timeout: int = 30) -> Dict[str, Any]:
        """执行命令"""
        if not self.connect():
            return {"success": False, "error": "连接失败"}
        
        try:
            stdin, stdout, stderr = self.client.exec_command(command, timeout=timeout)
            output = stdout.read().decode("utf-8", errors="ignore")
            error = stderr.read().decode("utf-8", errors="ignore")
            exit_code = stdout.channel.recv_exit_status()
            
            return {
                "success": exit_code == 0,
                "output": output,
                "error": error,
                "exit_code": exit_code
            }
        except Exception as e:
            logger.error(f"SSH 命令执行失败: {command} - {e}")
            return {"success": False, "error": str(e)}
    
    def close(self):
        """关闭连接"""
        with self._lock:
            if self.client:
                try:
                    self.client.close()
                except:
                    pass
                self.client = None
    
    def is_connected(self) -> bool:
        """检查连接状态"""
        if not self.client:
            return False
        transport = self.client.get_transport()
        return transport and transport.is_active()


class SSHManager:
    """SSH 连接池管理器"""
    
    def __init__(self):
        self.connections: Dict[str, SSHConnection] = {}
        self.hosts_config: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
    
    def add_host(self, alias: str, host: str, port: int = 22, username: str = "root",
                 password: Optional[str] = None, key_file: Optional[str] = None,
                 key_content: Optional[str] = None, name: Optional[str] = None) -> bool:
        """添加主机配置"""
        with self._lock:
            self.hosts_config[alias] = {
                "host": host,
                "port": port,
                "username": username,
                "password": password,
                "key_file": key_file,
                "key_content": key_content,
                "name": name or alias
            }
            return True
    
    def remove_host(self, alias: str) -> bool:
        """移除主机"""
        with self._lock:
            if alias in self.connections:
                self.connections[alias].close()
                del self.connections[alias]
            if alias in self.hosts_config:
                del self.hosts_config[alias]
            return True
    
    def get_connection(self, alias: str) -> Optional[SSHConnection]:
        """获取连接"""
        with self._lock:
            if alias not in self.hosts_config:
                return None
            
            if alias not in self.connections:
                config = self.hosts_config[alias]
                self.connections[alias] = SSHConnection(
                    host=config["host"],
                    port=config["port"],
                    username=config["username"],
                    password=config.get("password"),
                    key_file=config.get("key_file"),
                    key_content=config.get("key_content")
                )
            
            return self.connections[alias]
    
    def execute(self, alias: str, command: str, timeout: int = 30) -> Dict[str, Any]:
        """在指定主机执行命令"""
        conn = self.get_connection(alias)
        if not conn:
            return {"success": False, "error": f"未找到主机: {alias}"}
        return conn.execute(command, timeout)
    
    def get_system_info(self, alias: str) -> Dict[str, Any]:
        """获取系统信息"""
        conn = self.get_connection(alias)
        if not conn:
            return {"error": f"未找到主机: {alias}"}
        
        info = {}
        
        hostname_result = conn.execute("hostname")
        if hostname_result["success"]:
            info["hostname"] = hostname_result["output"].strip()
        
        os_result = conn.execute("cat /etc/os-release 2>/dev/null | grep -E '^(NAME|VERSION)=' | head -2")
        if os_result["success"]:
            lines = os_result["output"].strip().split("\n")
            for line in lines:
                if line.startswith("NAME="):
                    info["os_name"] = line.split("=")[1].strip('"')
                elif line.startswith("VERSION="):
                    info["os_version"] = line.split("=")[1].strip('"')
        
        kernel_result = conn.execute("uname -r")
        if kernel_result["success"]:
            info["kernel"] = kernel_result["output"].strip()
        
        arch_result = conn.execute("uname -m")
        if arch_result["success"]:
            info["arch"] = arch_result["output"].strip()
        
        uptime_result = conn.execute("uptime -p 2>/dev/null || uptime")
        if uptime_result["success"]:
            info["uptime"] = uptime_result["output"].strip()
        
        ip_result = conn.execute("hostname -I 2>/dev/null | awk '{print $1}'")
        if ip_result["success"]:
            info["ip"] = ip_result["output"].strip()
        
        return info
    
    def get_metrics(self, alias: str) -> Dict[str, Any]:
        """获取系统指标"""
        conn = self.get_connection(alias)
        if not conn:
            return {"error": f"未找到主机: {alias}"}
        
        metrics = {}
        
        cpu_result = conn.execute("top -bn1 | grep 'Cpu(s)' | awk '{print $2}'")
        if cpu_result["success"]:
            try:
                cpu_val = cpu_result["output"].strip().replace("%", "").replace(",", ".")
                metrics["cpu_percent"] = float(cpu_val)
            except:
                metrics["cpu_percent"] = 0
        
        cpu_cores_result = conn.execute("nproc")
        if cpu_cores_result["success"]:
            try:
                metrics["cpu_cores"] = int(cpu_cores_result["output"].strip())
            except:
                metrics["cpu_cores"] = 1
        
        mem_result = conn.execute("free -b | grep Mem")
        if mem_result["success"]:
            parts = mem_result["output"].split()
            if len(parts) >= 3:
                try:
                    total = int(parts[1])
                    used = int(parts[2])
                    metrics["mem_total"] = total
                    metrics["mem_used"] = used
                    metrics["mem_percent"] = round(used / total * 100, 2) if total > 0 else 0
                except:
                    pass
        
        load_result = conn.execute("cat /proc/loadavg")
        if load_result["success"]:
            parts = load_result["output"].split()
            if len(parts) >= 3:
                try:
                    metrics["load_1"] = float(parts[0])
                    metrics["load_5"] = float(parts[1])
                    metrics["load_15"] = float(parts[2])
                except:
                    pass
        
        disk_result = conn.execute("df -B1 / | tail -1")
        if disk_result["success"]:
            parts = disk_result["output"].split()
            if len(parts) >= 5:
                try:
                    total = int(parts[1])
                    used = int(parts[2])
                    metrics["disk_total"] = total
                    metrics["disk_used"] = used
                    metrics["disk_percent"] = round(used / total * 100, 2) if total > 0 else 0
                except:
                    pass
        
        net_result = conn.execute("cat /proc/net/dev | grep -E 'eth0|ens|enp' | head -1")
        if net_result["success"] and net_result["output"].strip():
            parts = net_result["output"].split()
            if len(parts) >= 10:
                try:
                    metrics["net_rx"] = int(parts[1])
                    metrics["net_tx"] = int(parts[9])
                except:
                    pass
        
        return metrics
    
    def list_hosts(self) -> list:
        """列出所有主机"""
        hosts = []
        for alias, config in self.hosts_config.items():
            conn = self.connections.get(alias)
            hosts.append({
                "alias": alias,
                "name": config.get("name", alias),
                "host": config["host"],
                "port": config["port"],
                "username": config["username"],
                "connected": conn.is_connected() if conn else False
            })
        return hosts
    
    def close_all(self):
        """关闭所有连接"""
        with self._lock:
            for conn in self.connections.values():
                conn.close()
            self.connections.clear()


ssh_manager = SSHManager()
