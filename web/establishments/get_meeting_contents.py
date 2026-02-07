from fastapi import Request
import asyncio
import logging
import time

logger = logging.getLogger(__name__)


async def handle(request: Request, config_manager):
    day = request.query_params.get("day", "")
    length = request.query_params.get("length", "300")
    
    if not day:
        return {
            "success": False,
            "error": "缺少必要参数 day",
            "example": "/api/establishments/get_meeting_contents?day=2024-12-30&length=300"
        }
    
    start_time = time.time()
    
    from web.establishments import get_day_meeting, get_meeting_content
    
    class MockRequest:
        def __init__(self, params):
            self.query_params = params
    
    meeting_request = MockRequest({"day": day})
    meeting_result = await get_day_meeting.handle(meeting_request, config_manager)
    
    if isinstance(meeting_result, dict) and meeting_result.get("code") == 400:
        return {
            "success": False,
            "error": meeting_result.get("message", "获取会议列表失败")
        }
    
    meetings = []
    if isinstance(meeting_result, dict):
        meetings = meeting_result.get("data", [])
    elif isinstance(meeting_result, list):
        meetings = meeting_result
    
    if not meetings:
        return {
            "success": True,
            "day": day,
            "total": 0,
            "meetings": [],
            "message": "当天没有会议"
        }
    
    results = []
    success_count = 0
    fail_count = 0
    
    for meeting in meetings:
        url = meeting.get("url") or meeting.get("meetingUrl") or meeting.get("link") or ""
        title = meeting.get("title") or meeting.get("meetingTitle") or meeting.get("name") or "未命名会议"
        meeting_id = meeting.get("id") or meeting.get("meetingId") or ""
        meeting_time = meeting.get("time") or meeting.get("meetingTime") or meeting.get("startTime") or ""
        
        if not url:
            results.append({
                "id": meeting_id,
                "title": title,
                "time": meeting_time,
                "success": False,
                "error": "缺少会议链接"
            })
            fail_count += 1
            continue
        
        try:
            content_request = MockRequest({
                "url": url,
                "length": length,
                "title": title
            })
            content_result = await get_meeting_content.handle(content_request, config_manager)
            
            if content_result.get("success"):
                results.append({
                    "id": meeting_id,
                    "title": title,
                    "time": meeting_time,
                    "url": url,
                    "success": True,
                    "summary": content_result.get("summary", ""),
                    "original_length": content_result.get("original_length", 0),
                    "summary_length": content_result.get("summary_length", 0)
                })
                success_count += 1
            else:
                results.append({
                    "id": meeting_id,
                    "title": title,
                    "time": meeting_time,
                    "url": url,
                    "success": False,
                    "error": content_result.get("error", "未知错误")
                })
                fail_count += 1
                
        except Exception as e:
            logger.error(f"处理会议 {title} 失败: {e}")
            results.append({
                "id": meeting_id,
                "title": title,
                "time": meeting_time,
                "url": url,
                "success": False,
                "error": str(e)
            })
            fail_count += 1
    
    elapsed_time = round(time.time() - start_time, 2)
    
    return {
        "success": True,
        "day": day,
        "total": len(meetings),
        "success_count": success_count,
        "fail_count": fail_count,
        "elapsed_time": f"{elapsed_time}s",
        "meetings": results
    }
