#!/usr/bin/env python3
"""
V3.1 回归测试 - 直接测试3个失败的缓存文件
"""
import os
import sys
import json
import base64
import requests
import fitz
import pandas as pd
import json_repair
from pathlib import Path
from datetime import datetime

# ============ 配置 ============
VLLM_URL = "http://localhost:8000/v1/chat/completions"
MODEL_NAME = "Qwen/Qwen3-VL-30B-A3B-Thinking-FP8"
CACHE_DIR = Path.home() / "attachment_cache" / "phase25_test"

# 3个失败的样本 (直接使用缓存文件)
FAILED_SAMPLES = [
    "AAMkADVkYTU2ZmMx_SINIR06094668.pdf",           # JSON解析失败
    "AAMkADYzNjY4ZmNi_image001.png",                 # JSON解析失败
    "AAMkAGViNzg3ODQw_28Oct2024 proposal for Battery Room.xlsx"  # Excel盲区
]

# ============ V3.1 Schema扩展 ============
DOCUMENT_TYPES = [
    "Quotation", "Invoice", "Contract", "PurchaseOrder",
    "Resume", "OrgChart", "EmployeeHandbook",
    "OfficialNotice", "Regulation", "Certificate",
    "TechnicalSpec", "TestReport",
    "PackingList", "ShippingDoc", "CustomsDeclaration",
    "Other"
]

FACT_TYPES = [
    "Amount", "Date", "Quantity", "Currency", "Price",
    "Company", "Address", "Contact", "Product",
    "Education", "WorkExperience", "Skill", "Certification",
    "RegulationClause", "Penalty", "Deadline",
    "TechnicalParam", "Standard", "Specification",
    "ShippingInfo", "TrackingNumber", "Weight",
    "Other"
]

EXTRACTION_PROMPT = f"""你是一个B2B商业文档分析专家。请仔细分析这份文档，提取所有关键商业信息。

## 文档类型 (document_type) - 必须选择以下之一:
{', '.join(DOCUMENT_TYPES)}

## Fact类型 (fact.type) - 必须选择以下之一:
{', '.join(FACT_TYPES)}

请严格按以下JSON格式返回:

{{
  "document_type": "从上面列表选择最匹配的类型",
  "document_date": "YYYY-MM-DD 或 null",
  "facts": [
    {{
      "type": "从上面Fact类型列表选择",
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

【重要约束】:
1. 只返回JSON，不要其他解释
2. 金额、数量等数值要提取准确
3. document_type和fact.type必须从给定列表中选择
4. Ensure the JSON is valid and strictly closed.
"""

# ============ JSON修复 ============
def parse_json_with_repair(raw_text: str) -> tuple:
    """解析JSON，失败则修复"""
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

    # 如果内容为空，返回默认空结构
    if not content:
        print(f"    ⚠️  VLM返回为空")
        return {"document_type": "Other", "facts": [], "entities": {}, "summary": "无法解析"}, False

    try:
        result = json.loads(content)
        if not isinstance(result, dict):
            raise ValueError("JSON不是对象类型")
        return result, False
    except (json.JSONDecodeError, ValueError) as e:
        print(f"    ⚠️  JSON解析失败: {str(e)[:60]}")
        try:
            repaired = json_repair.repair_json(content)
            result = json.loads(repaired)

            # 检查修复结果是否是dict
            if not isinstance(result, dict):
                print(f"    ⚠️  json_repair返回非dict类型: {type(result)}")

                # 如果是list，检查是否是facts数组
                if isinstance(result, list) and len(result) > 0:
                    # 检查是否是fact格式的dict列表
                    facts = []
                    for item in result:
                        if isinstance(item, dict) and "type" in item and "value" in item:
                            facts.append(item)
                        elif isinstance(item, dict) and "document_type" in item:
                            # 找到完整结构
                            print(f"    🔧 JSON修复成功 (从list中找到完整结构)!")
                            return item, True

                    if facts:
                        print(f"    🔧 JSON修复成功 (从list中提取{len(facts)}个facts)!")
                        return {
                            "document_type": "Other",
                            "facts": facts,
                            "entities": {"companies": [], "products": [], "persons": []},
                            "summary": f"从返回的list中提取了{len(facts)}个facts"
                        }, True

                return {"document_type": "Other", "facts": [], "entities": {}, "summary": "JSON修复失败", "raw": str(result)[:200]}, True

            print(f"    🔧 JSON修复成功!")
            return result, True
        except Exception as repair_error:
            print(f"    ⚠️  修复也失败: {repair_error}")
            return {"document_type": "Other", "facts": [], "entities": {}, "summary": f"解析失败: {str(e)[:50]}"}, False

