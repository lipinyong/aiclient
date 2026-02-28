#!/usr/bin/env python3
import sys
import os
import json
import asyncio
import argparse
import time
import yaml
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
# 加载当前目录的.env文件

script_real_path = Path(os.path.realpath(__file__))
script_dir = script_real_path.parent
env_path = script_dir / '.env'

print(f"脚本目录: {script_dir}")
print(f".env文件路径: {env_path}")
print(f".env文件是否存在: {env_path.exists()}")
# 加载.env文件（保留你的原有代码）
load_dotenv(env_path, override=True)
sys.path.insert(0, str(script_dir))

from module.aiagent import AIAgent, PromptPreprocessor
from module.mcpserver import MCPServerManager


def load_config() -> dict:
    """加载配置"""
    config_path = Path(__file__).parent / "config.yaml"
    # print(f"配置文件路径: {config_path}")
    if config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_content = f.read()
                # 替换环境变量
                for key, value in os.environ.items():
                    config_content = config_content.replace(f'${{{key}}}', value)
                config = yaml.safe_load(config_content)
                return config
        except Exception as e:
            print(f"配置加载失败: {e}")
    return {}


def typewriter_print(text: str, delay: float = 0.02):
    for char in text:
        sys.stdout.write(char)
        sys.stdout.flush()
        time.sleep(delay)


def print_colored(text: str, color: str = "default"):
    colors = {
        "default": "\033[0m",
        "green": "\033[32m",
        "yellow": "\033[33m",
        "blue": "\033[34m",
        "magenta": "\033[35m",
        "cyan": "\033[36m",
        "gray": "\033[90m",
        "reset": "\033[0m"
    }
    print(f"{colors.get(color, '')}{text}{colors['reset']}")


async def chat_stream(agent: AIAgent, preprocessor: PromptPreprocessor, prompt: str, 
                      typewriter: bool = True, delay: float = 0.02, preprocess: bool = True, quiet: bool = False, show_answer_tag: bool = False, skills=None):
    original_prompt = prompt  # 保存原始提问
    
    if not quiet:
        print_colored(f"\n[问题] {prompt}", "cyan")
        print_colored("-" * 50, "gray")
    
    if preprocess:
        prompt = await preprocessor.process(prompt)
    
    think_buffer = ""
    say_buffer = ""
    current_type = None
    tool_calls = []
    has_output = False
    token_stats = None  # 保存 token 统计
    
    try:
        async for chunk in agent.chat(prompt, stream=True, skills=skills):
            msg_type = chunk.get("type", "")
            content = chunk.get("content", "")
            
            if msg_type == "think":
                if not quiet:
                    if current_type != "think":
                        if current_type:
                            print()
                        print_colored("\n[思考]", "magenta")
                        current_type = "think"
                    if typewriter:
                        typewriter_print(content, delay)
                    else:
                        sys.stdout.write(content)
                        sys.stdout.flush()
                think_buffer += content
            
            elif msg_type == "say":
                if current_type != "say":
                    if not quiet or show_answer_tag:
                        if current_type:
                            print()
                        print_colored("\n[回答]", "green")
                        current_type = "say"
                        has_output = True
                if not quiet:
                    if typewriter:
                        typewriter_print(content, delay)
                    else:
                        sys.stdout.write(content)
                        sys.stdout.flush()
                say_buffer += content
            
            elif msg_type == "tool_call":
                if current_type and not quiet:
                    print()
                    current_type = None
                tool_name = chunk.get("tool_name", "unknown")
                tool_args = chunk.get("arguments", {})
                if not quiet:
                    print_colored(f"\n[工具调用] {tool_name}", "blue")
                    print_colored(f"  参数: {json.dumps(tool_args, ensure_ascii=False, indent=2)}", "gray")
                tool_calls.append({"tool": tool_name, "arguments": tool_args})
            
            elif msg_type == "tool_result":
                tool_name = chunk.get("tool_name", "unknown")
                result = chunk.get("result", "")
                if not quiet:
                    result_str = json.dumps(result, ensure_ascii=False, indent=2) if isinstance(result, (dict, list)) else str(result)
                    result_preview = result_str[:200] + "..." if len(result_str) > 200 else result_str
                    print_colored(f"\n[工具结果] {tool_name}", "blue")
                    print_colored(f"  结果: {result_preview}", "gray")
            
            elif msg_type == "error":
                if not quiet:
                    print_colored(f"\n[错误] {content}", "yellow")
                # 错误时也获取 token 统计
                if chunk.get("token_stats"):
                    token_stats = chunk.get("token_stats")
            
            elif msg_type == "complete":
                # 获取 token 统计信息
                token_stats = chunk.get("token_stats")
        
        if not quiet:
            print()
            print_colored("-" * 50, "gray")
            
            # 显示 token 统计信息
            if token_stats:
                elapsed = token_stats.get('elapsed_seconds', 0)
                if elapsed >= 60:
                    elapsed_str = f"{int(elapsed // 60)}分{int(elapsed % 60)}秒"
                else:
                    elapsed_str = f"{elapsed:.1f}秒"
                
                print_colored("\n[统计信息]", "magenta")
                print_colored(f"  提问内容: {original_prompt[:100]}{'...' if len(original_prompt) > 100 else ''}", "gray")
                print_colored(f"  耗时: {elapsed_str}", "gray")
                print_colored(f"  API调用次数: {token_stats.get('api_calls', 0)}", "gray")
                print_colored(f"  工具调用次数: {token_stats.get('tool_calls', 0)}", "gray")
                print_colored(f"  输入Token: ~{token_stats.get('prompt_tokens', 0):,}", "gray")
                print_colored(f"  输出Token: ~{token_stats.get('completion_tokens', 0):,}", "gray")
                print_colored(f"  总Token: ~{token_stats.get('total_tokens', 0):,}", "gray")
                print_colored("-" * 50, "gray")
        elif say_buffer:
            # 静默模式下输出最终回答
            if show_answer_tag and not has_output:
                # 如果还没有显示过[回答]标签，先显示标签
                print_colored("\n[回答]", "green")
            print(say_buffer)
        
    except KeyboardInterrupt:
        if not quiet:
            print_colored("\n[中断] 用户取消", "yellow")


