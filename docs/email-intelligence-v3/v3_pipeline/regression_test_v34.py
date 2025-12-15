#!/usr/bin/env python3
"""
V3.4 Schema压力测试 - Guided Decoding (JSON Schema约束)
核心改进:
  1. 使用vLLM guided_json强制JSON格式输出
  2. Pydantic模型定义Schema
  3. 彻底解决JSON格式崩坏和List问题
"""
import os
import sys
import json
import base64
import subprocess
import tempfile
import requests
import fitz  # PyMuPDF
import pymongo
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple, Any

# ============ 配置 ============
VLLM_URL = "http://localhost:8000/v1/chat/completions"
MODEL_NAME = "Qwen/Qwen3-VL-30B-A3B-Thinking-FP8"
CACHE_DIR = Path.home() / "attachment_cache" / "phase25_test"
RESULTS_DIR = Path.home() / "vulcan-brain/docs/email-intelligence-v3/progress"

# V3.4: 启用/禁用Guided Decoding (用于A/B测试)
USE_GUIDED_DECODING = True

FAILED_SAMPLES = [
    "AAMkADVkYTU2ZmMx_SINIR06094668.pdf",
    "AAMkADYzNjY4ZmNi_image001.png",
    "AAMkAGViNzg3ODQw_28Oct2024 proposal for Battery Room.xlsx"
]

# ============ V3.4 简化Schema (避免复杂Enum导致xgrammar问题) ============
# 注意: xgrammar对复杂enum支持有限，使用string类型+additionalProperties

EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "document_type": {
            "type": "string",
            "description": "文档类型: Quotation/Invoice/Contract/PurchaseOrder/Resume/ShippingDoc/Other等"
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
                    "type": {"type": "string", "description": "类型: Amount/Date/Company/Product/Identifier/Other等"},
                    "key": {"type": "string"},
                    "value": {"type": "string"}
                },
                "required": ["type", "key", "value"]
            }
        },
        "companies": {
            "type": "array",
            "items": {"type": "string"}
        },
        "products": {
            "type": "array",
            "items": {"type": "string"}
        },
        "summary": {"type": "string"}
    },
    "required": ["document_type", "facts", "summary"]
}

# ============ Prompt (简化版，因为有Schema约束) ============
EXTRACTION_PROMPT = """你是一个B2B商业文档分析专家。请仔细分析这份文档，提取所有关键商业信息。

【特别说明】:
- **Identifier**: 用于所有编号类字段，如发票号(Invoice No)、运单号(Tracking No)、订单号(PO No)、账号(Account No)等。

请提取文档中的关键信息，包括金额、日期、公司名、产品、各类编号等。"""

# ============ Identifier分类规则 (复用V3.3) ============
import re

