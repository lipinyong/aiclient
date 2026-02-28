"""
AI 客户端核心：调用 LLM，支持注入 Agent Skills、多轮上下文与工具调用（SSH/Shell 实际执行）。
"""

import asyncio
import os
import json
import logging
import time
from pathlib import Path
from typing import AsyncGenerator, Dict, Any, List, Optional

from openai import AsyncOpenAI

from skills_loader import discover_skills, get_skills_context, select_skills_for_prompt
from tools import TOOLS as BASE_TOOLS

logger = logging.getLogger(__name__)

MAX_TOOL_ITERATIONS = 20


def _load_skill_tools(project_root: Path, skill_name: str):
    """从 skills/<skill_name>/tools.py 加载 TOOLS 与 execute_tool。"""
    path = project_root / "skills" / skill_name / "tools.py"
    if not path.exists():
        return None
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(f"skill_tools_{skill_name}", path)
        if spec is None or spec.loader is None:
            return None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        tools = getattr(mod, "TOOLS", None)
        execute = getattr(mod, "execute_tool", None)
        if tools and callable(execute):
            return (list(tools), execute)
    except Exception as e:
        logger.warning("加载技能工具失败 %s: %s", path, e)
    return None


def _get_tools_and_executors(project_root: Path, skills_used: List[str]):
    """合并基础工具与已启用技能的工具，返回 (tools_list, executors_map)。"""
    tools = list(BASE_TOOLS)
    executors = {}
    for t in BASE_TOOLS:
        name = (t.get("function") or {}).get("name")
        if name:
            executors[name] = ("base", None)
    for skill_name in skills_used:
        loaded = _load_skill_tools(project_root, skill_name)
        if loaded:
            skill_tools, execute_fn = loaded
            tools.extend(skill_tools)
            for t in skill_tools:
                name = (t.get("function") or {}).get("name")
                if name:
                    executors[name] = ("skill", execute_fn)
    return tools, executors


def load_config(config_path: Optional[Path] = None) -> dict:
    """加载 config.yaml，并替换 ${VAR} 环境变量。"""
    import yaml
    path = config_path or Path(__file__).parent / "config.yaml"
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    for key, value in os.environ.items():
        text = text.replace(f"${{{key}}}", str(value))
    return yaml.safe_load(text) or {}


