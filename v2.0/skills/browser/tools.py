"""
浏览器技能：在默认浏览器中打开 URL；或在后台无头浏览并读取 JS 渲染后的 document.body.innerText（纯文本）。
Windows 下优先使用 Playwright（避免 ChromeDriver 问题），不可用时再尝试 Selenium；非 Windows 使用 Playwright。
"""

import logging
import platform
import time
import webbrowser
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

IS_WINDOWS = platform.system() == "Windows"


def _normalize_url(url: str) -> str:
    if not url or not url.strip():
        return ""
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        return "https://" + url
    return url


def browser_open(url: str) -> Dict[str, Any]:
    """在系统默认浏览器中打开指定 URL。"""
    url = _normalize_url(url)
    if not url:
        return {"success": False, "error": "URL 不能为空"}
    try:
        webbrowser.open(url)
        return {"success": True, "message": "已在默认浏览器中打开", "url": url}
    except Exception as e:
        logger.exception("打开浏览器失败")
        return {"success": False, "error": str(e), "url": url}


def browser_fetch_content(
    url: str,
    wait_for: Optional[str] = None,
    timeout_ms: int = 30000,
    extra_wait_ms: int = 2000,
) -> Dict[str, Any]:
    """
    使用浏览器抓取网页，等待 JavaScript 渲染完成后通过 document.body.innerText 读取纯文本。
    Windows 下优先使用 Playwright（无需 ChromeDriver），失败时再尝试 Selenium；非 Windows 使用 Playwright。
    抓取失败后等待 2 秒再重试一次。
    """
    url = _normalize_url(url)
    if not url:
        return {"success": False, "error": "URL 不能为空", "url": ""}

    def _do_fetch() -> Dict[str, Any]:
        if IS_WINDOWS:
            out = _fetch_content_playwright(url, wait_for, timeout_ms, extra_wait_ms)
            if out.get("success"):
                return out
            logger.info("Windows 上 Playwright 失败，尝试 Selenium: %s", out.get("error", ""))
            out_sel = _fetch_content_selenium(url, timeout_ms, extra_wait_ms)
            if out_sel.get("success"):
                return out_sel
            err_play = out.get("error", "")
            err_sel = out_sel.get("error", "")
            return {
                "success": False,
                "error": f"Playwright: {err_play}；Selenium: {err_sel}。建议：pip install playwright && playwright install chromium（无需 Chrome/ChromeDriver）",
                "url": url,
            }
        return _fetch_content_playwright(url, wait_for, timeout_ms, extra_wait_ms)

    result = _do_fetch()
    if result.get("success"):
        return result
    logger.info("抓取失败，2 秒后重试一次: %s", result.get("error", ""))
    time.sleep(2)
    return _do_fetch()


def _fetch_content_selenium(
    url: str,
    timeout_ms: int,
    extra_wait_ms: int,
) -> Dict[str, Any]:
    """Windows: 使用 Selenium + Chrome headless 抓取网页；ChromeDriver 由 webdriver-manager 自动匹配。"""
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
        from selenium.webdriver.support.ui import WebDriverWait
    except ImportError:
        return {"success": False, "error": "未安装 selenium，请执行: pip install selenium", "url": url}

    service = None
    try:
        from webdriver_manager.chrome import ChromeDriverManager
        service = Service(ChromeDriverManager().install())
    except ImportError:
        pass
    except Exception as e:
        logger.warning("webdriver-manager 获取 ChromeDriver 失败，尝试默认方式: %s", e)

    try:
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1280,720")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")

        if service is not None:
            driver = webdriver.Chrome(service=service, options=chrome_options)
        else:
            driver = webdriver.Chrome(options=chrome_options)
        try:
            driver.get(url)
            WebDriverWait(driver, timeout_ms / 1000.0).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            if extra_wait_ms and extra_wait_ms > 0:
                time.sleep(extra_wait_ms / 1000.0)
            title = driver.title or ""
            inner_text = driver.execute_script("return document.body ? document.body.innerText : ''")
            if inner_text is None:
                inner_text = ""
            content = (inner_text or "").strip()
            logger.info("网页抓取成功 (Selenium)，URL: %s，内容长度: %s 字符", url, len(content))
            return {
                "success": True,
                "url": url,
                "title": title,
                "content": content,
                "content_length": len(content),
                "status": "success",
                "method": "selenium",
            }
        finally:
            driver.quit()
    except Exception as e:
        logger.debug("Selenium 网页抓取失败: %s", e)
        err_msg = str(e)
        if "chromedriver" in err_msg.lower() or "session not created" in err_msg.lower() or "driver" in err_msg.lower():
            err_msg += "（ChromeDriver 与 Chrome 版本不匹配或未安装；建议改用 Playwright）"
        return {"success": False, "error": err_msg, "url": url}


