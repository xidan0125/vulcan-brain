#!/usr/bin/env python3
"""
KùzuDB ETL Pipeline
Event-Centric Architecture v2.0

Usage:
    python etl_pipeline.py --limit 100    # Test with 100 emails
    python etl_pipeline.py                # Process all unsynced
    python etl_pipeline.py --reset        # Reset DB and reprocess
"""
import kuzu
import pymongo
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import sys

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from schema import KUZU_DB_PATH, init_database, get_connection
from normalizer import (
    normalize_company_name,
    normalize_identifier,
    classify_identifier_type,
    extract_thread_id,
    infer_event_type,
    parse_amount,
)

# ============================================
# Configuration
# ============================================
MONGO_URI = "mongodb://localhost:27017"
MONGO_DB = "vulcan_brain"
EXTRACTION_FIELD = "v3_extraction_v312"  # V3.12 extraction results


def get_unsynced_emails(mongo_db, limit: Optional[int] = None) -> List[Dict]:
    """
    Get emails with V3.12 extraction but not yet synced to KùzuDB
    """
    query = {
        EXTRACTION_FIELD: {"$exists": True},
        "$or": [
            {"kuzu_synced_at": {"$exists": False}},
            {"kuzu_synced_at": None}
        ]
    }

    cursor = mongo_db.emails.find(query)
    if limit:
        cursor = cursor.limit(limit)

    return list(cursor)


