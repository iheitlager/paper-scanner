"""
Test 006: Claude Sonnet 4.5 Classification

This test uses Claude Sonnet 4.5 (via Anthropic API) to classify papers by study type.
Claude can process PDF files directly, providing high-quality classification based on
document understanding.

Advantages over Ollama:
- Direct PDF processing (no text extraction needed)
- Faster inference
- More reliable classifications
- Better instruction following
"""

import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, Tuple

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

try:
    from paper_scanner.models.anthropic import ClaudeHandler
except ImportError:
    print("Error: Cannot import ClaudeHandler from paper_scanner.models.anthropic")
    sys.exit(1)

try:
    from dotenv import load_dotenv
except ImportError:
    print("Installing python-dotenv...")
    import subprocess
    subprocess.check_call(["pip", "install", "python-dotenv"])
    from dotenv import load_dotenv


def get_api_key() -> str:
    """Get Anthropic API key from environment."""
    # Load from .env file
    load_dotenv()

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError(
            "ANTHROPIC_API_KEY not found in environment. "
            "Please add it to .env file or set as environment variable."
        )
    return api_key


def classify_paper_claude(pdf_path: str, handler: ClaudeHandler) -> Tuple[str, str, float]:
    """
    Classify paper using Claude Sonnet 4.5.

    Args:
        pdf_path: Path to PDF file
        handler: ClaudeHandler instance

    Returns:
        (study_type, reasoning, latency_ms)
    """
    system_prompt = """You are an expert academic researcher analyzing research papers.
Your task is to classify the paper's study type based on its methodology and content.

Study types:
- qualitative: Research using interviews, observations, case studies with qualitative analysis
- case_study: Research examining specific cases or examples (may include quantitative data)
- quantitative: Research using statistical analysis, numerical data, hypothesis testing
- mixed_methods: Research combining qualitative and quantitative methods
- literature_review: Systematic review, meta-analysis, or literature synthesis
- editorial: Editor's commentary, perspective piece, or opinion article
- conceptual: Theoretical framework, conceptual model, or definitional work

Instructions:
1. Analyze the paper's abstract, introduction, and methodology
2. Identify the primary research approach
3. Respond ONLY with valid JSON in this exact format:

{
  "study_type": "one of the study types above",
  "reasoning": "brief explanation of classification",
  "confidence": "high|medium|low"
}

Be precise and concise."""

    start_time = time.time()

    try:
        result, token_usage = handler.call(
            text=str(pdf_path),  # Claude handler will detect PDF and encode it
            system_prompt=system_prompt,
            max_tokens=500,
        )

        latency_ms = (time.time() - start_time) * 1000

        if result:
            study_type = result.get("study_type", "unknown")
            reasoning = result.get("reasoning", "No reasoning provided")
            confidence = result.get("confidence", "unknown")
            return study_type, reasoning, latency_ms, confidence, token_usage
        else:
            return "unknown", "Failed to parse response", latency_ms, "low", token_usage

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000
        print(f"Error classifying {pdf_path}: {e}")
        return "unknown", f"Error: {str(e)}", latency_ms, "low", {"input_tokens": 0, "output_tokens": 0}


