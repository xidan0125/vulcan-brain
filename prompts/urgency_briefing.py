"""
紧急简报生成 Prompt
将日报JSON喂给LLM，生成按紧急度排序的统一简报
"""

URGENCY_BRIEFING_PROMPT = """你是一位企业情报分析专家。请分析以下日报数据，生成一份按紧急度排序的统一简报。

## 日报数据
```json
{daily_report_json}
```

## 今天日期
{today_date}

## 任务
1. 从以下来源提取所有事项：
   - email.ai_analysis.action_items (待办事项)
   - email.ai_analysis.urgent_matters (紧急事项)
   - email.ai_analysis.vip_updates (VIP客户更新)
   - chat.chats[].analysis.risks (风险项)
   - chat.chats[].analysis.action_items (聊天待办)
   - approval.pending (待处理审批)

2. 合并去重：相同或相似的事项只保留一个

3. 为每个事项评估紧急度 (1-5分)：
   - 5分 极度紧急：今天必须处理、已超时、多次催促
   - 4分 紧急：24h内需处理、VIP客户、关键人员变动
   - 3分 重要：48h内需处理、需要回复确认、外部沟通
   - 2分 一般：本周内处理、内部事务
   - 1分 低优：信息性、无明确截止

4. 按紧急度从高到低排序

## 输出格式 (严格JSON)
```json
{{
  "briefing_date": "YYYY-MM-DD",
  "summary": "一句话概括今天的重点",
  "items": [
    {{
      "urgency": 5,
      "title": "简短标题",
      "detail": "具体内容",
      "source": "email/chat/approval",
      "reason": "为什么这个紧急度",
      "action": "建议的下一步行动",
      "deadline": "截止时间(如有)",
      "related_emails": ["邮件编号如1,2,3"]
    }}
  ],
  "stats": {{
    "total": 10,
    "critical": 2,
    "urgent": 3,
    "important": 5
  }}
}}
```

注意：
- 只输出JSON，不要其他内容
- 合并重复项，不要列出相同的事情多次
- related_emails填写邮件编号(如"1","3","5-7")，前端会用email_index_map查找实际ID
- 使用中文输出
"""


def get_urgency_briefing_prompt(daily_report: dict, today_date: str) -> str:
    """生成紧急简报的prompt"""
    import json
    
    # 只保留需要分析的字段，减少token
    slim_report = {
        "date": daily_report.get("date"),
        "email": {
            "ai_analysis": daily_report.get("email", {}).get("ai_analysis", {}),
            "vip_emails": daily_report.get("email", {}).get("vip_emails", [])[:5],
        },
        "chat": daily_report.get("chat", {}),
        "approval": daily_report.get("approval", {}),
        "projects": daily_report.get("projects", {}),
    }
    
    return URGENCY_BRIEFING_PROMPT.format(
        daily_report_json=json.dumps(slim_report, ensure_ascii=False, indent=2),
        today_date=today_date
    )
