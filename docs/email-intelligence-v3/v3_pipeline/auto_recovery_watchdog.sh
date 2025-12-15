#!/bin/bash
# V3.11 自动恢复监控脚本

LOG=/tmp/watchdog.log
EXTRACTION_LOG=/tmp/extraction_v311.log
CHECK_INTERVAL=60

log() {
    echo "$(date '+%m-%d %H:%M:%S') $1" | tee -a $LOG
}

check_vllm() {
    curl -s --max-time 10 http://localhost:8000/v1/models > /dev/null 2>&1
}

restart_vllm() {
    log "🔄 vLLM 无响应，重启容器..."
    docker restart qwen3-vl
    for i in {1..18}; do
        sleep 10
        if check_vllm; then
            log "✅ vLLM 已恢复"
            return 0
        fi
    done
    log "❌ vLLM 启动超时"
    return 1
}

check_extraction() {
    pgrep -f "batch_extractor_v311" > /dev/null 2>&1
}

start_extraction() {
    log "🚀 启动提取脚本..."
    cd ~/vulcan-brain
    source venv/bin/activate
    PYTHONUNBUFFERED=1 nohup python3 docs/email-intelligence-v3/v3_pipeline/batch_extractor_v311_sorted.py >> $EXTRACTION_LOG 2>&1 &
    sleep 5
}

get_progress() {
    python3 -c "import json; d=json.load(open('$HOME/vulcan_data/cache/extraction_state.json')); print(len(d.get('extracted_ids',[])))" 2>/dev/null || echo 0
}

log "========================================"
log "🐕 V3.11 自动恢复监控启动"
log "========================================"

last_progress=0
stall_count=0

while true; do
    progress=$(get_progress)
    
    # 检查 vLLM
    if ! check_vllm; then
        log "⚠️ vLLM 无响应"
        pkill -f batch_extractor_v311 2>/dev/null
        if restart_vllm; then
            sleep 5
            start_extraction
        fi
        stall_count=0
    else
        # vLLM 正常
        if ! check_extraction; then
            if [ "$progress" -lt 3237 ]; then
                log "⚠️ 提取未运行 ($progress/3237)"
                start_extraction
            else
                log "🎉 提取完成!"
                break
            fi
        else
            # 检查卡住
            if [ "$progress" -eq "$last_progress" ]; then
                stall_count=$((stall_count + 1))
                if [ $stall_count -ge 5 ]; then
                    log "🔄 进度停滞，重启 ($progress)"
                    pkill -f batch_extractor_v311
                    sleep 3
                    start_extraction
                    stall_count=0
                fi
            else
                stall_count=0
            fi
            log "✅ 运行中 $progress/3237"
        fi
    fi
    
    last_progress=$progress
    sleep $CHECK_INTERVAL
done
