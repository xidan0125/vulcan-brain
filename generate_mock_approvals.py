"""
生成Mock审批数据用于测试
"""

import asyncio
from datetime import datetime, timedelta
import random
import json
from pymongo import MongoClient
import os

# MongoDB连接
mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
client = MongoClient(mongo_uri)
db = client["vulcan_brain"]

# 审批定义（审批类型）
APPROVAL_DEFINITIONS = [
    {"approval_code": "LEAVE_001", "approval_name": "请假申请", "is_external": False},
    {"approval_code": "REIMB_001", "approval_name": "费用报销", "is_external": False},
    {"approval_code": "TRAVEL_001", "approval_name": "出差申请", "is_external": False},
    {"approval_code": "PURCHASE_001", "approval_name": "采购申请", "is_external": False},
    {"approval_code": "CONTRACT_001", "approval_name": "合同审批", "is_external": False},
    {"approval_code": "PAYMENT_001", "approval_name": "付款申请", "is_external": False},
]

# 用户列表
USERS = [
    {"user_id": "user_001", "open_id": "ou_a1b2c3d4e5f6", "name": "张三"},
    {"user_id": "user_002", "open_id": "ou_b2c3d4e5f6a1", "name": "李四"},
    {"user_id": "user_003", "open_id": "ou_c3d4e5f6a1b2", "name": "王五"},
    {"user_id": "user_004", "open_id": "ou_d4e5f6a1b2c3", "name": "赵六"},
    {"user_id": "user_005", "open_id": "ou_e5f6a1b2c3d4", "name": "孙七"},
]

# 状态列表
STATUSES = ["PENDING", "APPROVED", "REJECTED", "CANCELED"]

def generate_form(approval_code):
    """根据审批类型生成表单内容"""
    if approval_code == "LEAVE_001":
        return json.dumps([
            {"name": "请假类型", "value": random.choice(["年假", "事假", "病假", "调休"])},
            {"name": "开始时间", "value": (datetime.now() + timedelta(days=random.randint(1, 7))).strftime("%Y-%m-%d")},
            {"name": "天数", "value": random.randint(1, 5)},
            {"name": "原因", "value": random.choice(["个人事务", "身体不适", "家庭原因"])}
        ])
    elif approval_code == "REIMB_001":
        return json.dumps([
            {"name": "费用类型", "value": random.choice(["交通费", "餐费", "办公用品", "培训费"])},
            {"name": "金额", "value": random.randint(100, 5000)},
            {"name": "说明", "value": "业务相关费用报销"}
        ])
    elif approval_code == "TRAVEL_001":
        return json.dumps([
            {"name": "出差城市", "value": random.choice(["北京", "上海", "深圳", "杭州", "成都"])},
            {"name": "出差天数", "value": random.randint(2, 7)},
            {"name": "预算", "value": random.randint(3000, 15000)},
            {"name": "目的", "value": random.choice(["客户拜访", "项目交付", "培训学习", "商务洽谈"])}
        ])
    elif approval_code == "PURCHASE_001":
        return json.dumps([
            {"name": "采购物品", "value": random.choice(["办公设备", "软件许可", "服务器", "会议设备"])},
            {"name": "金额", "value": random.randint(1000, 50000)},
            {"name": "供应商", "value": random.choice(["京东", "淘宝", "官方渠道"])}
        ])
    elif approval_code == "CONTRACT_001":
        return json.dumps([
            {"name": "合同类型", "value": random.choice(["销售合同", "采购合同", "服务合同", "合作协议"])},
            {"name": "合同金额", "value": random.randint(10000, 500000)},
            {"name": "对方公司", "value": f"测试公司{random.randint(1, 10)}"}
        ])
    elif approval_code == "PAYMENT_001":
        return json.dumps([
            {"name": "付款类型", "value": random.choice(["货款", "服务费", "预付款"])},
            {"name": "金额", "value": random.randint(5000, 100000)},
            {"name": "收款方", "value": f"供应商{random.randint(1, 10)}"}
        ])
    return json.dumps([])


