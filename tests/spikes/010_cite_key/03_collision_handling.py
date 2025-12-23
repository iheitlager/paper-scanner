#!/usr/bin/env python
"""
03_collision_handling.py

Test collision resolution when multiple papers generate the same cite key.

Hypothesis: We can resolve collisions by appending suffixes (a, b, ..., z, aa, ab, ...).
"""

from paper_scanner.core.cite_key import make_collision_suffix, resolve_collision


def test_collision_resolution():
    """Test cite key collision resolution"""
    print("\n" + "=" * 60)
    print("03_collision_handling.py - Collision Suffix Generation")
    print("=" * 60)

    # Test 1: Single letter suffixes (a-z)
    print("\n[TEST 1] Single letter suffixes")
    suffixes = [make_collision_suffix(i) for i in range(26)]
    print(f"  Indices 0-25: {' '.join(suffixes)}")
    assert suffixes[0] == "a", "Index 0 should be 'a'"
    assert suffixes[25] == "z", "Index 25 should be 'z'"
    assert len(suffixes) == 26
    assert len(set(suffixes)) == 26, "All suffixes should be unique"
    print("  ✓ PASS")

    # Test 2: Double letter suffixes (aa-az, ba-bz, etc.)
    print("\n[TEST 2] Double letter suffixes")
    suffixes = [make_collision_suffix(i) for i in range(26, 52)]
    print(f"  Indices 26-51: {' '.join(suffixes[:10])}... (showing first 10)")
    assert suffixes[0] == "aa", "Index 26 should be 'aa'"
    assert suffixes[25] == "az", "Index 51 should be 'az'"
    assert len(set(suffixes)) == 26, "All double-letter suffixes should be unique"
    print("  ✓ PASS")

    # Test 3: Triple letter suffixes
    print("\n[TEST 3] Triple letter suffixes")
    suffixes = [make_collision_suffix(i) for i in range(52, 78)]
    print(f"  Indices 52-77: {' '.join(suffixes[:10])}... (showing first 10)")
    assert suffixes[0] == "aaa", "Index 52 should be 'aaa'"
    assert suffixes[25] == "aaz", "Index 77 should be 'aaz'"
    print("  ✓ PASS")

    # Test 4: Large index handling
    print("\n[TEST 4] Large indices")
    suffix_100 = make_collision_suffix(100)
    print(f"  Index 100: {suffix_100}")
    assert isinstance(suffix_100, str) and len(suffix_100) > 0
    print("  ✓ PASS")

    # Test 5: All suffixes are unique
    print("\n[TEST 5] Uniqueness across wide range")
    suffixes = [make_collision_suffix(i) for i in range(200)]
    unique_suffixes = set(suffixes)
    print(f"  Generated {len(suffixes)} suffixes, {len(unique_suffixes)} unique")
    assert len(suffixes) == len(unique_suffixes), "All suffixes should be unique"
    print("  ✓ PASS")

    # Test 6: Resolve collision with no existing keys
    print("\n[TEST 6] No collision - return base key")
    existing_keys = {}
    result = resolve_collision("Smith2020", existing_keys)
    print(f"  Base key: Smith2020, Existing: {existing_keys}")
    print(f"  Result: {result}")
    assert result == "Smith2020", "Should return base key if no collision"
    print("  ✓ PASS")

    # Test 7: Resolve single collision
    print("\n[TEST 7] Single collision - append 'a'")
    existing_keys = {"Smith2020": True}
    result = resolve_collision("Smith2020", existing_keys)
    print(f"  Base key: Smith2020, Existing: {list(existing_keys.keys())}")
    print(f"  Result: {result}")
    assert result == "Smith2020a", "Should append 'a' for first collision"
    print("  ✓ PASS")

    # Test 8: Resolve multiple collisions
    print("\n[TEST 8] Multiple collisions - sequential suffixes")
    existing_keys = {
        "Smith2020": True,
        "Smith2020a": True,
        "Smith2020b": True,
    }
    result = resolve_collision("Smith2020", existing_keys)
    print(f"  Base key: Smith2020, Existing: {list(existing_keys.keys())}")
    print(f"  Result: {result}")
    assert result == "Smith2020c", "Should find first unused suffix"
    print("  ✓ PASS")

    # Test 9: Resolve many collisions (double-letter suffixes)
    print("\n[TEST 9] Many collisions - transition to double letters")
    existing_keys = {f"Smith2020{make_collision_suffix(i)}": True for i in range(30)}
    result = resolve_collision("Smith2020", existing_keys)
    print(f"  Base key: Smith2020, Existing keys: {len(existing_keys)} (indices 0-29)")
    print(f"  Result: {result}")
    assert result not in existing_keys, "Result should not collide with existing keys"
    assert result.startswith("Smith2020"), "Result should maintain base key"
    print("  ✓ PASS")

    # Test 10: Real-world scenario - three Smith papers from 2020
    print("\n[TEST 10] Real-world: Three Smith 2020 papers")
    base_key = "Smith2020"
    keys_assigned = set()

    # First paper
    key1 = resolve_collision(base_key, keys_assigned)
    keys_assigned.add(key1)
    print(f"  Paper 1: {key1}")

    # Second paper (collides with first)
    key2 = resolve_collision(base_key, keys_assigned)
    keys_assigned.add(key2)
    print(f"  Paper 2: {key2}")

    # Third paper (collides with first two)
    key3 = resolve_collision(base_key, keys_assigned)
    keys_assigned.add(key3)
    print(f"  Paper 3: {key3}")

    print(f"  All keys: {sorted(keys_assigned)}")
    assert len(keys_assigned) == 3, "Should have 3 unique keys"
    assert key1 == "Smith2020", "First should be base key"
    assert key2 == "Smith2020a", "Second should have suffix 'a'"
    assert key3 == "Smith2020b", "Third should have suffix 'b'"
    print("  ✓ PASS")

    print("\n" + "=" * 60)
    print("✓ All collision handling tests passed!")
    print("=" * 60)


if __name__ == "__main__":
    test_collision_resolution()