def process_pdfs_claude() -> Dict:
    """Process all PDFs using Claude Sonnet 4.5."""
    test_data_dir = Path(__file__).parent.parent.parent / "data"
    pdf_files = sorted(test_data_dir.glob("*.pdf"))

    # Initialize Claude handler
    api_key = get_api_key()
    handler = ClaudeHandler(api_key=api_key, model="claude-sonnet-4-5-20250929")

    results = {
        "method": "claude_sonnet_4_5",
        "model": "claude-sonnet-4-5-20250929",
        "timestamp": time.time(),
        "papers_processed": 0,
        "papers": [],
        "total_latency_ms": 0,
        "total_input_tokens": 0,
        "total_output_tokens": 0,
    }

    print(f"Processing {len(pdf_files)} PDFs with Claude Sonnet 4.5...")
    print("Ground truth from eight_cases.bib:")
    print("  0c288904: case study (empirical with case studies)")
    print("  0e20b252: commentary/conceptual")
    print("  17af2c40: case study")
    print("  4f71d2ca: case study")
    print("  5c8f6a9b: editorial")
    print("  5f3b02b4: literature review")
    print("  639d1860: qualitative study")
    print("  77ecffcd: qualitative study")
    print()

    for pdf_path in pdf_files:
        print(f"Processing {pdf_path.name}...")

        study_type, reasoning, latency_ms, confidence, token_usage = classify_paper_claude(
            str(pdf_path), handler
        )

        paper_result = {
            "filename": pdf_path.name,
            "study_type": study_type,
            "reasoning": reasoning,
            "confidence": confidence,
            "latency_ms": latency_ms,
            "input_tokens": token_usage["input_tokens"],
            "output_tokens": token_usage["output_tokens"],
        }

        results["papers"].append(paper_result)
        results["papers_processed"] += 1
        results["total_latency_ms"] += latency_ms
        results["total_input_tokens"] += token_usage["input_tokens"]
        results["total_output_tokens"] += token_usage["output_tokens"]

        print(f"✓ {pdf_path.name}: {study_type} ({confidence} confidence) | {latency_ms:.1f}ms")
        print(f"  Reasoning: {reasoning[:100]}...")
        print(f"  Tokens: {token_usage['input_tokens']} in, {token_usage['output_tokens']} out")

    results["avg_latency_ms"] = (
        results["total_latency_ms"] / results["papers_processed"]
        if results["papers_processed"] > 0
        else 0
    )

    return results


def save_results(results: Dict, output_path: str):
    """Save results to JSON file."""
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\n📊 Results saved to {output_file}")


def main():
    """Run Claude Sonnet 4.5 classification test."""
    print("=" * 70)
    print("TEST 006: Claude Sonnet 4.5 Classification")
    print("=" * 70)

    try:
        results = process_pdfs_claude()
    except ValueError as e:
        print(f"\n❌ Error: {e}")
        print("\nTo fix this, add your Anthropic API key to the .env file:")
        print('ANTHROPIC_API_KEY=your_key_here')
        return None

    # Print summary
    print("\n📈 Summary:")
    print(f"  Papers processed: {results['papers_processed']}")
    print(f"  Total latency: {results['total_latency_ms']:.1f}ms")
    print(f"  Avg latency/paper: {results['avg_latency_ms']:.1f}ms")
    print(f"  Total tokens: {results['total_input_tokens']} in, {results['total_output_tokens']} out")

    # Compare to ground truth
    ground_truth = {
        "0c288904": "case_study",
        "0e20b252": "conceptual",
        "17af2c40": "case_study",
        "4f71d2ca": "case_study",
        "5c8f6a9b": "editorial",
        "5f3b02b4": "literature_review",
        "639d1860": "qualitative",
        "77ecffcd": "qualitative",
    }

    correct = 0
    total = 0
    print("\n📊 Accuracy vs Ground Truth:")
    for paper in results["papers"]:
        filename_prefix = paper["filename"][:8]
        if filename_prefix in ground_truth:
            expected = ground_truth[filename_prefix]
            actual = paper["study_type"]
            is_correct = expected == actual
            correct += is_correct
            total += 1
            symbol = "✓" if is_correct else "✗"
            print(f"  {symbol} {filename_prefix}: expected={expected}, got={actual} ({paper['confidence']})")

    if total > 0:
        accuracy = (correct / total) * 100
        print(f"\n🎯 Accuracy: {correct}/{total} = {accuracy:.1f}%")

    # Save results
    output_dir = Path(__file__).parent / "outputs"
    output_dir.mkdir(exist_ok=True)
    save_results(results, str(output_dir / "results_006_claude.json"))

    return results


if __name__ == "__main__":
    results = main()
