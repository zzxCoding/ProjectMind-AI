#!/usr/bin/env python3
"""
数据库配置模块
管理与script_manager数据库的连接配置
"""

import os
from dataclasses import dataclass
from typing import Optional

@dataclass
class DatabaseConfig:
    """数据库连接配置"""
    host: str = "10.0.129.128"
    port: int = 3306
    database: str = "script_manager"
    username: str = "script_manager"
    password: str = "script_manager"
    charset: str = "utf8mb4"
    
    @classmethod
    def from_env(cls) -> 'DatabaseConfig':
        """从环境变量创建配置"""
        return cls(
            host=os.getenv('DB_HOST', cls.host),
            port=int(os.getenv('DB_PORT', cls.port)),
            database=os.getenv('DB_DATABASE', cls.database),
            username=os.getenv('DB_USERNAME', cls.username),
            password=os.getenv('DB_PASSWORD', cls.password),
            charset=os.getenv('DB_CHARSET', cls.charset)
        )
    
    def get_connection_url(self) -> str:
        """获取数据库连接URL"""
        return f"mysql+pymysql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}?charset={self.charset}"
    
    def get_pymysql_config(self) -> dict:
        """获取PyMySQL连接配置"""
        return {
            'host': self.host,
            'port': self.port,
            'user': self.username,
            'password': self.password,
            'database': self.database,
            'charset': self.charset,
            'autocommit': True
        }

if __name__ == "__main__":
    config = DatabaseConfig.from_env()
    print(f"数据库连接URL: {config.get_connection_url()}")
    print(f"PyMySQL配置: {config.get_pymysql_config()}")