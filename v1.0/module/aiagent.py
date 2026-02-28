import re
import json
import asyncio
import logging
from typing import AsyncGenerator, Dict, Any, Optional, List
from pathlib import Path

import httpx
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

# ============ [新增] Token估算常量 ============
CHARS_PER_TOKEN = 2.5  # 平均每个token约2.5个字符
MAX_TOOL_RESULT_TOKENS = 80000  # 触发自动分块的阈值


# ============ [新增] Token估算函数 ============
def estimate_tokens(text: str) -> int:
    """估算文本的token数量"""
    return int(len(text) / CHARS_PER_TOKEN)


def clean_utf8(text: str) -> str:
    """清理字符串中的无效UTF-8字符"""
    if not isinstance(text, str):
        return text
    # 移除代理对和其他无效UTF-8字符
    return ''.join(c for c in text if c.isprintable() or c in '\n\r\t')

def redact_sensitive_data(data: Any, sensitive_keys: set = None) -> Any:
    """递归屏蔽敏感数据"""
    if sensitive_keys is None:
        sensitive_keys = {'access_token', 'token', 'password', 'secret', 'api_key'}
    
    if isinstance(data, dict):
        result = {}
        for key, value in data.items():
            if key.lower() in sensitive_keys or any(sk in key.lower() for sk in sensitive_keys):
                result[key] = '***REDACTED***'
            else:
                result[key] = redact_sensitive_data(value, sensitive_keys)
        return result
    elif isinstance(data, list):
        return [redact_sensitive_data(item, sensitive_keys) for item in data]
    elif isinstance(data, str):
        if len(data) > 50 and any(c.isalnum() for c in data):
            for sk in sensitive_keys:
                if sk in data.lower():
                    return '***REDACTED***'
        return clean_utf8(data)
    else:
        return data