async def interactive_mode(agent: AIAgent, preprocessor: PromptPreprocessor,
                           typewriter: bool = True, delay: float = 0.02, quiet: bool = False, skills=None):
    if not quiet:
        print_colored("=" * 60, "cyan")
        print_colored("  AI 聊天命令行工具 (本地模式)", "cyan")
        print_colored("  输入问题开始对话，输入 'exit' 或 'quit' 退出", "gray")
        print_colored("=" * 60, "cyan")
    
    while True:
        try:
            if not quiet:
                print()
            # 在静默模式下的交互模式中仍然显示输入提示
            prompt = input("\033[36m请输入问题: \033[0m").strip()
            
            if not prompt:
                continue
            
            if prompt.lower() in ("exit", "quit", "q", "bye"):
                if not quiet:
                    print_colored("再见！", "green")
                break
            
            await chat_stream(agent, preprocessor, prompt, typewriter, delay, quiet=quiet, show_answer_tag=True, skills=skills)
            
        except KeyboardInterrupt:
            if not quiet:
                print_colored("\n再见！", "green")
            break
        except EOFError:
            if not quiet:
                print_colored("\n再见！", "green")
            break


async def async_main():
    parser = argparse.ArgumentParser(description="AI 聊天命令行工具 (本地模式)")
    parser.add_argument("-p", "--prompt", help="直接提问（非交互模式）")
    parser.add_argument("-d", "--delay", type=float, default=0.02, help="打字机延迟（秒）")
    parser.add_argument("--no-typewriter", action="store_true", help="禁用打字机效果")
    parser.add_argument("--no-preprocess", action="store_true", help="禁用提示词预处理")
    parser.add_argument("-q", "--quiet", action="store_true", help="静默模式，减少输出信息")
    parser.add_argument("--debug", action="store_true", help="debug模式，打印info级别日志")
    # [新增] 热加载相关参数
    parser.add_argument("--hot-reload", action="store_true", help="启用MCP服务热加载")
    parser.add_argument("--hot-reload-interval", type=float, default=2.0, help="热加载检查间隔（秒），默认2秒")

    parser.add_argument("--skills", type=str, default=None, help="按需启用的 MCP 能力（逗号分隔），如 mail,data_processor,xmgl；不传则使用全部")

    args = parser.parse_args()
    
    # 根据debug参数设置日志级别
    import logging
    if args.debug:
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    else:
        logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    config = load_config()
    ai_config = config.get('ai', {})
    
    # 获取当前provider（默认为deepseek）
    provider = ai_config.get('provider', 'deepseek')
    providers = ai_config.get('providers', {})
    provider_config = providers.get(provider, {})
    
    api_key = provider_config.get('api_key', '')
    if api_key.startswith('${') and api_key.endswith('}'):
        env_var = api_key[2:-1]
        api_key = os.environ.get(env_var, '')
    
    if not api_key:
        print_colored(f"[错误] 未配置 AI API 密钥 (provider: {provider})")
        return
    
    ai_config['api_key'] = api_key
    
    mcp_manager = MCPServerManager()
    
    # 从配置中获取MCP服务路径，如果没有则使用默认路径
    mcp_config = config.get('mcp', {})
    services_path = mcp_config.get('services_path', 'mcp')
    
    # 将相对路径转换为绝对路径，基于项目根目录
    project_root = Path(__file__).parent
    absolute_services_path = project_root / services_path
    mcp_manager.set_services_path(str(absolute_services_path))
    
    # 加载所有服务
    if not args.quiet:
        print(f"MCP服务路径: {absolute_services_path}")
    services = mcp_manager.discover_services()
    if not args.quiet:
        print(f"发现服务: {services}")
    
    for service_name in services:
        mcp_manager.load_service(service_name)
    
    # 显示已加载的服务（简洁模式）
    loaded_services = mcp_manager.list_services()
    loaded_count = len(loaded_services)
    service_names = [service['name'] for service in loaded_services]
    if not args.quiet:
        print(f"已加载服务: {loaded_count} 个 - {', '.join(service_names)}")
    
    # [新增] 启动热加载监控
    if args.hot_reload:
        mcp_manager.start_hot_reload(interval=args.hot_reload_interval)
        if not args.quiet:
            print(f"热加载已启用，检查间隔: {args.hot_reload_interval}秒")
    
    agent = AIAgent(ai_config, mcp_manager)
    preprocessor = PromptPreprocessor(config.get('web', {}).get('root', 'web'))
    skills_list = [s.strip() for s in args.skills.split(",") if s.strip()] if args.skills else None
    if skills_list and not args.quiet:
        print(f"按需启用 skill: {', '.join(skills_list)}")

    typewriter = not args.no_typewriter
    preprocess = not args.no_preprocess
    
    if args.prompt:
        # 使用-p参数时，静默模式下不显示[回答]标签
        # 非交互模式下自动重试错误
        max_retries = 3
        retry_count = 0
        current_prompt = args.prompt
        
        while retry_count <= max_retries:
            error_occurred = False
            async for chunk in agent.chat(current_prompt if retry_count == 0 else "继续处理", stream=True, skills=skills_list):
                msg_type = chunk.get("type", "")
                content = chunk.get("content", "")
                
                if msg_type == "error":
                    error_occurred = True
                    if not args.quiet:
                        print_colored(f"\n[错误] {content}", "yellow")
                    break
                elif msg_type == "say" and chunk.get("partial"):
                    if typewriter:
                        for char in content:
                            print(char, end='', flush=True)
                            await asyncio.sleep(args.delay)
                    else:
                        print(content, end='', flush=True)
                elif msg_type == "think" and chunk.get("partial") and not args.quiet:
                    print_colored(content, "gray", end='')
                elif msg_type == "tool_call" and not args.quiet:
                    tool_name = chunk.get("tool_name", "")
                    print_colored(f"\n[工具调用] {tool_name}", "blue")
                elif msg_type == "tool_result" and not args.quiet:
                    tool_name = chunk.get("tool_name", "")
                    result_str = str(chunk.get("result", ""))[:200]
                    print_colored(f"\n[工具结果] {tool_name}: {result_str}...", "blue")
                elif msg_type == "complete":
                    token_stats = chunk.get("token_stats")
                    if token_stats and not args.quiet:
                        elapsed = token_stats.get('elapsed_seconds', 0)
                        elapsed_str = f"{int(elapsed // 60)}分{int(elapsed % 60)}秒" if elapsed >= 60 else f"{elapsed:.1f}秒"
                        print_colored(f"\n\n[统计] 耗时: {elapsed_str}, Token: ~{token_stats.get('total_tokens', 0):,}", "gray")
            
            if error_occurred and retry_count < max_retries:
                retry_count += 1
                if not args.quiet:
                    print_colored(f"\n[自动重试] 第 {retry_count}/{max_retries} 次，5秒后继续...", "yellow")
                await asyncio.sleep(5)
            else:
                break
        
        print()  # 最终换行
    else:
        # 交互模式下，静默模式仍然显示[回答]标签
        await interactive_mode(agent, preprocessor, typewriter, args.delay, args.quiet, skills=skills_list)


def main():
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
