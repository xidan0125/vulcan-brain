#!/usr/bin/env python3
"""
KùzuDB Verification Queries
Quick graph exploration and validation
"""
import kuzu
from pathlib import Path

KUZU_DB_PATH = Path.home() / "vulcan_data" / "kuzu_data" / "email_graph"


def get_conn():
    db = kuzu.Database(str(KUZU_DB_PATH))
    return kuzu.Connection(db)


def show_stats():
    """Show basic graph statistics"""
    conn = get_conn()
    print("=" * 60)
    print("📊 Graph Statistics")
    print("=" * 60)

    queries = [
        ("BusinessEvent", "MATCH (n:BusinessEvent) RETURN count(n)"),
        ("Email", "MATCH (n:Email) RETURN count(n)"),
        ("Company", "MATCH (n:Company) RETURN count(n)"),
        ("Identifier", "MATCH (n:Identifier) RETURN count(n)"),
        ("Thread", "MATCH (n:Thread) RETURN count(n)"),
        ("Product", "MATCH (n:Product) RETURN count(n)"),
        ("Person", "MATCH (n:Person) RETURN count(n)"),
        ("---", "---"),
        ("EVIDENCES", "MATCH ()-[r:EVIDENCES]->() RETURN count(r)"),
        ("INVOLVES", "MATCH ()-[r:INVOLVES]->() RETURN count(r)"),
        ("HAS_ID", "MATCH ()-[r:HAS_ID]->() RETURN count(r)"),
        ("BELONGS_TO", "MATCH ()-[r:BELONGS_TO]->() RETURN count(r)"),
        ("CONCERNS", "MATCH ()-[r:CONCERNS]->() RETURN count(r)"),
    ]

    for name, query in queries:
        if name == "---":
            print()
            continue
        try:
            result = conn.execute(query)
            count = result.get_next()[0]
            print(f"  {name:15} {count:>6}")
        except Exception as e:
            print(f"  {name:15} Error: {e}")


def show_sample_events(limit: int = 5):
    """Show sample BusinessEvents"""
    conn = get_conn()
    print("\n" + "=" * 60)
    print("🎯 Sample BusinessEvents")
    print("=" * 60)

    result = conn.execute(f"""
        MATCH (be:BusinessEvent)
        RETURN be.id, be.event_type, be.event_date, be.amount, be.currency
        LIMIT {limit}
    """)

    while result.has_next():
        row = result.get_next()
        print(f"  {row[0][:30]:30} | {row[1]:12} | {row[2]:12} | {row[3]:>10.2f} {row[4]}")


def show_sample_companies(limit: int = 10):
    """Show sample Companies"""
    conn = get_conn()
    print("\n" + "=" * 60)
    print("🏢 Sample Companies")
    print("=" * 60)

    result = conn.execute(f"""
        MATCH (c:Company)
        RETURN c.id, c.normalized_name, c.original_name
        LIMIT {limit}
    """)

    while result.has_next():
        row = result.get_next()
        print(f"  {row[0][:25]:25} | {row[1][:25]:25} | {row[2][:30]}")


def show_event_graph(event_id: str):
    """Show full graph around a BusinessEvent"""
    conn = get_conn()
    print("\n" + "=" * 60)
    print(f"🕸️  Event Graph: {event_id}")
    print("=" * 60)

    # Get event details
    result = conn.execute("""
        MATCH (be:BusinessEvent {id: $eid})
        RETURN be.event_type, be.event_date, be.summary, be.amount, be.currency
    """, {"eid": event_id})

    if result.has_next():
        row = result.get_next()
        print(f"  Type: {row[0]}")
        print(f"  Date: {row[1]}")
        print(f"  Summary: {row[2][:80]}...")
        print(f"  Amount: {row[3]} {row[4]}")

    # Get related emails
    print("\n  📧 Emails:")
    result = conn.execute("""
        MATCH (e:Email)-[:EVIDENCES]->(be:BusinessEvent {id: $eid})
        RETURN e.id, e.subject, e.sent_at
    """, {"eid": event_id})

    while result.has_next():
        row = result.get_next()
        print(f"    - {row[1][:50]}... ({row[2][:10]})")

    # Get related companies
    print("\n  🏢 Companies:")
    result = conn.execute("""
        MATCH (be:BusinessEvent {id: $eid})-[:INVOLVES]->(c:Company)
        RETURN c.normalized_name
    """, {"eid": event_id})

    while result.has_next():
        row = result.get_next()
        print(f"    - {row[0]}")

    # Get identifiers
    print("\n  🔖 Identifiers:")
    result = conn.execute("""
        MATCH (be:BusinessEvent {id: $eid})-[:HAS_ID]->(i:Identifier)
        RETURN i.val, i.id_type
    """, {"eid": event_id})

    while result.has_next():
        row = result.get_next()
        print(f"    - {row[0]} ({row[1]})")


