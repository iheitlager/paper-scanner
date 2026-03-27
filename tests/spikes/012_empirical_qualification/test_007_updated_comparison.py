"""
Test 007: Updated Comparison and Accuracy Analysis

This test compares results from all methods including the new enhanced regex
and Claude Sonnet 4.5 classifications against the ground truth from eight_cases.bib.
"""

import json
import sys
from pathlib import Path
from typing import Dict, List

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))


# Ground truth from eight_cases.bib
GROUND_TRUTH = {
    "0c288904-15b6-c0e3-18fd-52fd67393ebe.pdf": {
        "study_type": "case_study",
        "title": "Digital Transformation of Incumbent Pipeline Firms through Platformization",
        "keywords": ["Digital platformization", "digital transformation", "structural modeling"],
        "note": "Empirical case studies - starts with lit review but adds new empirical context",
    },
    "0e20b252-374a-8055-3ce5-67225751e3ce.pdf": {
        "study_type": "conceptual",
        "title": "Digital transformation requires digital resource primacy",
        "keywords": ["Digital ontology", "Digital organization", "Digital resources"],
        "note": "Commentary/conceptual piece",
    },
    "17af2c40-3c32-fc5f-7937-f73141ea979a.pdf": {
        "study_type": "case_study",
        "title": "Implementing a Digital Strategy: Learning from the Experience of Three Digital Transformation Projects",
        "keywords": ["digital strategy", "digital transformation", "strategy implementation"],
        "note": "3 case studies",
    },
    "4f71d2ca-999b-a1ed-1c5a-0e67ce61efb6.pdf": {
        "study_type": "case_study",
        "title": "Digital Transformation of Incumbent Firms: A Business Model Innovation Perspective",
        "keywords": ["Business model innovation", "digital transformation", "digitalization"],
        "note": "15 cases",
    },
    "5c8f6a9b-1772-8597-7e4c-7ebc1db9229e.pdf": {
        "study_type": "editorial",
        "title": "Leading digital transformation in incumbent firms: A strategic entrepreneurship framing",
        "keywords": ["business models", "dynamic capability", "strategy"],
    },
    "5f3b02b4-e497-39bf-2339-4c3c0a55968e.pdf": {
        "study_type": "literature_review",
        "title": "A survey on incumbent digital transformation: a paradoxical perspective and research agenda",
        "keywords": ["Computational literature review", "Digital transformation", "Systematic literature review"],
    },
    "639d1860-e441-e167-2966-721eb39d96f6.pdf": {
        "study_type": "qualitative",
        "title": "Digital transformation in incumbent companies: a qualitative study",
        "keywords": ["Digital transformation", "Exploration", "Exploitation"],
        "note": "33 semi-structured interviews",
    },
    "77ecffcd-fc1d-15df-525c-ffcaec251e82.pdf": {
        "study_type": "qualitative",
        "title": "Managing start-up–incumbent digital solution co-creation",
        "keywords": ["Tension mitigation", "digitalisation", "innovation orchestration"],
        "note": "2 intermediaries, 5 incumbents, 11 start-ups",
    },
}


