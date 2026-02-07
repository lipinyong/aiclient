import httpx
import logging
import yaml
import os
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


import urllib.parse


def filter_issue_data(issue: Dict[str, Any]) -> Dict[str, Any]:
    """过滤issue数据，只保留关键字段"""
    return {
        "id": issue.get("id"),
        "title": issue.get("title"),
        "description": issue.get("description", "")[:2000] if issue.get("description") else "",  # 限制描述长度
        "state": issue.get("state"),
        "created_at": issue.get("created_at"),
        "updated_at": issue.get("updated_at"),
        "closed_at": issue.get("closed_at"),
        "author": issue.get("author", {}).get("name") if issue.get("author") else None,
        "labels": [label.get("name") if isinstance(label, dict) else label for label in issue.get("labels", [])],
        "assignees": [assignee.get("name") for assignee in issue.get("assignees", []) if assignee.get("name")],
        "milestone": issue.get("milestone", {}).get("title") if issue.get("milestone") else None
    }


def filter_note_data(note: Dict[str, Any]) -> Dict[str, Any]:
    """过滤评论数据，只保留关键字段"""
    return {
        "id": note.get("id"),
        "body": note.get("body", "")[:1000] if note.get("body") else "",  # 限制评论长度
        "author": note.get("author", {}).get("name") if note.get("author") else None,
        "created_at": note.get("created_at"),
        "updated_at": note.get("updated_at")
    }


def filter_commit_data(commit: Dict[str, Any]) -> Dict[str, Any]:
    """过滤提交记录数据，只保留关键字段"""
    return {
        "id": commit.get("id"),
        "title": commit.get("title"),
        "message": commit.get("message", "")[:500] if commit.get("message") else "",  # 限制消息长度
        "author_name": commit.get("author_name"),
        "created_at": commit.get("created_at"),
        "committed_date": commit.get("committed_date"),
        "web_url": commit.get("web_url")
    }


def filter_project_data(project: Dict[str, Any]) -> Dict[str, Any]:
    """过滤项目数据，只保留关键字段"""
    return {
        "id": project.get("id"),
        "name": project.get("name"),
        "description": project.get("description", "")[:500] if project.get("description") else "",  # 限制描述长度
        "web_url": project.get("web_url"),
        "created_at": project.get("created_at"),
        "last_activity_at": project.get("last_activity_at")
    }

