"""
技能创建与管理工具：仅在启用 skill-creator 技能时由 agent 加载并调用。
提供：列出/创建/删除技能、从本地路径或 GitHub 安装技能。
"""

import logging
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)


def _project_root(project_root: Optional[str]) -> Path:
    if project_root and Path(project_root).is_dir():
        return Path(project_root).resolve()
    return Path.cwd()


def _load_path_keys(project_root: Path) -> List[str]:
    config_path = project_root / "config.yaml"
    if not config_path.is_file():
        return ["skills"]
    try:
        data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        paths = data.get("skills", {}).get("paths")
        if isinstance(paths, list) and paths:
            return paths
    except Exception as e:
        logger.warning("读取 config.yaml 失败: %s", e)
    return ["skills"]


def _resolve_first_skills_dir(project_root: Path, path_keys: List[str], create: bool = False) -> Optional[Path]:
    """返回第一个可用的 skills 根目录；create=True 时若为 skills 则创建。"""
    for key in path_keys:
        if key == "skills":
            root = project_root / "skills"
        elif key == "project":
            root = project_root / ".cursor" / "skills"
        elif key == "personal":
            root = Path.home() / ".cursor" / "skills"
        else:
            p = Path(key)
            root = p if p.is_absolute() else project_root / p
        if root.exists() and root.is_dir():
            return root
        if create and key == "skills":
            root.mkdir(parents=True, exist_ok=True)
            return root
    return None


def skill_list(project_root: Optional[str] = None) -> Dict[str, Any]:
    """列出当前已发现的所有技能（名称、描述、路径）。"""
    try:
        from skills_loader import discover_skills
    except ImportError:
        return {"success": False, "error": "无法导入 skills_loader"}
    proot = _project_root(project_root)
    path_keys = _load_path_keys(proot)
    skills = discover_skills(path_keys, project_root=proot)
    return {
        "success": True,
        "project_root": str(proot),
        "path_keys": path_keys,
        "skills": [
            {"name": s["name"], "description": s.get("description", ""), "path": s.get("path", "")}
            for s in skills
        ],
        "count": len(skills),
    }


def skill_delete(name: str, project_root: Optional[str] = None) -> Dict[str, Any]:
    """按名称删除一个技能目录（不可恢复）。"""
    if not name or not name.strip():
        return {"success": False, "error": "技能名称不能为空"}
    name = name.strip()
    proot = _project_root(project_root)
    path_keys = _load_path_keys(proot)
    try:
        from skills_loader import discover_skills
    except ImportError:
        return {"success": False, "error": "无法导入 skills_loader"}
    skills = discover_skills(path_keys, project_root=proot)
    by_name = {s["name"]: s for s in skills}
    if name not in by_name:
        return {"success": False, "error": f"未找到技能: {name}", "available": list(by_name.keys())}
    path = Path(by_name[name]["path"])
    if not path.is_dir():
        return {"success": False, "error": f"路径不是目录: {path}"}
    try:
        shutil.rmtree(path)
        return {"success": True, "message": f"已删除技能: {name}", "path": str(path)}
    except Exception as e:
        logger.exception("删除技能目录失败")
        return {"success": False, "error": str(e), "path": str(path)}


def _normalize_triggers(triggers: Any) -> List[str]:
    if isinstance(triggers, list):
        return [str(t).strip() for t in triggers if str(t).strip()]
    if isinstance(triggers, str):
        return [s.strip() for s in triggers.replace("，", ",").split(",") if s.strip()]
    return []


def skill_create(
    name: str,
    description: str,
    content_md: str,
    triggers: Optional[List[str]] = None,
    project_root: Optional[str] = None,
) -> Dict[str, Any]:
    """
    创建新技能：在 skills/<name>/ 下生成 SKILL.md。
    """
    if not name or not name.strip():
        return {"success": False, "error": "技能名称不能为空"}
    name = name.strip().lower().replace(" ", "-")
    proot = _project_root(project_root)
    path_keys = _load_path_keys(proot)
    root = _resolve_first_skills_dir(proot, path_keys, create=True)
    if not root:
        return {"success": False, "error": "无法解析 skills 目录"}
    skill_dir = root / name
    if skill_dir.exists():
        return {"success": False, "error": f"技能已存在: {name}", "path": str(skill_dir)}
    trigger_list = _normalize_triggers(triggers) if triggers else []
    triggers_yaml = yaml.dump(trigger_list, allow_unicode=True, default_flow_style=True).strip()
    front = f"""---
name: {name}
description: {description}
triggers: {triggers_yaml}
---

"""
    body = (content_md or "").strip()
    full_md = front + body
    try:
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text(full_md, encoding="utf-8")
        return {
            "success": True,
            "message": f"已创建技能: {name}",
            "path": str(skill_dir),
            "skill_name": name,
            "triggers": trigger_list,
        }
    except Exception as e:
        logger.exception("创建技能失败")
        return {"success": False, "error": str(e), "skill_name": name}


