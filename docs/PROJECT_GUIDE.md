# ProjectMind-AI Python扩展项目指南

## 📖 项目概述

这是一个为ProjectMind-AI系统设计的Python扩展模块，提供强大的数据分析、自动化处理和AI增强功能。该项目完全集成到现有的Java后端系统中，扩展了系统的分析和自动化能力。

### 🎯 设计目标
- **无缝集成**：与现有Java后端ProjectMind-AI完美配合
- **模块化设计**：每个功能独立，便于维护和扩展
- **AI增强**：集成Ollama提供智能分析能力
- **生产就绪**：提供完整的错误处理、日志记录和监控

## 🏗️ 系统架构

```mermaid
graph TB
    A[Java后端 ProjectMind-AI] --> B[Python脚本执行]
    A --> C[Web界面管理]
    
    B --> D[数据分析模块]
    B --> E[自动化模块] 
    B --> F[服务模块]
    
    D --> D1[日志分析]
    D --> D2[性能监控]
    D --> D3[趋势预测]
    
    E --> E1[备份管理]
    E --> E2[报告生成]
    E --> E3[通知发送]
    
    F --> F1[Ollama AI服务]
    F --> F2[API网关]
    
    G[(MySQL数据库)] --> A
    G --> B
    
    H[Ollama AI] --> F1
    I[邮件/微信/钉钉] --> E3
```

## 📁 详细目录说明

### `/config` - 配置管理
```
config/
├── __init__.py              # 配置模块入口
├── database_config.py       # 数据库连接配置
├── ollama_config.py         # AI服务配置
└── gitlab_config.py         # GitLab API配置
```

**核心功能**：
- 统一的配置管理
- 环境变量支持
- 默认值和验证

### `/shared` - 共享工具库
```
shared/
├── __init__.py              # 工具库入口
├── utils.py                 # 通用工具函数
├── database_client.py       # 数据库操作客户端
├── ollama_client.py         # AI分析客户端
└── gitlab_client.py         # GitLab API客户端
```

**核心功能**：
- 彩色日志系统
- 数据库连接池
- AI模型管理（支持控制思考过程输出）
- 参数解析器

### `/data_analysis` - 数据分析引擎
```
data_analysis/
├── __init__.py
├── log_analyzer.py          # 智能日志分析
├── performance_monitor.py   # 性能监控分析
├── trend_analysis.py        # 趋势预测分析
├── gitlab_merge_analyzer.py # GitLab合并记录分析
└── sonarqube_defect_analyzer.py # SonarQube缺陷分析器
```

**核心功能**：
- 日志模式识别
- 性能指标计算
- 趋势预测算法
- AI增强分析
- SonarQube缺陷检测和分析

### `/automation` - 自动化处理引擎
```
automation/
├── __init__.py
├── backup_processor.py      # 智能备份管理
├── report_generator.py      # 多格式报告生成
└── notification_sender.py   # 多渠道通知系统
```

**核心功能**：
- 增量备份策略
- HTML/Markdown/JSON报告
- 多渠道通知支持

### `/services` - 微服务架构
```
services/
├── __init__.py
├── ollama_service.py        # AI分析HTTP服务
└── api_gateway.py           # 统一API网关
```

**核心功能**：
- RESTful API接口
- 异步任务处理
- 服务健康监控

## 🚀 快速入门指南

### 步骤1：环境准备

```bash
# 进入项目目录
cd /Users/xuan/worksapce/manager/backend/python-scripts

# 创建虚拟环境（推荐）
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 步骤2：配置验证

```bash
# 测试数据库连接
python3 shared/database_client.py --test connection

# 测试Ollama连接（如果已安装）
python3 shared/ollama_client.py --test health

# 查看可用脚本
python3 -c "
import os
for root, dirs, files in os.walk('.'):
    for file in files:
        if file.endswith('.py') and file != '__init__.py':
            print(f'{root}/{file}')
"
```

### 步骤3：基础使用

```bash
# 快速系统健康检查
python3 data_analysis/performance_monitor.py --system --days 1

# 分析最近的执行日志
python3 data_analysis/log_analyzer.py --batch --days 1

# 生成简单报告
python3 automation/report_generator.py --type daily --format text

# GitLab合并记录分析（需配置GITLAB_TOKEN）
python3 data_analysis/gitlab_merge_analyzer.py --project-id YOUR_PROJECT_ID --start-date 2024-01-01 --end-date 2024-01-31 --use-ai

# SonarQube代码质量分析（需配置SONARQUBE_URL和SONARQUBE_TOKEN）
python3 data_analysis/sonarqube_defect_analyzer.py --project-key "your-project-key"

# SonarQube AI增强分析
python3 data_analysis/sonarqube_defect_analyzer.py --project-key "your-project-key" --use-ai --ai-model qwen3:32b
```

## 📚 详细使用手册

### 1. 数据分析功能详解

#### 1.1 日志分析器 (`log_analyzer.py`)

**基础用法**：
```bash
# 分析单个日志文件
python3 data_analysis/log_analyzer.py --log-path logs/execution_1_1756263197572.log

# 分析特定脚本的所有执行日志
python3 data_analysis/log_analyzer.py --script-id 1 --limit 10

# 批量分析最近7天的所有日志
python3 data_analysis/log_analyzer.py --batch --days 7
```

**高级用法**：
```bash
# 使用AI增强分析（需要Ollama）
python3 data_analysis/log_analyzer.py --batch --use-ai

# 输出JSON格式结果
python3 data_analysis/log_analyzer.py --script-id 1 --output-format json

# 分析错误模式和异常
python3 data_analysis/log_analyzer.py --batch --days 1 | grep "ERROR\|FAILED"
```

**输出解读**：
```
=== 日志分析结果 ===
日志总行数: 156
执行时间: 23.45秒
日志级别分布:
  INFO: 134
  WARNING: 15
  ERROR: 7
发现的异常:
  connection: 3个
  permission: 2个
  timeout: 2个
```

#### 1.2 性能监控器 (`performance_monitor.py`)

**系统级监控**：
```bash
# 监控整个系统的性能（最近7天）
python3 data_analysis/performance_monitor.py --system --days 7

# 生成性能趋势分析
python3 data_analysis/performance_monitor.py --trend --days 30

# AI增强的性能分析报告
python3 data_analysis/performance_monitor.py --system --use-ai
```

**脚本级监控**：
```bash
# 监控特定脚本的性能
python3 data_analysis/performance_monitor.py --script-id 1 --days 30

