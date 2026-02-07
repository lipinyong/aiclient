"""
FastAPI应用启动文件
用于Web API服务
"""
import os
import logging
import uvicorn
from fastapi import FastAPI
from pathlib import Path

from module.config_manager import ConfigManager
from module.router import setup_routes
from module.auth import AuthMiddleware
from module.mcpserver import MCPServerManager
from module.aiagent import AIAgent

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """创建FastAPI应用实例"""
    # 确定配置文件路径
    config_path = os.environ.get('CONFIG_PATH', 'config.yaml')
    if not os.path.isabs(config_path):
        # 相对路径，基于项目根目录
        project_root = Path(__file__).parent
        config_path = project_root / config_path
    
    # 初始化配置管理器
    config_manager = ConfigManager(str(config_path))
    config = config_manager.get_config()
    
    # 创建FastAPI应用
    app = FastAPI(
        title="FastAPI AI CLI",
        description="AI-powered CLI and API service with MCP integration",
        version="1.2.0"
    )
    
    # 添加认证中间件
    if config.get('auth', {}).get('enabled', False):
        app.add_middleware(AuthMiddleware, config_manager=config_manager)
        logger.info("认证中间件已启用")
    
    # 初始化MCP服务管理器
    mcp_config = config.get('mcp', {})
    services_path = mcp_config.get('services_path', 'mcp')
    
    # 将相对路径转换为绝对路径
    if not os.path.isabs(services_path):
        project_root = Path(__file__).parent
        services_path = project_root / services_path
    
    mcp_manager = MCPServerManager()
    mcp_manager.set_services_path(str(services_path))
    
    # 加载所有MCP服务
    services = mcp_manager.discover_services()
    logger.info(f"发现MCP服务: {services}")
    
    for service_name in services:
        mcp_manager.load_service(service_name)
    
    loaded_services = mcp_manager.list_services()
    logger.info(f"已加载MCP服务: {len(loaded_services)} 个")
    
    # 初始化AI Agent（用于API调用）
    ai_config = config.get('ai', {})
    provider = ai_config.get('provider', 'deepseek')
    providers = ai_config.get('providers', {})
    provider_config = providers.get(provider, {})
    
    # 处理API密钥
    api_key = provider_config.get('api_key', '')
    if api_key.startswith('${') and api_key.endswith('}'):
        env_var = api_key[2:-1]
        api_key = os.environ.get(env_var, '')
    
    if api_key:
        ai_config['api_key'] = api_key
        agent = AIAgent(ai_config, mcp_manager)
        # 将agent和mcp_manager存储到app state中
        app.state.agent = agent
        app.state.mcp_manager = mcp_manager
    else:
        logger.warning(f"未配置AI API密钥 (provider: {provider})")
    
    # 设置路由
    setup_routes(app, config_manager)
    
    return app


app = create_app()


if __name__ == "__main__":
    # 从环境变量获取配置
    host = os.environ.get('HOST', '0.0.0.0')
    port = int(os.environ.get('PORT', 8000))
    reload = os.environ.get('RELOAD', 'false').lower() == 'true'
    
    uvicorn.run(
        "app:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info"
    )
