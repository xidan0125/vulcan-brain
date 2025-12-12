"""
Master Extraction Prompt - Email Intelligence V2.0
===================================================

This prompt is designed for the Master Extractor to analyze business emails
and extract structured intelligence in a single pass.
"""

MASTER_EXTRACTION_PROMPT = '''You are an expert B2B business email analyst for a precision supply chain company.
Analyze the following email and extract structured intelligence.

CONTEXT:
- We supply precision parts to aerospace (SpaceX), automotive, and electronics industries
- Compliance (ITAR, EAR, W-9) is critical
- Email languages: English, Japanese, Chinese

EMAIL:
Subject: {subject}
From: {sender_name} <{sender_email}>
To: {recipients}
Date: {date}
Body:
{body}

---
Extract the following in strict JSON format:

{{
  "intent": "ORDER|INQUIRY|QUOTE|SHIPPING|COMPLIANCE|INVOICE|SUPPORT|MEETING|OTHER",
  "sub_intents": ["string array of specific purposes"],
  "urgency": "HIGH|MEDIUM|LOW",
  "sentiment": "POSITIVE|NEUTRAL|NEGATIVE",

  "mentioned_entities": [
    {{
      "type": "COMPANY|PERSON|PRODUCT|DOCUMENT|ORDER_NUMBER",
      "name": "exact name as mentioned",
      "normalized_name": "standardized name",
      "role": "requester|responder|mentioned|cc",
      "context": "brief context of mention"
    }}
  ],

  "action_items": [
    {{
      "action": "specific action required",
      "assignee_hint": "who should do this",
      "deadline_hint": "when mentioned"
    }}
  ],

  "topics": ["array of topics"],
  "compliance_flags": ["W9|EXPORT|CUSTOMS|ITAR|EAR|NONE"],

  "financial": {{
    "has_amount": true,
    "currency": "USD|JPY|CNY|EUR|null",
    "amounts": [12345],
    "payment_terms": "NET30|null"
  }},

  "summary": "One concise sentence summary",
  "key_sentences": ["up to 3 most important sentences"]
}}

RULES:
1. For Japanese emails, do NOT extract honorifics (様, 御中) as person names
2. Normalize company names (e.g., "Space X" -> "SpaceX")
3. If urgency words (ASAP, urgent, immediately) appear, set urgency to HIGH
4. Always extract order/PO numbers in DOCUMENT or ORDER_NUMBER type
5. If no action items found, return empty array
6. If no financial info, set has_amount to false and other fields to null

Return ONLY valid JSON, no explanation.'''


def format_extraction_prompt(email: dict) -> str:
    """Format the extraction prompt with email data."""
    sender = email.get("from", {})
    recipients = email.get("to", [])
    
    return MASTER_EXTRACTION_PROMPT.format(
        subject=email.get("subject", "(no subject)"),
        sender_name=sender.get("name", ""),
        sender_email=sender.get("email", ""),
        recipients=", ".join([r.get("email", "") for r in recipients[:5]]),
        date=str(email.get("received_at", "")),
        body=(email.get("body_clean") or email.get("body", ""))[:3000]
    )