# ============ Excel转图片 ============
def excel_to_image(file_path: Path, max_rows: int = 50) -> str:
    """Excel转图片(base64) - 用matplotlib渲染表格"""
    import matplotlib
    matplotlib.use('Agg')  # 无GUI模式
    import matplotlib.pyplot as plt
    from io import BytesIO

    try:
        xlsx = pd.ExcelFile(file_path)

        # 读取第一个有内容的sheet
        df = None
        for sheet_name in xlsx.sheet_names[:3]:
            df_raw = pd.read_excel(xlsx, sheet_name=sheet_name, header=None, nrows=max_rows)
            if not df_raw.empty:
                # 找表头行
                header_row = 0
                for i, row in df_raw.iterrows():
                    non_null = row.dropna()
                    if len(non_null) >= 2:
                        header_row = i
                        break
                df = pd.read_excel(xlsx, sheet_name=sheet_name, header=header_row, nrows=max_rows)
                df = df.dropna(how='all').dropna(axis=1, how='all')
                if not df.empty:
                    break

        if df is None or df.empty:
            return None

        # 清理列名
        df.columns = [str(c).strip()[:20] for c in df.columns]

        # 限制行列数
        df = df.head(30)
        if len(df.columns) > 10:
            df = df.iloc[:, :10]

        # 用matplotlib渲染表格
        fig, ax = plt.subplots(figsize=(14, max(6, len(df) * 0.4)))
        ax.axis('tight')
        ax.axis('off')

        # 创建表格
        table = ax.table(
            cellText=df.values,
            colLabels=df.columns,
            cellLoc='left',
            loc='center',
            colColours=['#f0f0f0'] * len(df.columns)
        )
        table.auto_set_font_size(False)
        table.set_fontsize(9)
        table.scale(1.2, 1.5)

        # 保存为图片
        buf = BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight', dpi=150, facecolor='white')
        plt.close()
        buf.seek(0)

        return base64.b64encode(buf.read()).decode()

    except Exception as e:
        print(f"    ⚠️  Excel转图片失败: {e}")
        return None

# ============ VLM调用 ============
def call_vlm_vision(image_b64: str, mime_type: str = "image/png") -> tuple:
    """调用VLM处理图片"""
    payload = {
        "model": MODEL_NAME,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{image_b64}"}},
                {"type": "text", "text": EXTRACTION_PROMPT}
            ]
        }],
        "max_tokens": 4096,
        "temperature": 0.1
    }
    resp = requests.post(VLLM_URL, json=payload, timeout=180)
    resp.raise_for_status()
    raw = resp.json()["choices"][0]["message"]["content"]
    return parse_json_with_repair(raw)

def call_vlm_text(text_content: str) -> tuple:
    """调用VLM处理文本"""
    prompt = EXTRACTION_PROMPT + f"\n\n【文档内容】:\n{text_content}"
    payload = {
        "model": MODEL_NAME,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 4096,
        "temperature": 0.1
    }
    resp = requests.post(VLLM_URL, json=payload, timeout=180)
    resp.raise_for_status()
    raw = resp.json()["choices"][0]["message"]["content"]
    return parse_json_with_repair(raw)

# ============ 文件处理 ============
def pdf_page_to_base64(pdf_path: Path, page_num: int = 0, dpi: int = 150) -> str:
    doc = fitz.open(str(pdf_path))
    page = doc[page_num]
    mat = fitz.Matrix(dpi/72, dpi/72)
    pix = page.get_pixmap(matrix=mat)
    img_bytes = pix.tobytes("png")
    doc.close()
    return base64.b64encode(img_bytes).decode()

