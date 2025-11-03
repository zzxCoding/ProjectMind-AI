# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概览

这是一个ProjectMind-AI的Python扩展模块，提供数据分析、自动化处理和AI增强功能。项目采用微服务架构，支持智能数据分析、GitLab MR审查、SonarQube代码质量分析、SQL项目扫描等功能。

## 环境设置

### 虚拟环境激活
```bash
source activate.sh
```

### 依赖安装
```bash
# 一键配置（包含虚拟环境创建）
./setup.sh

# 或者手动安装依赖
pip install -r requirements.txt
```

### 环境配置
项目配置通过`.env`文件管理，首次运行`./setup.sh`会自动创建模板配置。

## 核心架构

### 目录结构
- `config/` - 配置管理（数据库、GitLab、SonarQube、Ollama等）
- `shared/` - 共享工具库（数据库客户端、API客户端、工具函数）
- `data_analysis/` - 数据分析引擎（日志分析、性能监控、趋势分析）
- `automation/` - 自动化处理引擎（备份、报告、通知、MR审查、SQL扫描）
- `services/` - 微服务（API网关、AI分析服务）
- `docs/` - 项目文档

### 核心模块

1. **数据库集成** - 通过`shared/database_client.py`与ProjectMind-AI数据库交互
2. **GitLab集成** - 通过`shared/gitlab_client.py`处理MR和代码审查
3. **SonarQube集成** - 通过`shared/sonarqube_client.py`进行代码质量分析
4. **AI功能** - 通过`shared/ollama_client.py`集成Ollama本地AI模型
5. **自动化引擎** - `automation/mr_review_engine.py`实现GitLab MR自动审查

## 常用命令

### 开发测试
```bash
# 测试数据库连接
python shared/database_client.py --test connection

# 测试GitLab连接
python shared/gitlab_client.py --test connection

# 测试SonarQube连接
python shared/sonarqube_client.py --test connection

# 测试Ollama连接
python shared/ollama_client.py --test health

# 系统性能检查
python data_analysis/performance_monitor.py --system --days 1

# 查看帮助
python automation/mr_review_engine.py --help
```

### 服务管理
```bash
# 启动所有服务
./start_services.sh start

# 停止服务
./start_services.sh stop

# 检查服务状态
./start_services.sh status

# 重启服务
./start_services.sh restart
```

### 功能使用
```bash
# GitLab MR审查
python automation/mr_review_engine.py --project-id 93 --mr-iid 7078 --test-mode

# SQL项目扫描
python automation/sql_project_scanner.py --project-id 93 --version-path "v2.1.*" --branch "main"

# GitLab合并记录分析
python data_analysis/gitlab_merge_analyzer.py --project-id 93 --start-date 2024-01-01 --end-date 2024-01-31

# SonarQube缺陷分析
python data_analysis/sonarqube_defect_analyzer.py --project-key YOUR_PROJECT_KEY --use-ai
```

## 测试和调试

### AI功能测试
```bash
# 测试AI审查系统
python test_ai_prompts.py
```

### 日志级别调试
大多数脚本支持`--log-level DEBUG`参数进行详细调试：
```bash
python automation/mr_review_engine.py --project-id 93 --mr-iid 7078 --log-level DEBUG
```

## API集成说明

### 与ProjectMind-AI集成
- 脚本路径：相对于项目根目录，如`python-scripts/data_analysis/performance_monitor.py`
- 工作目录：`/app`
- Python路径：使用虚拟环境中的Python解释器

### 微服务架构
- API网关：默认端口9999
- Ollama服务：默认端口8888
- 服务启动：通过`start_services.sh`管理

## 配置要点

### 必需配置
- 数据库连接（DB_HOST、DB_DATABASE、DB_USERNAME、DB_PASSWORD）
- GitLab Token（GITLAB_TOKEN，用于MR审查功能）
- SonarQube Token（SONARQUBE_TOKEN，用于代码质量分析）

### 可选配置
- Ollama AI模型（OLLAMA_ENABLED=true启用）
- 邮件/微信/钉钉通知
- 备份和报告路径

## 文档参考

项目包含详细文档：
- `docs/PROJECT_GUIDE.md` - 完整项目指南
- `docs/mr_review_guide.md` - GitLab MR自动审查指南
- `docs/sql_scanner.md` - SQL项目扫描器指南
- `docs/sonarqube_integration_guide.md` - SonarQube集成指南

## 开发注意事项

1. **路径管理** - 使用`config.paths.py`中的路径配置，避免硬编码
2. **配置加载** - 通过`shared/config_loader.py`统一管理配置
3. **日志处理** - 使用统一日志系统，支持彩色输出和文件记录
4. **异步处理** - HTTP请求和文件操作支持异步处理
5. **错误处理** - 统一异常处理机制，详细的错误信息