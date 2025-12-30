#!/usr/bin/env python3
"""
V3.12 批量提取器 (Prompt 增强版)
- 解决序号污染问题
- Identifier vs Number 区分
- 金额必须带单位
"""
import os
import io
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
from PIL import Image
import subprocess

def restart_vllm():
    print("      🔄 vLLM 崩溃，正在重启...")
    subprocess.run(["docker", "restart", "qwen3-vl"], capture_output=True)
    import time
    for i in range(60):
        time.sleep(5)
        try:
            resp = requests.get("http://localhost:8000/health", timeout=5)
            if resp.status_code == 200:
                print("      ✅ vLLM 已重启")
                return True
        except:
            pass
        if i % 6 == 0:
            print(f"      ⏳ 等待 vLLM 启动... ({(i+1)*5}s)")
    return False



# ============ 配置 ============
VLLM_URL = "http://localhost:8000/v1/chat/completions"
MODEL_NAME = "Qwen/Qwen3-VL-30B-A3B-Thinking-FP8"

CACHE_DIR = Path.home() / "vulcan_data" / "cache"
RAW_DIR = CACHE_DIR / "raw"
IMAGES_DIR = CACHE_DIR / "images"
PROGRESS_PATH = CACHE_DIR / "download_progress.json"
EXTRACTION_LOG_PATH = CACHE_DIR / "extraction_log_v312.jsonl"  # 新日志文件
EXTRACTION_STATE_PATH = CACHE_DIR / "extraction_state_v312.json"  # 新状态文件

MAX_TOKENS = 16000  # 减少输出长度
MAX_PAGES_PER_ATT = 3  # 只取第一页
MAX_ATTACHMENTS = 5  # 减少附件数
RETRY_COUNT = 0
MAX_FILE_SIZE_KB = 999999  # 跳过大于此大小的附件(KB)
REQUEST_TIMEOUT = 150

# ============ 图像优化配置 ============
MAX_IMAGE_SIZE = 784  # 更保守，减少 token  # 最大边长 1024px，平衡清晰度和 token 消耗
JPEG_QUALITY = 75      # JPEG 压缩质量

# ============ V3.12 增强 Schema ============
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
                    "type": {
                        "type": "string",
                        "enum": ["identifier", "amount", "quantity", "date", "company", "person", "product", "location", "other"]
                    },
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

# ============ V3.12 增强 Prompt ============
EXTRACTION_PROMPT = """You are a B2B Document Data Extraction Expert. Extract structured business facts from the email and attachments.

**CRITICAL RULES - MUST FOLLOW:**

1. **NO ROW INDICES OR PAGE NUMBERS:**
   - Do NOT extract table row numbers (1, 2, 3, 4...) as facts
   - Do NOT extract page numbers as facts
   - Do NOT extract serial sequence numbers from tables
   - ONLY extract meaningful business data

2. **IDENTIFIER vs QUANTITY - CHOOSE CORRECTLY:**
   - type="identifier" for: Invoice No, PO No, Tracking No, Container No, HS Code, Waybill No, Reference No, Order ID
   - type="quantity" for: counts with units (150 pcs, 30 kg, 5 boxes)
   - type="amount" for: money values (USD 350.00, €500, ¥10000)
   - If a value contains letters/special chars (e.g., "SINIR06094668", "INV-2025-001"), it is an "identifier"

3. **AMOUNTS MUST HAVE CURRENCY UNIT:**
   - When extracting amount/price, ALWAYS include the currency
   - Look for currency in: the cell itself, table header, or document header
   - Output: value="350.00", unit="USD"
   - If currency cannot be determined, use unit="unknown_currency"

4. **DEDUPLICATION:**
   - Same information appearing multiple times = extract ONCE only
   - Use the most complete source (attachment > body if both have same info)

5. **SOURCE TRACKING:**
   - Body content: source_type="body"
   - Attachment content: source_type="attachment", include source_file and source_page

**OUTPUT FORMAT:**
Return a valid JSON object with: email_type, summary, document_date, facts[], companies[], products[], persons[]

**FACT TYPES (use exactly these values):**
- identifier: unique IDs, reference numbers, tracking numbers
- amount: monetary values (MUST have currency unit)
- quantity: counts, weights, dimensions (with unit like pcs, kg, m)
- date: dates and time periods
- company: company/organization names
- person: person names
- product: product names, descriptions
- location: addresses, cities, countries
- other: anything else important

IMPORTANT: Output ONLY the JSON object. No explanation, no reasoning, no markdown code blocks. Start directly with { and end with }.

Now analyze the document and extract all business-relevant facts."""

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

