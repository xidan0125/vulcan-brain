#!/usr/bin/env python3
"""
Extractor v3 - 稳定增量版
基于 Gemini 专家建议设计：
- 原子化写入 ($push + $addToSet)
- 断点续传 (keep_ids - processed_ids)
- 主动冷却 (错误时 sleep 30s)
- 实时保存 (每封邮件立即保存)
"""
import asyncio
import json
import re
import os
import base64
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set
import pymongo
import httpx

# ========== 日志配置 ==========
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ========== 配置 ==========
MONGO_URI = "mongodb://localhost:27017"
VLLM_URL = "http://localhost:8000/v1/chat/completions"
VLLM_MODEL = "Qwen/Qwen3-VL-30B-A3B-Thinking-FP8"
PROCESSED_ASSETS_ROOT = "/home/xinyue/vulcan-brain/data/processed_assets"
MAX_IMAGES = 5

# 冷却参数
SLEEP_PER_EMAIL = 3
SLEEP_ON_ERROR = 30

# Qwen3 参数
VLLM_PARAMS = {
    "temperature": 0.6,
    "top_p": 0.95,
    "max_tokens": 30000
}

# 分类定义
BUSINESS_CATEGORIES = {"CUSTOMER", "SUPPLY_CHAIN", "LOGISTICS", "MANAGEMENT"}
RECORD_CATEGORIES = {"ADMIN", "FILE"}
ALL_CATEGORIES = BUSINESS_CATEGORIES | RECORD_CATEGORIES

# ========== Prompt 模板 ==========
BUSINESS_PROMPT = """# Role
你是榕融新材料的 AI 业务分析专家。

# 公司背景
榕融新材料：氧化铝连续纤维生产商。产品用于航空航天、新能源汽车等耐高温场景。
核心客户：比亚迪、宁德时代、航空航天研究院等。

# 邮件数据
主题: {subject}
发件人: {sender}
正文: {body}
附件: {attachments}

# 任务（分两步完成）

## Step 1: 提取基础信息
先提取以下信息，不要急于判断：
- category: 邮件所属业务领域
- tag: 4字业务动作（如"预算提交"、"样件确认"）
- summary: 一句话概括邮件内容
- entities: 涉及的公司名/人名
- numbers: 涉及的金额/数量/日期

## Step 2: 基于提取的信息判断 Style
看着你在 Step 1 提取的信息，思考：
1. **主体是否战略重要？**（看 tag 和 entities）
   - 涉及资源配置（预算、投资）→ 重要
   - 涉及重要客户（审厂、大客户）→ 重要
   - 涉及日常运营（报销、机票、例会）→ 不重要

2. **金额规模如何？**（看 numbers）
   - 几百块的催款 vs 几十万的合同 → 重要性完全不同

3. **事件结果是什么？**
   - 正面结果（通过、确认、完成）→ GAIN
   - 负面结果（失败、问题、违规）→ RISK
   - 中性进展（准备、制作、讨论）→ INSIGHT
   - 不重要的日常 → LOG

# Category 定义

**对外业务：**
- CUSTOMER: 客户相关（询价、报价、样件、订单、审厂）
- SUPPLY_CHAIN: 供应链（采购、生产、质量检验）
- LOGISTICS: 物流（发货、报关、订舱、货运）

**对内管理：**
- MANAGEMENT: 公司内部**重要事务**（预算规划、安全管理、重要会议、人事决策、组织调整）
- ADMIN: 公司内部**日常事务**（报销、机票、催款账单、证照办理、银行通知、日常审批）

**文件类：**
- FILE: 扫描件/文件传输（主题含 Scan Data、扫描件，或正文为空只有附件）

💡 MANAGEMENT vs ADMIN 的判断：问自己"这件事老板需要知道吗？"
- 需要 → MANAGEMENT
- 不需要，正常处理就行 → ADMIN

# Style 判断框架

```
主体战略重要吗？
├── 不重要 → LOG（日常运转，不需要老板关注）
└── 重要 → 看事件结果
    ├── 正面结果（成功/通过/完成）→ GAIN
    ├── 销售进展（样件确认/需求确认/客户下单）→ GAIN（销售机会推进都是好事）
    ├── 负面结果（失败/问题/风险）→ RISK
    └── 中性进展（准备/制作/讨论）→ INSIGHT
```

**什么是"战略重要"的主体？**
- 资源配置：预算、投资计划、大额采购
- 重要客户：审厂、大客户关系、核心供应商
- 组织能力：高管人事、架构调整、制度变革
- 战略方向：年度规划、业务调整

**销售相关进展 = GAIN**（老板最关心收入）
- 客户需求确认
- 样件确认/样品进展
- 新客户开发
- 订单/合同签订

**什么是"不重要"的主体？**
- 日常行政：小额报销、机票、社保、考勤
- 常规运营：部门例会、日常审批、流程确认
- 事务性工作：通知、催办、协调

# 输出格式
仅返回一个 JSON（不要输出思考过程）:
```json
{{
  "category": "CUSTOMER|SUPPLY_CHAIN|LOGISTICS|MANAGEMENT|ADMIN",
  "tag": "4字业务动作",
  "style": "GAIN|RISK|INSIGHT|LOG",
  "summary": "一句话总结",
  "highlights": {{
    "entities": ["客户名/人名/公司名"],
    "numbers": ["金额/数量/日期"]
  }}
}}
```

# 强制规则
如果邮件主题包含 "Scan Data"、"扫描" 等关键词，或者正文几乎为空只有附件，必须分类为 FILE，不要分析附件内容。

仅返回 JSON，无其他内容。
"""

