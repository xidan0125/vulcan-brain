#!/usr/bin/env python3
"""
V3.9 批量统一提取器 (质量优先版)
- 单线程顺序执行，质量第一
- max_tokens=16384，解决 Thinking 模型输出截断问题
- 截断检测 + 完整性校验
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

# 质量优先配置
# 关键：Thinking模型会先输出思考内容，消耗大量token
# 之前 4096 导致 JSON 在 ~12k字符处被截断
# 16384 tokens ≈ 48k+ 字符，足够 thinking + JSON
MAX_TOKENS = 16384
MAX_PAGES_PER_ATT = 5  # 每个附件最多5页
MAX_ATTACHMENTS = 8  # 每封邮件最多8个附件
RETRY_COUNT = 0  # 失败重试1次（主要是网络问题）
REQUEST_TIMEOUT = 600  # 10分钟超时

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

请仔细分析后输出JSON。"""

@dataclass
class ExtractionLog:
    email_id: str
    subject: str
    status: str
    attachment_count: int
    fact_count: int = 0
    duration: float = 0
    error: Optional[str] = None
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

# ============ 统一图片加载 ============
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
                b64 = base64.b64encode(f.read()).decode()
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
            mat = fitz.Matrix(150/72, 150/72)
            pix = page.get_pixmap(matrix=mat)
            b64 = base64.b64encode(pix.tobytes("png")).decode()
            images.append({"base64": b64, "page": page_num + 1})
        doc.close()
        return images
    except Exception:
        return []

