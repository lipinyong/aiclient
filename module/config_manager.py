import os
import re
import yaml
import logging
from pathlib import Path
from typing import Any, Dict, Optional
from threading import Lock

logger = logging.getLogger(__name__)


def expand_env_vars(obj: Any) -> Any:
    if isinstance(obj, str):
        pattern = r'\$\{([^}]+)\}'
        def replace_env(match):
            env_var = match.group(1)
            return os.environ.get(env_var, match.group(0))
        return re.sub(pattern, replace_env, obj)
    elif isinstance(obj, dict):
        return {k: expand_env_vars(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [expand_env_vars(item) for item in obj]
    return obj


class ConfigManager:
    _instance = None
    _lock = Lock()
    
    def __new__(cls, config_path: str = "etc/config.yaml"):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, config_path: str = "etc/config.yaml"):
        if self._initialized:
            return
        
        self.config_path = Path(config_path)
        self._config: Dict[str, Any] = {}
        self._callbacks = []
        self._initialized = True
        self.reload()
    
    def reload(self) -> None:
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                raw_config = yaml.safe_load(f) or {}
            self._config = expand_env_vars(raw_config)
            logger.info(f"配置已加载: {self.config_path}")
            
            for callback in self._callbacks:
                try:
                    callback(self._config)
                except Exception as e:
                    logger.error(f"配置回调执行失败: {e}")
        except Exception as e:
            logger.error(f"配置加载失败: {e}")
            raise
    
    def get_config(self) -> Dict[str, Any]:
        return self._config.copy()
    
    def get(self, key: str, default: Any = None) -> Any:
        keys = key.split('.')
        value = self._config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
            if value is None:
                return default
        return value
    
    def register_callback(self, callback) -> None:
        self._callbacks.append(callback)
    
    def unregister_callback(self, callback) -> None:
        if callback in self._callbacks:
            self._callbacks.remove(callback)
    
    @property
    def server(self) -> Dict[str, Any]:
        return self._config.get('server', {})
    
    @property
    def web(self) -> Dict[str, Any]:
        return self._config.get('web', {})
    
    @property
    def auth(self) -> Dict[str, Any]:
        return self._config.get('auth', {})
    
    @property
    def ai(self) -> Dict[str, Any]:
        return self._config.get('ai', {})
    
    @property
    def login(self) -> Dict[str, Any]:
        return self._config.get('login', {})
    
    @property
    def lubanlou(self) -> Dict[str, Any]:
        return self._config.get('lubanlou', {})
    
    @property
    def gitlab(self) -> Dict[str, Any]:
        return self._config.get('gitlab', {})
