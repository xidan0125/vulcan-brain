#!/usr/bin/env python3
"""
V3.3 Schema压力测试 - Excel视觉化流水线
核心改进:
  1. Excel -> PDF -> 分页Image (利用LibreOffice原生排版)
  2. Schema增加Identifier类型
  3. 严格JSON校验 (list直接抛异常触发重试)
  4. Prompt末尾加"紧箍咒"防格式崩坏
"""
import os
import sys
import json
import base64
import subprocess
import tempfile
import requests
import fitz  # PyMuPDF
import json_repair
import pymongo
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from pdf2image import convert_from_path

# ============ 配置 ============
VLLM_URL = "http://localhost:8000/v1/chat/completions"
MODEL_NAME = "Qwen/Qwen3-VL-30B-A3B-Thinking-FP8"
CACHE_DIR = Path.home() / "attachment_cache" / "phase25_test"
RESULTS_DIR = Path.home() / "vulcan-brain/docs/email-intelligence-v3/progress"

# 测试模式
# --regression: 只测3个硬骨头
# --sample N: 随机抽N个附件测试
FAILED_SAMPLES = [
    "AAMkADVkYTU2ZmMx_SINIR06094668.pdf",
    "AAMkADYzNjY4ZmNi_image001.png",
    "AAMkAGViNzg3ODQw_28Oct2024 proposal for Battery Room.xlsx"
]

# ============ V3.3 Schema - 增加Identifier类型 ============
DOCUMENT_TYPES = [
    "Quotation", "Invoice", "Contract", "PurchaseOrder",
    "Resume", "OrgChart", "EmployeeHandbook",
    "OfficialNotice", "Regulation", "Certificate",
    "TechnicalSpec", "TestReport",
    "PackingList", "ShippingDoc", "CustomsDeclaration",
    "Other"
]

FACT_TYPES = [
    # 核心商务
    "Amount", "Date", "Quantity", "Currency", "Price",
    "Company", "Address", "Contact", "Product",
    # V3.3新增: Identifier - 用于各种编号
    "Identifier",  # Invoice No, Tracking No, PO No, Account No, etc.
    # 扩展类型
    "Education", "WorkExperience", "Skill", "Certification",
    "RegulationClause", "Penalty", "Deadline",
    "TechnicalParam", "Standard", "Specification",
    "ShippingInfo", "TrackingNumber", "Weight",
    "Other"
]

# V3.3 Prompt - 明确Identifier用途
EXTRACTION_PROMPT = f"""你是一个B2B商业文档分析专家。请仔细分析这份文档，提取所有关键商业信息。

## 文档类型 (document_type):
{', '.join(DOCUMENT_TYPES)}

## Fact类型 (fact.type):
{', '.join(FACT_TYPES)}

【特别说明】:
- **Identifier**: 用于所有编号类字段，如发票号(Invoice No)、运单号(Tracking No)、订单号(PO No)、账号(Account No)等。不要把编号归为Other。

请严格按以下JSON格式返回:

{{
  "document_type": "从上面列表选择",
  "document_date": "YYYY-MM-DD 或 null",
  "facts": [
    {{
      "type": "从Fact类型列表选择",
      "key": "字段名称",
      "value": "具体值",
      "unit": "单位(如有)",
      "context": "上下文说明"
    }}
  ],
  "entities": {{
    "companies": ["公司名列表"],
    "products": ["产品名列表"],
    "persons": ["人名列表"]
  }},
  "summary": "一句话概述"
}}
"""

# V3.3: 末尾紧箍咒
JSON_REMINDER = """

【重要】必须输出有效的JSON对象(Dict)，包含document_type, facts, entities, summary字段。
不要输出List。不要输出Markdown代码块。直接输出JSON。"""

# ============ V3.3 严格JSON校验 ============
def parse_json_strict(raw_text: str, max_retries: int = 2) -> Tuple[Dict, bool]:
    """
    严格解析JSON
    - list直接抛异常
    - 缺少必要字段抛异常
    返回: (parsed_dict, was_repaired)
    """
    content = raw_text

    # 清理VLM输出
    if "</think>" in content:
        content = content.split("</think>")[-1].strip()
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0]
    elif "```" in content:
        parts = content.split("```")
        if len(parts) >= 2:
            content = parts[1]
    content = content.strip()

    if not content:
        raise ValueError("VLM返回为空")

    # 尝试解析
    try:
        result = json.loads(content)
    except json.JSONDecodeError as e:
        print(f"    ⚠️  JSON解析失败: {str(e)[:50]}, 尝试修复...")
        try:
            repaired = json_repair.repair_json(content)
            result = json.loads(repaired)
        except Exception as repair_err:
            raise ValueError(f"JSON修复失败: {repair_err}")

    # V3.3严格校验
    if isinstance(result, list):
        raise ValueError(f"模型返回List而非Dict! 内容: {str(result)[:100]}")

    if not isinstance(result, dict):
        raise ValueError(f"模型返回非Dict类型: {type(result)}")

    if "facts" not in result:
        # 尝试构造
        if "type" in result and "value" in result:
            # 单个fact被当作顶层返回
            result = {
                "document_type": "Other",
                "facts": [result],
                "entities": {},
                "summary": "单fact提取"
            }
        else:
            raise ValueError(f"JSON缺少facts字段: {list(result.keys())}")

    return result, True

