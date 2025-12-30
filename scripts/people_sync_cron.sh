#!/bin/bash
# 人员数据定时同步

LOCKFILE="/tmp/people_sync.lock"
LOGDIR="/home/xinyue/vulcan-brain/logs"

mkdir -p $LOGDIR

if [ -f "$LOCKFILE" ]; then
    pid=$(cat $LOCKFILE)
    if ps -p $pid > /dev/null 2>&1; then
        echo "$(date) - 人员同步已在运行 (PID: $pid), 跳过" >> $LOGDIR/people_sync_cron.log
        exit 0
    fi
fi

echo $$ > $LOCKFILE

cd /home/xinyue/vulcan-brain
source venv/bin/activate
python3 scripts/people_sync_cron.py 2>&1

rm -f $LOCKFILE
