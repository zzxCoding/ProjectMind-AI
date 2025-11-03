# SQL项目扫描器文档

## 概述

SQL项目扫描器是一个基于GitLab和AI的SQL文件异常扫描工具，专门设计用于扫描多数据库类型（MySQL、Oracle、DB2）的SQL脚本，使用AI技术进行异常检测和分析。

## 功能特点

- 🎯 **版本路径支持**: 支持精确匹配、模糊匹配和正则表达式匹配
- 🗄️ **多数据库类型**: 自动识别MySQL、Oracle、DB2脚本
- 🤖 **AI智能分析**: 使用Ollama模型进行SQL异常检测
- ⚡ **高效并发**: 使用线程池并发处理多个文件
- 📊 **详细报告**: 支持控制台、文本、JSON多种输出格式
- 🔧 **灵活配置**: 支持自定义AI模型和参数
- 🌿 **分支支持**: 支持指定GitLab分支进行扫描

## 安装和配置

### 环境要求

- Python 3.8+
- Ollama服务
- GitLab访问权限

### 配置文件

配置文件位置：`examples/sql_project_config.json`

```json
{
  "projects": {
    "93": {
      "name": "核心业务系统",
      "version_base_path": "database/versions",
      "db_type_patterns": {
        "mysql": ["**/*.mysql.sql", "**/mysql/**/*.sql"],
        "oracle": ["**/*.oracle.sql", "**/oracle/**/*.sql"],
        "db2": ["**/*.db2.sql", "**/db2/**/*.sql"],
        "default": ["**/*.sql"]
      },
      "ai_analysis": {
        "model": "qwen:7b",
        "temperature": 0.7,
        "top_p": 0.9,
        "max_tokens": 2000,
        "analysis_depth": "standard",
        "enable_thinking": false,
        "focus_areas": ["语法错误", "性能问题", "安全风险"],
        "custom_instructions": ""
      }
    }
  }
}
```

## 使用方法

### 基本语法

```bash
python automation/sql_project_scanner.py --project-id PROJECT_ID --version-path VERSION_PATH [选项]
```

### 常用参数

| 参数 | 说明 | 示例 |
|------|------|------|
| `--project-id` | 项目ID（必需） | `93` |
| `--version-path` | 版本路径（必需） | `"v2.1.*"` |
| `--branch` | 指定扫描分支 | `"main"` |
| `--config` | 配置文件路径 | `custom_config.json` |
| `--db-type` | 数据库类型过滤 | `mysql` |
| `--output` | 输出格式 | `console\|text\|json` |

### AI模型参数

| 参数 | 说明 | 默认值 | 示例 |
|------|------|--------|------|
| `--model` | 自定义AI模型 | `qwen:7b` | `llama2:13b` |
| `--temperature` | AI温度参数 | `0.7` | `0.3` |
| `--top-p` | AI top_p参数 | `0.9` | `0.9` |
| `--max-tokens` | 最大输出令牌数 | `2000` | `3000` |
| `--enable-thinking` | 启用思考过程 | `false` | `-` |
| `--analysis-depth` | 分析深度 | `standard` | `deep` |
| `--focus-areas` | 重点关注领域 | - | `"安全风险" "性能问题"` |
| `--custom-instructions` | 自定义指令 | - | `"请特别关注事务处理"` |

## 使用示例

### 1. 基本使用

```bash
# 扫描项目93的v2.1版本
python automation/sql_project_scanner.py --project-id 93 --version-path "v2.1.*"
```

### 2. 自定义AI模型

```bash
# 使用llama2:13b模型进行分析
python automation/sql_project_scanner.py --project-id 93 --version-path "v2.1.*" --model "llama2:13b"
```

### 3. 深度分析

```bash
# 版本发布前的深度分析
python automation/sql_project_scanner.py --project-id 93 --version-path "v2.1.*" --analysis-depth deep --enable-thinking
```

### 4. 快速检查

```bash
# 日常快速检查
python automation/sql_project_scanner.py --project-id 93 --version-path "v2.1.*" --analysis-depth quick
```

### 5. 专注特定领域

```bash
# 重点关注安全和性能
python automation/sql_project_scanner.py --project-id 93 --version-path "v2.1.*" --focus-areas "安全风险" "性能问题"
```

### 6. 自定义指令

```bash
# 添加自定义分析要求
python automation/sql_project_scanner.py --project-id 93 --version-path "v2.1.*" --custom-instructions "请特别关注事务处理和并发问题"
```

### 7. 指定扫描分支

```bash
# 扫描main分支
python automation/sql_project_scanner.py --project-id 93 --version-path "v2.1.*" --branch "main"

# 扫描开发分支
python automation/sql_project_scanner.py --project-id 93 --version-path "v2.1.*" --branch "develop"

# 扫描功能分支
python automation/sql_project_scanner.py --project-id 93 --version-path "v2.1.*" --branch "feature/new-function"
```

## 版本路径匹配

### 精确匹配
```bash
--version-path "v2.1.3"          # 匹配 database/versions/v2.1.3
--version-path "release/2024/Q1"  # 匹配 database/versions/release/2024/Q1
```

### 模糊匹配
```bash
--version-path "v2.1.*"          # 匹配所有v2.1.x版本
--version-path "v2.*"            # 匹配所有v2.x版本
--version-path "*"                # 匹配所有版本
```

### 正则匹配
```bash
--version-path "v2\\.[0-9]+\\.[0-9]+"     # 匹配标准版本号
--version-path "20[0-9]{2}.*"              # 匹配2000-2099年版本
```

