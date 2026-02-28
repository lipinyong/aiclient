import os
import httpx
import logging
import platform
import asyncio
import shutil
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

IS_WINDOWS = platform.system() == "Windows"


async def read_file(file_path: str) -> Dict[str, Any]:
    try:
        path = Path(file_path)
        
        # 如果是相对路径，默认从data目录读取
        if not path.is_absolute():
            # 检查是否在Docker环境中（通常/app是Docker容器的工作目录）
            docker_working_dir = Path("/app")
            if docker_working_dir.exists():
                # Docker环境中，使用/app/data目录
                data_dir = docker_working_dir / "data"
            else:
                # 本地开发环境，使用项目根目录下的data目录
                data_dir = Path("data")
            
            # 构建完整路径
            path = data_dir / path
        
        if not path.exists():
            return {"error": f"文件不存在: {file_path}"}
        
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        return {
            "path": str(path),
            "content": content,
            "size": path.stat().st_size,
            "modified": datetime.fromtimestamp(path.stat().st_mtime).isoformat()
        }
    except Exception as e:
        logger.error(f"读取文件失败: {e}")
        return {"error": str(e)}

async def write_file(file_path: str, content: str) -> Dict[str, Any]:
    try:
        path = Path(file_path)
        
        # 如果是相对路径，默认输出到data目录
        if not path.is_absolute():
            # 检查是否在Docker环境中（通常/app是Docker容器的工作目录）
            docker_working_dir = Path("/app")
            if docker_working_dir.exists():
                # Docker环境中，使用/app/data目录
                data_dir = docker_working_dir / "data"
            else:
                # 本地开发环境，使用项目根目录下的data目录
                data_dir = Path("data")
            
            # 确保data目录存在
            data_dir.mkdir(parents=True, exist_ok=True)
            path = data_dir / path
        else:
            # 绝对路径时，确保父目录存在
            path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return {
            "success": True,
            "path": str(path),
            "size": len(content.encode('utf-8'))
        }
    except Exception as e:
        logger.error(f"写入文件失败: {e}")
        return {"error": str(e)}

async def list_directory(dir_path: str) -> Dict[str, Any]:
    try:
        path = Path(dir_path)
        
        # 如果是相对路径，默认从data目录读取
        if not path.is_absolute():
            # 检查是否在Docker环境中（通常/app是Docker容器的工作目录）
            docker_working_dir = Path("/app")
            if docker_working_dir.exists():
                # Docker环境中，使用/app/data目录
                data_dir = docker_working_dir / "data"
            else:
                # 本地开发环境，使用项目根目录下的data目录
                data_dir = Path("data")
            
            # 构建完整路径
            path = data_dir / path
        
        if not path.exists():
            return {"error": f"目录不存在: {dir_path}"}
        if not path.is_dir():
            return {"error": f"不是目录: {dir_path}"}
        
        items = []
        for item in sorted(path.iterdir()):
            items.append({
                "name": item.name,
                "type": "directory" if item.is_dir() else "file",
                "size": item.stat().st_size if item.is_file() else None,
                "modified": datetime.fromtimestamp(item.stat().st_mtime).isoformat()
            })
        
        return {
            "path": str(path),
            "items": items,
            "count": len(items)
        }
    except Exception as e:
        logger.error(f"列出目录失败: {e}")
        return {"error": str(e)}