class AIAgent:
    def __init__(self, config: Dict[str, Any], mcp_manager=None, user_info: Dict[str, Any] = None):
        self.config = config
        self.provider = config.get('provider', 'deepseek')
        
        providers = config.get('providers', {})
        provider_config = providers.get(self.provider, {})
        
        self.base_url = provider_config.get('base_url', 'https://api.deepseek.com')
        self.api_key = provider_config.get('api_key', '')
        self.model = provider_config.get('model', 'deepseek-chat')
        self.temperature = provider_config.get('temperature', config.get('temperature', 0.7))
        self.max_tokens = provider_config.get('max_tokens', config.get('max_tokens', 4096))
        self.max_iterations = config.get('max_iterations', 100)  # 工具调用最大迭代次数
        self.mcp_manager = mcp_manager
        self.user_info = user_info or {}
        
        # Token 统计
        self.token_stats = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "api_calls": 0,
            "tool_calls": 0,
            "current_prompt": ""
        }
        
        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )
    
    def reset_token_stats(self, prompt: str = ""):
        """重置 token 统计"""
        import time
        self.token_stats = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "api_calls": 0,
            "tool_calls": 0,
            "current_prompt": prompt,
            "start_time": time.time(),
            "elapsed_seconds": 0
        }
    
    def get_token_stats(self) -> Dict[str, Any]:
        """获取 token 统计信息"""
        return self.token_stats.copy()
    
    def get_tools(self, service_names: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """获取工具定义。当 service_names 指定时仅返回对应 skill 的工具（按需提交）。"""
        if not self.mcp_manager:
            return []

        # 工具名前缀 -> 服务名（用于按 skill 过滤）
        # dataproc_* -> data_processor，其余服务前缀即服务名
        prefix_to_service: Dict[str, str] = {}
        for s in self.mcp_manager.services:
            prefix_to_service[s] = s
        for prefix, svc in self.SERVICE_ALIASES.items():
            prefix_to_service[prefix] = svc

        tools = []
        for service_name, service in self.mcp_manager.services.items():
            if service_names is not None and len(service_names) > 0 and service_name not in service_names:
                continue
            defs = []
            if hasattr(service.module, 'TOOL_DEFINITIONS'):
                defs = list(service.module.TOOL_DEFINITIONS)
            elif hasattr(service.module, 'get_tool_definitions'):
                defs = list(service.module.get_tool_definitions())
            for d in defs:
                fn = d.get("function") or {}
                name = fn.get("name") if isinstance(fn, dict) else None
                if not name:
                    tools.append(d)
                    continue
                prefix = name.split("_", 1)[0]
                tool_service = prefix_to_service.get(prefix, prefix)
                if service_names is None or len(service_names) == 0 or tool_service in service_names:
                    tools.append(d)
        return tools
    
    # ============ [新增] 服务别名映射 ============
    # 解决工具名称前缀 "dataproc_" 与服务名 "data_processor" 不匹配的问题
    SERVICE_ALIASES = {
        "dataproc": "data_processor",
    }
    
    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        if not self.mcp_manager:
            return {"error": "MCP管理器未配置"}
        
        parts = tool_name.split('_', 1)
        if len(parts) < 2:
            return {"error": f"无效的工具名称: {tool_name}"}
        
        service_name = parts[0]
        # ============ [新增] 应用服务别名映射 ============
        service_name = self.SERVICE_ALIASES.get(service_name, service_name)
        func_name = parts[1]
        
        service = self.mcp_manager.get_service(service_name)
        if not service:
            return {"error": f"MCP服务不存在: {service_name}"}
        
        if func_name not in service.tools:
            return {"error": f"工具不存在: {func_name}"}
        
        try:
            # 验证必填参数
            tool_func = service.tools.get(func_name)
            if tool_func:
                import inspect
                sig = inspect.signature(tool_func)
                required_params = [
                    p.name for p in sig.parameters.values() 
                    if p.default == inspect.Parameter.empty and p.name not in ('self', 'kwargs')
                ]
                missing = [p for p in required_params if p not in arguments]
                if missing:
                    return {"error": f"缺少必填参数: {', '.join(missing)}。请提供完整参数后重试。"}
            
            if func_name == 'save_weekly_report':
                if 'access_token' not in arguments or not arguments.get('access_token'):
                    arguments['access_token'] = self.user_info.get('external_token', '') if self.user_info else ''
                if 'username' not in arguments or not arguments.get('username'):
                    arguments['username'] = self.user_info.get('username', '') if self.user_info else ''
            
            if func_name == 'send_email' and service_name == 'mail':
                to_addr = arguments.get('to', '')
                if to_addr.lower() in ['me', '我', 'myself', '自己']:
                    user_email = self.user_info.get('email', '') if self.user_info else ''
                    if user_email:
                        arguments['to'] = user_email
                        arguments['_replaced_to'] = f"{to_addr} -> {user_email}"
                        logger.info(f"邮件收件人替换: {to_addr} -> {user_email}")
                    else:
                        return {"error": "无法发送邮件给自己：未找到当前用户的邮箱地址，请登录后重试或在设置中配置邮箱"}
            
            result = await service.call_tool(func_name, **arguments)
            return result
        except Exception as e:
            logger.error(f"工具执行失败: {e}")
            return {"error": str(e)}
    
    # ============ [新增] 消息历史压缩方法 ============
    def _compress_messages_if_needed(self, messages: List[Dict], max_tokens: int) -> List[Dict]:
        """当消息历史过长时，压缩旧的工具结果
        
        策略：保留系统消息和用户消息，将大的工具结果替换为摘要
        """
        total_tokens = sum(estimate_tokens(json.dumps(m, ensure_ascii=False)) for m in messages)
        
        if total_tokens <= max_tokens:
            return messages
        
        logger.info(f"消息历史过长 ({total_tokens} tokens)，开始压缩...")
        
        compressed = []
        for i, msg in enumerate(messages):
            if msg["role"] == "tool":
                content = msg.get("content", "")
                content_tokens = estimate_tokens(content)
                
                # 如果工具结果超过 10000 tokens，压缩它
                if content_tokens > 10000:
                    try:
                        result = json.loads(content)
                        # 创建压缩摘要
                        if isinstance(result, dict):
                            if "content" in result:
                                # dataproc_get_chunk 结果，只保留元信息
                                summary = {
                                    "compressed": True,
                                    "original_tokens": content_tokens,
                                    "chunk_id": result.get("chunk_id", ""),
                                    "char_count": result.get("char_count", 0),
                                    "info": result.get("info", {}),
                                    "note": "内容已压缩，如需重新查看请再次调用 dataproc_get_chunk"
                                }
                            else:
                                # 其他工具结果，保留键名
                                summary = {
                                    "compressed": True,
                                    "original_tokens": content_tokens,
                                    "keys": list(result.keys())[:10],
                                    "note": "结果已压缩"
                                }
                        else:
                            summary = {
                                "compressed": True,
                                "original_tokens": content_tokens,
                                "type": type(result).__name__,
                                "note": "结果已压缩"
                            }
                        compressed.append({
                            "role": "tool",
                            "tool_call_id": msg.get("tool_call_id", ""),
                            "content": json.dumps(summary, ensure_ascii=False)
                        })
                        logger.info(f"压缩工具结果: {content_tokens} -> {estimate_tokens(json.dumps(summary))} tokens")
                        continue
                    except:
                        pass
            
            compressed.append(msg)
        
        new_total = sum(estimate_tokens(json.dumps(m, ensure_ascii=False)) for m in compressed)
        logger.info(f"消息压缩完成: {total_tokens} -> {new_total} tokens")
        
        return compressed
    
    # ============ [新增] 大数据自动分块方法 ============
    async def _auto_chunk_large_result(self, result_json: str, tool_name: str) -> Dict[str, Any]:
        """自动将大结果分块处理
        
        当工具返回结果超过 MAX_TOOL_RESULT_TOKENS 时调用此方法，
        使用 data_processor 服务将数据分块，避免上下文长度超限。
        """
        try:
            data_processor = self.mcp_manager.get_service("data_processor") if self.mcp_manager else None
            
            if data_processor and hasattr(data_processor.module, 'chunk_text'):
                chunk_result = await data_processor.module.chunk_text(result_json, source=tool_name)
                
                if chunk_result.get("success"):
                    chunks = chunk_result.get("chunks", [])
                    chunk_ids = [c["chunk_id"] for c in chunks]
                    
                    # 保存任务状态，方便后续继续处理
                    if hasattr(data_processor.module, '_save_task_state'):
                        import hashlib
                        task_id = hashlib.md5(f"{tool_name}_{len(chunks)}".encode()).hexdigest()[:8]
                        data_processor.module._save_task_state(
                            task_id=task_id,
                            chunk_ids=chunk_ids,
                            processed_ids=[],
                            description=f"来自 {tool_name} 的数据处理任务",
                            source=tool_name
                        )
                    
                    instructions = f"""
数据量过大，已自动分块处理。

📊 分块统计:
- 总数据块: {len(chunks)} 个
- 估计总Token数: {chunk_result.get('total_estimated_tokens', 0)}

📋 处理步骤（必须处理全部 {len(chunks)} 个数据块！）:
1. 调用 dataproc_get_next_chunk 获取下一个未处理的数据块
2. 分析数据块内容，调用 dataproc_save_summary 保存摘要（会自动标记为已处理）
3. 重复步骤1-2直到所有 {len(chunks)} 个数据块全部处理完毕
4. 最后调用 dataproc_merge_summaries 合并所有摘要生成最终报告

⚠️ 重要：必须处理全部 {len(chunks)} 个数据块，不能提前停止！

🔖 数据块ID (前5个):
{chr(10).join([f"  - {cid}" for cid in chunk_ids[:5]])}
{'  ... 还有 ' + str(len(chunk_ids) - 5) + ' 个数据块' if len(chunk_ids) > 5 else ''}

请立即开始处理第一个数据块。
"""
                    return {
                        "success": True,
                        "chunked": True,
                        "total_chunks": len(chunks),
                        "chunk_ids": chunk_ids,
                        "instructions": instructions
                    }
            
            # 降级处理：直接截断
            truncated = result_json[:50000] + f"\n\n... [数据过大，已截断，原始长度: {len(result_json)} 字符]"
            return {
                "success": True,
                "chunked": False,
                "truncated": True,
                "data": truncated,
                "message": "数据过大已截断，建议使用分块处理"
            }
        except Exception as e:
            logger.error(f"自动分块失败: {e}")
            truncated = result_json[:50000] + f"\n\n... [截断，错误: {str(e)}]"
            return {"success": False, "error": str(e), "data": truncated}
    
    async def chat(self, prompt: str, stream: bool = True, skills: Optional[List[str]] = None) -> AsyncGenerator[Dict[str, Any], None]:
        import time
        start_time = time.time()
        try:
            if stream:
                async for chunk in self._stream_chat_with_tools(prompt, skills=skills):
                    yield chunk
            else:
                result = await self._sync_chat_with_tools(prompt, skills=skills)
                yield result
        except Exception as e:
            logger.error(f"AI聊天错误: {e}", exc_info=True)
            # 确保错误时也返回统计信息
            self.token_stats["elapsed_seconds"] = time.time() - self.token_stats.get("start_time", start_time)
            self.token_stats["total_tokens"] = self.token_stats["prompt_tokens"] + self.token_stats["completion_tokens"]
            yield {"type": "error", "content": str(e), "token_stats": self.token_stats.copy()}
    
    async def _stream_chat_with_tools(self, prompt: str, skills: Optional[List[str]] = None) -> AsyncGenerator[Dict[str, Any], None]:
        # 重置 token 统计
        self.reset_token_stats(prompt)
        
        user_context = ""
        if self.user_info:
            username = self.user_info.get('username', '')
            cname = self.user_info.get('cname', '')
            if username:
                user_context = f"\n\n当前登录用户: {cname or username} (用户名: {username})。用户的access_token已自动获取，调用需要认证的工具时无需再询问用户提供token。"
        
        # 系统提示
        system_prompt = f"""你是一个智能助手，可以使用工具来帮助用户完成任务。

重要规则：
1. 当需要查询数据或提交报告时，请直接使用提供的工具，不要询问用户提供access_token等认证信息，这些信息会自动注入。
2. 【强制要求】当数据被分块处理时（收到chunk_ids列表），你必须处理全部数据块，绝对不能跳过任何块！
   - 收到N个chunk_ids，就必须调用N次dataproc_get_chunk获取每个块
   - 每获取一个块后，分析内容并调用dataproc_save_summary保存摘要
   - 持续处理直到所有块都完成，不要中途停止
3. 所有块处理完成后，调用dataproc_get_all_summaries获取所有摘要，然后生成最终报告。
4. 如果用户要求处理"所有"数据或"全年"数据，你必须处理100%的数据块，不能因为"样本足够"而提前停止。
5. 【重要】生成报告时必须覆盖数据的完整时间范围（如1月-12月），不能只输出部分月份的内容。所有摘要都要整合到最终报告中。
6. 回答时请使用中文。{user_context}"""
        
        # 清理用户输入中的无效UTF-8字符
        cleaned_prompt = clean_utf8(prompt)
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": cleaned_prompt}
        ]
        
        tools = self.get_tools(service_names=skills)
        max_iterations = self.max_iterations  # 从配置读取
        iteration = 0
        
        # 消息历史 token 限制（留出空间给新内容和回复）
        MAX_HISTORY_TOKENS = 80000
        
        while iteration < max_iterations:
            iteration += 1
            
            # ============ [新增] 消息历史压缩 ============
            messages = self._compress_messages_if_needed(messages, MAX_HISTORY_TOKENS)
            # ============ [新增结束] ============
            
            # ============ [新增] API 调用重试机制 ============
            max_retries = 3
            retry_delay = 2
            last_error = None
            stream_response = None
            
            for retry in range(max_retries):
                try:
                    if tools:
                        stream_response = await self.client.chat.completions.create(
                            model=self.model,
                            messages=messages,
                            temperature=self.temperature,
                            max_tokens=self.max_tokens,
                            tools=tools,
                            tool_choice="auto",
                            stream=True
                        )
                    else:
                        stream_response = await self.client.chat.completions.create(
                            model=self.model,
                            messages=messages,
                            temperature=self.temperature,
                            max_tokens=self.max_tokens,
                            stream=True
                        )
                    break  # 成功则跳出重试循环
                except Exception as e:
                    last_error = e
                    
                    # 检查是否为不可重试的错误类型
                    # 使用异常类型检查（更可靠）和字符串检查（兜底）
                    is_non_retryable = False
                    
                    # 检查 OpenAI SDK 的 BadRequestError (400 错误)
                    error_class_name = type(e).__name__
                    if error_class_name in ('BadRequestError', 'InvalidRequestError', 'AuthenticationError', 'PermissionDeniedError'):
                        is_non_retryable = True
                    
                    # 兜底：检查错误消息中的关键词
                    error_str = str(e).lower()
                    if any(kw in error_str for kw in ['invalid_request', 'maximum context length', 'authentication', 'permission denied']):
                        is_non_retryable = True
                    
                    # 检查 HTTP 状态码（如果可用）
                    if hasattr(e, 'status_code') and e.status_code in (400, 401, 403, 404):
                        is_non_retryable = True
                    
                    if is_non_retryable:
                        logger.error(f"API请求错误（不可重试）: {e}")
                        raise last_error
                    
                    # 可重试的错误（网络超时、连接错误等）
                    if retry < max_retries - 1:
                        logger.warning(f"API调用失败，{retry_delay}秒后重试 ({retry + 1}/{max_retries}): {e}")
                        yield {
                            "type": "process_info",
                            "message": f"网络连接中断，{retry_delay}秒后重试..."
                        }
                        import asyncio
                        await asyncio.sleep(retry_delay)
                        retry_delay *= 2  # 指数退避
                    else:
                        raise last_error
            # ============ [新增结束] ============
            
            collected_content = ""
            collected_tool_calls = {}
            thinking_content = ""
            say_content = ""
            in_thinking = False
            has_tool_calls = False
            stream_error = None
            
            # 更新 API 调用统计
            self.token_stats["api_calls"] += 1
            # 估算当前消息的 token 数（仅估算，不从 API 获取）
            messages_tokens = estimate_tokens(json.dumps(messages, ensure_ascii=False))
            self.token_stats["prompt_tokens"] += messages_tokens
            
            try:
                async for chunk in stream_response:
                    if not chunk.choices:
                        continue
                        
                    delta = chunk.choices[0].delta
                    
                    if delta.tool_calls:
                        has_tool_calls = True
                        for tc in delta.tool_calls:
                            idx = tc.index
                            if idx not in collected_tool_calls:
                                collected_tool_calls[idx] = {
                                    "id": "",
                                    "name": "",
                                    "arguments": ""
                                }
                            if tc.id:
                                collected_tool_calls[idx]["id"] = tc.id
                            if tc.function:
                                if tc.function.name:
                                    collected_tool_calls[idx]["name"] = tc.function.name
                                if tc.function.arguments:
                                    collected_tool_calls[idx]["arguments"] += tc.function.arguments
                    
                    if delta.content:
                        content = delta.content
                        collected_content += content
                        
                        if "<think>" in content:
                            in_thinking = True
                            content = content.replace("<think>", "")
                        
                        if "</think>" in content:
                            in_thinking = False
                            parts = content.split("</think>")
                            if len(parts) > 0:
                                thinking_content += parts[0]
                            if len(parts) > 1 and parts[1]:
                                say_content += parts[1]
                                yield {"type": "say", "content": parts[1], "partial": True}
                            continue
                        
                        if in_thinking:
                            thinking_content += content
                            yield {"type": "think", "content": content, "partial": True}
                        else:
                            say_content += content
                            yield {"type": "say", "content": content, "partial": True}
            except Exception as e:
                stream_error = e
                logger.error(f"流式读取错误: {e}")
                yield {
                    "type": "error",
                    "message": f"网络连接中断，请输入'继续'重试"
                }
                return
            
            if has_tool_calls and collected_tool_calls:
                tool_calls_list = []
                for idx in sorted(collected_tool_calls.keys()):
                    tc_data = collected_tool_calls[idx]
                    tool_calls_list.append({
                        "id": tc_data["id"],
                        "type": "function",
                        "function": {
                            "name": tc_data["name"],
                            "arguments": tc_data["arguments"]
                        }
                    })
                
                messages.append({
                    "role": "assistant",
                    "content": collected_content or "",
                    "tool_calls": tool_calls_list
                })
                
                for tc_data in tool_calls_list:
                    tool_name = tc_data["function"]["name"]
                    try:
                        arguments = json.loads(tc_data["function"]["arguments"])
                    except:
                        arguments = {}
                    
                    # 更新工具调用统计
                    self.token_stats["tool_calls"] += 1
                    
                    yield {
                        "type": "tool_call",
                        "tool_name": tool_name,
                        "arguments": redact_sensitive_data(arguments)
                    }
                    
                    result = await self.execute_tool(tool_name, arguments)
                    
                    if '_replaced_to' in arguments:
                        yield {
                            "type": "process_info",
                            "message": f"收件人已自动替换: {arguments['_replaced_to']}"
                        }
                        del arguments['_replaced_to']
                    
                    # ============ [新增] 大数据自动检测和分块处理 ============
                    result_json = json.dumps(result, ensure_ascii=False)
                    result_tokens = estimate_tokens(result_json)
                    
                    # [新增] 排除 data_processor 服务本身的结果，避免无限循环
                    is_dataproc_tool = tool_name.startswith("dataproc_")
                    
                    if result_tokens > MAX_TOOL_RESULT_TOKENS and not is_dataproc_tool:
                        # 数据过大，自动分块处理
                        yield {
                            "type": "process_info",
                            "message": f"数据量过大 ({result_tokens} tokens)，正在自动分块处理..."
                        }
                        
                        chunked_result = await self._auto_chunk_large_result(result_json, tool_name)
                        
                        yield {
                            "type": "tool_result",
                            "tool_name": tool_name,
                            "result": {"message": f"数据已分块，共 {chunked_result['total_chunks']} 个块", "chunk_ids": chunked_result.get('chunk_ids', [])[:5]}
                        }
                        
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc_data["id"],
                            "content": json.dumps(chunked_result, ensure_ascii=False)
                        })
                    else:
                        # 正常大小的结果，直接返回
                        yield {
                            "type": "tool_result",
                            "tool_name": tool_name,
                            "result": redact_sensitive_data(result)
                        }
                        
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc_data["id"],
                            "content": result_json
                        })
                    # ============ [新增结束] ============
                
                continue
            
            # 估算完成 token 数并计算耗时
            import time
            completion_tokens = estimate_tokens(collected_content)
            self.token_stats["completion_tokens"] += completion_tokens
            self.token_stats["total_tokens"] = self.token_stats["prompt_tokens"] + self.token_stats["completion_tokens"]
            self.token_stats["elapsed_seconds"] = time.time() - self.token_stats.get("start_time", time.time())
            
            yield {
                "type": "complete",
                "think": thinking_content,
                "say": say_content,
                "token_stats": self.token_stats.copy()
            }
            break
        else:
            # 达到最大迭代次数，生成最终总结
            if tools:
                messages.append({
                    "role": "user",
                    "content": "请根据上述工具调用结果，简要总结回答用户的问题。"
                })
                try:
                    self.token_stats["api_calls"] += 1
                    final_response = await self.client.chat.completions.create(
                        model=self.model,
                        messages=messages,
                        temperature=self.temperature,
                        max_tokens=self.max_tokens,
                        stream=True
                    )
                    final_content = ""
                    async for chunk in final_response:
                        if chunk.choices and chunk.choices[0].delta.content:
                            content = chunk.choices[0].delta.content
                            final_content += content
                            yield {"type": "say", "content": content, "partial": True}
                    
                    # 更新 token 统计
                    import time
                    self.token_stats["completion_tokens"] += estimate_tokens(final_content)
                    self.token_stats["total_tokens"] = self.token_stats["prompt_tokens"] + self.token_stats["completion_tokens"]
                    self.token_stats["elapsed_seconds"] = time.time() - self.token_stats.get("start_time", time.time())
                    yield {"type": "complete", "think": "", "say": final_content, "token_stats": self.token_stats.copy()}
                except Exception as e:
                    logger.error(f"生成最终总结失败: {e}")
                    import time
                    self.token_stats["total_tokens"] = self.token_stats["prompt_tokens"] + self.token_stats["completion_tokens"]
                    self.token_stats["elapsed_seconds"] = time.time() - self.token_stats.get("start_time", time.time())
                    yield {"type": "complete", "think": "", "say": "（已达到最大工具调用次数）", "token_stats": self.token_stats.copy()}
    
    async def _sync_chat_with_tools(self, prompt: str, skills: Optional[List[str]] = None) -> Dict[str, Any]:
        result = {"type": "complete", "think": "", "say": "", "tool_calls": []}

        async for chunk in self._stream_chat_with_tools(prompt, skills=skills):
            if chunk.get("type") == "tool_call":
                result["tool_calls"].append({
                    "name": chunk.get("tool_name"),
                    "arguments": chunk.get("arguments")
                })
            elif chunk.get("type") == "tool_result":
                for tc in result["tool_calls"]:
                    if tc["name"] == chunk.get("tool_name"):
                        tc["result"] = chunk.get("result")
            elif chunk.get("type") == "think" and chunk.get("partial"):
                result["think"] += chunk.get("content", "")
            elif chunk.get("type") == "say" and chunk.get("partial"):
                result["say"] += chunk.get("content", "")
            elif chunk.get("type") == "complete":
                if chunk.get("think"):
                    result["think"] = chunk.get("think")
                if chunk.get("say"):
                    result["say"] = chunk.get("say")
        
        return result


