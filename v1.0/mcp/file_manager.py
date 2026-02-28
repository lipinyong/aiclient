import os
import shutil
import logging
import hashlib
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

async def file_manager_list_files(directory: str = ".", pattern: str = "*") -> Dict[str, Any]:
    """
    列出指定目录中的文件
    """
    try:
        path = Path(directory)
        
        # 如果是相对路径，转换为绝对路径
        if not path.is_absolute():
            path = Path.cwd() / path
        
        if not path.exists():
            return {
                "success": False,
                "error": f"目录不存在: {directory}"
            }
        
        if not path.is_dir():
            return {
                "success": False,
                "error": f"不是目录: {directory}"
            }
        
        # 列出文件
        files = []
        for file_path in path.glob(pattern):
            stat = file_path.stat()
            files.append({
                "name": file_path.name,
                "path": str(file_path),
                "type": "directory" if file_path.is_dir() else "file",
                "size": stat.st_size if file_path.is_file() else None,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "created": datetime.fromtimestamp(stat.st_ctime).isoformat()
            })
        
        # 按类型和名称排序
        files.sort(key=lambda x: (x["type"], x["name"]))
        
        logger.info(f"列出文件: {directory}, 模式: {pattern}, 找到 {len(files)} 个文件")
        
        return {
            "success": True,
            "directory": str(path),
            "pattern": pattern,
            "files": files,
            "count": len(files)
        }
    except Exception as e:
        logger.error(f"列出文件失败: {e}")
        return {
            "success": False,
            "error": str(e)
        }

async def file_manager_get_file_info(file_path: str) -> Dict[str, Any]:
    """
    获取文件详细信息
    """
    try:
        path = Path(file_path)
        
        # 如果是相对路径，转换为绝对路径
        if not path.is_absolute():
            path = Path.cwd() / path
        
        if not path.exists():
            return {
                "success": False,
                "error": f"文件不存在: {file_path}"
            }
        
        stat = path.stat()
        
        # 计算文件哈希（仅对文件）
        file_hash = None
        if path.is_file():
            try:
                with open(path, 'rb') as f:
                    file_hash = hashlib.md5(f.read()).hexdigest()
            except:
                file_hash = "无法计算"
        
        info = {
            "name": path.name,
            "path": str(path),
            "type": "directory" if path.is_dir() else "file",
            "size": stat.st_size if path.is_file() else None,
            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
            "accessed": datetime.fromtimestamp(stat.st_atime).isoformat(),
            "is_file": path.is_file(),
            "is_dir": path.is_dir(),
            "is_symlink": path.is_symlink(),
            "hash": file_hash
        }
        
        # 如果是文本文件，读取前几行
        if path.is_file() and path.suffix in ['.txt', '.py', '.md', '.json', '.yaml', '.yml', '.csv']:
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    preview = f.read(1000)  # 读取前1000个字符
                    info["preview"] = preview
                    info["encoding"] = "utf-8"
            except:
                try:
                    with open(path, 'r', encoding='gbk') as f:
                        preview = f.read(1000)
                        info["preview"] = preview
                        info["encoding"] = "gbk"
                except:
                    info["preview"] = "无法读取文件内容"
        
        logger.info(f"获取文件信息: {file_path}")
        
        return {
            "success": True,
            "file_info": info
        }
    except Exception as e:
        logger.error(f"获取文件信息失败: {e}")
        return {
            "success": False,
            "error": str(e)
        }

