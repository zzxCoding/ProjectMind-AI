#!/bin/bash

# ProjectMind-AI Python扩展一键配置脚本
# 版本：1.0.0
# 作者：AI Assistant
# 描述：为Python扩展项目进行环境配置，不影响系统全局环境

set -e  # 遇到错误立即退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 项目配置
PROJECT_NAME="ProjectMind-AI Python扩展"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${PROJECT_DIR}/venv"
CONFIG_DIR="${PROJECT_DIR}/config"
LOG_FILE="${PROJECT_DIR}/setup.log"

# 检测操作系统
OS_TYPE="unknown"
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    OS_TYPE="linux"
elif [[ "$OSTYPE" == "darwin"* ]]; then
    OS_TYPE="macos"
fi

# 日志函数
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
    echo -e "$1"
}

info() {
    log "${BLUE}[INFO]${NC} $1"
}

success() {
    log "${GREEN}[SUCCESS]${NC} $1"
}

warning() {
    log "${YELLOW}[WARNING]${NC} $1"
}

error() {
    log "${RED}[ERROR]${NC} $1"
}

# 显示横幅
show_banner() {
    echo -e "${CYAN}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                                                              ║"
    echo "║              ProjectMind-AI Python扩展                       ║"
    echo "║                     一键配置脚本                              ║"
    echo "║                                                              ║"
    echo "║  🚀 智能数据分析   🤖 AI增强功能   📊 自动化报告              ║"
    echo "║                                                              ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo
}