IDENTIFIER_RULES = {
    "FINANCE": {
        "keywords": ["invoice", "inv no", "发票", "account", "账号", "账户", "gst", "tax", "transaction", "txn", "bank"],
        "subtypes": {
            "INVOICE_NUMBER": ["invoice", "inv no", "发票号"],
            "ACCOUNT_NUMBER": ["account no", "account number", "账号", "账户"],
            "TAX_CODE": ["gst", "tax code", "税号"],
            "TRANSACTION_REF": ["transaction", "txn", "reference"],
            "BANK_ACCOUNT": ["bank account", "银行账"]
        }
    },
    "LOGISTICS": {
        "keywords": ["booking", "b/l", "bl no", "提单", "po no", "purchase order", "订单", "hs code", "海关编码", "cnee", "consignee", "收货"],
        "subtypes": {
            "BOOKING_NUMBER": ["booking"],
            "BL_NUMBER": ["b/l", "bl no", "提单"],
            "PO_NUMBER": ["po no", "po number", "purchase order", "订单号"],
            "HS_CODE": ["hs code", "海关编码"],
            "CONSIGNEE_REF": ["cnee", "consignee", "收货人"]
        }
    },
    "LEGAL": {
        "keywords": ["registration", "注册号", "agreement", "contract", "合同", "审批", "approval", "exhibit", "reference", "ref no"],
        "subtypes": {
            "REGISTRATION_NUMBER": ["registration", "注册号", "uen"],
            "CONTRACT_NUMBER": ["agreement", "contract", "合同号"],
            "APPROVAL_NUMBER": ["审批", "approval", "批准"],
            "EXHIBIT_NUMBER": ["exhibit"],
            "REFERENCE_NUMBER": ["reference", "ref no", "ref."]
        }
    },
    "PRODUCT": {
        "keywords": ["serial", "序列号", "sn", "s/n", "model", "型号", "part no", "item no"],
        "subtypes": {
            "SERIAL_NUMBER": ["serial", "序列号", "sn", "s/n"],
            "MODEL_NUMBER": ["model", "型号"],
            "PART_NUMBER": ["part no", "item no", "料号"]
        }
    },
    "SHIPPING": {
        "keywords": ["seal", "container", "集装箱"],
        "subtypes": {
            "SEAL_NUMBER": ["seal"],
            "CONTAINER_NUMBER": ["container", "集装箱"]
        }
    }
}

def classify_identifier(key: str, value: str) -> tuple:
    """对Identifier进行二级分类"""
    key_lower = key.lower().strip()
    value_str = str(value) if value else ""

    if "http" in value_str or "www." in value_str:
        return ("CONTACT", "WEBSITE")
    if "@" in value_str and "." in value_str:
        return ("CONTACT", "EMAIL")

    for category, rules in IDENTIFIER_RULES.items():
        for keyword in rules["keywords"]:
            if keyword in key_lower:
                for subtype, subtype_keywords in rules["subtypes"].items():
                    for sk in subtype_keywords:
                        if sk in key_lower:
                            return (category, subtype)
                return (category, f"GENERIC_{category}")

    if re.match(r'^\d{10,}$', value_str):
        if any(k in key_lower for k in ["tracking", "waybill", "运单"]):
            return ("LOGISTICS", "TRACKING_NUMBER")
        return ("UNKNOWN", "LONG_NUMBER")

    return ("UNKNOWN", "GENERIC_ID")

def post_process_extraction(extraction: dict) -> dict:
    """后处理：Identifier分类"""
    if not extraction or "facts" not in extraction:
        return extraction

    processed_facts = []
    reclassified_count = 0

    for fact in extraction.get("facts", []):
        fact_type = fact.get("type", "")
        key = fact.get("key", "")
        value = fact.get("value", "")

        if fact_type == "Identifier":
            category, subtype = classify_identifier(key, value)
            if category == "CONTACT":
                fact["type"] = "Contact"
                fact["_reclassified_from"] = "Identifier"
                reclassified_count += 1
            else:
                fact["identifier_category"] = category
                fact["identifier_subtype"] = subtype

        processed_facts.append(fact)

    extraction["facts"] = processed_facts
    extraction["_post_processed"] = True
    extraction["_reclassified_count"] = reclassified_count
    return extraction

# ============ Excel视觉化流水线 (复用V3.3) ============
from pdf2image import convert_from_path

