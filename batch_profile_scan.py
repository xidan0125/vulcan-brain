#!/usr/bin/env python3
"""批量扫描VSG员工生成画像"""

import requests
import time
from pymongo import MongoClient
from datetime import datetime

# MongoDB
client = MongoClient("mongodb://localhost:27017")
db = client.vulcan_brain

# API
API_URL = "http://localhost:8001/api/employee-profile/generate"

# 获取所有VSG员工（排除公共邮箱）
def get_vsg_employees():
    pipeline = [
        {"$match": {"from.address": {"$regex": "vulcanshield\\.com$", "$options": "i"}}},
        {"$group": {"_id": "$from.address", "count": {"$sum": 1}}},
        {"$match": {"count": {"$gte": 20}}},
        {"$sort": {"count": -1}}
    ]
    results = list(db.emails.aggregate(pipeline))
    
    # 排除公共邮箱
    exclude = ['sales@', 'finance@', 'inquiry@', 'info@', 'hr@', 'admin@']
    employees = []
    for r in results:
        email = r['_id'].lower()
        if not any(email.startswith(ex) for ex in exclude):
            employees.append({'email': r['_id'], 'email_count': r['count']})
    return employees

def scan_employee(email):
    """扫描单个员工"""
    try:
        resp = requests.post(API_URL, json={"email": email, "force_refresh": False}, timeout=300)
        data = resp.json()
        return data.get('success', False), data.get('cached', False), data.get('error')
    except Exception as e:
        return False, False, str(e)

def main():
    employees = get_vsg_employees()
    print(f"找到 {len(employees)} 个VSG员工")
    print("=" * 60)
    
    # 记录进度
    success_count = 0
    cached_count = 0
    failed = []
    
    for i, emp in enumerate(employees, 1):
        email = emp['email']
        count = emp['email_count']
        
        print(f"[{i}/{len(employees)}] 扫描 {email} ({count}封邮件)...", end=" ", flush=True)
        
        start = time.time()
        success, cached, error = scan_employee(email)
        elapsed = time.time() - start
        
        if success:
            if cached:
                print(f"已缓存 ({elapsed:.1f}s)")
                cached_count += 1
            else:
                print(f"生成成功 ({elapsed:.1f}s)")
                success_count += 1
        else:
            print(f"失败: {error}")
            failed.append(email)
        
        # 避免过载
        if not cached:
            time.sleep(2)
    
    print("=" * 60)
    print(f"扫描完成!")
    print(f"  新生成: {success_count}")
    print(f"  已缓存: {cached_count}")
    print(f"  失败: {len(failed)}")
    if failed:
        print(f"  失败列表: {failed}")
    
    # 保存扫描记录
    db.profile_scan_logs.insert_one({
        "scan_time": datetime.now(),
        "total": len(employees),
        "success": success_count,
        "cached": cached_count,
        "failed": failed
    })

if __name__ == "__main__":
    main()
