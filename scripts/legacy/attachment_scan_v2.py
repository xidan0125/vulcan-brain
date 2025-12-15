import pymongo
from collections import defaultdict, Counter

client = pymongo.MongoClient("mongodb://localhost:27017/")
db = client.vulcan_brain

# 只扫描已经 V2 处理过的业务邮件
filter_query = {
    "processing_status.v2_extracted": True,
    "has_attachments": True
}

stats = {
    "total_emails_with_attachments": 0,
    "total_files": 0,
    "ext_counts": Counter(),
    "business_type_counts": Counter(),
    "size_dist": defaultdict(list),
    "content_type_counts": Counter(),
    "intent_with_attachments": Counter()
}

keywords = {
    "INVOICE": ["invoice", "inv", "fapiao", "发票", "bill"],
    "PO/ORDER": ["po", "order", "purchase", "订单"],
    "SPEC/DRAWING": ["spec", "drawing", "dwg", "cad", "图纸", "参数", "sheet"],
    "CONTRACT": ["contract", "agreement", "nda", "合同", "协议"],
    "PACKING": ["packing", "list", "shipping", "waybill", "装箱", "单号"],
    "QUOTE": ["quote", "quotation", "price", "报价"],
    "REPORT": ["report", "summary", "analysis", "报告"],
    "CERTIFICATE": ["cert", "certificate", "证书", "认证"]
}

print("扫描已处理业务邮件的附件...")

total_v2 = db.emails.count_documents({"processing_status.v2_extracted": True})
total_v2_with_att = db.emails.count_documents(filter_query)
print(f"V2已处理邮件: {total_v2}")
print(f"其中有附件的: {total_v2_with_att}")

for email in db.emails.find(filter_query):
    attachments = email.get("attachments", [])
    if not attachments:
        continue
        
    stats["total_emails_with_attachments"] += 1
    
    intent = email.get("ai_extracted", {}).get("intent", "UNKNOWN")
    stats["intent_with_attachments"][intent] += 1
    
    for att in attachments:
        fname = (att.get("name") or "").lower()
        fsize = att.get("size") or 0
        content_type = att.get("content_type") or ""
        
        if not fname:
            continue
        
        ext = fname.split(".")[-1] if "." in fname else "unknown"
        stats["ext_counts"][ext] += 1
        stats["total_files"] += 1
        stats["size_dist"][ext].append(fsize)
        stats["content_type_counts"][content_type] += 1

        found_type = False
        for b_type, kw_list in keywords.items():
            if any(k in fname for k in kw_list):
                stats["business_type_counts"][b_type] += 1
                found_type = True
                break
        if not found_type:
            stats["business_type_counts"]["UNKNOWN"] += 1

print("\n" + "="*60)
print("📊 业务邮件附件地形扫描报告")
print("="*60)

print(f"\n📧 V2已处理业务邮件: {total_v2}")
print(f"📎 其中有附件的邮件: {stats['total_emails_with_attachments']}")
print(f"📁 附件总数: {stats['total_files']}")

print("\n🎯 1. 各业务意图的附件分布:")
for intent, count in stats["intent_with_attachments"].most_common():
    print(f"   {intent}: {count}封邮件有附件")

print("\n📁 2. 文件格式分布 (Top 20):")
for ext, count in stats["ext_counts"].most_common(20):
    pct = count/stats["total_files"]*100 if stats["total_files"] > 0 else 0
    print(f"   .{ext}: {count} ({pct:.1f}%)")

print("\n💼 3. 业务类型分布 (基于文件名推测):")
for btype, count in stats["business_type_counts"].most_common():
    print(f"   {btype}: {count}")

print("\n⚖️ 4. 关键格式体积分析:")
key_exts = ["pdf", "xlsx", "xls", "jpg", "png", "zip", "doc", "docx", "csv", "eml"]
for ext in key_exts:
    if ext in stats["size_dist"] and stats["size_dist"][ext]:
        sizes = stats["size_dist"][ext]
        avg_kb = sum(sizes) / len(sizes) / 1024
        max_mb = max(sizes) / 1024 / 1024
        count = len(sizes)
        large = len([s for s in sizes if s > 2*1024*1024])
        print(f"   .{ext}: {count}个 | 平均 {avg_kb:.1f}KB | 最大 {max_mb:.2f}MB | >2MB: {large}个")

print("\n🔥 5. 超大文件统计:")
size_buckets = {"1-5MB": 0, "5-10MB": 0, "10-50MB": 0, ">50MB": 0}
for ext, sizes in stats["size_dist"].items():
    for s in sizes:
        mb = s / 1024 / 1024
        if mb >= 50:
            size_buckets[">50MB"] += 1
        elif mb >= 10:
            size_buckets["10-50MB"] += 1
        elif mb >= 5:
            size_buckets["5-10MB"] += 1
        elif mb >= 1:
            size_buckets["1-5MB"] += 1
            
for bucket, count in size_buckets.items():
    print(f"   {bucket}: {count}个")

print("\n✨ 6. 高价值附件汇总:")
pdf_count = stats["ext_counts"].get("pdf", 0)
xlsx_count = stats["ext_counts"].get("xlsx", 0) + stats["ext_counts"].get("xls", 0)
doc_count = stats["ext_counts"].get("doc", 0) + stats["ext_counts"].get("docx", 0)
csv_count = stats["ext_counts"].get("csv", 0)
img_count = stats["ext_counts"].get("jpg", 0) + stats["ext_counts"].get("png", 0) + stats["ext_counts"].get("jpeg", 0)

print(f"   - PDF文档: {pdf_count} (发票/合同/报价单)")
print(f"   - Excel表格: {xlsx_count} (订单/清单/报价)")
print(f"   - Word文档: {doc_count} (合同/协议)")
print(f"   - CSV数据: {csv_count} (数据导出)")
print(f"   - 图片: {img_count} (可能含扫描件)")

high_value = pdf_count + xlsx_count + doc_count + csv_count
large_png = len([s for s in stats["size_dist"].get("png", []) if s > 100*1024])
print(f"\n   📌 高价值文档附件: {high_value} 个")
print(f"   📌 大图片(>100KB，可能是扫描件): {large_png} 个")
print(f"   📌 需视觉模型处理: ~{pdf_count + large_png} 个")