# 对比多个脚本的性能
for id in 1 2 3; do
    python3 data_analysis/performance_monitor.py --script-id $id --days 7
done
```

**性能指标说明**：
- **成功率**: 执行成功的百分比
- **平均执行时间**: 所有执行的平均用时
- **性能等级**: A(优秀) B(良好) C(一般) D(较差) F(差)

#### 1.3 趋势分析器 (`trend_analysis.py`)

**执行趋势分析**：
```bash
# 分析整体执行趋势
python3 data_analysis/trend_analysis.py --type execution --days 30

# 分析脚本流行度变化
python3 data_analysis/trend_analysis.py --type popularity --days 30

# 分析失败趋势
python3 data_analysis/trend_analysis.py --type failure --days 7
```

**特定脚本趋势**：
```bash
# 分析特定脚本的执行趋势
python3 data_analysis/trend_analysis.py --type execution --script-id 1 --days 30
```

#### 1.4 GitLab合并记录分析器 (`gitlab_merge_analyzer.py`)

**功能概述**：
- 分析指定日期范围内每个开发人员的合并记录
- 生成包含AI分析的详细报告  
- 支持多GitLab实例和项目
- 自动发送HTML格式邮件报告

**基础用法（使用环境变量配置）**：
```bash
# 分析单个项目最近30天的合并记录
python3 data_analysis/gitlab_merge_analyzer.py \
  --project-id 12345 \
  --start-date 2024-01-01 \
  --end-date 2024-01-31 \
  --use-ai \
  --ai-model qwen3:32b \
  --output-format html \
  --output-file reports/project_analysis.html

# 分析指定分支的合并记录
python3 data_analysis/gitlab_merge_analyzer.py \
  --project-id 12345 \
  --start-date 2024-01-01 \
  --end-date 2024-01-31 \
  --target-branches main develop release \
  --use-ai \
  --ai-model llama3:8b

# 生成并发送邮件报告
python3 data_analysis/gitlab_merge_analyzer.py \
  --project-id 12345 \
  --start-date 2024-01-01 \
  --end-date 2024-01-31 \
  --use-ai \
  --ai-model qwen3:32b \
  --output-format html \
  --send-email \
  --email-recipients dev-team@company.com manager@company.com
```

**多项目支持（动态配置）**：
```bash
# 分析不同GitLab实例的项目
python3 data_analysis/gitlab_merge_analyzer.py \
  --project-id 67890 \
  --gitlab-url https://gitlab.company.com \
  --gitlab-token glpat-xxxxxxxxxxxxxxxxxxxx \
  --start-date 2024-01-01 \
  --end-date 2024-01-31 \
  --use-ai \
  --ai-model qwen3:32b \
  --send-email \
  --email-recipients team@company.com

# 分析私有GitLab实例（自签名证书）
python3 data_analysis/gitlab_merge_analyzer.py \
  --project-id 999 \
  --gitlab-url https://git.internal.company.com \
  --gitlab-token glpat-private-token \
  --gitlab-verify-ssl false \
  --start-date 2024-01-01 \
  --end-date 2024-01-31 \
  --use-ai \
  --ai-model gemma2:9b \
  --target-branches main staging \
  --send-email \
  --email-recipients internal-team@company.com
```

**批量多项目分析**：
```bash
# 使用配置文件批量分析
python3 examples/batch_analysis.py --config examples/projects_config.json

# 分析指定项目
python3 examples/batch_analysis.py \
  --config examples/projects_config.json \
  --projects "主项目" "移动应用" \
  --days 30

# 自定义时间范围批量分析
python3 examples/batch_analysis.py \
  --config examples/projects_config.json \
  --start-date 2024-01-01 \
  --end-date 2024-01-31

# 试运行（查看将要执行的操作）
python3 examples/batch_analysis.py \
  --config examples/projects_config.json \
  --dry-run
```

**报告格式和内容**：
- **JSON格式**: 结构化数据，便于后续处理
- **Markdown格式**: 易读的文档格式
- **HTML格式**: 美观的网页报告，支持邮件发送

报告包含内容：
- 项目基本信息和统计摘要
- 每个开发者的详细分析（合并数、频率、分支使用）
- AI智能分析和建议
- 合并请求详情（提交数、变更文件数、讨论数）
- 团队协作模式评估

**🤖 AI模型指定功能（新增功能）**：

支持指定不同的AI模型进行分析，提供更灵活的AI分析体验：

```bash
# 使用 Qwen3 32B 模型（推荐，中文支持好，分析质量高）
python3 data_analysis/gitlab_merge_analyzer.py \
  --project-id 12345 \
  --start-date 2024-01-01 \
  --end-date 2024-01-31 \
  --use-ai \
  --ai-model qwen3:32b

# 使用 Llama3 8B 模型（速度快，适合快速分析）
python3 data_analysis/gitlab_merge_analyzer.py \
  --project-id 12345 \
  --start-date 2024-01-01 \
  --end-date 2024-01-31 \
  --use-ai \
  --ai-model llama3:8b

# 使用 Gemma2 9B 模型（Google开发，平衡性能好）
python3 data_analysis/gitlab_merge_analyzer.py \
  --project-id 12345 \
  --start-date 2024-01-01 \
  --end-date 2024-01-31 \
  --use-ai \
  --ai-model gemma2:9b

# 使用自定义模型
python3 data_analysis/gitlab_merge_analyzer.py \
  --project-id 12345 \
  --start-date 2024-01-01 \
  --end-date 2024-01-31 \
  --use-ai \
  --ai-model your-custom-model:latest

# 不指定模型时使用默认模型（从配置文件获取）
python3 data_analysis/gitlab_merge_analyzer.py \
  --project-id 12345 \
  --start-date 2024-01-01 \
  --end-date 2024-01-31 \
  --use-ai
```

**支持的AI模型推荐**：
- **qwen3:32b** - 推荐用于重要分析，中文支持优秀，分析质量高
- **llama3:8b** - 推荐用于日常分析，速度快，资源占用少
- **gemma2:9b** - 推荐用于平衡需求，性能和质量兼顾
- **自定义模型** - 支持任何Ollama兼容的模型

**🔧 重要修复：提交数和变更文件数统计问题**

在v1.2版本中修复了一个重要的统计问题：

**问题描述**：
- 之前版本中，合并请求的提交数和变更文件数统计可能显示为0
- 原因是统计逻辑错误，`commits_count` 错误地使用了 `changes_count` 的值

**修复内容**：
1. **准确获取统计数据**：改为调用 `get_merge_request_details()` 获取真实的提交数和变更文件数
2. **增强错误处理**：当API调用失败时使用fallback逻辑，确保数据完整性
3. **性能优化**：在保证准确性的前提下，优化API调用逻辑

**修复后的功能**：
```bash
# 运行修复后的分析，可以正确获取统计数据
python3 data_analysis/gitlab_merge_analyzer.py \
  --project-id 6936 \
  --start-date 2024-08-01 \
  --end-date 2024-08-31 \
  --use-ai \
  --ai-model qwen3:32b