RECORD_PROMPT = """# Role
你是榕融新材料的 AI 文档分析助手。

# 邮件数据
主题: {subject}
发件人: {sender}
正文: {body}
附件: {attachments}

# 任务
这是一封行政/文件类邮件，提取简要信息。

# 输出格式
仅返回一个 JSON:
```json
{{
  "category": "ADMIN|FILE",
  "summary": "一句话描述",
  "entities": ["人名/部门/文件类型/金额"]
}}
```

# 分类定义
- ADMIN: 行政类（差旅、报销、审批通知、考勤）
- FILE: 文件类（扫描件、合同存档、单据传输）

仅返回 JSON，无其他内容。
"""


def extract_first_json(text: str) -> Optional[Dict]:
    """提取第一个完整 JSON（括号计数法）"""
    text = text.replace("```json", "").replace("```", "")
    start = text.find('{')
    if start == -1:
        return None

    depth = 0
    in_string = False
    escape = False

    for i, c in enumerate(text[start:], start):
        if escape:
            escape = False
            continue
        if c == '\\':
            escape = True
            continue
        if c == '"' and not escape:
            in_string = not in_string
            continue
        if in_string:
            continue
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:i+1])
                except json.JSONDecodeError:
                    return None
    return None


def load_image_base64(path: str) -> Optional[str]:
    if not os.path.exists(path):
        return None
    try:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    except:
        return None


def build_content_parts(email: Dict, prompt: str) -> List[Dict]:
    parts = []
    img_count = 0
    for asset in email.get("processed_assets", []):
        if img_count >= MAX_IMAGES:
            break
        if asset.get("asset_type") == "image":
            path = os.path.join(PROCESSED_ASSETS_ROOT, asset.get("asset_path", ""))
            img_b64 = load_image_base64(path)
            if img_b64:
                parts.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}
                })
                img_count += 1
    parts.append({"type": "text", "text": prompt})
    return parts


async def call_vllm(content_parts: List[Dict]) -> str:
    async with httpx.AsyncClient(timeout=180) as client:
        r = await client.post(VLLM_URL, json={
            "model": VLLM_MODEL,
            "messages": [{"role": "user", "content": content_parts}],
            **VLLM_PARAMS
        })
        data = r.json()
        if "choices" not in data:
            raise Exception(f"vLLM error: {data}")
        content = data["choices"][0]["message"]["content"]
        content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL)
        return content.strip()


