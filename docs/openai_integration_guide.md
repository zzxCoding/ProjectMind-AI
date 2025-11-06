# OpenAI API 集成使用指南

本文档介绍如何在 ProjectMind-AI Python 扩展中使用 OpenAI 兼容 API 替代 Ollama。

## 功能概述

项目现在支持两种 LLM 后端：
- **Ollama**: 本地部署的开源大模型服务
- **OpenAI**: OpenAI 官方 API 或兼容服务（vLLM、FastChat、通义千问等）

通过简单的配置切换，无需修改任何业务代码即可在两种后端之间切换。

## 配置方法

### 1. 环境变量配置

编辑项目根目录的 `.env` 文件，添加或修改以下配置：

```bash
# LLM 后端选择
LLM_BACKEND=openai  # 设置为 'openai' 启用 OpenAI API

# OpenAI API 配置
OPENAI_API_BASE=http://your-api-endpoint/v1
OPENAI_API_KEY=sk-your-api-key-here
OPENAI_MODEL=gpt-3.5-turbo
OPENAI_TIMEOUT=60
OPENAI_MAX_TOKENS=4096
OPENAI_TEMPERATURE=0.7
```

### 2. 配置参数说明

| 参数 | 说明 | 示例 |
|-----|------|------|
| `LLM_BACKEND` | 后端类型 | `ollama` 或 `openai` |
| `OPENAI_API_BASE` | API 基础URL（不含尾部斜杠） | `http://localhost:8000/v1` |
| `OPENAI_API_KEY` | API 密钥 | `sk-xxx...` |
| `OPENAI_MODEL` | 默认模型名称 | `gpt-3.5-turbo` |
| `OPENAI_TIMEOUT` | 请求超时时间（秒） | `60` |
| `OPENAI_MAX_TOKENS` | 最大生成 token 数 | `4096` |
| `OPENAI_TEMPERATURE` | 生成温度 | `0.7` |

### 3. 新项目配置

如果是新项目，运行 `./setup.sh` 会自动在 `.env` 文件中生成包含 OpenAI 配置的模板。

## 支持的 OpenAI 兼容服务

### 官方 OpenAI API
```bash
OPENAI_API_BASE=https://api.openai.com/v1
OPENAI_API_KEY=sk-your-openai-key
OPENAI_MODEL=gpt-3.5-turbo
```

### vLLM 服务
```bash
OPENAI_API_BASE=http://localhost:8000/v1
OPENAI_API_KEY=dummy-key
OPENAI_MODEL=your-model-name
```

### FastChat 服务
```bash
OPENAI_API_BASE=http://localhost:8000/v1
OPENAI_API_KEY=dummy-key
OPENAI_MODEL=vicuna-7b
```

### 阿里云通义千问
```bash
OPENAI_API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1
OPENAI_API_KEY=sk-your-qwen-key
OPENAI_MODEL=qwen-turbo
```

## 使用示例

### 命令行测试

```bash
# 1. 激活项目环境
source activate.sh

# 2. 运行测试脚本
python test_llm_backend.py
```

测试脚本会自动检测当前配置的后端，并执行以下测试：
- ✅ 后端检测
- ✅ 文本生成 (generate)
- ✅ 文本分析 (analyze_text)
- ✅ 聊天对话 (chat)

### Python 代码示例

```python
from shared.ollama_client import OllamaClient

# 创建客户端（自动根据环境变量选择后端）
client = OllamaClient()

# 文本生成
result = client.generate(
    model='gpt-3.5-turbo',  # 会使用配置的默认模型
    prompt='请解释什么是Python？'
)
print(result['response'])

# 文本分析
analysis = client.analyze_text(
    text='今天天气很好',
    analysis_type='sentiment'
)
print(analysis)

# 聊天对话
messages = [
    {'role': 'user', 'content': '你好'}
]
result = client.chat(
    model='gpt-3.5-turbo',
    messages=messages
)
print(result['response'])
```

## 在业务模块中使用

### GitLab MR 审查

```bash
# 设置环境变量使用 OpenAI
export LLM_BACKEND=openai

# 运行 MR 审查（自动使用 OpenAI API）
python automation/mr_review_engine.py \
  --project-id 93 \
  --mr-iid 7078 \
  --test-mode
```

