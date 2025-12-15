#!/usr/bin/env python3
"""
V3.11 批量提取器 - 按附件大小排序版
小文件优先，大文件留给 Gemini
"""
import os
import json
import base64
import time
import fitz
import requests
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from collections import defaultdict
from bson import ObjectId
import pymongo

# ============ 配置 ============
VLLM_URL = "http://localhost:8000/v1/chat/completions"
MODEL_NAME = "Qwen/Qwen3-VL-30B-A3B-Thinking-FP8"

CACHE_DIR = Path.home() / "vulcan_data" / "cache"
RAW_DIR = CACHE_DIR / "raw"
IMAGES_DIR = CACHE_DIR / "images"
PROGRESS_PATH = CACHE_DIR / "download_progress.json"
EXTRACTION_LOG_PATH = CACHE_DIR / "extraction_log.jsonl"
EXTRACTION_STATE_PATH = CACHE_DIR / "extraction_state.json"

MAX_TOKENS = 20000
MAX_PAGES_PER_ATT = 5
MAX_ATTACHMENTS = 8
RETRY_COUNT = 0
REQUEST_TIMEOUT = 300  # 5分钟

# ============ Schema ============
VLM_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "email_type": {"type": "string"},
        "summary": {"type": "string"},
        "document_date": {"type": "string"},
        "facts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "type": {"type": "string"},
                    "key": {"type": "string"},
                    "value": {"type": "string"},
                    "unit": {"type": "string"},
                    "source_type": {"type": "string", "enum": ["body", "attachment"]},
                    "source_file": {"type": "string"},
                    "source_page": {"type": "integer"}
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

EXTRACTION_PROMPT = """你是B2B商业文档分析专家。分析邮件正文和附件，提取所有关键信息。

【规则】:
- 正文内容标记 source_type: "body"
- 附件内容标记 source_type: "attachment"，注明 source_file 和 source_page
- 提取：金额、日期、编号（Invoice/PO/BL等）、数量、公司名、产品名、联系人
- 如正文与附件有冲突，以附件为准
- 【重要】同一信息只提取一次，不要因为在多处出现就重复记录
- 优先标注信息最完整的来源

请仔细分析后输出JSON。"""

@dataclass
class ExtractionLog:
    email_id: str
    subject: str
    status: str
    attachment_count: int
    total_size: int = 0
    fact_count: int = 0
    duration: float = 0
    error: Optional[str] = None
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

def load_attachment_images(local_path: str, filename: str) -> List[Dict]:
    path = Path(local_path)
    if not path.exists():
        return []
    stem = path.stem
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    img_dir = IMAGES_DIR / stem

    if ext == "pdf":
        if img_dir.exists():
            return _load_from_dir(img_dir)
        else:
            return _pdf_to_images_direct(path)
    elif ext in ("xlsx", "xls"):
        if img_dir.exists():
            return _load_from_dir(img_dir)
        return []
    elif ext in ("png", "jpg", "jpeg"):
        return _image_to_b64(path)
    return []

