#!/usr/bin/env python3
"""检查下载状态和匹配情况"""
from pymongo import MongoClient
import os
from collections import defaultdict

client = MongoClient("mongodb://localhost:27017")
db = client.vulcan_brain

# 获取所有本地PDF
cache_dir = os.path.expanduser("~/vulcan_data/cache/raw")
local_files = os.listdir(cache_dir)
local_pdfs = [f for f in local_files if f.endswith(".pdf")]

# 提取email_id前缀 (格式: AAMkADhhZDFjMjNh_filename.pdf)
email_id_to_pdfs = defaultdict(list)
for pdf in local_pdfs:
    parts = pdf.split("_", 1)
    if len(parts) == 2:
        email_id_prefix = parts[0]
        email_id_to_pdfs[email_id_prefix].append(pdf)

print(f"📊 下载状态分析")
print(f"=" * 50)
print(f"📁 本地文件统计:")
print(f"   总文件数: {len(local_files):,}")
print(f"   PDF文件数: {len(local_pdfs):,}")
print(f"   对应邮件ID数: {len(email_id_to_pdfs):,}")

# 检查DB中有附件的邮件
emails_with_att = list(db.emails.find(
    {"attachments.0": {"$exists": True}},
    {"_id": 1, "attachments": 1}
))

print(f"\n📧 数据库统计:")
print(f"   有附件邮件: {len(emails_with_att):,}")

# 匹配
matched_emails = 0
matched_pdfs = 0
for email in emails_with_att:
    email_id = email["_id"]
    # 尝试匹配前缀
    for prefix in email_id_to_pdfs.keys():
        if email_id.startswith(prefix):
            matched_emails += 1
            matched_pdfs += len(email_id_to_pdfs[prefix])
            break

print(f"\n🔗 匹配情况:")
print(f"   已下载邮件: {matched_emails:,} / {len(emails_with_att):,}")
print(f"   下载进度: {matched_emails/len(emails_with_att)*100:.1f}%")

# 按附件类型统计
att_types = defaultdict(int)
for email in emails_with_att:
    for att in email.get("attachments", []):
        ct = att.get("content_type", "unknown")
        att_types[ct] += 1

print(f"\n📎 附件类型分布 (Top 10):")
for ct, count in sorted(att_types.items(), key=lambda x: -x[1])[:10]:
    print(f"   {ct}: {count:,}")
