"""
图谱智能服务 - Graph Intelligence Service
基于知识图谱的智能查询、摘要和洞察功能
使用 SGLang + Qwen2.5-Coder-32B (OpenAI 兼容 API)
V2: 改进 prompt，不使用模板占位符
"""
import json
import os
import httpx
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

# 配置 - 使用 SGLang OpenAI 兼容 API
GRAPH_FILE = "/home/xinyue/vulcan-brain/static/email-intel/graph_with_relations_vllm.json"
SGLANG_HOST = os.getenv("SGLANG_HOST", "http://localhost:30000")
MODEL = "Qwen/Qwen2.5-Coder-32B-Instruct-AWQ"

# 单例缓存
_graph_data = None
_graph_load_time = None

def get_graph_data() -> dict:
    """获取图谱数据（带缓存）"""
    global _graph_data, _graph_load_time

    # 10分钟缓存
    if _graph_data and _graph_load_time and (datetime.now() - _graph_load_time).seconds < 600:
        return _graph_data

    with open(GRAPH_FILE, "r") as f:
        _graph_data = json.load(f)
    _graph_load_time = datetime.now()
    return _graph_data


def build_entity_index() -> Dict[str, List[dict]]:
    """构建实体索引"""
    data = get_graph_data()
    index = {}

    for rel in data.get("relationships", []):
        e1 = rel["entity1"].lower()
        e2 = rel["entity2"].lower()

        if e1 not in index:
            index[e1] = []
        index[e1].append(rel)

        if e2 not in index:
            index[e2] = []
        index[e2].append(rel)

    return index


async def call_sglang(prompt: str, max_tokens: int = 1000, temperature: float = 0.3) -> str:
    """
    调用 SGLang OpenAI 兼容 API
    """
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                f"{SGLANG_HOST}/v1/chat/completions",
                json={
                    "model": MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": max_tokens,
                    "temperature": temperature
                },
                timeout=120.0
            )
            result = resp.json()

            # OpenAI 格式响应
            content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
            return content.strip()

        except Exception as e:
            return f"调用失败: {str(e)}"


async def query_graph(question: str) -> dict:
    """
    图谱智能查询
    输入: 自然语言问题
    输出: 基于图谱的答案
    """
    data = get_graph_data()
    relationships = data.get("relationships", [])
    top_entities = data.get("top_entities", [])

    # 构建上下文
    context_parts = []

    # Top 20 实体
    context_parts.append("=== 核心实体 ===")
    for e in top_entities[:20]:
        name = e.get('text') or e.get('name', 'unknown')
        count = e.get('importance') or e.get('count', 0)
        context_parts.append(f"- {name} ({e.get('type', 'unknown')}): {count}次出现")

    # 按关系类型统计
    rel_by_type = {}
    for r in relationships:
        t = r.get("relation_type", "unknown")
        if t not in rel_by_type:
            rel_by_type[t] = []
        rel_by_type[t].append(r)

    context_parts.append("\n=== 关系统计 ===")
    for t, rels in sorted(rel_by_type.items(), key=lambda x: -len(x[1])):
        context_parts.append(f"- {t}: {len(rels)}条")

    # 搜索相关关系
    question_lower = question.lower()
    relevant_rels = []

    for rel in relationships:
        if (rel["entity1"].lower() in question_lower or
            rel["entity2"].lower() in question_lower or
            any(word in rel["entity1"].lower() or word in rel["entity2"].lower()
                for word in question_lower.split() if len(word) > 2)):
            relevant_rels.append(rel)

    if relevant_rels:
        context_parts.append(f"\n=== 相关关系 ({len(relevant_rels)}条) ===")
        for r in relevant_rels[:30]:
            context_parts.append(
                f"- {r['entity1']} --[{r['relation_type']}]--> {r['entity2']} (共现{r['count']}次)"
            )

    context = "\n".join(context_parts)

    prompt = f"""基于以下邮件知识图谱数据，回答用户问题。

{context}

用户问题: {question}

请基于上述图谱数据，给出简洁准确的回答。如果数据中没有直接答案，请说明并给出相关推测。"""

    answer = await call_sglang(prompt, max_tokens=1000, temperature=0.3)

    return {
        "question": question,
        "answer": answer,
        "relevant_relations": len(relevant_rels),
        "total_entities": len(top_entities),
        "total_relations": len(relationships)
    }


