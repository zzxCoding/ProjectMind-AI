# GitLab分支创建流水线使用指南

## 概述

GitLab分支创建流水线是一个用于创建版本分支的自动化工具，主要功能包括：

- 🔍 **MR状态检查** - 创建版本分支前检查源分支是否有未合并的请求
- 🌿 **自动分支创建** - 基于源分支创建版本分支
- ✅ **命名规范校验** - 支持多种版本号格式验证
- 🔄 **批量创建** - 支持批量创建多个版本分支
- 🔒 **并发安全** - 使用文件锁防止并发操作冲突

## 主要功能

### 1. MR状态检查

在创建版本分支前，工具会检查：

- **传出MR** - 从源分支发出的未合并请求
- **传入MR** - 指向源分支的未合并请求
- **总计统计** - 显示所有相关未合并请求

### 2. 版本命名规范

支持多种版本号格式：

| 模式 | 格式 | 示例 |
|------|------|------|
| `semantic` | 语义化版本 | `v1.0.0`, `2.1.3-beta`, `3.0.0-rc1` |
| `major_minor` | 主次版本 | `v1.0`, `2.1-beta` |
| `date_based` | 日期版本 | `2024.01.15`, `2024.12.31` |
| `custom` | 自定义格式 | `hotfix_123`, `release_candidate` |

### 3. 安全检查

- 源分支存在性验证
- 目标分支冲突检查
- 分支名称合法性验证
- 未合并MR警告机制

## 安装和配置

### 依赖要求

```bash
cd /Users/xuan/worksapce/ProjectMind-AI
pip install -r requirements.txt
```

### 配置GitLab连接

确保`config/gitlab_config.py`已正确配置：

```python
GITLAB_CONFIG = {
    'url': 'http://your-gitlab-server',
    'private_token': 'your-access-token',
    'project_id': 'your-project-id'
}
```

### 配置WPS Webhook通知（可选）

当分支创建成功后，系统可以自动调用WPS Webhook发送通知。

#### 环境变量配置（推荐）

在`.env`文件中配置：

```bash
# WPS Webhook URL（必需）
export WPS_WEBHOOK_URL="https://your-webhook-endpoint.com/notify"

# Origin头部值（二选一）
export WPS_WEBHOOK_ORIGIN="www.wps.cn"
# 或
export WPS_WEBHOOK_ORIGIN="www.kdocs.cn"

# 自定义JSON内容（可选）
export WPS_WEBHOOK_CUSTOM_JSON='{"app": "branch-creator", "env": "prod"}'
```

#### 命令行参数配置

```bash
python automation/branch_creation_pipeline.py \
  --project-id 93 \
  --source-branch main \
  --version v1.2.3 \
  --webhook-url https://your-webhook-endpoint.com/notify \
  --webhook-origin www.kdocs.cn \
  --webhook-json '{"project": "my-project", "team": "backend"}'
```

#### Webhook请求详情

- **请求方法**: 支持 POST 和 GET（默认POST）
- **Origin头部**: POST请求时必填，支持 `www.kdocs.cn` 或 `www.wps.cn`
- **数据格式**:
  ```json
  {
    "project_id": "93",
    "source_branch": "main",
    "version_branch": "v1.2.3",
    "commit": "abc123def456",
    "commit_short": "abc123d",
    "created_at": "2024-01-15T10:30:00",
    "status": "success",
    "app": "branch-creator",
    "env": "prod"
  }
  ```
  *注：最后两个字段来自自定义JSON*

## 使用方法

### 基本用法

#### 1. 创建单个版本分支

```bash
python automation/branch_creation_pipeline.py \
  --project-id 1 \
  --source-branch develop \
  --version v2.1.0
```

#### 2. 创建分支并发送WPS通知

```bash
python automation/branch_creation_pipeline.py \
  --project-id 93 \
  --source-branch main \
  --version v1.2.3 \
  --webhook-url https://api.example.com/branch-created \
  --webhook-origin www.wps.cn \
  --webhook-json '{"notify_team": "backend"}'
```

