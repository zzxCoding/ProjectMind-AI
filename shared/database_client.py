#!/usr/bin/env python3
"""
数据库客户端
提供与script_manager数据库交互的功能
"""

import os
import sys
import pymysql
from typing import List, Dict, Any, Optional, Union
from contextlib import contextmanager
from datetime import datetime

# 添加config目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)
from config.database_config import DatabaseConfig
from shared.config_loader import setup_environment
setup_environment()
from shared.utils import setup_logging

class DatabaseClient:
    """数据库客户端"""
    
    def __init__(self, config: Optional[DatabaseConfig] = None):
        """
        初始化数据库客户端
        
        Args:
            config: 数据库配置，默认从环境变量获取
        """
        self.config = config or DatabaseConfig.from_env()
        self.logger = setup_logging()
        
    @contextmanager
    def get_connection(self):
        """获取数据库连接（上下文管理器）"""
        connection = None
        try:
            connection = pymysql.connect(**self.config.get_pymysql_config())
            yield connection
        except Exception as e:
            self.logger.error(f"数据库连接失败: {e}")
            if connection:
                connection.rollback()
            raise
        finally:
            if connection:
                connection.close()
    
    def execute_query(self, sql: str, params: Optional[tuple] = None) -> List[Dict[str, Any]]:
        """
        执行查询SQL
        
        Args:
            sql: SQL语句
            params: 参数元组
            
        Returns:
            查询结果列表
        """
        with self.get_connection() as conn:
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                cursor.execute(sql, params)
                return cursor.fetchall()
    
    def execute_update(self, sql: str, params: Optional[tuple] = None) -> int:
        """
        执行更新SQL
        
        Args:
            sql: SQL语句
            params: 参数元组
            
        Returns:
            影响的行数
        """
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                affected_rows = cursor.execute(sql, params)
                conn.commit()
                return affected_rows
    
    # 脚本相关查询
    def get_all_scripts(self) -> List[Dict[str, Any]]:
        """获取所有脚本"""
        sql = """
        SELECT id, name, description, file_path, default_working_dir, 
               default_arguments, created_at, updated_at
        FROM scripts
        ORDER BY created_at DESC
        """
        return self.execute_query(sql)
    
    def get_script_by_id(self, script_id: int) -> Optional[Dict[str, Any]]:
        """根据ID获取脚本"""
        sql = """
        SELECT id, name, description, file_path, default_working_dir,
               default_arguments, created_at, updated_at
        FROM scripts
        WHERE id = %s
        """
        results = self.execute_query(sql, (script_id,))
        return results[0] if results else None
    
    def get_scripts_by_pattern(self, pattern: str) -> List[Dict[str, Any]]:
        """根据名称模式搜索脚本"""
        sql = """
        SELECT id, name, description, file_path, default_working_dir,
               default_arguments, created_at, updated_at
        FROM scripts
        WHERE name LIKE %s OR description LIKE %s
        ORDER BY created_at DESC
        """
        like_pattern = f"%{pattern}%"
        return self.execute_query(sql, (like_pattern, like_pattern))
    
    # 执行记录相关查询
    def get_executions_by_script(self, script_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """获取脚本的执行记录"""
        sql = """
        SELECT e.id, e.script_id, s.name as script_name, e.status,
               e.start_time, e.end_time, e.log_path
        FROM executions e
        JOIN scripts s ON e.script_id = s.id
        WHERE e.script_id = %s
        ORDER BY e.start_time DESC
        LIMIT %s
        """
        return self.execute_query(sql, (script_id, limit))
    
    def get_recent_executions(self, limit: int = 100) -> List[Dict[str, Any]]:
        """获取最近的执行记录"""
        sql = """
        SELECT e.id, e.script_id, s.name as script_name, e.status,
               e.start_time, e.end_time, e.log_path
        FROM executions e
        JOIN scripts s ON e.script_id = s.id
        ORDER BY e.start_time DESC
        LIMIT %s
        """
        return self.execute_query(sql, (limit,))
    
    def get_execution_stats(self, days: int = 30) -> Dict[str, Any]:
        """获取执行统计信息"""
        sql = """
        SELECT 
            COUNT(*) as total_executions,
            SUM(CASE WHEN status = 'SUCCESS' THEN 1 ELSE 0 END) as success_count,
            SUM(CASE WHEN status = 'FAILED' THEN 1 ELSE 0 END) as failed_count,
            SUM(CASE WHEN status = 'RUNNING' THEN 1 ELSE 0 END) as running_count,
            COUNT(DISTINCT script_id) as unique_scripts
        FROM executions
        WHERE start_time >= DATE_SUB(NOW(), INTERVAL %s DAY)
        """
        results = self.execute_query(sql, (days,))
        return results[0] if results else {}
    
    def get_script_execution_stats(self, script_id: int, days: int = 30) -> Dict[str, Any]:
        """获取单个脚本的执行统计"""
        sql = """
        SELECT 
            s.name as script_name,
            COUNT(e.id) as total_executions,
            SUM(CASE WHEN e.status = 'SUCCESS' THEN 1 ELSE 0 END) as success_count,
            SUM(CASE WHEN e.status = 'FAILED' THEN 1 ELSE 0 END) as failed_count,
            MAX(e.start_time) as last_execution,
            AVG(TIMESTAMPDIFF(SECOND, e.start_time, e.end_time)) as avg_duration
        FROM scripts s
        LEFT JOIN executions e ON s.id = e.script_id 
            AND e.start_time >= DATE_SUB(NOW(), INTERVAL %s DAY)
        WHERE s.id = %s
        GROUP BY s.id, s.name
        """
        results = self.execute_query(sql, (days, script_id))
        return results[0] if results else {}
    
    # 定时任务相关查询
    def get_scheduled_tasks(self) -> List[Dict[str, Any]]:
        """获取所有定时任务"""
        sql = """
        SELECT st.id, st.script_id, s.name as script_name, st.cron_expression,
               st.enabled, st.created_at, st.updated_at
        FROM scheduled_tasks st
        JOIN scripts s ON st.script_id = s.id
        ORDER BY st.created_at DESC
        """
        return self.execute_query(sql)
    
    def get_active_scheduled_tasks(self) -> List[Dict[str, Any]]:
        """获取启用的定时任务"""
        sql = """
        SELECT st.id, st.script_id, s.name as script_name, st.cron_expression,
               st.enabled, st.created_at, st.updated_at
        FROM scheduled_tasks st
        JOIN scripts s ON st.script_id = s.id
        WHERE st.enabled = 1
        ORDER BY st.created_at DESC
        """
        return self.execute_query(sql)
    
    # 用户相关查询
    def get_users(self) -> List[Dict[str, Any]]:
        """获取所有用户"""
        sql = """
        SELECT id, username, created_at, updated_at
        FROM users
        ORDER BY created_at DESC
        """
        return self.execute_query(sql)
    
    def test_connection(self) -> bool:
        """测试数据库连接"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT 1")
                    result = cursor.fetchone()
                    return result is not None
        except Exception as e:
            self.logger.error(f"数据库连接测试失败: {e}")
            return False

if __name__ == "__main__":
    # 测试数据库客户端
    import argparse
    
    parser = argparse.ArgumentParser(description="数据库客户端测试")
    parser.add_argument('--test', choices=['connection', 'scripts', 'executions', 'stats'], 
                       default='connection', help='测试类型')
    args = parser.parse_args()
    
    client = DatabaseClient()
    
    if args.test == 'connection':
        print("测试数据库连接...")
        if client.test_connection():
            print("✅ 数据库连接成功")
        else:
            print("❌ 数据库连接失败")
    
    elif args.test == 'scripts':
        print("获取脚本列表...")
        scripts = client.get_all_scripts()
        print(f"找到 {len(scripts)} 个脚本:")
        for script in scripts[:5]:  # 只显示前5个
            print(f"  - {script['name']}: {script['description']}")
    
    elif args.test == 'executions':
        print("获取最近执行记录...")
        executions = client.get_recent_executions(10)
        print(f"最近 {len(executions)} 次执行:")
        for execution in executions:
            print(f"  - {execution['script_name']}: {execution['status']} ({execution['start_time']})")
    
    elif args.test == 'stats':
        print("获取执行统计...")
        stats = client.get_execution_stats()
        print(f"统计信息:")
        print(f"  - 总执行次数: {stats.get('total_executions', 0)}")
        print(f"  - 成功次数: {stats.get('success_count', 0)}")
        print(f"  - 失败次数: {stats.get('failed_count', 0)}")
        print(f"  - 运行中: {stats.get('running_count', 0)}")
        print(f"  - 涉及脚本数: {stats.get('unique_scripts', 0)}")