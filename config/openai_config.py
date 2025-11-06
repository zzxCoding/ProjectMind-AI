#!/usr/bin/env python3
"""
OpenAI API配置模块
管理OpenAI兼容API服务连接和模型配置
支持标准OpenAI API以及兼容服务（如vLLM、FastChat等）
"""

import os
from dataclasses import dataclass
from typing import Optional

@dataclass
class OpenAIConfig:
    """OpenAI API服务配置"""
    api_base: str = "http://localhost:8000/v1"
    api_key: str = "sk-default-key"
    default_model: str = "gpt-3.5-turbo"
    timeout: int = 60
    max_tokens: int = 4096
    temperature: float = 0.7

    @classmethod
    def from_env(cls) -> 'OpenAIConfig':
        """从环境变量创建配置"""
        return cls(
            api_base=os.getenv('OPENAI_API_BASE', cls.api_base).rstrip('/'),
            api_key=os.getenv('OPENAI_API_KEY', cls.api_key),
            default_model=os.getenv('OPENAI_MODEL', cls.default_model),
            timeout=int(os.getenv('OPENAI_TIMEOUT', cls.timeout)),
            max_tokens=int(os.getenv('OPENAI_MAX_TOKENS', cls.max_tokens)),
            temperature=float(os.getenv('OPENAI_TEMPERATURE', cls.temperature))
        )

    def get_api_url(self, endpoint: str = "") -> str:
        """
        获取API URL

        Args:
            endpoint: API端点，如 'chat/completions'

        Returns:
            完整的API URL
        """
        if endpoint:
            return f"{self.api_base}/{endpoint.lstrip('/')}"
        return self.api_base

    def get_headers(self) -> dict:
        """
        获取API请求头

        Returns:
            包含认证信息的请求头
        """
        return {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }

def get_default_openai_config() -> OpenAIConfig:
    """获取默认OpenAI配置"""
    return OpenAIConfig.from_env()

# 常用OpenAI兼容模型配置
MODEL_CONFIGS = {
    "gpt-3.5-turbo": {
        "name": "gpt-3.5-turbo",
        "description": "OpenAI GPT-3.5 Turbo 模型",
        "context_length": 4096,
        "good_for": ["对话", "文本生成", "问答", "代码生成"]
    },
    "gpt-4": {
        "name": "gpt-4",
        "description": "OpenAI GPT-4 模型",
        "context_length": 8192,
        "good_for": ["复杂推理", "长文本处理", "高级代码分析"]
    },
    "gpt-4-turbo": {
        "name": "gpt-4-turbo",
        "description": "OpenAI GPT-4 Turbo 模型",
        "context_length": 128000,
        "good_for": ["超长文本处理", "复杂任务", "多轮对话"]
    },
    "qwen": {
        "name": "qwen",
        "description": "通义千问模型（需要兼容服务）",
        "context_length": 8192,
        "good_for": ["中文理解", "多语言支持"]
    },
    "deepseek-coder": {
        "name": "deepseek-coder",
        "description": "DeepSeek Coder 代码模型（需要兼容服务）",
        "context_length": 16384,
        "good_for": ["代码生成", "代码分析", "编程协助"]
    }
}

def get_available_models() -> list:
    """获取可用模型列表"""
    return list(MODEL_CONFIGS.keys())

def get_model_info(model_name: str) -> Optional[dict]:
    """获取模型信息"""
    return MODEL_CONFIGS.get(model_name)

if __name__ == "__main__":
    config = OpenAIConfig.from_env()
    print(f"OpenAI API Base URL: {config.api_base}")
    print(f"默认模型: {config.default_model}")
    print(f"最大Tokens: {config.max_tokens}")
    print(f"温度参数: {config.temperature}")
    print(f"可用模型: {get_available_models()}")
