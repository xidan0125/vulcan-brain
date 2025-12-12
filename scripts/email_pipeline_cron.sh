#!/bin/bash
# 邮件管道定时任务包装脚本
# 防止重复运行

LOCKFILE="/tmp/email_pipeline.lock"
LOGDIR="/home/xinyue/vulcan-brain/logs"

# 确保日志目录存在
mkdir -p $LOGDIR

# 检查是否已在运行
if [ -f "$LOCKFILE" ]; then
    pid=$(cat $LOCKFILE)
    if ps -p $pid > /dev/null 2>&1; then
        echo "$(date) - 管道已在运行 (PID: $pid), 跳过" >> $LOGDIR/email_pipeline_cron.log
        exit 0
    fi
fi

# 写入 PID
echo $$ > $LOCKFILE

# 运行管道
cd /home/xinyue/vulcan-brain
source venv/bin/activate
python3 scripts/email_pipeline.py >> $LOGDIR/email_pipeline_cron.log 2>&1
exit_code=$?

# 清理锁文件
rm -f $LOCKFILE

exit $exit_code
