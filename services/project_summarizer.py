"""
项目日报分析服务 - 调用LLM生成Asana风格的工作简报
"""

import os
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

# LLM 调用
import httpx

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:30b-a3b")


# ===== LLM 提示词 =====

PROJECT_ANALYSIS_PROMPT = """你是一位资深的项目管理专家，负责分析项目数据并生成工作简报。

请根据以下项目和任务数据，生成一份结构化的工作简报：

## 项目数据
{projects_json}

## 任务数据
{tasks_json}

## 汇报记录
{reports_json}

请按照以下6个维度进行分析，输出JSON格式：

```json
{
  "milestones": [
    {"title": "里程碑标题", "project": "所属项目", "due_date": "截止日期", "status": "状态", "risk_level": "low/medium/high"}
  ],
  "leftover_issues": [
    {"issue": "问题描述", "project": "所属项目", "owner": "负责人", "blocked_reason": "阻塞原因", "suggested_action": "建议行动"}
  ],
  "resource_allocation": [
    {"person": "人员姓名", "projects": ["项目1", "项目2"], "task_count": 3, "workload": "high/medium/low", "overloaded": true/false}
  ],
  "projects_needing_attention": [
    {"project": "项目名称", "reason": "需要关注的原因", "risk_factors": ["风险1", "风险2"], "priority": "high/medium/low"}
  ],
  "workload_warnings": [
    {"person": "人员姓名", "warning": "预警内容", "task_count": 5, "deadline_pressure": "本周有3个任务到期"}
  ],
  "cross_department_risks": [
    {"risk": "风险描述", "involved_projects": ["项目1"], "involved_people": ["人员1"], "mitigation": "缓解建议"}
  ],
  "summary": "一段简要的总结，概述当前项目整体状态和需要重点关注的事项"
}
```

分析要点：
1. **里程碑**: 识别即将到期(7天内)的重要任务作为里程碑
2. **遗留问题**: 找出blocked状态或at_risk状态的任务
3. **资源分配**: 统计每个人的任务数量，识别是否过载(>3个任务)
4. **重点监控**: 识别有风险的项目(有blocked/at_risk任务的项目)
5. **工作量预警**: 本周有多个任务到期的人员
6. **协作风险**: 跨项目协作的潜在问题

请直接输出JSON，不要有其他内容。确保JSON格式正确可解析。
"""


async def call_ollama(prompt: str) -> str:
    """调用本地Ollama模型"""
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.3,
                    "num_predict": 4000
                }
            }
        )
        if response.status_code == 200:
            return response.json().get("response", "")
        else:
            raise Exception(f"Ollama调用失败: {response.status_code}")


def extract_json_from_response(text: str) -> Dict:
    """从LLM响应中提取JSON"""
    import re
    # 尝试找到JSON块
    json_match = re.search(r'```json\s*([\s\S]*?)\s*```', text)
    if json_match:
        text = json_match.group(1)
    
    # 尝试找到 { 开始的JSON
    start = text.find('{')
    if start == -1:
        return {}
    
    # 找到匹配的 }
    depth = 0
    end = start
    for i, c in enumerate(text[start:], start):
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    
    try:
        return json.loads(text[start:end])
    except json.JSONDecodeError:
        return {}


async def generate_project_summary(date_str: Optional[str] = None) -> Dict:
    """生成项目日报摘要"""
    from services.project_store import get_project_store
    
    store = get_project_store()
    
    # 获取所有数据
    projects = await store.list_projects()
    tasks = await store.list_tasks()
    
    # 获取最近的汇报
    reports = await store.get_reports(limit=50)
    
    # 构建提示词
    prompt = PROJECT_ANALYSIS_PROMPT.format(
        projects_json=json.dumps(projects, ensure_ascii=False, indent=2, default=str),
        tasks_json=json.dumps(tasks, ensure_ascii=False, indent=2, default=str),
        reports_json=json.dumps(reports, ensure_ascii=False, indent=2, default=str)
    )
    
    # 调用LLM
    try:
        response = await call_ollama(prompt)
        analysis = extract_json_from_response(response)
    except Exception as e:
        print(f"LLM分析失败: {e}")
        analysis = generate_fallback_analysis(projects, tasks, reports)
    
    # 添加统计信息
    result = {
        "date": date_str or datetime.now().strftime("%Y-%m-%d"),
        "generated_at": datetime.now().isoformat(),
        "stats": {
            "total_projects": len(projects),
            "total_tasks": len(tasks),
            "completed_tasks": len([t for t in tasks if t.get("status") == "completed"]),
            "blocked_tasks": len([t for t in tasks if t.get("status") == "blocked"]),
            "at_risk_tasks": len([t for t in tasks if t.get("status") == "at_risk"]),
            "in_progress_tasks": len([t for t in tasks if t.get("status") == "in_progress"]),
        },
        "analysis": analysis
    }
    
    return result


