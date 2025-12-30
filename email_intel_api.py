"""
Email Intelligence Agent API V2
邮件数据智能分析Agent - 支持自然语言查询 + 可视化图表生成
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import kuzu
import json
import uuid
import re
import httpx
from datetime import datetime

from agent_session_store import get_agent_session, save_agent_session, list_user_sessions
from vulcan_libs.llm_client import get_llm_client, ChatMessage, ModelType

router = APIRouter(prefix="/api/email-intel", tags=["email-intel-agent"])

# KuzuDB 配置
KUZU_PATH = "/home/xinyue/vulcan_data/kuzu_data/email_graph"

# 代码执行器地址
CODE_EXECUTOR_URL = "http://localhost:8001/api/code-exec/execute"

# 可视化关键词
VIZ_KEYWORDS = ["画", "图", "图表", "可视化", "柱状图", "饼图", "折线图", "趋势", "分布", "对比"]

# System Prompt (增强版 - 支持可视化)
SYSTEM_PROMPT = """你是VSG公司的邮件数据分析助手。你可以：
1. 执行Cypher查询来回答数据问题
2. 生成Python代码绘制可视化图表

## 重要规则
1. **必须执行查询**：任何涉及数据的问题，必须先输出Cypher查询
2. **不要猜测数据**：所有数据必须来自查询结果
3. **可视化请求**：当用户要求"画图/图表/可视化"时，先查询数据，再生成Python绘图代码

## 数据库信息
- 数据库: KuzuDB (图数据库)
- 主要节点: BusinessEvent
- 事件类型: Order(订单), Quotation(报价), Shipment(物流), Contract(合同)
- 字段: event_type, counterparty(交易对手), amount(金额), currency, status, event_date, summary

## Cypher查询格式
```cypher
MATCH (e:BusinessEvent)
WHERE e.event_type = 'Order'
RETURN e.counterparty, count(*) as count
ORDER BY count DESC
LIMIT 10
```

## KuzuDB 特殊语法规则
- **不要使用 GROUP BY**: KuzuDB中聚合是隐式的，RETURN中的非聚合列会自动分组
- 错误示例: `RETURN a, b, count(*) GROUP BY a, b` ❌
- 正确示例: `RETURN a, b, count(*) as cnt` ✅ (自动按a,b分组)

## Python绘图格式（当用户要求可视化时）
```python
# 数据已在df变量中，列名直接对应RETURN字段名
plt.figure(figsize=(10, 6))
plt.barh(df['event_type'], df['count'], color='steelblue')  # 用真实列名!
plt.xlabel('数量')
plt.title('标题')
plt.tight_layout()
plt.show()
```

## 绘图规则
- 数据已加载到 `df` DataFrame，列名与RETURN字段名一致
- 例如: RETURN e.event_type, count(*) as count → df['event_type'], df['count']
- 例如: RETURN e.status, e.event_type, count(*) → df['status'], df['event_type'], df['count']
- 只能用: matplotlib, pandas, numpy, seaborn
- 必须调用 plt.figure() 开始，plt.show() 结束
- 柱状图用 plt.barh()（横向）或 plt.bar()（纵向）
- 饼图用 plt.pie()
- 折线图用 plt.plot()
- 需要pivot时: df.pivot(index='列1', columns='列2', values='列3')