# 输出示例（修复后）：
# 分支: feature/dev-00-202508-R5832-czk → release/20250731-b05
# 提交数: 3, 变更文件: 5  # 现在会显示正确的数字，而不是0
```

**验证修复效果**：
```bash
# 运行测试脚本验证修复效果
python3 test_gitlab_analyzer.py
```

该测试脚本包含专门的测试函数来验证：
- GitLab API连接状态
- 合并请求详细信息获取
- 统计数据的准确性
- AI分析功能的正常工作

#### 1.5 SonarQube缺陷分析器 (`sonarqube_defect_analyzer.py`)

**功能概述**：
- 基于python-sonarqube-api库的智能缺陷分析
- 支持多格式报告生成（JSON/Markdown/HTML）
- 集成AI分析提供深度洞察
- 自动邮件通知功能
- 支持批量项目分析

**技术栈**：
- **python-sonarqube-api**: SonarQube官方推荐的Python API库
- **ollama**: 本地AI模型集成
- **requests**: HTTP请求处理
- **markdown**: 报告格式化

**基础用法**：
```bash
# 基础项目分析
python3 data_analysis/sonarqube_defect_analyzer.py --project-key "your-project-key"

# 指定严重程度分析
python3 data_analysis/sonarqube_defect_analyzer.py \
  --project-key "your-project-key" \
  --severities CRITICAL BLOCKER \
  --issue-types BUG VULNERABILITY

# 生成JSON报告
python3 data_analysis/sonarqube_defect_analyzer.py \
  --project-key "your-project-key" \
  --output-format json \
  --output-file "analysis_result.json"
```

**AI增强分析**：
```bash
# 启用AI分析
python3 data_analysis/sonarqube_defect_analyzer.py \
  --project-key "your-project-key" \
  --use-ai

# 指定AI模型
python3 data_analysis/sonarqube_defect_analyzer.py \
  --project-key "your-project-key" \
  --use-ai \
  --ai-model "qwen3:32b"

# 发送邮件报告
python3 data_analysis/sonarqube_defect_analyzer.py \
  --project-key "your-project-key" \
  --use-ai \
  --output-format html \
  --send-email \
  --email-recipients "dev-team@company.com" \
  --email-subject "代码质量分析报告"
```

**支持的AI模型推荐**：
- **qwen3:32b** - 推荐用于重要分析，中文支持优秀，分析质量高
- **llama3:8b** - 推荐用于日常分析，速度快，资源占用少
- **gemma2:9b** - 推荐用于平衡需求，性能和质量兼顾
- **codellama:7b** - 专门优化代码理解，适合代码专项分析

**批量项目分析**：
```bash
# 分析多个项目
python3 data_analysis/sonarqube_defect_analyzer.py \
  --project-keys "project1,project2,project3" \
  --use-ai \
  --output-format html \
  --send-email \
  --email-recipients "team@company.com"

# 使用配置文件批量分析
python3 examples/batch_sonarqube_analysis.py \
  --config examples/sonarqube_projects.json \
  --use-ai
```

**报告内容结构**：
- **项目概览**：基本信息、质量门状态、风险等级
- **核心指标**：Bug、漏洞、代码异味统计，测试覆盖率
- **问题分布**：按类型和严重程度分类，安全热点分析
- **AI智能洞察**：整体质量评估，修复建议，优先级排序

**输出解读示例**：
```
=== SonarQube分析结果 ===
项目: my-project
分析时间: 2024-01-15 10:30:00

📊 质量概览:
- Bug数量: 12 (CRITICAL: 2, MAJOR: 10)
- 漏洞数量: 5 (CRITICAL: 1, MAJOR: 4)
- 代码异味: 48
- 测试覆盖率: 78.5%
- 安全评级: B
- 可维护性评级: A

🤖 AI分析建议:
1. 优先修复CRITICAL级别的Bug和漏洞
2. 提高测试覆盖率至85%以上
3. 处理重复代码问题（发现23处重复）
4. 关注安全热点，建议进行代码审查

⚠️ 风险评估: MEDIUM
建议在2周内修复关键问题
```

**环境变量配置**：
```bash
# GitLab配置
export GITLAB_URL="https://gitlab.com"
export GITLAB_TOKEN="your_gitlab_token"
export GITLAB_PROJECT_ID="default_project_id"
export GITLAB_TIMEOUT="30"
export GITLAB_VERIFY_SSL="true"

# 邮件配置
export EMAIL_ENABLED="true"
export SMTP_SERVER="smtp.qq.com"
export EMAIL_USERNAME="your_email@qq.com"
export EMAIL_PASSWORD="your_app_password"

# SonarQube配置
export SONARQUBE_URL="http://your-sonarqube.com:9000"
export SONARQUBE_TOKEN="your_generated_token_here"
export SONARQUBE_TIMEOUT="60"
export SONARQUBE_VERIFY_SSL="true"
```

**多项目配置文件示例** (`examples/projects_config.json`)：
```json
{
  "projects": [
    {
      "name": "主项目",
      "project_id": 12345,
      "gitlab_config": {
        "url": "https://gitlab.com",
        "token": "glpat-main-project-token"
      },
      "default_branches": ["main", "develop"],
      "team_email": "dev-team@company.com"
    },
    {
      "name": "移动应用",
      "project_id": 67890,
      "gitlab_config": {
        "url": "https://gitlab.company.com",
        "token": "glpat-mobile-token",
        "verify_ssl": false
      },
      "default_branches": ["main", "release"],
      "team_email": "mobile-team@company.com"
    },
    {
      "name": "后端服务",
      "sonarqube_config": {
        "project_key": "backend-service",
        "url": "https://sonarqube.company.com",
        "token": "squ-backend-token"
      },
      "team_email": "backend-team@company.com"
    }
  ],
  "default_settings": {
    "use_ai": true,
    "output_format": "html",
    "analysis_period_days": 30
  }
}
```

### 2. 自动化功能详解

#### 2.1 备份处理器 (`backup_processor.py`)

**创建备份**：
```bash
# 创建完整备份（包含所有脚本、日志、数据库元数据）
python3 automation/backup_processor.py --action backup --type full