class GitLabClient:
    def __init__(self, server: str, port: int = 80, token: str = ""):
        self.base_url = f"http://{server}:{port}/api/v4"
        self.token = token
        self.headers = {"PRIVATE-TOKEN": token} if token else {}
    
    def _encode_project_path(self, project_path: Any) -> str:
        """编码项目路径，用于GitLab API"""
        # 如果是数字ID，直接返回字符串形式
        if isinstance(project_path, (int, float)):
            return str(project_path)
        # 如果是字符串，进行URL编码
        if isinstance(project_path, str):
            return urllib.parse.quote(project_path, safe="")
        # 其他类型，转换为字符串
        return str(project_path)
    
    async def list_projects(self, per_page: int = 20) -> List[Dict[str, Any]]:
        url = f"{self.base_url}/projects"
        params = {"per_page": per_page}
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(url, headers=self.headers, params=params)
                response.raise_for_status()
                return response.json()
            except Exception as e:
                logger.error(f"获取项目列表失败: {e}")
                return []
    
    async def get_project(self, project_id: str) -> Dict[str, Any]:
        encoded_project_id = self._encode_project_path(project_id)
        url = f"{self.base_url}/projects/{encoded_project_id}"
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(url, headers=self.headers)
                response.raise_for_status()
                return response.json()
            except Exception as e:
                logger.error(f"获取项目详情失败: {e}")
                return {"error": str(e)}
    
    async def list_branches(self, project_id: str) -> List[Dict[str, Any]]:
        encoded_project_id = self._encode_project_path(project_id)
        url = f"{self.base_url}/projects/{encoded_project_id}/repository/branches"
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(url, headers=self.headers)
                response.raise_for_status()
                return response.json()
            except Exception as e:
                logger.error(f"获取分支列表失败: {e}")
                return []
    
    async def list_commits(self, project_id: str, ref_name: str = "main", per_page: int = 20, since: str = None, until: str = None) -> List[Dict[str, Any]]:
        """获取提交列表"""
        encoded_project_id = self._encode_project_path(project_id)
        url = f"{self.base_url}/projects/{encoded_project_id}/repository/commits"
        params = {"ref_name": ref_name, "per_page": per_page}
        
        # 添加日期过滤参数
        if since:
            params["since"] = since
        if until:
            params["until"] = until
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(url, headers=self.headers, params=params)
                response.raise_for_status()
                return response.json()
            except Exception as e:
                logger.error(f"获取提交列表失败: {e}")
                return []
    
    async def list_issues(self, project_id: str, per_page: int = 20, state: str = "all", created_after: str = None, created_before: str = None, updated_after: str = None) -> List[Dict[str, Any]]:
        """获取项目的issues列表，支持分页获取所有结果"""
        encoded_project_id = self._encode_project_path(project_id)
        url = f"{self.base_url}/projects/{encoded_project_id}/issues"
        params = {"per_page": per_page, "state": state}
        
        # 添加日期过滤参数
        if created_after:
            params["created_after"] = created_after
        if created_before:
            params["created_before"] = created_before
        if updated_after:
            params["updated_after"] = updated_after
        
        all_issues = []
        page = 1
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                while True:
                    # 添加页码参数
                    params["page"] = page
                    response = await client.get(url, headers=self.headers, params=params)
                    response.raise_for_status()
                    
                    issues = response.json()
                    if not issues:
                        break
                    
                    all_issues.extend(issues)
                    page += 1
                    
                    # 防止请求过多
                    if page > 100:
                        break
                
                return all_issues
            except Exception as e:
                logger.error(f"获取issues列表失败: {e}")
                return []
    
    async def get_issue(self, project_id: str, issue_id: int) -> Dict[str, Any]:
        """获取单个issue详情"""
        encoded_project_id = self._encode_project_path(project_id)
        url = f"{self.base_url}/projects/{encoded_project_id}/issues/{issue_id}"
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(url, headers=self.headers)
                response.raise_for_status()
                return response.json()
            except Exception as e:
                logger.error(f"获取issue详情失败: {e}")
                return {"error": str(e)}
    
    async def list_issue_notes(self, project_id: str, issue_id: int, per_page: int = 20) -> List[Dict[str, Any]]:
        """获取issue的评论(notes)列表"""
        encoded_project_id = self._encode_project_path(project_id)
        url = f"{self.base_url}/projects/{encoded_project_id}/issues/{issue_id}/notes"
        params = {"per_page": per_page}
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(url, headers=self.headers, params=params)
                response.raise_for_status()
                return response.json()
            except Exception as e:
                logger.error(f"获取issue评论失败: {e}")
                return []
    
    async def list_merge_request_notes(self, project_id: str, mr_id: int, per_page: int = 20) -> List[Dict[str, Any]]:
        """获取合并请求的评论(notes)列表"""
        encoded_project_id = self._encode_project_path(project_id)
        url = f"{self.base_url}/projects/{encoded_project_id}/merge_requests/{mr_id}/notes"
        params = {"per_page": per_page}
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(url, headers=self.headers, params=params)
                response.raise_for_status()
                return response.json()
            except Exception as e:
                logger.error(f"获取合并请求评论失败: {e}")
                return []


# 配置管理
class GitConfig:
    def __init__(self, config_file: str = "git.yaml"):
        self.config_file = config_file
        self.config = self.load_config()
    
    def load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        try:
            # 从git.yaml加载配置
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            config_path = os.path.join(base_dir, "git.yaml")
            
            if not os.path.exists(config_path):
                logger.warning(f"git.yaml 文件不存在，请从 git.yaml.example 复制并配置")
                return {}
            
            with open(config_path, "r", encoding="utf-8") as f:
                config_content = f.read()
                # 替换环境变量（类似 config.yaml 的处理方式）
                for key, value in os.environ.items():
                    config_content = config_content.replace(f'${{{key}}}', value)
                return yaml.safe_load(config_content)
        except Exception as e:
            logger.error(f"加载git配置失败: {e}")
            return {}
    
    def get_gitlab_config(self) -> Dict[str, Any]:
        """获取GitLab服务器配置"""
        return self.config.get("gitlab", {"server": "gitlab.example.com", "port": 80})
    
    def get_repository_config(self, repo_name: str) -> Dict[str, Any]:
        """获取指定仓库的配置"""
        repositories = self.config.get("repositories", {})
        return repositories.get(repo_name, {})
    
    def get_all_repositories(self) -> Dict[str, Any]:
        """获取所有仓库配置"""
        return self.config.get("repositories", {})
    
    def search_repositories_by_description(self, query: str) -> List[Dict[str, Any]]:
        """根据描述搜索仓库"""
        repositories = self.get_all_repositories()
        matching_repos = []
        
        for repo_name, repo_config in repositories.items():
            description = repo_config.get("description", "").lower()
            if query.lower() in description:
                matching_repos.append({
                    "name": repo_name,
                    "description": repo_config.get("description", ""),
                    "project_id": repo_config.get("project_id", ""),
                    "project_name": repo_config.get("project_name", "")
                })
        
        return matching_repos


