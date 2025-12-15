#!/usr/bin/env python3
"""
V3.8 统一提取测试 - 正文+附件一次性提取
"""
import json
import base64
import requests
import fitz  # PyMuPDF
from pathlib import Path
from datetime import datetime

# 配置
VLLM_URL = "http://localhost:8000/v1/chat/completions"
MODEL_NAME = "Qwen/Qwen3-VL-30B-A3B-Thinking-FP8"

# V1.2 Schema for Guided Decoding
VLM_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "email_type": {
            "type": "string",
            "description": "邮件类型: Quotation/Invoice/Contract/Inquiry/Notification/Other"
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
                    "type": {"type": "string", "description": "Amount/Date/Identifier/Company/Product/Contact/Quantity/Other"},
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

【重要】:
- 正文内容标记为 source_type: "body"
- 附件内容标记为 source_type: "attachment"，并注明 source_file（文件名）和 source_page（页码）
- Identifier类型用于各种编号：Invoice No, PO No, Quotation No等
- 金额、数量要提取准确

请提取：
1. 邮件整体类型（报价/发票/合同/询价/通知等）
2. 所有关键事实（价格、日期、数量、编号等）
3. 涉及的公司、产品、人员
"""


def pdf_to_images(pdf_path: Path, max_pages: int = 3, dpi: int = 150) -> list:
    """PDF转图片列表"""
    doc = fitz.open(str(pdf_path))
    images = []

    for page_num in range(min(len(doc), max_pages)):
        page = doc[page_num]
        mat = fitz.Matrix(dpi/72, dpi/72)
        pix = page.get_pixmap(matrix=mat)
        img_bytes = pix.tobytes("png")
        b64 = base64.b64encode(img_bytes).decode()
        images.append({
            "base64": b64,
            "page": page_num + 1
        })

    doc.close()
    return images


def unified_extract(email_body: str, attachments: list) -> dict:
    """
    统一提取：正文+附件一次性送VLM

    attachments: [{"filename": "xxx.pdf", "images": [{"base64": "...", "page": 1}, ...]}]
    """
    # 构建VLM输入
    content = []

    # 1. 正文
    content.append({
        "type": "text",
        "text": f"【邮件正文】\n{email_body}\n\n【附件内容如下】\n"
    })

    # 2. 附件图片
    for att in attachments:
        content.append({
            "type": "text",
            "text": f"\n--- 附件: {att['filename']} ---\n"
        })
        for img in att["images"]:
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{img['base64']}"}
            })

    # 3. 提取指令
    content.append({
        "type": "text",
        "text": EXTRACTION_PROMPT
    })

    # 调用VLM (带Guided Decoding)
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

    print(f"  📤 发送请求... (正文{len(email_body)}字符, {sum(len(a['images']) for a in attachments)}张图片)")

    start = datetime.now()
    resp = requests.post(VLLM_URL, json=payload, timeout=300)
    resp.raise_for_status()
    duration = (datetime.now() - start).total_seconds()

    raw = resp.json()["choices"][0]["message"]["content"]

    # 解析JSON
    try:
        if "</think>" in raw:
            raw = raw.split("</think>")[-1].strip()
        result = json.loads(raw)
        print(f"  ✅ 提取成功! 耗时: {duration:.1f}s")
        return result, False, duration
    except json.JSONDecodeError as e:
        print(f"  ⚠️ JSON解析失败: {e}")
        return {"raw": raw[:500]}, True, duration


def main():
    print("=" * 60)
    print("🧪 V3.8 统一提取测试 - 正文+附件")
    print("=" * 60)

    # 测试数据
    email_body = """Juan,
Per our conversation this quote is still accurate and you can use this for pricing. If we get further along and the volume looks to increase we can look to see what we can do next. If you need material please let me know ASAP and we will get to work on this for you.
-If you see a need for our M-99 we can work on a quote for that too.
Regards
Barry Claypool
Vice President Sales Americas
Vulcan Shield Global Pte. Ltd.
M: +1 248.514.2954 | E: Barry.Claypool@vulcanshield.com | W: www.vulcanshield.com"""

    pdf_path = Path.home() / "vulcan_data/cache/raw/AAMkADhhZDFjMjNh_Americarb_Quote_Q250228AC003.pdf"

    print(f"\n📧 邮件正文: {len(email_body)} 字符")
    print(f"📎 附件: {pdf_path.name}")

    # PDF转图片
    print(f"\n🔄 PDF转图片...")
    images = pdf_to_images(pdf_path)
    print(f"   生成 {len(images)} 页图片")

    # 统一提取
    print(f"\n🔍 开始统一提取...")
    attachments = [{
        "filename": pdf_path.name,
        "images": images
    }]

    result, had_error, duration = unified_extract(email_body, attachments)

    # 显示结果
    print("\n" + "=" * 60)
    print("📊 提取结果")
    print("=" * 60)

    if not had_error:
        print(f"\n邮件类型: {result.get('email_type', 'N/A')}")
        print(f"摘要: {result.get('summary', 'N/A')}")
        print(f"文档日期: {result.get('document_date', 'N/A')}")

        print(f"\n📋 Facts ({len(result.get('facts', []))}个):")
        for i, fact in enumerate(result.get("facts", [])[:15], 1):
            source = fact.get("source_type", "?")
            source_detail = ""
            if source == "attachment":
                source_detail = f" [{fact.get('source_file', '?')} p{fact.get('source_page', '?')}]"
            elif source == "body":
                source_detail = " [正文]"

            unit = f" {fact.get('unit', '')}" if fact.get('unit') else ""
            print(f"  {i}. [{fact.get('type', '?')}] {fact.get('key', '?')}: {fact.get('value', '?')}{unit}{source_detail}")

        if len(result.get("facts", [])) > 15:
            print(f"  ... 还有 {len(result.get('facts', [])) - 15} 个")

        print(f"\n🏢 公司: {result.get('companies', [])}")
        print(f"📦 产品: {result.get('products', [])}")
        print(f"👤 人员: {result.get('persons', [])}")
    else:
        print(f"❌ 提取失败")
        print(f"原始响应: {result.get('raw', 'N/A')[:300]}")

    # 保存完整结果
    output_path = Path("/tmp/unified_extraction_test_result.json")
    output_path.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"\n💾 完整结果已保存: {output_path}")


if __name__ == "__main__":
    main()
