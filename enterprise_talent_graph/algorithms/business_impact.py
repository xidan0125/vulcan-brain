"""
Business Impact Algorithm
从 KuzuDB 的 BusinessEvent 数据计算每个 VSG 员工的业务影响力

算法逻辑:
1. 从 KuzuDB 获取所有交易对手及其交易金额
2. 对每个交易对手，在 MongoDB emails 中统计 VSG 员工的邮件往来数量
3. 按邮件数量比例分配交易金额给参与的员工
4. 聚合计算每个员工的总业务贡献
"""

import kuzu
from pymongo import MongoClient
from collections import defaultdict
import re

def get_kuzu_connection():
    db = kuzu.Database("/home/xinyue/vulcan_data/kuzu_data/email_graph", read_only=True)
    return kuzu.Connection(db)

def get_mongo_db():
    client = MongoClient("mongodb://localhost:27017")
    return client.vulcan_brain

def get_all_counterparties_with_amounts(kuzu_conn):
    """从 KuzuDB 获取所有有金额的交易对手"""
    result = kuzu_conn.execute("""
        MATCH (be:BusinessEvent)
        WHERE be.amount > 100
        RETURN be.counterparty,
               sum(be.amount) as total_amount,
               count(*) as event_count,
               collect(be.event_type) as event_types
        ORDER BY total_amount DESC
    """)

    counterparties = []
    while result.has_next():
        row = result.get_next()
        if row[0]:  # 排除空的 counterparty
            counterparties.append({
                "name": row[0],
                "total_amount": row[1],
                "event_count": row[2],
                "event_types": row[3]
            })

    return counterparties

def get_vsg_employees_for_counterparty(mongo_db, counterparty_name):
    """找出与某个交易对手有邮件往来的 VSG 员工"""
    # 提取交易对手名称的关键词用于搜索
    # 使用第一个有意义的词 (跳过常见词)
    skip_words = {"PTE", "LTD", "SDN", "BHD", "INC", "CORP", "CO", "THE", "OF", "AND"}
    words = counterparty_name.upper().split()
    search_terms = [w for w in words if w not in skip_words and len(w) > 2][:2]

    if not search_terms:
        return {}

    # 构建搜索条件
    search_pattern = search_terms[0]

    # 搜索发送给这个交易对手的邮件 (VSG 员工发出)
    pipeline = [
        {
            "$match": {
                "$and": [
                    {"from.address": {"$regex": "vulcanshield", "$options": "i"}},
                    {"$or": [
                        {"subject": {"$regex": search_pattern, "$options": "i"}},
                        {"to.address": {"$regex": search_pattern.lower()[:8], "$options": "i"}}
                    ]}
                ]
            }
        },
        {
            "$group": {
                "_id": {"$toLower": "$from.address"},
                "email_count": {"$sum": 1}
            }
        },
        {"$sort": {"email_count": -1}},
        {"$limit": 10}
    ]

    results = list(mongo_db.emails.aggregate(pipeline))

    # 转换为字典
    employees = {}
    for r in results:
        email = r["_id"]
        # 过滤掉系统邮箱
        if "microsoft" not in email and "noreply" not in email:
            employees[email] = r["email_count"]

    return employees

