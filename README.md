# Python ProjectMind-AI

为ProjectMind-AI系统设计的Python扩展模块，提供强大的数据分析、自动化处理和AI增强功能。

## 🎯 核心特性

- **🔍 智能数据分析** - 日志分析、性能监控、趋势预测
- **🤖 AI增强功能** - 集成Ollama提供智能分析和洞察
- **🔄 自动化处理** - 备份管理、报告生成、多渠道通知
- **🌐 微服务架构** - RESTful API和独立服务模块

## 🏗️ 项目结构

```
python-scripts/
├── config/                      # 配置管理
│   ├── database_config.py       # 数据库连接配置
│   ├── ollama_config.py         # AI服务配置
│   ├── gitlab_config.py         # GitLab API配置
│   ├── review_config.py         # MR审查配置
│   └── paths.py                # 路径配置
├── shared/                      # 共享工具库
│   ├── utils.py                 # 通用工具函数
│   ├── database_client.py       # 数据库操作客户端
│   ├── ollama_client.py         # AI分析客户端
│   ├── gitlab_client.py         # GitLab API客户端
│   └── sonarqube_client.py      # SonarQube API客户端
├── data_analysis/               # 数据分析引擎
│   ├── log_analyzer.py          # 智能日志分析
│   ├── performance_monitor.py   # 性能监控分析
│   ├── trend_analysis.py        # 趋势预测分析
│   ├── gitlab_merge_analyzer.py # GitLab合并记录分析
│   └── sonarqube_defect_analyzer.py # SonarQube缺陷分析器
├── automation/                  # 自动化处理引擎
│   ├── backup_processor.py      # 智能备份管理
│   ├── report_generator.py      # 多格式报告生成
│   ├── notification_sender.py   # 多渠道通知系统
│   ├── mr_review_engine.py      # GitLab MR审查引擎
│   ├── gitlab_mr_interactor.py  # GitLab MR交互器
│   ├── gitlab_branch_merge_pipeline.py # GitLab分支合并流水线
│   ├── branch_creation_pipeline.py # GitLab分支创建流水线
│   └── sql_project_scanner.py   # SQL项目扫描器
├── services/                    # 微服务架构
│   ├── ollama_service.py        # AI分析HTTP服务
│   └── api_gateway.py           # 统一API网关
└── examples/                    # 示例和配置文件
    ├── mr_review_pipeline.py     # GitLab MR审查流水线
    ├── review_config_example.json # 审查配置示例
    └── sql_project_config.json    # SQL扫描器配置示例
```

## 🚀 快速开始

### 5分钟快速体验
```bash
# 1. 一键配置环境（创建虚拟环境、安装依赖、生成配置模板）
./setup.sh

# 2. 激活虚拟环境
source activate.sh

# 3. 测试GitLab MR审查（使用真实的MR数据进行AI代码审查）
python3 examples/mr_review_pipeline.py --project-id 93 --mr-iid 7078 --test-mode
```

### 详细指南
- 📚 **[详细项目指南](docs/PROJECT_GUIDE.md)** - 完整功能介绍和使用手册
- 🤖 **[OpenAI API集成指南](docs/openai_integration_guide.md)** - OpenAI兼容API替代Ollama的配置和使用
- 🔍 **[SonarQube分析器](docs/sonarqube_analyzer_guide.md)** - 代码质量分析专项文档
- 🔗 **[SonarQube集成指南](docs/sonarqube_integration_guide.md)** - SonarQube API集成详解
- 🤖 **[GitLab MR自动审查](docs/mr_review_guide.md)** - 完整的MR自动审查系统使用指南
- 🌿 **[GitLab分支创建流水线](docs/branch_creation_guide.md)** - 自动化版本分支创建工具使用指南
- 🔀 **[GitLab分支合并流水线](docs/gitlab_branch_merge_guide.md)** - 自动化分支合并操作完整指南
- 🗄️ **[SQL项目扫描器](docs/sql_scanner.md)** - 多数据库SQL文件AI异常扫描工具

## 🎯 主要功能

### 🔍 智能数据分析
- **日志分析** - 智能分析执行日志，识别异常模式和性能问题
- **性能监控** - 实时监控系统性能，提供趋势分析和预测
- **趋势分析** - 分析脚本执行趋势，提供数据洞察
- **GitLab分析** - 分析合并记录，评估团队协作效率
- **SonarQube分析** - 代码质量缺陷分析，AI增强报告生成
- **SQL扫描分析** - 多数据库SQL文件AI异常检测，支持MySQL、Oracle、DB2