def excel_to_images(excel_path: Path, dpi: int = 300) -> List[str]:
    """Excel -> PDF -> 分页Image"""
    print(f"    📊 Excel视觉化流水线启动...")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        pdf_path = tmpdir / f"{excel_path.stem}.pdf"

        cmd = ["libreoffice", "--headless", "--convert-to", "pdf", "--outdir", str(tmpdir), str(excel_path)]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if result.returncode != 0:
                raise RuntimeError(f"LibreOffice转换失败: {result.stderr}")
        except subprocess.TimeoutExpired:
            raise RuntimeError("LibreOffice转换超时")

        if not pdf_path.exists():
            pdfs = list(tmpdir.glob("*.pdf"))
            if pdfs:
                pdf_path = pdfs[0]
            else:
                raise RuntimeError(f"PDF文件未生成")

        print(f"       ✅ PDF生成: {pdf_path.stat().st_size / 1024:.1f} KB")

        images = convert_from_path(str(pdf_path), dpi=dpi)
        print(f"       ✅ 生成 {len(images)} 页图片")

        base64_images = []
        max_pages = 3
        for i, img in enumerate(images[:max_pages]):
            from io import BytesIO
            quality = 90
            buf = BytesIO()
            img.save(buf, format='JPEG', quality=quality)
            while buf.tell() > 1024 * 1024 and quality > 50:
                quality -= 10
                buf = BytesIO()
                img.save(buf, format='JPEG', quality=quality)
            buf.seek(0)
            b64 = base64.b64encode(buf.read()).decode()
            base64_images.append(b64)
            print(f"       📄 Page {i+1}: {len(b64) // 1024} KB")

        if len(images) > max_pages:
            print(f"       ⚠️ 仅处理前{max_pages}页 (共{len(images)}页)")

        return base64_images

# ============ V3.4 VLM调用 (带Guided Decoding) ============
def call_vlm_with_schema(content: list, use_guided: bool = True) -> Dict:
    """
    调用VLM，可选启用Guided Decoding
    """
    payload = {
        "model": MODEL_NAME,
        "messages": [{"role": "user", "content": content}],
        "max_tokens": 4096,
        "temperature": 0
    }

    # V3.4: 启用Guided Decoding (正确格式: response_format)
    if use_guided and USE_GUIDED_DECODING:
        payload["response_format"] = {
            "type": "json_schema",
            "json_schema": {
                "name": "extraction_result",
                "schema": EXTRACTION_SCHEMA
            }
        }

    resp = requests.post(VLLM_URL, json=payload, timeout=300)
    resp.raise_for_status()

    raw = resp.json()["choices"][0]["message"]["content"]

    # 解析JSON (有Schema约束应该不会失败)
    try:
        # 清理可能的think标签
        if "</think>" in raw:
            raw = raw.split("</think>")[-1].strip()
        result = json.loads(raw)
        if not isinstance(result, dict):
            raise ValueError(f"期望dict，得到{type(result)}")
        return result, False  # (result, was_error)
    except (json.JSONDecodeError, ValueError) as e:
        print(f"    ⚠️  JSON解析失败 (即使有Schema约束): {e}")
        # 尝试修复
        import json_repair
        try:
            repaired = json_repair.repair_json(raw)
            result = json.loads(repaired)
            if isinstance(result, list):
                # 如果是list，尝试找到第一个dict
                for item in result:
                    if isinstance(item, dict) and "facts" in item:
                        return item, True
                # 否则构造默认结构
                return {"document_type": "Other", "facts": [], "entities": {"companies": [], "products": [], "persons": []}, "summary": "JSON修复后为list"}, True
            if not isinstance(result, dict):
                raise ValueError("修复后仍不是dict")
            return result, True
        except Exception as repair_err:
            return {"document_type": "Other", "facts": [], "entities": {"companies": [], "products": [], "persons": []}, "summary": f"解析失败: {str(e)[:50]}"}, True

def call_vlm_single_image(image_b64: str, mime_type: str = "image/png") -> Tuple[Dict, bool]:
    """单图输入VLM"""
    content = [
        {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{image_b64}"}},
        {"type": "text", "text": EXTRACTION_PROMPT}
    ]
    return call_vlm_with_schema(content)

def call_vlm_multi_image(images_b64: List[str], file_type: str = "Excel") -> Tuple[Dict, bool]:
    """多图输入VLM"""
    content = [{"type": "text", "text": f"【Source: {file_type} ({len(images_b64)} pages)】\n"}]
    for img_b64 in images_b64:
        content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}})
    content.append({"type": "text", "text": EXTRACTION_PROMPT})
    return call_vlm_with_schema(content)