# 创建增量备份（只备份最近24小时的变更）
python3 automation/backup_processor.py --action backup --type incremental --since-hours 24

# 自定义备份目录
python3 automation/backup_processor.py --action backup --type full --backup-dir /custom/backup/path
```

**管理备份**：
```bash
# 列出所有备份
python3 automation/backup_processor.py --action list

# 恢复完整备份
python3 automation/backup_processor.py --action restore --backup-path /path/to/backup.tar.gz

# 只恢复特定组件
python3 automation/backup_processor.py --action restore --backup-path /path/to/backup.tar.gz --components scripts logs
```

**备份策略建议**：
- 每日增量备份
- 每周完整备份
- 重要变更前手动备份

#### 2.2 报告生成器 (`report_generator.py`)

**标准报告**：
```bash
# 生成今日报告（HTML格式）
python3 automation/report_generator.py --type daily --format html --output daily_report.html

# 生成本周报告（Markdown格式）
python3 automation/report_generator.py --type weekly --format markdown --output weekly_report.md

# 生成本月报告（JSON格式，便于后续处理）
python3 automation/report_generator.py --type monthly --format json --output monthly_report.json
```

**自定义报告**：
```bash
# 生成指定时间范围的报告
python3 automation/report_generator.py --type custom \
    --start-date 2024-01-01 \
    --end-date 2024-01-31 \
    --name "2024年1月运营报告" \
    --format html
```

**AI增强报告**：
```bash
# 使用AI生成洞察和建议
python3 automation/report_generator.py --type daily --use-ai --format html
```

#### 2.3 通知发送器 (`notification_sender.py`)

**配置通知渠道**：

首先设置环境变量：
```bash
# 邮件配置
export EMAIL_ENABLED="true"
export SMTP_SERVER="smtp.qq.com"
export SMTP_PORT="587"
export EMAIL_USERNAME="your_email@qq.com"
export EMAIL_PASSWORD="your_app_password"
export EMAIL_FROM_NAME="ProjectMind-AI"

# 微信配置（企业微信机器人）
export WECHAT_ENABLED="true"
export WECHAT_WEBHOOK="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=your-key"

# 钉钉配置
export DINGTALK_ENABLED="true"
export DINGTALK_WEBHOOK="https://oapi.dingtalk.com/robot/send?access_token=your-token"
export DINGTALK_SECRET="your-secret"
```

**发送通知**：
```bash
# 发送脚本失败告警
python3 automation/notification_sender.py \
    --type failure \
    --script-id 1 \
    --execution-id 123 \
    --recipients admin@company.com ops@company.com \
    --channels email wechat

# 发送系统健康报告
python3 automation/notification_sender.py \
    --type health \
    --recipients admin@company.com \
    --channels email

# 发送定时报告
python3 automation/notification_sender.py \
    --type report \
    --report-type daily \
    --recipients team@company.com \
    --channels email dingtalk

# 发送自定义通知
python3 automation/notification_sender.py \
    --type custom \
    --subject "系统维护通知" \
    --message "系统将于今晚22:00进行维护，预计2小时完成" \
    --recipients all@company.com \
    --channels email wechat dingtalk \
    --priority high
```

### 3. 服务模式使用

#### 3.1 Ollama AI分析服务 (`ollama_service.py`)

**启动服务**：
```bash
# 默认配置启动（localhost:8888）
python3 services/ollama_service.py

# 自定义配置启动
python3 services/ollama_service.py --host 0.0.0.0 --port 8888 --log-level DEBUG

# 测试模式（检查依赖）
python3 services/ollama_service.py --test
```

**API使用示例**：
```bash
# 健康检查
curl http://localhost:8888/health

# 获取可用模型
curl http://localhost:8888/models

# 文本分析
curl -X POST http://localhost:8888/analyze/text \
  -H "Content-Type: application/json" \
  -d '{
    "text": "系统出现大量连接超时错误",
    "type": "sentiment",
    "model": "llama2"
  }'

# 日志分析
curl -X POST http://localhost:8888/analyze/logs \
  -H "Content-Type: application/json" \
  -d '{
    "log_path": "logs/execution_1_1756263197572.log",
    "model": "llama2"
  }'

# 脚本性能分析
curl -X POST http://localhost:8888/analysis/script-performance \
  -H "Content-Type: application/json" \
  -d '{
    "script_id": 1,
    "days": 7,
    "use_ai": true
  }'
```

#### 3.2 API网关服务 (`api_gateway.py`)

**启动网关**：
```bash
# 启动API网关（默认端口9999）
python3 services/api_gateway.py

# 自定义启动
python3 services/api_gateway.py --host 0.0.0.0 --port 9999

# 测试依赖
python3 services/api_gateway.py --test
```

**API使用示例**：
```bash
# 系统健康检查
curl http://localhost:9999/health

# 获取API信息
curl http://localhost:9999/info

# 列出可用脚本
curl http://localhost:9999/scripts

# 执行日志分析
curl -X POST http://localhost:9999/api/v1/analysis/logs \
  -H "Content-Type: application/json" \
  -d '{
    "script_id": 1,
    "use_ai": true
  }'

# 执行性能分析
curl -X POST http://localhost:9999/api/v1/analysis/performance \
  -H "Content-Type: application/json" \
  -d '{
    "system": true,
    "days": 7,
    "use_ai": true
  }'

# 创建备份
curl -X POST http://localhost:9999/api/v1/backup/create \
  -H "Content-Type: application/json" \
  -d '{
    "type": "incremental",
    "since_hours": 24
  }'

# 生成报告
curl -X POST http://localhost:9999/api/v1/reports/generate \
  -H "Content-Type: application/json" \
  -d '{
    "type": "daily",
    "format": "json",
    "use_ai": true
  }'

# 异步执行脚本
curl -X POST http://localhost:9999/api/v1/execute/log_analyzer \
  -H "Content-Type: application/json" \
  -d '{
    "parameters": ["--batch", "--days", "1", "--use-ai"],
    "async": true
  }'

# 获取执行状态
curl http://localhost:9999/api/v1/execution/exec_20240129_143022_123456/status

# 实时仪表板数据
curl http://localhost:9999/api/v1/realtime/dashboard