def _load_from_dir(img_dir: Path) -> List[Dict]:
    images = []
    for jpg in sorted(img_dir.glob("page_*.jpg"))[:MAX_PAGES_PER_ATT]:
        try:
            with open(jpg, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            page_num = int(jpg.stem.split("_")[1])
            images.append({"base64": b64, "page": page_num})
        except:
            pass
    return images

def _pdf_to_images_direct(pdf_path: Path) -> List[Dict]:
    try:
        doc = fitz.open(str(pdf_path))
        images = []
        for page_num in range(min(len(doc), MAX_PAGES_PER_ATT)):
            page = doc[page_num]
            mat = fitz.Matrix(150/72, 150/72)
            pix = page.get_pixmap(matrix=mat)
            b64 = base64.b64encode(pix.tobytes("png")).decode()
            images.append({"base64": b64, "page": page_num + 1})
        doc.close()
        return images
    except:
        return []

def _image_to_b64(img_path: Path) -> List[Dict]:
    try:
        with open(img_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        return [{"base64": b64, "page": 1}]
    except:
        return []

def extract_email(email_id: str, body: str, attachments: List[Dict]) -> tuple:
    content = []
    body_text = body.strip() if body else "(无正文)"
    content.append({"type": "text", "text": f"[Email Body Start]\n{body_text}\n[Email Body End]\n\n"})

    if attachments:
        content.append({"type": "text", "text": "[Attachments]\n"})
        for att in attachments[:MAX_ATTACHMENTS]:
            content.append({"type": "text", "text": f"\n--- {att['filename']} ---\n"})
            for img in att.get("images", [])[:MAX_PAGES_PER_ATT]:
                content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img['base64']}"}})

    content.append({"type": "text", "text": EXTRACTION_PROMPT})

    payload = {
        "model": MODEL_NAME,
        "messages": [{"role": "user", "content": content}],
        "max_tokens": MAX_TOKENS,
        "temperature": 0,
        "response_format": {"type": "json_schema", "json_schema": {"name": "unified_extraction", "schema": VLM_OUTPUT_SCHEMA}}
    }

    start = time.time()
    resp = requests.post(VLLM_URL, json=payload, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    duration = time.time() - start

    resp_json = resp.json()
    choice = resp_json["choices"][0]
    
    if choice.get("finish_reason") == "length":
        raise ValueError("输出截断")

    raw = choice["message"].get("content", "")
    if "</think>" in raw:
        raw = raw.split("</think>")[-1].strip()
    if not raw.rstrip().endswith("}"):
        raise ValueError("JSON不完整")

    result = json.loads(raw)
    result["_extraction_meta"] = {
        "version": "v3.11",
        "extracted_at": datetime.now().isoformat(),
        "duration_sec": round(duration, 2),
        "attachment_count": len(attachments),
        "model": MODEL_NAME
    }
    return result, duration

def run_batch_extraction(limit: int = None, resume: bool = True):
    print("=" * 60)
    print("🚀 V3.11 批量提取 (按大小排序，小文件优先)")
    print("=" * 60)

    client = pymongo.MongoClient("mongodb://localhost:27017")
    db = client.vulcan_brain

    if not PROGRESS_PATH.exists():
        print("❌ 找不到 download_progress.json")
        return

    download_data = json.loads(PROGRESS_PATH.read_text())
    downloaded = [r for r in download_data if r["status"] in ("downloaded", "processed")]

    # 按 email_id 分组，计算总大小
    email_data = defaultdict(lambda: {"attachments": [], "total_size": 0})
    for r in downloaded:
        eid = r["email_id"]
        email_data[eid]["attachments"].append(r)
        local_path = Path(r.get("local_path", ""))
        if local_path.exists():
            email_data[eid]["total_size"] += local_path.stat().st_size

    # 按大小排序（小的优先）
    sorted_emails = sorted(email_data.items(), key=lambda x: x[1]["total_size"])
    
    print(f"📧 邮件数: {len(sorted_emails)}")
    print(f"📎 附件数: {len(downloaded)}")

    # 加载已提取状态
    extracted_ids = set()
    if resume and EXTRACTION_STATE_PATH.exists():
        state = json.loads(EXTRACTION_STATE_PATH.read_text())
        extracted_ids = set(state.get("extracted_ids", []))
        print(f"✅ 已提取: {len(extracted_ids)}")

    # 过滤
    to_extract = [(eid, data) for eid, data in sorted_emails if eid not in extracted_ids]
    if limit:
        to_extract = to_extract[:limit]

    print(f"🎯 待提取: {len(to_extract)}")
    if to_extract:
        sizes = [d["total_size"] for _, d in to_extract]
        print(f"📊 大小范围: {min(sizes)//1024}KB ~ {max(sizes)//1024}KB")
    print()

    if not to_extract:
        print("✅ 全部完成!")
        return

    success, failed, skipped = 0, 0, 0
    consecutive_failures = 0
    start_time = datetime.now()

    for i, (email_id, data) in enumerate(to_extract):
        att_records = data["attachments"]
        total_size = data["total_size"]

        if (i + 1) % 20 == 0:
            elapsed = (datetime.now() - start_time).total_seconds() / 60
            rate = (i + 1) / elapsed if elapsed > 0 else 0
            print(f"\n{'='*60}")
            print(f"📊 进度: {i+1}/{len(to_extract)} | ✅{success} ❌{failed}")
            print(f"⏱️ 速度: {rate:.1f}/min")
            print(f"{'='*60}\n")

        try:
            email = db.emails.find_one({"_id": ObjectId(email_id)})
            if not email:
                failed += 1
                continue

            subject = email.get("subject", "")[:50]
            body = email.get("body", "") or email.get("body_clean", "") or ""
            size_kb = total_size // 1024

            print(f"  [{i+1}/{len(to_extract)}] ({size_kb}KB) {subject}...")

            attachments = []
            for r in att_records:
                images = load_attachment_images(r["local_path"], r["filename"])
                if images:
                    attachments.append({"filename": r["filename"], "images": images})
                    print(f"      📎 {r['filename'][:40]}... ({len(images)}页)")

            if not attachments and not body.strip():
                print(f"      ⏭️ 无内容")
                skipped += 1
                continue

            result, duration = extract_email(email_id, body, attachments)

            db.emails.update_one(
                {"_id": ObjectId(email_id)},
                {"$set": {"v3_unified_extraction": result}}
            )

            fact_count = len(result.get("facts", []))
            print(f"      ✅ {fact_count} facts, {duration:.1f}s")

            log = ExtractionLog(email_id, subject, "success", len(attachments), total_size, fact_count, duration)
            _write_log(log)

            extracted_ids.add(email_id)
            success += 1
            consecutive_failures = 0

        except Exception as e:
            err = str(e)[:50]
            print(f"      ❌ {err}")
            log = ExtractionLog(email_id, subject if 'subject' in dir() else "", "failed", len(att_records) if 'att_records' in dir() else 0, total_size, error=str(e)[:100])
            _write_log(log)
            failed += 1
            consecutive_failures += 1

            # 连续失败3次，可能是大文件区域，停止
            if consecutive_failures >= 3:
                print(f"\n⚠️ 连续失败{consecutive_failures}次，可能进入大文件区域")
                print(f"💡 剩余 {len(to_extract)-i-1} 封邮件建议用 Gemini 处理")
                break

        _save_state(extracted_ids)

    elapsed = (datetime.now() - start_time).total_seconds() / 60
    print(f"\n{'='*60}")
    print(f"📊 提取完成!")
    print(f"{'='*60}")
    print(f"✅ 成功: {success}")
    print(f"❌ 失败: {failed}")
    print(f"⏭️ 跳过: {skipped}")
    print(f"⏱️ 总耗时: {elapsed:.1f} 分钟")
    if success + failed > 0:
        print(f"📈 成功率: {success/(success+failed)*100:.1f}%")

def _write_log(log: ExtractionLog):
    with open(EXTRACTION_LOG_PATH, "a") as f:
        f.write(json.dumps(asdict(log), ensure_ascii=False) + "\n")

def _save_state(extracted_ids: set):
    EXTRACTION_STATE_PATH.write_text(json.dumps({
        "extracted_ids": list(extracted_ids),
        "updated_at": datetime.now().isoformat()
    }, indent=2))

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int)
    parser.add_argument("--no-resume", action="store_true")
    args = parser.parse_args()
    run_batch_extraction(limit=args.limit, resume=not args.no_resume)
