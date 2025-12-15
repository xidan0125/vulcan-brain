#!/usr/bin/env python3
"""
V3.8 批量统一提取器
- 正文 + 附件一起送 VLM
- 邮件级提取，结果写入 v3_unified_extraction
"""
import os
import sys
import json
import base64
import time
import fitz  # PyMuPDF
import requests
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from collections import defaultdict
from bson import ObjectId
import pymongo

# ============ 配置 ============
VLLM_URL = "http://localhost:8000/v1/chat/completions"
MODEL_NAME = "Qwen/Qwen3-VL-30B-A3B-Thinking-FP8"

CACHE_DIR = Path.home() / "vulcan_data" / "cache"
RAW_DIR = CACHE_DIR / "raw"
PROGRESS_PATH = CACHE_DIR / "download_progress.json"
EXTRACTION_LOG_PATH = CACHE_DIR / "extraction_log.jsonl"
EXTRACTION_STATE_PATH = CACHE_DIR / "extraction_state.json"

MAX_PAGES_PER_PDF = 3
MAX_ATTACHMENTS_PER_EMAIL = 5
IMAGE_DPI = 150

# ============ Schema ============
VLM_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "email_type": {
            "type": "string",
            "description": "邮件类型: Quotation/Invoice/Contract/Inquiry/Notification/PurchaseOrder/Shipping/Other"
        },
        "summary": {
            "type": "string",
            "description": "整封邮件的一句话摘要（中文）"
        },
        "document_date": {
            "type": "string",
            "description": "文档日期 YYYY-MM-DD 或 null"
        },
        "facts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "type": {"type": "string", "description": "Amount/Date/Identifier/Company/Product/Contact/Quantity/Term/Other"},
                    "key": {"type": "string", "description": "字段名"},
                    "value": {"type": "string", "description": "值"},
                    "unit": {"type": "string", "description": "单位（如有）"},
                    "source_type": {"type": "string", "enum": ["body", "attachment"]},
                    "source_file": {"type": "string", "description": "附件文件名（正文时为null）"},
                    "source_page": {"type": "integer", "description": "页码（正文时为null）"}
                },
                "required": ["type", "key", "value", "source_type"]
            }
        },
        "companies": {"type": "array", "items": {"type": "string"}},
        "products": {"type": "array", "items": {"type": "string"}},
        "persons": {"type": "array", "items": {"type": "string"}}
    },
    "required": ["email_type", "summary", "facts"]
}

EXTRACTION_PROMPT = """你是一个B2B商业文档分析专家。请仔细分析这封邮件（包括正文和附件），提取所有关键商业信息。

【重要规则】:
- 正文内容标记为 source_type: "body"
- 附件内容标记为 source_type: "attachment"，并注明 source_file（文件名）和 source_page（页码）
- Identifier类型用于各种编号：Invoice No, PO No, Quotation No, BL No, Container No等
- 金额、数量、日期要提取准确
- 如果正文和附件有相同信息，以附件为准（更正式）

请提取：
1. 邮件整体类型（报价/发票/合同/询价/采购单/物流/通知等）
2. 所有关键事实（价格、日期、数量、编号、条款等）
3. 涉及的公司、产品、人员
"""

# ============ 数据结构 ============
@dataclass
class ExtractionLog:
    email_id: str
    subject: str
    status: str  # success/failed/skipped
    attachment_count: int
    fact_count: int = 0
    duration: float = 0
    error: Optional[str] = None
    timestamp: str = ""
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

# ============ 工具函数 ============
def pdf_to_images(pdf_path: Path, max_pages: int = MAX_PAGES_PER_PDF) -> List[Dict]:
    """PDF转图片列表"""
    try:
        doc = fitz.open(str(pdf_path))
        images = []
        for page_num in range(min(len(doc), max_pages)):
            page = doc[page_num]
            mat = fitz.Matrix(IMAGE_DPI/72, IMAGE_DPI/72)
            pix = page.get_pixmap(matrix=mat)
            img_bytes = pix.tobytes("png")
            b64 = base64.b64encode(img_bytes).decode()
            images.append({"base64": b64, "page": page_num + 1})
        doc.close()
        return images
    except Exception as e:
        print(f"    ⚠️ PDF转换失败: {e}")
        return []

def image_to_base64(image_path: Path) -> Optional[str]:
    """图片转base64"""
    try:
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except Exception as e:
        print(f"    ⚠️ 图片读取失败: {e}")
        return None