def load_results(results_file: str) -> Dict:
    """Load results from a JSON file."""
    try:
        with open(results_file, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading {results_file}: {e}")
        return {}


def calculate_accuracy(results: Dict, method_name: str) -> Dict:
    """Calculate accuracy against ground truth."""
    correct = 0
    total = 0
    mismatches = []

    for paper in results.get("papers", []):
        filename = paper["filename"]
        if filename in GROUND_TRUTH:
            expected = GROUND_TRUTH[filename]["study_type"]
            actual = paper.get("study_type", "unknown")

            total += 1
            if expected == actual:
                correct += 1
            else:
                mismatches.append({
                    "filename": filename,
                    "expected": expected,
                    "actual": actual,
                    "confidence": paper.get("confidence", "N/A"),
                })

    accuracy = (correct / total * 100) if total > 0 else 0

    return {
        "method": method_name,
        "correct": correct,
        "total": total,
        "accuracy": accuracy,
        "mismatches": mismatches,
    }


def generate_comparison_table(accuracy_results: List[Dict]) -> str:
    """Generate markdown table comparing methods."""
    table = "# Updated Comparison: All Methods vs Ground Truth\n\n"
    table += "## Accuracy Summary\n\n"
    table += "| Method | Correct | Total | Accuracy |\n"
    table += "|--------|---------|-------|----------|\n"

    for result in sorted(accuracy_results, key=lambda x: x["accuracy"], reverse=True):
        method = result["method"]
        correct = result["correct"]
        total = result["total"]
        accuracy = result["accuracy"]
        table += f"| {method} | {correct}/{total} | {total} | {accuracy:.1f}% |\n"

    table += "\n## Paper-by-Paper Comparison\n\n"
    table += "| Paper | Ground Truth | Regex | Enhanced Regex | Embedding | Ollama | Claude |\n"
    table += "|-------|--------------|-------|----------------|-----------|--------|--------|\n"

    # Get all papers from ground truth
    for filename, gt_data in GROUND_TRUTH.items():
        short_name = filename[:8]
        gt_type = gt_data["study_type"]

        row = f"| {short_name} | **{gt_type}** |"

        # Find classification for each method
        for result in accuracy_results:
            method_type = "unknown"
            for paper in result.get("papers", []):
                if paper["filename"] == filename:
                    method_type = paper.get("study_type", "unknown")
                    break

            # Mark correct matches
            if method_type == gt_type:
                row += f" ✓ {method_type} |"
            else:
                row += f" ✗ {method_type} |"

        table += row + "\n"

    return table


def generate_detailed_report(accuracy_results: List[Dict]) -> str:
    """Generate detailed analysis report."""
    report = "\n## Detailed Analysis\n\n"

    # Best performing method
    best = max(accuracy_results, key=lambda x: x["accuracy"])
    report += f"### Best Performing Method: {best['method']}\n"
    report += f"- Accuracy: {best['accuracy']:.1f}%\n"
    report += f"- Correct: {best['correct']}/{best['total']}\n\n"

    # Mismatches by method
    for result in accuracy_results:
        if result["mismatches"]:
            report += f"### {result['method']} Mismatches\n\n"
            for mismatch in result["mismatches"]:
                short_name = mismatch["filename"][:8]
                expected = mismatch["expected"]
                actual = mismatch["actual"]
                confidence = mismatch.get("confidence", "N/A")
                gt_note = GROUND_TRUTH[mismatch["filename"]].get("note", "")

                report += f"- **{short_name}**: Expected `{expected}`, got `{actual}`"
                if confidence != "N/A":
                    report += f" (confidence: {confidence})"
                if gt_note:
                    report += f" - Note: {gt_note}"
                report += "\n"
            report += "\n"

    return report


def main():
    """Run updated comparison analysis."""
    print("=" * 70)
    print("TEST 007: Updated Comparison and Accuracy Analysis")
    print("=" * 70)

    output_dir = Path(__file__).parent / "outputs"

    # Load all results
    methods = [
        ("Regex (Original)", "results_001_regex.json"),
        ("Enhanced Regex", "results_005_enhanced_regex.json"),
        ("Sentence Embedding", "results_002_embedding.json"),
        ("Ollama (phi3:mini)", "results_003_ollama.json"),
        ("Claude Sonnet 4.5", "results_006_claude.json"),
    ]

    accuracy_results = []
    all_results = {}

    for method_name, filename in methods:
        results_path = output_dir / filename
        if results_path.exists():
            print(f"✓ Loading {method_name} from {filename}")
            results = load_results(str(results_path))
            all_results[method_name] = results

            # Calculate accuracy
            accuracy = calculate_accuracy(results, method_name)
            accuracy["papers"] = results.get("papers", [])
            accuracy_results.append(accuracy)
        else:
            print(f"⚠️  {method_name} results not found: {filename}")

    if not accuracy_results:
        print("\n❌ No results found. Please run tests 001, 002, 003, 005, and 006 first.")
        return

    # Generate comparison table
    print("\n" + "=" * 70)
    print("ACCURACY COMPARISON")
    print("=" * 70)

    comparison_table = generate_comparison_table(accuracy_results)
    detailed_report = generate_detailed_report(accuracy_results)

    # Print to console
    print(comparison_table)
    print(detailed_report)

    # Save markdown report
    report_md = comparison_table + detailed_report
    report_path = output_dir / "comparison_report.md"
    with open(report_path, "w") as f:
        f.write(report_md)
    print(f"✓ Markdown report saved to {report_path}")

    # Save JSON report
    json_report = {
        "timestamp": json.load(open(output_dir / "results_001_regex.json"))["timestamp"],
        "ground_truth": GROUND_TRUTH,
        "accuracy_results": accuracy_results,
        "methods": [r["method"] for r in accuracy_results],
    }

    json_path = output_dir / "comparison_report.json"
    with open(json_path, "w") as f:
        json.dump(json_report, f, indent=2)
    print(f"✓ JSON report saved to {json_path}")

    # Print summary statistics
    print("\n" + "=" * 70)
    print("SUMMARY STATISTICS")
    print("=" * 70)

    for result in sorted(accuracy_results, key=lambda x: x["accuracy"], reverse=True):
        print(f"{result['method']:.<40} {result['accuracy']:.1f}%")

    print("\n🎯 Winner:", max(accuracy_results, key=lambda x: x["accuracy"])["method"])


if __name__ == "__main__":
    main()
