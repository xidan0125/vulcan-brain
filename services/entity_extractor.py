"""
Stage 3: 实体提取 + 优先级评分
- 从邮件正文提取实体 (LLM)
- 合并附件洞察
- 计算优先级评分
"""
import json
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
import requests

# 配置
VLLM_BASE = "http://localhost:8000/v1"
VLLM_MODEL = "Qwen/Qwen3-VL-30B-A3B-Thinking-FP8"


@dataclass
class ExtractedEntities:
    customers: List[str] = field(default_factory=list)
    contacts: List[Dict] = field(default_factory=list)  # {name, phone, email}
    products: List[str] = field(default_factory=list)
    deadlines: List[str] = field(default_factory=list)
    amounts: List[str] = field(default_factory=list)
    actions: List[str] = field(default_factory=list)
    

@dataclass
class EnrichedThread:
    """融合后的富信息 Thread"""
    thread_id: str
    subject: str
    category: str
    participants: List[str]
    message_count: int
    latest_at: datetime
    
    # 正文摘要
    body_summary: str
    
    # 实体
    entities: ExtractedEntities
    
    # 附件洞察
    attachment_insights: List[Dict]
    
    # 优先级
    priority_score: int
    priority_reasons: List[str]


def call_llm(prompt: str, max_tokens: int = 4000) -> str:
    """调用 LLM (文本模式)"""
    try:
        response = requests.post(
            f"{VLLM_BASE}/chat/completions",
            json={
                "model": VLLM_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": 0.1
            },
            timeout=120
        )
        result = response.json()
        text = result["choices"][0]["message"]["content"]
        
        if "</think>" in text:
            text = text.split("</think>")[-1].strip()
        
        return text
    except Exception as e:
        return f"LLM调用失败: {e}"


def extract_entities_from_body(subject: str, body: str, from_name: str) -> ExtractedEntities:
    """从邮件正文提取实体"""
    if not body or len(body) < 20:
        return ExtractedEntities()
    
    prompt = f"""分析这封邮件，提取业务实体。

主题: {subject}
发件人: {from_name}
正文:
{body[:2000]}

请提取以下信息（JSON格式）：
{{
  "customers": ["客户公司名称"],
  "contacts": [{{"name": "姓名", "phone": "电话", "email": "邮箱"}}],
  "products": ["产品名称"],
  "deadlines": ["截止日期 YYYY-MM-DD 或描述"],
  "amounts": ["金额/数量"],
  "actions": ["需要执行的动作"]
}}

只输出JSON，无其他文字。如果某项没有，用空数组[]。"""

    result = call_llm(prompt, max_tokens=4000)
    
    # 尝试解析 JSON
    try:
        # 提取 JSON 部分
        json_match = re.search(r'\{[\s\S]*\}', result)
        if json_match:
            data = json.loads(json_match.group())
            return ExtractedEntities(
                customers=data.get("customers", []),
                contacts=data.get("contacts", []),
                products=data.get("products", []),
                deadlines=data.get("deadlines", []),
                amounts=data.get("amounts", []),
                actions=data.get("actions", [])
            )
    except json.JSONDecodeError:
        pass
    
    return ExtractedEntities()


def merge_attachment_entities(entities: ExtractedEntities, attachment_insights: List[Dict]) -> ExtractedEntities:
    """合并附件中提取的实体"""
    for insight in attachment_insights:
        extracted = insight.get("extracted", "")
        if not extracted or not isinstance(extracted, str):
            continue
        
        # 尝试解析附件的 JSON
        try:
            json_match = re.search(r'\{[\s\S]*\}', extracted)
            if json_match:
                data = json.loads(json_match.group())
                
                # 合并客户
                if "key_data" in data:
                    kd = data["key_data"]
                    if "客户名称" in str(kd):
                        for k, v in kd.items():
                            if "客户" in k and v:
                                entities.customers.append(str(v).split()[0])
                    
                    # 合并联系人
                    if "销售人员" in str(kd) or "联系" in str(kd):
                        for k, v in kd.items():
                            if ("销售" in k or "联系" in k) and v:
                                # 尝试提取姓名和电话
                                match = re.match(r'([\u4e00-\u9fa5]{2,4})\s*(\d{11})?', str(v))
                                if match:
                                    entities.contacts.append({
                                        "name": match.group(1),
                                        "phone": match.group(2) or ""
                                    })
                    
                    # 合并截止日期
                    if "完成日期" in str(kd) or "日期" in str(kd):
                        for k, v in kd.items():
                            if "日期" in k and v:
                                entities.deadlines.append(str(v))
                    
                    # 合并产品
                    if "产品" in str(kd):
                        product_info = kd.get("产品要求", {})
                        if isinstance(product_info, dict):
                            name = product_info.get("产品名称", "")
                            if name:
                                entities.products.append(name)
        except:
            pass
    
    # 去重
    entities.customers = list(set(entities.customers))
    entities.products = list(set(entities.products))
    
    return entities