# 全局配置实例
_config: Optional[GitConfig] = None

# 全局客户端缓存
_clients: Dict[str, GitLabClient] = {}


def init_config(config_file: str = "git.yaml"):
    """初始化配置"""
    global _config
    _config = GitConfig(config_file)


def get_client(repo_name: str) -> Optional[GitLabClient]:
    """获取指定仓库的客户端"""
    global _config, _clients
    
    if not _config:
        init_config()
    
    # 处理完整仓库路径（如 GvSun/lubanlou）
    simple_repo_name = _get_simple_repo_name(repo_name)
    
    # 检查是否有缓存（用简化名称）
    if simple_repo_name in _clients:
        return _clients[simple_repo_name]
    
    # 尝试用简化名称获取配置
    repo_config = _config.get_repository_config(simple_repo_name)
    if not repo_config:
        logger.error(f"仓库配置不存在: {simple_repo_name}")
        return None
    
    # 获取GitLab服务器配置
    gitlab_config = _config.get_gitlab_config()
    
    # 创建客户端
    client = GitLabClient(
        server=gitlab_config.get("server", "gitlab.example.com"),
        port=gitlab_config.get("port", 80),
        token=repo_config.get("token", "")
    )
    
    # 缓存客户端（用简化名称）
    _clients[simple_repo_name] = client
    
    return client


def _get_simple_repo_name(repo_name: str) -> str:
    """获取简化的仓库名称"""
    if '/' in repo_name:
        return repo_name.split('/')[-1]
    return repo_name

async def list_issues(repo_name: str, per_page: int = 20, state: str = "all", created_after: str = None, created_before: str = None, updated_after: str = None) -> List[Dict[str, Any]]:
    """获取指定仓库的issues列表"""
    client = get_client(repo_name)
    if not client:
        return {"error": "GitLab客户端未初始化"}
    
    # 获取简化的仓库名称
    simple_repo_name = _get_simple_repo_name(repo_name)
    
    # 获取仓库ID
    repo_config = _config.get_repository_config(simple_repo_name)
    project_id = repo_config.get("project_id", "")
    
    if not project_id:
        return {"error": "仓库ID未配置"}
    
    issues = await client.list_issues(project_id, per_page, state, created_after, created_before, updated_after)
    # 过滤数据，只保留关键字段
    return [filter_issue_data(issue) for issue in issues]


async def get_issue(repo_name: str, issue_id: int) -> Dict[str, Any]:
    """获取指定仓库的单个issue详情"""
    client = get_client(repo_name)
    if not client:
        return {"error": "GitLab客户端未初始化"}
    
    # 获取简化的仓库名称
    simple_repo_name = _get_simple_repo_name(repo_name)
    
    # 获取仓库ID
    repo_config = _config.get_repository_config(simple_repo_name)
    project_id = repo_config.get("project_id", "")
    
    if not project_id:
        return {"error": "仓库ID未配置"}
    
    issue = await client.get_issue(project_id, issue_id)
    # 过滤数据，只保留关键字段
    if isinstance(issue, dict) and "error" not in issue:
        return filter_issue_data(issue)
    return issue


async def list_issue_notes(repo_name: str, issue_id: int, per_page: int = 20) -> List[Dict[str, Any]]:
    """获取指定仓库的issue评论列表"""
    client = get_client(repo_name)
    if not client:
        return {"error": "GitLab客户端未初始化"}
    
    # 获取简化的仓库名称
    simple_repo_name = _get_simple_repo_name(repo_name)
    
    # 获取仓库ID
    repo_config = _config.get_repository_config(simple_repo_name)
    project_id = repo_config.get("project_id", "")
    
    if not project_id:
        return {"error": "仓库ID未配置"}
    
    notes = await client.list_issue_notes(project_id, issue_id, per_page)
    # 过滤数据，只保留关键字段
    return [filter_note_data(note) for note in notes]


