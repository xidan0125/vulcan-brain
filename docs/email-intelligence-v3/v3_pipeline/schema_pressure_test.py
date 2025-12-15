#!/usr/bin/env python3
"""
Phase 2.5 Schema压力测试
- 随机抽取10-20个高价值附件 (PDF优先)
- VLM批量提取结构化JSON
- 输出Gap分析报告
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
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor, as_completed

# ============ 配置 ============
VLLM_URL = "http://localhost:8000/v1/chat/completions"
MODEL_NAME = "Qwen/Qwen3-VL-30B-A3B-Thinking-FP8"
CACHE_DIR = Path.home() / "attachment_cache" / "phase25_test"
RESULTS_DIR = Path.home() / "vulcan-brain/docs/email-intelligence-v3/progress"

# MS365 配置 (从环境变量读取)
MS365_TENANT_ID = os.environ.get("MS365_TENANT_ID", "")
MS365_CLIENT_ID = os.environ.get("MS365_CLIENT_ID", "")
MS365_CLIENT_SECRET = os.environ.get("MS365_CLIENT_SECRET", "")

# 提取Prompt - 要求结构化输出
EXTRACTION_PROMPT = """你是一个B2B商业文档分析专家。请仔细分析这份文档，提取所有关键商业信息。

请严格按以下JSON格式返回:

{
  "document_type": "发票|订单|报价单|合同|装箱单|技术规格|其他",
  "document_date": "YYYY-MM-DD 或 null",
  "facts": [
    {
      "type": "金额|数量|日期|产品|规格|价格|地址|联系方式|条款|其他",
      "key": "字段名称",
      "value": "具体值",
      "unit": "单位(如有)",
      "context": "上下文说明"
    }
  ],
  "entities": {
    "companies": ["公司名列表"],
    "products": ["产品名列表"],
    "persons": ["人名列表"]
  },
  "summary": "一句话概述"
}

注意:
1. 只返回JSON，不要其他解释
2. 金额、数量等数值要提取准确
3. 如果是扫描件/图片质量差，尽力识别
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

# ============ 抽样模块 ============
def sample_attachments(db, n: int = 15) -> List[AttachmentSample]:
    """从数据库抽取高价值附件样本"""
    print(f"\n📊 正在抽取 {n} 个高价值附件...")
    
    # 查询有PDF附件的业务邮件
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
        {"$sample": {"size": n * 3}}  # 多取一些以防过滤
    ]
    
    samples = []
    for email in db.emails.aggregate(pipeline):
        if len(samples) >= n:
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
        
        # 选择一个高价值附件
        for att in email.get("attachments", []):
            att_id = att.get("id", "")
            filename = att.get("name", "").lower()
            
            if not att_id:
                continue
            
            # 优先PDF，其次Excel，再次大图片
            is_pdf = filename.endswith('.pdf')
            is_excel = filename.endswith(('.xlsx', '.xls'))
            is_image = filename.endswith(('.png', '.jpg', '.jpeg'))
            size = att.get("size", 0)
            
            if is_pdf or is_excel or (is_image and size > 50000):
                samples.append(AttachmentSample(
                    email_id=str(email["_id"]),
                    attachment_id=att_id,
                    filename=att.get("name", "unknown"),
                    size=size,
                    content_type=att.get("content_type", ""),
                    user_email=user_email,
                    graph_message_id=graph_message_id,
                    email_subject=email.get("subject", "")[:50],
                    email_intent=str(intent)
                ))
                break
    
    # 打印统计
    pdf_count = sum(1 for s in samples if s.filename.lower().endswith('.pdf'))
    excel_count = sum(1 for s in samples if s.filename.lower().endswith(('.xlsx', '.xls')))
    image_count = len(samples) - pdf_count - excel_count
    
    print(f"   ✅ 抽取完成: {len(samples)} 个")
    print(f"      PDF: {pdf_count}, Excel: {excel_count}, 图片: {image_count}")
    
    return samples

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

def call_vlm(image_b64: str, mime_type: str = "image/png") -> Dict:
    """调用VLM提取"""
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
        "max_tokens": 4096,
        "temperature": 0.1
    }
    
    resp = requests.post(VLLM_URL, json=payload, timeout=180)
    resp.raise_for_status()
    
    content = resp.json()["choices"][0]["message"]["content"]
    
    # 解析JSON
    if "</think>" in content:
        content = content.split("</think>")[-1].strip()
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0]
    elif "```" in content:
        content = content.split("```")[1].split("```")[0]
    
    return json.loads(content.strip())