# ============ 图像优化函数 ============
def _resize_and_compress(img_data: bytes, max_size: int = MAX_IMAGE_SIZE, quality: int = JPEG_QUALITY) -> str:
    """
    Resize image to max_size (longest edge) and compress to JPEG.
    Returns base64 encoded string.
    """
    img = Image.open(io.BytesIO(img_data))

    # Convert to RGB if necessary (for PNG with alpha)
    if img.mode in ('RGBA', 'P'):
        img = img.convert('RGB')

    # Resize if larger than max_size
    w, h = img.size
    if max(w, h) > max_size:
        if w > h:
            new_w = max_size
            new_h = int(h * max_size / w)
        else:
            new_h = max_size
            new_w = int(w * max_size / h)
        img = img.resize((new_w, new_h), Image.LANCZOS)

    # Compress to JPEG
    buffer = io.BytesIO()
    img.save(buffer, format='JPEG', quality=quality, optimize=True)
    return base64.b64encode(buffer.getvalue()).decode()


# ============ 图片加载 (优化版) ============
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
        else:
            return []
    elif ext in ("png", "jpg", "jpeg"):
        return _image_to_b64(path)
    return []

def _load_from_dir(img_dir: Path) -> List[Dict]:
    images = []
    for jpg in sorted(img_dir.glob("page_*.jpg"))[:MAX_PAGES_PER_ATT]:
        try:
            with open(jpg, "rb") as f:
                img_data = f.read()
            b64 = _resize_and_compress(img_data)  # 优化: resize + compress
            page_num = int(jpg.stem.split("_")[1])
            images.append({"base64": b64, "page": page_num})
        except Exception:
            pass
    return images

def _pdf_to_images_direct(pdf_path: Path) -> List[Dict]:
    try:
        doc = fitz.open(str(pdf_path))
        images = []
        for page_num in range(min(len(doc), MAX_PAGES_PER_ATT)):
            page = doc[page_num]
            # 降低 DPI 到 100 (原 150)，然后再 resize
            mat = fitz.Matrix(100/72, 100/72)
            pix = page.get_pixmap(matrix=mat)
            img_data = pix.tobytes("png")
            b64 = _resize_and_compress(img_data)  # 优化: resize + compress
            images.append({"base64": b64, "page": page_num + 1})
        doc.close()
        return images
    except Exception:
        return []

def _image_to_b64(img_path: Path) -> List[Dict]:
    try:
        with open(img_path, "rb") as f:
            img_data = f.read()
        b64 = _resize_and_compress(img_data)  # 优化: resize + compress
        return [{"base64": b64, "page": 1}]
    except Exception:
        return []

