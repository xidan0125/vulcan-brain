#!/usr/bin/env python3
import pymongo
import kuzu
from datetime import datetime
import sys
sys.path.insert(0, "..")

from schema import get_connection
from etl_pipeline_v2 import etl_single_email, get_entity_resolver

client = pymongo.MongoClient("mongodb://localhost:27017")
mongo_db = client["vulcan_brain"]
db, conn = get_connection()
resolver = get_entity_resolver()

# 获取5封失败的邮件
emails = list(mongo_db.emails.find({
    "v3_extraction_v312": {"$exists": True},
    "kuzu_synced_at": {"$exists": False}
}).limit(5))

print(f"Testing {len(emails)} unsynced emails...")

for email in emails:
    subj = email.get("subject", "")[:40]
    print(f"\n--- {subj} ---")
    result = etl_single_email(email, conn, resolver)
    print(f"Status: {result['status']}")
    if result.get("error"):
        print(f"Error: {result['error']}")