def etl_single_email(email: Dict, conn: kuzu.Connection) -> Dict:
    """
    ETL single email to graph

    Returns:
        {"status": "success/skipped/error", "nodes": int, "rels": int, "error": str}
    """
    email_id = str(email["_id"])
    extraction = email.get(EXTRACTION_FIELD, {})

    if not extraction:
        return {"status": "skipped", "nodes": 0, "rels": 0, "error": "no_extraction"}

    stats = {"nodes": 0, "rels": 0}
    now = datetime.now().isoformat()

    try:
        # 1. Create Email node
        subject = (email.get("subject") or "")[:500]
        sent_at = email.get("received_time")
        if sent_at:
            sent_at = sent_at.isoformat() if hasattr(sent_at, 'isoformat') else str(sent_at)
        else:
            sent_at = ""
        sender = (email.get("sender") or "")[:200]

        conn.execute("""
            MERGE (e:Email {id: $id})
            SET e.subject = $subject,
                e.sent_at = $sent_at,
                e.sender = $sender,
                e.kuzu_synced_at = $synced
        """, {
            "id": email_id,
            "subject": subject,
            "sent_at": sent_at,
            "sender": sender,
            "synced": now
        })
        stats["nodes"] += 1

        # 2. Create/Update Thread
        thread_id = extract_thread_id(subject)
        if thread_id:
            conn.execute("""
                MERGE (t:Thread {id: $tid})
                ON CREATE SET t.topic = $topic, t.email_count = 1
                ON MATCH SET t.email_count = t.email_count + 1
            """, {"tid": thread_id, "topic": subject[:200]})
            stats["nodes"] += 1

            # Email -> Thread
            conn.execute("""
                MATCH (e:Email {id: $eid}), (t:Thread {id: $tid})
                MERGE (e)-[:BELONGS_TO]->(t)
            """, {"eid": email_id, "tid": thread_id})
            stats["rels"] += 1

        # 3. Process Identifiers and create BusinessEvent
        facts = extraction.get("facts", [])
        identifiers = [f for f in facts if f.get("type") == "identifier"]

        event_id = None
        primary_identifier = None

        for ident in identifiers:
            raw_val = ident.get("value", "")
            if not raw_val:
                continue

            norm_val = normalize_identifier(raw_val)
            id_type = classify_identifier_type(ident.get("key", ""))

            # Create Identifier node
            conn.execute("""
                MERGE (i:Identifier {val: $val})
                SET i.id_type = $type
            """, {"val": norm_val, "type": id_type})
            stats["nodes"] += 1

            # Use first identifier as event anchor
            if not primary_identifier:
                primary_identifier = norm_val
                event_id = f"evt_{norm_val}"

                # Create BusinessEvent
                event_type = infer_event_type(extraction.get("email_type", ""), facts)
                doc_date = extraction.get("document_date", "")
                summary = (extraction.get("summary") or "")[:500]

                # Extract amount if available
                amounts = [f for f in facts if f.get("type") == "amount"]
                amount_val, currency = 0.0, "USD"
                if amounts:
                    amount_val, currency = parse_amount(amounts[0].get("value", ""))

                conn.execute("""
                    MERGE (be:BusinessEvent {id: $eid})
                    ON CREATE SET
                        be.event_type = $etype,
                        be.event_date = $date,
                        be.summary = $summary,
                        be.amount = $amount,
                        be.currency = $currency,
                        be.created_at = $created
                    ON MATCH SET
                        be.summary = CASE WHEN be.summary = '' THEN $summary ELSE be.summary END
                """, {
                    "eid": event_id,
                    "etype": event_type,
                    "date": doc_date,
                    "summary": summary,
                    "amount": amount_val,
                    "currency": currency,
                    "created": now
                })
                stats["nodes"] += 1

            # BusinessEvent -> Identifier
            if event_id:
                conn.execute("""
                    MATCH (be:BusinessEvent {id: $eid}), (i:Identifier {val: $ival})
                    MERGE (be)-[:HAS_ID]->(i)
                """, {"eid": event_id, "ival": norm_val})
                stats["rels"] += 1

        # 4. Email -> BusinessEvent (EVIDENCES)
        if event_id:
            conn.execute("""
                MATCH (e:Email {id: $email_id}), (be:BusinessEvent {id: $event_id})
                MERGE (e)-[:EVIDENCES {confidence: 0.9, extracted_at: $now}]->(be)
            """, {"email_id": email_id, "event_id": event_id, "now": now})
            stats["rels"] += 1

        # 5. Process Companies
        companies = extraction.get("companies", [])
        for company_raw in companies:
            if not company_raw:
                continue

            normalized = normalize_company_name(company_raw)
            if not normalized:
                continue

            # Use normalized name as ID
            company_id = normalized.replace(" ", "_")[:100]

            conn.execute("""
                MERGE (c:Company {id: $cid})
                ON CREATE SET
                    c.original_name = $raw,
                    c.normalized_name = $norm
                ON MATCH SET
                    c.original_name = CASE WHEN c.original_name = '' THEN $raw ELSE c.original_name END
            """, {"cid": company_id, "raw": company_raw[:200], "norm": normalized})
            stats["nodes"] += 1

            # BusinessEvent -> Company (INVOLVES)
            if event_id:
                conn.execute("""
                    MATCH (be:BusinessEvent {id: $eid}), (c:Company {id: $cid})
                    MERGE (be)-[:INVOLVES {role: 'participant'}]->(c)
                """, {"eid": event_id, "cid": company_id})
                stats["rels"] += 1

        # 6. Process Persons
        persons = extraction.get("persons", [])
        for person_raw in persons:
            if not person_raw:
                continue

            person_id = person_raw.strip().upper().replace(" ", "_")[:100]

            conn.execute("""
                MERGE (p:Person {id: $pid})
                ON CREATE SET p.name = $name
            """, {"pid": person_id, "name": person_raw[:200]})
            stats["nodes"] += 1

        # 7. Process Products
        products = extraction.get("products", [])
        for product_raw in products:
            if not product_raw:
                continue

            product_id = product_raw.strip().upper().replace(" ", "_")[:100]

            conn.execute("""
                MERGE (pr:Product {id: $prid})
                ON CREATE SET pr.name = $name
            """, {"prid": product_id, "name": product_raw[:200]})
            stats["nodes"] += 1

            # BusinessEvent -> Product (CONCERNS)
            if event_id:
                conn.execute("""
                    MATCH (be:BusinessEvent {id: $eid}), (pr:Product {id: $prid})
                    MERGE (be)-[:CONCERNS]->(pr)
                """, {"eid": event_id, "prid": product_id})
                stats["rels"] += 1

        return {"status": "success", "nodes": stats["nodes"], "rels": stats["rels"], "error": None}

    except Exception as e:
        return {"status": "error", "nodes": stats["nodes"], "rels": stats["rels"], "error": str(e)[:200]}


