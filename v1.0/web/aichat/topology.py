import json
import re
import logging
from pathlib import Path
from fastapi import Request

from module.aiagent import AIAgent

logger = logging.getLogger(__name__)

PROMPT_DIR = Path(__file__).parent / "prompt"


def extract_json(text: str) -> str:
    text = text.strip()
    
    if text.startswith("```json"):
        text = text[7:]
    if text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()
    
    match = re.search(r'\{[\s\S]*\}', text)
    if match:
        return match.group(0)
    
    return text


def load_prompt(filename: str) -> str:
    prompt_file = PROMPT_DIR / filename
    if prompt_file.exists():
        return prompt_file.read_text(encoding='utf-8')
    logger.warning(f"提示词文件不存在: {prompt_file}")
    return ""


async def handle(request: Request, config_manager):
    if request.method == "GET":
        return {
            "service": "系统地铁图生成器",
            "version": "2.0.0",
            "description": "分步生成系统地铁图 JSON（三维拓扑：纵向活动流、横向资源层、反馈环）",
            "steps": {
                "step1": "分析文本，提取三条纵向主线、三条横向主线、三个反馈环",
                "step2": "将提取的结构映射到 gridX(0-14) 和 gridY(0-10) 坐标系，输出 Konva.js JSON"
            },
            "usage": {
                "method": "POST",
                "content_type": "multipart/form-data 或 application/json",
                "fields": {
                    "file": "需求文档文件 (multipart，step1使用)",
                    "content": "需求文档内容 (json，step1使用)",
                    "step1_result": "第一步结果 (step2使用)",
                    "step": "步骤编号: 1 或 2，默认1",
                    "prompt": "额外说明 (可选)"
                }
            }
        }
    
    if request.method != "POST":
        return {"error": "仅支持GET/POST请求"}
    
    content_type = request.headers.get("content-type", "")
    
    text_content = ""
    prompt = ""
    step = 1
    step1_result = None
    
    if "multipart/form-data" in content_type:
        form = await request.form()
        
        file = form.get("file")
        if file and hasattr(file, 'read'):
            file_content = await file.read()
            try:
                text_content = file_content.decode("utf-8")
            except:
                try:
                    text_content = file_content.decode("gbk")
                except:
                    return {"error": "无法解码文件，请使用UTF-8或GBK编码"}
        
        prompt_val = form.get("prompt", "")
        prompt = str(prompt_val) if prompt_val else ""
        step_val = form.get("step", "1")
        step = int(str(step_val)) if step_val else 1
        
        content_val = form.get("content")
        if not text_content and content_val:
            text_content = str(content_val)
        
        step1_json = form.get("step1_result")
        if step1_json:
            try:
                step1_result = json.loads(str(step1_json))
            except:
                step1_result = str(step1_json)
    
    elif "application/json" in content_type:
        try:
            body = await request.json()
            text_content = body.get("content", "")
            prompt = body.get("prompt", "")
            step = body.get("step", 1)
            step1_result = body.get("step1_result")
        except:
            return {"error": "无效的JSON请求体"}
    
    else:
        return {"error": "不支持的Content-Type，请使用multipart/form-data或application/json"}
    
    ai_config = dict(config_manager.ai)
    if step == 2:
        ai_config['max_tokens'] = 8192
    agent = AIAgent(ai_config)
    
    if step == 1:
        if not text_content:
            return {"error": "第一步需要提供需求文档内容（file或content字段）"}
        
        step1_prompt = load_prompt("step1_analyze.txt")
        if not step1_prompt:
            return {"error": "第一步提示词文件不存在"}
        
        full_prompt = step1_prompt.replace("{{#context#}}", text_content)
        
        if prompt:
            full_prompt += f"\n\n额外要求：{prompt}"
        
    elif step == 2:
        if not step1_result:
            return {"error": "第二步需要提供step1_result（第一步的分析结果）"}
        
        if isinstance(step1_result, dict):
            context_content = step1_result.get("markdown_result", "")
        else:
            context_content = str(step1_result)
        
        if not context_content:
            return {"error": "第一步分析结果为空"}
        
        step2_prompt = load_prompt("step2_coordinate.txt")
        if not step2_prompt:
            return {"error": "第二步提示词文件不存在"}
        
        full_prompt = f"""请根据以下第一步分析结果，生成 Konva.js 地铁图 JSON：

第一步分析结果：
{context_content}

{step2_prompt}"""
        
        if prompt:
            full_prompt += f"\n\n额外要求：{prompt}"
    
    else:
        return {"error": "step参数必须是1或2"}
    
    try:
        result: dict = {"step": step, "think": "", "say": "", "json_result": None}
        
        async for chunk in agent.chat(full_prompt, stream=False):
            if chunk.get("type") == "complete":
                result["think"] = chunk.get("think", "")
                result["say"] = chunk.get("say", "")
            elif chunk.get("type") == "error":
                return {"error": chunk.get("content")}
        
        say_content = str(result.get("say", "")).strip()
        
        if step == 1:
            result["markdown_result"] = say_content
            result["success"] = True
            result["next_step"] = "点击'生成地铁图'按钮，使用此分析结果生成 Konva.js JSON"
        else:
            json_str = extract_json(say_content)
            
            try:
                json_result = json.loads(json_str)
                result["json_result"] = json_result
                result["success"] = True
                
                if not all(key in json_result for key in ["nodes", "paths"]):
                    result["warning"] = "生成的JSON可能缺少必要字段（nodes/paths）"
                    
            except json.JSONDecodeError as e:
                result["json_result"] = None
                result["parse_error"] = str(e)
                result["raw_output"] = say_content
                result["success"] = False
        
        return result
        
    except Exception as e:
        logger.error(f"AI处理失败: {e}")
        return {"error": f"AI处理失败: {str(e)}"}