def _image_to_b64(img_path: Path) -> List[Dict]:
    try:
        with open(img_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        return [{"base64": b64, "page": 1}]
    except Exception:
        return []

# ============ 核心提取 (带重试) ============
def extract_email_with_retry(email_id: str, body: str, attachments: List[Dict], retry: int = RETRY_COUNT) -> tuple:
    """带重试的提取"""
    last_error = None

    for attempt in range(retry + 1):
        try:
            result, duration = _do_extract(email_id, body, attachments)
            return result, duration, None
        except json.JSONDecodeError as e:
            last_error = f"JSON解析失败: {str(e)[:100]}"
            print(f"      重试 {attempt+1}/{retry+1}: {last_error}")
            time.sleep(2)
        except requests.exceptions.Timeout:
            last_error = "请求超时"
            print(f"      重试 {attempt+1}/{retry+1}: {last_error}")
            time.sleep(5)
        except Exception as e:
            last_error = str(e)[:100]
            print(f"      重试 {attempt+1}/{retry+1}: {last_error}")
            time.sleep(2)

    return None, 0, last_error

def _do_extract(email_id: str, body: str, attachments: List[Dict]) -> tuple:
    """执行单次提取"""
    content = []

    # 正文
    body_text = body.strip() if body else "(无正文)"
    content.append({
        "type": "text",
        "text": f"[Email Body Start]\n{body_text}\n[Email Body End]\n\n"
    })

    # 附件
    if attachments:
        content.append({"type": "text", "text": "[Attachments]\n"})
        for att in attachments[:MAX_ATTACHMENTS]:
            content.append({
                "type": "text",
                "text": f"\n--- {att['filename']} ---\n"
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
    resp.raise_for_status()
    duration = time.time() - start

    resp_json = resp.json()
    choice = resp_json["choices"][0]

    # 检查是否被截断
    finish_reason = choice.get("finish_reason", "")
    if finish_reason == "length":
        raise ValueError(f"输出被截断 (finish_reason=length)，需要更大的 max_tokens")

    raw = choice["message"]["content"]

    # 处理 thinking 标签
    if "</think>" in raw:
        raw = raw.split("</think>")[-1].strip()

    # 额外检查：JSON 是否完整（以 } 结尾）
    if not raw.rstrip().endswith("}"):
        raise ValueError(f"JSON 不完整，末尾: ...{raw[-50:]}")

    result = json.loads(raw)
    result["_extraction_meta"] = {
        "version": "v3.9",
        "extracted_at": datetime.now().isoformat(),
        "duration_sec": round(duration, 2),
        "attachment_count": len(attachments),
        "model": MODEL_NAME
    }

    return result, duration

# ============ 批量处理 ============
def run_batch_extraction(limit: int = None, resume: bool = True):
    print("=" * 60)
    print("🚀 V3.9 批量统一提取 (质量优先)")
    print("=" * 60)
    print(f"配置: max_tokens={MAX_TOKENS}, 重试={RETRY_COUNT}次")
    print(f"修复: Thinking模型输出截断问题")
    print()

    client = pymongo.MongoClient("mongodb://localhost:27017")
    db = client.vulcan_brain

    if not PROGRESS_PATH.exists():
        print("❌ 找不到 download_progress.json")
        return

    download_data = json.loads(PROGRESS_PATH.read_text())
    downloaded = [r for r in download_data if r["status"] in ("downloaded", "processed")]

    # 按 email_id 分组
    email_attachments = defaultdict(list)
    for r in downloaded:
        email_attachments[r["email_id"]].append(r)

    print(f"📧 邮件数: {len(email_attachments)}")
    print(f"📎 附件数: {len(downloaded)}")

    # 加载已提取状态
    extracted_ids = set()
    if resume and EXTRACTION_STATE_PATH.exists():
        state = json.loads(EXTRACTION_STATE_PATH.read_text())
        extracted_ids = set(state.get("extracted_ids", []))
        print(f"✅ 已提取: {len(extracted_ids)}")

    # 过滤待提取
    to_extract = {eid: atts for eid, atts in email_attachments.items() if eid not in extracted_ids}
    if limit:
        to_extract = dict(list(to_extract.items())[:limit])

    print(f"🎯 待提取: {len(to_extract)}")
    print()

    if not to_extract:
        print("✅ 全部完成!")
        return

    success, failed, skipped = 0, 0, 0
    start_time = datetime.now()

    for i, (email_id, att_records) in enumerate(to_extract.items()):
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
                failed += 1
                continue

            subject = email.get("subject", "")[:50]
            body = email.get("body", "") or email.get("body_clean", "") or ""

            print(f"  [{i+1}/{len(to_extract)}] {subject}...")

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
                log = ExtractionLog(email_id, subject, "skipped", 0, error="no_content")
                _write_log(log)
                skipped += 1
                continue

            # 提取 (带重试)
            result, duration, error = extract_email_with_retry(email_id, body, attachments)

            if result:
                # 写入 MongoDB
                db.emails.update_one(
                    {"_id": ObjectId(email_id)},
                    {"$set": {"v3_unified_extraction": result}}
                )

                fact_count = len(result.get("facts", []))
                print(f"      ✅ 成功! {fact_count} facts, {duration:.1f}s")

                log = ExtractionLog(email_id, subject, "success", len(attachments), fact_count, duration)
                _write_log(log)

                extracted_ids.add(email_id)
                success += 1
            else:
                print(f"      ❌ 失败: {error}")
                log = ExtractionLog(email_id, subject, "failed", len(attachments), error=error)
                _write_log(log)
                failed += 1

        except Exception as e:
            print(f"      ❌ 异常: {str(e)[:50]}")
            log = ExtractionLog(email_id, subject if 'subject' in dir() else "", "failed", 0, error=str(e)[:100])
            _write_log(log)
            failed += 1

        # 每次都保存状态
        _save_state(extracted_ids)

    # 最终统计
    elapsed = (datetime.now() - start_time).total_seconds() / 60
    print(f"\n{'='*60}")
    print(f"📊 提取完成!")
    print(f"{'='*60}")
    print(f"✅ 成功: {success}")
    print(f"❌ 失败: {failed}")
    print(f"⏭️ 跳过: {skipped}")
    print(f"⏱️ 总耗时: {elapsed:.1f} 分钟")
    print(f"📈 成功率: {success/(success+failed)*100:.1f}%" if (success+failed) > 0 else "")

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
