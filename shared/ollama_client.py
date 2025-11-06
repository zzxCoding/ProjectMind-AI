#!/usr/bin/env python3
"""
Ollama客户端
提供与Ollama服务交互的功能
"""

import os
import sys
import json
import requests
from typing import Dict, List, Any, Optional, Iterator
from datetime import datetime

# 添加config目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)
from config.ollama_config import OllamaConfig, get_available_models, get_model_info
from shared.config_loader import setup_environment
setup_environment()
from shared.utils import setup_logging

class OllamaClient:
    """
    LLM客户端（支持Ollama和OpenAI兼容API）

    通过环境变量 LLM_BACKEND 控制使用哪个后端：
    - ollama: 使用本地Ollama服务
    - openai: 使用OpenAI兼容API
    """

    def __init__(self, config: Optional[OllamaConfig] = None):
        """
        初始化LLM客户端

        Args:
            config: Ollama配置，默认从环境变量获取（仅在backend=ollama时使用）
        """
        # 检测后端类型
        self.backend = os.getenv('LLM_BACKEND', 'ollama').lower()
        self.logger = setup_logging()

        if self.backend == 'openai':
            # OpenAI API 模式
            from config.openai_config import OpenAIConfig
            self.openai_config = OpenAIConfig.from_env()
            self.config = None  # OpenAI 模式下不使用 OllamaConfig
            self.session = requests.Session()
            self.session.timeout = self.openai_config.timeout
            self.logger.info(f"使用 OpenAI API 后端: {self.openai_config.api_base}")
        else:
            # Ollama 模式
            self.config = config or OllamaConfig.from_env()
            self.openai_config = None
            self.session = requests.Session()
            self.session.timeout = self.config.timeout
            self.logger.info(f"使用 Ollama 后端: {self.config.get_base_url()}")

        self.debug_mode = os.getenv('OLLAMA_DEBUG', 'false').lower() == 'true'
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """
        发起HTTP请求
        
        Args:
            method: HTTP方法
            endpoint: API端点
            **kwargs: requests参数
            
        Returns:
            响应对象
        """
        url = self.config.get_api_url(endpoint)
        
        # Debug模式打印请求信息
        if self.debug_mode:
            self.logger.debug(f"请求方法: {method}")
            self.logger.debug(f"请求URL: {url}")
            if 'json' in kwargs:
                self.logger.debug(f"请求参数: {json.dumps(kwargs['json'], ensure_ascii=False, indent=2)}")
            elif 'data' in kwargs:
                self.logger.debug(f"请求参数: {kwargs['data']}")
            elif 'params' in kwargs:
                self.logger.debug(f"请求参数: {kwargs['params']}")
        
        response = self.session.request(method, url, **kwargs)
        response.raise_for_status()
        return response
    
    def health_check(self) -> bool:
        """
        检查Ollama服务健康状态
        
        Returns:
            服务是否正常
        """
        try:
            response = self._make_request('GET', 'tags')
            return response.status_code == 200
        except Exception as e:
            self.logger.error(f"Ollama健康检查失败: {e}")
            return False
    
    def list_models(self) -> List[Dict[str, Any]]:
        """
        获取可用模型列表
        
        Returns:
            模型列表
        """
        try:
            response = self._make_request('GET', 'tags')
            data = response.json()
            return data.get('models', [])
        except Exception as e:
            self.logger.error(f"获取模型列表失败: {e}")
            return []
    
    def pull_model(self, model_name: str) -> bool:
        """
        拉取模型
        
        Args:
            model_name: 模型名称
            
        Returns:
            是否成功
        """
        try:
            self.logger.info(f"开始拉取模型: {model_name}")
            response = self._make_request('POST', 'pull', json={'name': model_name})
            
            # 处理流式响应
            for line in response.iter_lines():
                if line:
                    data = json.loads(line)
                    if 'status' in data:
                        self.logger.info(f"拉取进度: {data['status']}")
                    if data.get('error'):
                        self.logger.error(f"拉取失败: {data['error']}")
                        return False
            
            self.logger.info(f"模型拉取完成: {model_name}")
            return True
        except Exception as e:
            self.logger.error(f"拉取模型失败: {e}")
            return False
    
    def generate(self, model: str, prompt: str, options: Optional[Dict] = None,
                stream: bool = False, enable_thinking: bool = False,
                format: Optional[str] = None) -> Dict[str, Any]:
        """
        生成文本（支持Ollama和OpenAI后端）

        Args:
            model: 模型名称
            prompt: 输入提示
            options: 生成选项
            stream: 是否流式输出（注意：OpenAI模式暂不支持）
            enable_thinking: 是否启用思考过程输出
            format: 输出格式，可选'json'强制输出JSON格式

        Returns:
            生成结果
        """
        try:
            # 路由到不同的后端
            if self.backend == 'openai':
                # OpenAI API 模式
                if stream:
                    self.logger.warning("OpenAI 后端暂不支持流式输出，使用非流式模式")

                # 将 prompt 转换为 messages 格式
                messages = [{'role': 'user', 'content': prompt}]
                result = self._call_openai_api(messages, model, options, format)

            else:
                # Ollama 模式 - 过滤掉Ollama不支持的参数
                ollama_options = None
                if options:
                    # Ollama支持的参数列表
                    ollama_supported = {
                        'temperature', 'top_p', 'top_k', 'repeat_penalty',
                        'num_predict', 'seed', 'stop'
                    }
                    # 过滤掉不支持的参数（如 do_sample, presence_penalty 等 OpenAI 特有参数）
                    ollama_options = {k: v for k, v in options.items() if k in ollama_supported}

                    # 详细日志记录参数过滤过程
                    if self.debug_mode:
                        self.logger.debug(f"原始参数: {options}")
                        if len(options) != len(ollama_options):
                            removed_params = set(options.keys()) - set(ollama_options.keys())
                            self.logger.debug(f"移除Ollama不支持的参数: {removed_params}")
                        self.logger.debug(f"过滤后参数: {ollama_options}")

                payload = {
                    'model': model,
                    'prompt': prompt,
                    'stream': stream
                }

                if ollama_options:
                    payload['options'] = ollama_options

                if format:
                    payload['format'] = format

                response = self._make_request('POST', 'generate', json=payload)

                if stream:
                    return self._handle_stream_response(response)
                else:
                    result = response.json()

            # 统一的思考过程清理
            if not enable_thinking and 'response' in result:
                result['response'] = self._clean_thinking_output(result['response'])
                # Debug模式打印清理后的response内容
                if self.debug_mode:
                    self.logger.debug(f"清理后的response内容: {result['response'][:500]}...")

            return result

        except Exception as e:
            self.logger.error(f"文本生成失败 ({self.backend} 后端): {e}")
            return {'error': str(e)}
    
    def chat(self, model: str, messages: List[Dict[str, str]],
             options: Optional[Dict] = None, stream: bool = False, enable_thinking: bool = False) -> Dict[str, Any]:
        """
        聊天对话（支持Ollama和OpenAI后端）

        Args:
            model: 模型名称
            messages: 消息列表
            options: 生成选项
            stream: 是否流式输出（注意：OpenAI模式暂不支持）
            enable_thinking: 是否启用思考过程输出

        Returns:
            对话结果
        """
        try:
            # 路由到不同的后端
            if self.backend == 'openai':
                # OpenAI API 模式
                if stream:
                    self.logger.warning("OpenAI 后端暂不支持流式输出，使用非流式模式")

                # 直接使用 messages（已经是OpenAI格式）
                result = self._call_openai_api(messages, model, options)

            else:
                # Ollama 模式 - 过滤掉Ollama不支持的参数
                ollama_options = None
                if options:
                    # Ollama支持的参数列表
                    ollama_supported = {
                        'temperature', 'top_p', 'top_k', 'repeat_penalty',
                        'num_predict', 'seed', 'stop'
                    }
                    # 过滤掉不支持的参数（如 do_sample, presence_penalty 等 OpenAI 特有参数）
                    ollama_options = {k: v for k, v in options.items() if k in ollama_supported}

                    # 详细日志记录参数过滤过程
                    if self.debug_mode:
                        self.logger.debug(f"原始参数: {options}")
                        if len(options) != len(ollama_options):
                            removed_params = set(options.keys()) - set(ollama_options.keys())
                            self.logger.debug(f"移除Ollama不支持的参数: {removed_params}")
                        self.logger.debug(f"过滤后参数: {ollama_options}")

                payload = {
                    'model': model,
                    'messages': messages,
                    'stream': stream
                }

                if ollama_options:
                    payload['options'] = ollama_options

                response = self._make_request('POST', 'chat', json=payload)

                if stream:
                    return self._handle_stream_response(response)
                else:
                    result = response.json()

            # 统一的思考过程清理
            if not enable_thinking and 'response' in result:
                result['response'] = self._clean_thinking_output(result['response'])
                # Debug模式打印清理后的response内容
                if self.debug_mode:
                    self.logger.debug(f"清理后的response内容: {result['response'][:500]}...")

            return result

        except Exception as e:
            self.logger.error(f"聊天对话失败 ({self.backend} 后端): {e}")
            return {'error': str(e)}
    
    def _handle_stream_response(self, response: requests.Response) -> Iterator[Dict[str, Any]]:
        """
        处理流式响应

        Args:
            response: 响应对象

        Yields:
            响应数据片段
        """
        for line in response.iter_lines():
            if line:
                try:
                    data = json.loads(line)
                    yield data
                except json.JSONDecodeError:
                    continue

    def _call_openai_api(self, messages: List[Dict[str, str]], model: str,
                        options: Optional[Dict] = None, format: Optional[str] = None) -> Dict[str, Any]:
        """
        调用OpenAI兼容API

        Args:
            messages: 消息列表（OpenAI格式）
            model: 模型名称
            options: 生成选项
            format: 输出格式

        Returns:
            统一格式的响应
        """
        if not self.openai_config:
            raise RuntimeError("OpenAI配置未初始化")

        # 构建请求payload
        payload = {
            'model': model or self.openai_config.default_model,
            'messages': messages
        }

        # 处理options参数（Ollama风格 -> OpenAI风格）
        if options:
            # 标准OpenAI参数映射
            if 'temperature' in options:
                payload['temperature'] = options['temperature']
            if 'top_p' in options:
                payload['top_p'] = options['top_p']
            if 'max_tokens' in options:
                payload['max_tokens'] = options['max_tokens']
            # repeat_penalty -> frequency_penalty (保守映射)
            # repeat_penalty: 1.0-2.0 → frequency_penalty: 0-1.0 (使用1:1映射，更保守)
            if 'repeat_penalty' in options:
                frequency_penalty = options['repeat_penalty'] - 1.0
                # 限制在OpenAI的推荐范围内 (0-1.0)
                payload['frequency_penalty'] = min(max(frequency_penalty, 0.0), 1.0)

            # 支持OpenAI兼容服务的扩展参数（如vLLM、FastChat等）
            # 这些参数会被传递给API，如果服务不支持会被忽略
            extended_params = ['do_sample', 'presence_penalty', 'top_k', 'seed', 'stop']
            extended_used = []
            for param in extended_params:
                if param in options:
                    payload[param] = options[param]
                    extended_used.append(f"{param}={options[param]}")

            # Debug模式记录扩展参数使用情况
            if extended_used and self.debug_mode:
                self.logger.debug(f"传递扩展参数到OpenAI兼容API: {', '.join(extended_used)}")

        # 如果options中没有temperature，使用默认值
        if 'temperature' not in payload:
            payload['temperature'] = self.openai_config.temperature
        # 如果options中没有max_tokens，使用默认值
        if 'max_tokens' not in payload:
            payload['max_tokens'] = self.openai_config.max_tokens

        # JSON格式输出（如果指定）
        if format == 'json':
            payload['response_format'] = {'type': 'json_object'}

        # Debug模式打印请求信息
        if self.debug_mode:
            self.logger.debug(f"OpenAI API 请求: {self.openai_config.get_api_url('chat/completions')}")
            self.logger.debug(f"请求参数: {json.dumps(payload, ensure_ascii=False, indent=2)}")

        try:
            # 发送请求
            response = self.session.post(
                self.openai_config.get_api_url('chat/completions'),
                json=payload,
                headers=self.openai_config.get_headers(),
                timeout=self.openai_config.timeout
            )
            response.raise_for_status()

            # 解析响应
            openai_result = response.json()

            # 转换为Ollama格式的响应
            result = {
                'response': openai_result['choices'][0]['message']['content'],
                'model': openai_result.get('model', model),
                'created_at': datetime.now().isoformat(),
                'done': True
            }

            # Debug模式打印响应
            if self.debug_mode:
                self.logger.debug(f"OpenAI API 响应: {result['response'][:500]}...")

            return result

        except requests.exceptions.RequestException as e:
            self.logger.error(f"OpenAI API 请求失败: {e}")
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_detail = e.response.json()
                    self.logger.error(f"错误详情: {error_detail}")
                except:
                    self.logger.error(f"错误响应: {e.response.text}")
            raise

    def analyze_text(self, text: str, model: Optional[str] = None,
                    analysis_type: str = "summary", enable_thinking: bool = False) -> str:
        """
        分析文本

        Args:
            text: 待分析文本
            model: 模型名称，默认使用配置中的默认模型
            analysis_type: 分析类型 (summary, sentiment, keywords, etc.)
            enable_thinking: 是否启用思考过程输出，默认False（不显示思考过程）

        Returns:
            分析结果
        """
        if not model:
            # 根据后端类型选择默认模型
            if self.backend == 'openai':
                model = self.openai_config.default_model
            else:
                model = self.config.default_model
        
        # 根据分析类型构建prompt，添加输出控制指令
        
        prompts = {
            "summary": f"请总结以下文本的主要内容:\n\n{text}",
            "sentiment": f"请分析以下文本的情感倾向(积极/消极/中性):\n\n{text}",
            "keywords": f"请提取以下文本的关键词:\n\n{text}",
            "classification": f"请对以下文本进行分类:\n\n{text}",
            "translation": f"请将以下文本翻译成中文:\n\n{text}",
            "custom": f"{text}"  # 对于custom类型，保持原始prompt不变
        }
        
        prompt = prompts.get(analysis_type, f"请分析以下文本:\n\n{text}")
        
        # 使用更新后的generate方法，传递enable_thinking参数
        result = self.generate(model, prompt, enable_thinking=enable_thinking)
        response = result.get('response', result.get('error', '分析失败'))
        
        # 如果不启用思考过程，清理输出中的think标签
        if not enable_thinking:
            response = self._clean_thinking_output(response)
            
        return response
    
    def _clean_thinking_output(self, text: str) -> str:
        """
        清理输出中的think标签内容
        
        Args:
            text: 原始输出文本
            
        Returns:
            清理后的文本
        """
        import re
        
        # 移除 <think>...</think> 标签及其内容
        cleaned = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
        
        # 移除多余的空行
        cleaned = re.sub(r'\n\s*\n\s*\n', '\n\n', cleaned)
        
        # 去除首尾空白
        cleaned = cleaned.strip()
        
        return cleaned
    
    def analyze_logs(self, log_lines: List[str], model: Optional[str] = None, enable_thinking: bool = False) -> str:
        """
        分析日志文件

        Args:
            log_lines: 日志行列表
            model: 模型名称
            enable_thinking: 是否启用思考过程输出，默认False

        Returns:
            分析结果
        """
        if not model:
            # 根据后端类型选择默认模型
            if self.backend == 'openai':
                model = self.openai_config.default_model
            else:
                model = self.config.default_model
        
        log_text = '\n'.join(log_lines[:100])  # 限制日志长度
        
        thinking_instruction = "" if enable_thinking else "\n\n要求：直接给出分析结果，不要包含思考过程。"
        
        prompt = f"""
请分析以下系统日志，提供以下信息:
1. 主要问题或错误
2. 执行状态总结
3. 建议的改进措施

日志内容:
{log_text}{thinking_instruction}
"""
        
        result = self.generate(model, prompt, enable_thinking=enable_thinking)
        response = result.get('response', result.get('error', '日志分析失败'))
        
        # 如果不启用思考过程，清理输出中的think标签
        if not enable_thinking:
            response = self._clean_thinking_output(response)
            
        return response
    
    def analyze_performance_data(self, data: Dict[str, Any], model: Optional[str] = None, enable_thinking: bool = False) -> str:
        """
        分析性能数据

        Args:
            data: 性能数据字典
            model: 模型名称
            enable_thinking: 是否启用思考过程输出，默认False

        Returns:
            分析结果
        """
        if not model:
            # 根据后端类型选择默认模型
            if self.backend == 'openai':
                model = self.openai_config.default_model
            else:
                model = self.config.default_model
        
        data_str = json.dumps(data, indent=2, ensure_ascii=False)
        
        thinking_instruction = "" if enable_thinking else "\n\n要求：直接给出分析结果，不要包含思考过程。"
        
        prompt = f"""
请分析以下性能数据，提供:
1. 性能趋势分析
2. 可能的性能瓶颈
3. 优化建议

性能数据:
{data_str}{thinking_instruction}
"""
        
        result = self.generate(model, prompt, enable_thinking=enable_thinking)
        response = result.get('response', result.get('error', '性能数据分析失败'))
        
        # 如果不启用思考过程，清理输出中的think标签
        if not enable_thinking:
            response = self._clean_thinking_output(response)
            
        return response