async def file_manager_search_files(directory: str = ".", search_term: str = "", 
                                   file_type: str = "all", recursive: bool = True) -> Dict[str, Any]:
    """
    搜索文件
    """
    try:
        path = Path(directory)
        
        # 如果是相对路径，转换为绝对路径
        if not path.is_absolute():
            path = Path.cwd() / path
        
        if not path.exists():
            return {
                "success": False,
                "error": f"目录不存在: {directory}"
            }
        
        if not path.is_dir():
            return {
                "success": False,
                "error": f"不是目录: {directory}"
            }
        
        # 搜索文件
        matching_files = []
        
        if recursive:
            # 递归搜索
            search_path = path.rglob("*")
        else:
            # 仅当前目录
            search_path = path.glob("*")
        
        for file_path in search_path:
            # 过滤文件类型
            if file_type == "file" and not file_path.is_file():
                continue
            elif file_type == "directory" and not file_path.is_dir():
                continue
            
            # 搜索匹配
            if search_term:
                if search_term.lower() in file_path.name.lower():
                    stat = file_path.stat()
                    matching_files.append({
                        "name": file_path.name,
                        "path": str(file_path),
                        "type": "directory" if file_path.is_dir() else "file",
                        "size": stat.st_size if file_path.is_file() else None,
                        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
                    })
            else:
                # 如果没有搜索词，返回所有文件
                stat = file_path.stat()
                matching_files.append({
                    "name": file_path.name,
                    "path": str(file_path),
                    "type": "directory" if file_path.is_dir() else "file",
                    "size": stat.st_size if file_path.is_file() else None,
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
                })
        
        # 按修改时间排序（最新的在前）
        matching_files.sort(key=lambda x: x["modified"], reverse=True)
        
        logger.info(f"搜索文件: {directory}, 关键词: {search_term}, 找到 {len(matching_files)} 个匹配文件")
        
        return {
            "success": True,
            "directory": str(path),
            "search_term": search_term,
            "file_type": file_type,
            "recursive": recursive,
            "files": matching_files,
            "count": len(matching_files)
        }
    except Exception as e:
        logger.error(f"搜索文件失败: {e}")
        return {
            "success": False,
            "error": str(e)
        }

async def file_manager_create_directory(directory: str, parents: bool = True) -> Dict[str, Any]:
    """
    创建目录
    """
    try:
        path = Path(directory)
        
        # 如果是相对路径，转换为绝对路径
        if not path.is_absolute():
            path = Path.cwd() / path
        
        # 检查目录是否已存在
        if path.exists():
            return {
                "success": False,
                "error": f"目录已存在: {directory}"
            }
        
        # 创建目录
        path.mkdir(parents=parents, exist_ok=True)
        
        logger.info(f"创建目录: {directory}")
        
        return {
            "success": True,
            "directory": str(path),
            "created": True,
            "message": f"目录创建成功: {directory}"
        }
    except Exception as e:
        logger.error(f"创建目录失败: {e}")
        return {
            "success": False,
            "error": str(e)
        }

async def file_manager_copy_file(source: str, destination: str, overwrite: bool = False) -> Dict[str, Any]:
    """
    复制文件或目录
    """
    try:
        src_path = Path(source)
        dst_path = Path(destination)
        
        # 如果是相对路径，转换为绝对路径
        if not src_path.is_absolute():
            src_path = Path.cwd() / src_path
        
        if not dst_path.is_absolute():
            dst_path = Path.cwd() / dst_path
        
        if not src_path.exists():
            return {
                "success": False,
                "error": f"源文件不存在: {source}"
            }
        
        # 检查目标是否已存在
        if dst_path.exists() and not overwrite:
            return {
                "success": False,
                "error": f"目标文件已存在: {destination} (使用 overwrite=True 覆盖)"
            }
        
        # 复制文件或目录
        if src_path.is_file():
            shutil.copy2(src_path, dst_path)
            operation = "复制文件"
        else:
            if dst_path.exists():
                shutil.rmtree(dst_path)
            shutil.copytree(src_path, dst_path)
            operation = "复制目录"
        
        logger.info(f"{operation}: {source} -> {destination}")
        
        return {
            "success": True,
            "operation": operation,
            "source": str(src_path),
            "destination": str(dst_path),
            "message": f"{operation}成功"
        }
    except Exception as e:
        logger.error(f"复制文件失败: {e}")
        return {
            "success": False,
            "error": str(e)
        }

