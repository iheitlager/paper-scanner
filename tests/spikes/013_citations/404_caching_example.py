"""
Example demonstrating 404 caching functionality.

Shows how the handlers automatically cache 404 responses to reduce API calls.
"""

from pathlib import Path
from unittest.mock import Mock, patch
import tempfile

# Example setup
cache_dir = Path(tempfile.mkdtemp())

# This example shows how fetch_metadata in BaseFetcherHandler uses 404 caching
print("=" * 70)
print("404 CACHING EXAMPLE")
print("=" * 70)

print("\n1. FIRST FETCH - API CALL")
print("-" * 70)
print("DOI: 10.9999/nonexistent")
print("- Handler queries API")
print("- API returns 404 (not found)")
print("- Handler creates 404 marker: {'ITEM': '404 - NOT FOUND', ...}")
print("- 404 marker is cached with TTL (default 30 days)")
print("- Result: None (treated as not found)")

print("\n2. SECOND FETCH - CACHE HIT")
print("-" * 70)
print("DOI: 10.9999/nonexistent (same DOI)")
print("- Handler checks cache")
print("- Finds 404 marker (cache hit!)")
print("- Detects it's a 404 marker using is_404_marker()")
print("- Returns None immediately WITHOUT API CALL")
print("- Result: No API call made, saves bandwidth and time")

print("\n3. CACHE INVALIDATION (Optional)")
print("-" * 70)
print("After TTL expires (default 30 days):")
print("- 404 marker expires automatically")
print("- Next fetch will query API again (allows forward citations)")
print("- This handles discovery of new metadata over time")

print("\n4. KEY BENEFITS")
print("-" * 70)
print("✓ Reduces API load for non-existent DOIs")
print("✓ Faster response times (no network latency for 404s)")
print("✓ Backward citations also cached (fetch_cited_by)")
print("✓ TTL support allows cache invalidation for forward citations")
print("✓ Generic implementation in BaseFetcherHandler")
print("✓ Works for all handlers: Crossref, OpenAlex, Semantic Scholar")

print("\n5. CACHE MARKER STRUCTURE")
print("-" * 70)
print("404 marker example:")
print("""{
    "ITEM": "404 - NOT FOUND",
    "LAST-CHECKED": "2025-12-24T15:30:45.123456",
    "URL": "https://doi.org/10.9999/nonexistent"
}""")

print("\n6. HANDLER CODE CHANGES")
print("-" * 70)
print("Before (old behavior):")
print("  if api_data is None:")
print("      return None, False  # Cache miss, not tracked")
print("")
print("After (new behavior with 404 caching):")
print("  if api_data is None:")
print("      # Cache the 404 response to avoid future API calls")
print("      cache.set(doi, create_404_marker(url=...))")
print("      return None, False  # Cache miss, but 404 is now cached!")

print("\n" + "=" * 70)