async def search_content(repo_name: str, query: str, per_page: int = 20) -> Dict[str, Any]:
    """搜索仓库内容（issues、notes和提交记录）"""
    client = get_client(repo_name)
    if not client:
        return {"error": "GitLab客户端未初始化"}
    
    # 获取简化的仓库名称
    simple_repo_name = _get_simple_repo_name(repo_name)
    
    # 获取仓库ID
    repo_config = _config.get_repository_config(simple_repo_name)
    project_id = repo_config.get("project_id", "")
    
    if not project_id:
        return {"error": "仓库ID未配置"}
    
    # 搜索issues
    issues = await client.list_issues(project_id, per_page=per_page)
    
    # 过滤包含查询内容的issues
    matching_issues = []
    for issue in issues:
        if query.lower() in (issue.get("title", "").lower() + " " + issue.get("description", "").lower()):
            matching_issues.append(issue)
    
    # 对于匹配的issues，获取其notes
    result = {
        "issues": [filter_issue_data(issue) for issue in matching_issues],
        "notes": [],
        "commits": []
    }
    
    for issue in matching_issues[:5]:  # 只处理前5个匹配的issues
        issue_id = issue.get("id")
        if issue_id:
            notes = await client.list_issue_notes(project_id, issue_id, per_page=per_page)
            # 过滤包含查询内容的notes
            matching_notes = [note for note in notes if query.lower() in note.get("body", "").lower()]
            # 应用note过滤
            result["notes"].extend([filter_note_data(note) for note in matching_notes])
    
    # 搜索提交记录
    commits = await client.list_commits(project_id, per_page=per_page)
    # 过滤包含查询内容的提交记录
    matching_commits = []
    for commit in commits:
        commit_message = commit.get("message", "").lower()
        commit_title = commit.get("title", "").lower()
        if query.lower() in commit_message or query.lower() in commit_title:
            matching_commits.append(commit)
    # 应用commit过滤
    result["commits"] = [filter_commit_data(commit) for commit in matching_commits]
    
    return result


async def list_projects(per_page: int = 20) -> List[Dict[str, Any]]:
    """获取项目列表（使用默认配置）"""
    # 使用第一个仓库的配置
    repo_names = list(_config.get_all_repositories().keys()) if _config else []
    if not repo_names:
        return {"error": "未配置仓库"}
    
    client = get_client(repo_names[0])
    if not client:
        return {"error": "GitLab客户端未初始化"}
    
    projects = await client.list_projects(per_page)
    # 过滤数据，只保留关键字段
    return [filter_project_data(project) for project in projects]


async def get_project(project_id: str) -> Dict[str, Any]:
    """获取项目详情（使用默认配置）"""
    # 使用第一个仓库的配置
    repo_names = list(_config.get_all_repositories().keys()) if _config else []
    if not repo_names:
        return {"error": "未配置仓库"}
    
    client = get_client(repo_names[0])
    if not client:
        return {"error": "GitLab客户端未初始化"}
    
    project = await client.get_project(project_id)
    # 过滤数据，只保留关键字段
    if isinstance(project, dict) and "error" not in project:
        return filter_project_data(project)
    return project


async def list_branches(project_id: str) -> List[Dict[str, Any]]:
    """获取分支列表（使用默认配置）"""
    # 使用第一个仓库的配置
    repo_names = list(_config.get_all_repositories().keys()) if _config else []
    if not repo_names:
        return {"error": "未配置仓库"}
    
    client = get_client(repo_names[0])
    if not client:
        return {"error": "GitLab客户端未初始化"}
    
    return await client.list_branches(project_id)


async def list_commits(repo_name: str, ref_name: str = "main", per_page: int = 20, since: str = None, until: str = None) -> List[Dict[str, Any]]:
    """获取指定仓库的提交记录"""
    client = get_client(repo_name)
    if not client:
        return {"error": "GitLab客户端未初始化"}
    
    # 获取简化的仓库名称
    simple_repo_name = _get_simple_repo_name(repo_name)
    
    # 获取仓库ID
    repo_config = _config.get_repository_config(simple_repo_name)
    project_id = repo_config.get("project_id", "")
    
    if not project_id:
        return {"error": "仓库ID未配置"}
    
    commits = await client.list_commits(project_id, ref_name, per_page, since, until)
    # 过滤数据，只保留关键字段
    return [filter_commit_data(commit) for commit in commits]

