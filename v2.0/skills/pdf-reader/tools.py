"""
PDF Reader 技能的可执行工具：仅在启用 pdf-reader 技能时由 agent 加载并调用。

提供：
- pdf_read: 读取 PDF 并抽取文本（必要时分块存储），返回 doc_id、chunk_ids、预览
- pdf_get_chunk: 读取指定 chunk 文本
- pdf_clear_docs: 清理缓存
"""

from __future__ import annotations

import hashlib
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# 进程内缓存：doc_id -> {"path": str, "chunks": [str], "created_at": float, "meta": {...}}
_DOC_STORE: Dict[str, Dict[str, Any]] = {}


def _normalize_path(p: str) -> str:
    p = (p or "").strip()
    if (p.startswith('"') and p.endswith('"')) or (p.startswith("'") and p.endswith("'")):
        p = p[1:-1].strip()
    return p


def _make_doc_id(path: str) -> str:
    h = hashlib.sha256(path.encode("utf-8", errors="ignore")).hexdigest()[:16]
    return f"pdf_{h}"


def _chunk_text(text: str, chunk_size_chars: int) -> List[str]:
    if chunk_size_chars <= 0:
        chunk_size_chars = 8000
    chunks: List[str] = []
    for i in range(0, len(text), chunk_size_chars):
        chunks.append(text[i : i + chunk_size_chars])
    return chunks or [""]


def _extract_text_with_pypdf(pdf_path: str, page_start: int, page_end: int) -> Tuple[str, Dict[str, Any]]:
    from pypdf import PdfReader

    reader = PdfReader(pdf_path)
    total_pages = len(reader.pages)
    s = max(1, page_start)
    e = min(total_pages, page_end if page_end > 0 else total_pages)
    if s > e:
        s, e = 1, min(total_pages, 1)

    pages_text: List[str] = []
    extracted_pages = 0
    empty_pages = 0
    for idx in range(s - 1, e):
        page = reader.pages[idx]
        try:
            text = page.extract_text(extraction_mode="layout")  # pypdf 推荐 layout 提取
        except TypeError:
            text = page.extract_text()
        except Exception:
            text = None
        if text and text.strip():
            extracted_pages += 1
            pages_text.append(f"=== 第 {idx + 1} 页 ===\n{text.strip()}")
        else:
            empty_pages += 1
            pages_text.append(f"=== 第 {idx + 1} 页 ===\n")
    joined = "\n\n".join(pages_text)
    meta = {
        "total_pages": total_pages,
        "page_start": s,
        "page_end": e,
        "extracted_pages": extracted_pages,
        "empty_pages": empty_pages,
        "char_count": len(joined),
    }
    return joined, meta


def pdf_read(
    path: str,
    page_start: int = 1,
    page_end: int = 0,
    chunk_size_chars: int = 8000,
    max_preview_chars: int = 2000,
) -> Dict[str, Any]:
    """
    读取 PDF 并抽取文本；若较长则分块缓存。

    - page_start/page_end: 1-based，page_end=0 表示到最后一页
    - chunk_size_chars: 每块字符数
    - max_preview_chars: 返回 preview 最大字符数
    """
    p = _normalize_path(path)
    if not p:
        return {"success": False, "error": "path 不能为空"}

    pdf_path = Path(p)
    if not pdf_path.exists():
        return {"success": False, "error": f"文件不存在: {p}"}
    if pdf_path.suffix.lower() != ".pdf":
        return {"success": False, "error": f"不是 PDF 文件: {p}"}

    try:
        text, meta = _extract_text_with_pypdf(str(pdf_path), int(page_start), int(page_end))
        chunks = _chunk_text(text, int(chunk_size_chars))
        doc_id = _make_doc_id(str(pdf_path))
        _DOC_STORE[doc_id] = {
            "path": str(pdf_path),
            "chunks": chunks,
            "created_at": time.time(),
            "meta": meta,
        }
        preview = text[: max(0, int(max_preview_chars))]
        return {
            "success": True,
            "doc_id": doc_id,
            "path": str(pdf_path),
            "meta": meta,
            "chunk_count": len(chunks),
            "chunk_ids": [f"{doc_id}:{i}" for i in range(len(chunks))],
            "preview": preview,
            "note": "如需完整内容，请按 chunk_ids 逐个调用 pdf_get_chunk。",
        }
    except Exception as e:
        logger.exception("PDF 读取失败")
        return {"success": False, "error": str(e), "path": str(pdf_path)}