class PromptPreprocessor:
    def __init__(self, web_root: str = "web"):
        self.web_root = Path(web_root)
        self.http_client = httpx.AsyncClient(timeout=30.0)
    
    async def process(self, prompt: str) -> str:
        pattern = r'@\{([^}]+)\}'
        
        async def replace_match(match):
            expression = match.group(1).strip()
            return await self._evaluate_expression(expression)
        
        matches = list(re.finditer(pattern, prompt))
        if not matches:
            return prompt
        
        result = prompt
        for match in reversed(matches):
            replacement = await self._evaluate_expression(match.group(1).strip())
            result = result[:match.start()] + replacement + result[match.end():]
        
        return result
    
    async def _evaluate_expression(self, expression: str) -> str:
        if expression.startswith('file(') and expression.endswith(')'):
            file_path = expression[5:-1].strip().strip('"\'')
            return await self._load_file(file_path)
        
        elif expression.startswith('api(') and expression.endswith(')'):
            url = expression[4:-1].strip().strip('"\'')
            return await self._call_api(url)
        
        elif expression.startswith('browser(') and expression.endswith(')'):
            url = expression[8:-1].strip().strip('"\'')
            return await self._browser_fetch(url)
        
        return f"[未知表达式: {expression}]"
    
    async def _load_file(self, file_path: str) -> str:
        try:
            full_path = self.web_root / file_path
            if full_path.exists():
                with open(full_path, 'r', encoding='utf-8') as f:
                    return f.read()
            return f"[文件不存在: {file_path}]"
        except Exception as e:
            return f"[文件读取错误: {e}]"
    
    async def _call_api(self, url: str) -> str:
        try:
            response = await self.http_client.get(url)
            response.raise_for_status()
            return response.text
        except Exception as e:
            return f"[API调用错误: {e}]"
    
    async def _browser_fetch(self, url: str) -> str:
        try:
            from playwright.async_api import async_playwright
            
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.goto(url, wait_until='networkidle')
                content = await page.content()
                await browser.close()
                return content
        except Exception as e:
            logger.warning(f"Browser fetch失败，降级到httpx: {e}")
            try:
                response = await self.http_client.get(url)
                return response.text
            except Exception as e2:
                return f"[浏览器获取错误: {e2}]"
    
    async def close(self):
        await self.http_client.aclose()
