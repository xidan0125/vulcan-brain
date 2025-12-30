"""
Employee AI Profile API V2 - 增量式员工画像生成
每个batch处理一批线程，不断迭代更新画像
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from pymongo import MongoClient
from collections import defaultdict
import requests
import json
from datetime import datetime
import copy

router = APIRouter(prefix="/api/employee-profile", tags=["employee-profile"])

# MongoDB 连接
client = MongoClient("mongodb://localhost:27017")
db = client.vulcan_brain

# vLLM 配置
VLLM_URL = "http://localhost:8000/v1/chat/completions"
VLLM_MODEL = "Qwen/Qwen3-VL-30B-A3B-Thinking-FP8"

# Collections
profiles_collection = db.employee_profiles

# 每批处理的线程数
BATCH_SIZE = 8

class ProfileRequest(BaseModel):
    email: str
    force_refresh: bool = False
    batch_size: int = BATCH_SIZE

class ProfileResponse(BaseModel):
    success: bool
    profile: Optional[Dict] = None
    error: Optional[str] = None
    cached: bool = False
    batch_info: Optional[Dict] = None
    generated_at: Optional[str] = None


def get_employee_threads(email: str) -> List[Dict]:
    """获取员工的所有邮件线程"""
    query = {"from.address": {"$regex": email, "$options": "i"}}
    sent_emails = list(db.emails.find(query, {"conversation_id": 1}))

    if not sent_emails:
        return []

    conv_ids = list(set(e.get("conversation_id") for e in sent_emails if e.get("conversation_id")))
    all_emails = list(db.emails.find({"conversation_id": {"$in": conv_ids}}))

    threads = defaultdict(list)
    for e in all_emails:
        threads[e["conversation_id"]].append(e)

    formatted = []
    for conv_id, msgs in threads.items():
        msgs.sort(key=lambda x: x.get("received_at", ""))

        thread_data = {
            "conversation_id": conv_id,
            "subject": (msgs[0].get("subject") or "")[:100],
            "msg_count": len(msgs),
            "latest_time": str(msgs[-1].get("received_at", ""))[:16] if msgs else "",
            "messages": []
        }

        for m in msgs:
            body = m.get("body_clean") or m.get("body", "") or ""
            body = body[:1500]

            from_addr = m.get("from", {})
            from_str = from_addr.get("address", "") if isinstance(from_addr, dict) else str(from_addr)

            to_list = m.get("to", [])
            to_strs = [t.get("address", "") if isinstance(t, dict) else str(t) for t in to_list[:3]]

            thread_data["messages"].append({
                "time": str(m.get("received_at", ""))[:16],
                "from": from_str,
                "to": to_strs,
                "body": body
            })

        formatted.append(thread_data)

    # 按时间排序
    formatted.sort(key=lambda t: t["latest_time"], reverse=True)
    return formatted


def format_threads_for_llm(threads: List[Dict]) -> str:
    """格式化线程为LLM输入"""
    text = ""
    for i, t in enumerate(threads, 1):
        text += f"\n=== 对话{i}: {t.get('subject', '')[:50]} ===\n"
        for msg in t.get("messages", []):
            time_str = msg.get("time", "")[:10]
            from_str = msg.get("from", "").split("@")[0]
            to_str = ",".join(x.split("@")[0] for x in msg.get("to", [])[:2])
            body = msg.get("body", "")[:1000]
            text += f"[{time_str}] {from_str}->{to_str}: {body}\n"
    return text


def get_initial_schema() -> Dict:
    """初始画像schema"""
    return {
        "meta": {
            "employee_name": "",
            "email": "",
            "batch_count": 0,
            "threads_analyzed": 0,
            "last_updated": ""
        },
        "executive_summary": {
            "one_liner": "",
            "inferred_role": {"title": "", "confidence": 0, "evidence": ""},
            "core_value": "",
            "key_strengths": [],
            "attention_flags": []
        },
        "competency_profile": {
            "domain_expertise": [],
            "soft_skills": {}
        },
        "work_patterns": {
            "communication_habits": {},
            "project_involvement": [],
            "decision_style": {}
        },
        "relationship_network": {
            "internal": {"core_collaborators": [], "cross_department": []},
            "external": {"key_contacts": []},
            "network_position": ""
        },
        "management_insights": {
            "motivation_drivers": {},
            "task_fit": {"ideal_tasks": [], "avoid_tasks": []},
            "risk_indicators": {}
        },
        "discoveries": {
            "findings": [],
            "hypotheses": [],
            "anomalies": [],
            "custom_fields": {}  # 非标准化字段
        }
    }


def analyze_batch_with_llm(email: str, threads: List[Dict], existing_profile: Dict, batch_num: int) -> Dict:
    """分析一批线程，返回增量更新"""

    email_text = format_threads_for_llm(threads)

    # 构建prompt - 让LLM知道现有画像，输出增量更新
    existing_summary = ""
    if existing_profile.get("executive_summary", {}).get("one_liner"):
        existing_summary = f"""
