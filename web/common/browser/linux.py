from fastapi import Request
from playwright.async_api import async_playwright
import logging
import shutil
import os

logger = logging.getLogger(__name__)


def find_chromium():
    """查找 chromium 可执行文件路径"""
    candidates = [
        shutil.which("chromium"),
        shutil.which("chromium-browser"),
        shutil.which("google-chrome"),
        shutil.which("google-chrome-stable"),
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/usr/bin/google-chrome",
    ]
    for path in candidates:
        if path and os.path.exists(path):
            return path
    return None


async def handle(request: Request, config_manager):
    url = request.query_params.get("url", "")
    
    if not url:
        return {
            "success": False,
            "error": "缺少必要参数 url",
            "example": "/api/common/browser?url=https://example.com"
        }
    
    try:
        chromium_path = find_chromium()
        
        async with async_playwright() as p:
            launch_options = {"headless": True}
            if chromium_path:
                launch_options["executable_path"] = chromium_path
            
            browser = await p.chromium.launch(**launch_options)
            page = await browser.new_page()
            
            await page.goto(url, wait_until="networkidle", timeout=30000)
            
            inner_text = await page.evaluate("document.body.innerText")
            
            await browser.close()
            
            return {
                "success": True,
                "url": url,
                "content": inner_text
            }
    except Exception as e:
        logger.error(f"浏览器渲染失败: {e}")
        return {
            "success": False,
            "error": str(e),
            "url": url
        }
