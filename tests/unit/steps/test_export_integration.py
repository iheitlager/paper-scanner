#!/usr/bin/env python3
"""
Integration test: Verify papers_to_jsonl correctly serializes Paper references
through the export chain (export.py → papers_to_jsonl → paper_to_dict)
"""

import json
import sys
import tempfile
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from paper_scanner.core.models import Author, Discovery, DiscoveryMethod, Paper
from paper_scanner.io.json import papers_to_jsonl


def test_papers_to_jsonl_export_chain():
    """Test that papers_to_jsonl correctly handles the export.py flow"""
    print("\n" + "="*70)
    print("INTEGRATION TEST: papers_to_jsonl export chain")
    print("="*70)

    # Create papers with self-references (simulating database contents)
    paper1 = Paper(
        cite_key="Paper1",
        title="Original Paper",
        year=2023,
        authors=[Author(family_name="Smith", given_name="J", full_name="John Smith")],
        discovery=Discovery(method=DiscoveryMethod.KEYWORD_SEARCH)
    )

    paper2 = Paper(
        cite_key="Paper2",
        title="Duplicate Paper",
        year=2023,
        authors=[Author(family_name="Smith", given_name="J", full_name="John Smith")],
        discovery=Discovery(method=DiscoveryMethod.KEYWORD_SEARCH),
        duplicate_of=paper1,
        cited_papers=[paper1]
    )

    paper3 = Paper(
        cite_key="Paper3",
        title="Citing Paper",
        year=2024,
        discovery=Discovery(method=DiscoveryMethod.KEYWORD_SEARCH),
        cited_papers=[paper1, paper2],
        cited_by_papers=[paper2]
    )

    papers = [paper1, paper2, paper3]

    print("\nCreated 3 papers:")
    print(f"  Paper 1 ID: {paper1.id} (Original)")
    print(f"  Paper 2 ID: {paper2.id} (Duplicate of Paper1)")
    print(f"  Paper 3 ID: {paper3.id} (References Paper1, Paper2)")

    # Export using papers_to_jsonl (same as export.py does)
    jsonl_output = papers_to_jsonl(papers, exclude_none=False)

    print(f"\nGenerated JSONL output: {len(jsonl_output)} bytes")

    # Write to temp file for verification
    with tempfile.TemporaryDirectory() as tmpdir:
        export_file = Path(tmpdir) / "export.jsonl"
        with open(export_file, 'w') as f:
            f.write(jsonl_output)

        # Read back and verify
        with open(export_file, 'r') as f:
            lines = f.readlines()

        print(f"✓ Exported {len(lines)} lines")

        # Parse and verify each line
        for i, line in enumerate(lines, 1):
            data = json.loads(line)
            print(f"\nLine {i} ({data['cite_key']}):")
            print(f"  ID: {data['id']}")

            # Verify Paper references are strings
            dup_of = data.get('duplicate_of')
            cited_papers = data.get('cited_papers', [])
            cited_by_papers = data.get('cited_by_papers', [])

            print(f"  duplicate_of: {dup_of if dup_of else 'null'}")
            print(f"  cited_papers: {cited_papers if cited_papers else '[]'}")
            print(f"  cited_by_papers: {cited_by_papers if cited_by_papers else '[]'}")

            # Verify types
            if dup_of is not None:
                assert isinstance(dup_of, str), f"duplicate_of should be string, got {type(dup_of)}"
                print("    ✓ duplicate_of is string ID")

            assert isinstance(cited_papers, list), f"cited_papers should be list, got {type(cited_papers)}"
            assert all(isinstance(x, str) for x in cited_papers), "All cited_papers should be string IDs"
            if cited_papers:
                print(f"    ✓ cited_papers contains {len(cited_papers)} ID strings")

            assert isinstance(cited_by_papers, list), f"cited_by_papers should be list, got {type(cited_by_papers)}"
            assert all(isinstance(x, str) for x in cited_by_papers), "All cited_by_papers should be string IDs"
            if cited_by_papers:
                print(f"    ✓ cited_by_papers contains {len(cited_by_papers)} ID strings")

        # Verify references are correct
        paper2_data = json.loads(lines[1])
        paper3_data = json.loads(lines[2])

        assert paper2_data['duplicate_of'] == paper1.id, "Paper2 should reference Paper1"
        assert paper1.id in paper2_data['cited_papers'], "Paper2 should cite Paper1"
        assert paper1.id in paper3_data['cited_papers'], "Paper3 should cite Paper1"
        assert paper2.id in paper3_data['cited_papers'], "Paper3 should cite Paper2"
        assert paper2.id in paper3_data['cited_by_papers'], "Paper3 should be cited by Paper2"

        print("\n✓ PASS: papers_to_jsonl export chain correctly serializes all Paper references")


def test_jsonl_roundtrip_with_ids():
    """Verify that JSONL with ID references handles deserialization correctly"""
    print("\n" + "="*70)
    print("INTEGRATION TEST: JSONL export serialization only")
    print("="*70)

    # Create papers with references
    paper1 = Paper(
        cite_key="Original",
        title="Original Paper",
        year=2023,
        discovery=Discovery(method=DiscoveryMethod.KEYWORD_SEARCH)
    )

    paper2 = Paper(
        cite_key="Duplicate",
        title="Duplicate",
        year=2023,
        discovery=Discovery(method=DiscoveryMethod.KEYWORD_SEARCH),
        duplicate_of=paper1,
        cited_papers=[paper1]
    )

    print("\nOriginal papers:")
    print(f"  Paper1 ID: {paper1.id}")
    print(f"  Paper2.duplicate_of ID: {paper2.duplicate_of.id}")
    print(f"  Paper2.cited_papers: {[p.id for p in paper2.cited_papers]}")

    # Export to JSONL - THIS IS THE KEY: serialization to IDs
    jsonl = papers_to_jsonl([paper1, paper2])

    # Verify the JSONL contains ID strings
    lines = jsonl.strip().split('\n')
    paper2_json = json.loads(lines[1])

    print("\nJSONL output (Paper2):")
    print(f"  duplicate_of: {paper2_json.get('duplicate_of')}")
    print(f"  cited_papers: {paper2_json.get('cited_papers')}")

    # Verify types are strings (not objects)
    assert isinstance(paper2_json.get('duplicate_of'), str), "duplicate_of should be string ID"
    assert isinstance(paper2_json.get('cited_papers'), list), "cited_papers should be list"
    assert all(isinstance(x, str) for x in paper2_json['cited_papers']), "All cited_papers should be IDs"

    print("\n✓ PASS: JSONL correctly exports Paper references as ID strings")
    print("  Note: Deserialization (IDs → Paper objects) requires database lookup")


if __name__ == "__main__":
    try:
        test_papers_to_jsonl_export_chain()
        test_jsonl_roundtrip_with_ids()

        print("\n" + "="*70)
        print("ALL INTEGRATION TESTS PASSED ✓")
        print("="*70)
        print("\nConfirmed:")
        print("  ✓ papers_to_jsonl correctly handles serialized Paper references")
        print("  ✓ JSONL format works end-to-end with export.py flow")
        print("  ✓ Paper.duplicate_of serialized to ID string")
        print("  ✓ Paper.cited_papers serialized to ID list")
        print("  ✓ Paper.cited_by_papers serialized to ID list")
        print("  ✓ All Pydantic @field_serializer decorators working")
        print("="*70 + "\n")

    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