【现有画像摘要】
- 定位: {existing_profile['executive_summary'].get('one_liner', '')}
- 职位: {existing_profile['executive_summary'].get('inferred_role', {}).get('title', '')}
- 已分析线程数: {existing_profile['meta'].get('threads_analyzed', 0)}
"""

    prompt = f"""你是资深HR分析专家。这是对员工 {email} 的第 {batch_num} 批邮件分析。
{existing_summary}
【本批新邮件线程】
{email_text}

【任务】
分析这批新邮件，输出以下JSON格式的增量更新（只输出有新发现的字段）：

```json
{{
  "summary_update": {{
    "one_liner": "如果需要更新一句话定位，填写新版本；否则留空",
    "role_update": {{"title": "", "confidence": 0, "new_evidence": ""}},
    "new_strengths": ["新发现的强项"],
    "new_flags": ["新的注意事项"]
  }},
  "new_expertise": [
    {{"domain": "专业领域", "proficiency": "专家/熟练/了解", "evidence": "证据", "quote": "邮件原文"}}
  ],
  "new_projects": [
    {{"project_name": "", "role": "主导/参与/支持", "contribution": "", "status": ""}}
  ],
  "new_contacts": {{
    "internal": [{{"name": "", "relationship": "", "nature": "", "frequency": ""}}],
    "external": [{{"company": "", "contact": "", "type": "", "depth": "", "context": ""}}]
  }},
  "new_findings": [
    {{"finding": "发现内容", "significance": "重要性", "evidence": "证据"}}
  ],
  "new_hypotheses": [
    {{"claim": "假设", "evidence": "证据", "confidence": 0.7, "verify_how": "如何验证"}}
  ],
  "new_anomalies": [
    {{"anomaly": "异常", "explanation": "可能解释", "action": "建议行动"}}
  ],
  "custom_fields": {{
    "任意键": "任意值 - 放不进上面schema但值得记录的发现"
  }},
  "management_notes": {{
    "motivation_clues": ["观察到的驱动因素"],
    "risk_signals": {{"type": "turnover/performance", "level": "低/中/高", "signal": "信号"}}
  }}
}}
```

重点：
1. 只输出这批邮件中的新发现，不要重复已有内容
2. custom_fields 可以放任何你认为重要但schema放不下的发现
3. 引用具体邮件内容作为证据
4. 所有内容用中文

