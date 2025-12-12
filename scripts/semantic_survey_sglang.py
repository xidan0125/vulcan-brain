#!/usr/bin/env python3
"""
邮件语义普查脚本 - SGLang 版本 (Qwen2.5-Coder-32B)
与 Ollama 版本做对比
"""

import os
import json
import asyncio
from datetime import datetime
from typing import List, Dict, Any
from pymongo import MongoClient
import httpx

# ===== 配置 =====
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
SGLANG_URL = "http://localhost:30000/v1/chat/completions"
MODEL = "Qwen/Qwen2.5-Coder-32B-Instruct-AWQ"

# 分层抽样配置 - 与 Ollama 版本一致
SAMPLING_CONFIG = {
    "spacex.com": 150,
    "info-tech.com.sg": 100,
    "expeditors.com": 80,
    "dhl.com": 80,
    "syensqo.com": 80,
    "fibrecast.com": 60,
    "rongrongnm.com": 60,
    "dbs.com": 50,
    "ica.gov.sg": 50,
    "royalimaging.com.sg": 50,
    "rqam.com.sg": 50,
    "suindustry.com": 50,
    "adinalgroup.com": 50,
}

INTERNAL_SAMPLE = 100


class SemanticSurveySGLang:
    def __init__(self):
        self.client = MongoClient(MONGO_URI)
        self.db = self.client["vulcan_brain"]
        self.emails = self.db["emails"]
        self.results_collection = self.db["semantic_survey_results"]
        
    def sample_emails(self) -> Dict[str, List[Dict]]:
        """分层抽样邮件 - 使用固定种子保证与 Ollama 版本一致"""
        samples = {}
        
        print("\n=== 开始分层抽样 (SGLang) ===", flush=True)
        
        for domain, count in SAMPLING_CONFIG.items():
            cursor = self.emails.aggregate([
                {"$match": {
                    "from.address": {"$regex": f"@{domain}$", "$options": "i"},
                    "body_clean": {"$exists": True, "$ne": None, "$ne": ""}
                }},
                {"$sample": {"size": count}},
                {"$project": {
                    "_id": 1,
                    "subject": 1,
                    "body_clean": 1,
                    "from": 1,
                    "to": 1,
                    "received_at": 1
                }}
            ])
            emails = list(cursor)
            samples[domain] = emails
            print(f"  {domain}: 抽取 {len(emails)} 封", flush=True)
        
        # 内部邮件
        cursor = self.emails.aggregate([
            {"$match": {
                "from.address": {"$regex": "@vulcanshield.com$", "$options": "i"},
                "to.address": {"$regex": "@vulcanshield.com$", "$options": "i"},
                "body_clean": {"$exists": True, "$ne": None, "$ne": ""}
            }},
            {"$sample": {"size": INTERNAL_SAMPLE}},
            {"$project": {
                "_id": 1,
                "subject": 1,
                "body_clean": 1,
                "from": 1,
                "to": 1,
                "received_at": 1
            }}
        ])
        samples["internal"] = list(cursor)
        print(f"  internal: 抽取 {len(samples['internal'])} 封", flush=True)
        
        total = sum(len(v) for v in samples.values())
        print(f"\n总计抽取: {total} 封邮件", flush=True)
        
        return samples
    
    async def analyze_batch(self, emails: List[Dict], domain: str, batch_num: int) -> Dict:
        """用 SGLang (Qwen2.5-Coder-32B) 分析一批邮件"""
        
        email_summaries = []
        for i, email in enumerate(emails[:20]):
            subject = email.get("subject", "(无主题)")
            body = (email.get("body_clean") or "")[:800]
            email_summaries.append(f"邮件{i+1}:\n主题: {subject}\n正文: {body}\n---")
        
        emails_text = "\n".join(email_summaries)
        
        prompt = f"""你是一位专业的商业分析师。我给你 {len(email_summaries)} 封来自 {domain} 的商业邮件。

请分析这些邮件的核心交互意图，并将其归类。

要求：
1. 不要总结每封邮件的内容
2. 识别 3-6 个主要的交互类别
3. 每个类别给出：
   - 类别名称（中英文）
   - 占比估算
   - 典型关键词（3-5个）
   - 业务含义（一句话）

邮件内容：
{emails_text}

请用 JSON 格式输出：
{{
  "domain": "{domain}",
  "total_analyzed": {len(email_summaries)},
  "categories": [
    {{
      "name_zh": "类别名",
      "name_en": "Category Name", 
      "percentage": 40,
      "keywords": ["关键词1", "关键词2"],
      "business_meaning": "业务含义"
    }}
  ],
  "domain_relationship": "这个域名与公司的关系是什么（客户/供应商/合作伙伴/政府/服务商）",
  "overall_tone": "整体沟通风格（正式/友好/紧急/例行）"
}}

直接输出 JSON，不要解释。"""

        try:
            async with httpx.AsyncClient(timeout=120) as client:
                response = await client.post(
                    SGLANG_URL,
                    json={
                        "model": MODEL,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.3,
                        "max_tokens": 2000
                    }
                )
                result = response.json()
                text = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                
                # 解析 JSON
                start = text.find("{")
                end = text.rfind("}") + 1
                if start >= 0 and end > start:
                    json_str = text[start:end]
                    return json.loads(json_str)
                else:
                    return {"error": "No JSON found", "raw": text[:500]}
                    
        except Exception as e:
            return {"error": str(e), "domain": domain, "batch": batch_num}
    
    async def run_survey(self):
        """执行完整的语义普查"""
        print("\n" + "="*60, flush=True)
        print("邮件语义普查 - SGLang (Qwen2.5-Coder-32B)", flush=True)
        print("="*60, flush=True)
        
        samples = self.sample_emails()
        all_results = []
        
        print("\n=== 开始 AI 分析 (SGLang) ===", flush=True)
        
        for domain, emails in samples.items():
            if not emails:
                continue
                
            print(f"\n分析 {domain} ({len(emails)} 封)...", flush=True)
            
            batch_size = 20
            domain_results = []
            
            for i in range(0, len(emails), batch_size):
                batch = emails[i:i+batch_size]
                batch_num = i // batch_size + 1
                print(f"  批次 {batch_num}: 分析 {len(batch)} 封...", flush=True)
                
                result = await self.analyze_batch(batch, domain, batch_num)
                result["batch_num"] = batch_num
                result["sample_size"] = len(batch)
                domain_results.append(result)
                
                await asyncio.sleep(0.5)  # SGLang 更快，间隔可以短一点
            
            all_results.append({
                "domain": domain,
                "total_emails": len(emails),
                "batches": domain_results,
                "analyzed_at": datetime.now().isoformat()
            })
        
        # 保存结果
        survey_doc = {
            "_id": f"survey_sglang_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "created_at": datetime.now(),
            "model": "Qwen2.5-Coder-32B-Instruct-AWQ (SGLang)",
            "total_sampled": sum(len(v) for v in samples.values()),
            "domains_analyzed": len(samples),
            "results": all_results
        }
        
        self.results_collection.insert_one(survey_doc)
        
        print("\n" + "="*60, flush=True)
        print("调查完成！结果已保存到 semantic_survey_results 集合", flush=True)
        print(f"文档 ID: {survey_doc[_id]}", flush=True)
        print("="*60, flush=True)
        
        return survey_doc


async def main():
    survey = SemanticSurveySGLang()
    results = await survey.run_survey()
    
    print("\n=== 关键发现预览 (SGLang) ===", flush=True)
    for domain_result in results.get("results", [])[:5]:
        domain = domain_result.get("domain", "unknown")
        print(f"\n【{domain}】", flush=True)
        for batch in domain_result.get("batches", [])[:1]:
            if "categories" in batch:
                for cat in batch["categories"][:3]:
                    print(f"  - {cat.get(name_zh, N/A)}: {cat.get(percentage, 0)}%", flush=True)
            if "domain_relationship" in batch:
                print(f"  关系: {batch[domain_relationship]}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
