#!/bin/bash
# 定时生成日报脚本
# 每天早上7:00执行，生成昨天7AM到今天7AM的日报

LOG_FILE=/home/xinyue/vulcan-brain/logs/daily_report_cron.log
API_URL=http://localhost:8001/api/info-hub/daily/generate

# 计算昨天的日期 (日报标签)
# 早上7点运行时，生成昨天的日报
YESTERDAY=$(date -d 'yesterday' +%Y-%m-%d 2>/dev/null || date -v-1d +%Y-%m-%d)

echo "[$(date '+%Y-%m-%d %H:%M:%S %z')] 开始生成日报: $YESTERDAY (7AM-7AM)" >> $LOG_FILE

# 生成完整日报（所有维度）
RESPONSE=$(curl -s -X POST $API_URL \
  -H "Content-Type: application/json" \
  -d "{\"date\": \"$YESTERDAY\"}")

echo "Response: $RESPONSE" >> $LOG_FILE
echo "[$(date '+%Y-%m-%d %H:%M:%S %z')] 日报生成完成: $YESTERDAY" >> $LOG_FILE
echo "" >> $LOG_FILE