def generate_fallback_analysis(projects: List, tasks: List, reports: List) -> Dict:
    """当LLM不可用时生成基础分析"""
    # 按负责人统计任务
    person_tasks = {}
    for t in tasks:
        person = t.get("assignee_name", "未分配")
        if person not in person_tasks:
            person_tasks[person] = []
        person_tasks[person].append(t)
    
    # 里程碑: 7天内到期的任务
    now = datetime.now()
    week_later = now + timedelta(days=7)
    milestones = []
    for t in tasks:
        if t.get("deadline"):
            try:
                deadline = datetime.fromisoformat(t["deadline"].replace("Z", ""))
                if now <= deadline <= week_later and t.get("status") != "completed":
                    milestones.append({
                        "title": t.get("title"),
                        "project": t.get("project_id"),
                        "due_date": t.get("deadline"),
                        "status": t.get("status"),
                        "risk_level": "high" if t.get("status") in ["blocked", "at_risk"] else "medium"
                    })
            except:
                pass
    
    # 遗留问题
    leftover = []
    for t in tasks:
        if t.get("status") in ["blocked", "at_risk"]:
            leftover.append({
                "issue": t.get("title"),
                "project": t.get("project_id"),
                "owner": t.get("assignee_name"),
                "blocked_reason": t.get("blocker_reason", ""),
                "suggested_action": "需要跟进"
            })
    
    # 资源分配
    resource = []
    for person, ts in person_tasks.items():
        resource.append({
            "person": person,
            "projects": list(set(t.get("project_id") for t in ts)),
            "task_count": len(ts),
            "workload": "high" if len(ts) > 3 else ("medium" if len(ts) > 1 else "low"),
            "overloaded": len(ts) > 3
        })
    
    # 需要关注的项目
    attention = []
    project_risks = {}
    for t in tasks:
        if t.get("status") in ["blocked", "at_risk"]:
            pid = t.get("project_id")
            if pid not in project_risks:
                project_risks[pid] = []
            project_risks[pid].append(t.get("status"))
    
    for pid, risks in project_risks.items():
        proj = next((p for p in projects if p.get("id") == pid), {})
        attention.append({
            "project": proj.get("name", pid),
            "reason": f"有{len(risks)}个风险任务",
            "risk_factors": risks,
            "priority": "high" if len(risks) > 1 else "medium"
        })
    
    # 工作量预警
    warnings = []
    for person, ts in person_tasks.items():
        week_tasks = [t for t in ts if t.get("deadline") and t.get("status") != "completed"]
        if len(week_tasks) >= 3:
            warnings.append({
                "person": person,
                "warning": f"本周有{len(week_tasks)}个任务",
                "task_count": len(ts),
                "deadline_pressure": f"本周有{len(week_tasks)}个任务到期"
            })
    
    return {
        "milestones": milestones[:5],
        "leftover_issues": leftover[:5],
        "resource_allocation": resource,
        "projects_needing_attention": attention,
        "workload_warnings": warnings,
        "cross_department_risks": [],
        "summary": f"当前共{len(projects)}个项目，{len(tasks)}个任务。其中{len([t for t in tasks if t.get('status') == 'blocked'])}个阻塞，{len([t for t in tasks if t.get('status') == 'at_risk'])}个有风险。"
    }


# 单例
_service = None

def get_project_summarizer():
    global _service
    if _service is None:
        _service = True  # 占位
    return True


if __name__ == "__main__":
    import asyncio
    result = asyncio.run(generate_project_summary())
    print(json.dumps(result, ensure_ascii=False, indent=2))
