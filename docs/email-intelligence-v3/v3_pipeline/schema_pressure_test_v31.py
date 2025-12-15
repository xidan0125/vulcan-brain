#!/usr/bin/env python3
"""
Phase 2.5 Schema压力测试 - V3.1 Hotfix
修复:
  1. JSON不稳定 - json_repair + max_tokens增加
  2. Schema扩展 - Document/Fact Types枚举扩展
  3. Excel盲区 - Excel->Markdown预处理
"""
import os
import sys
import json
import random
import base64
import hashlib
import pymongo
import requests
import fitz  # PyMuPDF
import pandas as pd
import json_repair
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict

# ============ 配置 ============
VLLM_URL = "http://localhost:8000/v1/chat/completions"
MODEL_NAME = "Qwen/Qwen3-VL-30B-A3B-Thinking-FP8"
CACHE_DIR = Path.home() / "attachment_cache" / "phase25_test"
RESULTS_DIR = Path.home() / "vulcan-brain/docs/email-intelligence-v3/progress"

# MS365 配置
MS365_TENANT_ID = os.environ.get("MS365_TENANT_ID", "")
MS365_CLIENT_ID = os.environ.get("MS365_CLIENT_ID", "")
MS365_CLIENT_SECRET = os.environ.get("MS365_CLIENT_SECRET", "")

# ============ V3.1 FIX 2: 扩展Schema分类体系 ============
DOCUMENT_TYPES = [
    "Quotation", "Invoice", "Contract", "PurchaseOrder",  # 商务
    "Resume", "OrgChart", "EmployeeHandbook",              # 人事
    "OfficialNotice", "Regulation", "Certificate",         # 行政/合规
    "TechnicalSpec", "TestReport",                         # 技术
    "PackingList", "ShippingDoc", "CustomsDeclaration",    # 物流
    "Other"
]

FACT_TYPES = [
    # 核心商务
    "Amount", "Date", "Quantity", "Currency", "Price",
    "Company", "Address", "Contact", "Product",
    # 扩展类型
    "Education", "WorkExperience", "Skill", "Certification",  # 简历相关
    "RegulationClause", "Penalty", "Deadline",                 # 通知/合规
    "TechnicalParam", "Standard", "Specification",             # 技术规格
    "ShippingInfo", "TrackingNumber", "Weight",                # 物流
    "Other"
]

