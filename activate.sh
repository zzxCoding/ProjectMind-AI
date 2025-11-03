#!/bin/bash
# 激活ProjectMind-AI Python扩展项目环境

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${PROJECT_DIR}/venv"

# 检查虚拟环境是否存在
if [ ! -d "$VENV_DIR" ]; then
    echo "❌ 虚拟环境不存在，请先运行 ./setup.sh"
    return 1
fi

# 激活虚拟环境
source "$VENV_DIR/bin/activate"

# 加载项目环境变量
if [ -f "$PROJECT_DIR/.env" ]; then
    set -a  # 自动导出变量
    source "$PROJECT_DIR/.env"
    set +a
fi

# 设置PYTHONPATH
export PYTHONPATH="$PROJECT_DIR:$PYTHONPATH"

echo "✅ ProjectMind-AI Python扩展环境已激活"
echo "📁 项目目录: $PROJECT_DIR"
echo "🐍 Python: $(which python)"
echo "📦 虚拟环境: $VIRTUAL_ENV"
echo ""
echo "🚀 快速开始："
echo "  python shared/database_client.py --test connection  # 测试数据库连接"
echo "  python data_analysis/performance_monitor.py --system --days 1  # 系统性能检查"
echo "  python services/api_gateway.py --test  # 测试API网关"
echo ""
echo "📚 查看文档："
echo "  cat QUICK_START.md  # 快速开始指南"
echo "  cat PROJECT_GUIDE.md  # 详细项目指南"
echo ""
echo "🔧 退出环境："
echo "  deactivate  # 退出虚拟环境"