# ============ 核心提取 ============
def extract_email(email_id: str, body: str, attachments: List[Dict]) -> tuple:
    content = []

    # 正文
    body_text = body.strip() if body else "(No body content)"
    content.append({
        "type": "text",
        "text": f"[EMAIL BODY START]\n{body_text}\n[EMAIL BODY END]\n\n"
    })

    # 附件
    if attachments:
        content.append({"type": "text", "text": "[ATTACHMENTS]\n"})
        for att in attachments[:MAX_ATTACHMENTS]:
            content.append({
                "type": "text",
                "text": f"\n--- File: {att['filename']} ---\n"
            })
            for img in att.get("images", [])[:MAX_PAGES_PER_ATT]:
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{img['base64']}"}
                })

    content.append({"type": "text", "text": EXTRACTION_PROMPT})

    payload = {
        "model": MODEL_NAME,
        "messages": [{"role": "user", "content": content}],
        "max_tokens": MAX_TOKENS,
        "temperature": 0,
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "unified_extraction", "schema": VLM_OUTPUT_SCHEMA}
        }
    }

    start = time.time()
    resp = requests.post(VLLM_URL, json=payload, timeout=REQUEST_TIMEOUT)
    if resp.status_code != 200:
        try:
            err_detail = resp.json().get("error", {}).get("message", resp.text[:200])
        except:
            err_detail = resp.text[:200]
        raise ValueError(f"{resp.status_code}: {err_detail}")
    duration = time.time() - start

    resp_json = resp.json()
    choice = resp_json["choices"][0]

    finish_reason = choice.get("finish_reason", "")
    if finish_reason == "length":
        raise ValueError(f"Output truncated (finish_reason=length)")

    msg = choice["message"]
    raw = msg.get("content", "").strip()


    if not raw.rstrip().endswith("}"):
        raise ValueError(f"Incomplete JSON, ends with: ...{raw[-50:]}")

    result = json.loads(raw)
    result["_extraction_meta"] = {
        "version": "v3.12",
        "extracted_at": datetime.now().isoformat(),
        "duration_sec": round(duration, 2),
        "attachment_count": len(attachments),
        "model": MODEL_NAME
    }

    return result, duration

