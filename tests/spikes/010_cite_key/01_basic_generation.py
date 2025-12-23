#!/usr/bin/env python
"""
01_basic_generation.py

Test basic citation key generation from author and year metadata.

Hypothesis: We can generate simple, readable cite keys in 'LastnameYear' format.
"""

from paper_scanner.core.cite_key import generate_cite_key
from paper_scanner.core.models import Author, Paper


def test_basic_author_year_generation():
    """Test simple 'LastnameYear' format generation"""
    print("\n" + "=" * 60)
    print("01_basic_generation.py - Basic Author/Year Keys")
    print("=" * 60)

    # Test 1: Simple case
    print("\n[TEST 1] Simple author and year")
    author = Author(family_name="Smith", given_name="John", full_name="John Smith")
    paper = Paper(
        title="Test Paper",
        authors=[author],
        year=2020,
        cite_key="placeholder",
    )

    key = generate_cite_key(paper)
    print(f"  Author: {author.family_name}, Year: {paper.year}")
    print(f"  Generated key: {key}")
    assert key == "Smith2020", f"Expected 'Smith2020', got '{key}'"
    print("  ✓ PASS")

    # Test 2: Multi-word last name (spaces removed)
    print("\n[TEST 2] Multi-word last name")
    author = Author(family_name="Van Der Berg", given_name="Jan", full_name="Jan Van Der Berg")
    paper = Paper(
        title="Test Paper",
        authors=[author],
        year=2021,
        cite_key="placeholder",
    )

    key = generate_cite_key(paper)
    print(f"  Author: {author.family_name}, Year: {paper.year}")
    print(f"  Generated key: {key}")
    assert key == "VanDerBerg2021", f"Expected 'VanDerBerg2021', got '{key}'"
    print("  ✓ PASS")

    # Test 3: Hyphenated last name (hyphens removed)
    print("\n[TEST 3] Hyphenated last name")
    author = Author(family_name="Smith-Jones", given_name="Jane", full_name="Jane Smith-Jones")
    paper = Paper(
        title="Test Paper",
        authors=[author],
        year=2022,
        cite_key="placeholder",
    )

    key = generate_cite_key(paper)
    print(f"  Author: {author.family_name}, Year: {paper.year}")
    print(f"  Generated key: {key}")
    assert key == "SmithJones2022", f"Expected 'SmithJones2022', got '{key}'"
    print("  ✓ PASS")

    # Test 4: Uses only first author
    print("\n[TEST 4] Multiple authors - use first only")
    author1 = Author(family_name="Smith", given_name="John", full_name="John Smith")
    author2 = Author(family_name="Doe", given_name="Jane", full_name="Jane Doe")
    paper = Paper(
        title="Multi-author Paper",
        authors=[author1, author2],
        year=2020,
        cite_key="placeholder",
    )

    key = generate_cite_key(paper)
    print(f"  Authors: {[a.family_name for a in paper.authors]}")
    print(f"  Generated key: {key}")
    assert key == "Smith2020", f"Expected 'Smith2020', got '{key}'"
    assert "Doe" not in key, "Should only use first author"
    print("  ✓ PASS")

    # Test 5: Different year formats
    print("\n[TEST 5] Different years")
    for year in [1999, 2000, 2025]:
        author = Author(family_name="Author", given_name="Test", full_name="Test Author")
        paper = Paper(
            title="Test",
            authors=[author],
            year=year,
            cite_key="placeholder",
        )
        key = generate_cite_key(paper)
        print(f"  Year {year} -> {key}")
        assert key == f"Author{year}", f"Year format failed for {year}"
    print("  ✓ PASS")

    # Test 6: Error - no authors
    print("\n[TEST 6] Error handling - no authors")
    paper = Paper(
        title="No Author Paper",
        authors=[],
        year=2020,
        cite_key="placeholder",
    )

    try:
        key = generate_cite_key(paper)
        print("  ✗ FAIL - should have raised ValueError")
        assert False, "Should raise ValueError for missing authors"
    except ValueError as e:
        print(f"  Caught expected error: {str(e)[:50]}...")
        assert "no authors" in str(e).lower()
        print("  ✓ PASS")

    # Test 7: Error - no year
    print("\n[TEST 7] Error handling - no year")
    author = Author(family_name="Smith", given_name="John", full_name="John Smith")
    paper = Paper(
        title="No Year Paper",
        authors=[author],
        year=None,
        cite_key="placeholder",
    )

    try:
        key = generate_cite_key(paper)
        print("  ✗ FAIL - should have raised ValueError")
        assert False, "Should raise ValueError for missing year"
    except ValueError as e:
        print(f"  Caught expected error: {str(e)[:50]}...")
        assert "publication year" in str(e).lower()
        print("  ✓ PASS")

    # Test 8: Error - empty family name
    print("\n[TEST 8] Error handling - empty family name")
    author = Author(family_name="", given_name="John", full_name="John")
    paper = Paper(
        title="No Family Name",
        authors=[author],
        year=2020,
        cite_key="placeholder",
    )

    try:
        key = generate_cite_key(paper)
        print("  ✗ FAIL - should have raised ValueError")
        assert False, "Should raise ValueError for empty family name"
    except ValueError as e:
        print(f"  Caught expected error: {str(e)[:50]}...")
        assert "family name" in str(e).lower()
        print("  ✓ PASS")

    print("\n" + "=" * 60)
    print("✓ All basic generation tests passed!")
    print("=" * 60)


if __name__ == "__main__":
    test_basic_author_year_generation()
