"""
Agent Skills 加载器

支持 Cursor 风格的 Agent Skills：
- 每个技能是一个目录，内含 SKILL.md
- SKILL.md 包含 YAML frontmatter（name, description）和 markdown 正文
- 从项目 .cursor/skills 和用户 ~/.cursor/skills 加载（不加载 ~/.cursor/skills-cursor/）
"""

import os
import re
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

import yaml

logger = logging.getLogger(__name__)

# frontmatter 正则：--- 开头到下一个 --- 或文件末尾
FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)", re.DOTALL)
# 保留的 Cursor 内置目录，不扫描
RESERVED_SKILLS_DIR = "skills-cursor"


def _resolve_skills_dir(path_key: str, project_root: Optional[Path] = None) -> Optional[Path]:
    """将配置中的路径键解析为实际目录。"""
    project_root = project_root or Path.cwd()
    if path_key == "skills":
        # 项目根下的 skills 目录（推荐部署用）
        return project_root / "skills"
    if path_key == "project":
        return project_root / ".cursor" / "skills"
    if path_key == "personal":
        home = Path.home()
        return home / ".cursor" / "skills"
    # 支持绝对或相对路径字符串
    p = Path(path_key)
    if not p.is_absolute():
        p = project_root / p
    return p if p.is_dir() else None


def _parse_skill_md(content: str) -> Tuple[Optional[Dict[str, Any]], str]:
    """解析 SKILL.md：提取 YAML frontmatter 和正文。"""
    content = content.strip()
    match = FRONTMATTER_RE.match(content)
    if not match:
        return None, content
    yaml_str, body = match.group(1).strip(), match.group(2).strip()
    try:
        meta = yaml.safe_load(yaml_str)
        if isinstance(meta, dict):
            return meta, body
    except Exception as e:
        logger.warning("Skill frontmatter YAML 解析失败: %s", e)
    return None, body


def load_skill_from_dir(skill_dir: Path) -> Optional[Dict[str, Any]]:
    """
    从技能目录加载一个技能。
    返回 {"name", "description", "content", "path"} 或 None。
    """
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        return None
    try:
        text = skill_md.read_text(encoding="utf-8")
    except Exception as e:
        logger.warning("读取 SKILL.md 失败 %s: %s", skill_md, e)
        return None
    meta, body = _parse_skill_md(text)
    if not meta:
        meta = {}
    name = meta.get("name") or skill_dir.name
    description = meta.get("description") or ""
    # 可选：触发词列表，用于按需匹配用户输入
    triggers = meta.get("triggers")
    if isinstance(triggers, str):
        triggers = [t.strip() for t in triggers.split(",") if t.strip()]
    elif not isinstance(triggers, list):
        triggers = []
    return {
        "name": name,
        "description": description,
        "triggers": triggers,
        "content": body,
        "path": str(skill_dir),
    }


def discover_skills(
    path_keys: List[str],
    project_root: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """
    根据配置的路径键发现所有 Agent Skills。
    按 path_keys 顺序扫描，同名技能后者覆盖前者。
    """
    project_root = project_root or Path.cwd()
    by_name: Dict[str, Dict[str, Any]] = {}
    for key in path_keys:
        root = _resolve_skills_dir(key, project_root)
        if not root:
            continue
        if not root.exists():
            logger.debug("Skills 目录不存在，跳过: %s", root)
            continue
        # 不要扫描 Cursor 保留目录
        for entry in root.iterdir():
            if not entry.is_dir() or entry.name == RESERVED_SKILLS_DIR:
                continue
            skill = load_skill_from_dir(entry)
            if skill:
                by_name[skill["name"]] = skill
    return list(by_name.values())


def select_skills_for_prompt(prompt: str, skills: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    根据用户输入按需选择要注入的技能。
    - 若技能有 triggers：用户输入（小写）包含任一触发词则选中。
    - 若无 triggers：用 description 和 name 中的关键词匹配（分词后任一词在输入中出现则选中）。
    """
    if not prompt or not skills:
        return []
    text = prompt.strip().lower()
    if not text:
        return []
    selected = []
    for s in skills:
        triggers = s.get("triggers") or []
        if triggers:
            for t in triggers:
                if t and str(t).lower() in text:
                    selected.append(s)
                    break
        else:
            # 无 triggers：用 description 和 name 做简单关键词匹配
            desc = (s.get("description") or "").lower()
            name = (s.get("name") or "").replace("-", " ").lower()
            for part in (desc.split() + name.split()):
                part = part.strip(".,，。:：")
                if len(part) >= 2 and part in text:
                    selected.append(s)
                    break
    return selected


def get_skills_context(skills: List[Dict[str, Any]]) -> str:
    """将技能列表格式化为注入到系统提示中的文本。"""
    if not skills:
        return ""
    parts = [
        "## Agent Skills",
        "以下技能会在相关场景下被应用，请按技能说明执行：",
        "",
    ]
    for s in skills:
        parts.append(f"### {s['name']}")
        if s.get("description"):
            parts.append(f"**描述**: {s['description']}")
        parts.append("")
        parts.append(s.get("content", "").strip())
        parts.append("")
    return "\n".join(parts)
