#!/usr/bin/env python3
"""
KùzuDB 数据清洗脚本 v2 - 修复 SET 语法
"""
import kuzu
from dateutil import parser as date_parser
import re

KUZU_PATH = "/home/xinyue/vulcan_data/kuzu_data/email_graph"

def standardize_date(date_str: str) -> str:
    """将各种日期格式统一为 YYYY-MM-DD"""
    if not date_str or date_str in ('null', 'None', ''):
        return None
    try:
        parsed = date_parser.parse(str(date_str), fuzzy=True)
        return parsed.strftime("%Y-%m-%d")
    except:
        return None

def clean_amount(amount) -> tuple:
    """清洗金额，返回 (cleaned_amount, is_valid)"""
    if amount is None:
        return None, True
    try:
        amount = float(amount)
    except:
        return None, False
    if amount < 0 or amount > 100_000_000 or amount < 0.01:
        return None, False
    return amount, True

def main():
    print("🧹 KùzuDB 数据清洗 v2")
    print("=" * 50)

    db = kuzu.Database(KUZU_PATH)
    conn = kuzu.Connection(db)

    # 获取所有事件
    result = conn.execute("""
        MATCH (be:BusinessEvent)
        RETURN be.id, be.event_date, be.amount
    """)

    events = []
    while result.has_next():
        row = result.get_next()
        events.append({"id": row[0], "event_date": row[1], "amount": row[2]})

    print(f"📊 总事件数: {len(events)}")

    # 统计
    date_need_fix = 0
    amount_need_fix = 0

    for e in events:
        if e["event_date"]:
            new_date = standardize_date(e["event_date"])
            if new_date and new_date != str(e["event_date"]):
                date_need_fix += 1
        if e["amount"]:
            _, is_valid = clean_amount(e["amount"])
            if not is_valid:
                amount_need_fix += 1

    print(f"📅 需要修复日期: {date_need_fix}")
    print(f"💰 需要清理异常金额: {amount_need_fix}")

    # 执行清洗
    print("\n🔧 开始清洗...")

    date_fixed = 0
    amount_cleaned = 0
    errors = 0

    for e in events:
        # 日期标准化
        if e["event_date"]:
            new_date = standardize_date(e["event_date"])
            if new_date and new_date != str(e["event_date"]):
                try:
                    # KùzuDB SET 语法: SET be.property = value
                    conn.execute(f'MATCH (be:BusinessEvent {{id: "{e["id"]}"}}) SET be.event_date = "{new_date}"')
                    date_fixed += 1
                except Exception as ex:
                    errors += 1
                    if errors <= 3:
                        print(f"   ⚠️ 日期更新失败 {e['id'][:20]}: {str(ex)[:50]}")

        # 金额清洗
        if e["amount"]:
            _, is_valid = clean_amount(e["amount"])
            if not is_valid:
                try:
                    conn.execute(f'MATCH (be:BusinessEvent {{id: "{e["id"]}"}}) SET be.amount = null')
                    amount_cleaned += 1
                except Exception as ex:
                    errors += 1
                    if errors <= 3:
                        print(f"   ⚠️ 金额更新失败 {e['id'][:20]}: {str(ex)[:50]}")

    print(f"\n✅ 清洗完成:")
    print(f"   日期标准化: {date_fixed}")
    print(f"   异常金额清除: {amount_cleaned}")
    print(f"   错误数: {errors}")

    # 验证
    print("\n🔍 验证...")
    result = conn.execute("""
        MATCH (be:BusinessEvent)
        WHERE be.amount > 100000000
        RETURN count(*)
    """)
    anomaly_count = result.get_next()[0]
    print(f"   剩余异常金额 (>1亿): {anomaly_count}")

    result = conn.execute("""
        MATCH (be:BusinessEvent)
        WHERE be.event_date IS NOT NULL
        RETURN be.event_date
        LIMIT 5
    """)
    print("   日期样本:")
    while result.has_next():
        print(f"     {result.get_next()[0]}")

if __name__ == "__main__":
    main()