def skill_install_path(
    path: str,
    skill_name: Optional[str] = None,
    project_root: Optional[str] = None,
) -> Dict[str, Any]:
    """从本地目录安装技能。"""
    src = Path(path).resolve()
    if not src.is_dir():
        return {"success": False, "error": f"路径不是目录或不存在: {path}"}
    if not (src / "SKILL.md").is_file():
        return {"success": False, "error": f"该目录下无 SKILL.md: {src}"}
    proot = _project_root(project_root)
    path_keys = _load_path_keys(proot)
    root = _resolve_first_skills_dir(proot, path_keys, create=True)
    if not root:
        return {"success": False, "error": "无法解析 skills 目录"}
    name = (skill_name or src.name).strip()
    if not name:
        name = src.name
    dest = root / name
    if dest.exists():
        return {"success": False, "error": f"目标技能已存在: {name}", "path": str(dest)}
    try:
        shutil.copytree(src, dest)
        return {"success": True, "message": f"已安装技能: {name}", "path": str(dest), "skill_name": name}
    except Exception as e:
        logger.exception("安装技能失败")
        return {"success": False, "error": str(e), "path": path}


def _normalize_github_url(repo_url: str) -> str:
    u = repo_url.strip()
    if u.startswith("https://github.com/") or u.startswith("git@github.com:"):
        return u
    if "/" in u and "github" not in u:
        return f"https://github.com/{u}.git" if not u.endswith(".git") else f"https://github.com/{u}"
    return u


def skill_install_github(
    repo_url: str,
    subdir: Optional[str] = None,
    skill_name: Optional[str] = None,
    project_root: Optional[str] = None,
) -> Dict[str, Any]:
    """从 GitHub 仓库安装技能。"""
    url = _normalize_github_url(repo_url)
    proot = _project_root(project_root)
    path_keys = _load_path_keys(proot)
    root = _resolve_first_skills_dir(proot, path_keys, create=True)
    if not root:
        return {"success": False, "error": "无法解析 skills 目录"}
    tmp = None
    try:
        tmp = tempfile.mkdtemp(prefix="skill_install_")
        clone_dest = Path(tmp) / "repo"
        result = subprocess.run(
            ["git", "clone", "--depth", "1", url, str(clone_dest)],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=tmp,
        )
        if result.returncode != 0:
            return {
                "success": False,
                "error": f"git clone 失败: {result.stderr or result.stdout}",
                "repo_url": url,
            }
        if subdir:
            src = clone_dest / subdir.strip("/").replace("\\", "/")
        else:
            src = clone_dest
        if not src.is_dir():
            return {"success": False, "error": f"子目录不存在: {subdir}", "repo_url": url}
        if not (src / "SKILL.md").is_file():
            return {"success": False, "error": f"该目录下无 SKILL.md: {src}", "repo_url": url}
        name = (skill_name or src.name).strip() or clone_dest.name
        dest = root / name
        if dest.exists():
            return {"success": False, "error": f"目标技能已存在: {name}", "path": str(dest)}
        shutil.copytree(src, dest)
        return {
            "success": True,
            "message": f"已从 GitHub 安装技能: {name}",
            "path": str(dest),
            "skill_name": name,
            "repo_url": url,
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "git clone 超时", "repo_url": url}
    except FileNotFoundError:
        return {"success": False, "error": "未找到 git 命令，请先安装 Git", "repo_url": url}
    except Exception as e:
        logger.exception("从 GitHub 安装技能失败")
        return {"success": False, "error": str(e), "repo_url": url}
    finally:
        if tmp and Path(tmp).exists():
            try:
                shutil.rmtree(tmp, ignore_errors=True)
            except Exception:
                pass


