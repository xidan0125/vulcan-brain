#!/usr/bin/env python3
"""
KùzuDB ETL Pipeline V2 - 使用 V2 EntityResolver
架构决策 Option A+: 只读继承 V2 知识库
"""
import kuzu
import pymongo
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import sys
import json
import re

# Identifier Blocklist
_blocklist = None
def get_blocklist() -> Dict:
    global _blocklist
    if _blocklist is None:
        bl_path = Path(__file__).parent / "data" / "identifier_blocklist.json"
        if bl_path.exists():
            with open(bl_path) as f:
                _blocklist = json.load(f)
                print(f"  Loaded blocklist: {len(_blocklist.get("blocked", []))} blocked IDs")
        else:
            _blocklist = {"blocked": [], "patterns": []}
    return _blocklist

def is_blocked(norm_val: str) -> Tuple[bool, str]:
    bl = get_blocklist()
    for item in bl.get("blocked", []):
        if item["value"].upper().replace(" ", "") == norm_val:
            return True, item.get("reason", "blocked")
    for pattern in bl.get("patterns", []):
        if re.match(pattern["regex"], norm_val):
            return True, pattern.get("reason", "pattern")
    return False, ""


# Add parent to path for utils import
sys.path.insert(0, str(Path(__file__).parent.parent))

from schema import init_database, get_connection
from utils.entity_resolver import get_resolver
from utils.name_normalizer import normalize_for_matching

MONGO_URI = "mongodb://localhost:27017"
MONGO_DB = "vulcan_brain"
EXTRACTION_FIELD = "v3_extraction_v312"

# Global resolver
_resolver = None

def get_entity_resolver():
    global _resolver
    if _resolver is None:
        _resolver = get_resolver()
    return _resolver


def get_unsynced_emails(mongo_db, limit: Optional[int] = None) -> List[Dict]:
    query = {
        EXTRACTION_FIELD: {"$exists": True},
        "$or": [{"kuzu_synced_at": {"$exists": False}}, {"kuzu_synced_at": None}]
    }
    cursor = mongo_db.emails.find(query)
    if limit:
        cursor = cursor.limit(limit)
    return list(cursor)


def normalize_identifier(raw: str) -> str:
    import re
    if not raw:
        return ""
    val = raw.strip().upper()
    val = re.sub(r'[-./\s]+', '', val)
    return val


def classify_identifier_type(key: str) -> str:
    key_lower = key.lower()
    if any(x in key_lower for x in ['invoice', 'inv no', 'inv#']):
        return 'invoice'
    if any(x in key_lower for x in ['po', 'purchase order', 'order no']):
        return 'po'
    if any(x in key_lower for x in ['tracking', 'awb', 'waybill', 'shipment']):
        return 'tracking'
    if any(x in key_lower for x in ['container', 'cntr']):
        return 'container'
    return 'other'


def extract_thread_id(subject: str) -> str:
    import re
    import hashlib
    if not subject:
        return ""
    clean = re.sub(r'^(Re:\s*|Fwd:\s*|FW:\s*|回复:\s*|转发:\s*)+', '', subject, flags=re.IGNORECASE).strip()
    patterns = [r'[A-Z]{2,4}\d{6,}', r'[A-Z]{2,4}[-/]\d{4}[-/]\d+', r'PO\s*#?\s*\d+']
    for pattern in patterns:
        match = re.search(pattern, clean, re.IGNORECASE)
        if match:
            return normalize_identifier(match.group(0))
    return hashlib.md5(clean.encode()).hexdigest()[:12]


def infer_event_type(email_type: str, facts: list = None) -> str:
    if not email_type:
        return 'General'
    et_lower = email_type.lower()
    mapping = {
        'shipping': 'Shipment', 'logistics': 'Shipment', 'delivery': 'Shipment',
        'invoice': 'Payment', 'payment': 'Payment',
        'quotation': 'Quotation', 'quote': 'Quotation',
        'order': 'Order', 'inquiry': 'Inquiry', 'certificate': 'Certificate',
    }
    for key, val in mapping.items():
        if key in et_lower:
            return val
    return 'General'


def parse_amount(value: str) -> tuple:
    import re
    if not value:
        return 0.0, 'USD'
    match = re.search(r'([A-Z]{3})\s*([\d,]+\.?\d*)', value)
    if match:
        return float(match.group(2).replace(',', '')), match.group(1)
    match = re.search(r'([\d,]+\.?\d*)', value)
    if match:
        return float(match.group(1).replace(',', '')), 'USD'
    return 0.0, 'USD'