#### 3. 使用GET请求发送通知

```bash
python automation/branch_creation_pipeline.py \
  --project-id 93 \
  --source-branch main \
  --version v1.2.3 \
  --webhook-url https://api.example.com/branch-created \
  --webhook-method GET \
  --webhook-origin www.kdocs.cn
```

#### 4. 检查分支的未合并MR

```bash
# 这个命令会在创建分支前自动检查MR
python automation/branch_creation_pipeline.py \
  --project-id 1 \
  --source-branch develop \
  --version v2.1.0
```

### 高级用法

#### 1. 强制创建（忽略未合并MR）

```bash
python automation/branch_creation_pipeline.py \
  --project-id 1 \
  --source-branch develop \
  --version v2.1.0 \
  --force-create
```

#### 2. 使用不同的命名规范

```bash
# 日期版本
python automation/branch_creation_pipeline.py \
  --project-id 1 \
  --source-branch develop \
  --version 2024.01.15 \
  --pattern-type date_based

# 自定义格式
python automation/branch_creation_pipeline.py \
  --project-id 1 \
  --source-branch develop \
  --version hotfix_123 \
  --pattern-type custom
```

#### 3. 跳过MR检查

```bash
python automation/branch_creation_pipeline.py \
  --project-id 1 \
  --source-branch develop \
  --version v2.1.0 \
  --skip-mr-check
```

### 批量创建

#### 1. 从文件批量创建

创建版本列表文件 `versions.txt`：

```
v2.1.0
v2.1.1
v2.2.0-beta
v2.2.0-rc1
v2.2.0
```

然后执行：

```bash
python automation/branch_creation_pipeline.py \
  --project-id 1 \
  --source-branch develop \
  --batch-mode \
  --versions-file versions.txt
```

#### 2. 从标准输入批量创建

```bash
echo -e "v2.1.0\nv2.1.1\nv2.2.0" | \
python automation/branch_creation_pipeline.py \
  --project-id 1 \
  --source-branch develop \
  --batch-mode
```

## 输出示例

### 成功创建版本分支

```
✅ 版本分支创建成功
  项目ID: 1
  源分支: develop
  版本分支: v2.1.0
  提交: a1b2c3d4
  创建时间: 2024-01-15T10:30:45.123456
  执行时间: 2.34s

📋 MR检查结果:
  传出MR: 0 个
  传入MR: 0 个
  总计: 0 个
```

### 成功创建并发送Webhook通知

```
✅ 版本分支创建成功
  项目ID: 93
  源分支: main
  版本分支: v1.2.3
  提交: abc123d
  创建时间: 2024-01-15T10:30:00
  执行时间: 3.45s

📡 WPS Webhook 通知: ✅ 发送成功
```

### Webhook发送失败

```
✅ 版本分支创建成功
  项目ID: 93
  源分支: main
  版本分支: v1.2.3
  提交: abc123d
  创建时间: 2024-01-15T10:30:00
  执行时间: 3.45s

📡 WPS Webhook 通知: ❌ 发送失败
  错误: Webhook 请求超时
```

### 因未合并MR而失败

```
❌ 版本分支创建失败
  错误: 分支 develop 有 2 个未合并的MR

📋 未合并的MR:
  !15 - 修复登录bug (张三 -> main)
  !16 - 添加新功能 (李四 -> main)
  执行时间: 1.23s
```

### 批量创建结果

```
📊 批量创建完成，共 5 个版本
成功: 3, 失败: 2
  ✅ v2.1.0 (commit: a1b2c3d4)
  ✅ v2.1.1 (commit: e5f6g7h8)
  ❌ v2.2.0-beta - 分支 v2.2.0-beta 已存在
  ✅ v2.2.0-rc1 (commit: i9j0k1l2)
  ❌ v2.2.0 - 分支 develop 有 1 个未合并的MR
```

## 命令行参数

### 必需参数

| 参数 | 描述 |
|------|------|
| `--project-id` | GitLab项目ID |
| `--source-branch` | 源分支名称 |
| `--version` | 版本名称（单版本模式） |