async def generate_daily_summary(date: Optional[str] = None) -> dict:
    """
    生成每日邮件摘要
    """
    data = get_graph_data()
    relationships = data.get("relationships", [])
    top_entities = data.get("top_entities", [])

    # 关系类型分布
    rel_counts = {}
    for r in relationships:
        t = r.get("relation_type", "unknown")
        rel_counts[t] = rel_counts.get(t, 0) + 1

    # 高频联系人
    colleagues = [r for r in relationships if r.get("relation_type") == "colleague"]
    top_colleagues = sorted(colleagues, key=lambda x: -x["count"])[:10]

    # 业务伙伴
    partners = [r for r in relationships if r.get("relation_type") == "business_partner"]
    top_partners = sorted(partners, key=lambda x: -x["count"])[:10]

    summary_context = f"""
邮件图谱统计:
- 核心实体: {len(top_entities)}个
- 关系总数: {len(relationships)}条

关系类型分布:
{json.dumps(rel_counts, ensure_ascii=False, indent=2)}

高频同事关系:
{chr(10).join([f"- {r['entity1']} <-> {r['entity2']}: {r['count']}次" for r in top_colleagues])}

主要业务伙伴:
{chr(10).join([f"- {r['entity1']} <-> {r['entity2']}: {r['count']}次" for r in top_partners])}
"""

    prompt = f"""基于以下邮件知识图谱数据，生成一份简洁的每日工作摘要。

{summary_context}

请生成摘要，包含:
1. 关键联系人（最重要的3-5人，说明为什么重要）
2. 主要业务往来（公司/项目）
3. 建议关注事项

格式要求：使用中文，简洁明了，每点不超过2句话。"""

    summary = await call_sglang(prompt, max_tokens=800, temperature=0.5)

    return {
        "date": date or datetime.now().strftime("%Y-%m-%d"),
        "summary": summary,
        "stats": {
            "total_entities": len(top_entities),
            "total_relations": len(relationships),
            "relation_types": rel_counts,
            "top_colleagues": len(top_colleagues),
            "top_partners": len(top_partners)
        }
    }


def get_vsg_employees() -> set:
    """获取所有 VSG 员工名单"""
    data = get_graph_data()
    vsg_employees = set()
    for rel in data.get("relationships", []):
        if rel.get("relation_type") == "works_at" and rel["entity1"].lower() == "vsg":
            vsg_employees.add(rel["entity2"].lower())
    return vsg_employees


