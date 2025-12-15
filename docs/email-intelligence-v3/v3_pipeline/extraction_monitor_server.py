#!/usr/bin/env python3
"""
V3.8 提取监控 API 服务
提供实时状态数据给监控台
"""
import json
import os
from pathlib import Path
from datetime import datetime
from collections import Counter, defaultdict
from http.server import HTTPServer, SimpleHTTPRequestHandler
import pymongo

CACHE_DIR = Path.home() / "vulcan_data" / "cache"
PROGRESS_PATH = CACHE_DIR / "download_progress.json"
EXTRACTION_LOG_PATH = CACHE_DIR / "extraction_log_v312.jsonl"
EXTRACTION_STATE_PATH = CACHE_DIR / "extraction_state_v312.json"
MONITOR_HTML = Path(__file__).parent / "extraction_monitor.html"

class MonitorHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/api/extraction-status':
            self.send_status_api()
        elif self.path == '/' or self.path == '/index.html':
            self.send_dashboard()
        else:
            super().do_GET()
    
    def send_dashboard(self):
        """发送监控台页面"""
        html_path = MONITOR_HTML
        if not html_path.exists():
            # 尝试同目录
            html_path = Path(__file__).parent / "extraction_monitor.html"
        
        if html_path.exists():
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(html_path.read_bytes())
        else:
            self.send_error(404, "Dashboard not found")
    
    def send_status_api(self):
        """发送状态 API"""
        data = get_status()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode())
    
    def log_message(self, format, *args):
        pass  # 静默日志

def get_status():
    """获取当前状态"""
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
        except:
            pass
    
    # 提取状态
    if EXTRACTION_STATE_PATH.exists():
        try:
            state = json.loads(EXTRACTION_STATE_PATH.read_text())
            result["extracted"] = len(state.get("extracted_ids", []))
        except:
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
                # 状态统计
                status_counts = Counter(l["status"] for l in logs)
                result["success"] = status_counts.get("success", 0)
                result["failed"] = status_counts.get("failed", 0)
                result["skipped"] = status_counts.get("skipped", 0)
                
                # 性能统计
                success_logs = [l for l in logs if l["status"] == "success"]
                if success_logs:
                    result["avg_duration"] = sum(l["duration"] for l in success_logs) / len(success_logs)
                    result["avg_facts"] = sum(l["fact_count"] for l in success_logs) / len(success_logs)
                
                # 速率计算 (最近5分钟)
                recent = [l for l in logs if l.get("timestamp")]
                if len(recent) >= 2:
                    try:
                        first_time = datetime.fromisoformat(recent[0]["timestamp"])
                        last_time = datetime.fromisoformat(recent[-1]["timestamp"])
                        duration_min = (last_time - first_time).total_seconds() / 60
                        if duration_min > 0:
                            result["rate"] = len(recent) / duration_min
                            
                            # ETA
                            remaining = result["total"] - result["extracted"]
                            if result["rate"] > 0:
                                eta_min = remaining / result["rate"]
                                if eta_min < 60:
                                    result["eta"] = f"{eta_min:.0f}min"
                                else:
                                    result["eta"] = f"{eta_min/60:.1f}h"
                    except:
                        pass
                
                # 最近日志
                result["recent_logs"] = logs[-20:][::-1]
                
                # 检测是否正在运行 (最近30秒有新日志)
                if recent:
                    try:
                        last_time = datetime.fromisoformat(recent[-1]["timestamp"])
                        if (datetime.now() - last_time).total_seconds() < 30:
                            result["is_running"] = True
                    except:
                        pass
        except:
            pass
    
    # 类型分布 (从 MongoDB)
    try:
        client = pymongo.MongoClient("mongodb://localhost:27017", serverSelectionTimeoutMS=2000)
        db = client.vulcan_brain
        
        # 邮件类型分布
        pipeline = [
            {"$match": {"v3_extraction_v312": {"$exists": True}}},
            {"$group": {"_id": "$v3_extraction_v312.email_type", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 8}
        ]
        type_dist = list(db.emails.aggregate(pipeline))
        result["type_dist"] = {t["_id"]: t["count"] for t in type_dist if t["_id"]}
        
        # Fact 类型分布
        pipeline = [
            {"$match": {"v3_extraction_v312.facts": {"$exists": True}}},
            {"$unwind": "$v3_extraction_v312.facts"},
            {"$group": {"_id": "$v3_extraction_v312.facts.type", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 10}
        ]
        fact_dist = list(db.emails.aggregate(pipeline))
        result["fact_dist"] = {f["_id"]: f["count"] for f in fact_dist if f["_id"]}
        
        client.close()
    except:
        pass
    
    return result

def main():
    port = 8889
    print(f"🖥️  V3.8 提取监控服务启动")
    print(f"   访问: http://localhost:{port}")
    print(f"   API:  http://localhost:{port}/api/extraction-status")
    
    server = HTTPServer(('0.0.0.0', port), MonitorHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 监控服务已停止")

if __name__ == "__main__":
    main()