if __name__ == "__main__":
    # 测试Ollama客户端
    import argparse
    
    parser = argparse.ArgumentParser(description="Ollama客户端测试")
    parser.add_argument('--test', choices=['health', 'models', 'generate', 'analyze'], 
                       default='health', help='测试类型')
    parser.add_argument('--model', default='llama2', help='模型名称')
    parser.add_argument('--prompt', default='Hello, how are you?', help='测试提示')
    args = parser.parse_args()
    
    client = OllamaClient()
    
    if args.test == 'health':
        print("测试Ollama服务连接...")
        if client.health_check():
            print("✅ Ollama服务正常")
        else:
            print("❌ Ollama服务不可用")
    
    elif args.test == 'models':
        print("获取可用模型...")
        models = client.list_models()
        if models:
            print(f"找到 {len(models)} 个模型:")
            for model in models:
                print(f"  - {model.get('name', 'Unknown')}")
        else:
            print("未找到可用模型")
    
    elif args.test == 'generate':
        print(f"使用模型 {args.model} 生成文本...")
        result = client.generate(args.model, args.prompt)
        if 'error' in result:
            print(f"❌ 生成失败: {result['error']}")
        else:
            print(f"✅ 生成结果: {result.get('response', 'No response')}")
    
    elif args.test == 'analyze':
        print("测试文本分析...")
        test_text = "今天是个好天气，我很高兴能够完成这个项目。"
        result = client.analyze_text(test_text, args.model, "sentiment")
        print(f"情感分析结果: {result}")
        
        # 测试日志分析
        test_logs = [
            "2024-01-01 10:00:00 [INFO] 脚本开始执行",
            "2024-01-01 10:00:01 [WARNING] 数据库连接缓慢",
            "2024-01-01 10:00:05 [ERROR] 文件读取失败: permission denied",
            "2024-01-01 10:00:06 [INFO] 脚本执行完成"
        ]
        result = client.analyze_logs(test_logs, args.model)
        print(f"日志分析结果: {result}")