#!/usr/bin/env python3
"""
Filter v15 Final - 邮件分流 + Pipeline 存储

功能：
1. 按单封邮件分类（v15 prompt）
2. 结果保存到 MongoDB rongrong_filter_runs
3. 输出 email_id 列表供 Agent 使用
"""
import asyncio
import json
import re
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional
from motor.motor_asyncio import AsyncIOMotorClient
import httpx

# ========== 配置 ==========

MONGO_URI = "mongodb://localhost:27017"
DB_NAME = "vulcan_brain"
VLLM_URL = "http://localhost:8003/v1/chat/completions"
VLLM_MODEL = "Qwen/Qwen3-Coder-30B-A3B-Instruct-FP8"

CATEGORIES = ["CUSTOMER", "SUPPLY_CHAIN", "LOGISTICS", "MANAGEMENT", "ADMIN", "FILE", "FILTER"]

# ========== Prompt v15 ==========

FILTER_PROMPT_V15 = """# Role
你是企业邮件分发专家。根据邮件的【业务意图】将其分流到 6 个业务 Agent。

# ⚠️ 核心指令
- **不要** 仅仅进行关键词匹配
- **必须** 理解业务意图，进行泛化推理

---

# 分流分类定义 (6 业务类 + 1 过滤)

## 1. [CUSTOMER] 创收流
- **意图**: 拓展客户、确认需求、推进订单
- **包含**: 询价报价、订单确认、客户需求确认表、样件申请、客户投诉
- **部门会议**: 销售周会、客户拜访复盘会 → 归入此类
- **注意**: 此分类仅涉及销售业务动作，不涉及收付款

## 2. [SUPPLY_CHAIN] 交付流
- **意图**: 确保能造出产品（采购+制造+质量）
- **包含**:
  - 上游采购：询价、采购订单、供应商沟通、催货
  - 内部制造：生产排期、车间管理、EHS安全、设备维护、废料处理
  - 质量控制：审厂/验厂
- **部门会议**: 制造部例会、生产调度会、品质周会 → 归入此类

## 3. [LOGISTICS] 物流流
- **意图**: 运东西、进出口
- **包含**: 订舱、报关、货物追踪、货代沟通
- **部门会议**: 物流复盘会、发货协调会 → 归入此类

## 4. [MANAGEMENT] 决策流
- **意图**: 辅助高层经营决策
- **包含**: 财务报表、部门预算、人力成本分析、核心人事考评
- **🚨 负面约束**: 部门周会/例会归对应业务类别，MANAGEMENT仅收录公司级会议

## 5. [ADMIN] 行政流
- **意图**: 记录公司运营活动（人员流动、费用支出、审批流程）
- **包含**:
  - **差旅全流程**: 出差申请、机票审批、机票待审批、机票出票确认、机票报销凭证
  - **费用凭证**: 发票、报销凭证、电子行程单
  - **付款相关**: 付款提醒、款项待支付、服务商催款（快递/物业/水电等）
  - **采购审批**: 请购单申请/审批
  - **印章证照**: 用章申请、证照使用申请
  - **人事通知**: 值班申请、请假申请、职业健康体检

## 6. [FILE] 文件流
- **意图**: 邮件正文无业务价值，但不是垃圾邮件，需要归档备份
- **本质**: 文档传输载体，价值全在附件，正文只是"请查收"或空白
- **典型**: 扫描件转发、合同文档发送、报表附件、资料共享

## 7. [FILTER] 过滤流
- **仅包含真正噪音**:
  1. IT系统通知：邮件备份成功、邮箱容量警告、第三方客户端关闭
  2. 外部营销：展会邀请、软件推销、行业新闻订阅
  3. 招聘平台：BOSS直聘、前程无忧等推送
  4. 日常考勤：补打卡申请
  5. 离职员工邮箱提醒

---

# 仲裁指南

1. **部门例会归垂直业务**:
   - 制造部例会 → SUPPLY_CHAIN
   - 销售周会 → CUSTOMER
   - 物流复盘会 → LOGISTICS

2. **付款相关进 ADMIN**:
   - 款项待支付、付款提醒、服务商催款 → ADMIN

3. **差旅相关全进 ADMIN**:
   - 机票审批/待审批/出票/报销 → ADMIN

---

# 邮件列表
{email_list}

# 输出格式
仅返回 JSON 数组: `[{{"id": "...", "category": "..."}}]`
"""


# ========== 核心函数 ==========

async def call_vllm(prompt: str) -> str:
    """调用 vLLM Filter 模型"""
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(VLLM_URL, json={
            "model": VLLM_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 8000,
            "temperature": 0.3
        })
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        # 去除 thinking 标签
        content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL)
        return content


async def fetch_emails(
    db,
    company: str,
    date_str: str
) -> List[Dict]:
    """获取指定日期的邮件"""
    date = datetime.strptime(date_str, "%Y-%m-%d")
    start = datetime(date.year, date.month, date.day, tzinfo=timezone.utc) - timedelta(hours=8)
    end = start + timedelta(days=1)

    cursor = db.wecom_emails.find({
        "company": company,
        "received_at": {"$gte": start, "$lt": end},
        "is_filtered": False
    })
    return await cursor.to_list(length=500)


