"""
V3.8 提取监控 API
提供实时状态数据和监控台页面
"""
import json
from pathlib import Path
from datetime import datetime
from collections import Counter
from fastapi import APIRouter, Response
from fastapi.responses import HTMLResponse

router = APIRouter()

CACHE_DIR = Path.home() / "vulcan_data" / "cache"
PROGRESS_PATH = CACHE_DIR / "download_progress.json"
EXTRACTION_LOG_PATH = CACHE_DIR / "extraction_log.jsonl"
EXTRACTION_STATE_PATH = CACHE_DIR / "extraction_state.json"
MONITOR_HTML_PATH = Path.home() / "vulcan-brain" / "docs" / "email-intelligence-v3" / "v3_pipeline" / "extraction_monitor.html"

@router.get("/v3-monitor")
async def get_monitor_page():
    """返回监控台 HTML 页面"""
    if MONITOR_HTML_PATH.exists():
        html = MONITOR_HTML_PATH.read_text()
        # 修改 API 路径为相对路径
        html = html.replace("fetch('/api/extraction-status')", "fetch('/api/v3-monitor/status')")
        return HTMLResponse(content=html)
    return HTMLResponse(content="<h1>Monitor not found</h1>", status_code=404)

@router.get("/v3-monitor/status")
async def get_extraction_status():
    """返回提取状态 JSON"""
    result = {
        "total": 0,
        "extracted": 0,
        "success": 0,
        "failed": 0,
        "skipped": 0,
        "avg_duration": 0,
        "avg_facts": 0,
        "rate": 0,
        "eta": "--",
        "is_running": False,
        "download": {"total": 0, "done": 0, "pending": 0},
        "type_dist": {},
        "fact_dist": {},
        "recent_logs": []
    }
    
    # 下载状态
    if PROGRESS_PATH.exists():
        try:
            download_data = json.loads(PROGRESS_PATH.read_text())
            result["download"]["total"] = len(download_data)
            
            status_counts = Counter(r["status"] for r in download_data)
            result["download"]["done"] = status_counts.get("downloaded", 0) + status_counts.get("processed", 0)
            result["download"]["pending"] = status_counts.get("pending", 0)
            
            # 按 email_id 分组得到邮件总数
            email_ids = set(r["email_id"] for r in download_data if r["status"] in ("downloaded", "processed"))
            result["total"] = len(email_ids)
        except Exception:
            pass
    
    # 提取状态
    if EXTRACTION_STATE_PATH.exists():
        try:
            state = json.loads(EXTRACTION_STATE_PATH.read_text())
            result["extracted"] = len(state.get("extracted_ids", []))
        except Exception:
            pass
    
    # 日志分析
    if EXTRACTION_LOG_PATH.exists():
        try:
            logs = []
            with open(EXTRACTION_LOG_PATH) as f:
                for line in f:
                    if line.strip():
                        logs.append(json.loads(line))
            
            if logs:
                status_counts = Counter(l["status"] for l in logs)
                result["success"] = status_counts.get("success", 0)
                result["failed"] = status_counts.get("failed", 0)
                result["skipped"] = status_counts.get("skipped", 0)
                
                success_logs = [l for l in logs if l["status"] == "success"]
                if success_logs:
                    result["avg_duration"] = sum(l["duration"] for l in success_logs) / len(success_logs)
                    result["avg_facts"] = sum(l["fact_count"] for l in success_logs) / len(success_logs)
                
                # 速率计算
                recent = [l for l in logs if l.get("timestamp")]
                if len(recent) >= 2:
                    try:
                        first_time = datetime.fromisoformat(recent[0]["timestamp"])
                        last_time = datetime.fromisoformat(recent[-1]["timestamp"])
                        duration_min = (last_time - first_time).total_seconds() / 60
                        if duration_min > 0:
                            result["rate"] = len(recent) / duration_min
                            remaining = result["total"] - result["extracted"]
                            if result["rate"] > 0:
                                eta_min = remaining / result["rate"]
                                result["eta"] = f"{eta_min:.0f}min" if eta_min < 60 else f"{eta_min/60:.1f}h"
                    except Exception:
                        pass
                
                result["recent_logs"] = logs[-20:][::-1]
                
                # 检测是否正在运行
                if recent:
                    try:
                        last_time = datetime.fromisoformat(recent[-1]["timestamp"])
                        if (datetime.now() - last_time).total_seconds() < 30:
                            result["is_running"] = True
                    except Exception:
                        pass
        except Exception:
            pass
    
    # 类型分布 (从 MongoDB)
    try:
        import pymongo
        client = pymongo.MongoClient("mongodb://localhost:27017", serverSelectionTimeoutMS=2000)
        db = client.vulcan_brain
        
        pipeline = [
            {"$match": {"v3_unified_extraction": {"$exists": True}}},
            {"$group": {"_id": "$v3_unified_extraction.email_type", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 8}
        ]
        type_dist = list(db.emails.aggregate(pipeline))
        result["type_dist"] = {t["_id"]: t["count"] for t in type_dist if t["_id"]}
        
        pipeline = [
            {"$match": {"v3_unified_extraction.facts": {"$exists": True}}},
            {"$unwind": "$v3_unified_extraction.facts"},
            {"$group": {"_id": "$v3_unified_extraction.facts.type", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 10}
        ]
        fact_dist = list(db.emails.aggregate(pipeline))
        result["fact_dist"] = {f["_id"]: f["count"] for f in fact_dist if f["_id"]}
        
        client.close()
    except Exception:
        pass
    
    return result
