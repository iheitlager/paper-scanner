#!/usr/bin/env python
"""
04_combined_strategy.py

Test combined citation key generation strategy with all three approaches.

Hypothesis: We can pick the best cite key using:
1. Author/Year (primary)
2. DOI slug (fallback)
3. UUID or random suffix (last resort)
"""

from paper_scanner.core.cite_key import generate_cite_key, resolve_collision
from paper_scanner.core.doi import DOI
from paper_scanner.core.models import Author, Paper


def doi_to_slug(doi_str: str) -> str:
    """Convert DOI to slug for fallback cite key"""
    try:
        doi = DOI(doi_str)
        parts = doi.stem.split("/")
        if len(parts) == 2:
            prefix = parts[0].replace(".", "-")
            suffix_parts = parts[1].split(".")
            if suffix_parts:
                return f"{prefix}-{suffix_parts[0]}"
    except ValueError:
        pass
    return None


def generate_best_cite_key(paper: Paper) -> tuple[str, str]:
    """
    Generate best possible cite key using fallback strategy.

    Returns:
        (cite_key, strategy) where strategy is "author_year", "doi", or "uuid"
    """
    # Strategy 1: Author/Year
    if paper.authors and paper.year:
        try:
            key = generate_cite_key(paper)
            return (key, "author_year")
        except ValueError:
            pass

    # Strategy 2: DOI slug
    if paper.doi:
        slug = doi_to_slug(paper.doi)
        if slug:
            return (slug, "doi")

    # Strategy 3: Last resort - use UUID
    return (paper.id[:12], "uuid")


def test_combined_strategy():
    """Test combined cite key generation strategy"""
    print("\n" + "=" * 60)
    print("04_combined_strategy.py - Full Generation Strategy")
    print("=" * 60)

    # Test 1: Complete metadata - use author/year
    print("\n[TEST 1] Complete metadata - author/year strategy")
    author = Author(family_name="Smith", given_name="John", full_name="John Smith")
    paper = Paper(
        title="Complete Paper",
        authors=[author],
        year=2020,
        doi="10.1287/isre.2017.0732",
        cite_key="placeholder",
    )

    key, strategy = generate_best_cite_key(paper)
    print(f"  Has author: {bool(paper.authors)}, year: {paper.year}, DOI: {paper.doi}")
    print(f"  Generated: {key} (strategy: {strategy})")
    assert strategy == "author_year", "Should prefer author/year"
    assert key == "Smith2020"
    print("  ✓ PASS")

    # Test 2: Missing year - use DOI
    print("\n[TEST 2] Missing year - DOI fallback")
    author = Author(family_name="Smith", given_name="John", full_name="John Smith")
    paper = Paper(
        title="No Year Paper",
        authors=[author],
        year=None,  # Missing year
        doi="10.1287/isre.2017.0732",
        cite_key="placeholder",
    )

    key, strategy = generate_best_cite_key(paper)
    print(f"  Has author: {bool(paper.authors)}, year: {paper.year}, DOI: {paper.doi}")
    print(f"  Generated: {key} (strategy: {strategy})")
    assert strategy == "doi", "Should fall back to DOI"
    assert key == "10-1287-isre"
    print("  ✓ PASS")

    # Test 3: Missing authors - use DOI
    print("\n[TEST 3] Missing authors - DOI fallback")
    paper = Paper(
        title="No Author Paper",
        authors=[],  # Missing authors
        year=2020,
        doi="10.1287/isre.2017.0732",
        cite_key="placeholder",
    )

    key, strategy = generate_best_cite_key(paper)
    print(f"  Has author: {bool(paper.authors)}, year: {paper.year}, DOI: {paper.doi}")
    print(f"  Generated: {key} (strategy: {strategy})")
    assert strategy == "doi", "Should fall back to DOI"
    print("  ✓ PASS")

    # Test 4: No metadata - use UUID
    print("\n[TEST 4] Minimal metadata - UUID fallback")
    paper = Paper(
        title="Minimal Paper",
        authors=[],
        year=None,
        doi=None,
        cite_key="placeholder",
    )

    key, strategy = generate_best_cite_key(paper)
    print(f"  Has author: {bool(paper.authors)}, year: {paper.year}, DOI: {paper.doi}")
    print(f"  Generated: {key} (strategy: {strategy})")
    assert strategy == "uuid", "Should fall back to UUID"
    assert len(key) > 0, "Should have some key"
    print("  ✓ PASS")

    # Test 5: Invalid DOI - skip to next strategy
    print("\n[TEST 5] Invalid DOI - skip to next strategy")
    paper = Paper(
        title="Bad DOI Paper",
        authors=[],
        year=None,
        doi="not-a-valid-doi",
        cite_key="placeholder",
    )

    key, strategy = generate_best_cite_key(paper)
    print(f"  DOI: {paper.doi} (invalid)")
    print(f"  Generated: {key} (strategy: {strategy})")
    assert strategy == "uuid", "Should skip invalid DOI and use UUID"
    print("  ✓ PASS")

    # Test 6: Collision resolution integrated
    print("\n[TEST 6] Collision resolution with strategy")
    author1 = Author(family_name="Smith", given_name="John", full_name="John Smith")
    author2 = Author(family_name="Smith", given_name="Jane", full_name="Jane Smith")

    paper1 = Paper(
        title="First Smith 2020",
        authors=[author1],
        year=2020,
        cite_key="placeholder",
    )
    paper2 = Paper(
        title="Second Smith 2020",
        authors=[author2],
        year=2020,
        cite_key="placeholder",
    )

    # Generate first key
    key1, strategy1 = generate_best_cite_key(paper1)
    used_keys = {key1}
    print(f"  Paper 1: {key1} ({strategy1})")

    # Generate second key with collision handling
    base_key2, strategy2 = generate_best_cite_key(paper2)
    key2 = resolve_collision(base_key2, used_keys)
    used_keys.add(key2)
    print(f"  Paper 2: {base_key2} -> {key2} ({strategy2})")

    assert len(used_keys) == 2, "Should have 2 unique keys"
    assert key1 == "Smith2020"
    assert key2 == "Smith2020a"
    print("  ✓ PASS")

    # Test 7: Strategy preference order
    print("\n[TEST 7] Strategy preference verification")
    test_cases = [
        # (has_author, has_year, has_doi, expected_strategy)
        (True, True, True, "author_year"),  # Prefer author/year
        (True, True, False, "author_year"),  # Don't need DOI if author/year works
        (True, False, True, "doi"),  # Use DOI when year missing
        (False, True, True, "doi"),  # Use DOI when authors missing
        (False, False, True, "doi"),  # Use DOI when both missing
        (False, False, False, "uuid"),  # Last resort
    ]

    for has_author, has_year, has_doi, expected_strategy in test_cases:
        author = Author(family_name="Test", given_name="X", full_name="X Test") if has_author else None
        authors = [author] if author else []
        year = 2020 if has_year else None
        doi = "10.1287/isre.2017.0732" if has_doi else None

        paper = Paper(
            title="Test",
            authors=authors,
            year=year,
            doi=doi,
            cite_key="placeholder",
        )

        key, strategy = generate_best_cite_key(paper)
        status = "✓" if strategy == expected_strategy else "✗"
        print(f"  {status} A={has_author} Y={has_year} D={has_doi} -> {strategy}")
        assert strategy == expected_strategy, \
            f"Expected {expected_strategy}, got {strategy}"
    print("  ✓ PASS")

    print("\n" + "=" * 60)
    print("✓ All combined strategy tests passed!")
    print("=" * 60)


if __name__ == "__main__":
    test_combined_strategy()