# ============ V3.3 Excel视觉化流水线 ============
def excel_to_images(excel_path: Path, dpi: int = 300) -> List[str]:
    """
    Excel -> PDF -> 分页Image (base64列表)
    使用LibreOffice headless模式保留原生排版
    """
    print(f"    📊 Excel视觉化流水线启动...")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Step 1: Excel -> PDF (LibreOffice headless)
        print(f"       Step1: Excel -> PDF (LibreOffice)...")
        pdf_path = tmpdir / f"{excel_path.stem}.pdf"

        cmd = [
            "libreoffice",
            "--headless",
            "--convert-to", "pdf",
            "--outdir", str(tmpdir),
            str(excel_path)
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if result.returncode != 0:
                raise RuntimeError(f"LibreOffice转换失败: {result.stderr}")
        except subprocess.TimeoutExpired:
            raise RuntimeError("LibreOffice转换超时")

        if not pdf_path.exists():
            # LibreOffice可能生成不同名称
            pdfs = list(tmpdir.glob("*.pdf"))
            if pdfs:
                pdf_path = pdfs[0]
            else:
                raise RuntimeError(f"PDF文件未生成, 目录内容: {list(tmpdir.iterdir())}")

        print(f"       ✅ PDF生成: {pdf_path.stat().st_size / 1024:.1f} KB")

        # Step 2: PDF -> Images (pdf2image)
        print(f"       Step2: PDF -> Images (DPI={dpi})...")
        images = convert_from_path(str(pdf_path), dpi=dpi)
        print(f"       ✅ 生成 {len(images)} 页图片")

        # Step 3: Images -> Base64
        base64_images = []
        for i, img in enumerate(images[:5]):  # 最多5页
            from io import BytesIO
            buf = BytesIO()
            img.save(buf, format='JPEG', quality=90)
            buf.seek(0)
            b64 = base64.b64encode(buf.read()).decode()
            base64_images.append(b64)
            print(f"       📄 Page {i+1}: {len(b64) // 1024} KB")

        return base64_images

# ============ VLM调用 ============
def call_vlm_multi_image(images_b64: List[str], file_type: str = "Excel") -> Dict:
    """
    多图输入VLM (用于Excel分页)
    """
    # 构造多图content
    content = [
        {"type": "text", "text": f"【Source: {file_type} Spreadsheet (Converted to {len(images_b64)} page images)】\n"}
    ]

    for i, img_b64 in enumerate(images_b64):
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}
        })

    # V3.3: 末尾加紧箍咒
    content.append({"type": "text", "text": EXTRACTION_PROMPT + JSON_REMINDER})

    payload = {
        "model": MODEL_NAME,
        "messages": [{"role": "user", "content": content}],
        "max_tokens": 4096,
        "temperature": 0  # V3.3: 降到0减少随机性
    }

    resp = requests.post(VLLM_URL, json=payload, timeout=300)
    resp.raise_for_status()

    raw = resp.json()["choices"][0]["message"]["content"]
    return parse_json_strict(raw)

