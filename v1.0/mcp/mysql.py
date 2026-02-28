import sys
import logging
import mysql.connector
from pathlib import Path
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


class MySQLService:
    def __init__(self):
        self.connections = {}
        
    async def connect(self, host: str, port: int = 3306, user: str = "root", password: str = "", database: str = None) -> Dict[str, Any]:
        """连接到MySQL数据库"""
        try:
            # 创建连接
            conn = mysql.connector.connect(
                host=host,
                port=port,
                user=user,
                password=password,
                database=database
            )
            
            # 生成连接ID
            conn_id = f"{host}:{port}:{user}:{database}"
            self.connections[conn_id] = conn
            
            # 获取服务器版本
            cursor = conn.cursor()
            cursor.execute("SELECT VERSION()")
            version = cursor.fetchone()[0]
            cursor.close()
            
            return {
                "success": True,
                "message": "连接成功",
                "conn_id": conn_id,
                "server_version": version,
                "host": host,
                "port": port,
                "user": user,
                "database": database
            }
        except Exception as e:
            logger.error(f"连接MySQL失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def disconnect(self, conn_id: str) -> Dict[str, Any]:
        """断开MySQL连接"""
        try:
            if conn_id in self.connections:
                conn = self.connections[conn_id]
                conn.close()
                del self.connections[conn_id]
                return {
                    "success": True,
                    "message": "断开连接成功"
                }
            return {
                "success": False,
                "error": "连接不存在"
            }
        except Exception as e:
            logger.error(f"断开MySQL连接失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def execute_query(self, conn_id: str, query: str) -> Dict[str, Any]:
        """执行SQL查询"""
        try:
            if conn_id not in self.connections:
                return {
                    "success": False,
                    "error": "连接不存在"
                }
            
            conn = self.connections[conn_id]
            cursor = conn.cursor(dictionary=True)
            
            # 执行查询
            cursor.execute(query)
            
            # 获取结果
            rows = cursor.fetchall()
            field_names = [i[0] for i in cursor.description] if cursor.description else []
            
            cursor.close()
            
            return {
                "success": True,
                "query": query,
                "rows": rows,
                "columns": field_names,
                "row_count": len(rows)
            }
        except Exception as e:
            logger.error(f"执行SQL查询失败: {e}")
            return {
                "success": False,
                "query": query,
                "error": str(e)
            }
    
    async def execute_statement(self, conn_id: str, statement: str) -> Dict[str, Any]:
        """执行SQL语句（INSERT/UPDATE/DELETE等）"""
        try:
            if conn_id not in self.connections:
                return {
                    "success": False,
                    "error": "连接不存在"
                }
            
            conn = self.connections[conn_id]
            cursor = conn.cursor()
            
            # 执行语句
            cursor.execute(statement)
            conn.commit()
            
            # 获取受影响的行数
            row_count = cursor.rowcount
            
            cursor.close()
            
            return {
                "success": True,
                "statement": statement,
                "row_count": row_count
            }
        except Exception as e:
            logger.error(f"执行SQL语句失败: {e}")
            conn.rollback()
            return {
                "success": False,
                "statement": statement,
                "error": str(e)
            }
    
    async def get_databases(self, conn_id: str) -> Dict[str, Any]:
        """获取数据库列表"""
        try:
            return await self.execute_query(conn_id, "SHOW DATABASES")
        except Exception as e:
            logger.error(f"获取数据库列表失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_tables(self, conn_id: str, database: str = None) -> Dict[str, Any]:
        """获取表列表"""
        try:
            if database:
                query = f"SHOW TABLES FROM `{database}`"
            else:
                query = "SHOW TABLES"
            return await self.execute_query(conn_id, query)
        except Exception as e:
            logger.error(f"获取表列表失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_server_info(self, conn_id: str) -> Dict[str, Any]:
        """获取服务器信息"""
        try:
            if conn_id not in self.connections:
                return {
                    "success": False,
                    "error": "连接不存在"
                }
            
            conn = self.connections[conn_id]
            cursor = conn.cursor(dictionary=True)
            
            # 获取版本信息
            cursor.execute("SELECT VERSION() as version")
            version = cursor.fetchone()
            
            # 获取服务器状态
            cursor.execute("SHOW STATUS LIKE 'Uptime' OR Variable_name='Threads_connected' OR Variable_name='Threads_running' OR Variable_name='Questions'")
            status = cursor.fetchall()
            
            cursor.close()
            
            return {
                "success": True,
                "version": version,
                "status": status
            }
        except Exception as e:
            logger.error(f"获取服务器信息失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }


# 创建MySQL服务实例
mysql_service = MySQLService()


# 工具函数定义
async def connect_mysql(host: str, port: int = 3306, user: str = "root", password: str = "", database: str = None) -> Dict[str, Any]:
    """连接到MySQL数据库"""
    return await mysql_service.connect(host, port, user, password, database)


async def disconnect_mysql(conn_id: str) -> Dict[str, Any]:
    """断开MySQL连接"""
    return await mysql_service.disconnect(conn_id)


async def execute_mysql_query(conn_id: str, query: str) -> Dict[str, Any]:
    """执行MySQL查询"""
    return await mysql_service.execute_query(conn_id, query)


async def execute_mysql_statement(conn_id: str, statement: str) -> Dict[str, Any]:
    """执行MySQL语句（INSERT/UPDATE/DELETE等）"""
    return await mysql_service.execute_statement(conn_id, statement)


async def get_mysql_databases(conn_id: str) -> Dict[str, Any]:
    """获取MySQL数据库列表"""
    return await mysql_service.get_databases(conn_id)


async def get_mysql_tables(conn_id: str, database: str = None) -> Dict[str, Any]:
    """获取MySQL表列表"""
    return await mysql_service.get_tables(conn_id, database)


async def get_mysql_server_info(conn_id: str) -> Dict[str, Any]:
    """获取MySQL服务器信息"""
    return await mysql_service.get_server_info(conn_id)


# 工具注册
def register_tools() -> Dict[str, Any]:
    return {
        "connect": connect_mysql,
        "disconnect": disconnect_mysql,
        "query": execute_mysql_query,
        "execute": execute_mysql_statement,
        "get_databases": get_mysql_databases,
        "get_tables": get_mysql_tables,
        "get_server_info": get_mysql_server_info
    }


# 工具定义
def get_tool_definitions() -> List[Dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "mysql_connect",
                "description": "连接到MySQL数据库",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "host": {
                            "type": "string",
                            "description": "MySQL服务器主机名或IP地址"
                        },
                        "port": {
                            "type": "integer",
                            "description": "MySQL服务器端口号，默认3306",
                            "default": 3306
                        },
                        "user": {
                            "type": "string",
                            "description": "MySQL用户名，默认root",
                            "default": "root"
                        },
                        "password": {
                            "type": "string",
                            "description": "MySQL密码"
                        },
                        "database": {
                            "type": "string",
                            "description": "数据库名称，可选"
                        }
                    },
                    "required": ["host", "password"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "mysql_disconnect",
                "description": "断开MySQL连接",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "conn_id": {
                            "type": "string",
                            "description": "连接ID"
                        }
                    },
                    "required": ["conn_id"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "mysql_query",
                "description": "执行MySQL查询",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "conn_id": {
                            "type": "string",
                            "description": "连接ID"
                        },
                        "query": {
                            "type": "string",
                            "description": "SQL查询语句"
                        }
                    },
                    "required": ["conn_id", "query"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "mysql_execute",
                "description": "执行MySQL语句（INSERT/UPDATE/DELETE等）",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "conn_id": {
                            "type": "string",
                            "description": "连接ID"
                        },
                        "statement": {
                            "type": "string",
                            "description": "SQL语句"
                        }
                    },
                    "required": ["conn_id", "statement"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "mysql_get_databases",
                "description": "获取MySQL数据库列表",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "conn_id": {
                            "type": "string",
                            "description": "连接ID"
                        }
                    },
                    "required": ["conn_id"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "mysql_get_tables",
                "description": "获取MySQL表列表",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "conn_id": {
                            "type": "string",
                            "description": "连接ID"
                        },
                        "database": {
                            "type": "string",
                            "description": "数据库名称，可选"
                        }
                    },
                    "required": ["conn_id"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "mysql_get_server_info",
                "description": "获取MySQL服务器信息",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "conn_id": {
                            "type": "string",
                            "description": "连接ID"
                        }
                    },
                    "required": ["conn_id"]
                }
            }
        }
    ]
