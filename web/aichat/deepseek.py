import json
import asyncio
from typing import AsyncGenerator

from fastapi import Request
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse

from module.aiagent import AIAgent, PromptPreprocessor
from module.mcpserver import mcp_manager


async def handle(request: Request, config_manager):
    if not mcp_manager.services:
        mcp_manager.load_all_services()
    
    if request.method == "GET":
        return {
            "service": "DeepSeek AI Chat",
            "version": "1.0.0",
            "endpoints": {
                "POST /api/aichat/deepseek": "发送聊天消息",
                "GET /api/aichat/deepseek": "获取服务信息"
            },
            "tools": mcp_manager.list_services()
        }
    
    try:
        body = await request.json()
    except:
        return {"error": "无效的JSON请求体"}
    
    prompt = body.get("prompt", "")
    stream = body.get("stream", True)
    preprocess = body.get("preprocess", True)
    user_info = body.get("user_info", {})
    
    # 从请求中获取用户信息，包括email
    if not user_info:
        user_info = {}
        
        # 从请求状态获取用户信息（如果认证中间件已设置）
        if hasattr(request.state, 'user'):
            user_data = request.state.user
            user_info["username"] = user_data.get("sub", "")
            user_info["email"] = user_data.get("email", "")
            user_info["role"] = user_data.get("role", "user")
        
        # 从cookie中获取email（如果有）
        if not user_info.get("email"):
            email_cookie = request.cookies.get("email")
            if email_cookie:
                user_info["email"] = email_cookie
    
    if not prompt:
        return {"error": "prompt不能为空"}
    
    ai_config = config_manager.ai
    
    agent = AIAgent(ai_config, mcp_manager=mcp_manager, user_info=user_info)
    
    if preprocess:
        preprocessor = PromptPreprocessor(config_manager.web.get('root', 'web'))
        try:
            prompt = await preprocessor.process(prompt)
        finally:
            await preprocessor.close()
    
    if stream:
        return EventSourceResponse(
            stream_response(agent, prompt),
            media_type="text/event-stream"
        )
    else:
        result = {"think": "", "say": "", "tool_calls": []}
        async for chunk in agent.chat(prompt, stream=False):
            if chunk.get("type") == "complete":
                result["think"] = chunk.get("think", "")
                result["say"] = chunk.get("say", "")
                result["tool_calls"] = chunk.get("tool_calls", [])
            elif chunk.get("type") == "error":
                return {"error": chunk.get("content")}
        return result


async def stream_response(agent: AIAgent, prompt: str) -> AsyncGenerator[dict, None]:
    async for chunk in agent.chat(prompt, stream=True):
        yield {
            "event": chunk.get("type", "message"),
            "data": json.dumps(chunk, ensure_ascii=False)
        }
