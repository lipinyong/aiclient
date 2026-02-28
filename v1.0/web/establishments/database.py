import asyncio
import aiomysql
import json
import time
from datetime import datetime, date

# 数据库配置
DB_CONFIG = {
    'host': '172.31.21.251',
    'user': 'duty_admin',
    'password': 'gIqZ^p8w3F',
    'db': 'gvsun_analysis',
    'charset': 'utf8mb4',
    'cursorclass': aiomysql.cursors.DictCursor
}

async def get_connection():
    """获取数据库连接"""
    return await aiomysql.connect(**DB_CONFIG)

async def execute_query(sql, params=None):
    """执行SQL查询"""
    start_time = time.time()
    connection = None
    cursor = None
    try:
        connection = await get_connection()
        cursor = await connection.cursor()
        await cursor.execute(sql, params)
        result = await cursor.fetchall()
        
        # 将结果转换为JSON可序列化格式
        serializable_result = []
        for row in result:
            serializable_row = {}
            for key, value in row.items():
                if isinstance(value, (datetime, date)):
                    serializable_row[key] = value.isoformat()
                else:
                    serializable_row[key] = value
            serializable_result.append(serializable_row)
        
        end_time = time.time()
        execute_time = int((end_time - start_time) * 1000)  # 转换为毫秒
        
        return {
            "code": 200,
            "message": "success",
            "data": serializable_result,
            "timestamp": int(time.time() * 1000),
            "executeTime": execute_time
        }
    except Exception as e:
        end_time = time.time()
        execute_time = int((end_time - start_time) * 1000)
        return {
            "code": 500,
            "message": f"查询失败: {str(e)}",
            "data": [],
            "timestamp": int(time.time() * 1000),
            "executeTime": execute_time
        }
    finally:
        try:
            if cursor is not None:
                await cursor.close()
        except Exception:
            pass
        
        try:
            if connection is not None:
                await connection.close()
        except Exception:
            pass