请用简洁的中文回答。"""


class AgentRequest(BaseModel):
    query: str
    session_id: Optional[str] = None


class AgentResponse(BaseModel):
    answer: str
    session_id: str
    data: Optional[List] = None
    cypher: Optional[str] = None
    image: Optional[str] = None  # Base64图片
    python_code: Optional[str] = None


def get_kuzu_connection():
    """获取KuzuDB连接"""
    db = kuzu.Database(KUZU_PATH, read_only=True)
    return kuzu.Connection(db)


def execute_cypher(cypher: str) -> List:
    """执行Cypher查询"""
    try:
        conn = get_kuzu_connection()
        result = conn.execute(cypher)
        rows = []
        while result.has_next():
            rows.append(result.get_next())
        return rows
    except Exception as e:
        return [{"error": str(e)}]


def clean_think_tags(content: str) -> str:
    """清理LLM输出中的think标签"""
    if "</think>" in content:
        content = content.split("</think>")[-1].strip()
    return content


def extract_cypher(text: str) -> Optional[str]:
    """从LLM回复中提取Cypher查询"""
    pattern = r'```(?:cypher|sql)?\s*(MATCH[\s\S]*?)```'
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return match.group(1).strip()

    pattern2 = r'(MATCH\s+\(.*?(?:RETURN|LIMIT).*?)(?:\n\n|$)'
    match2 = re.search(pattern2, text, re.IGNORECASE | re.DOTALL)
    if match2:
        return match2.group(1).strip()

    return None


def extract_python_code(text: str) -> Optional[str]:
    """从LLM回复中提取Python代码"""
    pattern = r'```python\s*([\s\S]*?)```'
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return None


def extract_columns_from_cypher(cypher: str) -> List[str]:
    """从Cypher查询的RETURN子句提取列名

    示例:
    - "RETURN e.event_type, count(*)" → ["event_type", "count"]
    - "RETURN e.event_type AS type, count(*) AS cnt" → ["type", "cnt"]
    - "RETURN e.counterparty, sum(e.amount), count(*)" → ["counterparty", "sum", "count"]
    """
    columns = []

    # 找RETURN子句
    return_match = re.search(r'RETURN\s+(.+?)(?:ORDER|LIMIT|$)', cypher, re.IGNORECASE | re.DOTALL)
    if not return_match:
        return columns

    return_clause = return_match.group(1).strip()

    # 分割各列 (注意处理括号内的逗号)
    parts = []
    depth = 0
    current = ""
    for char in return_clause:
        if char == '(':
            depth += 1
        elif char == ')':
            depth -= 1
        elif char == ',' and depth == 0:
            parts.append(current.strip())
            current = ""
            continue
        current += char
    if current.strip():
        parts.append(current.strip())

    # 提取每列的列名
    for part in parts:
        part = part.strip()
        if not part:
            continue

        # 有别名: "xxx AS alias"
        alias_match = re.search(r'\s+AS\s+(\w+)\s*$', part, re.IGNORECASE)
        if alias_match:
            columns.append(alias_match.group(1))
            continue

        # 聚合函数: count(*), sum(e.amount), avg(...)
        agg_match = re.match(r'(count|sum|avg|min|max|collect)\s*\(', part, re.IGNORECASE)
        if agg_match:
            columns.append(agg_match.group(1).lower())
            continue

        # 属性访问: e.event_type → event_type
        prop_match = re.search(r'\.(\w+)\s*$', part)
        if prop_match:
            columns.append(prop_match.group(1))
            continue

        # 其他情况用整个表达式简化
        clean = re.sub(r'[^\w]', '_', part)[:20]
        columns.append(clean if clean else f"col{len(columns)}")

    return columns


def needs_visualization(query: str) -> bool:
    """判断用户是否需要可视化"""
    return any(keyword in query for keyword in VIZ_KEYWORDS)


async def execute_python_code(code: str, data: List, columns: List[str] = None) -> Dict:
    """调用代码执行器API

    Args:
        code: LLM生成的Python代码
        data: KuzuDB查询结果
        columns: 列名列表 (从Cypher提取)
    """
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                CODE_EXECUTOR_URL,
                json={
                    "code": code,
                    "data": data,
                    "columns": columns,  # 传递列名!
                    "timeout": 50
                }
            )
            return response.json()
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/agent", response_model=AgentResponse)
async def chat_with_agent(request: AgentRequest):
    """
    与邮件数据Agent对话

    - 支持自然语言查询
    - 自动生成Cypher并执行
    - 支持可视化图表生成
    - 维护对话session
    """
    user_id = "admin"
    session_id = request.session_id or str(uuid.uuid4())
    history = await get_agent_session(user_id, session_id)

    # 构建消息
    messages = [ChatMessage(role="system", content=SYSTEM_PROMPT)]
    for msg in history[-20:]:
        messages.append(ChatMessage(role=msg["role"], content=msg["content"]))
    messages.append(ChatMessage(role="user", content=request.query))

    # 调用LLM
    try:
        llm_client = get_llm_client()
        response = await llm_client.chat(messages, model=ModelType.QWEN3)
        llm_answer = clean_think_tags(response.content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM调用失败: {str(e)}")

    # 提取Cypher和Python代码
    cypher = extract_cypher(llm_answer)
    python_code = extract_python_code(llm_answer)
    query_result = None
    image_base64 = None
    final_answer = llm_answer
    columns = []  # Schema层: 列名

    # 执行Cypher查询
    if cypher:
        # 提取列名 (关键的Schema层!)
        columns = extract_columns_from_cypher(cypher); print(f"DEBUG: extracted columns = {columns}")
        query_result = execute_cypher(cypher)

        # 检查是否有错误
        has_error = query_result and any(
            isinstance(r, dict) and "error" in r for r in query_result
        )

        # 边缘情况: 空数据
        if not query_result or len(query_result) == 0:
            if needs_visualization(request.query):
                final_answer = "查询没有返回任何数据，无法生成图表。请尝试调整查询条件。"
            else:
                final_answer = "查询没有返回任何数据。"
        elif not has_error:
            # 如果有Python代码，执行可视化 (带列名!)
            if python_code:
                exec_result = await execute_python_code(python_code, query_result, columns)

                if exec_result.get("success") and exec_result.get("image_base64"):
                    image_base64 = exec_result["image_base64"]
                    final_answer = "已为您生成图表。"

                    # 如果有额外输出
                    if exec_result.get("output"):
                        final_answer += f"\n\n{exec_result['output']}"
                elif exec_result.get("error"):
                    final_answer = f"图表生成失败: {exec_result['error']}\n\n数据查询结果: {len(query_result)} 条"

            # 没有Python代码，让LLM总结数据
            elif not needs_visualization(request.query):
                summary_prompt = f"""查询结果:
{json.dumps(query_result[:20], ensure_ascii=False, default=str)}

