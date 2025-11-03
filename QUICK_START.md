# ProjectMind-AI Python扩展 - 快速开始

## ⚡ 5分钟快速体验

### 第一步：检查环境
```bash
# 检查Python版本（需要3.8+）
python3 --version

# 进入项目目录
cd /Users/xuan/worksapce/manager/backend/python-scripts

# 安装依赖
pip install -r requirements.txt
```

### 第二步：测试连接
```bash
# 测试数据库连接
python3 shared/database_client.py --test connection

# 如果看到 "✅ 数据库连接成功" 就表示正常
```

### 第三步：运行第一个分析
```bash
# 快速系统性能检查
python3 data_analysis/performance_monitor.py --system --days 1

# 你会看到类似这样的输出：
# === 系统性能分析 ===
# 系统健康度: Good
# 整体成功率: 95.2%
# 脚本数量: 8
```

### 第四步：生成第一个报告
```bash
# 生成今天的简单报告
python3 automation/report_generator.py --type daily --format text

# 输出示例：
# === DAILY报告 ===
# 总执行次数: 156
# 成功率: 94.2%
# 平均执行时间: 12.34秒
```

### 第五步：在Web界面中添加Python脚本

1. 打开你的ProjectMind-AI Web界面
2. 点击 "添加脚本"
3. 填写信息：
   - **脚本名称**: `Python系统监控`
   - **文件路径**: `python-scripts/data_analysis/performance_monitor.py`
   - **工作目录**: `/Users/xuan/worksapce/manager/backend`
   - **默认参数**: `--system --days 1 --output-format json`
4. 保存并执行

🎉 恭喜！你已经成功集成了Python分析功能！

---

## 🚀 常用功能速查

### 📊 数据分析（5个命令搞定）

```bash
# 1. 系统健康检查
python3 data_analysis/performance_monitor.py --system --days 1

# 2. 分析最近的执行日志  
python3 data_analysis/log_analyzer.py --batch --days 1

# 3. 查看脚本执行趋势
python3 data_analysis/trend_analysis.py --type execution --days 7

# 4. 分析特定脚本性能（替换1为实际脚本ID）
python3 data_analysis/performance_monitor.py --script-id 1 --days 7

# 5. AI增强分析（需要Ollama）
python3 data_analysis/log_analyzer.py --batch --days 1 --use-ai
```

### 🔄 自动化任务（3个命令搞定）

```bash
# 1. 创建备份
python3 automation/backup_processor.py --action backup --type incremental

# 2. 生成日报
python3 automation/report_generator.py --type daily --format html --output daily_report.html

# 3. 发送测试通知（需要配置邮箱）
python3 automation/notification_sender.py --type custom --subject "测试" --message "Hello" --recipients your-email@example.com
```

### 🌐 启动服务（2个命令搞定）

```bash
# 1. 启动API网关（提供统一API接口）
python3 services/api_gateway.py &

# 2. 启动AI分析服务（可选，需要Ollama）
python3 services/ollama_service.py &

# 然后访问：http://localhost:9999/health 检查状态
```

---

## 📋 Web界面集成示例

### 推荐添加的Python脚本

#### 1. 系统监控脚本
```
脚本名称: Python系统监控
文件路径: python-scripts/data_analysis/performance_monitor.py
默认参数: --system --days 1 --output-format json
描述: 监控系统整体性能状况
```

#### 2. 日志分析脚本
```
脚本名称: Python日志分析
文件路径: python-scripts/data_analysis/log_analyzer.py  
默认参数: --batch --days 1 --output-format json
描述: 智能分析系统执行日志
```

#### 3. 自动备份脚本
```
脚本名称: Python自动备份
文件路径: python-scripts/automation/backup_processor.py
默认参数: --action backup --type incremental --output-format json
描述: 创建增量备份
```

#### 4. 日报生成脚本
```
脚本名称: Python日报生成
文件路径: python-scripts/automation/report_generator.py
默认参数: --type daily --format json
描述: 生成系统运行日报
```

### 推荐的定时任务

```
任务1: 每日系统监控
Cron: 0 6 * * * (每天早上6点)
脚本: Python系统监控
参数: --system --days 1

任务2: 每日日志分析  
Cron: 0 7 * * * (每天早上7点)
脚本: Python日志分析
参数: --batch --days 1

任务3: 每日备份
Cron: 0 2 * * * (每天凌晨2点)
脚本: Python自动备份
参数: --action backup --type incremental

任务4: 周报生成
Cron: 0 8 * * 1 (每周一早上8点)
脚本: Python日报生成  
参数: --type weekly --format html
```

---

## 🔧 环境配置（可选）

### 邮件通知配置
```bash
export EMAIL_ENABLED="true"
export SMTP_SERVER="smtp.qq.com"
export SMTP_PORT="587" 
export EMAIL_USERNAME="your-email@qq.com"
export EMAIL_PASSWORD="your-app-password"
```

