#!/usr/bin/env python3
"""
Entity Normalization with V2 Library + LLM Dictionary
Implements 3-tier matching: Dictionary → V2 Lookup → Rule-based
"""
import re
import hashlib
import json
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass
import pymongo
from functools import lru_cache

# ============================================
# LLM Entity Dictionary (from clustering)
# ============================================

_llm_dictionary: Optional[Dict[str, str]] = None

def get_llm_dictionary() -> Dict[str, str]:
    """Load LLM-generated entity dictionary"""
    global _llm_dictionary
    if _llm_dictionary is None:
        dict_path = Path(__file__).parent / "data" / "entity_dictionary.json"
        if dict_path.exists():
            with open(dict_path) as f:
                data = json.load(f)
                _llm_dictionary = data.get("dictionary", {})
                print(f"📖 Loaded LLM dictionary: {len(_llm_dictionary)} mappings")
        else:
            _llm_dictionary = {}
            print("⚠️ No LLM dictionary found")
    return _llm_dictionary


# ============================================
# V2 Entity Library Client
# ============================================

class V2EntityLibrary:
    def __init__(self, mongo_uri: str = "mongodb://localhost:27017", db_name: str = "vulcan_brain"):
        self.client = pymongo.MongoClient(mongo_uri)
        self.db = self.client[db_name]
        self.entities = self.db.entities_v3
        self._name_index: Dict[str, Dict] = {}
        self._alias_index: Dict[str, Dict] = {}
        self._loaded = False

    def load_index(self, entity_type: str = "company"):
        if self._loaded:
            return
        print(f"📚 Loading V2 entity library ({entity_type})...")
        count = 0
        for doc in self.entities.find({"type": entity_type}):
            entity = {
                "entity_id": doc.get("entity_id"),
                "canonical_name": doc.get("canonical_name"),
                "normalized_name": doc.get("normalized_name", "").upper(),
                "aliases": [a.upper() for a in doc.get("aliases", [])],
                "mention_count": doc.get("mention_count", 0)
            }
            norm_name = entity["normalized_name"]
            if norm_name:
                self._name_index[norm_name] = entity
            for alias in entity["aliases"]:
                if alias:
                    self._alias_index[alias] = entity
            count += 1
        self._loaded = True
        print(f"   Loaded {count} entities, {len(self._name_index)} names, {len(self._alias_index)} aliases")

    def lookup(self, name: str) -> Optional[Dict]:
        if not self._loaded:
            self.load_index()
        name_upper = name.strip().upper()
        if name_upper in self._name_index:
            return self._name_index[name_upper]
        if name_upper in self._alias_index:
            return self._alias_index[name_upper]
        normalized = _normalize_company_name_rules(name)
        if normalized in self._name_index:
            return self._name_index[normalized]
        return None


_v2_library: Optional[V2EntityLibrary] = None

def get_v2_library() -> V2EntityLibrary:
    global _v2_library
    if _v2_library is None:
        _v2_library = V2EntityLibrary()
    return _v2_library


# ============================================
# Rule-based Normalization
# ============================================

def _normalize_company_name_rules(raw: str) -> str:
    if not raw:
        return ""
    name = raw.strip().upper()
    suffixes = [
        r'\s*(CO\.,?\s*LTD\.?)$', r'\s*(GMBH)$', r'\s*(INC\.?)$',
        r'\s*(LLC)$', r'\s*(PTE\.?\s*LTD\.?)$', r'\s*(LIMITED)$',
        r'\s*(CORPORATION)$', r'\s*(CORP\.?)$', r'\s*(AG)$',
        r'\s*(SA)$', r'\s*(SRL)$', r'\s*(BV)$', r'\s*(NV)$',
        r'\s*(S\.?A\.?)$', r'\s*(株式会社)$', r'\s*(有限公司)$',
    ]
    for suffix in suffixes:
        name = re.sub(suffix, '', name, flags=re.IGNORECASE)
    name = ' '.join(name.split())
    return name.strip()


# ============================================
# Main Normalization Function
# ============================================

@dataclass
class NormalizationResult:
    original: str
    normalized_name: str
    v2_entity_id: Optional[str]
    v2_canonical_name: Optional[str]
    match_type: str  # "llm_dict", "exact", "alias", "rule_only"
    confidence: float


