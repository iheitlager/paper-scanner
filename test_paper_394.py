#!/usr/bin/env python3
"""Quick test for paper 394 with updated keywords."""

import os
import re
import sys
from typing import List, Tuple
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor

load_dotenv()

def normalize_text(text: str) -> str:
    """Normalize text for keyword matching."""
    if not text:
        return ""
    return text.lower().strip()

def check_keyword_match(text: str, keywords: List[str]) -> Tuple[List[str], int]:
    """Check which keywords match in text."""
    matched = []
    for keyword in keywords:
        # Use word boundary matching
        pattern = r'\b' + re.escape(keyword) + r'\b'
        if re.search(pattern, text):
            matched.append(keyword)
    return matched, len(matched)

# Updated REQUIRED_KEYWORDS
REQUIRED_KEYWORDS = [
    # Innovation types
    'innovation', 'digital transformation', 'digitalization', 'technology adoption',
    'digital service innovation', 'service innovation', 'business model innovation',
    'radical innovation', 'business innovation', 'strategic innovation',

    # Organizational context
    'firm', 'company', 'organization', 'enterprise', 'incumbent',
    'organizational', 'business', 'corporate',

    # Supplier/partnership
    'supplier', 'vendor', 'partner', 'ecosystem', 'collaboration',

    # Methodology and analysis
    'qualitative comparative analysis', 'comparative analysis', 'configuration',
    'ambidexterity', 'ambidextrous', 'performance'
]

HARD_EXCLUSIONS = [
    # Completely different domains
    'cancer', 'tumor', 'disease', 'patient', 'clinical',
    'quantum', 'physics', 'chemistry', 'biology',
    'agriculture', 'farming', 'crop',

    # Irrelevant contexts
    'school', 'student', 'education', 'teaching',
    'military', 'weapon', 'defense',

    # Wrong level of analysis - be more specific to avoid false positives
    'consumer behavior', 'household', 'personal use', 'consumer purchase'
]

# Connect to database
db_url = os.getenv('DATABASE_URL')
conn = psycopg2.connect(db_url)
cursor = conn.cursor(cursor_factory=RealDictCursor)

# Get paper 394
cursor.execute('''
SELECT id, title, abstract, keywords, citekey
FROM papers
WHERE id = 394
''')
paper = cursor.fetchone()

if not paper:
    print("Paper 394 not found!")
    sys.exit(1)

print("=" * 80)
print("PAPER 394 ANALYSIS")
print("=" * 80)
print(f"Title: {paper['title']}")
print(f"Citekey: {paper['citekey']}")
print(f"\nKeywords: {paper['keywords']}")
print()

# Normalize text
title = normalize_text(paper['title'])
abstract = normalize_text(paper.get('abstract', '') or '')
combined_text = f"{title} {abstract}"

print("HARD EXCLUSIONS CHECK:")
excluded_kw, excluded_count = check_keyword_match(combined_text, HARD_EXCLUSIONS)
if excluded_count > 0:
    print(f"  ❌ EXCLUDED - Found {excluded_count} hard exclusion keywords:")
    for kw in excluded_kw:
        print(f"    - {kw}")
else:
    print(f"  ✓ PASS - No hard exclusion keywords")

print("\nREQUIRED KEYWORDS CHECK:")
required_kw, required_count = check_keyword_match(combined_text, REQUIRED_KEYWORDS)
print(f"  Found {required_count}/2 required keywords:")
if required_kw:
    for kw in required_kw:
        print(f"    ✓ {kw}")
else:
    print("    (none found)")

print(f"\nDECISION:")
if excluded_count > 0:
    print(f"  ❌ EXCLUDE - Hard exclusion detected")
elif required_count >= 2:
    print(f"  ✓ INCLUDE - {required_count}/2 required keywords met")
else:
    print(f"  ⚠️  AMBIGUOUS - Only {required_count}/2 required keywords met (will pass to next stage)")

cursor.close()
conn.close()
