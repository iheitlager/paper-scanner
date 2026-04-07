"""
Test 03: Extraction Approach Comparison

Compares different extraction approaches and generates accuracy reports.

Run with: uv run pytest tests/spikes/020_parsing/test_03_comparison.py -v -s
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

# Mark entire module as spike test
pytestmark = pytest.mark.spike


@dataclass
class AccuracyMetrics:
    """Accuracy metrics for an extractor."""

    extractor: str
    total_papers: int = 0
    title_accuracy: float = 0.0
    author_accuracy: float = 0.0
    year_accuracy: float = 0.0
    journal_accuracy: float = 0.0
    doi_accuracy: float = 0.0
    overall_accuracy: float = 0.0
    total_cost_usd: float = 0.0
    avg_duration_seconds: float = 0.0
    errors: List[str] = field(default_factory=list)


def calculate_field_match(extracted: Any, expected: Any) -> float:
    """Calculate match score between extracted and expected values."""
    if expected is None:
        return 1.0 if extracted is None else 0.5

    if extracted is None:
        return 0.0

    if isinstance(expected, str) and isinstance(extracted, str):
        expected_lower = expected.lower().strip()
        extracted_lower = extracted.lower().strip()
        if expected_lower == extracted_lower:
            return 1.0
        if expected_lower in extracted_lower or extracted_lower in expected_lower:
            return 0.8
        return 0.0

    if isinstance(expected, int) and isinstance(extracted, int):
        return 1.0 if expected == extracted else 0.0

    if isinstance(expected, list) and isinstance(extracted, list):
        if not expected:
            return 1.0 if not extracted else 0.5
        if expected and isinstance(expected[0], dict) and "name" in expected[0]:
            expected_names = {a.get("name", "").lower() for a in expected}
            extracted_names = {a.get("name", "").lower() for a in extracted}
            if not expected_names:
                return 1.0
            overlap = len(expected_names & extracted_names)
            return overlap / len(expected_names)
        return 0.0

    return 0.0


def calculate_accuracy_metrics(
    results: List[Dict], ground_truth: Dict[str, Dict[str, Any]], extractor_name: str
) -> AccuracyMetrics:
    """Calculate accuracy metrics for extraction results."""
    metrics = AccuracyMetrics(extractor=extractor_name, total_papers=len(results))

    title_scores = []
    author_scores = []
    year_scores = []
    journal_scores = []
    doi_scores = []
    total_cost = 0.0
    total_duration = 0.0

    for result in results:
        if not result.get("success", True):
            metrics.errors.append(f"{result['paper_id']}: {result.get('error')}")
            continue

        expected = ground_truth.get(result["paper_id"], {})
        extracted = result.get("metadata", {})

        title_scores.append(calculate_field_match(extracted.get("title"), expected.get("title")))
        author_scores.append(calculate_field_match(extracted.get("authors"), expected.get("authors")))
        year_scores.append(calculate_field_match(extracted.get("year"), expected.get("year")))
        journal_scores.append(calculate_field_match(extracted.get("journal"), expected.get("journal")))
        doi_scores.append(calculate_field_match(extracted.get("doi"), expected.get("doi")))

        total_cost += result.get("cost_usd", 0.0)
        total_duration += result.get("duration_seconds", 0.0)

    n = len(results) - len(metrics.errors)
    if n > 0:
        metrics.title_accuracy = sum(title_scores) / n if title_scores else 0.0
        metrics.author_accuracy = sum(author_scores) / n if author_scores else 0.0
        metrics.year_accuracy = sum(year_scores) / n if year_scores else 0.0
        metrics.journal_accuracy = sum(journal_scores) / n if journal_scores else 0.0
        metrics.doi_accuracy = sum(doi_scores) / n if doi_scores else 0.0
        metrics.overall_accuracy = (
            metrics.title_accuracy
            + metrics.author_accuracy
            + metrics.year_accuracy
            + metrics.journal_accuracy
            + metrics.doi_accuracy
        ) / 5
        metrics.total_cost_usd = total_cost
        metrics.avg_duration_seconds = total_duration / n

    return metrics


# =============================================================================
# TEST CASES
# =============================================================================


class TestRegexVsGroundTruth:
    """Compare regex extraction against ground truth."""

    def test_regex_accuracy_report(self, corpus_files, ground_truth, outputs_dir):
        """Generate accuracy report for regex extractor."""
        # Import here to avoid circular imports
        from test_01_regex_extractor import RegexExtractor

        extractor = RegexExtractor()
        extraction_results = extractor.extract_all(corpus_files)

        # Convert to dict format for comparison
        results = [
            {
                "paper_id": r.paper_id,
                "metadata": r.metadata,
                "success": r.success,
                "error": r.error,
                "duration_seconds": r.duration_seconds,
            }
            for r in extraction_results
        ]

        metrics = calculate_accuracy_metrics(results, ground_truth, "regex")

        print("\n" + "=" * 60)
        print("REGEX EXTRACTOR ACCURACY REPORT")
        print("=" * 60)
        print(f"Total papers: {metrics.total_papers}")
        print(f"Errors: {len(metrics.errors)}")
        print(f"\nField Accuracy:")
        print(f"  Title:   {metrics.title_accuracy:.1%}")
        print(f"  Authors: {metrics.author_accuracy:.1%}")
        print(f"  Year:    {metrics.year_accuracy:.1%}")
        print(f"  Journal: {metrics.journal_accuracy:.1%}")
        print(f"  DOI:     {metrics.doi_accuracy:.1%}")
        print(f"\nOverall:   {metrics.overall_accuracy:.1%}")
        print(f"Avg time:  {metrics.avg_duration_seconds:.3f}s")

        # Save report
        report = {
            "extractor": metrics.extractor,
            "total_papers": metrics.total_papers,
            "title_accuracy": metrics.title_accuracy,
            "author_accuracy": metrics.author_accuracy,
            "year_accuracy": metrics.year_accuracy,
            "journal_accuracy": metrics.journal_accuracy,
            "doi_accuracy": metrics.doi_accuracy,
            "overall_accuracy": metrics.overall_accuracy,
            "total_cost_usd": metrics.total_cost_usd,
            "avg_duration_seconds": metrics.avg_duration_seconds,
            "errors": metrics.errors,
            "raw_results": results,
        }

        report_path = outputs_dir / "regex_accuracy_report.json"
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2, default=str)

        print(f"\nReport saved to: {report_path}")


@pytest.mark.requires_api
@pytest.mark.slow
class TestClaudeVsGroundTruth:
    """Compare Claude extraction against ground truth."""

    def test_haiku_accuracy_report(self, corpus_files, ground_truth, outputs_dir, anthropic_api_key):
        """Generate accuracy report for Claude Haiku extractor."""
        from test_02_claude_extractor import ClaudeExtractor

        extractor = ClaudeExtractor(
            model="claude-haiku-4-5-20251001",
            api_key=anthropic_api_key
        )
        extraction_results = extractor.extract_all(corpus_files)

        results = [
            {
                "paper_id": r.paper_id,
                "metadata": r.metadata,
                "success": r.success,
                "error": r.error,
                "duration_seconds": r.duration_seconds,
                "cost_usd": r.cost_usd,
            }
            for r in extraction_results
        ]

        metrics = calculate_accuracy_metrics(results, ground_truth, "claude_haiku")

        print("\n" + "=" * 60)
        print("CLAUDE HAIKU ACCURACY REPORT")
        print("=" * 60)
        print(f"Total papers: {metrics.total_papers}")
        print(f"Total cost: ${metrics.total_cost_usd:.4f}")
        print(f"\nField Accuracy:")
        print(f"  Title:   {metrics.title_accuracy:.1%}")
        print(f"  Authors: {metrics.author_accuracy:.1%}")
        print(f"  Year:    {metrics.year_accuracy:.1%}")
        print(f"  Journal: {metrics.journal_accuracy:.1%}")
        print(f"  DOI:     {metrics.doi_accuracy:.1%}")
        print(f"\nOverall:   {metrics.overall_accuracy:.1%}")

        report = {
            "extractor": metrics.extractor,
            "total_papers": metrics.total_papers,
            "title_accuracy": metrics.title_accuracy,
            "author_accuracy": metrics.author_accuracy,
            "year_accuracy": metrics.year_accuracy,
            "journal_accuracy": metrics.journal_accuracy,
            "doi_accuracy": metrics.doi_accuracy,
            "overall_accuracy": metrics.overall_accuracy,
            "total_cost_usd": metrics.total_cost_usd,
            "avg_duration_seconds": metrics.avg_duration_seconds,
            "raw_results": results,
        }

        report_path = outputs_dir / "claude_haiku_accuracy_report.json"
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2, default=str)

        print(f"\nReport saved to: {report_path}")


class TestComparisonSummary:
    """Generate combined comparison summary."""

    def test_generate_comparison_summary(self, corpus_files, ground_truth, outputs_dir):
        """Generate comparison summary from all approaches."""
        from test_01_regex_extractor import RegexExtractor

        # Run regex extractor
        regex_extractor = RegexExtractor()
        regex_results = regex_extractor.extract_all(corpus_files)
        regex_data = [
            {
                "paper_id": r.paper_id,
                "metadata": r.metadata,
                "success": r.success,
                "duration_seconds": r.duration_seconds,
            }
            for r in regex_results
        ]
        regex_metrics = calculate_accuracy_metrics(regex_data, ground_truth, "regex")

        # Build summary
        summary = {
            "corpus_size": len(corpus_files),
            "approaches": [
                {
                    "name": "regex",
                    "description": "PyPDF + regex patterns",
                    "overall_accuracy": regex_metrics.overall_accuracy,
                    "title_accuracy": regex_metrics.title_accuracy,
                    "year_accuracy": regex_metrics.year_accuracy,
                    "doi_accuracy": regex_metrics.doi_accuracy,
                    "cost_per_paper": 0.0,
                    "avg_time_seconds": regex_metrics.avg_duration_seconds,
                }
            ],
            "recommendations": [],
        }

        # Add recommendations based on results
        if regex_metrics.overall_accuracy >= 0.8:
            summary["recommendations"].append(
                "Regex extraction achieves good accuracy. Consider as primary approach."
            )
        else:
            summary["recommendations"].append(
                "Regex accuracy is low. Consider Claude API for better results."
            )

        # Check for Claude results if available
        haiku_report = outputs_dir / "claude_haiku_accuracy_report.json"
        if haiku_report.exists():
            with open(haiku_report) as f:
                haiku_data = json.load(f)
            summary["approaches"].append({
                "name": "claude_haiku",
                "description": "Claude Haiku API",
                "overall_accuracy": haiku_data.get("overall_accuracy", 0),
                "title_accuracy": haiku_data.get("title_accuracy", 0),
                "year_accuracy": haiku_data.get("year_accuracy", 0),
                "doi_accuracy": haiku_data.get("doi_accuracy", 0),
                "cost_per_paper": haiku_data.get("total_cost_usd", 0) / max(haiku_data.get("total_papers", 1), 1),
                "avg_time_seconds": haiku_data.get("avg_duration_seconds", 0),
            })

        # Print summary
        print("\n" + "=" * 70)
        print("EXTRACTION APPROACH COMPARISON SUMMARY")
        print("=" * 70)
        print(f"Corpus size: {summary['corpus_size']} papers\n")

        print(f"{'Approach':<15} {'Overall':<10} {'Title':<10} {'Year':<10} {'DOI':<10} {'Cost':<10}")
        print("-" * 70)
        for approach in summary["approaches"]:
            print(
                f"{approach['name']:<15} "
                f"{approach['overall_accuracy']:.1%}     "
                f"{approach['title_accuracy']:.1%}     "
                f"{approach['year_accuracy']:.1%}     "
                f"{approach['doi_accuracy']:.1%}     "
                f"${approach['cost_per_paper']:.4f}"
            )

        print("\nRecommendations:")
        for rec in summary["recommendations"]:
            print(f"  - {rec}")

        # Save summary
        summary_path = outputs_dir / "comparison_summary.json"
        with open(summary_path, "w") as f:
            json.dump(summary, f, indent=2)

        print(f"\nSummary saved to: {summary_path}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
