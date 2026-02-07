from fastapi import Request
import httpx
import yaml
from pathlib import Path
from web.xmgl.database import execute_query


def load_config():
    config_path = Path(__file__).parent.parent.parent / 'config.yaml'
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)



def get_api_url(api_name: str) -> str:
    config = load_config()
    lubanlou = config.get('lubanlou', {})
    servers = lubanlou.get('servers', {'dev': 'https://dev.gvsun.com', 'prod': 'https://www.lubanlou.com'})
    api_config = lubanlou.get('api', {}).get(api_name, {})
    server_key = api_config.get('server', lubanlou.get('env', 'dev'))
    server = servers.get(server_key, servers.get('dev'))
    path = api_config.get('path', '')
    return f"{server}{path}"



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
    url = get_api_url('get_report_from_day')
    params = {"day": day}

    async with httpx.AsyncClient(timeout=30.0, verify=False) as client:
        try:
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
        sql = """
        select * from activity_sync 
        where activity_time = %s
        """

        result = await execute_query(sql, (day,))
        return result
    except Exception as e:
        return {
            "code": 500,
            "message": f"数据库查询失败: {str(e)}",
            "data": [],
            "timestamp": int(time.time() * 1000),
            "executeTime": 0
        }