# 获取活跃告警
curl http://localhost:9999/api/v1/realtime/alerts
```

## 🔧 与Java后端集成

### 在ProjectMind-AI中添加Python脚本

1. **登录Web管理界面**
2. **添加新脚本**，配置示例：

**日志分析脚本**：
- 脚本名称：`Python日志分析`
- 文件路径：`python-scripts/data_analysis/log_analyzer.py`
- 工作目录：`/Users/xuan/worksapce/manager/backend`
- 默认参数：`--batch --days 7 --output-format json`

**性能监控脚本**：
- 脚本名称：`Python性能监控`
- 文件路径：`python-scripts/data_analysis/performance_monitor.py`
- 默认参数：`--system --days 1 --output-format json`

**备份脚本**：
- 脚本名称：`Python自动备份`
- 文件路径：`python-scripts/automation/backup_processor.py`
- 默认参数：`--action backup --type incremental --output-format json`

**GitLab合并记录分析脚本**：
- 脚本名称：`GitLab合并记录分析`
- 文件路径：`python-scripts/data_analysis/gitlab_merge_analyzer.py`
- 工作目录：`/Users/xuan/worksapce/manager/backend`
- 默认参数：`--project-id 12345 --start-date 2024-01-01 --end-date 2024-01-31 --use-ai --ai-model qwen3:32b --output-format html --send-email --email-recipients team@company.com`

**SonarQube代码质量分析脚本**：
- 脚本名称：`SonarQube代码质量分析`
- 文件路径：`python-scripts/data_analysis/sonarqube_defect_analyzer.py`
- 工作目录：`/Users/xuan/worksapce/manager/backend`
- 默认参数：`--project-key your-project-key --use-ai --ai-model qwen3:32b --output-format html --send-email --email-recipients dev-team@company.com`

### 定时任务配置

在Web界面中设置定时任务：

**每日日志分析**：
- Cron表达式：`0 6 * * *` （每天早上6点）
- 脚本：Python日志分析
- 参数：`--batch --days 1 --use-ai`

**每周性能报告**：
- Cron表达式：`0 8 * * 1` （每周一早上8点）
- 脚本：Python性能监控
- 参数：`--system --days 7 --use-ai`

**每日备份**：
- Cron表达式：`0 2 * * *` （每天凌晨2点）
- 脚本：Python自动备份
- 参数：`--action backup --type incremental`

**每周GitLab合并记录分析**：
- Cron表达式：`0 9 * * 1` （每周一早上9点）
- 脚本：GitLab合并记录分析
- 参数：`--project-id 12345 --start-date $(date -d '7 days ago' +%Y-%m-%d) --end-date $(date +%Y-%m-%d) --use-ai --ai-model qwen3:32b --send-email --email-recipients dev-team@company.com`

**每月GitLab团队报告**：
- Cron表达式：`0 10 1 * *` （每月1日上午10点）
- 脚本：GitLab合并记录分析
- 参数：`--project-id 12345 --start-date 2024-01-01 --end-date 2024-01-31 --use-ai --ai-model qwen3:32b --send-email --email-recipients management@company.com`

**每日代码质量检查**：
- Cron表达式：`0 8 * * *` （每天早上8点）
- 脚本：SonarQube代码质量分析
- 参数：`--project-key your-project-key --severities CRITICAL BLOCKER --use-ai --send-email --email-recipients dev-team@company.com`

**周度质量趋势报告**：
- Cron表达式：`0 9 * * 1` （每周一早上9点）
- 脚本：SonarQube代码质量分析
- 参数：`--project-key your-project-key --use-ai --ai-model qwen3:32b --output-format html --send-email --email-recipients management@company.com`

### GitLab多项目管理

**在ProjectMind-AI平台中配置多项目分析**：

**方法1：为每个项目创建独立脚本**

1. **主项目分析脚本**：
   - 脚本名称：`主项目GitLab合并分析`
   - 文件路径：`python-scripts/data_analysis/gitlab_merge_analyzer.py`
   - 默认参数：`--project-id 12345 --start-date 2024-01-01 --end-date 2024-01-31 --use-ai --ai-model qwen3:32b --send-email --email-recipients dev-team@company.com`

2. **移动应用项目分析脚本**：
   - 脚本名称：`移动应用GitLab合并分析`
   - 文件路径：`python-scripts/data_analysis/gitlab_merge_analyzer.py`
   - 默认参数：`--project-id 67890 --gitlab-url https://gitlab.company.com --gitlab-token YOUR_MOBILE_TOKEN --start-date 2024-01-01 --end-date 2024-01-31 --use-ai --ai-model llama3:8b --send-email --email-recipients mobile-team@company.com`

**方法2：使用批量分析脚本**

- 脚本名称：`GitLab多项目批量分析`
- 文件路径：`python-scripts/examples/batch_analysis.py`
- 默认参数：`--config examples/projects_config.json --days 7`

**灵活使用参数**：
由于每次分析的时间范围不同，建议在ProjectMind-AI中：
- 将固定参数放在"默认参数"中（如项目ID、邮件收件人）
- 将变动参数（如日期范围）在执行时手动指定或使用参数变量

**执行时参数示例**：
```bash
# 分析最近7天
--start-date $(date -d '7 days ago' +%Y-%m-%d) --end-date $(date +%Y-%m-%d)

# 分析上个月
--start-date $(date -d 'last month' +%Y-%m-01) --end-date $(date -d 'last month' +%Y-%m-31)

# 分析指定分支
--target-branches main develop release
```

## 🎯 实际应用场景

### 场景1：智能运维监控

**目标**：实现7x24小时智能监控，自动发现问题并告警

**实现方案**：
```bash
# 1. 每小时检查系统健康状态
# Cron: 0 * * * *
python3 data_analysis/performance_monitor.py --system --days 1 | \
python3 automation/notification_sender.py --type health --recipients ops@company.com --channels wechat

# 2. 每天分析日志中的异常模式
# Cron: 0 6 * * *
python3 data_analysis/log_analyzer.py --batch --days 1 --use-ai --output-format json > /tmp/daily_log_analysis.json

# 3. 发现失败率异常时立即告警
python3 data_analysis/performance_monitor.py --system --days 1 | \
awk '/success_rate/ && $2 < 90 { print "告警：系统成功率低于90%" }' | \
xargs -I {} python3 automation/notification_sender.py --type custom --subject "系统告警" --message "{}" --recipients admin@company.com --priority urgent
```

### 场景2：智能报告生成

**目标**：自动生成各类运营报告，提供决策支持