def _fetch_content_playwright(
    url: str,
    wait_for: Optional[str],
    timeout_ms: int,
    extra_wait_ms: int,
) -> Dict[str, Any]:
    """非 Windows: 使用 Playwright 抓取网页。"""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {"success": False, "error": "未安装 playwright，请执行: pip install playwright && playwright install chromium", "url": url}
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.set_viewport_size({"width": 1280, "height": 720})
                wait_until = "networkidle" if not wait_for or wait_for == "networkidle" else wait_for
                if wait_until not in ("load", "domcontentloaded", "networkidle", "commit"):
                    wait_until = "networkidle"
                page.goto(url, wait_until=wait_until, timeout=timeout_ms)
                if extra_wait_ms and extra_wait_ms > 0:
                    page.wait_for_timeout(extra_wait_ms)
                title = page.title()
                inner_text = page.evaluate("document.body ? document.body.innerText : ''")
                if inner_text is None:
                    inner_text = ""
                content = (inner_text or "").strip()
                logger.info("网页抓取成功 (Playwright)，URL: %s，内容长度: %s 字符", url, len(content))
                return {
                    "success": True,
                    "url": url,
                    "title": title,
                    "content": content,
                    "content_length": len(content),
                    "status": "success",
                    "method": "playwright",
                }
            finally:
                browser.close()
    except Exception as e:
        logger.exception("Playwright 网页抓取失败")
        return {"success": False, "error": str(e), "url": url}


def execute_tool(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    if name == "browser_open":
        return browser_open(url=arguments.get("url", ""))
    if name == "browser_fetch_content":
        return browser_fetch_content(
            url=arguments.get("url", ""),
            wait_for=arguments.get("wait_for") or arguments.get("wait_until"),
            timeout_ms=int(arguments.get("timeout_ms", 30000)),
            extra_wait_ms=int(arguments.get("extra_wait_ms", 2000)),
        )
    return {"error": f"未知工具: {name}"}


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "browser_open",
            "description": "在系统默认浏览器中打开指定 URL。用于用户要求打开链接、在浏览器中打开某地址时。",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "要打开的完整 URL；可不带协议，将自动补全为 https"},
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_fetch_content",
            "description": "在后台无头浏览器中打开 URL，等待 JavaScript 渲染后通过 document.body.innerText 读取纯文本。Windows 优先 Playwright，非 Windows 用 Playwright。用于抓取/读取网页内容时；必须调用本工具。返回后回复中只展示整理后的 content，不要做内容特点分析或其它解读。",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "要读取的完整 URL；可不带协议，将自动补全为 https"},
                    "wait_for": {"type": "string", "description": "可选。等待条件，如 networkidle（默认）或 CSS 选择器"},
                    "timeout_ms": {"type": "integer", "description": "页面加载超时毫秒数", "default": 30000},
                    "extra_wait_ms": {"type": "integer", "description": "加载完成后额外等待毫秒数，用于 SPA 渲染", "default": 2000},
                },
                "required": ["url"],
            },
        },
    },
]
