#!/usr/bin/env python3
"""
Ollama配置模块
管理Ollama服务连接和模型配置
"""

import os
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class OllamaConfig:
    """Ollama服务配置"""
    host: str = "localhost"
    port: int = 11434
    timeout: int = 30
    default_model: str = "llama2"
    
    @classmethod
    def from_env(cls) -> 'OllamaConfig':
        """从环境变量创建配置"""
        return cls(
            host=os.getenv('OLLAMA_HOST', cls.host),
            port=int(os.getenv('OLLAMA_PORT', cls.port)),
            timeout=int(os.getenv('OLLAMA_TIMEOUT', cls.timeout)),
            default_model=os.getenv('OLLAMA_MODEL', cls.default_model)
        )
    
    def get_base_url(self) -> str:
        """获取Ollama基础URL"""
        return f"http://{self.host}:{self.port}"
    
    def get_api_url(self, endpoint: str = "") -> str:
        """获取API URL"""
        base_url = self.get_base_url()
        if endpoint:
            return f"{base_url}/api/{endpoint.lstrip('/')}"
        return f"{base_url}/api"

def get_default_ollama_config() -> OllamaConfig:
    """获取默认Ollama配置"""
    return OllamaConfig.from_env()

# 常用模型配置
MODEL_CONFIGS = {
    "llama2": {
        "name": "llama2",
        "description": "Meta Llama 2 通用模型",
        "context_length": 4096,
        "good_for": ["对话", "文本生成", "问答"]
    },
    "llama2:13b": {
        "name": "llama2:13b",
        "description": "Meta Llama 2 13B 模型",
        "context_length": 4096,
        "good_for": ["复杂推理", "长文本处理"]
    },
    "codellama": {
        "name": "codellama", 
        "description": "Code Llama 代码专用模型",
        "context_length": 4096,
        "good_for": ["代码生成", "代码分析", "编程协助"]
    },
    "mistral": {
        "name": "mistral",
        "description": "Mistral 7B 模型",
        "context_length": 8192,
        "good_for": ["快速推理", "多语言支持"]
    }
}

def get_available_models() -> List[str]:
    """获取可用模型列表"""
    return list(MODEL_CONFIGS.keys())

def get_model_info(model_name: str) -> Optional[dict]:
    """获取模型信息"""
    return MODEL_CONFIGS.get(model_name)

if __name__ == "__main__":
    config = OllamaConfig.from_env()
    print(f"Ollama服务URL: {config.get_base_url()}")
    print(f"API URL: {config.get_api_url()}")
    print(f"默认模型: {config.default_model}")
    print(f"可用模型: {get_available_models()}")