**实现方案**：
```bash
# 每日运营简报
# Cron: 0 7 * * *
python3 automation/report_generator.py --type daily --use-ai --format html --output /var/reports/daily_$(date +%Y%m%d).html
python3 automation/notification_sender.py --type custom --subject "每日运营简报" --message "详见附件" --recipients management@company.com

# 每周性能报告
# Cron: 0 9 * * 1
python3 automation/report_generator.py --type weekly --use-ai --format markdown --output /var/reports/weekly_$(date +%Y%W).md

# 每月深度分析报告
# Cron: 0 10 1 * *
python3 automation/report_generator.py --type monthly --use-ai --format html --output /var/reports/monthly_$(date +%Y%m).html
```

### 场景3：预测性维护

**目标**：基于趋势分析，预测系统问题并提前维护

**实现方案**：
```bash
# 每周趋势分析和预测
# Cron: 0 10 * * 0
python3 data_analysis/trend_analysis.py --type execution --days 30 --use-ai > /tmp/trend_analysis.json

# 基于趋势数据生成维护建议
python3 -c "
import json
with open('/tmp/trend_analysis.json') as f:
    data = json.load(f)
    if 'predictions' in data:
        print('根据趋势分析，建议关注以下问题：')
        for insight in data.get('insights', []):
            print(f'- {insight}')
" | python3 automation/notification_sender.py --type custom --subject "预测性维护建议" --recipients ops@company.com
```

### 场景4：智能代码质量监控

**目标**：实现代码质量的持续监控和智能分析，自动发现和报告代码缺陷

**实现方案**：
```bash
# 每日代码质量检查
# Cron: 0 8 * * *
python3 data_analysis/sonarqube_defect_analyzer.py \
  --project-key "critical-project" \
  --severities CRITICAL BLOCKER \
  --use-ai \
  --ai-model "qwen3:32b" \
  --send-email \
  --email-recipients "dev-team@company.com" \
  --email-subject "每日代码质量报告"

# 周度质量趋势分析
# Cron: 0 9 * * 1
python3 data_analysis/sonarqube_defect_analyzer.py \
  --project-keys "project1,project2,project3" \
  --use-ai \
  --output-format html \
  --output-file "/var/reports/weekly_quality_$(date +%Y%m%d).html"

# 发现严重缺陷时立即告警
python3 data_analysis/sonarqube_defect_analyzer.py \
  --project-key "production-project" \
  --severities CRITICAL \
  --output-format json | \
python3 -c "
import json, sys
data = json.load(sys.stdin)
critical_count = data['summary'].get('critical_issues', 0)
if critical_count > 0:
    print(f'发现{critical_count}个严重缺陷，需要立即处理！')
    sys.exit(1)
" || \
python3 automation/notification_sender.py \
  --type custom \
  --subject "严重缺陷告警" \
  --message "生产项目发现严重缺陷，请立即处理" \
  --recipients "emergency-team@company.com" \
  --priority urgent
```

**质量门集成示例**：
```bash
# 在CI/CD流水线中检查质量门
python3 data_analysis/sonarqube_defect_analyzer.py \
  --project-key "${CI_PROJECT_NAME}" \
  --output-format json \
  --output-file quality-gate.json

# 检查是否通过质量门
python3 -c "
import json
with open('quality-gate.json') as f:
    data = json.load(f)
    if data['summary']['quality_gate_status'] != 'OK':
        print('质量门检查失败！')
        exit(1)
    print('质量门检查通过')
"
```

## 🛠️ 高级配置

### 自定义Ollama模型

```python
# config/ollama_config.py 中添加自定义模型
CUSTOM_MODEL_CONFIGS = {
    "chinese-llama": {
        "name": "chinese-llama",
        "description": "中文优化的Llama模型",
        "context_length": 4096,
        "good_for": ["中文文本分析", "中文日志分析"]
    }
}
```

### 扩展数据库查询

```python
# 在 shared/database_client.py 中添加自定义查询
def get_custom_script_stats(self, date_range: int) -> Dict[str, Any]:
    """获取自定义脚本统计"""
    sql = """
    SELECT s.name, COUNT(e.id) as executions, 
           AVG(TIMESTAMPDIFF(SECOND, e.start_time, e.end_time)) as avg_duration
    FROM scripts s
    LEFT JOIN executions e ON s.id = e.script_id 
    WHERE e.start_time >= DATE_SUB(NOW(), INTERVAL %s DAY)
    GROUP BY s.id, s.name
    ORDER BY executions DESC
    """
    return self.execute_query(sql, (date_range,))
```

### 自定义通知模板

```python
# automation/notification_sender.py 中自定义消息模板
CUSTOM_TEMPLATES = {
    'performance_alert': """
🚨 性能告警

📊 脚本: {script_name}
📈 成功率: {success_rate:.1f}%
⏱️ 平均执行时间: {avg_time:.2f}秒
📅 统计周期: {period}

💡 建议: {recommendations}

🔗 详细报告: {report_link}
    """,
    'maintenance_notice': """
🔧 维护通知

📋 维护内容: {maintenance_type}
🕐 计划时间: {scheduled_time}
⏳ 预计时长: {duration}
📞 联系人: {contact}

⚠️ 影响范围: {impact}
    """
}
```

## 📊 监控和调优

### 性能监控

```bash
# 监控脚本自身的性能
python3 -m cProfile data_analysis/log_analyzer.py --batch --days 1

# 监控内存使用
python3 -c "
import psutil, os
process = psutil.Process(os.getpid())
print(f'内存使用: {process.memory_info().rss / 1024 / 1024:.2f} MB')
"

# 监控数据库连接
python3 shared/database_client.py --test connection
```

### 日志分析

```bash
# 分析脚本执行日志
grep "ERROR" logs/python_scripts.log | tail -20

# 统计各类型操作的频次
grep -E "(分析|备份|报告|通知)" logs/python_scripts.log | \
awk '{print $4}' | sort | uniq -c | sort -rn
```

### 系统调优建议

1. **数据库连接池**：调整`database_client.py`中的连接池大小
2. **并发处理**：在`api_gateway.py`中启用更多worker进程
3. **缓存机制**：为频繁查询添加Redis缓存
4. **日志轮转**：配置日志轮转避免文件过大

## 🔍 故障排查

### 常见问题及解决方案

#### 1. 数据库连接问题
```bash
# 错误：pymysql.err.OperationalError: (2003, "Can't connect to MySQL server")
# 解决：
# 1. 检查数据库服务状态
systemctl status mysql
# 2. 检查网络连通性
telnet 10.0.129.128 3306
# 3. 检查配置
python3 shared/database_client.py --test connection
```