def load_attachment_images(local_path: str, filename: str) -> List[Dict]:
    """加载附件图片"""
    path = Path(local_path)
    if not path.exists():
        return []
    
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    
    if ext == "pdf":
        return pdf_to_images(path)
    elif ext in ("png", "jpg", "jpeg"):
        b64 = image_to_base64(path)
        if b64:
            return [{"base64": b64, "page": 1}]
    elif ext in ("xlsx", "xls"):
        # Excel 已经在收割机中转为图片了，检查 images 目录
        images_dir = CACHE_DIR / "images"
        att_id = path.stem.split("_")[0]  # 从文件名提取 attachment_id 前缀
        img_dir = images_dir / att_id
        if img_dir.exists():
            images = []
            for img_file in sorted(img_dir.glob("page_*.jpg")):
                b64 = image_to_base64(img_file)
                if b64:
                    page_num = int(img_file.stem.split("_")[1])
                    images.append({"base64": b64, "page": page_num})
            return images
    
    return []

# ============ 核心提取 ============
def extract_email(email_id: str, body: str, attachments: List[Dict], db) -> Dict:
    """
    提取单封邮件
    attachments: [{"filename": "x.pdf", "local_path": "/...", "images": [...]}]
    """
    # 构建 VLM 输入
    content = []
    
    # 1. 正文
    body_text = body.strip() if body else "(无正文)"
    content.append({
        "type": "text",
        "text": f"【邮件正文】\n{body_text}\n\n"
    })
    
    # 2. 附件
    if attachments:
        content.append({"type": "text", "text": "【附件内容如下】\n"})
        
        for att in attachments[:MAX_ATTACHMENTS_PER_EMAIL]:
            content.append({
                "type": "text",
                "text": f"\n--- 附件: {att['filename']} ---\n"
            })
            for img in att.get("images", [])[:MAX_PAGES_PER_PDF]:
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{img['base64']}"}
                })
    
    # 3. 提取指令
    content.append({"type": "text", "text": EXTRACTION_PROMPT})
    
    # 调用 VLM
    payload = {
        "model": MODEL_NAME,
        "messages": [{"role": "user", "content": content}],
        "max_tokens": 4096,
        "temperature": 0,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "unified_extraction",
                "schema": VLM_OUTPUT_SCHEMA
            }
        }
    }
    
    start = time.time()
    resp = requests.post(VLLM_URL, json=payload, timeout=300)
    resp.raise_for_status()
    duration = time.time() - start
    
    raw = resp.json()["choices"][0]["message"]["content"]
    
    # 解析
    if "</think>" in raw:
        raw = raw.split("</think>")[-1].strip()
    
    result = json.loads(raw)
    result["_extraction_meta"] = {
        "version": "v3.8",
        "extracted_at": datetime.now().isoformat(),
        "duration_sec": round(duration, 2),
        "attachment_count": len(attachments),
        "model": MODEL_NAME
    }
    
    return result, duration