# ============ 批量处理 ============
def run_batch_extraction(limit: int = None, resume: bool = True):
    print("=" * 60)
    print("🚀 V3.12 批量提取 (Prompt 增强版)")
    print("=" * 60)
    print("修复: 序号污染 | Identifier区分 | 金额单位")
    print()

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

    # 按大小排序
    sorted_emails = sorted(email_data.items(), key=lambda x: x[1]["total_size"])

    print(f"📧 邮件数: {len(sorted_emails)}")
    print(f"📎 附件数: {len(downloaded)}")

    # 加载已提取状态
    extracted_ids = set()
    if resume and EXTRACTION_STATE_PATH.exists():
        state = json.loads(EXTRACTION_STATE_PATH.read_text())
        extracted_ids = set(state.get("extracted_ids", []))
        print(f"✅ 已提取: {len(extracted_ids)}")

    # 过滤待提取
    to_extract = [(eid, data) for eid, data in sorted_emails if eid not in extracted_ids]
    if limit:
        to_extract = to_extract[:limit]

    print(f"🎯 待提取: {len(to_extract)}")
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
        size_kb = total_size // 1024

        # 进度报告
        if (i + 1) % 20 == 0:
            elapsed = (datetime.now() - start_time).total_seconds() / 60
            rate = (i + 1) / elapsed if elapsed > 0 else 0
            remaining = len(to_extract) - i - 1
            eta = remaining / rate if rate > 0 else 0
            print(f"\n{'='*60}")
            print(f"📊 进度: {i+1}/{len(to_extract)} | ✅{success} ❌{failed} ⏭️{skipped}")
            print(f"⏱️ 速度: {rate:.1f}/min | 预计剩余: {eta:.0f}min")
            print(f"{'='*60}\n")

        try:
            email = db.emails.find_one({"_id": ObjectId(email_id)})
            if not email:
                print(f"  [{i+1}] ⚠️ 邮件不存在: {email_id}")
                extracted_ids.add(email_id)
                failed += 1
                continue

            subject = email.get("subject", "")[:50]
            body = email.get("body", "") or email.get("body_clean", "") or ""

            print(f"  [{i+1}/{len(to_extract)}] ({size_kb}KB) {subject}...")

            # 文件大小检查 - 跳过太大的文件
            if size_kb > MAX_FILE_SIZE_KB:
                print(f"      ⏭️ 文件太大 ({size_kb}KB > {MAX_FILE_SIZE_KB}KB)，跳过")
                log = ExtractionLog(email_id, subject, "skipped", 0, total_size, error=f"file_too_large_{size_kb}KB")
                _write_log(log)
                skipped += 1
                continue

            # 加载附件图片
            attachments = []
            for r in att_records:
                images = load_attachment_images(r["local_path"], r["filename"])
                if images:
                    attachments.append({
                        "filename": r["filename"],
                        "images": images
                    })
                    print(f"      📎 {r['filename'][:40]}... ({len(images)}页)")

            if not attachments and not body.strip():
                print(f"      ⏭️ 无内容，跳过")
                log = ExtractionLog(email_id, subject, "skipped", 0, total_size, error="no_content")
                _write_log(log)
                skipped += 1
                continue

            # 提取
            result, duration = extract_email(email_id, body, attachments)

            # 写入 MongoDB (使用新字段名)
            db.emails.update_one(
                {"_id": ObjectId(email_id)},
                {"$set": {"v3_extraction_v312": result}}
            )

            fact_count = len(result.get("facts", []))
            print(f"      ✅ {fact_count} facts, {duration:.1f}s")

            log = ExtractionLog(email_id, subject, "success", len(attachments), total_size, fact_count, duration)
            _write_log(log)

            extracted_ids.add(email_id)
            success += 1
            consecutive_failures = 0

        except Exception as e:
            err_msg = str(e)[:200]
            
            # 区分错误类型
            if "400" in err_msg or "maximum context length" in err_msg.lower():
                # Token overflow - 快速跳过，标记为需要 map-reduce
                print(f"      ⏭️ Token超限，跳过 (需Map-Reduce)")
                log = ExtractionLog(email_id, subject if "subject" in dir() else "", "skipped", len(att_records) if "att_records" in dir() else 0, total_size, error="token_overflow")
                skipped += 1
            elif "500" in err_msg or "Internal Server Error" in err_msg or "Connection" in err_msg or "reset" in err_msg.lower():
                print(f"      ⏭️ vLLM崩溃，跳过 (需Map-Reduce)")
                restart_vllm()
                log = ExtractionLog(email_id, subject if "subject" in dir() else "", "skipped", len(att_records) if "att_records" in dir() else 0, total_size, error="vllm_crash")
                skipped += 1
            elif "truncated" in err_msg.lower() or "length" in err_msg.lower():
                # 输出被截断
                print(f"      ⏭️ 输出截断，跳过")
                log = ExtractionLog(email_id, subject if "subject" in dir() else "", "skipped", len(att_records) if "att_records" in dir() else 0, total_size, error="output_truncated")
                skipped += 1
            elif "timed out" in err_msg.lower() or "timeout" in err_msg.lower():
                # 超时 - 可能是处理太慢
                print(f"      ⏭️ 超时，跳过")
                log = ExtractionLog(email_id, subject if "subject" in dir() else "", "skipped", len(att_records) if "att_records" in dir() else 0, total_size, error="timeout")
                skipped += 1
            else:
                # 其他错误
                print(f"      ❌ 失败: {err_msg[:80]}")
                log = ExtractionLog(email_id, subject if "subject" in dir() else "", "failed", len(att_records) if "att_records" in dir() else 0, total_size, error=err_msg[:100])
                failed += 1
                consecutive_failures += 1
            
            _write_log(log)
            extracted_ids.add(email_id)

            if consecutive_failures >= 9999:
                print(f"\n⚠️ 连续失败{consecutive_failures}次，可能进入大文件区域")
                print(f"💡 剩余 {len(to_extract)-i-1} 封邮件建议用 Gemini 处理")
                break

        _save_state(extracted_ids)

    # 最终统计
    elapsed = (datetime.now() - start_time).total_seconds() / 60
    print(f"\n{'='*60}")
    print(f"📊 V3.12 提取完成!")
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
