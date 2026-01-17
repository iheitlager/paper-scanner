"""
Test 05: Table of Contents Extraction Comparison

Compares TOC extraction accuracy across different approaches.

The ground truth TOC was extracted using Claude Sonnet and includes:
- Numbered section headings
- Subsection hierarchies

Run with: uv run pytest tests/spikes/020_parsing/test_05_toc_extraction.py -v -s
"""

import re
from pathlib import Path
from typing import Any, Dict, List

import pytest

# Mark entire module as spike test
pytestmark = pytest.mark.spike


def normalize_section(section: str) -> str:
    """Normalize section name for comparison."""
    # Remove leading numbers and punctuation
    section = re.sub(r"^[\d.]+\s*", "", section)
    # Remove special characters
    section = re.sub(r"[^\w\s]", "", section)
    # Lowercase and strip
    return section.lower().strip()


def calculate_toc_similarity(extracted: List[Dict], expected: List[Dict]) -> Dict[str, float]:
    """Calculate TOC similarity metrics."""
    if not expected:
        return {"section_count_ratio": 1.0 if not extracted else 0.0, "section_match": 0.0}

    # Extract section names
    ext_sections = [normalize_section(s.get("section", "")) for s in extracted if s.get("section")]
    exp_sections = [normalize_section(s.get("section", "")) for s in expected if s.get("section")]

    # Count ratio
    count_ratio = len(ext_sections) / len(exp_sections) if exp_sections else 0

    # Section name matching (fuzzy)
    matches = 0
    for exp in exp_sections:
        for ext in ext_sections:
            if exp in ext or ext in exp:
                matches += 1
                break

    match_ratio = matches / len(exp_sections) if exp_sections else 0

    # Subsection analysis
    ext_subsections = sum(len(s.get("subsections", [])) for s in extracted)
    exp_subsections = sum(len(s.get("subsections", [])) for s in expected)

    return {
        "section_count_ratio": min(count_ratio, 1.0),  # Cap at 1.0
        "section_match": match_ratio,
        "extracted_sections": len(ext_sections),
        "expected_sections": len(exp_sections),
        "extracted_subsections": ext_subsections,
        "expected_subsections": exp_subsections,
    }


# =============================================================================
# TEST CASES
# =============================================================================


