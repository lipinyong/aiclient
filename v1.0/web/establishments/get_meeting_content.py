from fastapi import Request
from fastapi.responses import StreamingResponse
import httpx
import yaml
import logging
import os
from pathlib import Path
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


def load_config():
    config_path = Path(__file__).parent.parent.parent / 'etc' / 'config.yaml'
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


async def fetch_page_content(url: str) -> dict:
    """调用 browser 接口获取网页内容"""
    import platform
    import asyncio
    import shutil
    
    is_windows = platform.system() == "Windows"
    
    if is_windows:
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.support.ui import WebDriverWait
            
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
                return {"success": True, "content": inner_text}
            finally:
                driver.quit()
        except Exception as e:
            logger.error(f"Selenium 获取网页失败: {e}")
            return {"success": False, "error": str(e)}
    else:
        try:
            from playwright.async_api import async_playwright
            
            def find_chromium():
                import glob
                candidates = [
                    shutil.which("chromium"),
                    shutil.which("chromium-browser"),
                    shutil.which("google-chrome"),
                    "/usr/bin/chromium",
                    "/usr/bin/chromium-browser",
                ]
                nix_paths = glob.glob("/nix/store/*chromium*/bin/chromium")
                candidates.extend(nix_paths)
                for path in candidates:
                    if path and os.path.exists(path):
                        return path
                return None
            
            chromium_path = find_chromium()
            
            async with async_playwright() as p:
                launch_options = {"headless": True}
                if chromium_path:
                    launch_options["executable_path"] = chromium_path
                
                browser = await p.chromium.launch(**launch_options)
                page = await browser.new_page()
                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                    await page.wait_for_timeout(3000)
                except Exception:
                    pass
                inner_text = await page.evaluate("document.body.innerText")
                await browser.close()
                return {"success": True, "content": inner_text}
        except Exception as e:
            logger.error(f"Playwright 获取网页失败: {e}")
            return {"success": False, "error": str(e)}


async def handle(request: Request, config_manager):
    url = request.query_params.get("url", "")
    length = request.query_params.get("length", "500")
    title = request.query_params.get("title", "会议")
    
    if not url:
        return {
            "success": False,
            "error": "缺少必要参数 url",
            "example": "/api/establishments/get_meeting_content?url=https://example.com&length=500&title=会议标题"
        }
    
    page_result = await fetch_page_content(url)
    
    if not page_result.get("success"):
        return {
            "success": False,
            "error": f"获取网页内容失败: {page_result.get('error', '未知错误')}"
        }
    
    content = page_result.get("content", "")
    
    if not content.strip():
        return {
            "success": False,
            "error": "网页内容为空"
        }
    
    config = load_config()
    ai_config = config.get('ai', {})
    
    api_key = ai_config.get('api_key', '')
    if api_key.startswith('${') and api_key.endswith('}'):
        env_var = api_key[2:-1]
        api_key = os.environ.get(env_var, '')
    
    base_url = ai_config.get('base_url', 'https://api.deepseek.com')
    model = ai_config.get('model', 'deepseek-chat')
    
    client = AsyncOpenAI(api_key=api_key, base_url=base_url)
    
    prompt = f"""请为以下会议内容生成一个{length}字左右的摘要。

会议标题：{title}

会议内容：
{content[:8000]}

请输出结构化的会议摘要，包含：
1. 会议主题
2. 主要讨论内容
3. 关键决议或结论
4. 后续行动计划（如有）

摘要："""

    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "你是一个专业的会议记录整理助手，擅长提炼会议要点和生成结构化摘要。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=int(length) * 2
        )
        
        summary = response.choices[0].message.content
        
        return {
            "success": True,
            "title": title,
            "url": url,
            "summary": summary,
            "original_length": len(content),
            "summary_length": len(summary)
        }
        
    except Exception as e:
        logger.error(f"AI 生成摘要失败: {e}")
        return {
            "success": False,
            "error": f"AI 生成摘要失败: {str(e)}"
        }