### SQL 项目扫描

```bash
# 使用 OpenAI 后端进行 SQL 分析
python automation/sql_project_scanner.py \
  --project-id 93 \
  --version-path "v2.1.*" \
  --branch "main"
```

### SonarQube 缺陷分析

```bash
# 使用 OpenAI 进行代码质量分析
python data_analysis/sonarqube_defect_analyzer.py \
  --project-key YOUR_PROJECT_KEY \
  --use-ai
```

## 参数映射

Ollama 和 OpenAI 的参数自动映射关系：

| Ollama 参数 | OpenAI 参数 | 说明 |
|------------|------------|------|
| `temperature` | `temperature` | 温度参数（0-2） |
| `top_p` | `top_p` | 核采样 |
| `top_k` | - | OpenAI 不支持，自动忽略 |
| `repeat_penalty` | `frequency_penalty` | 重复惩罚（映射公式：`(repeat_penalty - 1.0) * 2.0`） |
| `max_tokens` | `max_tokens` | 最大 token 数 |

## 响应格式统一

无论使用哪个后端，返回的响应格式都是统一的：

```python
{
    'response': '生成的内容',
    'model': 'gpt-3.5-turbo',
    'created_at': '2024-01-01T00:00:00Z',
    'done': True
}
```

## 调试模式

启用调试模式查看详细的 API 请求和响应：

```bash
# 在 .env 中设置
OLLAMA_DEBUG=true

# 或者运行时设置
export OLLAMA_DEBUG=true
python test_llm_backend.py
```

调试模式下会输出：
- API 请求 URL
- 请求参数（JSON 格式）
- 响应内容（前 500 字符）

## 切换回 Ollama

如果需要切换回 Ollama 后端：

```bash
# 在 .env 中修改
LLM_BACKEND=ollama

# 或者运行时设置
export LLM_BACKEND=ollama
```

## 注意事项

### 1. 流式输出
OpenAI 模式暂不支持流式输出 (`stream=True`)，如果设置了该参数会自动降级为非流式模式并显示警告。

### 2. API 密钥安全
- 不要将 API 密钥提交到版本控制系统
- `.env` 文件已在 `.gitignore` 中
- 生产环境建议使用环境变量或密钥管理服务

### 3. 成本控制
使用 OpenAI 官方 API 会产生费用，建议：
- 设置合理的 `OPENAI_MAX_TOKENS` 限制
- 在测试时使用 `--test-mode` 减少 API 调用
- 监控 API 使用量和成本

### 4. 模型兼容性
不同的 OpenAI 兼容服务支持的模型不同，请确保配置的模型名称在目标服务中存在。

## 故障排查

### 问题1: 连接失败
```
❌ OpenAI API 请求失败: Connection refused
```

**解决方法**:
- 检查 `OPENAI_API_BASE` 是否正确
- 确认目标服务是否运行中
- 检查网络连接和防火墙设置

### 问题2: 认证失败
```
❌ OpenAI API 请求失败: 401 Unauthorized
```

**解决方法**:
- 检查 `OPENAI_API_KEY` 是否正确
- 确认 API 密钥是否有效且未过期

### 问题3: 模型不存在
```
❌ OpenAI API 请求失败: 404 Model not found
```

**解决方法**:
- 检查 `OPENAI_MODEL` 配置的模型名称
- 确认目标服务支持该模型
- 查看服务的模型列表

### 问题4: 超时
```
❌ OpenAI API 请求失败: Timeout
```

**解决方法**:
- 增加 `OPENAI_TIMEOUT` 值
- 减少 `OPENAI_MAX_TOKENS`
- 检查网络延迟

## 技术支持

如有问题，请：
1. 查看日志文件：`logs/` 目录
2. 启用调试模式获取详细信息
3. 提交 Issue 到项目仓库

## 更新日志

- **v1.0.0** (2024-01-XX)
  - ✅ 支持 OpenAI 兼容 API
  - ✅ 统一后端接口
  - ✅ 零业务代码改动
  - ✅ 参数自动映射
  - ✅ 调试模式支持
