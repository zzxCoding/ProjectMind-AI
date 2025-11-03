"""
配置模块
提供数据库连接、Ollama服务等配置管理
"""

from .database_config import DatabaseConfig
from .ollama_config import OllamaConfig

__all__ = ['DatabaseConfig', 'OllamaConfig']