def etl_single_email(email: Dict, conn: kuzu.Connection, resolver) -> Dict:
    email_id = str(email["_id"])
    extraction = email.get(EXTRACTION_FIELD, {})

    if not extraction:
        return {"status": "skipped", "nodes": 0, "rels": 0, "v2_matches": 0}

    stats = {"nodes": 0, "rels": 0, "v2_matches": 0}
    now = datetime.now().isoformat()

    try:
        # 1. Email node
        subject = (email.get("subject") or "")[:500]
        sent_at = email.get("received_time")
        sent_at = sent_at.isoformat() if hasattr(sent_at, 'isoformat') else str(sent_at) if sent_at else ""
        sender = (email.get("sender") or "")[:200]

        conn.execute("""
            MERGE (e:Email {id: $id})
            SET e.subject = $subject, e.sent_at = $sent_at, e.sender = $sender, e.kuzu_synced_at = $synced
        """, {"id": email_id, "subject": subject, "sent_at": sent_at, "sender": sender, "synced": now})
        stats["nodes"] += 1

        # 2. Thread
        thread_id = extract_thread_id(subject)
        if thread_id:
            conn.execute("""
                MERGE (t:Thread {id: $tid})
                ON CREATE SET t.topic = $topic, t.email_count = 1
                ON MATCH SET t.email_count = t.email_count + 1
            """, {"tid": thread_id, "topic": subject[:200]})
            stats["nodes"] += 1
            conn.execute("MATCH (e:Email {id: $eid}), (t:Thread {id: $tid}) MERGE (e)-[:BELONGS_TO]->(t)",
                        {"eid": email_id, "tid": thread_id})
            stats["rels"] += 1

        # 3. Identifiers & BusinessEvent
        facts = extraction.get("facts", [])
        identifiers = [f for f in facts if f.get("type") == "identifier"]
        event_id = None

        for i, ident in enumerate(identifiers):
            raw_val = ident.get("value", "")
            if not raw_val:
                continue
            norm_val = normalize_identifier(raw_val)
            id_type = classify_identifier_type(ident.get("key", ""))

            # Check blocklist
            blocked, reason = is_blocked(norm_val)
            if blocked:
                stats["blocked"] = stats.get("blocked", 0) + 1
                continue

            conn.execute("MERGE (i:Identifier {val: $val}) SET i.id_type = $type",
                        {"val": norm_val, "type": id_type})
            stats["nodes"] += 1

            if i == 0:  # First identifier = primary
                event_id = f"evt_{norm_val}"
                event_type = infer_event_type(extraction.get("email_type", ""), facts)
                amounts = [f for f in facts if f.get("type") == "amount"]
                amount_val, currency = parse_amount(amounts[0].get("value", "")) if amounts else (0.0, "USD")

                conn.execute("""
                    MERGE (be:BusinessEvent {id: $eid})
                    ON CREATE SET be.event_type = $etype, be.event_date = $date, be.summary = $summary,
                                  be.amount = $amount, be.currency = $currency, be.created_at = $created
                """, {
                    "eid": event_id, "etype": event_type,
                    "date": extraction.get("document_date", ""),
                    "summary": (extraction.get("summary") or "")[:500],
                    "amount": amount_val, "currency": currency, "created": now
                })
                stats["nodes"] += 1

            if event_id:
                conn.execute("MATCH (be:BusinessEvent {id: $eid}), (i:Identifier {val: $ival}) MERGE (be)-[:HAS_ID]->(i)",
                            {"eid": event_id, "ival": norm_val})
                stats["rels"] += 1

        # 4. Email -> BusinessEvent
        if event_id:
            conn.execute("""
                MATCH (e:Email {id: $email_id}), (be:BusinessEvent {id: $event_id})
                MERGE (e)-[:EVIDENCES {confidence: 0.9}]->(be)
            """, {"email_id": email_id, "event_id": event_id})
            stats["rels"] += 1

        # 5. Companies (使用 V2 EntityResolver!)
        companies = extraction.get("companies", [])
        for company_raw in companies:
            if not company_raw:
                continue
            
            # 🔑 核心：使用 V2 知识库解析
            resolved_name, match_type = resolver.resolve(company_raw)
            if not resolved_name:
                continue
            
            company_id = resolved_name.upper().replace(" ", "_")[:100]
            
            if match_type == "V2_MATCH":
                stats["v2_matches"] += 1

            conn.execute("""
                MERGE (c:Company {id: $cid})
                ON CREATE SET c.canonical_name = $canonical, c.original_name = $raw, c.match_type = $mtype
            """, {"cid": company_id, "canonical": resolved_name, "raw": company_raw[:200], "mtype": match_type})
            stats["nodes"] += 1

            if event_id:
                conn.execute("MATCH (be:BusinessEvent {id: $eid}), (c:Company {id: $cid}) MERGE (be)-[:INVOLVES]->(c)",
                            {"eid": event_id, "cid": company_id})
                stats["rels"] += 1

        # 6. Persons
        for person_raw in extraction.get("persons", []):
            if not person_raw:
                continue
            person_id = person_raw.strip().upper().replace(" ", "_")[:100]
            conn.execute("MERGE (p:Person {id: $pid}) ON CREATE SET p.name = $name",
                        {"pid": person_id, "name": person_raw[:200]})
            stats["nodes"] += 1

        # 7. Products
        for product_raw in extraction.get("products", []):
            if not product_raw:
                continue
            product_id = product_raw.strip().upper().replace(" ", "_")[:100]
            conn.execute("MERGE (pr:Product {id: $prid}) ON CREATE SET pr.name = $name",
                        {"prid": product_id, "name": product_raw[:200]})
            stats["nodes"] += 1
            if event_id:
                conn.execute("MATCH (be:BusinessEvent {id: $eid}), (pr:Product {id: $prid}) MERGE (be)-[:CONCERNS]->(pr)",
                            {"eid": event_id, "prid": product_id})
                stats["rels"] += 1

        return {"status": "success", **stats}

    except Exception as e:
        return {"status": "error", "nodes": stats["nodes"], "rels": stats["rels"], "v2_matches": 0, "error": str(e)[:200]}


