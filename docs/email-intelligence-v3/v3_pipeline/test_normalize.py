#!/usr/bin/env python3
import re

def normalize_key(text: str) -> str:
    if not text:
        return ""
    text = text.lower().strip()
    text = re.sub(r'[.,;:!?\-_()]+', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    for suffix in ['pte ltd', 'pte', 'ltd', 'inc', 'corp', 'co', 'llc', 'gmbh']:
        text = re.sub(rf'\b{suffix}\b', '', text)
    text = re.sub(r'\s+', '_', text.strip())
    return text.upper() if text else ""

tests = [
    "VSG",
    "Vulcan Shield Global Pte.",
    "Vulcan Shield",
    "vulcanshield",
    "Barry",
    "Barry Claypool",
    "David",
    "David Kneale",
    "Microsoft",
    "Microsoft Teams"
]

for t in tests:
    print(f"{t:35} -> {normalize_key(t)}")
