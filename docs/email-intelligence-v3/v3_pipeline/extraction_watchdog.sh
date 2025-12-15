#!/bin/bash
# V3.10 提取监控脚本 - 自动检测并恢复

LOG_FILE=/tmp/watchdog.log
EXTRACTION_LOG=/tmp/extraction_v310.log
CHECK_INTERVAL=120  # 2分钟检查一次

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a $LOG_FILE
}

check_vllm() {
    curl -s --max-time 10 http://localhost:8000/v1/models > /dev/null 2>&1
    return $?
}

restart_vllm() {
    log "🔄 重启 vLLM 容器..."
    docker restart qwen3-vl
    
    # 等待启动 (最多3分钟)
    for i in {1..18}; do
        sleep 10
        if check_vllm; then
            log "✅ vLLM 已恢复"
            return 0
        fi
        log "   等待 vLLM 启动... ($i/18)"
    done
    
    log "❌ vLLM 启动失败"
    return 1
}

check_extraction() {
    pgrep -f "batch_extractor_v310" > /dev/null 2>&1
    return $?
}

start_extraction() {
    log "🚀 启动提取脚本..."
    cd ~/vulcan-brain
    source venv/bin/activate
    PYTHONUNBUFFERED=1 nohup python3 docs/email-intelligence-v3/v3_pipeline/batch_extractor_v310.py >> $EXTRACTION_LOG 2>&1 &
    sleep 5
    
    if check_extraction; then
        log "✅ 提取脚本已启动"
        return 0
    else
        log "❌ 提取脚本启动失败"
        return 1
    fi
}

get_progress() {
    if [ -f ~/vulcan_data/cache/extraction_state.json ]; then
        count=$(cat ~/vulcan_data/cache/extraction_state.json | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('extracted_ids',[])))")
        echo $count
    else
        echo 0
    fi
}

log "========================================"
log "🐕 V3.10 提取监控启动"
log "检查间隔: ${CHECK_INTERVAL}秒"
log "========================================"

while true; do
    # 1. 检查 vLLM
    if ! check_vllm; then
        log "⚠️ vLLM 无响应!"
        restart_vllm
    fi
    
    # 2. 检查提取脚本
    if ! check_extraction; then
        progress=$(get_progress)
        if [ "$progress" -lt 3237 ]; then
            log "⚠️ 提取脚本未运行 (进度: $progress/3237)"
            start_extraction
        else
            log "✅ 提取完成! ($progress/3237)"
            break
        fi
    else
        progress=$(get_progress)
        log "✅ 运行中 - 进度: $progress/3237"
    fi
    
    sleep $CHECK_INTERVAL
done

log "🎉 监控结束"
