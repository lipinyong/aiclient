"""
图片 OCR 技能的可执行工具：仅在启用 image-ocr 技能时由 agent 加载并调用。

提供 ocr_run：对本地图片进行 OCR 文字识别，支持中英文等。
依赖：easyocr（pip install easyocr），首次调用会下载模型。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# 懒加载 Reader，避免 import 时下载模型
_READER: Any = None
_DEFAULT_LANGS = ["ch_sim", "en"]


def _normalize_path(p: str) -> str:
    p = (p or "").strip()
    if (p.startswith('"') and p.endswith('"')) or (p.startswith("'") and p.endswith("'")):
        p = p[1:-1].strip()
    return p


def _get_reader(languages: Optional[List[str]] = None):
    global _READER
    if _READER is None:
        try:
            import easyocr
            langs = list(languages or _DEFAULT_LANGS)
            _READER = easyocr.Reader(langs, gpu=False, verbose=False)
        except Exception as e:
            logger.exception("EasyOCR 初始化失败")
            raise RuntimeError(f"OCR 引擎初始化失败，请确保已安装: pip install easyocr。错误: {e}")
    return _READER


def ocr_run(
    path: str,
    languages: Optional[List[str]] = None,
    detail: int = 1,
) -> Dict[str, Any]:
    """
    对本地图片执行 OCR，返回识别出的文字。

    - path: 图片文件路径（支持 png、jpg、jpeg、bmp 等）
    - languages: 语言列表，如 ["ch_sim", "en"]，默认中英
    - detail: 1 返回每行/块文字及坐标与置信度，0 仅返回全文
    """
    p = _normalize_path(path)
    if not p:
        return {"success": False, "error": "path 不能为空"}

    img_path = Path(p)
    if not img_path.exists():
        return {"success": False, "error": f"文件不存在: {p}"}

    suffix = img_path.suffix.lower()
    if suffix not in (".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tiff", ".tif"):
        return {"success": False, "error": f"不支持的图片格式: {suffix}"}

    try:
        reader = _get_reader(languages)
        result = reader.readtext(str(img_path), detail=detail)
        if detail == 0:
            # 仅文本列表，拼接成一段
            text = "\n".join((r if isinstance(r, str) else str(r)) for r in result)
            return {
                "success": True,
                "path": str(img_path),
                "text": text,
                "detail": None,
            }
        # detail=1: list of (bbox, text, confidence)
        lines: List[Dict[str, Any]] = []
        all_text: List[str] = []
        for item in result:
            bbox, text, conf = item[0], item[1], item[2]
            lines.append({"text": text, "confidence": round(float(conf), 4), "bbox": bbox})
            all_text.append(text)
        full_text = "\n".join(all_text)
        return {
            "success": True,
            "path": str(img_path),
            "text": full_text,
            "details": lines,
        }
    except Exception as e:
        logger.exception("OCR 执行失败")
        return {"success": False, "error": str(e), "path": str(img_path)}


def execute_tool(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """供 agent 调用的统一入口。"""
    if name == "ocr_run":
        langs = arguments.get("languages")
        if isinstance(langs, str):
            langs = [s.strip() for s in langs.split(",") if s.strip()]
        elif not isinstance(langs, list):
            langs = None
        return ocr_run(
            path=arguments.get("path", ""),
            languages=langs,
            detail=int(arguments.get("detail", 1)),
        )
    return {"error": f"未知工具: {name}"}


# OpenAI 工具定义，仅在启用 image-ocr 技能时注入
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "ocr_run",
            "description": "对本地图片进行 OCR 文字识别，返回图中文字（支持中英文等）。用于用户提供图片路径并要求识别/提取图中文字时。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "图片文件路径（支持 png、jpg、jpeg、bmp 等，Windows 路径可直接传入）"},
                    "languages": {"type": "array", "items": {"type": "string"}, "description": "语言列表，如 ['ch_sim','en'] 表示简体中文+英文；不传默认中英"},
                    "detail": {"type": "integer", "description": "1=返回每块文字及置信度，0=仅返回全文", "default": 1},
                },
                "required": ["path"],
            },
        },
    },
]