# ============ 批量处理 ============
def run_batch_extraction(limit: int = None, resume: bool = True):
    """批量提取"""
    print("=" * 60)
    print("🚀 V3.8 批量统一提取")
    print("=" * 60)
    print(f"时间: {datetime.now()}")
    
    # 连接 MongoDB
    client = pymongo.MongoClient("mongodb://localhost:27017")
    db = client.vulcan_brain
    
    # 加载下载进度
    if not PROGRESS_PATH.exists():
        print("❌ 找不到 download_progress.json")
        return
    
    download_data = json.loads(PROGRESS_PATH.read_text())
    downloaded = [r for r in download_data if r["status"] in ("downloaded", "processed")]
    print(f"\n📁 已下载附件: {len(downloaded)}")
    
    # 按 email_id 分组
    email_attachments = defaultdict(list)
    for r in downloaded:
        email_attachments[r["email_id"]].append(r)
    
    print(f"📧 涉及邮件: {len(email_attachments)}")
    
    # 加载已提取状态 (支持断点续传)
    extracted_ids = set()
    if resume and EXTRACTION_STATE_PATH.exists():
        state = json.loads(EXTRACTION_STATE_PATH.read_text())
        extracted_ids = set(state.get("extracted_ids", []))
        print(f"📂 已提取: {len(extracted_ids)} (断点续传)")
    
    # 过滤待提取
    to_extract = {eid: atts for eid, atts in email_attachments.items() 
                  if eid not in extracted_ids}
    
    if limit:
        to_extract = dict(list(to_extract.items())[:limit])
    
    print(f"🎯 待提取: {len(to_extract)}")
    
    if not to_extract:
        print("✅ 全部已提取完成!")
        return
    
    # 开始提取
    success = 0
    failed = 0
    start_time = datetime.now()
    
    for i, (email_id, att_records) in enumerate(to_extract.items()):
        # 进度报告
        if (i + 1) % 10 == 0 or i == 0:
            elapsed = (datetime.now() - start_time).total_seconds()
            rate = (i + 1) / elapsed * 60 if elapsed > 0 else 0
            eta = (len(to_extract) - i - 1) / (rate / 60) / 60 if rate > 0 else 0
            print(f"\n📊 进度: {i+1}/{len(to_extract)} | 成功:{success} 失败:{failed} | {rate:.1f}/min | ETA:{eta:.0f}min")
        
        try:
            # 获取邮件
            email = db.emails.find_one({"_id": ObjectId(email_id)})
            if not email:
                print(f"  ⚠️ 邮件不存在: {email_id}")
                failed += 1
                continue
            
            subject = email.get("subject", "")[:50]
            body = email.get("body", "") or email.get("body_clean", "") or ""
            
            print(f"  📧 [{i+1}] {subject}...")
            
            # 加载附件图片
            attachments = []
            for r in att_records:
                images = load_attachment_images(r["local_path"], r["filename"])
                if images:
                    attachments.append({
                        "filename": r["filename"],
                        "local_path": r["local_path"],
                        "images": images
                    })
            
            if not attachments and not body.strip():
                print(f"    ⚠️ 无内容可提取，跳过")
                log = ExtractionLog(email_id, subject, "skipped", 0, error="no_content")
                _write_log(log)
                continue
            
            # 提取
            result, duration = extract_email(email_id, body, attachments, db)
            
            # 写入 MongoDB
            db.emails.update_one(
                {"_id": ObjectId(email_id)},
                {"$set": {"v3_unified_extraction": result}}
            )
            
            # 记录成功
            fact_count = len(result.get("facts", []))
            print(f"    ✅ 成功! {fact_count} facts, {duration:.1f}s")
            
            log = ExtractionLog(email_id, subject, "success", len(attachments), fact_count, duration)
            _write_log(log)
            
            extracted_ids.add(email_id)
            success += 1
            
        except json.JSONDecodeError as e:
            print(f"    ❌ JSON解析失败: {e}")
            log = ExtractionLog(email_id, subject, "failed", len(att_records), error=f"json_error: {e}")
            _write_log(log)
            failed += 1
            
        except requests.exceptions.Timeout:
            print(f"    ❌ 请求超时")
            log = ExtractionLog(email_id, subject, "failed", len(att_records), error="timeout")
            _write_log(log)
            failed += 1
            
        except Exception as e:
            print(f"    ❌ 错误: {e}")
            log = ExtractionLog(email_id, subject, "failed", len(att_records), error=str(e)[:100])
            _write_log(log)
            failed += 1
        
        # 保存状态 (每10个)
        if (i + 1) % 10 == 0:
            _save_state(extracted_ids)
    
    # 最终保存
    _save_state(extracted_ids)
    
    # 统计
    print("\n" + "=" * 60)
    print("📊 提取完成!")
    print("=" * 60)
    print(f"成功: {success}")
    print(f"失败: {failed}")
    print(f"总耗时: {(datetime.now() - start_time).total_seconds() / 60:.1f} 分钟")

def _write_log(log: ExtractionLog):
    """追加日志"""
    with open(EXTRACTION_LOG_PATH, "a") as f:
        f.write(json.dumps(asdict(log), ensure_ascii=False) + "\n")

def _save_state(extracted_ids: set):
    """保存状态"""
    state = {
        "extracted_ids": list(extracted_ids),
        "updated_at": datetime.now().isoformat()
    }
    EXTRACTION_STATE_PATH.write_text(json.dumps(state, indent=2))

# ============ 主入口 ============
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, help="限制提取数量")
    parser.add_argument("--no-resume", action="store_true", help="不从断点续传")
    args = parser.parse_args()
    
    run_batch_extraction(limit=args.limit, resume=not args.no_resume)
