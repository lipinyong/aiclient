#!/usr/bin/env python3
"""
AI Client v2.0 命令行入口，支持 Agent Skills。
"""

import asyncio
import argparse
import json
import sys
from pathlib import Path

# 确保可导入当前目录模块
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env", override=True)

from agent import AIClient, load_config

HISTORY_PATH = Path(__file__).parent / "data" / "chat_history.json"
MAX_HISTORY_ENTRIES = 20


def load_history() -> list:
    """从 data/chat_history.json 读入对话历史，不存在或格式异常则返回空列表。"""
    if not HISTORY_PATH.is_file():
        return []
    try:
        raw = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            return []
        return [
            {"role": str(item.get("role", "")), "content": str(item.get("content", ""))}
            for item in raw
            if item.get("role") in ("user", "assistant") and "content" in item
        ]
    except (OSError, json.JSONDecodeError):
        return []


def save_history(history: list) -> None:
    """将对话历史写入 data/chat_history.json；保留最近 MAX_HISTORY_ENTRIES 条。"""
    if len(history) > MAX_HISTORY_ENTRIES:
        history = history[-MAX_HISTORY_ENTRIES:]
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_PATH.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")


def color(text: str, c: str) -> str:
    colors = {"green": "\033[32m", "cyan": "\033[36m", "yellow": "\033[33m", "gray": "\033[90m", "magenta": "\033[35m", "reset": "\033[0m"}
    return f"{colors.get(c, '')}{text}{colors['reset']}"


async def typewriter_print(text: str, delay: float = 0.02) -> None:
    """逐字输出，产生打字效果。"""
    for ch in text:
        print(ch, end="", flush=True)
        await asyncio.sleep(delay)


def _delete_scripts_created(paths: list[str], quiet: bool) -> None:
    """删除本轮 run_script 生成的脚本文件；非 quiet 时若删除了文件则打印提示。"""
    deleted = 0
    for p in paths:
        if not p:
            continue
        try:
            path = Path(p)
            if path.is_file():
                path.unlink()
                deleted += 1
        except OSError:
            pass
    if not quiet and deleted:
        print(color(f"\n[清理] 已删除本轮生成的 {deleted} 个脚本", "gray"))


async def run_chat(
    client: AIClient,
    prompt: str,
    skill_names: list[str] | None,
    quiet: bool,
    typewriter: bool = True,
    typewriter_delay: float = 0.02,
    history: list | None = None,
) -> str:
    """返回本轮助手完整回复内容。"""
    print(color(f"\n[问题] {prompt}", "cyan"))
    print(color("-" * 50, "gray"))
    answer_started = False
    full_reply = []
    scripts_created_this_turn: list[str] = []
    async for chunk in client.chat(prompt, stream=True, skill_names=skill_names, history=history):
        t = chunk.get("type")
        if t == "think":
            print(color("\n[思考] ", "magenta") + color(chunk.get("content", ""), "gray"))
        elif t == "tool_result":
            name = chunk.get("tool_name", "")
            result = chunk.get("result", {})
            if name == "run_script" and result.get("script_path"):
                scripts_created_this_turn.append(result["script_path"])
            if not quiet:
                preview = str(result).replace("password", "***")[:200]
                print(color(f"\n[工具结果] {name}: ", "gray") + color(preview + ("..." if len(str(result)) > 200 else ""), "gray"))
        elif t == "say" and chunk.get("partial"):
            content = chunk.get("content", "")
            if content:
                full_reply.append(content)
                if not answer_started:
                    print(color("\n[回答] ", "green"))
                    answer_started = True
                if typewriter:
                    await typewriter_print(content, typewriter_delay)
                else:
                    print(content, end="", flush=True)
        elif t == "complete":
            print()
            if not quiet:
                elapsed = chunk.get("elapsed_seconds")
                prompt_tokens = chunk.get("prompt_tokens")
                completion_tokens = chunk.get("completion_tokens")
                total_tokens = chunk.get("total_tokens")
                parts = []
                if elapsed is not None:
                    parts.append(color(f"耗时 {elapsed:.1f}s", "gray"))
                if total_tokens is not None and (prompt_tokens is not None or completion_tokens is not None):
                    tok = f"token 输入 {prompt_tokens or 0} / 输出 {completion_tokens or 0} / 合计 {total_tokens or 0}"
                    parts.append(color(tok, "gray"))
                if parts:
                    print(color("\n[统计] ", "gray") + "  ".join(parts))
            _delete_scripts_created(scripts_created_this_turn, quiet)
        elif t == "error":
            print(color(f"\n[错误] {chunk.get('content', '')}", "yellow"))
            if not quiet:
                elapsed = chunk.get("elapsed_seconds")
                total_tokens = chunk.get("total_tokens")
                if elapsed is not None:
                    print(color(f"[统计] 耗时 {elapsed:.1f}s", "gray"))
                if total_tokens is not None:
                    print(color(f"[统计] token 合计 {total_tokens}", "gray"))
            _delete_scripts_created(scripts_created_this_turn, quiet)
    print(color("-" * 50, "gray"))
    return "".join(full_reply)