def normalize_company(raw: str, use_v2: bool = True) -> NormalizationResult:
    """
    三层公司名称规范化:
    Layer 1: LLM Dictionary (最高优先级)
    Layer 2: V2 实体库查找
    Layer 3: 规则清洗
    """
    if not raw:
        return NormalizationResult("", "", None, None, "empty", 0.0)

    # Layer 1: LLM Dictionary
    llm_dict = get_llm_dictionary()
    if raw in llm_dict:
        canonical = llm_dict[raw]
        return NormalizationResult(
            original=raw,
            normalized_name=canonical.upper(),
            v2_entity_id=None,
            v2_canonical_name=canonical,
            match_type="llm_dict",
            confidence=0.95
        )

    # Layer 2: V2 lookup
    if use_v2:
        v2 = get_v2_library()
        entity = v2.lookup(raw)
        if entity:
            return NormalizationResult(
                original=raw,
                normalized_name=entity["normalized_name"],
                v2_entity_id=entity["entity_id"],
                v2_canonical_name=entity["canonical_name"],
                match_type="exact" if raw.upper() == entity["normalized_name"] else "alias",
                confidence=1.0
            )

    # Layer 3: Rule-based normalization
    normalized = _normalize_company_name_rules(raw)
    return NormalizationResult(
        original=raw,
        normalized_name=normalized,
        v2_entity_id=None,
        v2_canonical_name=None,
        match_type="rule_only",
        confidence=0.5
    )


# ============================================
# Other Normalization Functions
# ============================================

def normalize_identifier(raw: str) -> str:
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
    if any(x in key_lower for x in ['hs code', 'hs no', 'hts']):
        return 'hs_code'
    if any(x in key_lower for x in ['bl', 'bill of lading', 'b/l']):
        return 'bl'
    return 'other'


def extract_thread_id(subject: str) -> str:
    if not subject:
        return ""
    clean = re.sub(r'^(Re:\s*|Fwd:\s*|FW:\s*|回复:\s*|转发:\s*)+', '', subject, flags=re.IGNORECASE)
    clean = clean.strip()
    patterns = [r'[A-Z]{2,4}\d{6,}', r'[A-Z]{2,4}[-/]\d{4}[-/]\d+', r'PO\s*#?\s*\d+']
    for pattern in patterns:
        match = re.search(pattern, clean, re.IGNORECASE)
        if match:
            return normalize_identifier(match.group(0))
    return hashlib.md5(clean.encode()).hexdigest()[:12]


def infer_event_type(email_type: str, facts: list = None) -> str:
    if not email_type:
        email_type = ""
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


def parse_amount(value: str) -> Tuple[float, str]:
    if not value:
        return 0.0, 'USD'
    symbol_map = {'$': 'USD', '€': 'EUR', '£': 'GBP', '¥': 'CNY'}
    match = re.search(r'([A-Z]{3})\s*([\d,]+\.?\d*)', value)
    if match:
        return float(match.group(2).replace(',', '')), match.group(1)
    for symbol, curr in symbol_map.items():
        if symbol in value:
            match = re.search(r'([\d,]+\.?\d*)', value)
            if match:
                return float(match.group(1).replace(',', '')), curr
    match = re.search(r'([\d,]+\.?\d*)', value)
    if match:
        return float(match.group(1).replace(',', '')), 'USD'
    return 0.0, 'USD'


if __name__ == "__main__":
    print("=" * 60)
    print("🔬 V2 + LLM Dictionary Test")
    print("=" * 60)
    
    test_companies = [
        "Space X",        # Should resolve via LLM dict
        "SpaceX",         # Direct match
        "Microsoft",      # LLM dict -> Microsoft Corporation
        "DHL",            # V2 lookup
        "Unknown XYZ",    # Rule-only
    ]
    
    print("\n📊 Results:")
    for company in test_companies:
        result = normalize_company(company)
        print(f"  {company:25} -> {result.normalized_name:30} [{result.match_type}]")


# ============================================
# Identifier Blocklist
# ============================================

_identifier_blocklist: Optional[Dict] = None

def get_identifier_blocklist() -> Dict:
    """Load identifier blocklist (super-connectors to exclude)"""
    global _identifier_blocklist
    if _identifier_blocklist is None:
        blocklist_path = Path(__file__).parent / "data" / "identifier_blocklist.json"
        if blocklist_path.exists():
            with open(blocklist_path) as f:
                _identifier_blocklist = json.load(f)
                blocked_count = len(_identifier_blocklist.get("blocked", []))
                pattern_count = len(_identifier_blocklist.get("patterns", []))
                print(f"🚫 Loaded identifier blocklist: {blocked_count} values, {pattern_count} patterns")
        else:
            _identifier_blocklist = {"blocked": [], "patterns": []}
    return _identifier_blocklist


def is_identifier_blocked(value: str) -> Tuple[bool, Optional[str]]:
    """Check if identifier should be blocked. Returns (is_blocked, reason)"""
    if not value:
        return False, None
    
    blocklist = get_identifier_blocklist()
    norm_val = normalize_identifier(value)
    
    # Check exact matches
    for item in blocklist.get("blocked", []):
        if normalize_identifier(item["value"]) == norm_val:
            return True, item.get("reason", "blocked")
    
    # Check patterns
    for pattern in blocklist.get("patterns", []):
        if re.match(pattern["regex"], norm_val):
            return True, pattern.get("reason", "pattern match")
    
    return False, None
