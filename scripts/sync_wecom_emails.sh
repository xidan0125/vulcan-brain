#!/bin/bash
# 企业微信邮件自动同步脚本
# 每15分钟运行一次

LOG_FILE="/home/xinyue/vulcan-brain/logs/wecom_sync.log"
API_URL="http://localhost:8001/api/wecom-email/sync-all?days=3"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 开始同步..." >> $LOG_FILE

result=$(curl -s -X POST "$API_URL" --max-time 300)

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 结果: $result" >> $LOG_FILE
echo "" >> $LOG_FILE
