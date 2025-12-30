#!/bin/bash
# 飞书群聊消息定时采集 - 自动获取所有群

LOCKFILE="/tmp/feishu_chat.lock"
LOGDIR="/home/xinyue/vulcan-brain/logs"

mkdir -p $LOGDIR

if [ -f "$LOCKFILE" ]; then
    pid=$(cat $LOCKFILE)
    if ps -p $pid > /dev/null 2>&1; then
        echo "$(date) - 飞书采集已在运行 (PID: $pid), 跳过" >> $LOGDIR/feishu_chat_cron.log
        exit 0
    fi
fi

echo $$ > $LOCKFILE

cd /home/xinyue/vulcan-brain
source venv/bin/activate
python3 scripts/feishu_chat_cron.py 2>&1

rm -f $LOCKFILE