def find_company_events(company_name: str):
    """Find all events involving a company"""
    conn = get_conn()
    print("\n" + "=" * 60)
    print(f"🔍 Events for: {company_name}")
    print("=" * 60)

    result = conn.execute("""
        MATCH (c:Company)<-[:INVOLVES]-(be:BusinessEvent)
        WHERE c.normalized_name CONTAINS $name
        RETURN be.id, be.event_type, be.event_date, be.amount, be.currency, c.normalized_name
        ORDER BY be.event_date DESC
        LIMIT 20
    """, {"name": company_name.upper()})

    while result.has_next():
        row = result.get_next()
        print(f"  {row[0][:25]:25} | {row[1]:12} | {row[2]:12} | {row[3]:>10.2f} {row[4]}")


def trace_identifier(identifier: str):
    """Trace all entities connected to an identifier"""
    conn = get_conn()
    # Normalize the input
    from normalizer import normalize_identifier
    norm_id = normalize_identifier(identifier)

    print("\n" + "=" * 60)
    print(f"🔗 Tracing: {identifier} -> {norm_id}")
    print("=" * 60)

    # Find the identifier
    result = conn.execute("""
        MATCH (i:Identifier {val: $val})
        RETURN i.val, i.id_type
    """, {"val": norm_id})

    if not result.has_next():
        print(f"  ❌ Identifier not found: {norm_id}")
        return

    row = result.get_next()
    print(f"  Identifier: {row[0]} ({row[1]})")

    # Find connected events
    print("\n  📋 Connected Events:")
    result = conn.execute("""
        MATCH (be:BusinessEvent)-[:HAS_ID]->(i:Identifier {val: $val})
        RETURN be.id, be.event_type, be.amount, be.currency
    """, {"val": norm_id})

    while result.has_next():
        row = result.get_next()
        print(f"    - {row[0]} | {row[1]} | {row[2]} {row[3]}")

    # Find connected emails
    print("\n  📧 Connected Emails:")
    result = conn.execute("""
        MATCH (e:Email)-[:EVIDENCES]->(be:BusinessEvent)-[:HAS_ID]->(i:Identifier {val: $val})
        RETURN e.subject, e.sent_at
    """, {"val": norm_id})

    while result.has_next():
        row = result.get_next()
        print(f"    - {row[0][:50]}... ({row[1][:10]})")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "stats":
            show_stats()
        elif cmd == "events":
            show_sample_events(int(sys.argv[2]) if len(sys.argv) > 2 else 5)
        elif cmd == "companies":
            show_sample_companies(int(sys.argv[2]) if len(sys.argv) > 2 else 10)
        elif cmd == "event" and len(sys.argv) > 2:
            show_event_graph(sys.argv[2])
        elif cmd == "company" and len(sys.argv) > 2:
            find_company_events(sys.argv[2])
        elif cmd == "trace" and len(sys.argv) > 2:
            trace_identifier(sys.argv[2])
        else:
            print("Usage:")
            print("  python queries.py stats           # Show graph statistics")
            print("  python queries.py events [n]      # Show n sample events")
            print("  python queries.py companies [n]   # Show n sample companies")
            print("  python queries.py event <id>      # Show event details")
            print("  python queries.py company <name>  # Find company events")
            print("  python queries.py trace <id>      # Trace identifier")
    else:
        show_stats()
        show_sample_events()
        show_sample_companies()