### 批量模式参数

| 参数 | 描述 |
|------|------|
| `--batch-mode` | 启用批量模式 |
| `--versions-file` | 版本列表文件路径 |

### 验证选项

| 参数 | 可选值 | 默认值 | 描述 |
|------|--------|--------|------|
| `--pattern-type` | semantic, major_minor, date_based, custom | semantic | 分支名称验证模式 |
| `--force-create` | - | False | 强制创建（忽略未合并MR） |
| `--skip-mr-check` | - | False | 跳过未合并MR检查 |

### 其他选项

| 参数 | 描述 |
|------|------|
| `--log-level` | 日志级别 (DEBUG, INFO, WARNING, ERROR) |
| `--lock-timeout` | 锁等待超时时间（秒） |

### WPS Webhook配置参数

| 参数 | 可选值 | 默认值 | 描述 |
|------|--------|--------|------|
| `--webhook-url` | - | 环境变量 | WPS Webhook URL地址 |
| `--webhook-method` | POST, GET | POST | Webhook请求方法 |
| `--webhook-origin` | www.kdocs.cn, www.wps.cn | www.wps.cn | Origin头部值（POST时必填） |
| `--webhook-json` | - | `{}` | 自定义JSON内容（字符串格式） |

### 环境变量

| 变量名 | 必需 | 默认值 | 说明 |
|--------|------|--------|------|
| `WPS_WEBHOOK_URL` | ✅ | - | WPS Webhook URL地址 |
| `WPS_WEBHOOK_ORIGIN` | ❌ | www.wps.cn | Origin头部值 |
| `WPS_WEBHOOK_CUSTOM_JSON` | ❌ | `{}` | 自定义JSON内容 |

## 常见使用场景

### 1. 发布版本前检查

```bash
# 在发布v2.1.0版本前，确保所有相关MR已合并
python automation/branch_creation_pipeline.py \
  --project-id 1 \
  --source-branch develop \
  --version v2.1.0
```

### 2. 创建补丁版本

```bash
# 基于主分支创建热修复版本
python automation/branch_creation_pipeline.py \
  --project-id 1 \
  --source-branch main \
  --version v2.1.1 \
  --force-create  # 热修复可能需要强制创建
```

### 3. 批量创建版本分支

```bash
# 为一个版本系列创建多个候选版本
echo -e "v3.0.0-alpha\nv3.0.0-beta\nv3.0.0-rc1\nv3.0.0" | \
python automation/branch_creation_pipeline.py \
  --project-id 1 \
  --source-branch develop \
  --batch-mode
```

## 错误处理和故障排除

### 常见错误

1. **分支已存在**
   ```
   错误: 分支 v2.1.0 已存在
   ```
   解决：使用不同的版本名或删除现有分支

2. **源分支不存在**
   ```
   错误: 源分支 feature-xyz 不存在
   ```
   解决：检查源分支名称是否正确

3. **未合并的MR**
   ```
   错误: 分支 develop 有 2 个未合并的MR
   ```
   解决：合并相关MR或使用`--force-create`强制创建

4. **版本名称格式错误**
   ```
   错误: 分支名称验证失败: 分支名称不符合 semantic 模式
   ```
   解决：使用正确的版本号格式或更换验证模式

### 调试模式

使用DEBUG日志级别获取详细信息：

```bash
python automation/branch_creation_pipeline.py \
  --project-id 1 \
  --source-branch develop \
  --version v2.1.0 \
  --log-level DEBUG
```

### 权限问题

确保GitLab访问令牌具有以下权限：
- `read_repository` - 读取仓库
- `read_api` - 读取API
- `write_repository` - 写入仓库（创建分支）

### Webhook故障排除

#### 1. Webhook URL未配置

**现象**：未看到Webhook通知发送

**解决方案**：
```bash
export WPS_WEBHOOK_URL="https://your-webhook-url.com"
```

#### 2. Origin头部错误

**现象**：Webhook返回403 Forbidden

