#!/bin/bash
echo "=== Email Intelligence V2.0 批量处理进度 ==="
echo "时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# 检查进程是否运行
if pgrep -f "run_batch_filtered" > /dev/null; then
    echo "状态: ✅ 运行中"
else
    echo "状态: ⏹️ 已停止"
fi

echo ""
mongosh vulcan_brain --quiet --eval '
const total = db.email_events.countDocuments({});
const recent = db.email_events.find().sort({_id: -1}).limit(1).toArray()[0];

print("已处理: " + total + " 封");

if (recent) {
    print("最新处理: " + (recent.email_subject || "").substring(0, 50) + "...");
}

// 统计最近 5 分钟的处理速度
const fiveMinAgo = new Date(Date.now() - 5*60*1000);
const recentCount = db.email_events.countDocuments({"_id": {"$gte": ObjectId.createFromTime(Math.floor(fiveMinAgo.getTime()/1000))}});
print("最近5分钟: " + recentCount + " 封 (" + (recentCount / 5).toFixed(1) + " 封/分钟)");
'

echo ""
echo "最新日志:"
tail -5 /tmp/email_batch.log 2>/dev/null | grep -E "(意图|处理邮件|批次|完成)" | tail -3