### 微信通知配置（企业微信机器人）
```bash
export WECHAT_ENABLED="true"
export WECHAT_WEBHOOK="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=your-key"
```

### Ollama AI配置（可选）
```bash
# 安装Ollama
curl -fsSL https://ollama.com/install.sh | sh

# 启动服务
ollama serve

# 拉取模型
ollama pull llama2

# 设置配置
export OLLAMA_HOST="localhost"
export OLLAMA_PORT="11434"
export OLLAMA_MODEL="llama2"
```

---

## 🐛 常见问题快速解决

### Q: 数据库连接失败？
```bash
# 检查数据库服务
systemctl status mysql

# 检查网络连通性  
telnet 10.0.129.128 3306

# 检查配置文件
python3 shared/database_client.py --test connection
```

### Q: Python脚本没有执行权限？
```bash
# 给脚本添加执行权限
find python-scripts -name "*.py" -exec chmod +x {} \;
```

### Q: 缺少Python依赖包？
```bash
# 重新安装依赖
pip install -r requirements.txt

# 或者使用虚拟环境
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Q: Ollama服务连接失败？
```bash
# 检查Ollama服务状态
curl http://localhost:11434/api/tags

# 如果服务未启动
ollama serve

# 拉取基础模型
ollama pull llama2
```

### Q: 日志文件找不到？
```bash
# 检查日志目录
ls -la /Users/xuan/worksapce/manager/backend/logs/

# 确保目录存在
mkdir -p /Users/xuan/worksapce/manager/backend/logs/
```

---

## 🎯 使用技巧

### 1. 批量操作
```bash
# 分析所有脚本的性能
for id in {1..10}; do
    python3 data_analysis/performance_monitor.py --script-id $id --days 7
done

# 备份后自动生成报告
python3 automation/backup_processor.py --action backup --type full && \
python3 automation/report_generator.py --type daily --format html
```

### 2. 结果筛选
```bash
# 只显示错误信息
python3 data_analysis/log_analyzer.py --batch --days 1 | grep -E "ERROR|FAILED"

# 只显示性能数据
python3 data_analysis/performance_monitor.py --system --days 1 | grep -E "成功率|执行时间"
```

### 3. 输出重定向
```bash
# 保存分析结果到文件
python3 data_analysis/performance_monitor.py --system --days 7 > system_performance.txt

# JSON格式保存便于后续处理
python3 data_analysis/log_analyzer.py --batch --days 1 --output-format json > log_analysis.json
```

### 4. 组合使用
```bash
# 分析后自动发送通知
python3 data_analysis/performance_monitor.py --system --days 1 | \
awk '/成功率/ && $2 < 90 {print "系统成功率过低：" $2}' | \
xargs -I {} python3 automation/notification_sender.py --type custom --subject "告警" --message "{}" --recipients admin@example.com
```

---

## 📱 API接口速查

### 启动API服务
```bash
python3 services/api_gateway.py
```

### 常用API调用
```bash
# 健康检查
curl http://localhost:9999/health

# 获取系统状态
curl http://localhost:9999/api/v1/realtime/dashboard

# 执行日志分析
curl -X POST http://localhost:9999/api/v1/analysis/logs \
  -H "Content-Type: application/json" \
  -d '{"batch": true, "days": 1}'

# 创建备份
curl -X POST http://localhost:9999/api/v1/backup/create \
  -H "Content-Type: application/json" \
  -d '{"type": "incremental"}'

# 生成报告
curl -X POST http://localhost:9999/api/v1/reports/generate \
  -H "Content-Type: application/json" \
  -d '{"type": "daily", "format": "json"}'
```

---

## 📚 学习路径

### 初级用户（系统管理员）
1. ✅ 完成快速开始
2. ✅ 在Web界面添加Python脚本  
3. ✅ 设置基础定时任务
4. ✅ 配置邮件通知

### 中级用户（运维工程师）
1. ✅ 掌握所有命令行工具
2. ✅ 配置多渠道通知
3. ✅ 启用AI分析功能
4. ✅ 自定义报告模板

### 高级用户（开发工程师）  
1. ✅ 启动API服务
2. ✅ 开发自定义分析脚本
3. ✅ 集成到CI/CD流程
4. ✅ 扩展功能模块

---

## 🎉 恭喜完成快速开始！

现在你已经掌握了基础用法，可以：

- ✅ **监控系统性能** - 实时了解系统运行状况
- ✅ **智能日志分析** - 快速定位问题根因  
- ✅ **自动化备份** - 保障数据安全
- ✅ **定时报告** - 获得运营洞察
- ✅ **多渠道通知** - 及时获取重要信息

**下一步建议**：
1. 查看 `docs/PROJECT_GUIDE.md` 了解更多高级功能
2. 根据实际需求配置定时任务
3. 尝试启用AI增强功能
4. 探索API接口集成

有问题随时查看详细文档，祝你使用愉快！🚀