async def interactive(client: AIClient, skill_names: list[str] | None, quiet: bool, typewriter: bool, typewriter_delay: float):
    print(color("AI Client v2.0 (支持 Agent Skills)", "cyan"))
    print(color("输入问题开始对话，exit/quit 退出；对话带上下文", "gray"))
    print(color("对话历史保存至 data/chat_history.json", "gray"))
    print(color("=" * 50, "cyan"))
    history = load_history()
    try:
        while True:
            try:
                prompt = input(color("你: ", "green")).strip()
                if not prompt:
                    continue
                if prompt.lower() in ("exit", "quit", "q", "bye"):
                    print(color("再见", "green"))
                    break
                reply = await run_chat(client, prompt, skill_names, quiet, typewriter, typewriter_delay, history=history)
                history.append({"role": "user", "content": prompt})
                history.append({"role": "assistant", "content": reply})
                if len(history) > MAX_HISTORY_ENTRIES:
                    history = history[-MAX_HISTORY_ENTRIES:]
                save_history(history)
            except (KeyboardInterrupt, EOFError):
                print(color("\n再见", "green"))
                break
    finally:
        save_history(history)


def main():
    parser = argparse.ArgumentParser(description="AI Client v2.0 - 支持 Agent Skills")
    parser.add_argument("-p", "--prompt", help="直接提问（非交互）")
    parser.add_argument("--skills", type=str, default=None, help="显式指定技能名（逗号分隔）；不传则按需自动选择相关技能")
    parser.add_argument("-q", "--quiet", action="store_true", help="少输出")
    parser.add_argument("--no-typewriter", action="store_true", help="禁用打字机效果，立即输出")
    parser.add_argument("--typewriter-delay", type=float, default=0.02, help="打字机每字延迟（秒），默认 0.02")
    parser.add_argument("--list-skills", action="store_true", help="列出已发现的 Agent Skills 后退出")
    parser.add_argument("--config", type=str, default=None, help="配置文件路径")
    args = parser.parse_args()

    config = load_config(Path(args.config) if args.config else None)
    client = AIClient(config=config)

    if not client.api_key:
        print(color("错误: 未配置 API Key。请在 .env 中设置 DEEPSEEK_API_KEY 或在 config.yaml 中配置。", "yellow"))
        sys.exit(1)

    skill_names = None
    if args.skills:
        skill_names = [s.strip() for s in args.skills.split(",") if s.strip()]

    if args.list_skills:
        skills = client.list_skills()
        print(color("已发现的 Agent Skills:", "cyan"))
        for s in skills:
            print(f"  - {s['name']}: {s['description'][:60]}...")
        if not skills:
            print("  (无。请在 skills/<skill-name>/ 下添加 SKILL.md)")
        return

    typewriter = not args.no_typewriter
    delay = max(0.001, args.typewriter_delay)
    if args.prompt:
        asyncio.run(run_chat(client, args.prompt, skill_names, args.quiet, typewriter, delay))
    else:
        asyncio.run(interactive(client, skill_names, args.quiet, typewriter, delay))


if __name__ == "__main__":
    main()