**解决方案**：
```bash
--webhook-origin www.wps.cn
# 或
--webhook-origin www.kdocs.cn
```

#### 3. 自定义JSON格式错误

**现象**：解析自定义JSON失败警告

**解决方案**：
```bash
# 正确的JSON格式
--webhook-json '{"key": "value", "num": 123}'

# 错误的JSON格式（会导致警告但不会中断）
--webhook-json '{key: value}'  # 错误！
```

#### 4. 测试Webhook

使用curl测试Webhook是否可用：

```bash
curl -X POST \
  -H "Origin: www.wps.cn" \
  -H "Content-Type: application/json" \
  -d '{"project_id": "93", "test": true}' \
  https://your-webhook-url.com/notify
```

## 最佳实践

1. **版本命名规范**
   - 使用语义化版本号（如`v1.0.0`）
   - 包含预发布标识（如`-beta`, `-rc1`）
   - 保持命名一致性

2. **发布流程**
   - 先使用MR检查功能确认没有遗漏的功能
   - 在非高峰时间创建版本分支
   - 保留版本分支的创建记录

3. **分支管理**
   - 定期清理不需要的版本分支
   - 使用保护分支功能防止意外修改
   - 为重要版本打标签

4. **Webhook通知**
   - 配置WPS Webhook自动通知团队成员
   - 使用自定义JSON添加项目标识和环境信息
   - 在通知失败时记录日志以便排查问题
   - 为不同环境（dev/staging/prod）配置不同的Webhook URL

5. **自动化集成**
   - 与CI/CD流水线集成
   - 在版本创建后自动触发构建
   - 发送通知给相关团队

## 示例脚本

### 发布流程脚本

```bash
#!/bin/bash
# release.sh - 自动化发布脚本

PROJECT_ID="1"
SOURCE_BRANCH="develop"
VERSION=$1

if [ -z "$VERSION" ]; then
    echo "用法: $0 <版本号>"
    exit 1
fi

echo "开始发布版本 $VERSION..."

# 检查并创建版本分支
python automation/branch_creation_pipeline.py \
  --project-id $PROJECT_ID \
  --source-branch $SOURCE_BRANCH \
  --version $VERSION

if [ $? -eq 0 ]; then
    echo "✅ 版本 $VERSION 创建成功"
    echo "🔗 请在GitLab中查看新分支: $VERSION"
else
    echo "❌ 版本创建失败，请检查日志"
    exit 1
fi
```

### 批量版本准备脚本

```bash
#!/bin/bash
# prepare_versions.sh - 批量准备版本

PROJECT_ID="1"
SOURCE_BRANCH="develop"

# 创建版本列表
cat > versions.txt << EOF
v$(date +%Y.%m.%d)-dev
v$(date +%Y.%m.%d)-qa
v$(date +%Y.%m.%d)-staging
EOF

echo "准备版本分支..."
python automation/branch_creation_pipeline.py \
  --project-id $PROJECT_ID \
  --source-branch $SOURCE_BRANCH \
  --batch-mode \
  --versions-file versions.txt

echo "版本准备完成！"
```

## 总结

GitLab分支创建流水线提供了安全、可靠的版本分支创建功能，通过MR状态检查确保版本发布的完整性，支持多种命名规范和批量操作，是DevOps流程中的重要工具。

**主要特性**：
- 🔍 MR状态检查 - 创建前自动检查未合并请求
- 🌿 自动分支创建 - 基于源分支快速创建版本分支
- ✅ 命名规范校验 - 支持多种版本号格式验证
- 🔄 批量创建 - 支持批量创建多个版本分支
- 📡 WPS Webhook通知 - 创建成功后自动发送通知
- 🔒 并发安全 - 使用文件锁防止并发操作冲突

**WPS Webhook支持**：
- 支持POST和GET请求
- 兼容www.kdocs.cn和www.wps.cn Origin头部
- 支持自定义JSON数据
- 完善的错误处理机制
- 支持环境变量和命令行参数配置

更多问题请参考项目文档或提交Issue。