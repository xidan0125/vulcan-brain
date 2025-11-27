#\!/bin/bash
# ==================== GPU 温度监控脚本 ====================
# 用法: 添加到 crontab 每 5 分钟检查一次
# */5 * * * * /path/to/gpu_monitor.sh

TEMP_THRESHOLD=85  # 摄氏度
# FEISHU_WEBHOOK="https://open.feishu.cn/open-apis/bot/v2/hook/xxx"  # 取消注释并填写

# 获取 GPU 温度
GPU_TEMP=$(nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader,nounits 2>/dev/null | head -1)

if [ -z "$GPU_TEMP" ]; then
    echo "[$(date)] ❌ 无法获取 GPU 温度"
    exit 1
fi

echo "[$(date)] GPU 温度: ${GPU_TEMP}°C"

if [ "$GPU_TEMP" -ge "$TEMP_THRESHOLD" ]; then
    echo "[$(date)] ⚠️ 警告: GPU 温度过高 (${GPU_TEMP}°C >= ${TEMP_THRESHOLD}°C)"
    
    # 飞书告警 (取消注释启用)
    # if [ -n "$FEISHU_WEBHOOK" ]; then
    #     curl -s -X POST "$FEISHU_WEBHOOK" \
    #         -H "Content-Type: application/json" \
    #         -d "{\"msg_type\":\"text\",\"content\":{\"text\":\"🔥 Vulcan Brain GPU 温度告警\\n当前温度: ${GPU_TEMP}°C\\n阈值: ${TEMP_THRESHOLD}°C\"}}"
    # fi
fi
