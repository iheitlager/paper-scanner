"""
Test 004: Comparison and Accuracy Analysis

This test compares the results from all three classification methods
and generates accuracy metrics, latency comparisons, and recommendations.
"""

import json
import sys
from pathlib import Path
from typing import Dict

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))


def load_results(results_file: str) -> Dict:
    """Load results from a JSON file."""
    try:
        with open(results_file, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading {results_file}: {e}")
        return {}


def compare_classifications(results_dict: Dict[str, Dict]) -> Dict:
    """
    Compare classifications across methods for each paper.
    """
    # Get all filenames from first method
    if not results_dict or "regex" not in results_dict:
        return {}

    filenames = {p["filename"] for p in results_dict["regex"]["papers"]}

    comparison = {}
    for filename in filenames:
        comparison[filename] = {}

        for method, results in results_dict.items():
            paper = next(
                (p for p in results["papers"] if p["filename"] == filename),
                None
            )
            if paper:
                comparison[filename][method] = {
                    "study_type": paper.get("study_type"),
                    "confidence": paper.get("confidence", 1.0),  # Regex has no confidence
                    "latency_ms": paper.get("latency_ms"),
                }

    return comparison


def calculate_agreement_metrics(comparison: Dict) -> Dict:
    """Calculate how much methods agree with each other."""
    if not comparison:
        return {}

    len(comparison)
    methods = list(next(iter(comparison.values())).keys())

    # Count agreements
    pairwise_agreements = {}
    for paper_data in comparison.values():
        [paper_data[m]["study_type"] for m in methods]

        for i, m1 in enumerate(methods):
            for m2 in methods[i+1:]:
                pair = f"{m1}_vs_{m2}"
                if pair not in pairwise_agreements:
                    pairwise_agreements[pair] = {"agree": 0, "total": 0}

                pairwise_agreements[pair]["total"] += 1
                if paper_data[m1]["study_type"] == paper_data[m2]["study_type"]:
                    pairwise_agreements[pair]["agree"] += 1

    # Convert to percentages
    agreement_percentages = {}
    for pair, counts in pairwise_agreements.items():
        if counts["total"] > 0:
            agreement_percentages[pair] = (
                counts["agree"] / counts["total"] * 100
            )

    return agreement_percentages


def analyze_latency(results_dict: Dict[str, Dict]) -> Dict:
    """Analyze latency across methods."""
    latency_stats = {}

    for method, results in results_dict.items():
        latencies = [p["latency_ms"] for p in results["papers"]]

        if latencies:
            latency_stats[method] = {
                "min_ms": min(latencies),
                "max_ms": max(latencies),
                "avg_ms": sum(latencies) / len(latencies),
                "total_ms": sum(latencies),
                "papers": len(latencies),
            }

            # Add model load time if present
            if "model_load_time_ms" in results:
                latency_stats[method]["model_load_ms"] = results["model_load_time_ms"]
                latency_stats[method]["total_with_load_ms"] = (
                    latency_stats[method]["total_ms"] + results["model_load_time_ms"]
                )

    return latency_stats


def generate_report(
    comparison: Dict,
    agreement: Dict,
    latency_stats: Dict,
) -> Dict:
    """Generate comprehensive analysis report."""
    report = {
        "timestamp": Path(__file__).stat().st_mtime,
        "total_papers": len(comparison),
        "methods_compared": list(latency_stats.keys()),
        "agreement_metrics": agreement,
        "latency_analysis": latency_stats,
        "paper_classifications": comparison,
        "recommendations": [],
    }

    # Generate recommendations
    if "regex" in latency_stats:
        regex_latency = latency_stats["regex"]["avg_ms"]
    else:
        regex_latency = float("inf")

    if "embedding" in latency_stats:
        embedding_latency = latency_stats["embedding"]["avg_ms"]
    else:
        embedding_latency = float("inf")

    if "ollama" in latency_stats:
        ollama_latency = latency_stats["ollama"]["avg_ms"]
    else:
        ollama_latency = float("inf")

    # Speed ranking
    methods_by_speed = sorted(
        latency_stats.items(),
        key=lambda x: x[1]["avg_ms"]
    )

    report["speed_ranking"] = [m[0] for m in methods_by_speed]

    # Recommendations
    if regex_latency < 100:
        report["recommendations"].append(
            "Regex method is extremely fast (<100ms) - suitable for real-time use"
        )

    if embedding_latency < 2000 and embedding_latency > regex_latency:
        report["recommendations"].append(
            "Embedding method provides good balance of speed and semantic understanding"
        )

    if ollama_latency > 5000:
        report["recommendations"].append(
            "Ollama is slower - suitable only for batch processing or non-real-time workflows"
        )

    # Check for agreement
    if agreement:
        avg_agreement = sum(agreement.values()) / len(agreement)
        if avg_agreement > 70:
            report["recommendations"].append(
                f"Methods show good agreement (avg {avg_agreement:.1f}%) - ensemble approach viable"
            )
        else:
            report["recommendations"].append(
                f"Low agreement between methods (avg {avg_agreement:.1f}%) - methods capture different aspects"
            )

    return report


def format_report_markdown(report: Dict) -> str:
    """Format report as markdown."""
    md = "# Spike 012: Comparison and Accuracy Analysis\n\n"

    md += "## Summary\n"
    md += f"- Papers analyzed: {report['total_papers']}\n"
    md += f"- Methods compared: {', '.join(report['methods_compared'])}\n\n"

    md += "## Speed Ranking\n"
    for i, method in enumerate(report["speed_ranking"], 1):
        stats = report["latency_analysis"].get(method, {})
        avg_latency = stats.get("avg_ms", 0)
        md += f"{i}. **{method}**: {avg_latency:.1f}ms avg per paper\n"

    md += "\n## Detailed Latency Analysis\n"
    md += "| Method | Min | Max | Avg | Total (w/o load) |\n"
    md += "|--------|-----|-----|-----|------------------|\n"

    for method, stats in report["latency_analysis"].items():
        min_ms = stats.get("min_ms", 0)
        max_ms = stats.get("max_ms", 0)
        avg_ms = stats.get("avg_ms", 0)
        total_ms = stats.get("total_ms", 0)
        md += f"| {method} | {min_ms:.1f}ms | {max_ms:.1f}ms | {avg_ms:.1f}ms | {total_ms:.1f}ms |\n"

    md += "\n## Inter-Method Agreement\n"
    for pair, agreement_pct in report["agreement_metrics"].items():
        md += f"- **{pair}**: {agreement_pct:.1f}% agreement\n"

    md += "\n## Paper Classifications\n"
    md += "| File | Regex | Embedding | Ollama |\n"
    md += "|------|-------|-----------|--------|\n"

    for filename, classifications in report["paper_classifications"].items():
        short_name = filename[:30] + "..." if len(filename) > 30 else filename
        regex_type = classifications.get("regex", {}).get("study_type", "?")
        embedding_type = classifications.get("embedding", {}).get("study_type", "?")
        ollama_type = classifications.get("ollama", {}).get("study_type", "?")
        md += f"| {short_name} | {regex_type} | {embedding_type} | {ollama_type} |\n"

    md += "\n## Recommendations\n"
    for rec in report["recommendations"]:
        md += f"- {rec}\n"

    return md


def save_report(report: Dict, markdown: str, output_dir: str):
    """Save report in JSON and markdown formats."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Save JSON
    json_file = output_path / "accuracy_report.json"
    with open(json_file, "w") as f:
        json.dump(report, f, indent=2)
    print(f"✓ JSON report saved to {json_file}")

    # Save markdown
    md_file = output_path / "accuracy_report.md"
    with open(md_file, "w") as f:
        f.write(markdown)
    print(f"✓ Markdown report saved to {md_file}")


def main():
    """Run comparison analysis."""
    print("=" * 60)
    print("TEST 004: Comparison and Accuracy Analysis")
    print("=" * 60)

    output_dir = Path(__file__).parent / "outputs"

    # Load results from all methods
    results_dict = {
        "regex": load_results(str(output_dir / "results_001_regex.json")),
        "embedding": load_results(str(output_dir / "results_002_embedding.json")),
        "ollama": load_results(str(output_dir / "results_003_ollama.json")),
    }

    # Filter out empty results
    results_dict = {k: v for k, v in results_dict.items() if v}

    if not results_dict:
        print("❌ No results found. Run tests 001-003 first.")
        return

    print(f"\n✓ Loaded results from {len(results_dict)} methods\n")

    # Generate comparison
    comparison = compare_classifications(results_dict)
    agreement = calculate_agreement_metrics(comparison)
    latency_stats = analyze_latency(results_dict)

    # Generate report
    report = generate_report(comparison, agreement, latency_stats)
    markdown = format_report_markdown(report)

    # Display summary
    print(markdown)

    # Save report
    save_report(report, markdown, str(output_dir))

    return report


if __name__ == "__main__":
    report = main()