# 检查系统要求
check_system_requirements() {
    info "检查系统要求..."
    
    # 检查Python版本
    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2)
        PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d'.' -f1)
        PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d'.' -f2)
        
        if [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -ge 8 ]; then
            success "Python版本检查通过: $PYTHON_VERSION"
        else
            error "Python版本过低，需要Python 3.8+，当前版本：$PYTHON_VERSION"
            exit 1
        fi
    else
        error "未找到Python3，请先安装Python 3.8+"
        exit 1
    fi
    
    # 检查pip
    if ! command -v pip3 &> /dev/null; then
        error "未找到pip3，请先安装pip"
        exit 1
    fi
    
    # 检查必要的系统工具
    local missing_tools=()
    for tool in curl wget git; do
        if ! command -v $tool &> /dev/null; then
            missing_tools+=($tool)
        fi
    done
    
    if [ ${#missing_tools[@]} -gt 0 ]; then
        warning "缺少系统工具: ${missing_tools[*]}，部分功能可能受限"
    fi
    
    success "系统要求检查完成"
}

# 创建Python虚拟环境
setup_virtual_environment() {
    info "设置Python虚拟环境..."
    
    if [ -d "$VENV_DIR" ]; then
        warning "虚拟环境已存在，跳过创建"
    else
        info "创建虚拟环境：$VENV_DIR"
        python3 -m venv "$VENV_DIR"
        success "虚拟环境创建完成"
    fi
    
    # 激活虚拟环境
    source "$VENV_DIR/bin/activate"
    
    # 升级pip
    info "升级pip..."
    pip install --upgrade pip > /dev/null 2>&1
    
    success "虚拟环境设置完成"
}

# 安装Python依赖
install_python_dependencies() {
    info "安装Python依赖包..."
    
    if [ ! -f "$PROJECT_DIR/requirements.txt" ]; then
        error "requirements.txt文件不存在"
        exit 1
    fi
    
    # 激活虚拟环境
    source "$VENV_DIR/bin/activate"
    
    # 安装依赖包
    pip install -r "$PROJECT_DIR/requirements.txt"
    
    success "Python依赖包安装完成"
}

# 创建项目配置文件
create_project_config() {
    info "创建项目配置文件..."
    
    # 检查.env文件是否已存在
    if [ -f "$PROJECT_DIR/.env" ]; then
        warning ".env文件已存在，跳过创建（使用 rm .env 手动删除后重新运行）"
        return
    fi
    
    # 创建项目环境变量文件
    cat > "$PROJECT_DIR/.env" << EOF
# ProjectMind-AI Python扩展项目配置
# 该文件仅影响当前项目，不影响系统全局环境

# 项目基础配置
PROJECT_ROOT=${PROJECT_DIR}
PYTHON_PATH=${VENV_DIR}/bin/python
LOG_LEVEL=INFO

# 数据库配置（容器环境中使用mysql服务名）
DB_HOST=${DB_HOST:-mysql}
DB_PORT=${DB_PORT:-3306}
DB_DATABASE=${DB_DATABASE:-script_manager}
DB_USERNAME=${DB_USERNAME:-script_manager}
DB_PASSWORD=${DB_PASSWORD:-script_manager}
DB_CHARSET=utf8mb4

# GitLab API配置（新增）
GITLAB_URL=https://gitlab.com
GITLAB_TOKEN=
GITLAB_PROJECT_ID=
GITLAB_TIMEOUT=30
GITLAB_VERIFY_SSL=true

# SonarQube API配置（新增）
SONARQUBE_URL=
SONARQUBE_TOKEN=
SONARQUBE_PROJECT_KEY=
SONARQUBE_TIMEOUT=30
SONARQUBE_VERIFY_SSL=true

# Ollama AI配置（可选）
OLLAMA_ENABLED=false
OLLAMA_HOST=localhost
OLLAMA_PORT=11434
OLLAMA_MODEL=llama2
OLLAMA_TIMEOUT=30

# 邮件通知配置（可选）
EMAIL_ENABLED=false
SMTP_SERVER=smtp.qq.com
SMTP_PORT=587
EMAIL_USERNAME=
EMAIL_PASSWORD=
EMAIL_FROM_NAME="ProjectMind-AI"

# 微信通知配置（可选）
WECHAT_ENABLED=false
WECHAT_WEBHOOK=

# 钉钉通知配置（可选）
DINGTALK_ENABLED=false
DINGTALK_WEBHOOK=
DINGTALK_SECRET=

# Slack通知配置（可选）
SLACK_ENABLED=false
SLACK_WEBHOOK=

# 备份配置
BACKUP_DIR=${PROJECT_DIR}/backups
BACKUP_RETENTION_DAYS=30
BACKUP_COMPRESS=true

# 日志配置
LOGS_DIR=${PROJECT_DIR}/../logs
EXECUTION_LOGS_DIR=${PROJECT_DIR}/../logs

# 脚本配置
SCRIPTS_BASE_DIR=${PROJECT_DIR}/..
SCRIPTS_DIR=${PROJECT_DIR}/../scripts

# API服务配置
API_GATEWAY_HOST=localhost
API_GATEWAY_PORT=9999
OLLAMA_SERVICE_HOST=localhost
OLLAMA_SERVICE_PORT=8888
EOF

    success "项目配置文件创建完成: .env"
}

# 创建启动脚本
create_startup_scripts() {
    info "创建项目启动脚本..."
    
    # 创建项目激活脚本
    cat > "$PROJECT_DIR/activate.sh" << 'EOF'
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
EOF

    chmod +x "$PROJECT_DIR/activate.sh"
    
    # 创建API服务启动脚本
    cat > "$PROJECT_DIR/start_services.sh" << 'EOF'
#!/bin/bash
# 启动ProjectMind-AI Python扩展服务

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_DIR="${PROJECT_DIR}/run"

# 创建PID目录
mkdir -p "$PID_DIR"

# 激活项目环境
source "$PROJECT_DIR/activate.sh"

# 启动API网关服务
start_api_gateway() {
    echo "🚀 启动API网关服务..."
    python "$PROJECT_DIR/services/api_gateway.py" --host $API_GATEWAY_HOST --port $API_GATEWAY_PORT > "$PROJECT_DIR/logs/api_gateway.log" 2>&1 &
    echo $! > "$PID_DIR/api_gateway.pid"
    echo "✅ API网关服务已启动 (PID: $!)"
    echo "📊 访问地址: http://$API_GATEWAY_HOST:$API_GATEWAY_PORT"
}

# 启动Ollama服务（如果启用）
start_ollama_service() {
    if [ "$OLLAMA_ENABLED" = "true" ]; then
        echo "🤖 启动Ollama分析服务..."
        python "$PROJECT_DIR/services/ollama_service.py" --host $OLLAMA_SERVICE_HOST --port $OLLAMA_SERVICE_PORT > "$PROJECT_DIR/logs/ollama_service.log" 2>&1 &
        echo $! > "$PID_DIR/ollama_service.pid"
        echo "✅ Ollama分析服务已启动 (PID: $!)"
        echo "🧠 访问地址: http://$OLLAMA_SERVICE_HOST:$OLLAMA_SERVICE_PORT"
    fi
}

# 检查服务状态
check_services() {
    echo ""
    echo "📋 服务状态检查："
    
    if [ -f "$PID_DIR/api_gateway.pid" ]; then
        PID=$(cat "$PID_DIR/api_gateway.pid")
        if kill -0 $PID 2>/dev/null; then
            echo "✅ API网关服务运行中 (PID: $PID)"
        else
            echo "❌ API网关服务未运行"
            rm -f "$PID_DIR/api_gateway.pid"
        fi
    fi
    
    if [ -f "$PID_DIR/ollama_service.pid" ]; then
        PID=$(cat "$PID_DIR/ollama_service.pid")
        if kill -0 $PID 2>/dev/null; then
            echo "✅ Ollama服务运行中 (PID: $PID)"
        else
            echo "❌ Ollama服务未运行"
            rm -f "$PID_DIR/ollama_service.pid"
        fi
    fi
}

# 主函数
main() {
    case "${1:-start}" in
        start)
            start_api_gateway
            start_ollama_service
            check_services
            ;;
        stop)
            echo "🛑 停止所有服务..."
            for pidfile in "$PID_DIR"/*.pid; do
                if [ -f "$pidfile" ]; then
                    PID=$(cat "$pidfile")
                    if kill -0 $PID 2>/dev/null; then
                        kill $PID
                        echo "✅ 服务已停止 (PID: $PID)"
                    fi
                    rm -f "$pidfile"
                fi
            done
            ;;
        status)
            check_services
            ;;
        restart)
            $0 stop
            sleep 2
            $0 start
            ;;
        *)
            echo "用法: $0 {start|stop|status|restart}"
            exit 1
            ;;
    esac
}

main "$@"
EOF

    chmod +x "$PROJECT_DIR/start_services.sh"
    
    success "启动脚本创建完成"
}

# 创建必要的目录结构
create_directories() {
    info "创建项目目录结构..."
    
    local dirs=(
        "logs"
        "backups"
        "run"
        "temp"
        "reports"
    )
    
    for dir in "${dirs[@]}"; do
        mkdir -p "$PROJECT_DIR/$dir"
        info "创建目录: $dir"
    done
    
    success "目录结构创建完成"
}

# 修复脚本中的硬编码路径
fix_hardcoded_paths() {
    info "修复脚本中的硬编码路径..."
    
    # 创建路径配置文件
    cat > "$PROJECT_DIR/config/paths.py" << EOF
#!/usr/bin/env python3
"""
项目路径配置
自动检测项目根目录，避免硬编码路径
"""

import os
import sys
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.absolute()

# 添加项目根目录到Python路径
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 各模块路径
CONFIG_DIR = PROJECT_ROOT / "config"
SHARED_DIR = PROJECT_ROOT / "shared"
DATA_ANALYSIS_DIR = PROJECT_ROOT / "data_analysis"
AUTOMATION_DIR = PROJECT_ROOT / "automation"
SERVICES_DIR = PROJECT_ROOT / "services"

# 数据路径
LOGS_DIR = PROJECT_ROOT.parent / "logs"
SCRIPTS_DIR = PROJECT_ROOT.parent / "scripts"
BACKUPS_DIR = PROJECT_ROOT / "backups"
REPORTS_DIR = PROJECT_ROOT / "reports"
TEMP_DIR = PROJECT_ROOT / "temp"

# 确保目录存在
for directory in [BACKUPS_DIR, REPORTS_DIR, TEMP_DIR]:
    directory.mkdir(exist_ok=True)

def get_project_root():
    """获取项目根目录"""
    return PROJECT_ROOT

def get_data_path(relative_path=""):
    """获取数据文件路径"""
    if relative_path.startswith('/'):
        # 绝对路径，直接返回
        return Path(relative_path)
    else:
        # 相对于项目根目录的路径
        return PROJECT_ROOT / relative_path

def get_log_path(log_name=""):
    """获取日志文件路径"""
    if not log_name:
        return LOGS_DIR
    return LOGS_DIR / log_name

def setup_python_path():
    """设置Python路径"""
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

# 自动执行路径设置
setup_python_path()

if __name__ == "__main__":
    print(f"项目根目录: {PROJECT_ROOT}")
    print(f"配置目录: {CONFIG_DIR}")
    print(f"共享目录: {SHARED_DIR}")
    print(f"日志目录: {LOGS_DIR}")
    print(f"脚本目录: {SCRIPTS_DIR}")
EOF

    # 创建通用的导入文件
    cat > "$PROJECT_DIR/__init__.py" << 'EOF'
#!/usr/bin/env python3
"""
ProjectMind-AI Python扩展项目
"""

# 自动设置项目路径
from config.paths import setup_python_path
setup_python_path()

__version__ = "1.0.0"
__author__ = "ProjectMind-AI Team"
__description__ = "Python扩展模块，提供数据分析、自动化处理和AI增强功能"
EOF

    success "路径配置文件创建完成"
}

# 测试项目配置
test_project_setup() {
    info "测试项目配置..."
    
    # 激活虚拟环境
    source "$VENV_DIR/bin/activate"
    
    # 加载环境变量
    set -a
    source "$PROJECT_DIR/.env"
    set +a
    
    local test_results=()
    
    # 测试Python导入
    info "测试Python模块导入..."
    if python -c "import sys; sys.path.insert(0, '$PROJECT_DIR'); import config, shared" 2>/dev/null; then
        test_results+=("✅ Python模块导入正常")
    else
        test_results+=("❌ Python模块导入失败")
    fi
    
    # 测试数据库连接
    info "测试数据库连接..."
    if python "$PROJECT_DIR/shared/database_client.py" --test connection 2>/dev/null | grep -q "数据库连接成功"; then
        test_results+=("✅ 数据库连接正常")
    else
        test_results+=("⚠️  数据库连接失败（请检查数据库配置）")
    fi
    
    # 测试GitLab连接（如果配置了Token）
    if [ -n "$GITLAB_TOKEN" ]; then
        info "测试GitLab连接..."
        if python "$PROJECT_DIR/shared/gitlab_client.py" --test connection 2>/dev/null | grep -q "GitLab连接正常"; then
            test_results+=("✅ GitLab服务连接正常")
        else
            test_results+=("⚠️  GitLab服务连接失败（请检查Token配置）")
        fi
    fi
    
    # 测试SonarQube连接（如果配置了Token）
    if [ -n "$SONARQUBE_TOKEN" ]; then
        info "测试SonarQube连接..."
        if python "$PROJECT_DIR/shared/sonarqube_client.py" --test connection 2>/dev/null | grep -q "SonarQube连接正常"; then
            test_results+=("✅ SonarQube服务连接正常")
        else
            test_results+=("⚠️  SonarQube服务连接失败（请检查Token配置）")
        fi
    fi
    
    # 测试Ollama连接（可选）
    if [ "$OLLAMA_ENABLED" = "true" ]; then
        info "测试Ollama连接..."
        if python "$PROJECT_DIR/shared/ollama_client.py" --test health 2>/dev/null | grep -q "Ollama服务正常"; then
            test_results+=("✅ Ollama服务连接正常")
        else
            test_results+=("⚠️  Ollama服务连接失败（可选功能）")
        fi
    fi
    
    # 测试基础脚本
    info "测试基础脚本功能..."
    if python "$PROJECT_DIR/data_analysis/performance_monitor.py" --help > /dev/null 2>&1; then
        test_results+=("✅ 数据分析脚本正常")
    else
        test_results+=("❌ 数据分析脚本异常")
    fi
    
    # 显示测试结果
    echo ""
    echo -e "${CYAN}📋 配置测试结果：${NC}"
    for result in "${test_results[@]}"; do
        echo "  $result"
    done
}

# 显示配置完成信息
show_completion_info() {
    echo ""
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                     🎉 配置完成！                            ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    
    echo -e "${YELLOW}📂 项目位置：${NC} $PROJECT_DIR"
    echo -e "${YELLOW}🐍 虚拟环境：${NC} $VENV_DIR"
    echo -e "${YELLOW}⚙️ 配置文件：${NC} $PROJECT_DIR/.env"
    echo -e "${YELLOW}📋 日志文件：${NC} $LOG_FILE"
    echo ""
    
    echo -e "${CYAN}🚀 快速开始：${NC}"
    echo "  # 激活项目环境"
    echo -e "  ${GREEN}source activate.sh${NC}"
    echo ""
    echo "  # 测试各项连接"
    echo -e "  ${GREEN}python shared/database_client.py --test connection${NC}"
    echo -e "  ${GREEN}python shared/gitlab_client.py --test connection${NC}"
    echo -e "  ${GREEN}python shared/sonarqube_client.py --test connection${NC}"
    echo ""
    echo "  # 运行系统性能检查"
    echo -e "  ${GREEN}python data_analysis/performance_monitor.py --system --days 1${NC}"
    echo ""
    echo "  # GitLab合并记录分析（需配置GITLAB_TOKEN）"
    echo -e "  ${GREEN}python data_analysis/gitlab_merge_analyzer.py --project-id YOUR_PROJECT_ID --start-date 2024-01-01 --end-date 2024-01-31 --use-ai${NC}"
    echo ""
    echo "  # SonarQube缺陷分析（需配置SONARQUBE_TOKEN）"
    echo -e "  ${GREEN}python data_analysis/sonarqube_defect_analyzer.py --project-key YOUR_PROJECT_KEY --use-ai${NC}"
    echo ""
    echo "  # 启动API服务"
    echo -e "  ${GREEN}./start_services.sh${NC}"
    echo ""
    
    echo -e "${CYAN}📚 文档指南：${NC}"
    echo -e "  ${GREEN}cat QUICK_START.md${NC}     # 5分钟快速开始"
    echo -e "  ${GREEN}cat PROJECT_GUIDE.md${NC}   # 完整项目指南"
    echo ""
    
    echo -e "${CYAN}🔧 可选配置：${NC}"
    echo "  1. 编辑 .env 文件配置GitLab Token和项目ID"
    echo "  2. 配置邮件/微信/钉钉通知"
    echo "  3. 安装Ollama启用AI功能"
    echo "  4. 在Web界面添加Python脚本"
    echo ""
    
    if [ -f "$LOG_FILE" ]; then
        echo -e "${YELLOW}📋 详细日志：${NC} $LOG_FILE"
    fi
}

# 清理函数
cleanup() {
    if [ $? -ne 0 ]; then
        error "配置过程中出现错误，请查看日志：$LOG_FILE"
    fi
}

# 主函数
main() {
    # 设置错误处理
    trap cleanup EXIT
    
    # 清空日志文件
    > "$LOG_FILE"
    
    # 显示横幅
    show_banner
    
    # 检查参数
    local skip_tests=false
    local force_reinstall=false
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            --skip-tests)
                skip_tests=true
                shift
                ;;
            --force-reinstall)
                force_reinstall=true
                shift
                ;;
            --help|-h)
                echo "用法: $0 [选项]"
                echo ""
                echo "选项:"
                echo "  --skip-tests        跳过测试步骤"
                echo "  --force-reinstall   强制重新安装依赖"
                echo "  --help, -h          显示帮助信息"
                echo ""
                exit 0
                ;;
            *)
                error "未知参数: $1"
                echo "使用 --help 查看帮助信息"
                exit 1
                ;;
        esac
    done
    
    info "开始配置 $PROJECT_NAME"
    info "项目目录: $PROJECT_DIR"
    info "操作系统: $OS_TYPE"
    echo ""
    
    # 执行配置步骤
    check_system_requirements
    echo ""
    
    setup_virtual_environment
    echo ""
    
    if [ "$force_reinstall" = true ] || [ ! -f "$VENV_DIR/pyvenv.cfg" ]; then
        install_python_dependencies
        echo ""
    else
        info "依赖已安装，跳过安装步骤（使用 --force-reinstall 强制重装）"
        echo ""
    fi
    
    create_directories
    echo ""
    
    create_project_config
    echo ""
    
    fix_hardcoded_paths
    echo ""
    
    create_startup_scripts
    echo ""
    
    if [ "$skip_tests" = false ]; then
        test_project_setup
        echo ""
    else
        info "跳过测试步骤"
        echo ""
    fi
    
    show_completion_info
    
    success "🎉 ProjectMind-AI Python扩展配置完成！"
}

# 执行主函数
main "$@"