def mark_synced(mongo_db, email_id: str):
    """Mark email as synced in MongoDB"""
    from bson import ObjectId
    mongo_db.emails.update_one(
        {"_id": ObjectId(email_id)},
        {"$set": {"kuzu_synced_at": datetime.now()}}
    )


def run_etl(limit: Optional[int] = None, reset: bool = False):
    """
    Main ETL runner
    """
    print("=" * 60)
    print("🚀 KùzuDB ETL Pipeline")
    print("=" * 60)

    # Initialize database
    if reset:
        init_database(reset=True)
    else:
        # Ensure schema exists
        init_database(reset=False)

    # Get connection
    db, conn = get_connection()

    # Connect to MongoDB
    mongo_client = pymongo.MongoClient(MONGO_URI)
    mongo_db = mongo_client[MONGO_DB]

    # Get unsynced emails
    print(f"\n📧 Fetching unsynced emails...")
    emails = get_unsynced_emails(mongo_db, limit)
    print(f"   Found: {len(emails)} emails to process")

    if not emails:
        print("\n✅ All emails already synced!")
        return

    # Process
    success, errors, skipped = 0, 0, 0
    total_nodes, total_rels = 0, 0
    start_time = datetime.now()

    for i, email in enumerate(emails):
        email_id = str(email["_id"])
        subject = (email.get("subject") or "")[:40]

        # Progress report every 50
        if (i + 1) % 50 == 0:
            elapsed = (datetime.now() - start_time).total_seconds()
            rate = (i + 1) / elapsed * 60 if elapsed > 0 else 0
            print(f"\n📊 Progress: {i+1}/{len(emails)} | ✅{success} ❌{errors} ⏭️{skipped} | {rate:.1f}/min")

        # ETL
        result = etl_single_email(email, conn)

        if result["status"] == "success":
            mark_synced(mongo_db, email_id)
            success += 1
            total_nodes += result["nodes"]
            total_rels += result["rels"]
            if (i + 1) <= 10 or (i + 1) % 20 == 0:
                print(f"  [{i+1}] ✅ {subject}... (+{result['nodes']}N, +{result['rels']}R)")
        elif result["status"] == "skipped":
            skipped += 1
        else:
            errors += 1
            print(f"  [{i+1}] ❌ {subject}... Error: {result['error'][:50]}")

    # Final stats
    elapsed = (datetime.now() - start_time).total_seconds()
    print(f"\n{'='*60}")
    print("📊 ETL Complete!")
    print(f"{'='*60}")
    print(f"✅ Success: {success}")
    print(f"❌ Errors:  {errors}")
    print(f"⏭️  Skipped: {skipped}")
    print(f"📦 Nodes:   {total_nodes}")
    print(f"🔗 Rels:    {total_rels}")
    print(f"⏱️  Time:    {elapsed:.1f}s")

    # Quick verification
    print(f"\n{'='*60}")
    print("🔍 Graph Stats")
    print(f"{'='*60}")

    queries = [
        ("BusinessEvent", "MATCH (n:BusinessEvent) RETURN count(n)"),
        ("Email", "MATCH (n:Email) RETURN count(n)"),
        ("Company", "MATCH (n:Company) RETURN count(n)"),
        ("Identifier", "MATCH (n:Identifier) RETURN count(n)"),
        ("Thread", "MATCH (n:Thread) RETURN count(n)"),
        ("EVIDENCES", "MATCH ()-[r:EVIDENCES]->() RETURN count(r)"),
        ("INVOLVES", "MATCH ()-[r:INVOLVES]->() RETURN count(r)"),
        ("HAS_ID", "MATCH ()-[r:HAS_ID]->() RETURN count(r)"),
    ]

    for name, query in queries:
        try:
            result = conn.execute(query)
            count = result.get_next()[0]
            print(f"  {name}: {count}")
        except Exception as e:
            print(f"  {name}: Error - {e}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, help="Limit number of emails to process")
    parser.add_argument("--reset", action="store_true", help="Reset database and reprocess")
    args = parser.parse_args()

    run_etl(limit=args.limit, reset=args.reset)
