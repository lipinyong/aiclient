from fastapi import Request
import logging
import shutil
import os
import platform
import asyncio

logger = logging.getLogger(__name__)

IS_WINDOWS = platform.system() == "Windows"


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


def get_content_with_selenium(url: str) -> dict:
    """使用 Selenium WebDriver 获取页面内容 (Windows)"""
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        
        driver = webdriver.Chrome(options=chrome_options)
        
        try:
            driver.get(url)
            WebDriverWait(driver, 30).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            import time
            time.sleep(2)
            
            inner_text = driver.execute_script("return document.body.innerText")
            
            return {
                "success": True,
                "url": url,
                "content": inner_text
            }
        finally:
            driver.quit()
            
    except Exception as e:
        logger.error(f"Selenium 浏览器渲染失败: {e}")
        return {
            "success": False,
            "error": str(e),
            "url": url
        }


async def get_content_with_playwright(url: str) -> dict:
    """使用 Playwright 获取页面内容 (Linux/Mac)"""
    try:
        from playwright.async_api import async_playwright
        
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
        logger.error(f"Playwright 浏览器渲染失败: {e}")
        return {
            "success": False,
            "error": str(e),
            "url": url
        }


async def handle(request: Request, config_manager):
    url = request.query_params.get("url", "")
    
    if not url:
        return {
            "success": False,
            "error": "缺少必要参数 url",
            "example": "/api/common/browser?url=https://example.com"
        }
    
    if IS_WINDOWS:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, get_content_with_selenium, url)
        return result
    else:
        return await get_content_with_playwright(url)