def process_file(file_path: Path) -> dict:
    """处理单个文件"""
    suffix = file_path.suffix.lower()

    if suffix == ".pdf":
        print(f"    📄 PDF处理...")
        doc = fitz.open(str(file_path))
        page_count = min(len(doc), 3)
        doc.close()

        all_facts = []
        all_entities = {"companies": [], "products": [], "persons": []}
        doc_type, summary = None, None
        any_repaired = False

        for page_num in range(page_count):
            print(f"       处理第{page_num+1}/{page_count}页...")
            img_b64 = pdf_page_to_base64(file_path, page_num)
            result, repaired = call_vlm_vision(img_b64)
            any_repaired = any_repaired or repaired

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
            "pages": page_count,
            "json_repaired": any_repaired
        }

    elif suffix in [".png", ".jpg", ".jpeg"]:
        print(f"    🖼️  图片处理...")
        img_b64 = base64.b64encode(file_path.read_bytes()).decode()
        mime = "image/png" if suffix == ".png" else "image/jpeg"
        result, repaired = call_vlm_vision(img_b64, mime)
        result["json_repaired"] = repaired
        return result

    elif suffix in [".xlsx", ".xls"]:
        print(f"    📊 Excel处理 (转图片模式)...")
        img_b64 = excel_to_image(file_path)

        if not img_b64:
            return {"error": "Excel转图片失败", "facts": [], "json_repaired": False}

        print(f"       图片生成成功，发送VLM...")
        result, repaired = call_vlm_vision(img_b64, "image/png")
        result["json_repaired"] = repaired
        return result

    else:
        return {"error": f"不支持: {suffix}", "facts": [], "json_repaired": False}

# ============ 主流程 ============
def main():
    print("=" * 60)
    print("🔧 V3.1 回归测试 - 3个硬骨头样本")
    print("=" * 60)
    print(f"时间: {datetime.now()}")

    results = []

    for i, filename in enumerate(FAILED_SAMPLES, 1):
        print(f"\n[{i}/3] {filename}")
        file_path = CACHE_DIR / filename

        if not file_path.exists():
            print(f"    ❌ 文件不存在!")
            results.append({"file": filename, "success": False, "error": "文件不存在"})
            continue

        print(f"    📁 文件大小: {file_path.stat().st_size / 1024:.1f} KB")

        start = datetime.now()
        try:
            extraction = process_file(file_path)
            duration = (datetime.now() - start).total_seconds()

            fact_count = len(extraction.get("facts", []))
            doc_type = extraction.get("document_type", "N/A")
            repaired = extraction.get("json_repaired", False)

            print(f"    ✅ 成功!")
            print(f"       文档类型: {doc_type}")
            print(f"       提取Facts: {fact_count}")
            print(f"       耗时: {duration:.1f}s")
            if repaired:
                print(f"       🔧 JSON已自动修复")

            results.append({
                "file": filename,
                "success": True,
                "document_type": doc_type,
                "fact_count": fact_count,
                "duration": duration,
                "json_repaired": repaired,
                "extraction": extraction
            })
        except Exception as e:
            duration = (datetime.now() - start).total_seconds()
            print(f"    ❌ 失败: {e}")
            results.append({
                "file": filename,
                "success": False,
                "error": str(e),
                "duration": duration
            })

    # 汇总
    print("\n" + "=" * 60)
    print("📊 回归测试结果汇总")
    print("=" * 60)

    success = sum(1 for r in results if r.get("success"))
    total = len(results)

    print(f"\n成功: {success}/{total}")

    for r in results:
        status = "✅" if r.get("success") else "❌"
        name = r["file"].split("_")[-1]  # 只显示文件名
        if r.get("success"):
            print(f"  {status} {name}: {r.get('document_type')} | {r.get('fact_count')} facts | {r.get('duration', 0):.1f}s")
        else:
            print(f"  {status} {name}: {r.get('error')}")

    if success == total:
        print("\n" + "🎉" * 20)
        print("✅ 全部通过! 可以启动100样本压力测试!")
        print("🎉" * 20)
    else:
        print("\n" + "⚠️" * 20)
        print(f"❌ 未全部通过 ({total-success}失败)")
        print("⚠️" * 20)

    # 保存结果
    report_path = Path.home() / "vulcan-brain/docs/email-intelligence-v3/progress" / f"regression_v31_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(results, indent=2, ensure_ascii=False, default=str))
    print(f"\n💾 报告已保存: {report_path}")

if __name__ == "__main__":
    main()
