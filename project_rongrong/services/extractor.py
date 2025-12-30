#!/usr/bin/env python3
"""
Extractor v4 - 定义清晰版
核心改进：
- 用概念定义代替示例 (entities=谁, numbers=多少)
- 强调金额必须放 numbers
- Category 定义更清晰
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
BUSINESS_CATEGORIES = {"SALES", "OPERATIONS", "DELIVERY", "GOVERNANCE"}
RECORD_CATEGORIES = {"ADMIN", "FILE"}
ALL_CATEGORIES = BUSINESS_CATEGORIES | RECORD_CATEGORIES

# ========== Prompt 模板 ==========
BUSINESS_PROMPT = """# Role
你是榕融新材料的 AI 业务分析专家。

# 公司背景
榕融新材料：氧化铝连续纤维生产商。
- 产品：耐高温纤维材料，用于航空航天、新能源汽车等场景
- 核心客户：比亚迪、宁德时代、航空航天研究院等
- 业务流：销售 → 供应链/生产 → 交付物流（大量海外客户）

# 邮件数据
主题: {subject}
发件人: {sender}
正文: {body}
附件: {attachments}

# 任务（分两步完成）

## Step 1: 提取基础信息

先提取以下信息，不要急于判断：
- category: 邮件所属业务领域
- tag: 4字业务动作
- summary: 一句话概括邮件内容
- entities: 涉及的对象（人、公司、部门、产品、文件类型等）
- numbers: 涉及的量化属性（金额、数量、日期等）

**entities vs numbers 的边界**：
- entities = 存在的对象（名词）
- numbers = 量化的属性（数字+单位）
- 只提取与核心事件相关的信息，忽略背景噪音

## Step 2: 判断 Style
基于 Step 1 的信息，判断战略重要性：

1. **主体是否战略重要？**
   - 资源配置（预算、投资）→ 重要
   - 重要客户（审厂、大客户）→ 重要
   - 销售进展（样件、订单）→ 重要
   - 日常运营（报销、机票）→ 不重要

2. **事件结果是什么？**
   - 正面结果 → GAIN
   - 负面结果 → RISK
   - 中性进展 → INSIGHT
   - 不重要日常 → LOG

# Category 定义

## 对外业务（跟客户/供应商/物流商打交道）

**SALES** - 销售与客户
- 客户开发、询价、报价
- 样件申请、样品确认
- 订单签订、合同确认
- 客户审厂、客户关系

**OPERATIONS** - 供应链与生产
- 采购、供应商管理
- 生产计划、排产
- 质量检验、来料检测
- 生产异常、工艺调整

**DELIVERY** - 物流与交付
- 发货安排、提货通知
- 订舱、报关、货代协调
- 运输跟踪、签收确认
- 出口文件、贸易单证

## 对内管理

**GOVERNANCE** - 重要内部事务
- 预算规划、资金管理
- 安全管理、合规审计
- 人事决策、组织调整
- 重要会议、战略讨论
- 判断标准：老板需要知道的事

**ADMIN** - 日常行政
- 报销、差旅、机票
- 考勤、社保、日常审批
- 催款账单、银行通知
- 证照办理、行政事务
- 判断标准：正常处理就行，不用汇报老板

## 文件类

**FILE** - 扫描件与文件传输
- 扫描件（主题含 Scan Data）
- 纯文件传输（正文几乎为空）
- 存档备份

# Style 判断框架

```
主体战略重要吗？
├── 不重要 → LOG
└── 重要 → 看结果
    ├── 正面（成功/通过/完成/进展）→ GAIN
    ├── 负面（失败/问题/违规/风险）→ RISK
    └── 中性（准备/讨论/制作中）→ INSIGHT
```

**销售相关进展默认 = GAIN**（老板最关心收入）
- 客户需求确认 → GAIN
- 样件确认/申请通过 → GAIN
- 新客户开发 → GAIN
- 订单/合同 → GAIN

# 输出格式

仅返回一个 JSON（不要输出思考过程）:
```json
{{
  "category": "SALES|OPERATIONS|DELIVERY|GOVERNANCE|ADMIN|FILE",
  "tag": "4字业务动作",
  "style": "GAIN|RISK|INSIGHT|LOG",
  "summary": "一句话总结",
  "highlights": {{
    "entities": [],
    "numbers": []
  }}
}}
```

# 强制规则