直接输出JSON，不要其他内容。"""

    try:
        response = requests.post(
            VLLM_URL,
            json={
                "model": VLLM_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.15,
                "max_tokens": 4000
            },
            timeout=180
        )

        result = response.json()
        if "choices" not in result:
            raise Exception(f"vLLM error: {result}")

        content = result["choices"][0]["message"]["content"]

        # 提取JSON
        if "</think>" in content:
            content = content.split("</think>")[-1]
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        start = content.find("{")
        end = content.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(content[start:end])

        raise Exception("Failed to parse JSON")

    except Exception as e:
        raise Exception(f"LLM call failed: {str(e)}")


def merge_updates(existing: Dict, updates: Dict, threads_in_batch: int) -> Dict:
    """将增量更新合并到现有画像"""

    profile = copy.deepcopy(existing)

    # 更新meta
    profile["meta"]["batch_count"] = profile["meta"].get("batch_count", 0) + 1
    profile["meta"]["threads_analyzed"] = profile["meta"].get("threads_analyzed", 0) + threads_in_batch
    profile["meta"]["last_updated"] = datetime.now().isoformat()

    # 更新executive_summary
    summary_update = updates.get("summary_update", {})
    if summary_update.get("one_liner"):
        profile["executive_summary"]["one_liner"] = summary_update["one_liner"]

    role_update = summary_update.get("role_update", {})
    if role_update.get("title"):
        # 更新职位推断
        old_conf = profile["executive_summary"]["inferred_role"].get("confidence", 0)
        new_conf = role_update.get("confidence", 0)
        if new_conf >= old_conf:
            profile["executive_summary"]["inferred_role"] = {
                "title": role_update["title"],
                "confidence": new_conf,
                "evidence": role_update.get("new_evidence", "")
            }

    # 追加新强项（去重）
    existing_strengths = set(profile["executive_summary"].get("key_strengths", []))
    for s in summary_update.get("new_strengths", []):
        if s and s not in existing_strengths:
            profile["executive_summary"].setdefault("key_strengths", []).append(s)

    # 追加注意事项（去重）
    existing_flags = set(profile["executive_summary"].get("attention_flags", []))
    for f in summary_update.get("new_flags", []):
        if f and f not in existing_flags:
            profile["executive_summary"].setdefault("attention_flags", []).append(f)

    # 追加专业领域
    existing_domains = {e.get("domain") for e in profile["competency_profile"].get("domain_expertise", [])}
    for exp in updates.get("new_expertise", []):
        if exp.get("domain") and exp["domain"] not in existing_domains:
            profile["competency_profile"].setdefault("domain_expertise", []).append(exp)

    # 追加项目
    existing_projects = {p.get("project_name") for p in profile["work_patterns"].get("project_involvement", [])}
    for proj in updates.get("new_projects", []):
        if proj.get("project_name") and proj["project_name"] not in existing_projects:
            profile["work_patterns"].setdefault("project_involvement", []).append(proj)

    # 追加联系人
    new_contacts = updates.get("new_contacts", {})

    existing_internal = {c.get("name") for c in profile["relationship_network"]["internal"].get("core_collaborators", [])}
    for c in new_contacts.get("internal", []):
        if c.get("name") and c["name"] not in existing_internal:
            profile["relationship_network"]["internal"].setdefault("core_collaborators", []).append(c)

    existing_external = {(c.get("company"), c.get("contact")) for c in profile["relationship_network"]["external"].get("key_contacts", [])}
    for c in new_contacts.get("external", []):
        if c.get("company") and (c["company"], c.get("contact")) not in existing_external:
            profile["relationship_network"]["external"].setdefault("key_contacts", []).append(c)

    # 追加发现
    for f in updates.get("new_findings", []):
        if f.get("finding"):
            profile["discoveries"].setdefault("findings", []).append(f)

    for h in updates.get("new_hypotheses", []):
        if h.get("claim"):
            profile["discoveries"].setdefault("hypotheses", []).append(h)

    for a in updates.get("new_anomalies", []):
        if a.get("anomaly"):
            profile["discoveries"].setdefault("anomalies", []).append(a)

    # 合并custom_fields
    for k, v in updates.get("custom_fields", {}).items():
        if v:
            profile["discoveries"].setdefault("custom_fields", {})[k] = v

    # 更新管理洞察
    mgmt = updates.get("management_notes", {})
    if mgmt.get("motivation_clues"):
        existing_motives = set(profile["management_insights"].get("motivation_drivers", {}).get("observed_drivers", []))
        for m in mgmt["motivation_clues"]:
            if m and m not in existing_motives:
                profile["management_insights"].setdefault("motivation_drivers", {}).setdefault("observed_drivers", []).append(m)

    risk = mgmt.get("risk_signals", {})
    if risk.get("type") and risk.get("level"):
        risk_key = f"{risk['type']}_risk"
        profile["management_insights"].setdefault("risk_indicators", {})[risk_key] = {
            "level": risk["level"],
            "signals": [risk.get("signal", "")]
        }

    return profile


@router.post("/generate", response_model=ProfileResponse)
async def generate_profile(request: ProfileRequest):
    """增量式生成员工画像 - 每次处理一批线程"""

    email = request.email.lower().strip()
    batch_size = request.batch_size or BATCH_SIZE

    # 获取所有线程
    all_threads = get_employee_threads(email)

    if not all_threads:
        return ProfileResponse(
            success=False,
            error="未找到该员工的邮件数据",
            batch_info={"total_threads": 0}
        )

    # 获取现有画像
    existing = profiles_collection.find_one({"email": email})
    if existing and not request.force_refresh:
        profile = existing.get("profile")
        # 如果已有完整画像，直接返回（兼容旧数据）
        if profile and profile.get("executive_summary", {}).get("one_liner"):
            return ProfileResponse(
                success=True,
                profile=profile,
                cached=True,
                batch_info={
                    "total_threads": len(all_threads),
                    "analyzed_threads": len(existing.get("analyzed_thread_ids", [])),
                    "pending_threads": 0
                }
            )
        analyzed_ids = set(existing.get("analyzed_thread_ids", []))
    else:
        profile = get_initial_schema()
        profile["meta"]["email"] = email
        analyzed_ids = set()

    # 找出未分析的线程
    pending_threads = [t for t in all_threads if t["conversation_id"] not in analyzed_ids]

    if not pending_threads:
        return ProfileResponse(
            success=True,
            profile=profile,
            cached=True,
            batch_info={
                "total_threads": len(all_threads),
                "analyzed_threads": len(analyzed_ids),
                "pending_threads": 0,
                "batch_count": profile["meta"].get("batch_count", 0)
            }
        )

    # 取一批处理
    batch = pending_threads[:batch_size]
    batch_num = profile["meta"].get("batch_count", 0) + 1

    try:
        # 分析这批线程
        updates = analyze_batch_with_llm(email, batch, profile, batch_num)

        # 合并更新
        profile = merge_updates(profile, updates, len(batch))

        # 记录已分析的线程ID
        new_analyzed_ids = list(analyzed_ids) + [t["conversation_id"] for t in batch]

        # 如果是第一批，尝试从邮件推断姓名
        if batch_num == 1 and not profile["meta"].get("employee_name"):
            for t in batch:
                for m in t.get("messages", []):
                    if email.lower() in m.get("from", "").lower():
                        # 尝试从邮件地址推断姓名
                        name_part = email.split("@")[0]
                        profile["meta"]["employee_name"] = name_part.replace(".", " ").title()
                        break

        # 保存到MongoDB
        profiles_collection.update_one(
            {"email": email},
            {"$set": {
                "email": email,
                "profile": profile,
                "analyzed_thread_ids": new_analyzed_ids,
                "updated_at": datetime.now().isoformat()
            }},
            upsert=True
        )

        return ProfileResponse(
            success=True,
            profile=profile,
            cached=False,
            batch_info={
                "total_threads": len(all_threads),
                "analyzed_threads": len(new_analyzed_ids),
                "pending_threads": len(pending_threads) - len(batch),
                "batch_count": profile["meta"]["batch_count"],
                "this_batch": len(batch)
            },
            generated_at=datetime.now().isoformat()
        )

    except Exception as e:
        return ProfileResponse(
            success=False,
            error=str(e),
            profile=profile,
            batch_info={
                "total_threads": len(all_threads),
                "analyzed_threads": len(analyzed_ids),
                "pending_threads": len(pending_threads)
            }
        )


@router.post("/generate-full")
async def generate_full_profile(request: ProfileRequest):
    """完整生成画像 - 循环处理所有batch直到完成"""

    email = request.email.lower().strip()
    batch_size = request.batch_size or BATCH_SIZE

    all_threads = get_employee_threads(email)
    if not all_threads:
        return {"success": False, "error": "未找到邮件数据"}

    # 重置画像
    if request.force_refresh:
        profiles_collection.delete_one({"email": email})

    results = []
    max_batches = 20  # 安全限制

    for i in range(max_batches):
        resp = await generate_profile(ProfileRequest(email=email, batch_size=batch_size))
        results.append({
            "batch": i + 1,
            "success": resp.success,
            "batch_info": resp.batch_info
        })

        if not resp.success:
            break

        if resp.batch_info and resp.batch_info.get("pending_threads", 0) == 0:
            break

    # 获取最终画像
    final = profiles_collection.find_one({"email": email})

    return {
        "success": True,
        "profile": final.get("profile") if final else None,
        "batch_results": results,
        "total_batches": len(results)
    }


@router.get("/cached/{email}")
async def get_cached_profile(email: str):
    """获取缓存的画像"""
    cached = profiles_collection.find_one({"email": email.lower()})

    if cached:
        return {
            "cached": True,
            "profile": cached.get("profile"),
            "batch_info": {
                "batch_count": cached.get("profile", {}).get("meta", {}).get("batch_count", 0),
                "threads_analyzed": cached.get("profile", {}).get("meta", {}).get("threads_analyzed", 0)
            },
            "updated_at": cached.get("updated_at")
        }

    return {"cached": False, "profile": None}


@router.get("/stats/{email}")
async def get_email_stats(email: str):
    """获取员工邮件统计"""
    all_threads = get_employee_threads(email.lower())

    existing = profiles_collection.find_one({"email": email.lower()})
    analyzed_count = len(existing.get("analyzed_thread_ids", [])) if existing else 0

    return {
        "email": email,
        "total_threads": len(all_threads),
        "analyzed_threads": analyzed_count,
        "pending_threads": len(all_threads) - analyzed_count,
        "can_generate": len(all_threads) > 0
    }


@router.delete("/reset/{email}")
async def reset_profile(email: str):
    """重置员工画像"""
    result = profiles_collection.delete_one({"email": email.lower()})
    return {"deleted": result.deleted_count > 0}
