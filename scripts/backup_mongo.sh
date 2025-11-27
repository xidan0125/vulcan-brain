#\!/bin/bash
# ==================== Vulcan Brain MongoDB 备份脚本 ====================
# 用法: 添加到 crontab，每天凌晨 3 点执行
# crontab -e → 0 3 * * * /home/xinyueyu/vulcan_brain_v2/scripts/backup_mongo.sh

BACKUP_DIR="$HOME/backups/mongodb"
RETENTION_DAYS=7
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/vulcan_brain_$DATE.gz"

# 创建备份目录
mkdir -p "$BACKUP_DIR"

# 执行备份
echo "[$(date)] 开始备份 MongoDB..."
mongodump --db vulcan_brain --archive="$BACKUP_FILE" --gzip

if [ $? -eq 0 ]; then
    echo "[$(date)] ✅ 备份成功: $BACKUP_FILE"
    echo "[$(date)] 文件大小: $(du -h "$BACKUP_FILE" | cut -f1)"
else
    echo "[$(date)] ❌ 备份失败\!"
    exit 1
fi

# 删除旧备份
echo "[$(date)] 清理 $RETENTION_DAYS 天前的备份..."
find "$BACKUP_DIR" -name "vulcan_brain_*.gz" -mtime +$RETENTION_DAYS -delete

# 列出当前备份
echo "[$(date)] 当前备份列表:"
ls -lh "$BACKUP_DIR"

echo "[$(date)] 备份任务完成"