def generate_mock_approvals(count=50):
    """生成Mock审批数据"""
    approvals = []

    for i in range(count):
        definition = random.choice(APPROVAL_DEFINITIONS)
        user = random.choice(USERS)
        status = random.choice(STATUSES)

        # 生成时间（最近7天内）
        days_ago = random.randint(0, 7)
        start_time = datetime.now() - timedelta(days=days_ago, hours=random.randint(0, 23))

        # 如果已完成，设置结束时间
        end_time = None
        if status in ["APPROVED", "REJECTED", "CANCELED"]:
            end_time = start_time + timedelta(hours=random.randint(1, 48))

        approval = {
            "instance_code": f"INST_{datetime.now().strftime('%Y%m%d')}_{i:04d}",
            "approval_code": definition["approval_code"],
            "approval_name": definition["approval_name"],
            "status": status,
            "user_id": user["user_id"],
            "open_id": user["open_id"],
            "department_id": f"dept_{random.randint(1, 5)}",
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat() if end_time else None,
            "serial_number": f"SN{random.randint(100000, 999999)}",
            "form": generate_form(definition["approval_code"]),
            "timeline": [],
            "comment_list": [],
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }

        approvals.append(approval)

    return approvals


def main():
    print("=" * 50)
    print("开始生成Mock审批数据")
    print("=" * 50)

    # 1. 插入审批定义
    print("\n1. 插入审批定义...")
    for defn in APPROVAL_DEFINITIONS:
        defn["cached_at"] = datetime.now().isoformat()
        db.approval_definitions.update_one(
            {"approval_code": defn["approval_code"]},
            {"$set": defn},
            upsert=True
        )
    print(f"   已插入 {len(APPROVAL_DEFINITIONS)} 个审批定义")

    # 2. 生成并插入审批实例
    print("\n2. 生成审批实例...")
    approvals = generate_mock_approvals(50)

    inserted = 0
    for ap in approvals:
        result = db.feishu_approvals.update_one(
            {"instance_code": ap["instance_code"]},
            {"$set": ap},
            upsert=True
        )
        if result.upserted_id:
            inserted += 1

    print(f"   已生成 {len(approvals)} 条审批, 新插入 {inserted} 条")

    # 3. 生成日报汇总
    print("\n3. 生成日报汇总...")
    today = datetime.now().strftime("%Y-%m-%d")

    # 统计
    total = db.feishu_approvals.count_documents({})
    pending = db.feishu_approvals.count_documents({"status": "PENDING"})
    approved = db.feishu_approvals.count_documents({"status": "APPROVED"})
    rejected = db.feishu_approvals.count_documents({"status": "REJECTED"})

    by_type = {}
    for defn in APPROVAL_DEFINITIONS:
        count = db.feishu_approvals.count_documents({"approval_code": defn["approval_code"]})
        by_type[defn["approval_name"]] = count

    summary = {
        "date": today,
        "total_count": total,
        "by_status": {
            "PENDING": pending,
            "APPROVED": approved,
            "REJECTED": rejected
        },
        "by_type": by_type,
        "pending_count": pending,
        "summary": f"今日共{total}条审批记录，{pending}条待处理",
        "highlights": ["费用报销金额较大需关注", "3条合同审批待处理"],
        "pending_attention": ["紧急付款申请需尽快处理"],
        "risks": [],
        "recommendations": ["建议加快审批流程"],
        "generated_at": datetime.now().isoformat()
    }

    db.approval_summaries.update_one(
        {"date": today},
        {"$set": summary},
        upsert=True
    )
    print(f"   已生成 {today} 日报汇总")

    # 4. 输出统计
    print("\n" + "=" * 50)
    print("Mock数据生成完成!")
    print("=" * 50)
    print(f"\n📊 统计:")
    print(f"   - 审批定义: {len(APPROVAL_DEFINITIONS)} 个")
    print(f"   - 审批实例: {total} 条")
    print(f"   - 待处理: {pending} 条")
    print(f"   - 已通过: {approved} 条")
    print(f"   - 已拒绝: {rejected} 条")
    print(f"\n📝 按类型分布:")
    for name, count in by_type.items():
        print(f"   - {name}: {count} 条")


if __name__ == "__main__":
    main()