def pdf_get_chunk(chunk_id: str) -> Dict[str, Any]:
    """获取指定 chunk 文本，chunk_id 形如 pdf_xxx:0"""
    cid = (chunk_id or "").strip()
    if ":" not in cid:
        return {"success": False, "error": "chunk_id 格式错误，应为 doc_id:idx"}
    doc_id, idx_s = cid.split(":", 1)
    try:
        idx = int(idx_s)
    except Exception:
        return {"success": False, "error": "chunk_id idx 必须是整数"}
    doc = _DOC_STORE.get(doc_id)
    if not doc:
        return {"success": False, "error": f"doc_id 不存在或已清理: {doc_id}"}
    chunks: List[str] = doc.get("chunks") or []
    if idx < 0 or idx >= len(chunks):
        return {"success": False, "error": f"chunk idx 越界: {idx} / {len(chunks)}"}
    return {
        "success": True,
        "doc_id": doc_id,
        "chunk_id": cid,
        "index": idx,
        "chunk_count": len(chunks),
        "content": chunks[idx],
        "meta": doc.get("meta", {}),
        "path": doc.get("path", ""),
    }


def pdf_clear_docs(doc_id: Optional[str] = None) -> Dict[str, Any]:
    """清理缓存；doc_id 为空则清空全部。"""
    if doc_id:
        existed = doc_id in _DOC_STORE
        _DOC_STORE.pop(doc_id, None)
        return {"success": True, "cleared": doc_id, "existed": existed}
    n = len(_DOC_STORE)
    _DOC_STORE.clear()
    return {"success": True, "cleared_all": True, "count": n}


def execute_tool(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """供 agent 调用的统一入口。"""
    if name == "pdf_read":
        return pdf_read(
            path=arguments.get("path", ""),
            page_start=int(arguments.get("page_start", 1)),
            page_end=int(arguments.get("page_end", 0)),
            chunk_size_chars=int(arguments.get("chunk_size_chars", 8000)),
            max_preview_chars=int(arguments.get("max_preview_chars", 2000)),
        )
    if name == "pdf_get_chunk":
        return pdf_get_chunk(chunk_id=arguments.get("chunk_id", ""))
    if name == "pdf_clear_docs":
        return pdf_clear_docs(doc_id=arguments.get("doc_id"))
    return {"error": f"未知工具: {name}"}


# OpenAI 工具定义，仅在启用 pdf-reader 技能时注入
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "pdf_read",
            "description": "读取本地 PDF 文件并抽取文本，必要时自动分块缓存。用于在回答前拿到文档实际内容（生成摘要/问答/提取要点）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "PDF 文件路径（Windows 路径可直接传入）"},
                    "page_start": {"type": "integer", "description": "起始页（1-based）", "default": 1},
                    "page_end": {"type": "integer", "description": "结束页（1-based），0 表示到最后一页", "default": 0},
                    "chunk_size_chars": {"type": "integer", "description": "每块字符数（用于长文档分块）", "default": 8000},
                    "max_preview_chars": {"type": "integer", "description": "返回预览最大字符数", "default": 2000},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "pdf_get_chunk",
            "description": "获取 pdf_read 生成的指定 chunk 文本，chunk_id 形如 pdf_xxx:0。",
            "parameters": {
                "type": "object",
                "properties": {"chunk_id": {"type": "string", "description": "chunk_id，例如 pdf_xxx:0"}},
                "required": ["chunk_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "pdf_clear_docs",
            "description": "清理 pdf-reader 的缓存文档；doc_id 为空则清空全部。",
            "parameters": {
                "type": "object",
                "properties": {"doc_id": {"type": "string", "description": "要清理的 doc_id（可选）"}},
            },
        },
    },
]