async def search_repositories(query: str) -> Dict[str, Any]:
    """根据描述搜索仓库"""
    if not _config:
        init_config()
    
    matching_repos = _config.search_repositories_by_description(query)
    
    return {
        "repositories": matching_repos,
        "count": len(matching_repos)
    }


def get_tool_definitions() -> List[Dict[str, Any]]:
    """获取工具定义，用于AI调用"""
    return [
        {
            "type": "function",
            "function": {
                "name": "git_list_issues",
                "description": "获取指定GitLab仓库的issues列表，支持按日期过滤",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "repo_name": {
                            "type": "string",
                            "description": "仓库名称，如 'lubanlou' 或 'production_document'"
                        },
                        "per_page": {
                            "type": "integer",
                            "description": "每页数量，默认20"
                        },
                        "state": {
                            "type": "string",
                            "description": "状态，可选值：all（默认）、opened、closed"
                        },
                        "created_after": {
                            "type": "string",
                            "description": "创建时间过滤（开始），格式：YYYY-MM-DD"
                        },
                        "created_before": {
                            "type": "string",
                            "description": "创建时间过滤（结束），格式：YYYY-MM-DD"
                        },
                        "updated_after": {
                            "type": "string",
                            "description": "更新时间过滤，格式：YYYY-MM-DD"
                        }
                    },
                    "required": ["repo_name"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "git_get_issue",
                "description": "获取指定GitLab仓库的单个issue详情",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "repo_name": {
                            "type": "string",
                            "description": "仓库名称，如 'lubanlou' 或 'production_document'"
                        },
                        "issue_id": {
                            "type": "integer",
                            "description": "Issue ID"
                        }
                    },
                    "required": ["repo_name", "issue_id"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "git_list_issue_notes",
                "description": "获取指定GitLab仓库的issue评论列表",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "repo_name": {
                            "type": "string",
                            "description": "仓库名称，如 'lubanlou' 或 'production_document'"
                        },
                        "issue_id": {
                            "type": "integer",
                            "description": "Issue ID"
                        },
                        "per_page": {
                            "type": "integer",
                            "description": "每页数量，默认20"
                        }
                    },
                    "required": ["repo_name", "issue_id"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "git_search_content",
                "description": "搜索指定GitLab仓库中的内容（issues、notes和提交记录）",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "repo_name": {
                            "type": "string",
                            "description": "仓库名称，如 'lubanlou' 或 'production_document'"
                        },
                        "query": {
                            "type": "string",
                            "description": "搜索关键词"
                        },
                        "per_page": {
                            "type": "integer",
                            "description": "每页数量，默认20"
                        }
                    },
                    "required": ["repo_name", "query"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "git_list_projects",
                "description": "获取GitLab项目列表",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "per_page": {
                            "type": "integer",
                            "description": "每页数量，默认20"
                        }
                    }
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "git_search_repositories",
                "description": "根据描述搜索仓库，返回匹配的仓库列表",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "搜索关键词，例如 '值班'、'产品开发' 等"
                        }
                    },
                    "required": ["query"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "git_list_commits",
                "description": "获取指定GitLab仓库的提交记录，支持按日期过滤",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "repo_name": {
                            "type": "string",
                            "description": "仓库名称，如 'lubanlou' 或 'production_document'"
                        },
                        "ref_name": {
                            "type": "string",
                            "description": "分支名称，默认main"
                        },
                        "per_page": {
                            "type": "integer",
                            "description": "每页数量，默认20"
                        },
                        "since": {
                            "type": "string",
                            "description": "开始日期，格式：YYYY-MM-DD"
                        },
                        "until": {
                            "type": "string",
                            "description": "结束日期，格式：YYYY-MM-DD"
                        }
                    },
                    "required": ["repo_name"]
                }
            }
        }
    ]

def register_tools() -> Dict[str, Any]:
    return {
        "init_config": init_config,
        "get_client": get_client,
        "list_issues": list_issues,
        "get_issue": get_issue,
        "list_issue_notes": list_issue_notes,
        "search_content": search_content,
        "list_projects": list_projects,
        "get_project": get_project,
        "list_branches": list_branches,
        "list_commits": list_commits,
        "search_repositories": search_repositories,
        "get_tool_definitions": get_tool_definitions
    }


TOOLS = register_tools()

# 初始化配置
init_config()
