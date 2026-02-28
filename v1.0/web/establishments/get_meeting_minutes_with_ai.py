from fastapi import Request
import httpx
import time
import asyncio

async def handle(request: Request, config_manager):
    """
    获取指定日期的会议列表，批量获取会议内容，然后调用AI生成纪要
    参数：
        day: 指定日期，格式：YYYY-MM-DD
        length: 纪要长度，字节数，可选，如果没有则不限制
    """
    day = request.query_params.get("day", "")
    length = request.query_params.get("length", "")
    
    if not day:
        return {
            "code": 400,
            "message": "缺少day参数",
            "data": [],
            "timestamp": int(time.time() * 1000),
            "executeTime": 0
        }
    
    try:
        # 转换length参数为整数
        max_length = int(length) if length.isdigit() else None
        
        # 1. 调用get_day_meeting接口获取会议列表
        meeting_list_response = await fetch_meeting_list(day, config_manager)
        if meeting_list_response.get("code") != 200:
            return {
                "code": 500,
                "message": f"获取会议列表失败: {meeting_list_response.get('message', '未知错误')}",
                "data": [],
                "timestamp": int(time.time() * 1000),
                "executeTime": 0
            }
        
        meeting_list = meeting_list_response.get("data", [])
        if not meeting_list:
            return {
                "code": 200,
                "message": "success",
                "data": [],
                "timestamp": int(time.time() * 1000),
                "executeTime": 0
            }
        
        # 2. 遍历会议列表，批量获取会议内容
        meeting_minutes_list = []
        start_time = time.time()
        
        for meeting in meeting_list:
            meeting_url = meeting.get("url", "")
            if not meeting_url:
                continue
            
            # 调用browser接口获取会议内容
            meeting_content = await fetch_meeting_content(meeting_url, config_manager)
            if not meeting_content.get("success"):
                print(f"获取会议 {meeting.get('node_name', '')} 内容失败: {meeting_content.get('error', '未知错误')}")
                continue
            
            # 提取会议文本内容
            content = meeting_content.get("content", "")
            
            # 3. 调用AI生成纪要
            minutes = await generate_minutes(content, config_manager)
            if not minutes:
                print(f"生成会议 {meeting.get('node_name', '')} 纪要失败")
                continue
            
            # 4. 根据length参数限制纪要长度
            if max_length and len(minutes) > max_length:
                minutes = minutes[:max_length]
            
            # 5. 构建会议纪要对象
            meeting_minutes = {
                "meeting_id": meeting.get("uid"),
                "meeting_name": meeting.get("node_name"),
                "meeting_url": meeting_url,
                "minutes": minutes,
                "minutes_length": len(minutes),
                "created_time": meeting.get("created_time"),
                "updated_time": meeting.get("updated_time")
            }
            
            meeting_minutes_list.append(meeting_minutes)
        
        end_time = time.time()
        execute_time = int((end_time - start_time) * 1000)  # 转换为毫秒
        
        return {
            "code": 200,
            "message": "success",
            "data": meeting_minutes_list,
            "timestamp": int(time.time() * 1000),
            "executeTime": execute_time
        }
    except Exception as e:
        return {
            "code": 500,
            "message": f"处理失败: {str(e)}",
            "data": [],
            "timestamp": int(time.time() * 1000),
            "executeTime": 0
        }

async def fetch_meeting_list(day: str, config_manager) -> dict:
    """
    调用get_day_meeting接口获取会议列表
    """
    # 导入数据库模块，避免循环导入
    from web.establishments.get_day_meeting import handle as get_day_meeting_handle
    
    # 创建模拟请求对象
    class MockRequest:
        def __init__(self, query_params):
            self.query_params = query_params
    
    mock_request = MockRequest({"day": day})
    return await get_day_meeting_handle(mock_request, config_manager)

async def fetch_meeting_content(url: str, config_manager) -> dict:
    """
    调用browser接口获取会议内容
    """
    try:
        # 直接调用browser模块的handle函数，避免HTTP请求的开销
        from web.common.browser import handle as browser_handle
        
        # 创建模拟请求对象
        class MockRequest:
            def __init__(self, query_params):
                self.query_params = query_params
                self.method = "GET"
        
        mock_request = MockRequest({"url": url, "text_only": "true"})
        result = await browser_handle(mock_request, config_manager)
        
        # 转换为字典格式
        if hasattr(result, "body"):
            import json
            return json.loads(result.body.decode("utf-8"))
        return result
    except Exception as e:
        return {"success": False, "error": str(e), "url": url}

async def generate_minutes(content: str, config_manager) -> str:
    """
    调用AI生成会议纪要
    """
    try:
        # 调用AI接口生成纪要
        async with httpx.AsyncClient(timeout=60.0) as client:
            # 构建AI请求
            ai_prompt = f"""
            请根据以下会议内容生成一份简洁明了的会议纪要：
            
            {content}
            
            会议纪要要求：
            1. 结构清晰，包含会议主题、时间、参会人员、会议内容、决策事项、行动项等
            2. 语言简洁，重点突出
            3. 保留关键信息，去除冗余内容
            """
            
            response = await client.post(
                "http://localhost:9528/api/aichat/deepseek",
                json={
                    "prompt": ai_prompt,
                    "stream": False,
                    "preprocess": False
                }
            )
            response.raise_for_status()
            result = response.json()
            
            # 提取AI生成的纪要
            if "say" in result:
                return result["say"]
            return ""
    except Exception as e:
        print(f"调用AI生成纪要失败: {str(e)}")
        return ""