# V3.1 Prompt - 使用扩展的分类体系
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
3. document_type和fact.type必须从上面给定的列表中选择
4. Ensure the JSON is valid and strictly closed. 所有引号和括号必须正确闭合。
"""

# ============ 数据结构 ============
@dataclass
class AttachmentSample:
    """附件样本"""
    email_id: str
    attachment_id: str
    filename: str
    size: int
    content_type: str
    user_email: str
    graph_message_id: str
    email_subject: str
    email_intent: str

@dataclass
class ExtractionResult:
    """提取结果"""
    sample: AttachmentSample
    success: bool
    local_path: Optional[str]
    extraction: Optional[Dict]
    error: Optional[str]
    duration_seconds: float
    json_repaired: bool = False  # 是否使用了json_repair

# ============ Graph API 客户端 ============
class GraphAPIClient:
    def __init__(self):
        self.tenant_id = MS365_TENANT_ID
        self.client_id = MS365_CLIENT_ID
        self.client_secret = MS365_CLIENT_SECRET
        self.token = None

        if not all([self.tenant_id, self.client_id, self.client_secret]):
            self._load_from_pm2()

    def _load_from_pm2(self):
        """从PM2环境变量文件读取"""
        config_path = Path.home() / "vulcan-brain" / "ecosystem.config.js"
        if config_path.exists():
            content = config_path.read_text()
            import re
            for line in content.split('\n'):
                if 'MS365_TENANT_ID' in line:
                    m = re.search(r'"([^"]+)"', line.split(':')[-1])
                    if m: self.tenant_id = m.group(1)
                elif 'MS365_CLIENT_ID' in line:
                    m = re.search(r'"([^"]+)"', line.split(':')[-1])
                    if m: self.client_id = m.group(1)
                elif 'MS365_CLIENT_SECRET' in line:
                    m = re.search(r'"([^"]+)"', line.split(':')[-1])
                    if m: self.client_secret = m.group(1)

    def get_token(self) -> str:
        if self.token:
            return self.token
        resp = requests.post(
            f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token",
            data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "scope": "https://graph.microsoft.com/.default",
                "grant_type": "client_credentials"
            }
        )
        data = resp.json()
        if "access_token" not in data:
            raise Exception(f"获取token失败: {data}")
        self.token = data["access_token"]
        return self.token

    def download_attachment(self, user_email: str, message_id: str,
                           attachment_id: str, save_path: Path) -> bool:
        """下载附件"""
        url = f"https://graph.microsoft.com/v1.0/users/{user_email}/messages/{message_id}/attachments/{attachment_id}/$value"
        headers = {"Authorization": f"Bearer {self.get_token()}"}
        try:
            resp = requests.get(url, headers=headers, timeout=120)
            resp.raise_for_status()
            save_path.parent.mkdir(parents=True, exist_ok=True)
            save_path.write_bytes(resp.content)
            return True
        except Exception as e:
            print(f"    ❌ 下载失败: {e}")
            return False

# ============ V3.1 FIX 1: JSON解析容错 ============
def parse_json_with_repair(raw_text: str) -> tuple[Dict, bool]:
    """
    解析JSON，失败则尝试修复
    返回: (parsed_dict, was_repaired)
    """
    # 清理VLM输出
    content = raw_text
    if "</think>" in content:
        content = content.split("</think>")[-1].strip()
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0]
    elif "```" in content:
        parts = content.split("```")
        if len(parts) >= 2:
            content = parts[1]

    content = content.strip()

    # 第一次尝试: 直接解析
    try:
        return json.loads(content), False
    except json.JSONDecodeError as e:
        print(f"    ⚠️  JSON解析失败，尝试修复: {str(e)[:50]}")

        # 第二次尝试: json_repair
        try:
            repaired = json_repair.repair_json(content)
            result = json.loads(repaired)
            print(f"    🔧 JSON修复成功!")
            return result, True
        except Exception as repair_error:
            raise ValueError(f"JSON修复也失败: {repair_error}")

# ============ V3.1 FIX 3: Excel预处理 ============
def excel_to_markdown(file_path: Path, max_rows: int = 100) -> str:
    """
    Excel转Markdown表格
    - 最多取前100行
    - 返回markdown格式的文本
    """
    try:
        # 读取所有sheet
        xlsx = pd.ExcelFile(file_path)
        all_tables = []

        for sheet_name in xlsx.sheet_names[:3]:  # 最多3个sheet
            df = pd.read_excel(xlsx, sheet_name=sheet_name, nrows=max_rows)

            if df.empty:
                continue

            # 清理列名
            df.columns = [str(c).strip() for c in df.columns]

            # 转markdown
            md_table = df.to_markdown(index=False)
            all_tables.append(f"### Sheet: {sheet_name}\n{md_table}")

        if not all_tables:
            return "【Excel文件为空或无法读取】"

        result = "\n\n".join(all_tables)

        # 如果太长，截断并提示
        if len(result) > 8000:
            result = result[:8000] + "\n\n... (内容已截断，共" + str(len(result)) + "字符)"

        return result

    except Exception as e:
        return f"【Excel读取错误: {e}】"

# ============ VLM提取模块 ============
def pdf_page_to_base64(pdf_path: Path, page_num: int = 0, dpi: int = 150) -> str:
    """PDF页面转base64图片"""
    doc = fitz.open(str(pdf_path))
    page = doc[page_num]
    mat = fitz.Matrix(dpi/72, dpi/72)
    pix = page.get_pixmap(matrix=mat)
    img_bytes = pix.tobytes("png")
    doc.close()
    return base64.b64encode(img_bytes).decode()

def image_to_base64(image_path: Path) -> str:
    """图片转base64"""
    return base64.b64encode(image_path.read_bytes()).decode()

def call_vlm_vision(image_b64: str, mime_type: str = "image/png") -> tuple[Dict, bool]:
    """
    调用VLM处理图片
    返回: (extraction_dict, json_was_repaired)
    """
    payload = {
        "model": MODEL_NAME,
        "messages": [{
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime_type};base64,{image_b64}"}
                },
                {"type": "text", "text": EXTRACTION_PROMPT}
            ]
        }],
        "max_tokens": 4096,  # V3.1: 增加token上限
        "temperature": 0.1
    }

    resp = requests.post(VLLM_URL, json=payload, timeout=180)
    resp.raise_for_status()

    raw_content = resp.json()["choices"][0]["message"]["content"]
    return parse_json_with_repair(raw_content)

def call_vlm_text(text_content: str) -> tuple[Dict, bool]:
    """
    调用VLM处理纯文本（用于Excel转换后的markdown）
    返回: (extraction_dict, json_was_repaired)
    """
    prompt = EXTRACTION_PROMPT + f"\n\n【文档内容】:\n{text_content}"

    payload = {
        "model": MODEL_NAME,
        "messages": [{
            "role": "user",
            "content": prompt
        }],
        "max_tokens": 4096,
        "temperature": 0.1
    }

    resp = requests.post(VLLM_URL, json=payload, timeout=180)
    resp.raise_for_status()

    raw_content = resp.json()["choices"][0]["message"]["content"]
    return parse_json_with_repair(raw_content)

def extract_from_file(file_path: Path) -> tuple[Dict, bool]:
    """
    从文件提取信息
    返回: (extraction_dict, json_was_repaired)
    """
    suffix = file_path.suffix.lower()

    # ========== PDF处理 ==========
    if suffix == ".pdf":
        doc = fitz.open(str(file_path))
        page_count = min(len(doc), 3)  # 最多处理前3页
        doc.close()

        all_facts = []
        all_entities = {"companies": [], "products": [], "persons": []}
        doc_type = None
        summary = None
        any_repaired = False

        for page_num in range(page_count):
            img_b64 = pdf_page_to_base64(file_path, page_num)
            result, repaired = call_vlm_vision(img_b64, "image/png")
            any_repaired = any_repaired or repaired

            if not doc_type:
                doc_type = result.get("document_type")
                summary = result.get("summary")

            all_facts.extend(result.get("facts", []))
            for key in all_entities:
                all_entities[key].extend(result.get("entities", {}).get(key, []))

        # 去重
        for key in all_entities:
            all_entities[key] = list(set(all_entities[key]))

        return {
            "document_type": doc_type,
            "facts": all_facts,
            "entities": all_entities,
            "summary": summary,
            "pages_processed": page_count
        }, any_repaired

    # ========== 图片处理 ==========
    elif suffix in [".png", ".jpg", ".jpeg"]:
        img_b64 = image_to_base64(file_path)
        mime = "image/png" if suffix == ".png" else "image/jpeg"
        return call_vlm_vision(img_b64, mime)

    # ========== V3.1 FIX 3: Excel处理 ==========
    elif suffix in [".xlsx", ".xls"]:
        print(f"    📊 Excel预处理: 转换为Markdown...")
        md_content = excel_to_markdown(file_path)

        if md_content.startswith("【"):  # 错误消息
            return {"error": md_content, "facts": []}, False

        print(f"    📝 Markdown长度: {len(md_content)} 字符")
        return call_vlm_text(md_content)

    else:
        return {"error": f"不支持的文件类型: {suffix}", "facts": []}, False

# ============ 抽样模块 (支持指定文件名) ============
def sample_attachments(db, n: int = 15, target_files: List[str] = None) -> List[AttachmentSample]:
    """
    从数据库抽取附件样本
    - 如果指定target_files，则只抽取这些文件
    - 否则随机抽取n个高价值附件
    """
    print(f"\n📊 正在抽取附件样本...")

    if target_files:
        print(f"   🎯 目标模式: 查找 {len(target_files)} 个指定文件")
        # 精确查找指定文件
        pipeline = [
            {"$match": {
                "has_attachments": True,
                "attachments.name": {"$in": target_files}
            }}
        ]
    else:
        print(f"   🎲 随机模式: 抽取 {n} 个样本")
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
    target_set = set(target_files) if target_files else None

    for email in db.emails.aggregate(pipeline):
        if not target_files and len(samples) >= n:
            break

        # 获取用户邮箱
        user_email = email.get("user_id") or ""
        if not user_email:
            tos = email.get("to", [])
            if tos and isinstance(tos[0], dict):
                user_email = tos[0].get("address", "")

        graph_message_id = email.get("email_id") or email.get("graph_id") or ""
        if not graph_message_id or not user_email:
            continue

        # 获取intent
        ai_extracted = email.get("ai_extracted", {})
        intent = "UNKNOWN"
        if isinstance(ai_extracted, dict):
            intent = ai_extracted.get("intent", "UNKNOWN")
            if isinstance(intent, dict):
                intent = intent.get("type", "UNKNOWN")

        # 选择附件
        for att in email.get("attachments", []):
            att_id = att.get("id", "")
            filename = att.get("name", "")

            if not att_id:
                continue

            # 如果指定了目标文件，只匹配目标
            if target_set:
                if filename not in target_set:
                    continue
                target_set.discard(filename)  # 找到了就移除
            else:
                # 随机模式: 优先PDF，其次Excel，再次大图片
                fn_lower = filename.lower()
                is_pdf = fn_lower.endswith('.pdf')
                is_excel = fn_lower.endswith(('.xlsx', '.xls'))
                is_image = fn_lower.endswith(('.png', '.jpg', '.jpeg'))
                size = att.get("size", 0)

                if not (is_pdf or is_excel or (is_image and size > 50000)):
                    continue

            samples.append(AttachmentSample(
                email_id=str(email["_id"]),
                attachment_id=att_id,
                filename=filename,
                size=att.get("size", 0),
                content_type=att.get("content_type", ""),
                user_email=user_email,
                graph_message_id=graph_message_id,
                email_subject=email.get("subject", "")[:50],
                email_intent=str(intent)
            ))

            if not target_files:
                break  # 随机模式每封邮件只取一个附件

    # 打印统计
    pdf_count = sum(1 for s in samples if s.filename.lower().endswith('.pdf'))
    excel_count = sum(1 for s in samples if s.filename.lower().endswith(('.xlsx', '.xls')))
    image_count = len(samples) - pdf_count - excel_count

    print(f"   ✅ 抽取完成: {len(samples)} 个")
    print(f"      PDF: {pdf_count}, Excel: {excel_count}, 图片: {image_count}")

    if target_files and target_set:
        print(f"   ⚠️  未找到: {list(target_set)}")

    return samples

# ============ 主流程 ============
def run_pressure_test(n_samples: int = 15, target_files: List[str] = None):
    """
    运行压力测试
    - n_samples: 随机抽取数量(target_files为空时使用)
    - target_files: 指定要测试的文件名列表
    """
    print("=" * 60)
    print("🧪 Phase 2.5 Schema压力测试 - V3.1 Hotfix")
    print("=" * 60)
    print(f"时间: {datetime.now()}")
    if target_files:
        print(f"模式: 回归测试 ({len(target_files)} 个指定文件)")
    else:
        print(f"模式: 随机采样 ({n_samples} 个)")

    # 连接数据库
    client = pymongo.MongoClient("mongodb://localhost:27017/")
    db = client.vulcan_brain

    # 1. 抽样
    samples = sample_attachments(db, n_samples, target_files)
    if not samples:
        print("❌ 没有找到合适的样本")
        return

    # 2. 初始化下载器
    print("\n⬇️  初始化Graph API...")
    try:
        graph_client = GraphAPIClient()
        graph_client.get_token()
        print("   ✅ 认证成功")
    except Exception as e:
        print(f"   ❌ 认证失败: {e}")
        graph_client = None

    # 3. 处理每个样本
    results: List[ExtractionResult] = []
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    print(f"\n🔄 开始处理 {len(samples)} 个样本...")

    for i, sample in enumerate(samples, 1):
        print(f"\n[{i}/{len(samples)}] {sample.filename}")
        print(f"    邮件: {sample.email_subject}")
        print(f"    意图: {sample.email_intent}")

        start_time = datetime.now()

        # 下载附件
        local_path = CACHE_DIR / f"{sample.attachment_id[:16]}_{sample.filename}"

        if not local_path.exists():
            if graph_client:
                print(f"    📥 下载中...")
                success = graph_client.download_attachment(
                    sample.user_email,
                    sample.graph_message_id,
                    sample.attachment_id,
                    local_path
                )
                if not success:
                    results.append(ExtractionResult(
                        sample=sample, success=False, local_path=None,
                        extraction=None, error="下载失败",
                        duration_seconds=(datetime.now() - start_time).total_seconds(),
                        json_repaired=False
                    ))
                    continue
            else:
                results.append(ExtractionResult(
                    sample=sample, success=False, local_path=None,
                    extraction=None, error="无法下载(Graph API未配置)",
                    duration_seconds=(datetime.now() - start_time).total_seconds(),
                    json_repaired=False
                ))
                continue
        else:
            print(f"    📁 使用缓存")

        # VLM提取
        print(f"    🔍 VLM提取中...")
        try:
            extraction, json_repaired = extract_from_file(local_path)
            duration = (datetime.now() - start_time).total_seconds()

            fact_count = len(extraction.get("facts", []))
            doc_type = extraction.get("document_type", "N/A")
            repair_flag = " (JSON已修复)" if json_repaired else ""
            print(f"    ✅ 完成: {doc_type}, {fact_count} facts, {duration:.1f}s{repair_flag}")

            results.append(ExtractionResult(
                sample=sample, success=True, local_path=str(local_path),
                extraction=extraction, error=None, duration_seconds=duration,
                json_repaired=json_repaired
            ))
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            print(f"    ❌ 提取失败: {e}")
            results.append(ExtractionResult(
                sample=sample, success=False, local_path=str(local_path),
                extraction=None, error=str(e), duration_seconds=duration,
                json_repaired=False
            ))

    # 4. 生成报告
    generate_report(results, is_regression=(target_files is not None))

def generate_report(results: List[ExtractionResult], is_regression: bool = False):
    """生成Gap分析报告"""
    print("\n" + "=" * 60)
    print("📊 Gap分析报告" + (" (回归测试)" if is_regression else ""))
    print("=" * 60)

    # 统计
    total = len(results)
    success = sum(1 for r in results if r.success)
    failed = total - success
    repaired = sum(1 for r in results if r.json_repaired)

    print(f"\n📈 总体统计:")
    print(f"   总样本: {total}")
    print(f"   成功: {success} ({success/total*100:.1f}%)")
    print(f"   失败: {failed}")
    print(f"   JSON修复: {repaired} 个")

    if success > 0:
        avg_duration = sum(r.duration_seconds for r in results if r.success) / success
        print(f"   平均耗时: {avg_duration:.1f}s")

    # 文档类型分布
    doc_types = {}
    for r in results:
        if r.success and r.extraction:
            dt = r.extraction.get("document_type", "未知")
            doc_types[dt] = doc_types.get(dt, 0) + 1

    print(f"\n📄 文档类型分布:")
    for dt, count in sorted(doc_types.items(), key=lambda x: -x[1]):
        print(f"   {dt}: {count}")

    # Fact类型分布
    fact_types = {}
    for r in results:
        if r.success and r.extraction:
            for fact in r.extraction.get("facts", []):
                ft = fact.get("type", "未知")
                fact_types[ft] = fact_types.get(ft, 0) + 1

    print(f"\n🔢 Fact类型分布:")
    for ft, count in sorted(fact_types.items(), key=lambda x: -x[1])[:15]:
        print(f"   {ft}: {count}")

    # 错误分析
    if failed > 0:
        print(f"\n❌ 失败原因:")
        errors = {}
        for r in results:
            if not r.success:
                err = r.error or "未知错误"
                errors[err] = errors.get(err, 0) + 1
        for err, count in errors.items():
            print(f"   {err}: {count}")

    # V3.1: Schema合规性检查
    print(f"\n🔍 Schema合规性:")
    doc_type_compliance = sum(1 for dt in doc_types.keys() if dt in DOCUMENT_TYPES)
    fact_type_compliance = sum(1 for ft in fact_types.keys() if ft in FACT_TYPES)
    print(f"   文档类型合规: {doc_type_compliance}/{len(doc_types)} ({doc_type_compliance/max(len(doc_types),1)*100:.0f}%)")
    print(f"   Fact类型合规: {fact_type_compliance}/{len(fact_types)} ({fact_type_compliance/max(len(fact_types),1)*100:.0f}%)")

    # 列出不合规的类型
    invalid_doc_types = [dt for dt in doc_types.keys() if dt not in DOCUMENT_TYPES]
    invalid_fact_types = [ft for ft in fact_types.keys() if ft not in FACT_TYPES]
    if invalid_doc_types:
        print(f"   ⚠️  非标准文档类型: {invalid_doc_types}")
    if invalid_fact_types:
        print(f"   ⚠️  非标准Fact类型: {invalid_fact_types}")

    # 保存详细结果
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    suffix = "_regression" if is_regression else ""
    report_path = RESULTS_DIR / f"phase25_report_v31{suffix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    report_data = {
        "version": "3.1",
        "timestamp": datetime.now().isoformat(),
        "mode": "regression" if is_regression else "random",
        "summary": {
            "total": total,
            "success": success,
            "failed": failed,
            "success_rate": success/total if total > 0 else 0,
            "json_repaired": repaired
        },
        "doc_type_distribution": doc_types,
        "fact_type_distribution": fact_types,
        "schema_compliance": {
            "valid_doc_types": doc_type_compliance,
            "valid_fact_types": fact_type_compliance,
            "invalid_doc_types": invalid_doc_types,
            "invalid_fact_types": invalid_fact_types
        },
        "results": [
            {
                "filename": r.sample.filename,
                "email_subject": r.sample.email_subject,
                "email_intent": r.sample.email_intent,
                "success": r.success,
                "error": r.error,
                "duration_seconds": r.duration_seconds,
                "json_repaired": r.json_repaired,
                "extraction": r.extraction
            }
            for r in results
        ]
    }

    report_path.write_text(json.dumps(report_data, indent=2, ensure_ascii=False))
    print(f"\n💾 详细报告已保存: {report_path}")

    # 回归测试: 判断是否全部通过
    if is_regression:
        if success == total:
            print("\n" + "🎉" * 20)
            print("✅ 回归测试全部通过! 可以开始100样本压力测试。")
            print("🎉" * 20)
        else:
            print("\n" + "⚠️" * 20)
            print(f"❌ 回归测试未通过: {failed}/{total} 失败")
            print("请检查失败原因后重试。")
            print("⚠️" * 20)

if __name__ == "__main__":
    # 支持两种模式:
    # 1. python script.py 10              -> 随机抽取10个
    # 2. python script.py --regression    -> 回归测试失败的3个样本

    if len(sys.argv) > 1 and sys.argv[1] == "--regression":
        # V3.1回归测试: 失败的2个 + Excel样本
        target_files = [
            "SINIR06094668.pdf",                              # JSON解析失败
            "image001.png",                                    # JSON解析失败
            "28Oct2024 proposal for Battery Room.xlsx"         # Excel盲区
        ]
        run_pressure_test(target_files=target_files)
    else:
        n = int(sys.argv[1]) if len(sys.argv) > 1 else 15
        run_pressure_test(n_samples=n)