# ============ 文件处理 ============
def pdf_page_to_base64(pdf_path: Path, page_num: int = 0, dpi: int = 150) -> str:
    doc = fitz.open(str(pdf_path))
    page = doc[page_num]
    mat = fitz.Matrix(dpi/72, dpi/72)
    pix = page.get_pixmap(matrix=mat)
    img_bytes = pix.tobytes("png")
    doc.close()
    return base64.b64encode(img_bytes).decode()

def process_pdf(file_path: Path) -> Dict:
    print(f"    📄 PDF处理...")
    doc = fitz.open(str(file_path))
    page_count = min(len(doc), 3)
    doc.close()

    all_facts = []
    all_entities = {"companies": [], "products": [], "persons": []}
    doc_type, summary = None, None
    any_error = False

    for page_num in range(page_count):
        print(f"       处理第{page_num+1}/{page_count}页...")
        img_b64 = pdf_page_to_base64(file_path, page_num)
        result, had_error = call_vlm_single_image(img_b64)
        any_error = any_error or had_error

        if not doc_type:
            doc_type = result.get("document_type")
            summary = result.get("summary")
        all_facts.extend(result.get("facts", []))
        for key in all_entities:
            all_entities[key].extend(result.get("entities", {}).get(key, []))

    for key in all_entities:
        all_entities[key] = list(set(all_entities[key]))

    extraction = {
        "document_type": doc_type,
        "facts": all_facts,
        "entities": all_entities,
        "summary": summary,
        "pages": page_count,
        "_had_json_error": any_error
    }
    return post_process_extraction(extraction)

def process_image(file_path: Path) -> Dict:
    print(f"    🖼️  图片处理...")
    img_b64 = base64.b64encode(file_path.read_bytes()).decode()
    suffix = file_path.suffix.lower()
    mime = "image/png" if suffix == ".png" else "image/jpeg"
    result, had_error = call_vlm_single_image(img_b64, mime)
    result["_had_json_error"] = had_error
    return post_process_extraction(result)

def process_excel(file_path: Path) -> Dict:
    images_b64 = excel_to_images(file_path, dpi=300)
    if not images_b64:
        return {"error": "Excel转图片失败", "facts": []}

    print(f"    🔍 VLM处理 {len(images_b64)} 页Excel图片...")
    result, had_error = call_vlm_multi_image(images_b64, "Excel")
    result["_had_json_error"] = had_error
    return post_process_extraction(result)

def process_file(file_path: Path) -> Dict:
    suffix = file_path.suffix.lower()
    if suffix == ".pdf":
        return process_pdf(file_path)
    elif suffix in [".png", ".jpg", ".jpeg"]:
        return process_image(file_path)
    elif suffix in [".xlsx", ".xls"]:
        return process_excel(file_path)
    else:
        return {"error": f"不支持: {suffix}", "facts": []}