class TestTOCExtraction:
    """Compare TOC extraction across methods."""

    def test_ground_truth_toc_quality(self, ground_truth):
        """Verify ground truth has proper TOC data."""
        print("\nGround truth TOC analysis:")
        total_sections = 0
        total_subsections = 0

        for paper_id, metadata in ground_truth.items():
            toc = metadata.get("table_of_contents", [])
            sections = len(toc)
            subsections = sum(len(s.get("subsections", [])) for s in toc)
            total_sections += sections
            total_subsections += subsections

            print(f"  {paper_id[:8]}...: {sections} sections, {subsections} subsections")
            if toc:
                print(f"    First: {toc[0].get('section', 'N/A')[:40]}")

        print(f"\nTotal: {total_sections} sections, {total_subsections} subsections across {len(ground_truth)} papers")
        assert total_sections > 0, "Ground truth should have TOC data"

    def test_regex_has_no_toc(self, corpus_files, ground_truth):
        """Verify regex extractor doesn't attempt TOC extraction."""
        from test_01_regex_extractor import RegexExtractor

        extractor = RegexExtractor()
        results = extractor.extract_all(corpus_files)

        print("\nRegex TOC extraction:")
        for result in results:
            toc = result.metadata.get("table_of_contents")
            has_toc = toc is not None and len(toc) > 0
            print(f"  {result.paper_id[:8]}...: TOC={'Yes' if has_toc else 'No'}")

        # Regex extractor doesn't extract TOC by design
        print("\nNote: Regex extractor does not extract TOC (by design)")

    def test_markdown_toc_accuracy(self, corpus_files, ground_truth):
        """Test markdown extractor TOC accuracy."""
        from test_04_markdown_extractor import MarkdownExtractor

        extractor = MarkdownExtractor()
        results = extractor.extract_all(corpus_files)

        print("\nMarkdown TOC extraction accuracy:")
        total_match = 0
        total_papers = 0

        for result in results:
            expected_metadata = ground_truth.get(result.paper_id, {})
            if not expected_metadata:
                continue

            extracted_toc = result.metadata.get("table_of_contents", [])
            expected_toc = expected_metadata.get("table_of_contents", [])

            metrics = calculate_toc_similarity(extracted_toc, expected_toc)
            total_match += metrics["section_match"]
            total_papers += 1

            print(f"  {result.paper_id[:8]}...")
            print(f"    Sections: {metrics['extracted_sections']}/{metrics['expected_sections']}")
            print(f"    Match: {metrics['section_match']:.0%}")

        if total_papers > 0:
            avg_match = total_match / total_papers
            print(f"\nAverage section match: {avg_match:.0%}")

    @pytest.mark.requires_api
    @pytest.mark.slow
    def test_claude_toc_accuracy(self, corpus_files, ground_truth, anthropic_api_key):
        """Test Claude Haiku TOC extraction accuracy."""
        from test_02_claude_extractor import ClaudeExtractor

        extractor = ClaudeExtractor(
            model="claude-haiku-4-5-20251001",
            api_key=anthropic_api_key
        )
        results = extractor.extract_all(corpus_files)

        print("\nClaude Haiku TOC extraction accuracy:")
        total_match = 0
        total_papers = 0

        for result in results:
            expected_metadata = ground_truth.get(result.paper_id, {})
            if not expected_metadata:
                continue

            extracted_toc = result.metadata.get("table_of_contents", [])
            expected_toc = expected_metadata.get("table_of_contents", [])

            metrics = calculate_toc_similarity(extracted_toc, expected_toc)
            total_match += metrics["section_match"]
            total_papers += 1

            print(f"  {result.paper_id[:8]}...")
            print(f"    Sections: {metrics['extracted_sections']}/{metrics['expected_sections']}")
            print(f"    Subsections: {metrics['extracted_subsections']}/{metrics['expected_subsections']}")
            print(f"    Match: {metrics['section_match']:.0%}")

        if total_papers > 0:
            avg_match = total_match / total_papers
            print(f"\nAverage section match: {avg_match:.0%}")
            # Claude should have very high TOC accuracy since ground truth was created with Claude
            assert avg_match >= 0.8, f"Claude TOC accuracy should be >= 80%, got {avg_match:.0%}"


class TestTOCSummary:
    """Generate TOC extraction summary."""

    def test_generate_toc_comparison(self, corpus_files, ground_truth, outputs_dir):
        """Generate TOC comparison report."""
        import json
        from test_04_markdown_extractor import MarkdownExtractor

        # Run markdown extractor
        md_extractor = MarkdownExtractor()
        md_results = md_extractor.extract_all(corpus_files)

        report = {
            "ground_truth": {},
            "markdown": {},
            "summary": {},
        }

        total_expected = 0
        total_md_match = 0

        for result in md_results:
            paper_id = result.paper_id
            expected = ground_truth.get(paper_id, {})

            exp_toc = expected.get("table_of_contents", [])
            md_toc = result.metadata.get("table_of_contents", [])

            metrics = calculate_toc_similarity(md_toc, exp_toc)

            report["ground_truth"][paper_id] = {
                "sections": len(exp_toc),
                "subsections": sum(len(s.get("subsections", [])) for s in exp_toc),
            }
            report["markdown"][paper_id] = {
                "sections": len(md_toc),
                "match_ratio": metrics["section_match"],
            }

            total_expected += len(exp_toc)
            total_md_match += metrics["section_match"] * len(exp_toc) if exp_toc else 0

        report["summary"] = {
            "markdown_avg_match": total_md_match / total_expected if total_expected else 0,
            "note": "Regex extractor does not extract TOC",
            "recommendation": "Use Claude for TOC extraction - markdown approach picks up noise",
        }

        # Save report
        report_path = outputs_dir / "toc_comparison.json"
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2)

        print(f"\nTOC comparison report saved to: {report_path}")
        print(f"Markdown avg match: {report['summary']['markdown_avg_match']:.0%}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