def calculate_priority(thread, entities: ExtractedEntities, attachment_insights: List[Dict]) -> tuple:
    """计算优先级评分"""
    score = 0
    reasons = []
    
    today = datetime.now().date()
    tomorrow = today + timedelta(days=1)
    
    # 1. 分类权重
    category_scores = {
        "CUSTOMER": 30,
        "LOGISTICS": 25,
        "FINANCE": 20,
        "INTERNAL": 10,
        "OTHER": 5,
        "NOISE": 0
    }
    cat_score = category_scores.get(thread.category, 5)
    score += cat_score
    if cat_score >= 25:
        reasons.append(f"类别:{thread.category}")
    
    # 2. 截止日期
    for deadline in entities.deadlines:
        try:
            # 尝试解析日期
            for fmt in ["%Y-%m-%d", "%Y/%m/%d", "%Y年%m月%d日"]:
                try:
                    d = datetime.strptime(deadline.split()[0], fmt).date()
                    if d <= today:
                        score += 50
                        reasons.append(f"今日截止:{deadline}")
                    elif d <= tomorrow:
                        score += 30
                        reasons.append(f"明日截止:{deadline}")
                    break
                except:
                    continue
        except:
            pass
    
    # 3. 邮件链长度（多轮往来说明重要）
    if thread.message_count >= 3:
        score += 20
        reasons.append(f"多轮往来({thread.message_count}封)")
    
    # 4. 有客户名称
    if entities.customers:
        score += 15
        reasons.append(f"涉及客户:{','.join(entities.customers[:2])}")
    
    # 5. 有附件且提取成功
    valid_attachments = [a for a in attachment_insights if a.get("extracted")]
    if valid_attachments:
        score += 10
        reasons.append(f"有{len(valid_attachments)}个关键附件")
    
    # 6. 需要行动
    if entities.actions:
        score += 10
        reasons.append(f"待办:{entities.actions[0][:20]}")
    
    return score, reasons


def summarize_thread_body(messages) -> str:
    """生成 thread 的正文摘要"""
    # 取最新一封邮件的清理后正文
    if not messages:
        return ""
    
    latest = messages[-1]
    body = latest.body_clean or latest.body
    
    if not body or len(body) < 50:
        return body[:200] if body else ""
    
    # 如果正文太长，用 LLM 摘要
    if len(body) > 500:
        prompt = f"""用一句话概括这封邮件的核心内容（不超过100字）：

{body[:1500]}

只输出摘要，无其他文字。"""
        summary = call_llm(prompt, max_tokens=150)
        return summary[:200]
    
    return body[:200]


def enrich_thread(thread, attachment_insights: List[Dict]) -> EnrichedThread:
    """将 Thread 转换为 EnrichedThread"""
    # 1. 从最新邮件提取实体
    latest_msg = thread.messages[-1] if thread.messages else None
    if latest_msg:
        entities = extract_entities_from_body(
            thread.subject,
            latest_msg.body_clean or latest_msg.body,
            latest_msg.from_name
        )
    else:
        entities = ExtractedEntities()
    
    # 2. 合并附件实体
    entities = merge_attachment_entities(entities, attachment_insights)
    
    # 3. 计算优先级
    priority_score, priority_reasons = calculate_priority(thread, entities, attachment_insights)
    
    # 4. 生成正文摘要
    body_summary = summarize_thread_body(thread.messages)
    
    return EnrichedThread(
        thread_id=thread.thread_id,
        subject=thread.subject,
        category=thread.category,
        participants=thread.participants,
        message_count=thread.message_count,
        latest_at=thread.latest_message_at,
        body_summary=body_summary,
        entities=entities,
        attachment_insights=attachment_insights,
        priority_score=priority_score,
        priority_reasons=priority_reasons
    )


# 测试
if __name__ == "__main__":
    # 测试实体提取
    test_body = """
    Dear Karling，

    附件托书请查收。
    货今天备好，来厂提货请提前通知，谢谢。

    货物信息：
    共11托：8托：1.3*1*1.38m（H），3托：1.3*1.15*1.22m（H），总毛重：1441.5kg
    货物请勿堆叠。

    提货地址：
    广西壮族自治区百色市右江区百东新区百贤路BD11-02-02-01地块榕融新材料技术有限公司
    联系人：滕宏建15296261986
    """
    
    entities = extract_entities_from_body(
        "空运订舱/FCA 广西工厂",
        test_body,
        "仝占凤"
    )
    print("=== 实体提取测试 ===")
    print(f"客户: {entities.customers}")
    print(f"联系人: {entities.contacts}")
    print(f"产品: {entities.products}")
    print(f"截止: {entities.deadlines}")
    print(f"数量: {entities.amounts}")
    print(f"动作: {entities.actions}")
