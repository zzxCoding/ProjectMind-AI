#!/usr/bin/env python3
"""
GitLab配置管理
提供GitLab API连接和认证配置
"""

import os
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

@dataclass
class GitLabConfig:
    """GitLab配置类"""
    
    url: str
    token: str
    project_id: Optional[str] = None
    timeout: int = 30
    verify_ssl: bool = True
    
    @classmethod
    def from_env(cls) -> 'GitLabConfig':
        """从环境变量创建配置"""
        return cls(
            url=os.getenv('GITLAB_URL', 'https://gitlab.com'),
            token=os.getenv('GITLAB_TOKEN', ''),
            project_id=os.getenv('GITLAB_PROJECT_ID'),
            timeout=int(os.getenv('GITLAB_TIMEOUT', '30')),
            verify_ssl=os.getenv('GITLAB_VERIFY_SSL', 'true').lower() == 'true'
        )
    
    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> 'GitLabConfig':
        """从字典创建配置"""
        return cls(**config_dict)
    
    def validate(self) -> bool:
        """验证配置有效性"""
        if not self.url:
            raise ValueError("GitLab URL不能为空")
        if not self.token:
            raise ValueError("GitLab Token不能为空")
        return True
    
    def get_api_url(self, endpoint: str = '') -> str:
        """获取API URL"""
        base_url = self.url.rstrip('/')
        if endpoint:
            return f"{base_url}/api/v4/{endpoint.lstrip('/')}"
        return f"{base_url}/api/v4"

# 预定义的GitLab实例配置
DEFAULT_CONFIGS = {
    'gitlab.com': {
        'url': 'https://gitlab.com',
        'description': 'GitLab.com 公共实例'
    },
    'github.com': {
        'url': 'https://api.github.com',
        'description': 'GitHub API (兼容模式)'
    }
}

def get_default_config() -> GitLabConfig:
    """获取默认配置"""
    return GitLabConfig.from_env()

def load_config_from_file(config_path: str) -> GitLabConfig:
    """从配置文件加载"""
    import json
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
        return GitLabConfig.from_dict(config_data)
    except FileNotFoundError:
        raise FileNotFoundError(f"配置文件不存在: {config_path}")
    except json.JSONDecodeError as e:
        raise ValueError(f"配置文件格式错误: {e}")

if __name__ == "__main__":
    # 测试配置
    try:
        config = get_default_config()
        config.validate()
        print("✅ GitLab配置验证成功")
        print(f"   URL: {config.url}")
        print(f"   Token: {'*' * (len(config.token) - 4) + config.token[-4:] if config.token else 'Not Set'}")
        print(f"   Project ID: {config.project_id or 'Not Set'}")
    except Exception as e:
        print(f"❌ GitLab配置验证失败: {e}")