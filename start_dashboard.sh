#\!/bin/bash
# start_dashboard.sh - Vulcan Brain V4 Executive Dashboard 启动脚本

echo "==========================================="
echo "🚀 Vulcan Brain V4 - Executive Dashboard"
echo "==========================================="
echo ""
echo "正在启动服务..."
echo ""

# 检查 Python 环境
if \! command -v python3 &> /dev/null; then
    echo "❌ 错误: python3 未找到"
    exit 1
fi

# 检查必要的包
echo "📦 检查依赖..."
python3 -c "import chainlit" 2>/dev/null || {
    echo "❌ 错误: chainlit 未安装"
    echo "请运行: pip install chainlit"
    exit 1
}

python3 -c "import fastapi" 2>/dev/null || {
    echo "❌ 错误: fastapi 未安装"
    echo "请运行: pip install fastapi uvicorn"
    exit 1
}

# 检查 Ollama 服务
echo "🔍 检查 Ollama 服务..."
if \! curl -s http://localhost:11434/api/tags > /dev/null; then
    echo "⚠️  警告: Ollama 服务未运行"
    echo "  请先启动 Ollama: ollama serve"
fi

# 启动服务器
echo ""
echo "✅ 依赖检查完成"
echo ""
echo "启动 Vulcan Brain Dashboard..."
echo "访问地址: http://0.0.0.0:8000"
echo ""
echo "按 Ctrl+C 停止服务"
echo "-------------------------------------------"
echo ""

# 启动 server.py
cd "$(dirname "$0")"
python3 server.py