async def classify_emails(emails: List[Dict]) -> Dict[str, List[str]]:
    """
    对邮件列表进行分类

    Returns:
        {category: [email_id, ...]}
    """
    if not emails:
        return {cat: [] for cat in CATEGORIES}

    # 构建 email_id -> subject 映射
    id_to_subject = {e["email_id"]: e.get("subject", "(无主题)") for e in emails}

    # 分批处理
    BATCH_SIZE = 30
    all_results = []

    for i in range(0, len(emails), BATCH_SIZE):
        batch = emails[i:i+BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1

        # 构建邮件列表
        email_list = []
        for e in batch:
            eid = e["email_id"]
            subj = e.get("subject", "(无主题)")[:60]
            email_list.append(f"ID={eid}, 主题={subj}")

        prompt = FILTER_PROMPT_V15.format(email_list="\n".join(email_list))

        try:
            result = await call_vllm(prompt)
            match = re.search(r'\[.*\]', result, re.DOTALL)
            if match:
                classifications = json.loads(match.group())
                all_results.extend(classifications)
                print(f"  批次 {batch_num}: 分类 {len(classifications)} 封")
        except Exception as e:
            print(f"  批次 {batch_num} 失败: {e}")
            # 失败的默认分到 FILTER
            for e in batch:
                all_results.append({"id": e["email_id"], "category": "FILTER"})

    # 整理结果
    result = {cat: [] for cat in CATEGORIES}
    for r in all_results:
        cat = r.get("category", "FILTER")
        eid = r.get("id", "")

        # 匹配 email_id（处理可能的截断）
        matched_id = None
        if eid in id_to_subject:
            matched_id = eid
        else:
            for full_id in id_to_subject:
                if eid in full_id or full_id.startswith(eid):
                    matched_id = full_id
                    break

        if matched_id and cat in result:
            result[cat].append(matched_id)

    return result


async def run_filter(
    company: str,
    date_str: str,
    save_to_db: bool = True
) -> Dict:
    """
    运行 Filter 流程

    Args:
        company: 公司 (shanghai/guangxi)
        date_str: 日期 YYYY-MM-DD
        save_to_db: 是否保存到 MongoDB

    Returns:
        {
            "date": "...",
            "company": "...",
            "total_emails": N,
            "filter_result": {category: [email_id, ...]}
        }
    """
    client = AsyncIOMotorClient(MONGO_URI)
    db = client[DB_NAME]

    print(f"[Filter v15] {company} {date_str}")

    # 1. 获取邮件
    emails = await fetch_emails(db, company, date_str)
    print(f"  邮件数: {len(emails)}")

    if not emails:
        client.close()
        return {
            "date": date_str,
            "company": company,
            "total_emails": 0,
            "filter_result": {cat: [] for cat in CATEGORIES}
        }

    # 2. 分类
    print(f"  调用 Filter 分类...")
    filter_result = await classify_emails(emails)

    # 3. 统计
    print(f"\n=== 分类结果 ===")
    for cat, ids in filter_result.items():
        if ids:
            print(f"  {cat}: {len(ids)} 封")

    # 4. 保存到 MongoDB (使用新的集合名)
    if save_to_db:
        pipeline_doc = {
            "date": date_str,
            "company": company,
            "stage": "filter",
            "total_emails": len(emails),
            "filter_result": filter_result,
            "agent_results": None,
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        }

        await db.rongrong_filter_runs.update_one(
            {"date": date_str, "company": company},
            {"$set": pipeline_doc},
            upsert=True
        )
        print(f"\n已保存到 MongoDB: rongrong_filter_runs")

    client.close()

    return {
        "date": date_str,
        "company": company,
        "total_emails": len(emails),
        "filter_result": filter_result
    }


async def get_emails_by_category(
    company: str,
    date_str: str,
    category: str
) -> List[Dict]:
    """
    获取指定分类的完整邮件数据（供 Agent 使用）

    Returns:
        [邮件对象列表，包含 subject, body, attachments 等]
    """
    client = AsyncIOMotorClient(MONGO_URI)
    db = client[DB_NAME]

    # 从 rongrong_filter_runs 获取 email_ids
    pipeline = await db.rongrong_filter_runs.find_one({
        "date": date_str,
        "company": company
    })

    if not pipeline or "filter_result" not in pipeline:
        client.close()
        return []

    email_ids = pipeline["filter_result"].get(category, [])

    if not email_ids:
        client.close()
        return []

    # 获取完整邮件数据
    cursor = db.wecom_emails.find({
        "email_id": {"$in": email_ids}
    })
    emails = await cursor.to_list(length=500)

    client.close()
    return emails


# ========== CLI ==========

async def main():
    import argparse
    parser = argparse.ArgumentParser(description="Filter v15 - 邮件分流")
    parser.add_argument("--company", default="shanghai", help="公司: shanghai/guangxi")
    parser.add_argument("--date", default=None, help="日期: YYYY-MM-DD，默认今天")
    parser.add_argument("--no-save", action="store_true", help="不保存到数据库")
    args = parser.parse_args()

    date_str = args.date or datetime.now().strftime("%Y-%m-%d")

    result = await run_filter(
        args.company,
        date_str,
        save_to_db=not args.no_save
    )

    # 打印详细结果
    print(f"\n=== 详细分类 ===")
    client = AsyncIOMotorClient(MONGO_URI)
    db = client[DB_NAME]

    for cat, email_ids in result["filter_result"].items():
        if email_ids:
            print(f"\n[{cat}] ({len(email_ids)} 封)")
            # 获取主题
            cursor = db.wecom_emails.find(
                {"email_id": {"$in": email_ids[:5]}},
                {"subject": 1, "has_attachments": 1}
            )
            samples = await cursor.to_list(length=5)
            for s in samples:
                att = " 📎" if s.get("has_attachments") else ""
                print(f"  - {s.get('subject', '(无主题)')[:50]}{att}")
            if len(email_ids) > 5:
                print(f"  ... 还有 {len(email_ids)-5} 封")

    client.close()


if __name__ == "__main__":
    asyncio.run(main())