1. **Event-Centric**：先识别 Event，再提取相关 Entity 和 Number

2. **FILE 识别**：主题含 "Scan Data" 或正文为空 → 归类 FILE

3. **背景 vs 事件**：只提取与核心事件相关的信息，忽略背景内容

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
提取简要信息：
- category: ADMIN 或 FILE
- tag: 4字业务动作
- summary: 一句话描述
- entities: 涉及的对象（名词）
- numbers: 量化属性（数字+单位）

# 分类
- ADMIN: 行政事务
- FILE: 文件传输（主题含 Scan Data 或正文为空）

# 原则
只提取与核心事件相关的信息，忽略背景内容

# 输出格式
```json
{{
  "category": "ADMIN|FILE",
  "tag": "4字业务动作",
  "summary": "一句话描述",
  "entities": [],
  "numbers": []
}}
```

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
    """Build content parts for VLM, including images and text attachments"""
    parts = []
    img_count = 0
    text_contents = []
    
    for asset in email.get("processed_assets", []):
        asset_type = asset.get("asset_type")
        
        # Handle images
        if asset_type == "image" and img_count < MAX_IMAGES:
            path = os.path.join(PROCESSED_ASSETS_ROOT, asset.get("asset_path", ""))
            img_b64 = load_image_base64(path)
            if img_b64:
                parts.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}
                })
                img_count += 1
        
        # Collect text content from docx etc
        elif asset_type == "text":
            text_content = asset.get("text_content", "")
            if text_content:
                source = asset.get("source_attachment", "document")
                text_contents.append(f"[Attachment: {source}]\n{text_content}")
    
    # If there are text attachments, prepend to prompt
    if text_contents:
        attachment_text = "\n\n".join(text_contents)
        prompt = f"Attachment Content:\n{attachment_text}\n\n---\n\n{prompt}"
    
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

    def reset_extraction(self):
        """清空之前的提取结果，重新开始"""
        logger.info("Resetting extraction results...")
        self.db.rongrong_filter_runs.update_one(
            {"company": self.company, "date": self.date_str},
            {
                "$set": {
                    "extraction_processed_ids": [],
                    "extraction_failed_ids": [],
                    "extraction_results": {cat: [] for cat in ALL_CATEGORIES},
                    "extractor_version": "v4"
                }
            }
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

    async def run(self, fresh_start: bool = True):
        logger.info(f"Extractor v4 - {self.company} {self.date_str}")

        run_doc = self.get_run_doc()
        if not run_doc or "binary_filter_result" not in run_doc:
            logger.error("未找到 filter 结果")
            return

        if fresh_start:
            self.reset_extraction()

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
                        hl = extracted.get("highlights", {})
                        entities = hl.get("entities", [])
                        numbers = hl.get("numbers", [])
                        print(f"-> {cat} | {extracted.get('tag', '?')} | {style}")
                        print(f"   entities: {entities[:3]}")
                        print(f"   numbers: {numbers[:3]}")
                    else:
                        entities = extracted.get("entities", [])
                        numbers = extracted.get("numbers", [])
                        print(f"-> {cat}")
                        print(f"   entities: {entities[:3]}, numbers: {numbers[:3]}")
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

        # Style 统计
        style_counts = {"GAIN": 0, "RISK": 0, "INSIGHT": 0, "LOG": 0}
        for cat, items in results.items():
            if isinstance(items, list):
                for item in items:
                    s = item.get("style")
                    if s in style_counts:
                        style_counts[s] += 1

        print(f"\n{'='*50}")
        print(f"Extractor v4 完成")
        print(f"   处理: {processed}/{keep_total}")
        print(f"   成功: {total}")
        print(f"   失败: {failed}")
        print(f"\n   Category 分布:")
        for cat, items in results.items():
            if isinstance(items, list) and len(items) > 0:
                print(f"   - {cat}: {len(items)}")
        print(f"\n   Style 分布:")
        for s, c in style_counts.items():
            if c > 0:
                print(f"   - {s}: {c}")
        print(f"{'='*50}")


async def main():
    import sys
    company = sys.argv[1] if len(sys.argv) > 1 else "shanghai"
    date_str = sys.argv[2] if len(sys.argv) > 2 else "2025-12-26"

    extractor = StableExtractor(company, date_str)
    await extractor.run(fresh_start=True)


if __name__ == "__main__":
    asyncio.run(main())