def mark_synced(mongo_db, email_id: str):
    from bson import ObjectId
    mongo_db.emails.update_one({"_id": ObjectId(email_id)}, {"$set": {"kuzu_synced_at": datetime.now()}})


def run_etl(limit: Optional[int] = None, reset: bool = False):
    print("=" * 60)
    print("🚀 KùzuDB ETL V2 (V2 Knowledge Inheritance)")
    print("=" * 60)

    # Load V2 resolver
    resolver = get_entity_resolver()
    stats = resolver.stats()
    print(f"📖 V2 Knowledge: {stats['total_mappings']} mappings, {stats['total_canonicals']} canonicals")

    # Init DB
    if reset:
        init_database(reset=True)
    else:
        init_database(reset=False)

    db, conn = get_connection()
    mongo_client = pymongo.MongoClient(MONGO_URI)
    mongo_db = mongo_client[MONGO_DB]

    emails = get_unsynced_emails(mongo_db, limit)
    print(f"\n📧 Found {len(emails)} emails to process")

    if not emails:
        print("✅ All synced!")
        return

    success, errors, v2_total = 0, 0, 0
    start = datetime.now()

    for i, email in enumerate(emails):
        result = etl_single_email(email, conn, resolver)
        
        if result["status"] == "success":
            mark_synced(mongo_db, str(email["_id"]))
            success += 1
            v2_total += result.get("v2_matches", 0)
            if (i + 1) <= 5 or (i + 1) % 20 == 0:
                print(f"  [{i+1}] ✅ +{result['nodes']}N +{result['rels']}R (V2:{result.get('v2_matches',0)})")
        else:
            errors += 1

        if (i + 1) % 50 == 0:
            print(f"\n📊 Progress: {i+1}/{len(emails)} | ✅{success} ❌{errors} | V2 matches: {v2_total}")

    elapsed = (datetime.now() - start).total_seconds()
    print(f"\n{'='*60}")
    print(f"✅ Done! {success} success, {errors} errors in {elapsed:.1f}s")
    print(f"🔑 V2 Knowledge matches: {v2_total}")
    print(f"{'='*60}")

    # Stats
    for name, q in [("Company", "MATCH (n:Company) RETURN count(n)"),
                    ("  V2_MATCH", "MATCH (n:Company) WHERE n.match_type = 'V2_MATCH' RETURN count(n)"),
                    ("BusinessEvent", "MATCH (n:BusinessEvent) RETURN count(n)")]:
        try:
            r = conn.execute(q)
            print(f"  {name}: {r.get_next()[0]}")
        except:
            pass


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int)
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()
    run_etl(limit=args.limit, reset=args.reset)
