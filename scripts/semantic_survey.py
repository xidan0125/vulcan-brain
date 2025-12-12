#!/usr/bin/env python3
"""
邮件语义普查脚本 - Phase 1: 数据勘测与语义建模
用大模型对邮件进行无监督话题聚类
"""

import os
import json
import random
import asyncio
from datetime import datetime
from typing import List, Dict, Any
from pymongo import MongoClient
import httpx

# ===== 配置 =====
MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017')
OLLAMA_URL = 'http://localhost:11434/api/generate'
MODEL = 'qwen3:30b-a3b'

# 分层抽样配置 - 基于实际数据
SAMPLING_CONFIG = {
    # 大客户
    'spacex.com': 150,
    # IT/系统服务
    'info-tech.com.sg': 100,
    # 物流
    'expeditors.com': 80,
    'dhl.com': 80,
    # 材料供应商
    'syensqo.com': 80,
    'fibrecast.com': 60,
    'rongrongnm.com': 60,
    # 金融/银行
    'dbs.com': 50,
    # 政府
    'ica.gov.sg': 50,
    # 其他重要供应商
    'royalimaging.com.sg': 50,
    'rqam.com.sg': 50,
    'suindustry.com': 50,
    'adinalgroup.com': 50,
}

# 内部邮件单独采样
INTERNAL_SAMPLE = 100

# 排除的系统通知域名
EXCLUDE_DOMAINS = {
    'gmail.com', 'email.teams.microsoft.com', 'trip.com', 
    'myworkday.com', 'asana.com', 'teams.mail.microsoft',
    'kametcapital.com',
}


class SemanticSurvey:
    def __init__(self):
        self.client = MongoClient(MONGO_URI)
        self.db = self.client['vulcan_brain']
        self.emails = self.db['emails']
        self.results_collection = self.db['semantic_survey_results']
        
    def sample_emails(self) -> Dict[str, List[Dict]]:
        """分层抽样邮件"""
        samples = {}
        
        print("\n=== 开始分层抽样 ===")
        
        # 1. 按域名抽样外部邮件
        for domain, count in SAMPLING_CONFIG.items():
            cursor = self.emails.aggregate([
                {'$match': {
                    'from.address': {'$regex': f'@{domain}$', '$options': 'i'},
                    'body_clean': {'$exists': True, '$ne': None, '$ne': ''}
                }},
                {'$sample': {'size': count}},
                {'$project': {
                    '_id': 1,
                    'subject': 1,
                    'body_clean': 1,
                    'from': 1,
                    'to': 1,
                    'received_at': 1
                }}
            ])
            emails = list(cursor)
            samples[domain] = emails
            print(f"  {domain}: 抽取 {len(emails)} 封")
        
        # 2. 内部邮件抽样
        cursor = self.emails.aggregate([
            {'$match': {
                'from.address': {'$regex': '@vulcanshield.com$', '$options': 'i'},
                'to.address': {'$regex': '@vulcanshield.com$', '$options': 'i'},
                'body_clean': {'$exists': True, '$ne': None, '$ne': ''}
            }},
            {'$sample': {'size': INTERNAL_SAMPLE}},
            {'$project': {
                '_id': 1,
                'subject': 1,
                'body_clean': 1,
                'from': 1,
                'to': 1,
                'received_at': 1
            }}
        ])
        samples['internal'] = list(cursor)
        print(f"  internal: 抽取 {len(samples['internal'])} 封")
        
        total = sum(len(v) for v in samples.values())
        print(f"\n总计抽取: {total} 封邮件")
        
        return samples
    
    async def analyze_batch(self, emails: List[Dict], domain: str, batch_num: int) -> Dict:
        """用 LLM 分析一批邮件的话题"""
        
        # 准备邮件摘要 (只取前 800 字符避免太长)
        email_summaries = []
        for i, email in enumerate(emails[:20]):  # 每批最多 20 封
            subject = email.get('subject', '(无主题)')
            body = (email.get('body_clean') or '')[:800]
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

/no_think 直接输出 JSON，不要解释。"""

        try:
            async with httpx.AsyncClient(timeout=120) as client:
                response = await client.post(
                    OLLAMA_URL,
                    json={
                        'model': MODEL,
                        'prompt': prompt,
                        'stream': False,
                        'options': {'temperature': 0.3}
                    }
                )
                result = response.json()
                text = result.get('response', '')
                
                # 尝试解析 JSON
                start = text.find('{')
                end = text.rfind('}') + 1
                if start >= 0 and end > start:
                    json_str = text[start:end]
                    return json.loads(json_str)
                else:
                    return {'error': 'No JSON found', 'raw': text[:500]}
                    
        except Exception as e:
            return {'error': str(e), 'domain': domain, 'batch': batch_num}
    
    async def run_survey(self):
        """执行完整的语义普查"""
        print("\n" + "="*60)
        print("邮件语义普查 - Phase 1: 数据勘测与语义建模")
        print("="*60)
        
        # 1. 分层抽样
        samples = self.sample_emails()
        
        # 2. 逐域名分析
        all_results = []
        
        print("\n=== 开始 AI 分析 ===")
        
        for domain, emails in samples.items():
            if not emails:
                continue
                
            print(f"\n分析 {domain} ({len(emails)} 封)...")
            
            # 分批处理（每批 20 封）
            batch_size = 20
            domain_results = []
            
            for i in range(0, len(emails), batch_size):
                batch = emails[i:i+batch_size]
                batch_num = i // batch_size + 1
                print(f"  批次 {batch_num}: 分析 {len(batch)} 封...")
                
                result = await self.analyze_batch(batch, domain, batch_num)
                result['batch_num'] = batch_num
                result['sample_size'] = len(batch)
                domain_results.append(result)
                
                # 避免请求过快
                await asyncio.sleep(1)
            
            # 合并该域名的所有批次结果
            all_results.append({
                'domain': domain,
                'total_emails': len(emails),
                'batches': domain_results,
                'analyzed_at': datetime.now().isoformat()
            })
        
        # 3. 保存结果
        survey_doc = {
            '_id': f'survey_{datetime.now().strftime("%Y%m%d_%H%M%S")}',
            'created_at': datetime.now(),
            'total_sampled': sum(len(v) for v in samples.values()),
            'domains_analyzed': len(samples),
            'results': all_results
        }
        
        self.results_collection.insert_one(survey_doc)
        
        # 4. 输出汇总
        print("\n" + "="*60)
        print("调查完成！结果已保存到 semantic_survey_results 集合")
        print("="*60)
        
        return survey_doc


async def main():
    survey = SemanticSurvey()
    results = await survey.run_survey()
    
    # 打印关键发现
    print("\n=== 关键发现预览 ===")
    for domain_result in results.get('results', [])[:5]:
        domain = domain_result.get('domain', 'unknown')
        print(f"\n【{domain}】")
        for batch in domain_result.get('batches', [])[:1]:
            if 'categories' in batch:
                for cat in batch['categories'][:3]:
                    print(f"  - {cat.get('name_zh', 'N/A')}: {cat.get('percentage', 0)}%")
            if 'domain_relationship' in batch:
                print(f"  关系: {batch['domain_relationship']}")


if __name__ == '__main__':
    asyncio.run(main())
