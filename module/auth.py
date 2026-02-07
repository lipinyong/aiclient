import json
import logging
from pathlib import Path
from typing import Optional
from datetime import datetime, timedelta

from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware
from jose import jwt, JWTError
from passlib.context import CryptContext

logger = logging.getLogger(__name__)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

SECRET_KEY = "ai-node-mcp-secret-key-change-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24


class AuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, config_manager):
        super().__init__(app)
        self.config_manager = config_manager
    
    async def dispatch(self, request: Request, call_next):
        auth_config = self.config_manager.auth
        
        if not auth_config.get('enabled', False):
            return await call_next(request)
        
        path = request.url.path
        
        allow_paths = auth_config.get('allow_paths', [])
        deny_paths = auth_config.get('deny_paths', [])
        
        for deny_path in deny_paths:
            if path.startswith(deny_path):
                return JSONResponse(
                    status_code=403,
                    content={"error": "访问被拒绝"}
                )
        
        is_allowed = False
        for allow_path in allow_paths:
            if allow_path == '/':
                if path == '/' or path == '':
                    is_allowed = True
                    break
            elif path == allow_path or path.startswith(allow_path + '/') or path.startswith(allow_path + '?'):
                is_allowed = True
                break
        
        if is_allowed:
            return await call_next(request)
        
        token = request.cookies.get("access_token")
        if not token:
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header[7:]
        
        if not token:
            if request.url.path.startswith("/api/"):
                return JSONResponse(
                    status_code=401,
                    content={"error": "未授权访问"}
                )
            login_config = self.config_manager.login
            redirect_url = login_config.get('default_redirect', '/login')
            
            # 从X-Original-Uri头获取原始请求URI
            forwarded_uri = request.headers.get('X-Original-Uri', '')
            
            # 确定代理前缀
            proxy_prefix = ''
            if forwarded_uri and '/ai_node/' in forwarded_uri:
                # 如果有X-Original-Uri头且包含/ai_node/，则使用/ai_node作为前缀
                proxy_prefix = '/ai_node'
            
            # 构建完整的重定向路径
            redirect_path = f"{proxy_prefix}{redirect_url}?redirect={proxy_prefix}{path}"
            
            return RedirectResponse(url=redirect_path)
        
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            request.state.user = payload
        except JWTError:
            return JSONResponse(
                status_code=401,
                content={"error": "无效的认证令牌"}
            )
        
        return await call_next(request)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def load_local_users(users_file: str) -> list:
    try:
        with open(users_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('users', [])
    except Exception as e:
        logger.error(f"加载用户文件失败: {e}")
        return []


def authenticate_user(username: str, password: str, users_file: str) -> Optional[dict]:
    users = load_local_users(users_file)
    for user in users:
        if user.get('username') == username:
            if verify_password(password, user.get('password_hash', '')):
                return {
                    "username": user.get('username'),
                    "role": user.get('role', 'user'),
                    "email": user.get('email', '')
                }
    return None