def calculate_business_impact(counterparties, mongo_db):
    """计算每个员工的业务影响"""
    # 存储每个员工的业务贡献
    employee_impact = defaultdict(lambda: {
        "total_attributed_value": 0,
        "deals_involved": 0,
        "counterparties": [],
        "event_type_distribution": defaultdict(lambda: {"count": 0, "amount": 0}),
        "top_deals": []
    })

    print(f"处理 {len(counterparties)} 个交易对手...")

    for i, cp in enumerate(counterparties):
        if i % 50 == 0:
            print(f"  进度: {i}/{len(counterparties)}")

        cp_name = cp["name"]
        total_amount = cp["total_amount"]
        event_count = cp["event_count"]
        event_types = cp["event_types"]

        # 找出参与这个交易的 VSG 员工
        employees = get_vsg_employees_for_counterparty(mongo_db, cp_name)

        if not employees:
            continue

        # 计算总邮件数用于分配权重
        total_emails = sum(employees.values())

        # 确定主要事件类型
        primary_event_type = max(set(event_types), key=event_types.count) if event_types else "Unknown"

        # 按邮件数量比例分配金额给每个员工
        for email, email_count in employees.items():
            weight = email_count / total_emails
            attributed_amount = total_amount * weight

            employee_impact[email]["total_attributed_value"] += attributed_amount
            employee_impact[email]["deals_involved"] += 1
            employee_impact[email]["counterparties"].append({
                "name": cp_name,
                "amount": total_amount,
                "attributed": attributed_amount,
                "email_count": email_count,
                "weight": weight
            })
            employee_impact[email]["event_type_distribution"][primary_event_type]["count"] += 1
            employee_impact[email]["event_type_distribution"][primary_event_type]["amount"] += attributed_amount

            # 记录大额交易
            if attributed_amount > 100000:
                employee_impact[email]["top_deals"].append({
                    "counterparty": cp_name,
                    "total_amount": total_amount,
                    "attributed": attributed_amount,
                    "event_type": primary_event_type
                })

    return dict(employee_impact)

def save_business_impact_to_mongodb(mongo_db, employee_impact):
    """将业务影响数据保存到 MongoDB talent_nodes"""
    print(f"\n保存 {len(employee_impact)} 个员工的业务影响数据...")

    updated_count = 0
    for email, impact in employee_impact.items():
        # 准备 business_impact 字段
        business_impact = {
            "total_attributed_value": round(impact["total_attributed_value"], 2),
            "deals_involved": impact["deals_involved"],
            "event_type_distribution": {
                k: {"count": v["count"], "amount": round(v["amount"], 2)}
                for k, v in impact["event_type_distribution"].items()
            },
            "top_counterparties": sorted(
                impact["counterparties"],
                key=lambda x: x["attributed"],
                reverse=True
            )[:5],  # 只保留 top 5
            "top_deals": sorted(
                impact["top_deals"],
                key=lambda x: x["attributed"],
                reverse=True
            )[:5]  # 只保留 top 5 大额交易
        }

        # 更新 MongoDB
        result = mongo_db.talent_nodes.update_one(
            {"email": email},
            {"$set": {"business_impact": business_impact}},
            upsert=False
        )

        if result.modified_count > 0:
            updated_count += 1

    print(f"成功更新 {updated_count} 个员工的 business_impact")
    return updated_count

def main():
    print("=== 业务影响算法 (Business Impact) ===\n")

    # 连接数据库
    kuzu_conn = get_kuzu_connection()
    mongo_db = get_mongo_db()

    # 1. 获取所有交易对手
    print("1. 从 KuzuDB 获取交易对手数据...")
    counterparties = get_all_counterparties_with_amounts(kuzu_conn)
    print(f"   找到 {len(counterparties)} 个有金额的交易对手")

    total_deal_value = sum(cp["total_amount"] for cp in counterparties)
    print(f"   总交易金额: ${total_deal_value:,.0f}")

    # 2. 计算业务影响
    print("\n2. 计算每个员工的业务影响...")
    employee_impact = calculate_business_impact(counterparties, mongo_db)

    # 3. 打印结果
    print("\n3. 业务影响排名 TOP 15:")
    sorted_employees = sorted(
        employee_impact.items(),
        key=lambda x: x[1]["total_attributed_value"],
        reverse=True
    )[:15]

    for rank, (email, impact) in enumerate(sorted_employees, 1):
        name = email.split("@")[0]
        value = impact["total_attributed_value"]
        deals = impact["deals_involved"]
        print(f"   {rank:2}. {name:25} ${value:>15,.0f}  ({deals} deals)")

    # 4. 保存到 MongoDB
    print("\n4. 保存到 MongoDB...")
    save_business_impact_to_mongodb(mongo_db, employee_impact)

    print("\n=== 完成 ===")

if __name__ == "__main__":
    main()