def call_vlm_single_image(image_b64: str, mime_type: str = "image/png") -> Dict:
    """单图输入VLM"""
    content = [
        {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{image_b64}"}},
        {"type": "text", "text": EXTRACTION_PROMPT + JSON_REMINDER}
    ]

    payload = {
        "model": MODEL_NAME,
        "messages": [{"role": "user", "content": content}],
        "max_tokens": 4096,
        "temperature": 0
    }

    resp = requests.post(VLLM_URL, json=payload, timeout=180)
    resp.raise_for_status()

    raw = resp.json()["choices"][0]["message"]["content"]
    return parse_json_strict(raw)

# ============ 文件处理 ============
def pdf_page_to_base64(pdf_path: Path, page_num: int = 0, dpi: int = 150) -> str:
    doc = fitz.open(str(pdf_path))
    page = doc[page_num]
    mat = fitz.Matrix(dpi/72, dpi/72)
    pix = page.get_pixmap(matrix=mat)
    img_bytes = pix.tobytes("png")
    doc.close()
    return base64.b64encode(img_bytes).decode()

def process_file(file_path: Path, max_retries: int = 2) -> Dict:
    """处理单个文件，支持重试"""
    suffix = file_path.suffix.lower()
    last_error = None

    for attempt in range(max_retries):
        try:
            if attempt > 0:
                print(f"    🔄 重试 #{attempt + 1}...")

            if suffix == ".pdf":
                return process_pdf(file_path)
            elif suffix in [".png", ".jpg", ".jpeg"]:
                return process_image(file_path)
            elif suffix in [".xlsx", ".xls"]:
                return process_excel(file_path)
            else:
                return {"error": f"不支持: {suffix}", "facts": []}

        except ValueError as e:
            last_error = str(e)
            print(f"    ⚠️  尝试{attempt + 1}失败: {last_error}")
            continue

    return {"error": f"重试{max_retries}次后仍失败: {last_error}", "facts": []}

def process_pdf(file_path: Path) -> Dict:
    print(f"    📄 PDF处理...")
    doc = fitz.open(str(file_path))
    page_count = min(len(doc), 3)
    doc.close()

    all_facts = []
    all_entities = {"companies": [], "products": [], "persons": []}
    doc_type, summary = None, None

    for page_num in range(page_count):
        print(f"       处理第{page_num+1}/{page_count}页...")
        img_b64 = pdf_page_to_base64(file_path, page_num)
        result, _ = call_vlm_single_image(img_b64)

        if not doc_type:
            doc_type = result.get("document_type")
            summary = result.get("summary")
        all_facts.extend(result.get("facts", []))
        for key in all_entities:
            all_entities[key].extend(result.get("entities", {}).get(key, []))

    for key in all_entities:
        all_entities[key] = list(set(all_entities[key]))

    return {
        "document_type": doc_type,
        "facts": all_facts,
        "entities": all_entities,
        "summary": summary,
        "pages": page_count
    }

def process_image(file_path: Path) -> Dict:
    print(f"    🖼️  图片处理...")
    img_b64 = base64.b64encode(file_path.read_bytes()).decode()
    suffix = file_path.suffix.lower()
    mime = "image/png" if suffix == ".png" else "image/jpeg"
    result, _ = call_vlm_single_image(img_b64, mime)
    return result

def process_excel(file_path: Path) -> Dict:
    """V3.3: Excel视觉化流水线"""
    images_b64 = excel_to_images(file_path, dpi=300)

    if not images_b64:
        return {"error": "Excel转图片失败", "facts": []}

    print(f"    🔍 VLM处理 {len(images_b64)} 页Excel图片...")
    result, _ = call_vlm_multi_image(images_b64, "Excel")
    return result

# ============ 数据库抽样 ============
def sample_from_db(n: int = 10) -> List[Dict]:
    """从数据库随机抽取n个高价值附件"""
    print(f"\n📊 从数据库抽取 {n} 个高价值附件...")

    client = pymongo.MongoClient("mongodb://localhost:27017/")
    db = client.vulcan_brain

    pipeline = [
        {"$match": {
            "processing_status.v2_extracted": True,
            "has_attachments": True,
            "attachments": {
                "$elemMatch": {
                    "id": {"$exists": True, "$ne": ""},
                    "name": {"$regex": r"\.(pdf|xlsx?|png|jpg)$", "$options": "i"}
                }
            }
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

    print(f"   ✅ 抽取完成: {len(samples)} 个")
    print(f"      PDF: {pdf_count}, Excel: {excel_count}, 图片: {image_count}")

    return samples

def download_attachment(sample: Dict) -> Optional[Path]:
    """下载附件到缓存"""
    # 检查缓存
    cache_file = CACHE_DIR / f"{sample['attachment_id'][:16]}_{sample['filename']}"
    if cache_file.exists():
        return cache_file

    # 需要下载 - 使用Graph API
    from pathlib import Path
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

    # 获取token
    resp = requests.post(
        f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token",
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": "https://graph.microsoft.com/.default",
            "grant_type": "client_credentials"
        }
    )
    token = resp.json().get("access_token")
    if not token:
        return None

    # 下载
    url = f"https://graph.microsoft.com/v1.0/users/{sample['user_email']}/messages/{sample['graph_message_id']}/attachments/{sample['attachment_id']}/$value"
    headers = {"Authorization": f"Bearer {token}"}

    try:
        resp = requests.get(url, headers=headers, timeout=120)
        resp.raise_for_status()
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_bytes(resp.content)
        return cache_file
    except:
        return None

# ============ 主流程 ============
def main():
    # 解析命令行参数
    mode = "regression"
    sample_count = 10

    if len(sys.argv) > 1:
        if sys.argv[1] == "--regression":
            mode = "regression"
        elif sys.argv[1] == "--sample" and len(sys.argv) > 2:
            mode = "sample"
            sample_count = int(sys.argv[2])
        else:
            try:
                sample_count = int(sys.argv[1])
                mode = "sample"
            except:
                pass

    print("=" * 60)
    print("🧪 V3.3 压力测试 - Excel视觉化流水线")
    print("=" * 60)
    print(f"时间: {datetime.now()}")
    print(f"模式: {mode} ({'回归测试' if mode == 'regression' else f'随机{sample_count}样本'})")
    print(f"改进: Excel->PDF->分页Image, Identifier类型, 严格校验")

    results = []

    if mode == "regression":
        # 回归测试模式 - 使用固定的3个硬骨头
        test_files = [(CACHE_DIR / f, f) for f in FAILED_SAMPLES]
    else:
        # 随机采样模式
        samples = sample_from_db(sample_count)
        test_files = []

        print("\n⬇️  下载附件...")
        for sample in samples:
            file_path = download_attachment(sample)
            if file_path:
                test_files.append((file_path, sample["filename"]))
            else:
                print(f"   ⚠️  下载失败: {sample['filename']}")

        print(f"   ✅ 成功下载: {len(test_files)}/{len(samples)}")

    total = len(test_files)

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
                results.append({
                    "file": filename,
                    "success": False,
                    "error": extraction["error"],
                    "duration": duration
                })
            else:
                fact_count = len(extraction.get("facts", []))
                doc_type = extraction.get("document_type", "N/A")

                # V3.3: 统计Identifier使用情况
                identifier_count = sum(1 for f in extraction.get("facts", [])
                                       if f.get("type") == "Identifier")
                other_count = sum(1 for f in extraction.get("facts", [])
                                  if f.get("type") == "Other")

                print(f"    ✅ 成功!")
                print(f"       文档类型: {doc_type}")
                print(f"       提取Facts: {fact_count}")
                print(f"       Identifier: {identifier_count}, Other: {other_count}")
                print(f"       耗时: {duration:.1f}s")

                results.append({
                    "file": filename,
                    "success": True,
                    "document_type": doc_type,
                    "fact_count": fact_count,
                    "identifier_count": identifier_count,
                    "other_count": other_count,
                    "duration": duration,
                    "extraction": extraction
                })
        except Exception as e:
            duration = (datetime.now() - start).total_seconds()
            print(f"    ❌ 异常: {e}")
            results.append({
                "file": filename,
                "success": False,
                "error": str(e),
                "duration": duration
            })

    # 汇总
    print("\n" + "=" * 60)
    print("📊 V3.3 回归测试结果")
    print("=" * 60)

    success = sum(1 for r in results if r.get("success"))
    total = len(results)

    print(f"\n成功: {success}/{total}")

    # V3.3验收标准检查
    print("\n🎯 验收标准检查:")

    excel_result = next((r for r in results if "xlsx" in r["file"]), None)
    pdf_result = next((r for r in results if r["file"].endswith(".pdf")), None)

    # 标准1: Excel fact_count > 10
    if excel_result and excel_result.get("success"):
        fc = excel_result.get("fact_count", 0)
        status = "✅ PASS" if fc > 10 else "❌ FAIL"
        print(f"  Excel fact_count > 10: {status} (实际: {fc})")
    else:
        print(f"  Excel fact_count > 10: ❌ FAIL (提取失败)")

    # 标准2: PDF Identifier类型使用
    if pdf_result and pdf_result.get("success"):
        ic = pdf_result.get("identifier_count", 0)
        oc = pdf_result.get("other_count", 0)
        status = "✅ PASS" if ic > 0 else "⚠️ WARN"
        print(f"  PDF使用Identifier类型: {status} (Identifier: {ic}, Other: {oc})")
    else:
        print(f"  PDF使用Identifier类型: ❌ FAIL (提取失败)")

    # 标准3: 所有JSON都是Dict
    all_dict = all(r.get("success", False) or "List" not in r.get("error", "")
                   for r in results)
    print(f"  JSON结构为Dict: {'✅ PASS' if all_dict else '❌ FAIL'}")

    for r in results:
        status = "✅" if r.get("success") else "❌"
        name = r["file"].split("_")[-1]
        if r.get("success"):
            print(f"\n  {status} {name}")
            print(f"     类型: {r.get('document_type')} | Facts: {r.get('fact_count')}")
            print(f"     Identifier: {r.get('identifier_count')} | Other: {r.get('other_count')}")
        else:
            print(f"\n  {status} {name}: {r.get('error', 'Unknown error')[:60]}")

    # 保存结果
    report_path = RESULTS_DIR / f"regression_v33_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(results, indent=2, ensure_ascii=False, default=str))
    print(f"\n💾 报告已保存: {report_path}")

if __name__ == "__main__":
    main()