#### 2. Ollama服务不可用
```bash
# 错误：requests.exceptions.ConnectionError
# 解决：
# 1. 检查Ollama服务
curl http://localhost:11434/api/tags
# 2. 启动Ollama服务
ollama serve
# 3. 拉取必要模型
ollama pull llama2
```

#### 3. 权限问题
```bash
# 错误：PermissionError: [Errno 13] Permission denied
# 解决：
# 1. 检查文件权限
ls -la python-scripts/
# 2. 修复权限
chmod +x python-scripts/**/*.py
# 3. 检查目录权限
chmod 755 python-scripts/
```

#### 4. 依赖包缺失
```bash
# 错误：ModuleNotFoundError: No module named 'xxx'
# 解决：
# 1. 重新安装依赖
pip install -r requirements.txt
# 2. 检查虚拟环境
which python3
# 3. 更新pip
pip install --upgrade pip
```

#### 5. SonarQube连接问题
```bash
# 错误：sonarqube.APIError: 401 Unauthorized
# 解决：
# 1. 检查Token是否正确
echo $SONARQUBE_TOKEN

# 2. 重新生成Token
# 登录SonarQube → My Account → Security → Generate new token

# 3. 测试连接
python3 shared/sonarqube_client.py --test connection

# 错误：sonarqube.APIError: 404 Project not found
# 解决：
# 1. 检查项目标识符
python3 shared/sonarqube_client.py --test project --project-key "your-project-key"

# 2. 列出所有可访问的项目
python3 -c "
from shared.sonarqube_client import SonarQubeClient
client = SonarQubeClient()
projects = client.sonar.projects.search_projects()
for p in projects['components']:
    print(f'{p[\"key\"]}: {p[\"name\"]}')
"

# 错误：ModuleNotFoundError: No module named 'sonarqube'
# 解决：
pip install python-sonarqube-api==2.0.5
```

### 调试工具

```bash
# 启用详细日志
python3 script_name.py --log-level DEBUG

# Python调试器
python3 -m pdb script_name.py

# 性能分析
python3 -m cProfile -s cumtime script_name.py

# 内存分析
python3 -m memory_profiler script_name.py
```

## 🔄 版本升级指南

### 从旧版本升级

```bash
# 1. 备份现有配置
cp -r python-scripts python-scripts.backup

# 2. 拉取新版本
git pull origin main

# 3. 更新依赖
pip install -r requirements.txt --upgrade

# 4. 迁移配置
# 手动合并配置文件中的变更

# 5. 测试功能
python3 services/api_gateway.py --test
```

### 版本兼容性

| 版本 | Python要求 | 主要变更 | 兼容性 |
|------|------------|----------|--------|
| v1.0 | Python 3.8+ | 初始版本 | - |
| v1.1 | Python 3.8+ | 增加AI功能 | 向后兼容 |
| v2.0 | Python 3.9+ | API重构 | 需要配置迁移 |

## 📞 技术支持

### 获取帮助

```bash
# 查看脚本帮助
python3 script_name.py --help

# 查看详细文档
python3 -c "
import script_name
help(script_name.main)
"

# 生成支持报告
python3 -c "
import sys, platform
print(f'Python版本: {sys.version}')
print(f'系统版本: {platform.platform()}')
print(f'可用内存: {psutil.virtual_memory().available / 1024 / 1024 / 1024:.2f} GB')
"
```

### 社区资源

- **项目文档**：查看../README.md获取最新信息
- **问题反馈**：通过日志文件收集错误信息
- **功能请求**：在项目中记录Enhancement需求

---

## 📋 快速参考卡片

### 常用命令速查
```bash
# 🔍 系统检查
python3 shared/database_client.py --test connection
python3 shared/ollama_client.py --test health
python3 shared/gitlab_client.py --test connection

# 📊 快速分析
python3 data_analysis/performance_monitor.py --system --days 1
python3 data_analysis/log_analyzer.py --batch --days 1
python3 data_analysis/gitlab_merge_analyzer.py --project-id 12345 --start-date 2024-01-01 --end-date 2024-01-31 --use-ai --ai-model qwen3:32b

# 🔄 自动化任务
python3 automation/backup_processor.py --action backup --type incremental
python3 automation/report_generator.py --type daily --format html

# 🌐 启动服务
python3 services/api_gateway.py --host 0.0.0.0 --port 9999
python3 services/ollama_service.py --host 0.0.0.0 --port 8888

# 📋 GitLab多项目分析
python3 examples/batch_analysis.py --config examples/projects_config.json --days 7
python3 test_gitlab_analyzer.py  # 测试GitLab功能

# 🤖 AI模型测试和使用
python3 shared/ollama_client.py --test models  # 查看可用AI模型
python3 data_analysis/gitlab_merge_analyzer.py --project-id 6936 --start-date 2024-08-01 --end-date 2024-08-31 --use-ai --ai-model qwen3:32b  # 使用指定AI模型

# 🔍 SonarQube代码质量分析
python3 shared/sonarqube_client.py --test connection  # 测试SonarQube连接
python3 data_analysis/sonarqube_defect_analyzer.py --project-key "your-project-key"  # 基础项目分析
python3 data_analysis/sonarqube_defect_analyzer.py --project-key "your-project-key" --use-ai --ai-model qwen3:32b  # AI增强分析
python3 data_analysis/sonarqube_defect_analyzer.py --project-key "your-project-key" --severities CRITICAL BLOCKER --send-email  # 严重缺陷分析并邮件通知
```

### API端点速查
```bash
# 健康检查
curl http://localhost:9999/health

# 执行分析
curl -X POST http://localhost:9999/api/v1/analysis/logs -d '{"batch": true}'

# 创建备份
curl -X POST http://localhost:9999/api/v1/backup/create -d '{"type": "incremental"}'

# 生成报告
curl -X POST http://localhost:9999/api/v1/reports/generate -d '{"type": "daily"}'
```

## 🔧 自定义Python脚本开发指南

### 快速开始 - 添加自定义脚本

**步骤1：选择脚本位置**
```bash
# 根据功能选择合适的目录
data_analysis/     # 数据分析脚本
automation/        # 自动化处理脚本  
services/         # 独立服务脚本
custom_module/    # 新建自定义模块（推荐）
```