# ============ 数据库抽样 (复用V3.3) ============
def sample_from_db(n: int = 10) -> List[Dict]:
    print(f"\n📊 从数据库抽取 {n} 个高价值附件...")
    client = pymongo.MongoClient("mongodb://localhost:27017/")
    db = client.vulcan_brain

    pipeline = [
        {"$match": {
            "processing_status.v2_extracted": True,
            "has_attachments": True,
            "attachments": {"$elemMatch": {"id": {"$exists": True, "$ne": ""}, "name": {"$regex": r"\.(pdf|xlsx?|png|jpg)$", "$options": "i"}}}
        }},
        {"$sample": {"size": n * 3}}
    ]

    samples = []
    for email in db.emails.aggregate(pipeline):
        if len(samples) >= n:
            break

        user_email = email.get("user_id") or ""
        if not user_email:
            tos = email.get("to", [])
            if tos and isinstance(tos[0], dict):
                user_email = tos[0].get("address", "")

        graph_message_id = email.get("email_id") or email.get("graph_id") or ""
        if not graph_message_id or not user_email:
            continue

        for att in email.get("attachments", []):
            att_id = att.get("id", "")
            filename = att.get("name", "")
            if not att_id:
                continue

            fn_lower = filename.lower()
            is_pdf = fn_lower.endswith('.pdf')
            is_excel = fn_lower.endswith(('.xlsx', '.xls'))
            is_image = fn_lower.endswith(('.png', '.jpg', '.jpeg'))
            size = att.get("size", 0)

            if is_pdf or is_excel or (is_image and size > 50000):
                samples.append({
                    "email_id": str(email["_id"]),
                    "attachment_id": att_id,
                    "filename": filename,
                    "size": size,
                    "user_email": user_email,
                    "graph_message_id": graph_message_id,
                    "email_subject": email.get("subject", "")[:50]
                })
                break

    pdf_count = sum(1 for s in samples if s["filename"].lower().endswith('.pdf'))
    excel_count = sum(1 for s in samples if s["filename"].lower().endswith(('.xlsx', '.xls')))
    image_count = len(samples) - pdf_count - excel_count

    print(f"   ✅ 抽取完成: {len(samples)} 个 (PDF:{pdf_count}, Excel:{excel_count}, 图片:{image_count})")
    return samples

def download_attachment(sample: Dict) -> Optional[Path]:
    cache_file = CACHE_DIR / f"{sample['attachment_id'][:16]}_{sample['filename']}"
    if cache_file.exists():
        return cache_file

    config_path = Path.home() / "vulcan-brain" / "ecosystem.config.js"
    tenant_id = client_id = client_secret = ""
    if config_path.exists():
        import re
        content = config_path.read_text()
        for line in content.split('\n'):
            if 'MS365_TENANT_ID' in line:
                m = re.search(r'"([^"]+)"', line.split(':')[-1])
                if m: tenant_id = m.group(1)
            elif 'MS365_CLIENT_ID' in line:
                m = re.search(r'"([^"]+)"', line.split(':')[-1])
                if m: client_id = m.group(1)
            elif 'MS365_CLIENT_SECRET' in line:
                m = re.search(r'"([^"]+)"', line.split(':')[-1])
                if m: client_secret = m.group(1)

    resp = requests.post(
        f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token",
        data={"client_id": client_id, "client_secret": client_secret, "scope": "https://graph.microsoft.com/.default", "grant_type": "client_credentials"}
    )
    token = resp.json().get("access_token")
    if not token:
        return None

    url = f"https://graph.microsoft.com/v1.0/users/{sample['user_email']}/messages/{sample['graph_message_id']}/attachments/{sample['attachment_id']}/$value"
    try:
        resp = requests.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=120)
        resp.raise_for_status()
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_bytes(resp.content)
        return cache_file
    except:
        return None