class AIClient:
    """支持 Agent Skills 的 AI 聊天客户端。"""

    def __init__(
        self,
        config: Optional[dict] = None,
        project_root: Optional[Path] = None,
    ):
        config = config or load_config()
        self.project_root = project_root or Path(__file__).parent
        ai = config.get("ai", {})
        self.provider = ai.get("provider", "deepseek")
        providers = ai.get("providers", {})
        pc = providers.get(self.provider, {})
        self.base_url = pc.get("base_url", "https://api.deepseek.com")
        self.api_key = pc.get("api_key", "") or os.environ.get("DEEPSEEK_API_KEY", "")
        self.model = pc.get("model", "deepseek-chat")
        self.temperature = float(pc.get("temperature", ai.get("temperature", 0.7)))
        self.max_tokens = int(pc.get("max_tokens", ai.get("max_tokens", 8192)))
        self.config = config

        skills_config = config.get("skills", {})
        self.skills_path_keys = skills_config.get("paths", ["project", "personal"])

        self._all_skills: List[Dict[str, Any]] = []
        self._client: Optional[AsyncOpenAI] = None
        self._tool_executors: Dict[str, Any] = {}

    @property
    def client(self) -> AsyncOpenAI:
        if self._client is None:
            self._client = AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
            )
        return self._client

    def reload_skills(self) -> List[Dict[str, Any]]:
        """发现并缓存所有 Agent Skills。"""
        self._all_skills = discover_skills(
            self.skills_path_keys,
            project_root=self.project_root,
        )
        return self._all_skills

    def list_skills(self) -> List[Dict[str, Any]]:
        """返回当前已发现的技能列表（含 name, description）。"""
        if not self._all_skills:
            self.reload_skills()
        return [{"name": s["name"], "description": s["description"]} for s in self._all_skills]

    def _get_skills_to_use(
        self,
        prompt: str,
        skill_names: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        确定本次对话要注入的技能。
        - skill_names 非空：显式指定，只注入这些技能。
        - skill_names 为 None：按需自动选择，根据用户 prompt 与技能的 triggers/description 匹配。
        """
        if not self._all_skills:
            self.reload_skills()
        if skill_names is not None and len(skill_names) > 0:
            name_set = set(skill_names)
            return [s for s in self._all_skills if s["name"] in name_set]
        return select_skills_for_prompt(prompt, self._all_skills)

    def _build_system_prompt(self, skills: List[Dict[str, Any]]) -> str:
        base = "你是一个智能助手。请用中文回答。"
        skill_names = [s["name"] for s in skills]
        if "ssh" in skill_names:
            base += "\n\n当用户要求连接 SSH、在远程执行命令或分析系统时，你必须直接调用 ssh_run 工具执行，并根据工具返回的结果进行分析总结、给出结论；不要只给操作建议或命令示例。"
            base += "\n【重要】每次用户在本轮消息中提供了新的主机 IP、账号或密码时，必须针对本轮给出的主机重新调用 ssh_run，不得沿用上一轮或其他主机的执行结果；回答开头须明确标注「以下为主机 <用户给出的IP> 的检查结果」。"
        if "shell" in skill_names:
            base += "\n\n当用户要求在本地执行命令、查看目录、查进程或跑脚本时，你必须直接调用 run_shell 工具执行，并根据返回结果回答；Windows 下用 PowerShell 或 CMD，Linux/macOS 下用 bash。"
        if "pdf-reader" in skill_names:
            base += "\n\n当用户提供本地 PDF 路径并要求摘要/问答/提取信息时，你必须先调用 pdf_read 抽取文本；若返回 chunk_ids，必须把所有 chunk 通过 pdf_get_chunk 取回后再生成最终摘要/结论；不要在未读取文档内容时直接编造摘要。"
        if "image-ocr" in skill_names:
            base += "\n\n当用户提供本地图片路径并要求识别图中文字、提取文字或翻译图中内容时，你必须先调用 ocr_run 对图片做 OCR，再根据返回的 text 和 details 作答；不要未识别就编造图中文字。"
        if "skill-creator" in skill_names:
            base += "\n\n当用户要求创建技能、管理技能、列出/删除技能、从本地目录或 GitHub 安装技能时，你必须调用 skill_list / skill_create / skill_delete / skill_install_path / skill_install_github / skill_get_info 等工具完成操作；创建技能时根据用户需求生成完整的 SKILL.md 正文与触发词，并告知用户新技能名与用法。"
        if "lubanlou" in skill_names:
            base += "\n\n当用户需要从鲁班楼（lubanlou.com）采集或查询信息时，你必须先调用 lubanlou_login 获取 token（若用户提供账号密码则传入），再使用 lubanlou_request 调用相应 API 路径；若返回 401 或提示 token 失效，需重新登录后再请求。"
        if "browser" in skill_names:
            base += "\n\n【网页抓取】当用户要求读取、抓取某 URL 的网页内容时，你必须且只能调用 browser_fetch_content 工具（传入该 URL），禁止使用 run_script、run_shell 或任何自写脚本。browser_fetch_content 返回后，回复中**只展示抓取到的内容**：可对 content 做分段、排版、整理，但**不要**做内容特点分析、要点归纳、评价或其它解读，仅输出整理后的抓取信息本身，不添加「该页面特点」「从内容可以看出」等分析性表述。在浏览器中打开链接时用 browser_open。"
        ctx = get_skills_context(skills)
        if ctx:
            base += "\n\n" + ctx
        return base

    def _execute_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if self._tool_executors:
            kind, fn = self._tool_executors.get(name, (None, None))
            if kind == "skill" and callable(fn):
                return fn(name, arguments)
        return {"error": f"未知工具: {name}"}

    async def chat(
        self,
        prompt: str,
        stream: bool = True,
        skill_names: Optional[List[str]] = None,
        history: Optional[List[Dict[str, Any]]] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        history: 多轮对话历史，每项 {"role":"user"|"assistant","content":"..."}，不含 system。
        """
        skills = self._get_skills_to_use(prompt, skill_names)
        system_prompt = self._build_system_prompt(skills)
        skills_used = [s["name"] for s in skills]
        # 本轮使用的工具与 system 仅依赖当前 prompt 匹配的技能，下一问若不匹配 ssh 则不会提交 ssh 工具与说明
        tools_list, self._tool_executors = _get_tools_and_executors(self.project_root, skills_used)
        if skills_used:
            yield {"type": "think", "content": "本次调用技能: " + ", ".join(skills_used)}
        else:
            yield {"type": "think", "content": "未匹配到技能，按通用助手回答。"}
        messages = [{"role": "system", "content": system_prompt}]
        if history:
            for h in history:
                if h.get("role") in ("user", "assistant") and "content" in h:
                    messages.append({"role": h["role"], "content": h["content"]})
        messages.append({"role": "user", "content": prompt})
        start = time.time()
        loop = asyncio.get_event_loop()
        total_prompt_tokens = 0
        total_completion_tokens = 0
        try:
            iteration = 0
            while iteration < MAX_TOOL_ITERATIONS:
                iteration += 1
                api_kw: Dict[str, Any] = {
                    "model": self.model,
                    "messages": messages,
                    "temperature": self.temperature,
                    "max_tokens": self.max_tokens,
                    "stream": True,
                }
                if tools_list:
                    api_kw["tools"] = tools_list
                    api_kw["tool_choice"] = "auto"
                stream_resp = await self.client.chat.completions.create(**api_kw)
                collected = ""
                tool_calls_collected = {}
                usage_from_stream = None
                async for chunk in stream_resp:
                    if not chunk.choices:
                        continue
                    if getattr(chunk, "usage", None) is not None:
                        usage_from_stream = chunk.usage
                    delta = chunk.choices[0].delta
                    if delta.content:
                        collected += delta.content
                        yield {"type": "say", "content": delta.content, "partial": True}
                    if delta.tool_calls:
                        for tc in delta.tool_calls:
                            idx = tc.index
                            if idx not in tool_calls_collected:
                                tool_calls_collected[idx] = {"id": "", "name": "", "arguments": ""}
                            if tc.id:
                                tool_calls_collected[idx]["id"] = tc.id
                            if tc.function:
                                if tc.function.name:
                                    tool_calls_collected[idx]["name"] = tc.function.name
                                if tc.function.arguments:
                                    tool_calls_collected[idx]["arguments"] += tc.function.arguments or ""
                if usage_from_stream:
                    total_prompt_tokens += getattr(usage_from_stream, "prompt_tokens", 0) or 0
                    total_completion_tokens += getattr(usage_from_stream, "completion_tokens", 0) or 0
                if not tool_calls_collected:
                    yield {
                        "type": "complete",
                        "say": collected,
                        "elapsed_seconds": time.time() - start,
                        "skills_used": skills_used,
                        "prompt_tokens": total_prompt_tokens,
                        "completion_tokens": total_completion_tokens,
                        "total_tokens": total_prompt_tokens + total_completion_tokens,
                    }
                    return
                tool_calls_list = []
                for idx in sorted(tool_calls_collected.keys()):
                    tc = tool_calls_collected[idx]
                    tool_calls_list.append({"id": tc["id"], "type": "function", "function": {"name": tc["name"], "arguments": tc["arguments"]}})
                messages.append({"role": "assistant", "content": collected or "", "tool_calls": tool_calls_list})
                for tc in tool_calls_list:
                    name = tc["function"]["name"]
                    try:
                        args = json.loads(tc["function"]["arguments"] or "{}")
                    except Exception:
                        args = {}
                    yield {"type": "think", "content": f"正在执行 {name}: {str(args.get('command', args.get('host', '')))[:60]}..."}
                    result = await loop.run_in_executor(None, lambda n=name, a=args: self._execute_tool(n, a))
                    yield {"type": "tool_result", "tool_name": name, "result": result}
                    messages.append({"role": "tool", "tool_call_id": tc["id"], "content": json.dumps(result, ensure_ascii=False)})
                collected = ""
            yield {
                "type": "complete",
                "say": collected,
                "elapsed_seconds": time.time() - start,
                "skills_used": skills_used,
                "prompt_tokens": total_prompt_tokens,
                "completion_tokens": total_completion_tokens,
                "total_tokens": total_prompt_tokens + total_completion_tokens,
            }
        except Exception as e:
            logger.exception("chat error")
            yield {
                "type": "error",
                "content": str(e),
                "elapsed_seconds": time.time() - start,
                "skills_used": skills_used,
                "prompt_tokens": total_prompt_tokens,
                "completion_tokens": total_completion_tokens,
                "total_tokens": total_prompt_tokens + total_completion_tokens,
            }
        finally:
            self._tool_executors = {}
