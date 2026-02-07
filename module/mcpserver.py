import os
import sys
import importlib.util
import logging
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable
from threading import Lock, Thread
import time

logger = logging.getLogger(__name__)


class MCPService:
    def __init__(self, name: str, module_path: Path):
        self.name = name
        self.module_path = module_path
        self.module = None
        self.tools: Dict[str, Callable] = {}
        self.loaded = False
        self.last_modified: float = 0  # [新增] 文件修改时间跟踪
    
    def load(self) -> bool:
        try:
            # [新增] 清除旧模块缓存，确保重新加载
            module_name = f"mcp_{self.name}"
            if module_name in sys.modules:
                del sys.modules[module_name]
            
            spec = importlib.util.spec_from_file_location(module_name, self.module_path)
            self.module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = self.module  # [新增] 注册到sys.modules
            spec.loader.exec_module(self.module)
            
            if hasattr(self.module, 'register_tools'):
                self.tools = self.module.register_tools()
            elif hasattr(self.module, 'TOOLS'):
                self.tools = self.module.TOOLS
            
            self.loaded = True
            self.last_modified = self.module_path.stat().st_mtime  # [新增] 记录修改时间
            logger.info(f"MCP服务已加载: {self.name}")
            return True
        except Exception as e:
            logger.error(f"MCP服务加载失败 {self.name}: {e}")
            return False
    
    def unload(self) -> bool:
        # [新增] 从sys.modules中移除
        module_name = f"mcp_{self.name}"
        if module_name in sys.modules:
            del sys.modules[module_name]
        
        self.module = None
        self.tools = {}
        self.loaded = False
        logger.info(f"MCP服务已卸载: {self.name}")
        return True
    
    # [新增] 检查文件是否已修改
    def is_modified(self) -> bool:
        """检查服务文件是否已被修改"""
        try:
            current_mtime = self.module_path.stat().st_mtime
            return current_mtime > self.last_modified
        except:
            return False
    
    async def call_tool(self, tool_name: str, **kwargs) -> Any:
        if not self.loaded:
            raise RuntimeError(f"MCP服务未加载: {self.name}")
        
        if tool_name not in self.tools:
            raise ValueError(f"工具不存在: {tool_name}")
        
        tool_func = self.tools[tool_name]
        if asyncio.iscoroutinefunction(tool_func):
            return await tool_func(**kwargs)
        else:
            return tool_func(**kwargs)


class MCPServerManager:
    _instance = None
    _lock = Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self.services: Dict[str, MCPService] = {}
        self.services_path = Path("service/mcp")
        self._initialized = True
        # [新增] 热加载相关属性
        self._hot_reload_enabled = False
        self._hot_reload_thread: Optional[Thread] = None
        self._hot_reload_interval = 2.0  # 检查间隔（秒）
        self._stop_hot_reload = False
    
    def set_services_path(self, path: str):
        self.services_path = Path(path)
    
    def discover_services(self) -> List[str]:
        if not self.services_path.exists():
            return []
        
        services = []
        for py_file in self.services_path.glob("*.py"):
            if py_file.name.startswith("_"):
                continue
            service_name = py_file.stem
            services.append(service_name)
        
        return services
    
    def load_service(self, name: str) -> bool:
        module_path = self.services_path / f"{name}.py"
        if not module_path.exists():
            logger.error(f"MCP服务文件不存在: {module_path}")
            return False
        
        service = MCPService(name, module_path)
        if service.load():
            self.services[name] = service
            return True
        return False
    
    def unload_service(self, name: str) -> bool:
        if name in self.services:
            self.services[name].unload()
            del self.services[name]
            return True
        return False
    
    def reload_service(self, name: str) -> bool:
        """重新加载指定服务"""
        logger.info(f"正在重新加载服务: {name}")
        self.unload_service(name)
        return self.load_service(name)
    
    def reload_all_services(self) -> Dict[str, bool]:
        """重新加载所有服务"""
        results = {}
        for name in list(self.services.keys()):
            results[name] = self.reload_service(name)
        return results
    
    def load_all_services(self) -> Dict[str, bool]:
        results = {}
        for name in self.discover_services():
            results[name] = self.load_service(name)
        return results
    
    def get_service(self, name: str) -> Optional[MCPService]:
        return self.services.get(name)
    
    def list_services(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": name,
                "loaded": service.loaded,
                "tools": list(service.tools.keys())
            }
            for name, service in self.services.items()
        ]
    
    async def call_tool(self, service_name: str, tool_name: str, **kwargs) -> Any:
        service = self.get_service(service_name)
        if not service:
            raise ValueError(f"MCP服务不存在: {service_name}")
        return await service.call_tool(tool_name, **kwargs)
    
    # ============ [新增] 热加载功能 ============
    
    def check_and_reload_modified(self) -> List[str]:
        """检查并重新加载已修改的服务，返回已重载的服务名列表"""
        reloaded = []
        for name, service in list(self.services.items()):
            if service.is_modified():
                logger.info(f"检测到服务文件变化: {name}")
                if self.reload_service(name):
                    reloaded.append(name)
        
        # 检查新增的服务
        discovered = set(self.discover_services())
        loaded = set(self.services.keys())
        new_services = discovered - loaded
        for name in new_services:
            logger.info(f"发现新服务: {name}")
            if self.load_service(name):
                reloaded.append(name)
        
        return reloaded
    
    def _hot_reload_loop(self):
        """热加载后台线程循环"""
        logger.info("MCP热加载监控已启动")
        while not self._stop_hot_reload:
            try:
                reloaded = self.check_and_reload_modified()
                if reloaded:
                    logger.info(f"已热加载服务: {', '.join(reloaded)}")
            except Exception as e:
                logger.error(f"热加载检查失败: {e}")
            
            time.sleep(self._hot_reload_interval)
        logger.info("MCP热加载监控已停止")
    
    def start_hot_reload(self, interval: float = 2.0):
        """启动热加载监控
        
        Args:
            interval: 检查文件变化的间隔时间（秒），默认2秒
        """
        if self._hot_reload_enabled:
            logger.warning("热加载已在运行中")
            return
        
        self._hot_reload_interval = interval
        self._stop_hot_reload = False
        self._hot_reload_thread = Thread(target=self._hot_reload_loop, daemon=True)
        self._hot_reload_thread.start()
        self._hot_reload_enabled = True
        logger.info(f"热加载监控已启动，检查间隔: {interval}秒")
    
    def stop_hot_reload(self):
        """停止热加载监控"""
        if not self._hot_reload_enabled:
            return
        
        self._stop_hot_reload = True
        if self._hot_reload_thread:
            self._hot_reload_thread.join(timeout=5)
        self._hot_reload_enabled = False
        logger.info("热加载监控已停止")
    
    @property
    def hot_reload_enabled(self) -> bool:
        """热加载是否已启用"""
        return self._hot_reload_enabled
    
    # ============ [新增结束] ============


mcp_manager = MCPServerManager()
