#!/usr/bin/env python3
"""
Entity Normalization Functions
Handles: Company names, Identifiers, Thread IDs
"""
import re
import hashlib
from typing import Optional


def normalize_company_name(raw: str) -> str:
    """
    Rule-driven company name normalization

    Examples:
        "Alpha Tech Co., Ltd." -> "ALPHA TECH"
        "DHL Express GmbH" -> "DHL EXPRESS"
        "ABC Corporation Inc." -> "ABC CORPORATION"
    """
    if not raw:
        return ""

    name = raw.strip().upper()

    # Remove common suffixes
    suffixes = [
        r'\s*(CO\.,?\s*LTD\.?)$',
        r'\s*(GMBH)$',
        r'\s*(INC\.?)$',
        r'\s*(LLC)$',
        r'\s*(PTE\.?\s*LTD\.?)$',
        r'\s*(LIMITED)$',
        r'\s*(CORPORATION)$',
        r'\s*(CORP\.?)$',
        r'\s*(AG)$',
        r'\s*(SA)$',
        r'\s*(SRL)$',
        r'\s*(BV)$',
        r'\s*(NV)$',
    ]
    for suffix in suffixes:
        name = re.sub(suffix, '', name, flags=re.IGNORECASE)

    # Remove extra whitespace
    name = ' '.join(name.split())

    return name.strip()


def normalize_identifier(raw: str) -> str:
    """
    Normalize identifier values

    Handles punctuation: -, ., /, spaces
    Examples:
        "INV-001" -> "INV001"
        "PO.2024.001" -> "PO2024001"
        "BL/123/456" -> "BL123456"
        "AWB 123-456-789" -> "AWB123456789"
    """
    if not raw:
        return ""

    # Convert to uppercase
    val = raw.strip().upper()

    # Remove common punctuation separators
    val = re.sub(r'[-./\s]+', '', val)

    return val


def classify_identifier_type(key: str) -> str:
    """
    Classify identifier type from key name

    Returns: 'invoice', 'po', 'tracking', 'container', 'hs_code', 'bl', 'other'
    """
    key_lower = key.lower()

    if any(x in key_lower for x in ['invoice', 'inv no', 'inv#', 'inv.']):
        return 'invoice'
    if any(x in key_lower for x in ['po', 'purchase order', 'order no']):
        return 'po'
    if any(x in key_lower for x in ['tracking', 'awb', 'waybill', 'shipment']):
        return 'tracking'
    if any(x in key_lower for x in ['container', 'cntr']):
        return 'container'
    if any(x in key_lower for x in ['hs code', 'hs no', 'hts']):
        return 'hs_code'
    if any(x in key_lower for x in ['bl', 'bill of lading', 'b/l']):
        return 'bl'
    if any(x in key_lower for x in ['reference', 'ref']):
        return 'reference'

    return 'other'


def extract_thread_id(subject: str) -> str:
    """
    Extract thread ID from email subject

    Logic:
    1. Remove Re:/Fwd: prefixes
    2. Try to find identifier pattern (e.g., HN125040209)
    3. Fall back to MD5 hash of cleaned subject
    """
    if not subject:
        return ""

    # Remove Re: Fwd: prefixes (multiple)
    clean = re.sub(
        r'^(Re:\s*|Fwd:\s*|FW:\s*|回复:\s*|转发:\s*)+',
        '',
        subject,
        flags=re.IGNORECASE
    )
    clean = clean.strip()

    # Try to extract identifier pattern
    # Common patterns: HN125040209, INV-2024-001, PO123456
    patterns = [
        r'[A-Z]{2,4}\d{6,}',           # HN125040209, INV202401
        r'[A-Z]{2,4}[-/]\d{4}[-/]\d+', # INV-2024-001
        r'PO\s*#?\s*\d+',              # PO #12345
    ]

    for pattern in patterns:
        match = re.search(pattern, clean, re.IGNORECASE)
        if match:
            return normalize_identifier(match.group(0))

    # Fall back to hash
    return hashlib.md5(clean.encode()).hexdigest()[:12]


