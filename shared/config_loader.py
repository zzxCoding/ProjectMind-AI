#!/usr/bin/env python3
"""
配置加载器 - 智能检测环境并加载配置
支持容器和本地环境的自动适配
"""

import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional

class ConfigLoader:
    """智能配置加载器"""
    
    def __init__(self):
        self.project_root = self._detect_project_root()
        self.is_container = self._detect_container_environment()
        self.config = self._load_config()
    
    def _detect_project_root(self) -> Path:
        """检测项目根目录"""
        # 从当前文件往上查找项目根目录
        current = Path(__file__).parent
        while current.parent != current:
            if (current / 'requirements.txt').exists() or (current / 'setup.sh').exists():
                return current
            current = current.parent
        
        # 如果找不到，使用当前脚本的父目录
        return Path(__file__).parent.parent
    
    def _detect_container_environment(self) -> bool:
        """检测是否在容器环境中"""
        return (
            os.path.exists('/.dockerenv') or 
            os.environ.get('DOCKER_CONTAINER') or
            os.path.exists('/app/logs')
        )
    
    def _load_config(self) -> Dict[str, Any]:
        """加载配置"""
        config = {}
        
        # 基础配置
        if self.is_container:
            # 容器环境配置
            config.update({
                'PROJECT_ROOT': '/app/scripts/python-scripts',
                'LOGS_DIR': '/app/logs', 
                'SCRIPTS_BASE_DIR': '/app',
                'SCRIPTS_DIR': '/app/scripts',
                'BACKUP_DIR': '/app/scripts/python-scripts/backups',
                'REPORTS_DIR': '/app/scripts/python-scripts/reports',
                'TEMP_DIR': '/app/scripts/python-scripts/temp',
                'PYTHON_CMD': '/usr/local/bin/python3.10' if os.path.exists('/usr/local/bin/python3.10') else '/usr/bin/python3'
            })
        else:
            # 本地环境配置
            config.update({
                'PROJECT_ROOT': str(self.project_root),
                'LOGS_DIR': str(self.project_root.parent / 'logs'),
                'SCRIPTS_BASE_DIR': str(self.project_root.parent),
                'SCRIPTS_DIR': str(self.project_root.parent / 'scripts'),
                'BACKUP_DIR': str(self.project_root / 'backups'),
                'REPORTS_DIR': str(self.project_root / 'reports'),
                'TEMP_DIR': str(self.project_root / 'temp'),
                'PYTHON_CMD': 'python3'
            })
        
        # 从环境变量覆盖配置
        env_overrides = {
            'PROJECT_ROOT', 'LOGS_DIR', 'SCRIPTS_BASE_DIR', 'BACKUP_DIR',
            'DB_HOST', 'DB_PORT', 'DB_DATABASE', 'DB_USERNAME', 'DB_PASSWORD',
            'OLLAMA_HOST', 'OLLAMA_PORT', 'OLLAMA_MODEL'
        }
        
        for key in env_overrides:
            if key in os.environ:
                config[key] = os.environ[key]
        
        # 加载.env文件（如果存在）
        env_file = self.project_root / '.env'
        if env_file.exists():
            self._load_env_file(str(env_file), config)
        
        return config
    
    def _load_env_file(self, env_path: str, config: Dict[str, Any]):
        """加载.env文件"""
        try:
            with open(env_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip().strip('"\'')
                        
                        # 只覆盖不存在的配置项
                        if key not in config or not config[key]:
                            config[key] = value
        except Exception as e:
            print(f"Warning: Failed to load .env file: {e}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值"""
        return self.config.get(key, default)
    
    def get_path(self, key: str) -> Path:
        """获取路径配置"""
        value = self.get(key)
        return Path(value) if value else Path('.')
    
    def setup_python_path(self):
        """设置Python路径"""
        project_root = str(self.get_path('PROJECT_ROOT'))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
    
    def get_log_path(self, relative_path: str) -> str:
        """获取日志文件的完整路径"""
        if os.path.isabs(relative_path):
            return relative_path
        
        logs_dir = self.get('LOGS_DIR')
        return os.path.join(logs_dir, relative_path)
    
    def ensure_directories(self):
        """确保必要的目录存在"""
        dirs_to_create = ['BACKUP_DIR', 'REPORTS_DIR', 'TEMP_DIR']
        for dir_key in dirs_to_create:
            dir_path = self.get_path(dir_key)
            dir_path.mkdir(parents=True, exist_ok=True)

# 全局配置实例
config = ConfigLoader()

# 便捷函数
def get_config(key: str, default: Any = None) -> Any:
    """获取配置值"""
    return config.get(key, default)

def get_log_path(relative_path: str) -> str:
    """获取日志路径"""
    return config.get_log_path(relative_path)

def setup_environment():
    """设置环境"""
    config.setup_python_path()
    config.ensure_directories()

if __name__ == '__main__':
    # 测试配置
    print("配置测试:")
    print(f"项目根目录: {config.get('PROJECT_ROOT')}")
    print(f"日志目录: {config.get('LOGS_DIR')}")
    print(f"是否容器环境: {config.is_container}")
    print(f"Python命令: {config.get('PYTHON_CMD')}")