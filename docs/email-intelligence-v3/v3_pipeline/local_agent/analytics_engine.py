#!/usr/bin/env python3
"""
Vulcan Analytics Engine
KùzuDB query wrapper for Local Agent
"""
import kuzu
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from pathlib import Path


@dataclass
class QueryResult:
    success: bool
    data: Any
    error: Optional[str] = None


class VulcanAnalytics:
    """Local-first analytics engine for KùzuDB"""

    def __init__(self, db_path: str = None, read_only: bool = True):
        if db_path is None:
            db_path = "/home/xinyue/vulcan_data/kuzu_data/email_graph"
        self.db = kuzu.Database(db_path, read_only=read_only)
        self.conn = kuzu.Connection(self.db)

    def _execute(self, query: str, params: dict = None) -> QueryResult:
        """Execute query with error handling"""
        try:
            result = self.conn.execute(query, params or {})
            rows = []
            while result.has_next():
                rows.append(result.get_next())
            return QueryResult(success=True, data=rows)
        except Exception as e:
            return QueryResult(success=False, data=None, error=str(e))

    # ==========================================
    # Tool 1: Company 360 View
    # ==========================================
    def get_company_360(self, company_name: str) -> Dict:
        """
        Get comprehensive company profile including:
        - Basic info and name variants
        - Related business events
        - Financial summary (total amounts)
        - Connected entities
        """
        name_upper = company_name.strip().upper()

        # 1. Find company (fuzzy match)
        result = self._execute("""
            MATCH (c:Company)
            WHERE c.canonical_name CONTAINS $name
               OR c.original_name CONTAINS $name
               OR upper(c.id) CONTAINS $name
            RETURN c.id, c.canonical_name, c.original_name, c.match_type
            LIMIT 5
        """, {"name": name_upper})

        if not result.success or not result.data:
            return {"error": f"Company '{company_name}' not found", "suggestions": []}

        companies = []
        for row in result.data:
            company_id = row[0]

            # Get related events
            events_result = self._execute("""
                MATCH (be:BusinessEvent)-[:INVOLVES]->(c:Company {id: $cid})
                RETURN be.id, be.event_type, be.event_date, be.summary, be.amount, be.currency
                ORDER BY be.event_date DESC
                LIMIT 10
            """, {"cid": company_id})

            events = []
            total_amount = 0.0
            for e in (events_result.data or []):
                events.append({
                    "event_id": e[0],
                    "type": e[1],
                    "date": e[2],
                    "summary": e[3][:100] if e[3] else "",
                    "amount": e[4],
                    "currency": e[5]
                })
                if e[4]:
                    total_amount += float(e[4])

            # Get connected companies (via shared events)
            partners_result = self._execute("""
                MATCH (c:Company {id: $cid})<-[:INVOLVES]-(be:BusinessEvent)-[:INVOLVES]->(other:Company)
                WHERE other.id <> $cid
                RETURN other.canonical_name, count(be) as shared_events
                ORDER BY shared_events DESC
                LIMIT 5
            """, {"cid": company_id})

            partners = [{"name": p[0], "shared_events": p[1]} for p in (partners_result.data or [])]

            companies.append({
                "id": company_id,
                "canonical_name": row[1],
                "original_name": row[2],
                "match_type": row[3],
                "events_count": len(events),
                "recent_events": events[:5],
                "total_amount": total_amount,
                "business_partners": partners
            })

        return {
            "query": company_name,
            "matches": len(companies),
            "companies": companies
        }

    # ==========================================
    # Tool 2: Trace Identifier
    # ==========================================
    def trace_identifier(self, identifier: str) -> Dict:
        """
        Trace an invoice/PO/tracking number to find:
        - Related business events
        - Source emails
        - Involved companies
        """
        # Normalize identifier
        norm_id = identifier.strip().upper().replace("-", "").replace("/", "").replace(" ", "")

        # Find identifier
        result = self._execute("""
            MATCH (i:Identifier)
            WHERE i.val CONTAINS $id
            RETURN i.val, i.id_type
            LIMIT 5
        """, {"id": norm_id})

        if not result.success or not result.data:
            return {"error": f"Identifier '{identifier}' not found"}

        traces = []
        for row in result.data:
            id_val = row[0]
            id_type = row[1]

            # Get linked events
            events_result = self._execute("""
                MATCH (i:Identifier {val: $val})<-[:HAS_ID]-(be:BusinessEvent)
                OPTIONAL MATCH (be)-[:INVOLVES]->(c:Company)
                RETURN be.id, be.event_type, be.event_date, be.summary,
                       collect(DISTINCT c.canonical_name) as companies
            """, {"val": id_val})

            events = []
            for e in (events_result.data or []):
                events.append({
                    "event_id": e[0],
                    "type": e[1],
                    "date": e[2],
                    "summary": e[3][:150] if e[3] else "",
                    "companies": e[4][:5] if e[4] else []
                })

            # Get source emails
            emails_result = self._execute("""
                MATCH (i:Identifier {val: $val})<-[:HAS_ID]-(be:BusinessEvent)<-[:EVIDENCES]-(e:Email)
                RETURN e.id, e.subject, e.sender, e.sent_at
                LIMIT 5
            """, {"val": id_val})

            emails = []
            for em in (emails_result.data or []):
                emails.append({
                    "email_id": em[0],
                    "subject": em[1][:100] if em[1] else "",
                    "sender": em[2],
                    "sent_at": em[3]
                })

            traces.append({
                "identifier": id_val,
                "type": id_type,
                "events": events,
                "source_emails": emails
            })

        return {
            "query": identifier,
            "matches": len(traces),
            "traces": traces
        }

    # ==========================================
    # Tool 3: Search Events by Date Range
    # ==========================================
    def search_events(self,
                      event_type: Optional[str] = None,
                      company: Optional[str] = None,
                      start_date: Optional[str] = None,
                      end_date: Optional[str] = None,
                      limit: int = 20) -> Dict:
        """
        Search business events with filters
        """
        params = {"limit": limit}
        
        # Build query differently based on whether company filter is present
        if company:
            # When filtering by company, filter first then aggregate
            be_conditions = []
            if event_type:
                be_conditions.append("be.event_type = $etype")
                params["etype"] = event_type
            if start_date:
                be_conditions.append("be.event_date >= $start")
                params["start"] = start_date
            if end_date:
                be_conditions.append("be.event_date <= $end")
                params["end"] = end_date
                
            params["company"] = company.upper()
            be_where = " AND ".join(be_conditions) if be_conditions else "TRUE"
            
            query = f"""
                MATCH (be:BusinessEvent)-[:INVOLVES]->(c:Company)
                WHERE c.canonical_name CONTAINS $company AND {be_where}
                WITH be, collect(DISTINCT c.canonical_name) as companies
                RETURN be.id, be.event_type, be.event_date, be.summary, be.amount, be.currency, companies
                ORDER BY be.event_date DESC
                LIMIT $limit
            """
        else:
            # No company filter - use OPTIONAL MATCH
            conditions = []
            if event_type:
                conditions.append("be.event_type = $etype")
                params["etype"] = event_type
            if start_date:
                conditions.append("be.event_date >= $start")
                params["start"] = start_date
            if end_date:
                conditions.append("be.event_date <= $end")
                params["end"] = end_date
                
            where_clause = " AND ".join(conditions) if conditions else "TRUE"
            
            query = f"""
                MATCH (be:BusinessEvent)
                WHERE {where_clause}
                OPTIONAL MATCH (be)-[:INVOLVES]->(c:Company)
                WITH be, collect(DISTINCT c.canonical_name) as companies
                RETURN be.id, be.event_type, be.event_date, be.summary, be.amount, be.currency, companies
                ORDER BY be.event_date DESC
                LIMIT $limit
            """

        result = self._execute(query, params)

        if not result.success:
            return {"error": result.error}

        events = []
        for row in result.data:
            events.append({
                "event_id": row[0],
                "type": row[1],
                "date": row[2],
                "summary": row[3][:150] if row[3] else "",
                "amount": row[4],
                "currency": row[5],
                "companies": row[6][:3] if row[6] else []
            })

        return {
            "filters": {
                "event_type": event_type,
                "company": company,
                "start_date": start_date,
                "end_date": end_date
            },
            "total": len(events),
            "events": events
        }

    # ==========================================
    # Tool 4: Get Email Context
    # ==========================================
    def get_email_context(self, email_id: str) -> Dict:
        """
        Get full context of an email including thread and related events
        """
        result = self._execute("""
            MATCH (e:Email {id: $eid})
            OPTIONAL MATCH (e)-[:BELONGS_TO]->(t:Thread)
            OPTIONAL MATCH (e)-[:EVIDENCES]->(be:BusinessEvent)
            OPTIONAL MATCH (be)-[:INVOLVES]->(c:Company)
            OPTIONAL MATCH (be)-[:HAS_ID]->(i:Identifier)
            RETURN e.subject, e.sender, e.sent_at,
                   t.topic, t.email_count,
                   be.event_type, be.summary,
                   collect(DISTINCT c.canonical_name) as companies,
                   collect(DISTINCT {val: i.val, type: i.id_type}) as identifiers
        """, {"eid": email_id})

        if not result.success or not result.data:
            return {"error": f"Email '{email_id}' not found"}

        row = result.data[0]
        return {
            "email": {
                "id": email_id,
                "subject": row[0],
                "sender": row[1],
                "sent_at": row[2]
            },
            "thread": {
                "topic": row[3],
                "email_count": row[4]
            } if row[3] else None,
            "business_event": {
                "type": row[5],
                "summary": row[6][:200] if row[6] else None,
                "companies": row[7][:5] if row[7] else [],
                "identifiers": row[8][:5] if row[8] else []
            } if row[5] else None
        }

    # ==========================================
    # Tool 5: Graph Stats
    # ==========================================
    def get_graph_stats(self) -> Dict:
        """Get current graph database statistics"""
        stats = {}

        node_types = ["Email", "BusinessEvent", "Company", "Identifier", "Thread", "Person", "Product"]
        for nt in node_types:
            result = self._execute(f"MATCH (n:{nt}) RETURN count(n)")
            if result.success and result.data:
                stats[nt] = result.data[0][0]

        rel_types = ["EVIDENCES", "INVOLVES", "HAS_ID", "BELONGS_TO", "CONCERNS"]
        for rt in rel_types:
            result = self._execute(f"MATCH ()-[r:{rt}]->() RETURN count(r)")
            if result.success and result.data:
                stats[f"rel_{rt}"] = result.data[0][0]

        return {"graph_stats": stats}


# Quick test
if __name__ == "__main__":
    print("Testing VulcanAnalytics...")
    analytics = VulcanAnalytics()

    print("\n1. Graph Stats:")
    print(analytics.get_graph_stats())

    print("\n2. Company 360 (SpaceX):")
    result = analytics.get_company_360("SpaceX")
    print(f"  Matches: {result.get('matches', 0)}")

    print("\n3. Company 360 (DHL):")
    result = analytics.get_company_360("DHL")
    print(f"  Matches: {result.get('matches', 0)}")