# ============ 主流程 ============
def main():
    mode = "regression"
    sample_count = 10

    if len(sys.argv) > 1:
        if sys.argv[1] == "--regression":
            mode = "regression"
        elif sys.argv[1] == "--sample" and len(sys.argv) > 2:
            mode = "sample"
            sample_count = int(sys.argv[2])
        elif sys.argv[1] == "--no-guided":
            global USE_GUIDED_DECODING
            USE_GUIDED_DECODING = False
            mode = "regression"
        else:
            try:
                sample_count = int(sys.argv[1])
                mode = "sample"
            except:
                pass

    print("=" * 60)
    print("🧪 V3.4 压力测试 - Guided Decoding (JSON Schema约束)")
    print("=" * 60)
    print(f"时间: {datetime.now()}")
    print(f"模式: {mode}")
    print(f"Guided Decoding: {'✅ 启用' if USE_GUIDED_DECODING else '❌ 禁用'}")
    print(f"vLLM Schema: {len(json.dumps(EXTRACTION_SCHEMA))} bytes")

    results = []

    if mode == "regression":
        test_files = [(CACHE_DIR / f, f) for f in FAILED_SAMPLES]
    else:
        samples = sample_from_db(sample_count)
        test_files = []
        print("\n⬇️  下载附件...")
        for sample in samples:
            file_path = download_attachment(sample)
            if file_path:
                test_files.append((file_path, sample["filename"]))

    total = len(test_files)
    json_errors = 0

    for i, (file_path, filename) in enumerate(test_files, 1):
        print(f"\n[{i}/{total}] {filename}")

        if not file_path.exists():
            print(f"    ❌ 文件不存在!")
            results.append({"file": filename, "success": False, "error": "文件不存在"})
            continue

        print(f"    📁 文件大小: {file_path.stat().st_size / 1024:.1f} KB")

        start = datetime.now()
        try:
            extraction = process_file(file_path)
            duration = (datetime.now() - start).total_seconds()

            if "error" in extraction and extraction.get("facts", []) == []:
                print(f"    ❌ 失败: {extraction['error']}")
                results.append({"file": filename, "success": False, "error": extraction["error"], "duration": duration})
            else:
                fact_count = len(extraction.get("facts", []))
                doc_type = extraction.get("document_type", "N/A")
                had_error = extraction.get("_had_json_error", False)
                if had_error:
                    json_errors += 1

                identifier_count = sum(1 for f in extraction.get("facts", []) if f.get("type") == "Identifier")
                other_count = sum(1 for f in extraction.get("facts", []) if f.get("type") == "Other")

                id_categories = {}
                for f in extraction.get("facts", []):
                    if f.get("type") == "Identifier":
                        cat = f.get("identifier_category", "UNKNOWN")
                        id_categories[cat] = id_categories.get(cat, 0) + 1

                print(f"    ✅ 成功!")
                print(f"       文档类型: {doc_type}")
                print(f"       提取Facts: {fact_count}")
                print(f"       Identifier: {identifier_count}, Other: {other_count}")
                if id_categories:
                    print(f"       分类: {', '.join(f'{k}:{v}' for k, v in id_categories.items())}")
                if had_error:
                    print(f"       ⚠️ JSON需要修复")
                print(f"       耗时: {duration:.1f}s")

                results.append({
                    "file": filename,
                    "success": True,
                    "document_type": doc_type,
                    "fact_count": fact_count,
                    "identifier_count": identifier_count,
                    "other_count": other_count,
                    "identifier_categories": id_categories,
                    "had_json_error": had_error,
                    "duration": duration,
                    "extraction": extraction
                })
        except Exception as e:
            duration = (datetime.now() - start).total_seconds()
            print(f"    ❌ 异常: {e}")
            results.append({"file": filename, "success": False, "error": str(e), "duration": duration})

    # 汇总
    print("\n" + "=" * 60)
    print("📊 V3.4 测试结果")
    print("=" * 60)

    success = sum(1 for r in results if r.get("success"))
    total = len(results)

    print(f"\n成功率: {success}/{total} ({100*success/total:.0f}%)")
    print(f"JSON错误: {json_errors} (Guided Decoding {'应该为0' if USE_GUIDED_DECODING else '预期有'})")

    for r in results:
        status = "✅" if r.get("success") else "❌"
        name = r["file"].split("_")[-1][:40]
        if r.get("success"):
            err_mark = " ⚠️JSON" if r.get("had_json_error") else ""
            print(f"  {status} {name}: {r.get('document_type')} | {r.get('fact_count')} facts{err_mark}")
        else:
            print(f"  {status} {name}: {r.get('error', '')[:50]}")

    # 保存
    report_path = RESULTS_DIR / f"regression_v34_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(results, indent=2, ensure_ascii=False, default=str))
    print(f"\n💾 报告: {report_path}")

if __name__ == "__main__":
    main()
