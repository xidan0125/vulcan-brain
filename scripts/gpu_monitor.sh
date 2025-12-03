#!/bin/bash
# GPU Temperature Monitor
THRESHOLD=80
while true; do
    TEMPS=$(nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader,nounits 2>/dev/null)
    for temp in $TEMPS; do
        if [ "$temp" -gt "$THRESHOLD" ]; then
            echo "[$(date)] WARNING: GPU temp ${temp}C > ${THRESHOLD}C threshold" | tee -a ~/logs/gpu_alerts.log
        fi
    done
    sleep 60
done
