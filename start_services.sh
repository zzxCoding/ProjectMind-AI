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