def extract_from_file(file_path: Path) -> Dict:
    """从文件提取信息"""
    suffix = file_path.suffix.lower()
    
    if suffix == ".pdf":
        doc = fitz.open(str(file_path))
        page_count = min(len(doc), 3)  # 最多处理前3页
        doc.close()
        
        all_facts = []
        all_entities = {"companies": [], "products": [], "persons": []}
        doc_type = None
        summary = None
        
        for page_num in range(page_count):
            img_b64 = pdf_page_to_base64(file_path, page_num)
            result = call_vlm(img_b64, "image/png")
            
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
        }
    
    elif suffix in [".png", ".jpg", ".jpeg"]:
        img_b64 = image_to_base64(file_path)
        mime = "image/png" if suffix == ".png" else "image/jpeg"
        return call_vlm(img_b64, mime)
    
    else:
        return {"error": f"不支持的文件类型: {suffix}"}

# ============ 主流程 ============
def run_pressure_test(n_samples: int = 15):
    """运行压力测试"""
    print("=" * 60)
    print("🧪 Phase 2.5 Schema压力测试")
    print("=" * 60)
    print(f"时间: {datetime.now()}")
    print(f"样本数: {n_samples}")
    
    # 连接数据库
    client = pymongo.MongoClient("mongodb://localhost:27017/")
    db = client.vulcan_brain
    
    # 1. 抽样
    samples = sample_attachments(db, n_samples)
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
        print("   ⚠️  将跳过需要下载的附件")
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
                        duration_seconds=(datetime.now() - start_time).total_seconds()
                    ))
                    continue
            else:
                results.append(ExtractionResult(
                    sample=sample, success=False, local_path=None,
                    extraction=None, error="无法下载(Graph API未配置)",
                    duration_seconds=(datetime.now() - start_time).total_seconds()
                ))
                continue
        else:
            print(f"    📁 使用缓存")
        
        # VLM提取
        print(f"    🔍 VLM提取中...")
        try:
            extraction = extract_from_file(local_path)
            duration = (datetime.now() - start_time).total_seconds()
            
            fact_count = len(extraction.get("facts", []))
            doc_type = extraction.get("document_type", "N/A")
            print(f"    ✅ 完成: {doc_type}, {fact_count} facts, {duration:.1f}s")
            
            results.append(ExtractionResult(
                sample=sample, success=True, local_path=str(local_path),
                extraction=extraction, error=None, duration_seconds=duration
            ))
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            print(f"    ❌ 提取失败: {e}")
            results.append(ExtractionResult(
                sample=sample, success=False, local_path=str(local_path),
                extraction=None, error=str(e), duration_seconds=duration
            ))
    
    # 4. 生成报告
    generate_report(results)

def generate_report(results: List[ExtractionResult]):
    """生成Gap分析报告"""
    print("\n" + "=" * 60)
    print("📊 Gap分析报告")
    print("=" * 60)
    
    # 统计
    total = len(results)
    success = sum(1 for r in results if r.success)
    failed = total - success
    
    print(f"\n📈 总体统计:")
    print(f"   总样本: {total}")
    print(f"   成功: {success} ({success/total*100:.1f}%)")
    print(f"   失败: {failed}")
    
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
    for ft, count in sorted(fact_types.items(), key=lambda x: -x[1])[:10]:
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
    
    # 保存详细结果
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = RESULTS_DIR / f"phase25_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    report_data = {
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "total": total,
            "success": success,
            "failed": failed,
            "success_rate": success/total if total > 0 else 0
        },
        "doc_type_distribution": doc_types,
        "fact_type_distribution": fact_types,
        "results": [
            {
                "filename": r.sample.filename,
                "email_subject": r.sample.email_subject,
                "email_intent": r.sample.email_intent,
                "success": r.success,
                "error": r.error,
                "duration_seconds": r.duration_seconds,
                "extraction": r.extraction
            }
            for r in results
        ]
    }
    
    report_path.write_text(json.dumps(report_data, indent=2, ensure_ascii=False))
    print(f"\n💾 详细报告已保存: {report_path}")

if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 15
    run_pressure_test(n)