async def file_manager_get_disk_usage() -> Dict[str, Any]:
    """
    获取磁盘使用情况
    """
    try:
        import shutil
        
        disk_info = []
        
        # 获取所有磁盘分区
        for partition in shutil.disk_usage.__code__.co_consts:
            if isinstance(partition, str) and partition.startswith('/'):
                try:
                    usage = shutil.disk_usage(partition)
                    disk_info.append({
                        "partition": partition,
                        "total_gb": round(usage.total / (1024**3), 2),
                        "used_gb": round(usage.used / (1024**3), 2),
                        "free_gb": round(usage.free / (1024**3), 2),
                        "percent_used": round((usage.used / usage.total) * 100, 2) if usage.total > 0 else 0
                    })
                except:
                    continue
        
        # 如果无法获取分区信息，获取当前目录所在磁盘
        if not disk_info:
            current_dir = Path.cwd()
            usage = shutil.disk_usage(current_dir)
            disk_info.append({
                "partition": str(current_dir),
                "total_gb": round(usage.total / (1024**3), 2),
                "used_gb": round(usage.used / (1024**3), 2),
                "free_gb": round(usage.free / (1024**3), 2),
                "percent_used": round((usage.used / usage.total) * 100, 2) if usage.total > 0 else 0
            })
        
        logger.info("获取磁盘使用情况")
        
        return {
            "success": True,
            "disk_info": disk_info,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"获取磁盘使用情况失败: {e}")
        return {
            "success": False,
            "error": str(e)
        }

def get_tool_definitions() -> List[Dict[str, Any]]:
    """
    获取工具定义，用于AI调用
    """
    return [
        {
            "type": "function",
            "function": {
                "name": "file_manager_list_files",
                "description": "列出指定目录中的文件，支持通配符模式匹配",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "directory": {
                            "type": "string",
                            "description": "目录路径，默认为当前目录"
                        },
                        "pattern": {
                            "type": "string",
                            "description": "文件匹配模式，如 *.txt, *.py，默认为 *"
                        }
                    },
                    "required": []
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "file_manager_get_file_info",
                "description": "获取文件的详细信息，包括大小、修改时间、哈希值等",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "文件路径"
                        }
                    },
                    "required": ["file_path"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "file_manager_search_files",
                "description": "搜索文件，支持按文件名、类型和递归搜索",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "directory": {
                            "type": "string",
                            "description": "搜索目录，默认为当前目录"
                        },
                        "search_term": {
                            "type": "string",
                            "description": "搜索关键词（文件名中包含）"
                        },
                        "file_type": {
                            "type": "string",
                            "description": "文件类型：all（全部）、file（仅文件）、directory（仅目录）",
                            "enum": ["all", "file", "directory"],
                            "default": "all"
                        },
                        "recursive": {
                            "type": "boolean",
                            "description": "是否递归搜索子目录，默认为True",
                            "default": True
                        }
                    },
                    "required": []
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "file_manager_create_directory",
                "description": "创建目录，支持创建多级目录",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "directory": {
                            "type": "string",
                            "description": "要创建的目录路径"
                        },
                        "parents": {
                            "type": "boolean",
                            "description": "是否创建父目录，默认为True",
                            "default": True
                        }
                    },
                    "required": ["directory"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "file_manager_copy_file",
                "description": "复制文件或目录，支持覆盖选项",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "source": {
                            "type": "string",
                            "description": "源文件或目录路径"
                        },
                        "destination": {
                            "type": "string",
                            "description": "目标文件或目录路径"
                        },
                        "overwrite": {
                            "type": "boolean",
                            "description": "是否覆盖已存在的文件，默认为False",
                            "default": False
                        }
                    },
                    "required": ["source", "destination"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "file_manager_get_disk_usage",
                "description": "获取磁盘使用情况，包括总空间、已用空间和可用空间",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            }
        }
    ]

def register_tools() -> Dict[str, Any]:
    """
    注册所有工具函数
    """
    return {
        "file_manager_list_files": file_manager_list_files,
        "file_manager_get_file_info": file_manager_get_file_info,
        "file_manager_search_files": file_manager_search_files,
        "file_manager_create_directory": file_manager_create_directory,
        "file_manager_copy_file": file_manager_copy_file,
        "file_manager_get_disk_usage": file_manager_get_disk_usage,
        "get_tool_definitions": get_tool_definitions
    }

TOOLS = register_tools()