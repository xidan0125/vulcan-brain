#!/usr/bin/env python3
"""
Entity Clustering with Gemini API
Expands entity dictionary by clustering similar company names
"""
import json
import requests
import time
from pathlib import Path
from typing import List, Dict

# Gemini API
GEMINI_API_KEY = "AIzaSyAzdtbNnuG9fE3ilV4mKYewlkJbakbvWAM"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"

# Paths
DATA_DIR = Path(__file__).parent / "kuzu_etl" / "data"
ROSTER_PATH = DATA_DIR / "entity_roster.json"
DICT_PATH = DATA_DIR / "entity_dictionary.json"


def call_gemini(prompt: str) -> str:
    """Call Gemini API"""
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 4096
        }
    }

    resp = requests.post(GEMINI_URL, json=payload, timeout=60)
    resp.raise_for_status()

    data = resp.json()
    return data["candidates"][0]["content"]["parts"][0]["text"]


def parse_clusters(response: str) -> List[Dict]:
    """Parse JSON clusters from response"""
    try:
        # Extract JSON from markdown code blocks
        if "```json" in response:
            response = response.split("```json")[1].split("```")[0]
        elif "```" in response:
            response = response.split("```")[1].split("```")[0]

        data = json.loads(response.strip())

        if isinstance(data, list):
            return data
        elif isinstance(data, dict) and "clusters" in data:
            return data["clusters"]
        return []
    except:
        return []


def cluster_batch(entities: List[Dict], batch_num: int) -> List[Dict]:
    """Cluster a batch of entities"""
    # Build numbered list
    numbered = "\n".join([f"{i+1}. {e['name']} ({e['count']}x)" for i, e in enumerate(entities)])

    prompt = f"""You are a B2B COMPANY entity resolution expert. Below is a list of COMPANY names with occurrence counts.

Find groups of company names that refer to THE SAME COMPANY. Look for:
- Abbreviations (VSG = Vulcan Shield Global)
- Company suffixes (Pte. Ltd. = Pte Ltd = Ltd)
- Typos (Vulcan Sheild = Vulcan Shield)
- Subsidiary notation (Apple Inc. = Apple)

CRITICAL RULES:
1. ONLY merge COMPANIES, not people
2. NEVER put different people in the same group (e.g. "David", "Amanda", "Barry" are DIFFERENT people)
3. "XXX Vsg" are different employees at Vulcan Shield - DO NOT merge them together
4. Products like "Alumina Fiber", "Needle Blanket" are NOT companies
5. When uncertain, DO NOT merge

Entity List:
{numbered}

Return JSON format only:
[
  {{"canonical": "Company Full Name", "aliases": ["variant1", "variant2"]}},
  ...
]

Only output COMPANY groups with 2+ variants. No explanations. No person names."""

    print(f"\n=== Batch {batch_num}: {len(entities)} entities ===")

    try:
        response = call_gemini(prompt)
        clusters = parse_clusters(response)

        if clusters:
            print(f"Found {len(clusters)} clusters")
            for c in clusters[:3]:
                print(f"  - {c.get('canonical', 'N/A')}: {len(c.get('aliases', []))} aliases")
        else:
            print("No clusters found or parse failed")

        return clusters
    except Exception as e:
        print(f"Error: {e}")
        return []


def filter_company_entities(entities: List[Dict]) -> List[Dict]:
    """Filter out non-company entities (persons, locations, generic terms)"""
    # Known person names (VSG employees)
    person_names = {
        "DAVID", "BARRY", "MATTHIAS", "RENEE", "SHENG KAI", "SHERMAINE", "CINDY",
        "AMANDA", "WIDODO", "LUMIN", "GRACE", "ADELINE", "GLENN", "DANIEL", "CHRIS",
        "CHRISTOPH", "BENJAMIN", "WANG XIANG PING", "JIAOJI QIAN", "ERANTHE"
    }

    # Skip patterns
    skip_words = {"SINGAPORE", "SHANGHAI", "GERMANY", "UK", "USA", "CHINA", "PARIS",
                  "ORLANDO", "SALES MANAGER", "CEO", "DIRECTOR", "MANAGER"}
    skip_contains = ["MICROSOFT TEAMS", "DBS IDEAL", "MARINA", "BOULEVARD", " VSG"]

    # Product patterns (not companies)
    product_patterns = ["FIBER", "BLANKET", "FABRIC", "PREPREG", "CERAMIC"]

    filtered = []
    for e in entities:
        name = e["name"]
        name_upper = name.upper()

        # Skip single short words (likely first names)
        if len(name.split()) == 1 and len(name) < 12:
            continue
        # Skip known person names
        if name_upper in person_names:
            continue
        # Skip "XXX Vsg" pattern (employee names)
        if name_upper.endswith(" VSG"):
            continue
        # Skip known locations/titles
        if name_upper in skip_words:
            continue
        # Skip addresses/tools
        if any(s in name_upper for s in skip_contains):
            continue
        # Skip likely products
        if any(p in name_upper for p in product_patterns) and "CO" not in name_upper and "LTD" not in name_upper:
            continue

        filtered.append(e)

    return filtered


def main():
    print("=" * 60)
    print("Entity Clustering with Gemini")
    print("=" * 60)

    # Load roster
    with open(ROSTER_PATH) as f:
        roster = json.load(f)

    entities = roster.get("entities", [])
    print(f"\nTotal entities in roster: {len(entities)}")

    # Filter to likely companies (count >= 5)
    high_freq = [e for e in entities if e["count"] >= 5]
    print(f"High frequency (>=5): {len(high_freq)}")

    # Filter out non-companies
    companies = filter_company_entities(high_freq)
    print(f"After filtering non-companies: {len(companies)}")

    # Load existing dictionary
    existing_aliases = set()
    if DICT_PATH.exists():
        with open(DICT_PATH) as f:
            existing = json.load(f)
            for c in existing.get("clusters", []):
                for a in c.get("aliases", []):
                    existing_aliases.add(a.upper())
        print(f"Existing aliases: {len(existing_aliases)}")

    # Filter out already-clustered
    to_cluster = [e for e in companies if e["name"].upper() not in existing_aliases]
    print(f"To cluster (new): {len(to_cluster)}")

    if not to_cluster:
        print("\nNothing new to cluster!")
        return

    # Process in batches
    batch_size = 80
    all_clusters = []

    for i in range(0, min(len(to_cluster), 500), batch_size):
        batch = to_cluster[i:i+batch_size]
        clusters = cluster_batch(batch, i // batch_size + 1)
        all_clusters.extend(clusters)
        time.sleep(1)

    print(f"\n=== Results ===")
    print(f"Total new clusters: {len(all_clusters)}")

    # Merge with existing
    if DICT_PATH.exists():
        with open(DICT_PATH) as f:
            existing = json.load(f)
    else:
        existing = {"clusters": []}

    # Add new clusters
    existing["clusters"].extend(all_clusters)

    # Rebuild dictionary mapping
    dictionary = {}
    for c in existing["clusters"]:
        canonical = c.get("canonical", "")
        for alias in c.get("aliases", []):
            if alias and alias != canonical:
                dictionary[alias] = canonical

    existing["dictionary"] = dictionary
    existing["stats"] = {
        "total_clusters": len(existing["clusters"]),
        "total_mappings": len(dictionary)
    }

    # Save
    with open(DICT_PATH, "w") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)

    print(f"\n Saved to {DICT_PATH}")
    print(f"   Total clusters: {existing['stats']['total_clusters']}")
    print(f"   Total mappings: {existing['stats']['total_mappings']}")


if __name__ == "__main__":
    main()
