#!/usr/bin/env python3
"""
AI Client v2.0 命令行入口，支持 Agent Skills。
"""

import asyncio
import argparse
import sys
from pathlib import Path

# 确保可导入当前目录模块
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env", override=True)

from agent import AIClient, load_config


def color(text: str, c: str) -> str:
    colors = {"green": "\033[32m", "cyan": "\033[36m", "yellow": "\033[33m", "gray": "\033[90m", "magenta": "\033[35m", "reset": "\033[0m"}
    return f"{colors.get(c, '')}{text}{colors['reset']}"


async def typewriter_print(text: str, delay: float = 0.02) -> None:
    """逐字输出，产生打字效果。"""
    for ch in text:
        print(ch, end="", flush=True)
        await asyncio.sleep(delay)


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
    async for chunk in client.chat(prompt, stream=True, skill_names=skill_names, history=history):
        t = chunk.get("type")
        if t == "think":
            print(color("\n[思考] ", "magenta") + color(chunk.get("content", ""), "gray"))
        elif t == "tool_result" and not quiet:
            name = chunk.get("tool_name", "")
            result = chunk.get("result", {})
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
            if not quiet and chunk.get("elapsed_seconds") is not None:
                print(color(f"\n[耗时] {chunk['elapsed_seconds']:.1f}s", "gray"))
        elif t == "error":
            print(color(f"\n[错误] {chunk.get('content', '')}", "yellow"))
    print(color("-" * 50, "gray"))
    return "".join(full_reply)


async def interactive(client: AIClient, skill_names: list[str] | None, quiet: bool, typewriter: bool, typewriter_delay: float):
    print(color("AI Client v2.0 (支持 Agent Skills)", "cyan"))
    print(color("输入问题开始对话，exit/quit 退出；对话带上下文", "gray"))
    print(color("=" * 50, "cyan"))
    history = []
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
            if len(history) > 20:
                history = history[-20:]
        except (KeyboardInterrupt, EOFError):
            print(color("\n再见", "green"))
            break


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