def infer_event_type(email_type: str, facts: list = None) -> str:
    """
    Infer business event type from email classification and facts

    Returns: 'Shipment', 'Payment', 'Quotation', 'Order', 'Inquiry', 'Certificate', 'General'
    """
    if not email_type:
        email_type = ""

    et_lower = email_type.lower()

    # Direct mapping
    mapping = {
        'shipping': 'Shipment',
        'logistics': 'Shipment',
        'delivery': 'Shipment',
        'invoice': 'Payment',
        'payment': 'Payment',
        'quotation': 'Quotation',
        'quote': 'Quotation',
        'offer': 'Quotation',
        'order': 'Order',
        'purchase': 'Order',
        'inquiry': 'Inquiry',
        'enquiry': 'Inquiry',
        'certificate': 'Certificate',
        'certification': 'Certificate',
    }

    for key, val in mapping.items():
        if key in et_lower:
            return val

    # Try to infer from facts
    if facts:
        fact_types = set(f.get('type', '') for f in facts)
        fact_keys = ' '.join(f.get('key', '').lower() for f in facts)

        if 'invoice' in fact_keys or 'payment' in fact_keys:
            return 'Payment'
        if 'tracking' in fact_keys or 'awb' in fact_keys or 'bl' in fact_keys:
            return 'Shipment'
        if 'quotation' in fact_keys or 'price' in fact_keys:
            return 'Quotation'

    return 'General'


def parse_amount(value: str) -> tuple:
    """
    Parse amount string to (float, currency)

    Examples:
        "USD 5,000.00" -> (5000.0, "USD")
        "€1,234.56" -> (1234.56, "EUR")
        "¥10000" -> (10000.0, "CNY")
    """
    if not value:
        return 0.0, 'USD'

    # Currency symbol mapping
    symbol_map = {
        '$': 'USD',
        '€': 'EUR',
        '£': 'GBP',
        '¥': 'CNY',
        '₹': 'INR',
    }

    # Try pattern: CURRENCY AMOUNT
    match = re.search(r'([A-Z]{3})\s*([\d,]+\.?\d*)', value)
    if match:
        currency = match.group(1)
        amount = float(match.group(2).replace(',', ''))
        return amount, currency

    # Try pattern: SYMBOL AMOUNT
    for symbol, curr in symbol_map.items():
        if symbol in value:
            match = re.search(r'([\d,]+\.?\d*)', value)
            if match:
                amount = float(match.group(1).replace(',', ''))
                return amount, curr

    # Try just extracting number
    match = re.search(r'([\d,]+\.?\d*)', value)
    if match:
        amount = float(match.group(1).replace(',', ''))
        return amount, 'USD'

    return 0.0, 'USD'


# Self-test
if __name__ == "__main__":
    print("=== Company Name Normalization ===")
    tests = [
        "Alpha Tech Co., Ltd.",
        "DHL Express GmbH",
        "ABC Corporation Inc.",
        "Test Company Pte. Ltd.",
    ]
    for t in tests:
        print(f"  '{t}' -> '{normalize_company_name(t)}'")

    print("\n=== Identifier Normalization ===")
    tests = [
        "INV-001",
        "PO.2024.001",
        "BL/123/456",
        "AWB 123-456-789",
        "HN125040209",
    ]
    for t in tests:
        print(f"  '{t}' -> '{normalize_identifier(t)}'")

    print("\n=== Identifier Type Classification ===")
    tests = [
        "Invoice No",
        "PO Number",
        "Tracking #",
        "Container ID",
        "HS Code",
        "Reference",
    ]
    for t in tests:
        print(f"  '{t}' -> '{classify_identifier_type(t)}'")

    print("\n=== Amount Parsing ===")
    tests = [
        "USD 5,000.00",
        "€1,234.56",
        "¥10000",
        "$350.00",
    ]
    for t in tests:
        print(f"  '{t}' -> {parse_amount(t)}")
