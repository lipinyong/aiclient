import os
import importlib.util
import logging
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, Request, HTTPException, Body
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, Response
from pydantic import BaseModel
import aiofiles

from module.markdown import markdown_renderer

logger = logging.getLogger(__name__)


def setup_routes(app: FastAPI, config_manager):
    
    # 定义请求模型
    class DeepSeekChatRequest(BaseModel):
        prompt: str
        stream: Optional[bool] = True
        preprocess: Optional[bool] = True
        user_info: Optional[dict] = {}
    
    @app.get("/health")
    async def health_check():
        return {"status": "ok", "message": "AI Node MCP is running"}
    
    # 添加FastAPI默认文档路由的精确匹配
    # 这样可以确保FastAPI的默认文档路由能够正常工作
    @app.get("/docs", include_in_schema=False)
    async def custom_docs(request: Request):
        from fastapi.openapi.docs import get_swagger_ui_html
        return get_swagger_ui_html(
            openapi_url=app.openapi_url,
            title=app.title + " - Swagger UI",
            oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url,
            swagger_js_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js",
            swagger_css_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css",
        )
    
    @app.get("/redoc", include_in_schema=False)
    async def custom_redoc(request: Request):
        from fastapi.openapi.docs import get_redoc_html
        return get_redoc_html(
            openapi_url=app.openapi_url,
            title=app.title + " - ReDoc",
            redoc_js_url="https://cdn.jsdelivr.net/npm/redoc@next/bundles/redoc.standalone.js",
        )
    
    @app.get("/openapi.json", include_in_schema=False)
    async def custom_openapi(request: Request):
        return JSONResponse(app.openapi())
    
    @app.api_route("/raw/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
    async def raw_file_handler(request: Request, path: str):
        web_root = config_manager.web.get('root', 'web')
        file_path = Path(web_root) / path
        
        if request.method == "GET":
            if not file_path.exists():
                raise HTTPException(status_code=404, detail="文件不存在")
            if file_path.is_dir():
                raise HTTPException(status_code=400, detail="无法读取目录")
            
            async with aiofiles.open(file_path, 'rb') as f:
                content = await f.read()
            
            content_type = get_content_type(str(file_path))
            return Response(content=content, media_type=content_type)
        
        elif request.method == "PUT":
            file_path.parent.mkdir(parents=True, exist_ok=True)
            body = await request.body()
            async with aiofiles.open(file_path, 'wb') as f:
                await f.write(body)
            return JSONResponse({"success": True, "message": "文件已保存"})
        
        elif request.method == "DELETE":
            if not file_path.exists():
                raise HTTPException(status_code=404, detail="文件不存在")
            os.remove(file_path)
            return JSONResponse({"success": True, "message": "文件已删除"})
        
        return JSONResponse({"error": "不支持的方法"}, status_code=405)
    
    @app.get("/tree/{path:path}")
    async def tree_handler(request: Request, path: str = ""):
        web_root = config_manager.web.get('root', 'web')
        dir_path = Path(web_root) / path if path else Path(web_root)
        
        if not dir_path.exists():
            raise HTTPException(status_code=404, detail="目录不存在")
        if not dir_path.is_dir():
            raise HTTPException(status_code=400, detail="路径不是目录")
        
        items = []
        for item in sorted(dir_path.iterdir()):
            items.append({
                "name": item.name,
                "type": "directory" if item.is_dir() else "file",
                "path": str(item.relative_to(web_root)),
                "size": item.stat().st_size if item.is_file() else None
            })
        
        return JSONResponse({
            "path": path,
            "items": items
        })
    
    # 为特定API添加静态路由定义，以便它们能出现在FastAPI文档中
    # /api/aichat/deepseek - DeepSeek AI聊天接口
    @app.get("/api/aichat/deepseek", tags=["AI聊天"])
    async def api_aichat_deepseek_get(request: Request):
        """获取DeepSeek AI聊天服务信息"""
        return await api_handler(request, "aichat/deepseek")
    
    @app.post("/api/aichat/deepseek", tags=["AI聊天"])
    async def api_aichat_deepseek_post(
        request: Request,
        prompt: str = Body(..., description="聊天内容，用于输入AI模型"),
        stream: Optional[bool] = Body(True, description="是否使用流式响应"),
        preprocess: Optional[bool] = Body(True, description="是否预处理prompt"),
        user_info: Optional[dict] = Body(
            {
                "username": '',
                "cname": '',
                "email": '',
                "phone": '',
                "access_token":'',
                "external_token":''
            },
            description="""用户信息，可选，通常从localStorage获取，结构示例：
{
    username: localStorage.getItem('username') || '',
    cname: localStorage.getItem('cname') || '',
    email: localStorage.getItem('email') || '',
    phone: localStorage.getItem('phone') || '',
    access_token: localStorage.getItem('access_token') || '',
    external_token: localStorage.getItem('external_token') || '',
    domain: localStorage.getItem('domain') || ''
}"""
        )
    ):
        """发送DeepSeek AI聊天消息"""
        return await api_handler(request, "aichat/deepseek")
    
    # /api/aichat/topology - 拓扑图生成接口
    @app.get("/api/aichat/topology", tags=["AI聊天"])
    async def api_aichat_topology_get(request: Request):
        """获取拓扑图生成服务信息"""
        return await api_handler(request, "aichat/topology")
    
    @app.post("/api/aichat/topology", tags=["AI聊天"])
    async def api_aichat_topology_post(
        request: Request,
        file: Optional[Any] = Body(None, description="需求文档文件 (multipart，step1使用)"),
        content: Optional[str] = Body(None, description="需求文档内容 (json，step1使用)"),
        step1_result: Optional[dict] = Body(None, description="第一步结果 (step2使用)"),
        step: Optional[int] = Body(1, description="步骤编号: 1 或 2，默认1"),
        prompt: Optional[str] = Body(None, description="额外说明 (可选)")
    ):
        """生成系统地铁图 JSON（三维拓扑：纵向活动流、横向资源层、反馈环）"""
        return await api_handler(request, "aichat/topology")
    
    # /api/xmgl/* - 项目管理接口
    @app.get("/api/xmgl/getreport", tags=["项目管理"])
    async def api_xmgl_getreport(
        request: Request,
        daystart: str = "",
        dayend: str = ""
    ):
        """获取日期范围内日报"""
        return await api_handler(request, "xmgl/getreport")
    
    @app.get("/api/xmgl/getreportfromusername", tags=["项目管理"])
    async def api_xmgl_getreportfromusername(
        request: Request,
        username: str = "",
        daystart: str = "",
        dayend: str = ""
    ):
        """获取指定人员日报"""
        return await api_handler(request, "xmgl/getreportfromusername")
    
    @app.get("/api/xmgl/getreportfromday", tags=["项目管理"])
    async def api_xmgl_getreportfromday(
        request: Request,
        day: str = ""
    ):
        """获取指定日期日报"""
        return await api_handler(request, "xmgl/getreportfromday")
    
    # /api/establishments/* - 会议管理接口
    @app.get("/api/establishments/get_meeting_contents", tags=["会议管理"])
    async def api_establishments_get_meeting_contents(
        request: Request,
        day: str = "",
        length: str = "300"
    ):
        """获取指定日期的会议内容"""
        return await api_handler(request, "establishments/get_meeting_contents")
    
    @app.get("/api/establishments/get_meeting_content", tags=["会议管理"])
    async def api_establishments_get_meeting_content(
        request: Request,
        url: str = "",
        length: str = "300",
        title: str = ""
    ):
        """获取单个会议的内容"""
        return await api_handler(request, "establishments/get_meeting_content")
    
    @app.get("/api/establishments/get_meeting_minutes_with_ai", tags=["会议管理"])
    async def api_establishments_get_meeting_minutes_with_ai(
        request: Request,
        url: str = "",
        title: str = ""
    ):
        """使用AI生成会议纪要"""
        return await api_handler(request, "establishments/get_meeting_minutes_with_ai")
    
    @app.get("/api/establishments/get_day_meeting", tags=["会议管理"])
    async def api_establishments_get_day_meeting(
        request: Request,
        day: str = ""
    ):
        """获取指定日期的会议列表"""
        return await api_handler(request, "establishments/get_day_meeting")
    
    # /api/mail/* - 邮件发送接口
    @app.get("/api/mail/send", tags=["邮件服务"])
    async def api_mail_send_get(request: Request):
        """获取邮件发送服务信息"""
        return await api_handler(request, "mail/send")
    
    @app.post("/api/mail/send", tags=["邮件服务"])
    async def api_mail_send_post(
        request: Request,
        subject: str = Body(..., description="邮件主题"),
        content: str = Body(..., description="邮件内容（支持 Markdown 格式）"),
        to: str = Body(..., description="收件人邮箱，可以是单个邮箱或逗号分隔的邮箱列表"),
        cc: Optional[str] = Body(None, description="抄送邮箱，可以是单个邮箱或逗号分隔的邮箱列表（可选）"),
        bcc: Optional[str] = Body(None, description="密送邮箱，可以是单个邮箱或逗号分隔的邮箱列表（可选）"),
        content_type: Optional[str] = Body("markdown", description="内容类型：markdown、html 或 plain（可选，默认 markdown）"),
        send_separately: Optional[bool] = Body(False, description="是否单独发送给每个收件人（可选，默认 false）")
    ):
        """发送邮件"""
        return await api_handler(request, "mail/send")
    
    # 通用API路由，处理所有其他API请求
    @app.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
    async def api_handler(request: Request, path: str):
        web_root = config_manager.web.get('root', 'web')
        py_path = Path(web_root) / f"{path}.py"
        
        if not py_path.exists():
            return JSONResponse(
                {"error": "API不存在", "path": path},
                status_code=404
            )
        
        try:
            result = await execute_py_module(py_path, request, config_manager)
            if isinstance(result, Response):
                return result
            return JSONResponse(result)
        except Exception as e:
            logger.error(f"API执行错误: {path} - {e}")
            return JSONResponse(
                {"error": str(e)},
                status_code=500
            )
    
    # 定义通用页面路由
    @app.get("/{path:path}")
    async def page_handler(request: Request, path: str = ""):
        web_root = config_manager.web.get('root', 'web')
        default_files = config_manager.web.get('default_files', ['index.html', 'index.md'])
        
        if not path:
            path = ""
        
        target_path = Path(web_root) / path
        
        if target_path.is_dir():
            for default_file in default_files:
                default_path = target_path / default_file
                if default_path.exists():
                    target_path = default_path
                    break
            else:
                raise HTTPException(status_code=404, detail="未找到默认页面")
        
        if not target_path.exists():
            raise HTTPException(status_code=404, detail="页面不存在")
        
        suffix = target_path.suffix.lower()
        
        if suffix == '.py':
            try:
                result = await execute_py_module(target_path, request, config_manager)
                if isinstance(result, Response):
                    return result
                return JSONResponse(result)
            except Exception as e:
                logger.error(f"执行Python模块错误: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        if suffix == '.md':
            async with aiofiles.open(target_path, 'r', encoding='utf-8') as f:
                content = await f.read()
            html = markdown_renderer.render(content, str(target_path.parent))
            return HTMLResponse(content=html, headers={"Cache-Control": "no-cache"})
        
        if suffix in ['.html', '.htm']:
            async with aiofiles.open(target_path, 'r', encoding='utf-8') as f:
                content = await f.read()
            return HTMLResponse(content=content, headers={"Cache-Control": "no-cache"})
        
        content_type = get_content_type(str(target_path))
        return FileResponse(target_path, media_type=content_type)


async def execute_py_module(py_path: Path, request: Request, config_manager) -> Any:
    spec = importlib.util.spec_from_file_location("dynamic_module", py_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    
    if hasattr(module, 'handle'):
        handler = module.handle
        if callable(handler):
            import asyncio
            if asyncio.iscoroutinefunction(handler):
                return await handler(request, config_manager)
            else:
                return handler(request, config_manager)
    
    if hasattr(module, 'main'):
        main_func = module.main
        if callable(main_func):
            import asyncio
            if asyncio.iscoroutinefunction(main_func):
                return await main_func(request, config_manager)
            else:
                return main_func(request, config_manager)
    
    raise HTTPException(status_code=500, detail="模块缺少handle或main函数")


def get_content_type(file_path: str) -> str:
    extension_map = {
        '.html': 'text/html',
        '.htm': 'text/html',
        '.css': 'text/css',
        '.js': 'application/javascript',
        '.json': 'application/json',
        '.xml': 'application/xml',
        '.txt': 'text/plain',
        '.md': 'text/markdown',
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.gif': 'image/gif',
        '.svg': 'image/svg+xml',
        '.ico': 'image/x-icon',
        '.pdf': 'application/pdf',
        '.zip': 'application/zip',
        '.py': 'text/x-python',
    }
    
    suffix = Path(file_path).suffix.lower()
    return extension_map.get(suffix, 'application/octet-stream')