### 多版本扫描
```bash
--version-path "v2.1.3,v2.0.5"    # 扫描多个指定版本
```

## 数据库类型识别

工具会自动识别SQL文件的数据库类型：

### 识别规则
1. **路径匹配**: 根据文件路径中的关键字
2. **扩展名识别**: 
   - `.mysql.sql` 或 `.mysql` → MySQL
   - `.oracle.sql` 或 `.oracle` → Oracle  
   - `.db2.sql` 或 `.db2` → DB2
3. **内容检测**: 可扩展的内容识别

### 配置示例
```json
{
  "db_type_patterns": {
    "mysql": ["**/*.mysql.sql", "**/mysql/**/*.sql"],
    "oracle": ["**/*.oracle.sql", "**/oracle/**/*.sql"],
    "db2": ["**/*.db2.sql", "**/db2/**/*.sql"],
    "default": ["**/*.sql"]
  }
}
```

## AI分析能力

### 分析维度
- **语法检查**: SQL语法正确性、关键字使用、命名规范
- **性能分析**: 索引使用、查询优化、性能瓶颈
- **安全检查**: SQL注入风险、权限控制、敏感数据
- **逻辑分析**: 业务逻辑、数据一致性、事务处理
- **最佳实践**: 代码规范、可维护性、文档完整性

### 分析深度

#### 快速分析 (quick)
- 明显的语法错误
- 严重的性能问题
- 关键的安全风险

#### 标准分析 (standard)
- 完整的语法检查
- 性能问题识别
- 安全风险评估
- 逻辑一致性检查

#### 深度分析 (deep)
- 详细的执行计划分析
- 复杂查询的性能影响评估
- 潜在的并发问题
- 长期维护性评估

## 输出报告

### 控制台输出
实时显示扫描进度和结果统计，适合快速查看。

### 文本报告
生成详细的文本格式报告，包含完整的分析结果。

### JSON报告
生成结构化的JSON格式报告，便于后续处理和分析。

## 实际应用场景

### 版本发布前检查
```bash
python automation/sql_project_scanner.py \
  --project-id 93 \
  --version-path "v2.1.*" \
  --branch "main" \
  --analysis-depth deep \
  --model "llama2:13b" \
  --output text
```

### 日常快速检查
```bash
python automation/sql_project_scanner.py \
  --project-id 93 \
  --version-path "v2.1.*" \
  --branch "develop" \
  --analysis-depth quick \
  --focus-areas "语法错误" "安全风险"
```

### 性能专项审计
```bash
python automation/sql_project_scanner.py \
  --project-id 93 \
  --version-path "v2.1.*" \
  --branch "main" \
  --focus-areas "性能问题" \
  --custom-instructions "重点关注索引和查询优化"
```

### 安全专项审计
```bash
python automation/sql_project_scanner.py \
  --project-id 93 \
  --version-path "v2.1.*" \
  --branch "main" \
  --focus-areas "安全风险" \
  --temperature 0.1 \
  --analysis-depth deep
```

### 不同分支对比扫描
```bash
# 扫描main分支
python automation/sql_project_scanner.py \
  --project-id 93 \
  --version-path "v2.1.*" \
  --branch "main" \
  --output json \
  > main_branch_report.json

# 扫描develop分支
python automation/sql_project_scanner.py \
  --project-id 93 \
  --version-path "v2.1.*" \
  --branch "develop" \
  --output json \
  > develop_branch_report.json
```

## 故障排除

### 常见问题

1. **GitLab连接失败**
   - 检查GitLab配置信息
   - 确认网络连接正常
   - 验证访问令牌有效性

2. **Ollama服务不可用**
   - 确认Ollama服务正在运行
   - 检查模型是否已下载
   - 验证服务端口配置

3. **文件获取失败**
   - 确认项目ID正确
   - 检查版本路径是否存在
   - 验证GitLab访问权限

4. **AI分析超时**
   - 调整`--max-tokens`参数
   - 使用`--analysis-depth quick`
   - 检查Ollama服务状态

### 调试技巧

1. **启用详细输出**
   ```bash
   python automation/sql_project_scanner.py --verbose ...
   ```

2. **测试基本连接**
   ```bash
   python test_sql_scanner.py
   ```

3. **检查配置文件**
   ```bash
   python -c "import json; print(json.load(open('examples/sql_project_config.json')))"
   ```

## 最佳实践

### 配置建议
1. **项目配置**: 为每个项目定制合适的路径规则
2. **AI参数**: 根据需求调整模型和参数
3. **分析深度**: 根据使用场景选择合适的深度

### 使用建议
1. **定期扫描**: 建议在版本发布前定期扫描
2. **增量扫描**: 使用版本路径只扫描变更内容
3. **结果记录**: 保存扫描报告用于后续分析

### 性能优化
1. **并发控制**: 调整`max_concurrent_files`参数
2. **文件大小**: 设置合理的`max_file_size`限制
3. **模型选择**: 根据任务复杂度选择合适的模型

## 更新日志

### v1.1.0 (2024-09-22)
- 新增分支扫描支持（--branch参数）
- 优化AI分析参数传递
- 改进GitLab客户端集成
- 更新文档和使用示例

### v1.0.0 (2024-01-22)
- 初始版本发布
- 支持多数据库类型识别
- 集成AI智能分析
- 支持版本路径匹配
- 实现多种输出格式
- 支持自定义AI模型和参数