### 🤖 AI增强功能
- **Ollama集成** - 本地AI模型，提供智能分析和洞察
- **智能建议** - 基于分析结果提供优化建议
- **自然语言处理** - 理解日志内容，自动分类问题

### 🔄 自动化处理
- **备份管理** - 智能备份策略，支持完整和增量备份
- **报告生成** - 多格式报告（HTML/Markdown/JSON）
- **通知系统** - 支持邮件、微信、钉钉等多渠道通知
- **GitLab MR审查** - 自动化的合并请求代码审查，集成SonarQube和AI分析
- **GitLab分支管理** - 自动化分支创建和合并流水线，支持版本发布和MR检查
- **SQL项目扫描** - 版本发布前SQL文件异常扫描，支持多数据库类型和自定义AI模型

### 🌐 微服务架构
- **API网关** - 统一的RESTful API接口
- **独立服务** - 模块化设计，易于扩展和维护

## 🔧 与ProjectMind-AI集成

### 推荐的集成方式
```bash
# 1. 在ProjectMind-AI中添加Python脚本
脚本路径: python-scripts/examples/mr_review_pipeline.py
工作目录: /Users/xuan/worksapce/ProjectMind-AI
默认参数: --project-id 93 --mr-iid 7078 --test-mode

# 2. 使用环境变量切换LLM后端
export LLM_BACKEND=openai  # 使用OpenAI API
export OPENAI_API_KEY=sk-your-key
export OPENAI_MODEL=gpt-3.5-turbo

# 或切换到Ollama
export LLM_BACKEND=ollama
export OLLAMA_MODEL=llama2
```

### 定时任务建议
- **MR自动审查**: `*/5 * * * *` (监控模式，持续审查新的合并请求)
- **每日质量报告**: `0 9 * * 1` (生成周报)
- **SQL项目扫描**: `0 2 * * *` (在版本发布前扫描SQL异常)

## 🔍 故障排查

### 快速诊断
```bash
# 测试数据库连接
python3 shared/database_client.py --test connection

# 测试Ollama服务
python3 shared/ollama_client.py --test health

# 测试GitLab连接
python3 shared/gitlab_client.py --test connection

# 测试SonarQube连接
python3 shared/sonarqube_client.py --test connection

# 测试MR审查功能
python3 examples/mr_review_pipeline.py --project-id 123 --mr-iid 45 --log-level DEBUG

# 测试GitLab分支创建
python3 automation/branch_creation_pipeline.py --project-id 123 --source-branch develop --version v1.0.0

# 测试GitLab分支合并
python3 automation/gitlab_branch_merge_pipeline.py --project-id 123 --source-branch feature/test --target-branch main

# 测试SQL扫描器
python3 test_sql_scanner.py
python3 automation/sql_project_scanner.py --project-id 93 --version-path "v2.1.*" --help

# 启用调试模式
python3 script_name.py --log-level DEBUG
```

## 📈 扩展开发

项目采用模块化设计，易于扩展：
- 添加新的分析脚本到相应模块目录
- 扩展通知渠道支持
- 集成新的AI模型
- 开发自定义API端点

## 📝 更新日志

- **v2.4** (2025-11-05) - 新增OpenAI兼容API支持，可在Ollama和OpenAI API之间灵活切换，零业务代码改动，支持多种兼容服务（vLLM、FastChat、通义千问等）
- **v2.3** (2025-11-05) - 新增GitLab分支管理工具集，包含分支创建流水线和分支合并流水线，支持版本发布前的MR检查和WPS Webhook通知
- **v2.2** (2024-09-22) - 新增SQL项目扫描器，支持多数据库SQL文件AI异常检测，自定义AI模型配置
- **v2.1** (2024-09) - 新增GitLab MR自动审查系统，集成SonarQube和AI智能审查
- **v2.0** (2024-01) - 重构版本，新增SonarQube分析和AI增强功能
- **v1.0** (2023-12) - 初始版本，基础数据分析和自动化功能

## 🤝 贡献

欢迎提交Issue和Pull Request来改进这个项目。

## 📄 许可证

本项目采用MIT许可证。
