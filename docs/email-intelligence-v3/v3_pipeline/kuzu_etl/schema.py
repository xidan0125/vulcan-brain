#!/usr/bin/env python3
"""
KùzuDB Schema - V2 Compatible
"""
import kuzu
from pathlib import Path

KUZU_DB_PATH = Path.home() / "vulcan_data" / "kuzu_data" / "email_graph"

NODE_TABLES = [
    """
    CREATE NODE TABLE IF NOT EXISTS BusinessEvent (
        id STRING,
        event_type STRING,
        event_date STRING,
        summary STRING,
        amount DOUBLE,
        currency STRING,
        created_at STRING,
        PRIMARY KEY (id)
    )
    """,
    """
    CREATE NODE TABLE IF NOT EXISTS Thread (
        id STRING,
        topic STRING,
        email_count INT32,
        PRIMARY KEY (id)
    )
    """,
    """
    CREATE NODE TABLE IF NOT EXISTS Email (
        id STRING,
        subject STRING,
        sent_at STRING,
        sender STRING,
        kuzu_synced_at STRING,
        PRIMARY KEY (id)
    )
    """,
    """
    CREATE NODE TABLE IF NOT EXISTS Company (
        id STRING,
        canonical_name STRING,
        original_name STRING,
        match_type STRING,
        PRIMARY KEY (id)
    )
    """,
    """
    CREATE NODE TABLE IF NOT EXISTS Identifier (
        val STRING,
        id_type STRING,
        PRIMARY KEY (val)
    )
    """,
    """
    CREATE NODE TABLE IF NOT EXISTS Product (
        id STRING,
        name STRING,
        PRIMARY KEY (id)
    )
    """,
    """
    CREATE NODE TABLE IF NOT EXISTS Person (
        id STRING,
        name STRING,
        PRIMARY KEY (id)
    )
    """,
]

REL_TABLES = [
    "CREATE REL TABLE IF NOT EXISTS BELONGS_TO (FROM Email TO Thread)",
    "CREATE REL TABLE IF NOT EXISTS EVIDENCES (FROM Email TO BusinessEvent, confidence DOUBLE)",
    "CREATE REL TABLE IF NOT EXISTS INVOLVES (FROM BusinessEvent TO Company)",
    "CREATE REL TABLE IF NOT EXISTS HAS_ID (FROM BusinessEvent TO Identifier)",
    "CREATE REL TABLE IF NOT EXISTS CONCERNS (FROM BusinessEvent TO Product)",
    "CREATE REL TABLE IF NOT EXISTS EMPLOYS (FROM Company TO Person)",
    "CREATE REL TABLE IF NOT EXISTS REPLIES_TO (FROM Email TO Email)",
]

DROP_STATEMENTS = [
    "DROP TABLE IF EXISTS REPLIES_TO",
    "DROP TABLE IF EXISTS EMPLOYS",
    "DROP TABLE IF EXISTS CONCERNS",
    "DROP TABLE IF EXISTS HAS_ID",
    "DROP TABLE IF EXISTS INVOLVES",
    "DROP TABLE IF EXISTS EVIDENCES",
    "DROP TABLE IF EXISTS BELONGS_TO",
    "DROP TABLE IF EXISTS Person",
    "DROP TABLE IF EXISTS Product",
    "DROP TABLE IF EXISTS Identifier",
    "DROP TABLE IF EXISTS Company",
    "DROP TABLE IF EXISTS Email",
    "DROP TABLE IF EXISTS Thread",
    "DROP TABLE IF EXISTS BusinessEvent",
]


def init_database(reset: bool = False) -> kuzu.Database:
    print(f"{'='*60}")
    print(f"KùzuDB Schema Initialization")
    print(f"{'='*60}")
    print(f"Database path: {KUZU_DB_PATH}")

    KUZU_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = kuzu.Database(str(KUZU_DB_PATH))
    conn = kuzu.Connection(db)

    if reset:
        print("\n🗑️  Dropping existing tables...")
        for stmt in DROP_STATEMENTS:
            try:
                conn.execute(stmt)
                print(f"   Dropped: {stmt.split()[-1]}")
            except:
                pass

    print("\n📦 Creating node tables...")
    for ddl in NODE_TABLES:
        try:
            conn.execute(ddl)
            name = ddl.split("TABLE")[1].split("IF NOT EXISTS")[1].split("(")[0].strip()
            print(f"   ✅ {name}")
        except Exception as e:
            if "already exists" not in str(e).lower():
                print(f"   ❌ {e}")

    print("\n🔗 Creating relationship tables...")
    for ddl in REL_TABLES:
        try:
            conn.execute(ddl)
            name = ddl.split("TABLE")[1].split("IF NOT EXISTS")[1].split("(")[0].strip()
            print(f"   ✅ {name}")
        except Exception as e:
            if "already exists" not in str(e).lower():
                print(f"   ❌ {e}")

    print(f"\n{'='*60}")
    print("✅ Schema initialization complete!")
    print(f"{'='*60}")
    return db


def get_connection() -> tuple:
    db = kuzu.Database(str(KUZU_DB_PATH))
    conn = kuzu.Connection(db)
    return db, conn


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()
    init_database(reset=args.reset)