请根据以上查询结果，用简洁的中文回答用户的问题: "{request.query}"
不要再输出Cypher语句。"""

                try:
                    summary_messages = [
                        ChatMessage(role="system", content="你是数据分析助手，请简洁地总结查询结果。"),
                        ChatMessage(role="user", content=summary_prompt)
                    ]
                    summary_response = await llm_client.chat(summary_messages, model=ModelType.QWEN3)
                    final_answer = clean_think_tags(summary_response.content)
                except:
                    final_answer = f"查询到 {len(query_result)} 条结果"

    # 保存对话
    new_history = history + [
        {"role": "user", "content": request.query, "timestamp": datetime.now().isoformat()},
        {"role": "assistant", "content": final_answer, "timestamp": datetime.now().isoformat()}
    ]
    await save_agent_session(user_id, session_id, new_history, agent_type="email_agent")

    return AgentResponse(
        answer=final_answer,
        session_id=session_id,
        data=query_result[:20] if query_result else None,
        cypher=cypher,
        image=image_base64,
        python_code=python_code
    )


@router.get("/sessions")
async def get_sessions():
    """获取用户的所有邮件Agent会话"""
    user_id = "admin"
    sessions = await list_user_sessions(user_id, agent_type="email_agent")
    return {"sessions": sessions}


@router.delete("/session/{session_id}")
async def delete_session(session_id: str):
    """删除指定会话"""
    from agent_session_store import delete_agent_session
    user_id = "admin"
    success = await delete_agent_session(user_id, session_id)
    return {"success": success}


@router.get("/stats")
async def get_quick_stats():
    """获取快速统计（不需要LLM）"""
    try:
        conn = get_kuzu_connection()
        stats = {}

        result = conn.execute("""
            MATCH (e:BusinessEvent)
            WHERE e.event_type IN ['Order', 'Quotation', 'Shipment', 'Contract']
            RETURN e.event_type, count(*) as cnt
            ORDER BY cnt DESC
        """)
        stats["by_type"] = []
        while result.has_next():
            row = result.get_next()
            stats["by_type"].append({"type": row[0], "count": row[1]})

        result = conn.execute("""
            MATCH (e:BusinessEvent)
            RETURN e.status, count(*) as cnt
            ORDER BY cnt DESC
        """)
        stats["by_status"] = {}
        while result.has_next():
            row = result.get_next()
            stats["by_status"][row[0]] = row[1]

        result = conn.execute("MATCH (e:BusinessEvent) RETURN count(e)")
        stats["total"] = result.get_next()[0]

        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