def skill_get_info(name: str, project_root: Optional[str] = None) -> Dict[str, Any]:
    """获取单个技能的 SKILL.md 全文及是否包含 tools.py。"""
    if not name or not name.strip():
        return {"success": False, "error": "技能名称不能为空"}
    name = name.strip()
    try:
        from skills_loader import discover_skills
    except ImportError:
        return {"success": False, "error": "无法导入 skills_loader"}
    proot = _project_root(project_root)
    path_keys = _load_path_keys(proot)
    skills = discover_skills(path_keys, project_root=proot)
    by_name = {s["name"]: s for s in skills}
    if name not in by_name:
        return {"success": False, "error": f"未找到技能: {name}", "available": list(by_name.keys())}
    path = Path(by_name[name]["path"])
    skill_md = path / "SKILL.md"
    tools_py = path / "tools.py"
    content = ""
    if skill_md.is_file():
        content = skill_md.read_text(encoding="utf-8")
    return {
        "success": True,
        "skill_name": name,
        "path": str(path),
        "content": content,
        "has_tools": tools_py.is_file(),
    }


def execute_tool(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """供 agent 调用的统一入口。"""
    project_root = arguments.get("project_root")
    if name == "skill_list":
        return skill_list(project_root=project_root)
    if name == "skill_delete":
        return skill_delete(name=arguments.get("name", ""), project_root=project_root)
    if name == "skill_create":
        triggers = arguments.get("triggers")
        return skill_create(
            name=arguments.get("name", ""),
            description=arguments.get("description", ""),
            content_md=arguments.get("content_md", ""),
            triggers=triggers,
            project_root=project_root,
        )
    if name == "skill_install_path":
        return skill_install_path(
            path=arguments.get("path", ""),
            skill_name=arguments.get("skill_name"),
            project_root=project_root,
        )
    if name == "skill_install_github":
        return skill_install_github(
            repo_url=arguments.get("repo_url", ""),
            subdir=arguments.get("subdir"),
            skill_name=arguments.get("skill_name"),
            project_root=project_root,
        )
    if name == "skill_get_info":
        return skill_get_info(name=arguments.get("name", ""), project_root=project_root)
    return {"error": f"未知工具: {name}"}


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "skill_list",
            "description": "列出当前已发现的所有 Agent Skills（名称、描述、路径）。用于用户要求查看、管理或列出技能时。",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_root": {"type": "string", "description": "可选。项目根目录，不传则使用当前工作目录。"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "skill_delete",
            "description": "按名称删除一个技能目录（不可恢复）。删除前请先用 skill_list 确认名称。",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "要删除的技能名称"},
                    "project_root": {"type": "string", "description": "可选。项目根目录。"},
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "skill_create",
            "description": "根据用户描述创建新技能。在项目 skills/ 下生成 <name> 目录和 SKILL.md，创建后系统即可按触发词加载该技能。",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "技能唯一标识，建议小写连字符，如 my-skill"},
                    "description": {"type": "string", "description": "一句话描述该技能的用途与触发场景"},
                    "content_md": {"type": "string", "description": "技能正文（Markdown）：使用步骤、示例、注意事项等，不含 frontmatter"},
                    "triggers": {"type": "array", "items": {"type": "string"}, "description": "触发词列表，用户输入包含任一词时自动启用该技能"},
                    "project_root": {"type": "string", "description": "可选。项目根目录。"},
                },
                "required": ["name", "description", "content_md"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "skill_install_path",
            "description": "从本地目录安装技能。将指定目录（需含 SKILL.md）复制到项目 skills/ 下。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "本地技能目录的绝对或相对路径"},
                    "skill_name": {"type": "string", "description": "安装后的技能名，不传则使用源目录名"},
                    "project_root": {"type": "string", "description": "可选。项目根目录。"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "skill_install_github",
            "description": "从 GitHub 仓库安装技能。支持 owner/repo 或完整 URL；若技能在仓库子目录，用 subdir 指定。需本机已安装 git。",
            "parameters": {
                "type": "object",
                "properties": {
                    "repo_url": {"type": "string", "description": "GitHub 仓库地址，如 https://github.com/owner/repo 或 owner/repo"},
                    "subdir": {"type": "string", "description": "仓库内技能子目录，如 skills/my-skill；不传则使用仓库根"},
                    "skill_name": {"type": "string", "description": "安装后的技能名，不传则使用 subdir 名或仓库名"},
                    "project_root": {"type": "string", "description": "可选。项目根目录。"},
                },
                "required": ["repo_url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "skill_get_info",
            "description": "获取单个技能的 SKILL.md 全文及是否包含 tools.py。用于查看或编辑前查看内容。",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "技能名称"},
                    "project_root": {"type": "string", "description": "可选。项目根目录。"},
                },
                "required": ["name"],
            },
        },
    },
]
