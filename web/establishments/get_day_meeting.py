from fastapi import Request
import httpx
import yaml
import time
from pathlib import Path

async def handle(request: Request, config_manager):
    day = request.query_params.get("day", "")

    if not day:
        return {
            "code": 400,
            "message": "缺少day参数",
            "data": [],
            "timestamp": int(time.time() * 1000),
            "executeTime": 0
        }

    # 先尝试调用外部API
    try:
        # 从config_manager获取配置，而不是重新加载
        lubanlou_config = config_manager.lubanlou
        servers = lubanlou_config.get('servers', {'dev': 'https://dev.gvsun.com', 'prod': 'https://www.lubanlou.com'})
        api_config = lubanlou_config.get('api', {}).get('get_day_meeting', {})
        server_key = api_config.get('server', lubanlou_config.get('env', 'dev'))
        server = servers.get(server_key, servers.get('dev'))
        path = api_config.get('path', '')
        url = f"{server}{path}"

        params = {"day": day}

        async with httpx.AsyncClient(timeout=30.0, verify=False) as client:
            headers = {"x-datasource": "limsproduct"}
            response = await client.get(url, params=params, headers=headers)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        print(f"API调用失败: HTTP错误 {e.response.status_code}，将尝试从数据库获取数据")
    except Exception as e:
        print(f"API调用失败: {str(e)}，将尝试从数据库获取数据")
    
    # API调用失败，从数据库获取数据
    try:
        # 导入数据库模块，避免循环导入
        from web.establishments.database import execute_query
        
        sql = f"""
        SELECT
            uid,
            businessType,
            node_name,
            CASE 
                WHEN TRIM(JSON_UNQUOTE(JSON_EXTRACT(attr, '$\.customField\.url'))) = '' 
                    OR JSON_UNQUOTE(JSON_EXTRACT(attr, '$\.customField\.url')) IS NULL 
                THEN CONCAT('https://www.lubanlou.com/teacherInformationCenter/configcenter/organization/organizationalSystemPortal?uid=', uid)
                ELSE JSON_UNQUOTE(JSON_EXTRACT(attr, '$\.customField\.url'))
            END AS url,
            pid,
            created_time,
            updated_time
        FROM
            graph_node_arc_rel
        WHERE
            node_name like '%会%'
            and( (created_time BETWEEN '{day} 00:00:00' AND '{day} 23:00:00')
            or (updated_time BETWEEN '{day} 00:00:00' AND '{day} 23:00:00'))
        """
        
        result = await execute_query(sql)
        return result
    except Exception as e:
        return {
            "code": 500,
            "message": f"数据库查询失败: {str(e)}",
            "data": [],
            "timestamp": int(time.time() * 1000),
            "executeTime": 0
        }