#!/bin/bash
# MongoDB Daily Backup Script
BACKUP_DIR="$HOME/backups/mongodb"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/vulcan_brain_$DATE.gz"
RETENTION_DAYS=7

mkdir -p "$BACKUP_DIR"
mongodump --db vulcan_brain --archive="$BACKUP_FILE" --gzip
find "$BACKUP_DIR" -name "vulcan_brain_*.gz" -mtime +$RETENTION_DAYS -delete
echo "[$(date)] Backup complete: $BACKUP_FILE"
