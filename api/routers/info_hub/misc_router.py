"""
信息中心 - 其他 API (search, entities, emails, lightrag, projects)
"""

from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Query, HTTPException, BackgroundTasks
from ._common import get_db, GenerateReportRequest

router = APIRouter(tags=["InfoHub-Misc"])

@router.get("/search")
async def semantic_search(
    q: str = Query(..., min_length=1, description="搜索关键词"),
    limit: int = Query(10, ge=1, le=50),
    user_id: str = Query(None, description="限定用户 ID")
):
    """语义搜索邮件
    
    支持中英文自然语言搜索，返回相关度最高的邮件。
    """
    try:
        svc = get_embedding_service()
        results = svc.search(q, limit=limit, user_id=user_id)
        
        return {
            "query": q,
            "count": len(results),
            "results": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"搜索失败: {str(e)}")


@router.get("/search/stats")
async def search_stats():
    """获取搜索索引统计"""
    try:
        svc = get_embedding_service()
        stats = svc.get_stats()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取统计失败: {str(e)}")

# ===== 实体抽取 API (Phase 2) =====
from services.entity_service import get_entity_service

@router.get("/entities/stats")
async def get_entity_stats():
    """获取实体抽取统计"""
    svc = get_entity_service()
    return await svc.get_entity_stats()


@router.get("/entities/search")
async def search_entities(
    type: str = Query(None, description="实体类型: person, company, project, money, date, product, location"),
    text: str = Query(None, description="搜索文本"),
    limit: int = Query(50, ge=1, le=200),
):
    """搜索实体"""
    svc = get_entity_service()
    results = await svc.search_entities(entity_type=type, text=text, limit=limit)
    return {"results": results, "count": len(results)}


@router.get("/entities/email/{email_id}")
async def get_email_entities(email_id: str):
    """获取单封邮件的实体"""
    svc = get_entity_service()
    doc = await svc.entities.find_one({"email_id": email_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Email entities not found")
    doc["_id"] = str(doc["_id"])
    return doc


@router.post("/entities/extract")
async def extract_entities_batch(
    background_tasks: BackgroundTasks,
    limit: int = Query(500, ge=1, le=5000),
):
    """批量抽取实体（后台任务）"""
    async def do_extract():
        svc = get_entity_service()
        await svc.process_batch(limit=limit)
    
    background_tasks.add_task(do_extract)
    return {"success": True, "message": f"开始抽取，最多处理 {limit} 封邮件"}


# ===== 邮件浏览 API =====

@router.get("/emails")
async def list_emails(
    folder: str = Query(None, description="文件夹: inbox, sentitems"),
    category: str = Query(None, description="分类: external, internal, finance, sales, hr, technical, legal, marketing, procurement"),
    limit: int = Query(30, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """获取邮件列表，支持分类筛选"""
    db = get_db()
    
    query = {}
    if folder:
        query["folder"] = folder
    if category:
        query["category"] = category
    
    cursor = db.emails.find(
        query,
        {"email_id": 1, "subject": 1, "from": 1, "to": 1, "received_at": 1, "folder": 1, "category": 1, "entities": 1}
    ).sort("received_at", -1).skip(offset).limit(limit)
    
    emails = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        emails.append(doc)
    
    total = await db.emails.count_documents(query)
    
    return {
        "emails": emails,
        "total": total,
        "offset": offset,
        "limit": limit,
    }


# ===== LightRAG Q&A API (Phase 4) =====
from services.lightrag_service import get_lightrag_service

@router.get("/lightrag/stats")
async def get_lightrag_stats():
    """获取 LightRAG 索引统计"""
    svc = get_lightrag_service()
    return await svc.get_stats()


@router.post("/lightrag/index")
async def index_emails_to_lightrag(
    background_tasks: BackgroundTasks,
    limit: int = Query(500, ge=1, le=5000),
    days: int = Query(90, ge=1, le=365),
):
    """批量索引邮件到知识图谱（后台任务）"""
    async def do_index():
        svc = get_lightrag_service()
        await svc.index_emails(limit=limit, days=days)

    background_tasks.add_task(do_index)
    return {"success": True, "message": f"开始索引，最多处理 {limit} 封邮件（{days}天内）"}


@router.post("/lightrag/query")
async def query_lightrag(
    question: str = Query(..., description="问题"),
    mode: str = Query("hybrid", description="查询模式: naive/local/global/hybrid"),
):
    """知识图谱问答"""
    svc = get_lightrag_service()
    return await svc.query(question=question, mode=mode)


@router.post("/lightrag/summarize")
async def summarize_recent_emails(
    days: int = Query(1, ge=1, le=30),
):
    """总结最近邮件"""
    svc = get_lightrag_service()
    return await svc.summarize_recent(days=days)


# ===== 项目日报 API =====
from services.project_summarizer import generate_project_summary

@router.get("/projects/summary")
async def get_project_summary(date: str = Query(None)):
    """获取项目工作简报"""
    date_str = date or (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    
    db = get_db()
    
    # 先从缓存读取
    cached = await db.project_summaries.find_one({"date": date_str})
    if cached:
        cached["_id"] = str(cached["_id"])
        return {"summary": cached, "cached": True}
    
    # 无缓存，返回空
    return {
        "summary": None,
        "cached": False,
        "message": f"日期 {date_str} 无缓存数据，请先生成"
    }


@router.post("/projects/summary/generate")
async def generate_projects_summary(req: GenerateReportRequest, background_tasks: BackgroundTasks):
    """生成项目工作简报（调用LLM分析）"""
    date_str = req.date or (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    
    async def do_generate():
        db = get_db()
        try:
            result = await generate_project_summary(date_str)
            
            # 存储到数据库
            await db.project_summaries.update_one(
                {"date": date_str},
                {"$set": result},
                upsert=True
            )
            print(f"✅ 项目简报已生成: {date_str}")
        except Exception as e:
            print(f"❌ 项目简报生成失败: {e}")
            import traceback
            traceback.print_exc()
    
    background_tasks.add_task(do_generate)
    return {"success": True, "message": f"项目简报生成已启动: {date_str}"}


@router.get("/projects/raw")
async def get_projects_raw():
    """获取原始项目数据（不经过LLM分析）"""
    from services.project_store import get_project_store
    
    store = get_project_store()
    projects = await store.list_projects()
    tasks = await store.list_tasks()
    
    # 按项目分组任务
    project_tasks = {}
    for t in tasks:
        pid = t.get("project_id")
        if pid not in project_tasks:
            project_tasks[pid] = []
        project_tasks[pid].append(t)
    
    # 统计
    stats = {
        "total_projects": len(projects),
        "total_tasks": len(tasks),
        "by_status": {},
        "by_assignee": {}
    }
    
    for t in tasks:
        status = t.get("status", "unknown")
        stats["by_status"][status] = stats["by_status"].get(status, 0) + 1
        
        assignee = t.get("assignee_name", "未分配")
        if assignee not in stats["by_assignee"]:
            stats["by_assignee"][assignee] = {"count": 0, "projects": set()}
        stats["by_assignee"][assignee]["count"] += 1
        stats["by_assignee"][assignee]["projects"].add(t.get("project_id"))
    
    # 转换set为list
    for a in stats["by_assignee"]:
        stats["by_assignee"][a]["projects"] = list(stats["by_assignee"][a]["projects"])
    
    return {
        "projects": projects,
        "tasks": tasks,
        "project_tasks": project_tasks,
        "stats": stats
    }