async def http_get(url: str, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    async with httpx.AsyncClient(timeout=120.0, verify=False, follow_redirects=True) as client:
        try:
            response = await client.get(url, headers=headers or {})
            return {
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "content": response.text
            }
        except httpx.TimeoutException as e:
            logger.error(f"HTTP GET 超时: {url}")
            return {"error": f"请求超时: {url}"}
        except httpx.ConnectError as e:
            logger.error(f"HTTP GET 连接失败: {url} - {e}")
            return {"error": f"连接失败: {str(e)}"}
        except Exception as e:
            logger.error(f"HTTP GET 失败: {url} - {e}")
            return {"error": str(e) if str(e) else f"请求失败: {type(e).__name__}"}

async def http_post(url: str, data: Optional[Dict] = None, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(url, json=data, headers=headers or {})
            return {
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "content": response.text
            }
        except Exception as e:
            logger.error(f"HTTP POST 失败: {e}")
            return {"error": str(e)}

async def get_current_time() -> Dict[str, Any]:
    now = datetime.now()
    return {
        "datetime": now.isoformat(),
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S"),
        "timestamp": now.timestamp()
    }

def find_chromium():
    """查找系统中的 Chromium 可执行文件"""
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

async def web_scrape(url: str, wait_for: Optional[str] = None, timeout: int = 30000) -> Dict[str, Any]:
    """
    使用浏览器抓取网页，等待JavaScript渲染完成

    Args:
        url: 要抓取的网页URL
        wait_for: 等待的选择器或条件，例如 "networkidle" 或 "#some-element"
        timeout: 超时时间（毫秒）

    Returns:
        包含抓取结果的字典
    """
    if IS_WINDOWS:
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
                WebDriverWait(driver, timeout / 1000).until(
                    lambda d: d.execute_script("return document.readyState") == "complete"
                )
                import time
                time.sleep(2)
                
                title = driver.title
                inner_text = driver.execute_script("return document.body.innerText")
                
                logger.info(f"网页抓取成功 (Selenium)，URL: {url}，内容长度: {len(inner_text)}字符")
                
                return {
                    "url": url,
                    "title": title,
                    "content": inner_text,
                    "status": "success",
                    "method": "selenium"
                }
            finally:
                driver.quit()
        except Exception as e:
            logger.error(f"Selenium 网页抓取失败: {e}")
            return {"error": f"网页抓取失败: {str(e)}"}
    else:
        try:
            from playwright.async_api import async_playwright
            
            chromium_path = find_chromium()
            
            async with async_playwright() as p:
                launch_options = {"headless": True}
                if chromium_path:
                    launch_options["executable_path"] = chromium_path
                
                browser = await p.chromium.launch(**launch_options)
                page = await browser.new_page()
                
                wait_until = "networkidle" if not wait_for else wait_for
                await page.goto(url, wait_until=wait_until, timeout=timeout)
                
                title = await page.title()
                inner_text = await page.evaluate("document.body.innerText")
                
                await browser.close()
                
                logger.info(f"网页抓取成功 (Playwright)，URL: {url}，内容长度: {len(inner_text)}字符")
                
                return {
                    "url": url,
                    "title": title,
                    "content": inner_text,
                    "status": "success",
                    "method": "playwright"
                }
        except Exception as e:
            logger.error(f"Playwright 网页抓取失败: {e}")
            return {"error": f"网页抓取失败: {str(e)}"}

def register_tools() -> Dict[str, Any]:
    return {
        "read_file": read_file,
        "write_file": write_file,
        "list_directory": list_directory,
        "http_get": http_get,
        "http_post": http_post,
        "web_scrape": web_scrape,
        "get_current_time": get_current_time
    }

def get_tool_definitions() -> list:
    """获取工具定义，用于AI调用"""
    return [
        {
            "type": "function",
            "function": {
                "name": "common_read_file",
                "description": "读取本地文件内容",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "文件路径"}
                    },
                    "required": ["file_path"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "common_write_file",
                "description": "写入文件内容",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "文件路径"},
                        "content": {"type": "string", "description": "文件内容"}
                    },
                    "required": ["file_path", "content"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "common_list_directory",
                "description": "列出目录内容",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "dir_path": {"type": "string", "description": "目录路径"}
                    },
                    "required": ["dir_path"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "common_http_get",
                "description": "发送HTTP GET请求",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "请求URL"},
                        "headers": {"type": "object", "description": "请求头"}
                    },
                    "required": ["url"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "common_http_post",
                "description": "发送HTTP POST请求",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "请求URL"},
                        "data": {"type": "object", "description": "请求体数据"},
                        "headers": {"type": "object", "description": "请求头"}
                    },
                    "required": ["url"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "common_web_scrape",
                "description": "使用无头浏览器抓取网页，等待JavaScript渲染完成",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "要抓取的网页URL"},
                        "wait_for": {"type": "string", "description": "等待条件，例如'networkidle'或'#some-element'"},
                        "timeout": {"type": "integer", "description": "超时时间（毫秒）"}
                    },
                    "required": ["url"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "common_get_current_time",
                "description": "获取当前时间",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            }
        }
    ]

TOOLS = register_tools()
