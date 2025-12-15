#!/usr/bin/env python3
"""
KùzuDB 初始化脚本
创建Schema并导入种子实体
"""
import kuzu
import pymongo
from pathlib import Path
import shutil

# KùzuDB 存储路径
KUZU_DB_PATH = Path.home() / "vulcan-brain" / "kuzu_db"

def init_database():
    """初始化KùzuDB数据库"""
    print('='*60)
    print('🚀 KùzuDB 初始化')
    print('='*60)

    # 清理旧数据库（如果存在）
    if KUZU_DB_PATH.exists():
        print(f'\n⚠️  删除旧数据库: {KUZU_DB_PATH}')
        shutil.rmtree(KUZU_DB_PATH)

    # 创建数据库
    print(f'\n📂 创建数据库: {KUZU_DB_PATH}')
    db = kuzu.Database(str(KUZU_DB_PATH))
    conn = kuzu.Connection(db)

    # ========== 创建节点表 ==========
    print('\n📋 创建节点表...')

    # Event节点（每封邮件=一个事件）
    conn.execute("""
        CREATE NODE TABLE IF NOT EXISTS Event (
            event_id STRING PRIMARY KEY,
            mongo_ref STRING,
            event_type STRING,
            timestamp TIMESTAMP,
            subject STRING
        )
    """)
    print('   ✅ Event')

    # Entity节点（公司/人/产品/地点）
    conn.execute("""
        CREATE NODE TABLE IF NOT EXISTS Entity (
            entity_id STRING PRIMARY KEY,
            mongo_ref STRING,
            type STRING,
            name STRING,
            normalized_key STRING
        )
    """)
    print('   ✅ Entity')

    # Fact节点（原子数据点）
    conn.execute("""
        CREATE NODE TABLE IF NOT EXISTS Fact (
            fact_id STRING PRIMARY KEY,
            mongo_ref STRING,
            type STRING,
            value STRING,
            normalized_value DOUBLE,
            confidence DOUBLE
        )
    """)
    print('   ✅ Fact')

    # ========== 创建边表 ==========
    print('\n🔗 创建边表...')

    # Event → Entity（邮件涉及哪些实体）
    conn.execute("""
        CREATE REL TABLE IF NOT EXISTS INVOLVES (
            FROM Event TO Entity,
            role STRING
        )
    """)
    print('   ✅ INVOLVES (Event → Entity)')

    # Event → Fact（邮件包含哪些数据点）
    conn.execute("""
        CREATE REL TABLE IF NOT EXISTS HAS_FACT (
            FROM Event TO Fact,
            source_file STRING
        )
    """)
    print('   ✅ HAS_FACT (Event → Fact)')

    # Entity → Entity（实体间关系）
    conn.execute("""
        CREATE REL TABLE IF NOT EXISTS RELATES_TO (
            FROM Entity TO Entity,
            relation_type STRING,
            confidence DOUBLE,
            derived_from STRING
        )
    """)
    print('   ✅ RELATES_TO (Entity → Entity)')

    # Fact → Entity（事实关联到谁）
    conn.execute("""
        CREATE REL TABLE IF NOT EXISTS BELONGS_TO (
            FROM Fact TO Entity
        )
    """)
    print('   ✅ BELONGS_TO (Fact → Entity)')

    # Event → Event（邮件线程）
    conn.execute("""
        CREATE REL TABLE IF NOT EXISTS REPLY_TO (
            FROM Event TO Event
        )
    """)
    print('   ✅ REPLY_TO (Event → Event)')

    return db, conn


def import_seed_entities(conn):
    """从entities_v3导入种子实体到KùzuDB"""
    print('\n' + '='*60)
    print('📥 导入种子实体')
    print('='*60)

    mongo_client = pymongo.MongoClient('mongodb://localhost:27017/')
    mongo_db = mongo_client.vulcan_brain

    total = mongo_db.entities_v3.count_documents({})
    print(f'\n从 entities_v3 导入 {total} 个实体...')

    imported = 0
    batch_size = 500
    batch = []

    for doc in mongo_db.entities_v3.find():
        entity_id = doc['entity_id']
        mongo_ref = str(doc['_id'])
        entity_type = doc['type']
        name = doc['canonical_name'].replace("'", "''")  # 转义单引号
        normalized_key = doc['normalized_key']

        # 构建插入语句
        query = f"""
            CREATE (e:Entity {{
                entity_id: '{entity_id}',
                mongo_ref: '{mongo_ref}',
                type: '{entity_type}',
                name: '{name}',
                normalized_key: '{normalized_key}'
            }})
        """
        batch.append(query)

        if len(batch) >= batch_size:
            for q in batch:
                try:
                    conn.execute(q)
                    imported += 1
                except Exception as e:
                    print(f'   ⚠️ 跳过: {e}')
            batch = []
            print(f'   已导入: {imported}/{total}')

    # 处理剩余
    for q in batch:
        try:
            conn.execute(q)
            imported += 1
        except Exception as e:
            pass

    print(f'\n✅ 导入完成: {imported} 个实体')
    return imported


def verify_database(conn):
    """验证数据库"""
    print('\n' + '='*60)
    print('🔍 验证数据库')
    print('='*60)

    # 统计节点
    result = conn.execute("MATCH (e:Entity) RETURN COUNT(e) AS count")
    count = result.get_next()[0]
    print(f'\n   Entity节点: {count}')

    # 按类型统计
    result = conn.execute("""
        MATCH (e:Entity)
        RETURN e.type AS type, COUNT(e) AS count
        ORDER BY count DESC
    """)
    print('\n   按类型分布:')
    while result.has_next():
        row = result.get_next()
        print(f'     {row[0]}: {row[1]}')

    # 测试查询
    print('\n   测试查询 - 查找包含"Vulcan"的实体:')
    result = conn.execute("""
        MATCH (e:Entity)
        WHERE e.name CONTAINS 'Vulcan'
        RETURN e.name, e.type
        LIMIT 5
    """)
    while result.has_next():
        row = result.get_next()
        print(f'     [{row[1]}] {row[0]}')


def main():
    # 初始化数据库和Schema
    db, conn = init_database()

    # 导入种子实体
    import_seed_entities(conn)

    # 验证
    verify_database(conn)

    print('\n' + '='*60)
    print('✅ KùzuDB 初始化完成!')
    print(f'   数据库路径: {KUZU_DB_PATH}')
    print('='*60)


if __name__ == '__main__':
    main()
