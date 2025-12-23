#!/usr/bin/env python
"""
02_doi_fallback.py

Test citation key generation from DOI when metadata is incomplete.

Hypothesis: We can use DOI as a fallback when author/year are missing.
"""

from paper_scanner.core.doi import DOI


def doi_to_slug(doi_str: str) -> str:
    """
    Convert DOI to a slug suitable for citation keys.
    
    Example: "10.1287/isre.2017.0732" -> "10-1287-isre"
    """
    import re
    try:
        doi = DOI(doi_str)
        # Take prefix + first part of suffix
        parts = doi.stem.split("/")
        if len(parts) == 2:
            prefix = parts[0].replace(".", "-")
            suffix_parts = parts[1].split(".")
            # Use first meaningful part - extract leading letters/numbers until dot
            if suffix_parts:
                # First try: leading letters
                match = re.match(r"([a-z]+)", suffix_parts[0], re.IGNORECASE)
                if match:
                    slug = f"{prefix}-{match.group(1).lower()}"
                    return slug
                # Fallback: leading alphanumeric (for numeric-only suffixes)
                match = re.match(r"([a-z0-9]+)", suffix_parts[0], re.IGNORECASE)
                if match:
                    slug = f"{prefix}-{match.group(1).lower()}"
                    return slug
    except ValueError:
        pass
    return None


def test_doi_to_slug_conversion():
    """Test DOI to slug conversion for fallback keys"""
    print("\n" + "=" * 60)
    print("02_doi_fallback.py - DOI as Fallback Keys")
    print("=" * 60)

    # Test 1: Standard DOI slug
    print("\n[TEST 1] Standard DOI to slug")
    doi_str = "10.1287/isre.2017.0732"
    slug = doi_to_slug(doi_str)
    print(f"  DOI: {doi_str}")
    print(f"  Slug: {slug}")
    assert slug == "10-1287-isre", f"Expected '10-1287-isre', got '{slug}'"
    print("  ✓ PASS")

    # Test 2: Different publisher
    print("\n[TEST 2] Different publisher DOI")
    doi_str = "10.1038/nature12373"
    slug = doi_to_slug(doi_str)
    print(f"  DOI: {doi_str}")
    print(f"  Slug: {slug}")
    assert slug == "10-1038-nature", f"Expected '10-1038-nature', got '{slug}'"
    print("  ✓ PASS")

    # Test 3: arXiv-style DOI
    print("\n[TEST 3] arXiv DOI")
    doi_str = "10.48550/arxiv.2301.13688"
    slug = doi_to_slug(doi_str)
    print(f"  DOI: {doi_str}")
    print(f"  Slug: {slug}")
    assert slug == "10-48550-arxiv", f"Expected '10-48550-arxiv', got '{slug}'"
    print("  ✓ PASS")

    # Test 4: DOI with URL prefix
    print("\n[TEST 4] DOI with URL prefix")
    doi_str = "https://doi.org/10.1145/3062341.3062383"
    slug = doi_to_slug(doi_str)
    print(f"  DOI: {doi_str}")
    print(f"  Slug: {slug}")
    assert slug == "10-1145-3062341", f"Expected '10-1145-3062341', got '{slug}'"
    print("  ✓ PASS")

    # Test 5: Invalid DOI
    print("\n[TEST 5] Invalid DOI returns None")
    doi_str = "not-a-valid-doi"
    slug = doi_to_slug(doi_str)
    print(f"  DOI: {doi_str}")
    print(f"  Slug: {slug}")
    assert slug is None, f"Expected None for invalid DOI, got '{slug}'"
    print("  ✓ PASS")

    # Test 6: DOI object validation
    print("\n[TEST 6] DOI object validation")
    valid_dois = [
        "10.1287/isre.2017.0732",
        "https://doi.org/10.1145/3062341.3062383",
        "doi:10.1038/nature12373",
        "doi.10.48550/arxiv.2301.13688",
    ]

    for doi_str in valid_dois:
        try:
            doi = DOI(doi_str)
            print(f"  ✓ {doi_str[:40]}... -> {doi.stem}")
        except ValueError:
            print(f"  ✗ Failed to parse: {doi_str}")
            assert False, f"Should parse {doi_str}"
    print("  ✓ PASS")

    # Test 7: DOI normalization
    print("\n[TEST 7] DOI normalization to stem")
    test_cases = [
        ("10.1287/isre.2017.0732", "10.1287/isre.2017.0732"),
        ("https://doi.org/10.1287/isre.2017.0732", "10.1287/isre.2017.0732"),
        ("doi:10.1038/nature12373", "10.1038/nature12373"),  # case-insensitive
        ("doi:10.48550/arxiv.2301.13688", "10.48550/arxiv.2301.13688"),
    ]

    for input_doi, expected_stem in test_cases:
        try:
            doi = DOI(input_doi)
            # DOI normalizes to lowercase
            expected_stem_lower = expected_stem.lower()
            assert doi.stem == expected_stem_lower, f"Expected {expected_stem_lower}, got {doi.stem}"
            print(f"  ✓ {input_doi[:35]}... -> {doi.stem}")
        except AssertionError as e:
            print(f"  ✗ {e}")
            raise
    print("  ✓ PASS")

    print("\n" + "=" * 60)
    print("✓ All DOI fallback tests passed!")
    print("=" * 60)


if __name__ == "__main__":
    test_doi_to_slug_conversion()
