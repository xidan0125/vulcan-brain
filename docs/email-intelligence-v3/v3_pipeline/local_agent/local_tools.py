#!/usr/bin/env python3
"""
Local Tools for Vulcan Agent
No HTTP, No SSE - just pure Python function calls
"""
import json
from typing import Dict, Any
from analytics_engine import VulcanAnalytics

# Singleton analytics instance
_analytics = None

def get_analytics() -> VulcanAnalytics:
    global _analytics
    if _analytics is None:
        _analytics = VulcanAnalytics(read_only=True)
        print("📊 VulcanAnalytics initialized (read-only mode)")
    return _analytics


# ==========================================
# Tool Schema (OpenAI Function Calling Format)
# ==========================================

TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "get_company_360",
            "description": "Get comprehensive company profile including name variants, recent business events, financial summary, and business partners. Use this when user asks about a specific company.",
            "parameters": {
                "type": "object",
                "properties": {
                    "company_name": {
                        "type": "string",
                        "description": "Company name to search (supports partial match)"
                    }
                },
                "required": ["company_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "trace_identifier",
            "description": "Trace an invoice number, PO number, tracking number, or any business identifier to find related events and source emails. Use this when user provides a specific number/code.",
            "parameters": {
                "type": "object",
                "properties": {
                    "identifier": {
                        "type": "string",
                        "description": "The identifier to trace (invoice#, PO#, tracking#, etc.)"
                    }
                },
                "required": ["identifier"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_events",
            "description": "Search business events with filters like event type, company, or date range. Use this for broad queries like 'recent payments' or 'shipments to Company X'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "event_type": {
                        "type": "string",
                        "description": "Filter by event type: Payment, Shipment, Order, Quotation, Inquiry, General",
                        "enum": ["Payment", "Shipment", "Order", "Quotation", "Inquiry", "General"]
                    },
                    "company": {
                        "type": "string",
                        "description": "Filter by company name (partial match)"
                    },
                    "start_date": {
                        "type": "string",
                        "description": "Start date in YYYY-MM-DD format"
                    },
                    "end_date": {
                        "type": "string",
                        "description": "End date in YYYY-MM-DD format"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results to return (default 20)",
                        "default": 20
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_email_context",
            "description": "Get full context of an email including thread history and related business events. Use when user wants details about a specific email.",
            "parameters": {
                "type": "object",
                "properties": {
                    "email_id": {
                        "type": "string",
                        "description": "The email ID (MongoDB ObjectId)"
                    }
                },
                "required": ["email_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_graph_stats",
            "description": "Get current statistics of the knowledge graph - node counts, relationship counts. Use when user asks about database status or data coverage.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    }
]


# ==========================================
# Tool Execution
# ==========================================

def execute_tool(tool_name: str, args: Dict[str, Any]) -> Dict:
    """
    Execute a tool by name with given arguments.
    Returns the result as a dictionary.
    """
    analytics = get_analytics()

    if tool_name == "get_company_360":
        return analytics.get_company_360(args["company_name"])

    elif tool_name == "trace_identifier":
        return analytics.trace_identifier(args["identifier"])

    elif tool_name == "search_events":
        return analytics.search_events(
            event_type=args.get("event_type"),
            company=args.get("company"),
            start_date=args.get("start_date"),
            end_date=args.get("end_date"),
            limit=args.get("limit", 20)
        )

    elif tool_name == "get_email_context":
        return analytics.get_email_context(args["email_id"])

    elif tool_name == "get_graph_stats":
        return analytics.get_graph_stats()

    else:
        return {"error": f"Unknown tool: {tool_name}"}


# ==========================================
# Helper: Format tool result for display
# ==========================================

def format_tool_result(result: Dict, max_length: int = 500) -> str:
    """Format tool result for human-readable display"""
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if len(text) > max_length:
        return text[:max_length] + "..."
    return text


# Quick test
if __name__ == "__main__":
    print("Testing Local Tools...")
    print(f"\nAvailable tools: {[t['function']['name'] for t in TOOLS_SCHEMA]}")

    print("\n1. get_graph_stats:")
    result = execute_tool("get_graph_stats", {})
    print(format_tool_result(result))

    print("\n2. get_company_360 (Vulcan):")
    result = execute_tool("get_company_360", {"company_name": "Vulcan"})
    print(format_tool_result(result))

    print("\n3. search_events (Payment):")
    result = execute_tool("search_events", {"event_type": "Payment", "limit": 3})
    print(format_tool_result(result))
