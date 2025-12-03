#!/bin/bash
# 定时生成日报脚本
# 每天22:00执行

LOG_FILE=/home/xinyue/vulcan-brain/logs/daily_report_cron.log
API_URL=http://localhost:8001/api/info-hub/daily/generate

echo "[$(date)] 开始生成日报..." >> $LOG_FILE
curl -X POST $API_URL >> $LOG_FILE 2>&1
echo "" >> $LOG_FILE
echo "[$(date)] 日报生成完成" >> $LOG_FILE