async def get_entity_insights(entity_name: str) -> dict:
    """
    获取实体洞察 (客户360视图)
    """
    data = get_graph_data()
    relationships = data.get("relationships", [])

    entity_lower = entity_name.lower()

    # 获取 VSG 员工名单
    vsg_employees = get_vsg_employees()

    # 查找所有相关关系
    related = []
    for rel in relationships:
        if entity_lower in rel["entity1"].lower() or entity_lower in rel["entity2"].lower():
            related.append(rel)

    if not related:
        return {
            "entity": entity_name,
            "found": False,
            "message": f"未找到与 '{entity_name}' 相关的关系"
        }

    # 按关系类型分组
    by_type = {}
    for r in related:
        t = r.get("relation_type", "unknown")
        if t not in by_type:
            by_type[t] = []
        by_type[t].append(r)

    # 统计并分类联系人
    total_interactions = sum(r["count"] for r in related)
    unique_contacts = set()
    vsg_contacts = []  # VSG员工联系人
    external_contacts = []  # 外部联系人

    for r in related:
        if entity_lower in r["entity1"].lower():
            contact = r["entity2"]
        else:
            contact = r["entity1"]

        # 跳过公司实体本身
        if contact.lower() in ["vsg", entity_lower] or "spacex" in contact.lower() or "space x" in contact.lower():
            continue

        unique_contacts.add(contact)

        # 判断是VSG员工还是外部人员
        contact_info = {"name": contact, "count": r["count"], "type": r.get("relation_type")}
        if contact.lower() in vsg_employees:
            vsg_contacts.append(contact_info)
        else:
            external_contacts.append(contact_info)

    # 去重并排序
    vsg_contacts_unique = {}
    for c in vsg_contacts:
        if c["name"] not in vsg_contacts_unique or c["count"] > vsg_contacts_unique[c["name"]]["count"]:
            vsg_contacts_unique[c["name"]] = c
    vsg_contacts = sorted(vsg_contacts_unique.values(), key=lambda x: -x["count"])

    external_contacts_unique = {}
    for c in external_contacts:
        if c["name"] not in external_contacts_unique or c["count"] > external_contacts_unique[c["name"]]["count"]:
            external_contacts_unique[c["name"]] = c
    external_contacts = sorted(external_contacts_unique.values(), key=lambda x: -x["count"])

    # 生成洞察上下文 - 明确标注人员归属
    insight_context = f"""
实体: {entity_name}
关系总数: {len(related)}
总互动次数: {total_interactions}
唯一联系人: {len(unique_contacts)}

=== VSG公司员工（我方人员）===
"""
    for c in vsg_contacts[:10]:
        insight_context += f"  - {c['name']}: {c['count']}次互动\n"

    if not vsg_contacts:
        insight_context += "  (无)\n"

    insight_context += f"""
=== {entity_name}方人员（外部联系人）===
"""
    for c in external_contacts[:10]:
        insight_context += f"  - {c['name']}: {c['count']}次互动\n"

    if not external_contacts:
        insight_context += "  (无明确外部人员，可能都是VSG员工在处理)\n"

    prompt = f"""你是一个专业的商业情报分析师。这是VSG公司的邮件系统数据。基于以下邮件通讯数据，为 "{entity_name}" 生成一份专业的洞察报告。

重要说明:
- 数据已经区分了VSG员工和外部联系人
- "VSG公司员工"是我方人员，负责对接{entity_name}
- "{entity_name}方人员"是外部联系人，可能是{entity_name}公司员工

{insight_context}

请直接输出分析报告（不要输出任何思考过程），格式如下:

## 实体概况
描述 {entity_name} 是什么类型的实体（公司/个人），在业务网络中的角色

## 人员分析
### VSG方对接人（我方公司）
列出VSG公司负责与{entity_name}对接的人员，推断其职位/角色，按互动频率排序

### {entity_name}方联系人（对方）
列出{entity_name}方的联系人（如有），推断其可能的职位/角色

## 合作关系分析
描述双方的合作类型、沟通频率、业务往来特点

## 关键对接人
- VSG方主要对接人: XXX（推断职位）
- {entity_name}方主要联系人: XXX（推断职位，如无外部人员则说明）

## 建议关注点
- 建议1
- 建议2"""

    insight = await call_sglang(prompt, max_tokens=1500, temperature=0.4)

    return {
        "entity": entity_name,
        "found": True,
        "insight": insight,
        "stats": {
            "total_relations": len(related),
            "total_interactions": total_interactions,
            "unique_contacts": len(unique_contacts),
            "vsg_contacts_count": len(vsg_contacts),
            "external_contacts_count": len(external_contacts),
            "relation_types": {k: len(v) for k, v in by_type.items()}
        },
        "vsg_contacts": [{"name": c["name"], "count": c["count"]} for c in vsg_contacts[:10]],
        "external_contacts": [{"name": c["name"], "count": c["count"]} for c in external_contacts[:10]],
        "top_contacts": [
            {
                "name": r["entity2"] if entity_lower in r["entity1"].lower() else r["entity1"],
                "type": r.get("relation_type"),
                "count": r["count"]
            }
            for r in sorted(related, key=lambda x: -x["count"])[:10]
        ]
    }


# 测试入口
if __name__ == "__main__":
    import asyncio

    async def test():
        print("=== 测试图谱智能查询 ===")
        result = await query_graph("谁和SpaceX有关系？")
        print(json.dumps(result, ensure_ascii=False, indent=2))

        print("\n=== 测试每日摘要 ===")
        summary = await generate_daily_summary()
        print(json.dumps(summary, ensure_ascii=False, indent=2))

        print("\n=== 测试实体洞察 ===")
        insight = await get_entity_insights("spacex")
        print(json.dumps(insight, ensure_ascii=False, indent=2))

    asyncio.run(test())