class StableExtractor:
    def __init__(self, company: str, date_str: str):
        self.company = company
        self.date_str = date_str
        self.mongo = pymongo.MongoClient(MONGO_URI)
        self.db = self.mongo.vulcan_brain

    def get_run_doc(self):
        return self.db.rongrong_filter_runs.find_one({
            "company": self.company,
            "date": self.date_str
        })

    def initialize_storage(self):
        """初始化存储结构"""
        self.db.rongrong_filter_runs.update_one(
            {"company": self.company, "date": self.date_str},
            {"$setOnInsert": {
                "extraction_processed_ids": [],
                "extraction_failed_ids": []
            }},
            upsert=False
        )
        for cat in ALL_CATEGORIES:
            self.db.rongrong_filter_runs.update_one(
                {"company": self.company, "date": self.date_str},
                {"$setOnInsert": {f"extraction_results.{cat}": []}}
            )

    def save_result(self, email_id: str, data: dict):
        """原子化保存结果"""
        category = data.get("category", "FILE").upper()
        if category not in ALL_CATEGORIES:
            category = "FILE"
        data["source_id"] = email_id
        if data.get("style") == "null":
            data["style"] = None

        self.db.rongrong_filter_runs.update_one(
            {"company": self.company, "date": self.date_str},
            {
                "$push": {f"extraction_results.{category}": data},
                "$addToSet": {"extraction_processed_ids": email_id}
            }
        )
        logger.info(f"Saved {email_id[:20]}... -> {category}")

    def mark_failed(self, email_id: str, reason: str):
        """标记失败，同时加入 processed 防止死循环"""
        self.db.rongrong_filter_runs.update_one(
            {"company": self.company, "date": self.date_str},
            {
                "$addToSet": {
                    "extraction_failed_ids": email_id,
                    "extraction_processed_ids": email_id
                }
            }
        )
        logger.error(f"Failed {email_id[:20]}...: {reason[:50]}")

    def get_pending_ids(self) -> List[str]:
        """计算待处理列表"""
        run_doc = self.get_run_doc()
        if not run_doc:
            return []

        keep_ids = set(run_doc.get("binary_filter_result", {}).get("KEEP", []))
        processed_ids = set(run_doc.get("extraction_processed_ids", []))

        pending = list(keep_ids - processed_ids)
        logger.info(f"Progress: {len(processed_ids)}/{len(keep_ids)} done. Pending: {len(pending)}")
        return pending

    async def process_email(self, email: Dict) -> Optional[Dict]:
        """处理单封邮件"""
        subject = email.get("subject", "") or "(无主题)"
        sender = email.get("from", "")
        if isinstance(sender, dict):
            sender = sender.get("name") or sender.get("address", "")
        body = (email.get("body", "") or "")[:2000]
        att_names = [a.get("filename", "") for a in email.get("attachments", [])]
        attachments = ", ".join(att_names[:5]) if att_names else "无"

        prompt = BUSINESS_PROMPT.format(
            subject=subject, sender=sender, body=body, attachments=attachments
        )
        content_parts = build_content_parts(email, prompt)
        result = await call_vllm(content_parts)
        parsed = extract_first_json(result)

        if parsed:
            cat = parsed.get("category", "")
            if cat in RECORD_CATEGORIES:
                prompt = RECORD_PROMPT.format(
                    subject=subject, sender=sender, body=body, attachments=attachments
                )
                content_parts = build_content_parts(email, prompt)
                result = await call_vllm(content_parts)
                parsed = extract_first_json(result)
            return parsed
        return None

    async def run(self):
        logger.info(f"Extractor v3 - {self.company} {self.date_str}")

        run_doc = self.get_run_doc()
        if not run_doc or "binary_filter_result" not in run_doc:
            logger.error("未找到 filter 结果")
            return

        self.initialize_storage()
        pending_ids = self.get_pending_ids()

        if not pending_ids:
            logger.info("所有邮件已处理完成")
            self.print_stats()
            return

        emails = list(self.db.wecom_emails.find({"email_id": {"$in": pending_ids}}))
        logger.info(f"加载 {len(emails)} 封邮件")

        for i, email in enumerate(emails):
            email_id = email.get("email_id", "")
            subj = (email.get("subject") or "")[:35]
            img_count = len([a for a in email.get("processed_assets", []) if a.get("asset_type") == "image"])

            print(f"[{i+1}/{len(emails)}] {subj}... ({img_count}图)", end=" ", flush=True)

            try:
                extracted = await self.process_email(email)
                if extracted:
                    cat = extracted.get("category", "FILE")
                    if cat in BUSINESS_CATEGORIES:
                        style = extracted.get("style") or "-"
                        entities = extracted.get("highlights", {}).get("entities", [])
                        print(f"-> {cat} | {extracted.get('tag', '?')} | {style} | {entities[:2]}")
                    else:
                        entities = extracted.get("entities", [])
                        print(f"-> {cat} | {entities[:3]}")
                    self.save_result(email_id, extracted)
                else:
                    print("-> 解析失败")
                    self.mark_failed(email_id, "JSON parse failed")

                await asyncio.sleep(SLEEP_PER_EMAIL)

            except Exception as e:
                err_msg = str(e)
                print(f"-> 错误: {err_msg[:50]}")
                self.mark_failed(email_id, err_msg)
                logger.warning(f"Cooling down for {SLEEP_ON_ERROR}s...")
                await asyncio.sleep(SLEEP_ON_ERROR)

        self.print_stats()

    def print_stats(self):
        """打印统计信息"""
        run_doc = self.get_run_doc()
        if not run_doc:
            return

        results = run_doc.get("extraction_results", {})
        processed = len(run_doc.get("extraction_processed_ids", []))
        failed = len(run_doc.get("extraction_failed_ids", []))
        keep_total = len(run_doc.get("binary_filter_result", {}).get("KEEP", []))

        total = sum(len(v) for v in results.values() if isinstance(v, list))

        print(f"\n{'='*50}")
        print(f"Extractor v3 完成")
        print(f"   处理: {processed}/{keep_total}")
        print(f"   成功: {total}")
        print(f"   失败: {failed}")
        for cat, items in results.items():
            if isinstance(items, list) and len(items) > 0:
                print(f"   {cat}: {len(items)}")
        print(f"{'='*50}")


async def main():
    import sys
    company = sys.argv[1] if len(sys.argv) > 1 else "shanghai"
    date_str = sys.argv[2] if len(sys.argv) > 2 else "2025-12-26"

    extractor = StableExtractor(company, date_str)
    await extractor.run()


if __name__ == "__main__":
    asyncio.run(main())
