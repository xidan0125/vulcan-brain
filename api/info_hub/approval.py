"""
审批 API 模块
/api/info-hub/approval/*
"""
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Query, HTTPException, BackgroundTasks
from pydantic import BaseModel

from services.approval_store import get_approval_store
from services.approval_service import collect_all_approvals, trigger_approval_analysis

router = APIRouter(prefix="/approval", tags=["Approval"])


class CollectApprovalsRequest(BaseModel):
    approval_codes: Optional[List[str]] = None
    since_hours: int = 24


@router.get("/dashboard")
async def get_approval_dashboard(date: str = Query(None)):
    """获取审批仪表盘"""
    store = get_approval_store()
    
    if date:
        try:
            date_obj = datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format")
    else:
        date_obj = datetime.now()
    
    start = date_obj.replace(hour=0, minute=0, second=0)
    end = date_obj.replace(hour=23, minute=59, second=59)
    stats = await store.get_stats(since=start, until=end)
    summary = await store.get_summary(date_obj.strftime("%Y-%m-%d"))
    
    return {
        "date": date_obj.strftime("%Y-%m-%d"),
        "stats": stats,
        "summary": summary,
        "pending_count": stats.get("pending_count", 0)
    }


@router.get("/list")
async def list_approvals(
    status: str = Query(None, description="状态: PENDING/APPROVED/REJECTED/CANCELED"),
    approval_code: str = Query(None, description="审批类型 code"),
    date: str = Query(None, description="日期 YYYY-MM-DD"),
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0)
):
    """获取审批列表"""
    store = get_approval_store()
    
    since, until = None, None
    if date:
        try:
            date_obj = datetime.strptime(date, "%Y-%m-%d")
            since = date_obj.replace(hour=0, minute=0, second=0)
            until = date_obj.replace(hour=23, minute=59, second=59)
        except:
            pass
    
    approvals = await store.list_approvals(
        approval_code=approval_code,
        status=status,
        since=since,
        until=until,
        limit=limit + skip
    )
    approvals = approvals[skip:skip + limit]
    
    result = []
    for ap in approvals:
        result.append({
            "instance_code": ap.get("instance_code"),
            "approval_code": ap.get("approval_code"),
            "approval_name": ap.get("approval_name"),
            "status": ap.get("status"),
            "user_id": ap.get("user_id"),
            "open_id": ap.get("open_id"),
            "start_time": ap.get("start_time"),
            "end_time": ap.get("end_time"),
            "serial_number": ap.get("serial_number")
        })
    
    return {"approvals": result, "count": len(result)}


@router.get("/definitions")
async def list_approval_definitions():
    """获取审批定义列表"""
    store = get_approval_store()
    definitions = await store.list_definitions()
    return {"definitions": definitions, "count": len(definitions)}


@router.get("/pending")
async def get_pending_approvals(user_id: str = Query(None)):
    """获取待处理审批"""
    store = get_approval_store()
    approvals = await store.get_pending_approvals(user_id)
    return {"approvals": approvals, "count": len(approvals)}


@router.get("/summaries")
async def get_approval_summaries(days: int = Query(7, ge=1, le=30)):
    """获取最近 N 天的审批汇总"""
    store = get_approval_store()
    summaries = await store.list_summaries(days)
    return {"summaries": summaries, "count": len(summaries)}


@router.get("/{instance_code}")
async def get_approval_detail(instance_code: str):
    """获取审批详情"""
    store = get_approval_store()
    approval = await store.get_approval(instance_code)
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")
    return {"approval": approval}


@router.post("/collect")
async def collect_approvals(req: CollectApprovalsRequest, background_tasks: BackgroundTasks):
    """采集飞书审批数据"""
    async def do_collect():
        try:
            result = await collect_all_approvals(since_hours=req.since_hours)
            print(f"[Approval] ✅ 审批采集完成: {result}")
        except Exception as e:
            print(f"[Approval] ❌ 审批采集失败: {e}")
    
    background_tasks.add_task(do_collect)
    return {
        "success": True,
        "message": f"审批采集已启动，范围: {req.since_hours} 小时"
    }


@router.post("/analyze")
async def analyze_approvals(date: str = Query(None)):
    """生成审批日报分析"""
    date_str = date or datetime.now().strftime("%Y-%m-%d")
    try:
        result = await trigger_approval_analysis(date_str)
        return {"success": True, "summary": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