**步骤2：创建脚本模板**
```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自定义脚本: 你的脚本名称
功能: 描述脚本功能
"""

import sys
import json
import argparse
from pathlib import Path

# 导入共享工具
sys.path.append(str(Path(__file__).parent.parent))
from shared.utils import setup_logger
from shared.database_client import DatabaseClient

def main():
    parser = argparse.ArgumentParser(description='你的脚本描述')
    parser.add_argument('--log-level', default='INFO', help='日志级别')
    parser.add_argument('--output-format', choices=['text', 'json'], 
                       default='text', help='输出格式')
    # 添加你的自定义参数
    parser.add_argument('--custom-param', help='自定义参数')
    
    args = parser.parse_args()
    logger = setup_logger('custom_script', args.log_level)
    
    try:
        # 你的业务逻辑
        result = process_your_logic(args, logger)
        
        # 输出结果
        if args.output_format == 'json':
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"执行结果: {result}")
            
    except Exception as e:
        logger.error(f"执行失败: {e}")
        sys.exit(1)

def process_your_logic(args, logger):
    """实现你的业务逻辑"""
    logger.info("开始执行自定义逻辑")
    
    # 在这里添加你的代码
    return {"status": "success", "message": "执行完成"}

if __name__ == '__main__':
    main()
```

**步骤3：测试脚本**
```bash
# 本地测试
python3 your_module/your_script.py --help
python3 your_module/your_script.py --log-level DEBUG

# 测试Docker环境（重新构建后）
./deploy.sh
docker exec -it manager-backend python3 python-scripts/your_module/your_script.py
```

**步骤4：添加到管理界面**
在ProjectMind-AI Web界面中添加脚本：
- **脚本名称**: "我的自定义脚本"
- **文件路径**: `python-scripts/your_module/your_script.py`
- **工作目录**: `/app`
- **默认参数**: `--output-format json`

### 开发最佳实践

**1. 使用共享工具**
```python
from shared.utils import setup_logger, format_duration, retry_on_failure
from shared.database_client import DatabaseClient
from shared.ollama_client import OllamaClient  # AI分析能力
```

**2. 标准化输出格式**
```python
# 支持JSON和文本两种输出格式
def output_result(result, format_type):
    if format_type == 'json':
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"=== 执行结果 ===")
        print(f"状态: {result['status']}")
        print(f"消息: {result['message']}")
```

**3. 错误处理和日志**
```python
import logging

def your_function():
    try:
        # 业务逻辑
        pass
    except DatabaseError as e:
        logger.error(f"数据库错误: {e}")
        return {"status": "error", "type": "database", "message": str(e)}
    except Exception as e:
        logger.error(f"未知错误: {e}")
        return {"status": "error", "type": "unknown", "message": str(e)}
```

### 部署流程

**方法1：直接放入容器（推荐）**
```bash
# 1. 复制脚本到容器
docker cp your_script.py manager-backend:/app/scripts/python-scripts/your_module/

# 2. 进入容器并快速设置环境
docker exec -it manager-backend sh
cd /app/scripts/python-scripts
source quick_start.sh

# 3. 测试脚本
python_test    # 快捷命令测试
python3 your_module/your_script.py --help
```

**方法2：通过源码重建（生产环境推荐）**
```bash
# 1. 将脚本添加到源码目录
cp your_script.py backend/python-scripts/your_module/

# 2. 重新构建镜像（自动包含新脚本）
./deploy.sh
```

**优点**：
- ✅ 持久化保存，容器重启不丢失
- ✅ 适合生产环境部署
- ✅ 便于版本控制和团队协作

**方法3：手动添加到Dockerfile**
如需要特殊处理，可以在Dockerfile中添加：
```dockerfile
# 复制自定义脚本
COPY python-scripts/your_module python-scripts/your_module

# 设置执行权限
RUN chmod +x /app/python-scripts/your_module/*.py
```

### 高级功能集成

**1. 集成AI分析**
```python
from shared.ollama_client import OllamaClient

def analyze_with_ai(data):
    ollama = OllamaClient()
    prompt = f"请分析以下数据: {data}"
    return ollama.analyze_text(prompt)
```

**2. 添加API端点**
在`services/api_gateway.py`中添加：
```python
@app.route('/api/v1/custom/your-endpoint', methods=['POST'])
def your_api_endpoint():
    result = execute_python_script('your_module/your_script.py', request.json)
    return jsonify(result)
```

**3. 定时任务配置**
在Web界面中设置定时执行：
```
Cron表达式: 0 */6 * * *  # 每6小时执行一次
脚本参数: --output-format json --custom-param value
```

### 常见问题解决

**Q: 脚本找不到模块？**
```bash
# 确保Python路径正确
sys.path.append(str(Path(__file__).parent.parent))
```

**Q: 权限问题？**
```bash
# Dockerfile中已设置权限，如有问题可手动修复
chmod +x python-scripts/your_module/*.py
```

**Q: 数据库连接失败？**
```bash
# 测试连接
python3 shared/database_client.py --test connection
```

**Q: 服务器上VIRTUAL_ENV环境变量更新失败？**
```bash
# 方法1：直接在容器中设置环境变量
docker exec -it manager-backend bash
export VIRTUAL_ENV=/app/python-scripts/venv
export PATH="$VIRTUAL_ENV/bin:$PATH"

# 方法2：修改activate.sh脚本
docker exec -it manager-backend bash
cd /app/python-scripts
# 编辑activate.sh，手动设置VIRTUAL_ENV
echo 'export VIRTUAL_ENV="'$(pwd)'/venv"' >> activate.sh
echo 'export PATH="$VIRTUAL_ENV/bin:$PATH"' >> activate.sh

# 方法3：绕过虚拟环境直接使用系统Python
# 在Dockerfile中的Python 3.10已经全局安装了依赖
python3 your_script.py  # 直接使用，无需虚拟环境

# 方法4：创建新的环境激活脚本
cat > /app/python-scripts/env.sh << 'EOF'
#!/bin/bash
export VIRTUAL_ENV="/app/python-scripts/venv"
export PATH="$VIRTUAL_ENV/bin:$PATH"
export PYTHONPATH="/app/python-scripts:$PYTHONPATH"
export PYTHON_SCRIPTS_BASE="/app/python-scripts"
EOF
source /app/python-scripts/env.sh
```

**推荐解决方案**：
由于容器环境的特殊性，推荐使用**方法3**直接使用系统Python，因为：
- ✅ Dockerfile已经全局安装了所有依赖包
- ✅ 避免虚拟环境权限和路径问题  
- ✅ 简化容器内的环境管理
- ✅ 更适合Docker化部署

这个项目为你的ProjectMind-AI系统提供了强大的扩展能力，让系统运维变得更加智能和自动化！🚀