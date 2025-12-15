import pymongo
from collections import defaultdict, Counter

client = pymongo.MongoClient("mongodb://localhost:27017/")
db = client.vulcan_brain
collection = db.emails

stats = {
    "total_emails_with_attachments": 0,
    "total_files": 0,
    "ext_counts": Counter(),
    "business_type_counts": Counter(),
    "size_dist": defaultdict(list),
    "content_type_counts": Counter()
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

print("开始扫描附件元数据...")

# 使用聚合管道确保能获取到数据
pipeline = [
    {"$match": {"has_attachments": True}},
    {"$project": {"attachments": 1, "subject": 1}}
]

for email in collection.aggregate(pipeline):
    attachments = email.get("attachments", [])
    if not attachments:
        continue
        
    stats["total_emails_with_attachments"] += 1
    
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
print("📊 附件地形扫描报告")
print("="*60)

print(f"\n📧 含附件邮件数: {stats['total_emails_with_attachments']}")
print(f"📎 附件总数: {stats['total_files']}")

print("\n📁 1. 文件格式分布 (Top 20):")
for ext, count in stats["ext_counts"].most_common(20):
    pct = count/stats["total_files"]*100 if stats["total_files"] > 0 else 0
    print(f"   .{ext}: {count} ({pct:.1f}%)")

print("\n📋 2. Content-Type 分布 (Top 15):")
for ct, count in stats["content_type_counts"].most_common(15):
    print(f"   {ct}: {count}")

print("\n💼 3. 业务类型分布 (基于文件名推测):")
for btype, count in stats["business_type_counts"].most_common():
    print(f"   {btype}: {count}")

print("\n⚖️ 4. 关键格式体积分析:")
key_exts = ["pdf", "xlsx", "xls", "jpg", "png", "dwg", "dxf", "zip", "rar", "doc", "docx", "p7m", "eml", "msg", "gif", "bmp", "tif", "tiff"]
for ext in key_exts:
    if ext in stats["size_dist"] and stats["size_dist"][ext]:
        sizes = stats["size_dist"][ext]
        avg_kb = sum(sizes) / len(sizes) / 1024
        max_mb = max(sizes) / 1024 / 1024
        min_kb = min(sizes) / 1024
        count = len(sizes)
        print(f"   .{ext}: {count}个 | 平均 {avg_kb:.1f}KB | 最大 {max_mb:.2f}MB | 最小 {min_kb:.1f}KB")

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

print("\n⚠️ 6. 关键发现与风险提示:")
pdf_count = stats["ext_counts"].get("pdf", 0)
xlsx_count = stats["ext_counts"].get("xlsx", 0) + stats["ext_counts"].get("xls", 0)
zip_count = stats["ext_counts"].get("zip", 0) + stats["ext_counts"].get("rar", 0) + stats["ext_counts"].get("7z", 0)
cad_count = stats["ext_counts"].get("dwg", 0) + stats["ext_counts"].get("dxf", 0)
img_count = stats["ext_counts"].get("jpg", 0) + stats["ext_counts"].get("png", 0) + stats["ext_counts"].get("jpeg", 0) + stats["ext_counts"].get("gif", 0) + stats["ext_counts"].get("bmp", 0)
smime_count = stats["ext_counts"].get("p7m", 0)
ics_count = stats["ext_counts"].get("ics", 0)

print(f"   - PDF文档: {pdf_count} (视觉模型主战场)")
print(f"   - Excel表格: {xlsx_count} (结构化数据提取)")
print(f"   - 压缩包: {zip_count} (需递归解压)")
print(f"   - CAD图纸: {cad_count} (需专用解析)")
print(f"   - 图片: {img_count} (OCR/Vision)")
print(f"   - S/MIME签名: {smime_count} (加密邮件签名)")
print(f"   - 日历文件: {ics_count} (会议邀请)")

if "pdf" in stats["size_dist"] and stats["size_dist"]["pdf"]:
    pdf_avg = sum(stats["size_dist"]["pdf"]) / len(stats["size_dist"]["pdf"]) / 1024
    pdf_large = len([s for s in stats["size_dist"]["pdf"] if s > 2*1024*1024])
    print(f"\n   📌 PDF深度分析:")
    print(f"      平均大小: {pdf_avg:.0f}KB")
    print(f"      >2MB的PDF: {pdf_large}个 (可能是扫描件/图纸)")
