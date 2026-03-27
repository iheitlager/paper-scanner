#!/usr/bin/env python3
"""
Test 010: Claude Haiku 4.5 on BibTeX Data
==========================================

Tests the cost-effective Claude Haiku model on structured BibTeX data
(title + abstract only) instead of full PDFs.

Expected benefits:
- Much lower token count (structured text vs full PDF)
- Faster processing
- Lower cost per paper
- Maintain good accuracy

Hypothesis: Structured BibTeX + cheap model = best cost/accuracy balance
"""

import json
import os
import time
from pathlib import Path

from paper_scanner.models.anthropic import ClaudeHandler

# Path to BibTeX test data
BIBTEX_FILE = Path(__file__).parent.parent.parent / "data" / "eight_cases.bib"

# Ground truth for the 7 papers (excluding 5c8f6a9b which is not in BibTeX)
GROUND_TRUTH = {
    "0c288904": "case_study",  # Empirical case studies (priority over lit review)
    "0e20b252": "commentory,_conceptual",  # Editorial/commentary with conceptual framing
    "17af2c40": "case_study",  # Single case study
    "4f71d2ca": "case_study",  # Multiple case studies (qualitative + empirical)
    "5f3b02b4": "literature_review",  # Survey paper
    "639d1860": "qualitative_study",  # Qualitative study with interviews
    "77ecffcd": "qualitative_study",  # Qualitative case-based study
}

# Classification categories with detailed descriptions
CATEGORIES = {
    "qualitative": "Qualitative research using interviews, observations, ethnography, grounded theory. Look for: 'semi-structured interviews', 'thematic analysis', 'coding', 'NVivo'",
    "case_study": "Case study research examining one or multiple real-world cases in depth. Look for: 'case study', 'case analysis', 'multiple cases', 'within-case', 'cross-case'",
    "quantitative": "Quantitative research with statistical analysis, surveys, experiments. Look for: 'regression', 'ANOVA', 'correlation', 'survey data', 'hypothesis testing'",
    "mixed_methods": "Combined qualitative and quantitative approaches. Look for: 'mixed methods', 'triangulation', 'both qualitative and quantitative'",
    "literature_review": "Systematic or narrative literature reviews, meta-analyses. Look for: 'literature review', 'systematic review', 'meta-analysis', 'bibliometric'",
    "editorial": "Editorial, commentary, opinion piece. Look for: 'editorial', 'commentary', 'perspective', 'viewpoint'",
    "conceptual": "Conceptual or theoretical papers developing frameworks. Look for: 'framework', 'conceptual model', 'theoretical', 'propositions'",
}

SYSTEM_PROMPT = """You are an expert research methodology classifier for academic papers.

Analyze the paper's title and abstract to determine its research methodology type.

Categories:
- qualitative: Uses interviews, observations, ethnography, grounded theory
- case_study: In-depth examination of one or more real-world cases
- quantitative: Statistical analysis, surveys, experiments
- mixed_methods: Combines qualitative and quantitative approaches
- literature_review: Systematic or narrative review of existing literature
- editorial: Commentary, opinion, or editorial piece
- conceptual: Develops theoretical frameworks or conceptual models

CRITICAL RULES:
1. If paper describes EMPIRICAL CASE STUDIES (new data/cases), classify as "case_study" even if it reviews literature
2. If paper only REVIEWS existing case studies without new cases, classify as "literature_review"
3. Multiple categories possible but use underscores: "case_study" not "case study"
4. Base decision on ABSTRACT CONTENT, not just title

Return ONLY a JSON object:
{
    "category": "primary_category",
    "confidence": "high|medium|low",
    "reasoning": "Brief explanation of classification"
}"""


def parse_bibtex(file_path):
    """Parse BibTeX file and extract papers with abstracts."""
    papers = []

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Split by @article entries
    entries = content.split('@article{')[1:]  # Skip first empty split

    for entry in entries:
        lines = entry.strip().split('\n')
        cite_key = lines[0].split(',')[0].strip()

        paper = {'cite_key': cite_key}

        # Parse fields
        for line in lines[1:]:
            line = line.strip()
            if line.startswith('title'):
                paper['title'] = line.split('=', 1)[1].strip(' {},')
            elif line.startswith('abstract'):
                paper['abstract'] = line.split('=', 1)[1].strip(' {},')
            elif line.startswith('keywords'):
                paper['keywords'] = line.split('=', 1)[1].strip(' {},')
            elif line.startswith('pdf'):
                # Extract paper ID from PDF filename (e.g., "0c288904-...")
                pdf_value = line.split('=', 1)[1].strip(' {},')
                paper['id'] = pdf_value.split('-')[0] if '-' in pdf_value else pdf_value.replace('.pdf', '')

        # Only include papers with abstracts and paper ID
        if 'abstract' in paper and paper['abstract'] and 'id' in paper:
            papers.append(paper)

    return papers


def classify_paper(handler, paper):
    """Classify a single paper using Claude Haiku."""
    # Build structured input text
    text_parts = [f"TITLE: {paper['title']}"]

    if 'keywords' in paper:
        text_parts.append(f"KEYWORDS: {paper['keywords']}")

    text_parts.append(f"ABSTRACT: {paper['abstract']}")

    input_text = "\n\n".join(text_parts)

    # Call Claude API
    start_time = time.time()
    result, tokens = handler.call(
        text=input_text,
        system_prompt=SYSTEM_PROMPT,
        max_tokens=500
    )
    latency = int((time.time() - start_time) * 1000)

    return result, tokens, latency


def main():
    print("=" * 80)
    print("Test 010: Claude Haiku 4.5 on BibTeX Data")
    print("=" * 80)
    print()

    # Check for API key
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("❌ Error: ANTHROPIC_API_KEY environment variable not set")
        return

    # Initialize Claude Haiku handler
    print("🤖 Initializing Claude Haiku 4.5 (claude-haiku-4-5-20251001)...")
    handler = ClaudeHandler(
        api_key=api_key,
        model="claude-haiku-4-5-20251001",
        logger=lambda msg: print(f"   {msg}")
    )
    print()

    # Load papers from BibTeX
    print(f"📚 Loading papers from {BIBTEX_FILE.name}...")
    papers = parse_bibtex(BIBTEX_FILE)
    print(f"   Loaded {len(papers)} papers with abstracts")
    print(f"   Testing on {len(GROUND_TRUTH)} papers with ground truth")
    print()

    # Classify each paper
    results = []
    correct = 0
    total_tokens = {"input_tokens": 0, "output_tokens": 0}
    total_latency = 0

    print("Classifying papers...")
    print()

    paper_count = 0
    for i, paper in enumerate(papers):
        paper_id = paper['id']

        # Skip papers without ground truth
        if paper_id not in GROUND_TRUTH:
            print(f"   Skipping {paper_id} (not in ground truth)")
            continue

        paper_count += 1

        ground_truth = GROUND_TRUTH[paper_id]

        print(f"[{paper_count}/{len(GROUND_TRUTH)}] {paper['title'][:60]}...")
        print(f"   Ground truth: {ground_truth}")

        result, tokens, latency = classify_paper(handler, paper)

        # Track tokens and latency
        total_tokens["input_tokens"] += tokens.get("input_tokens", 0)
        total_tokens["output_tokens"] += tokens.get("output_tokens", 0)
        total_latency += latency

        if result:
            predicted = result.get("category", "unknown")
            confidence = result.get("confidence", "unknown")
            reasoning = result.get("reasoning", "")

            is_correct = predicted.lower().replace(" ", "_") == ground_truth.lower()
            if is_correct:
                correct += 1
                print(f"   ✓ Predicted: {predicted} (confidence: {confidence})")
            else:
                print(f"   ✗ Predicted: {predicted} (expected: {ground_truth})")
                print(f"     Confidence: {confidence}")
                print(f"     Reasoning: {reasoning[:100]}...")

            print(f"   Tokens: in={tokens.get('input_tokens', 0)} out={tokens.get('output_tokens', 0)}")
            print(f"   Latency: {latency}ms")

            results.append({
                "paper_id": paper_id,
                "title": paper["title"],
                "ground_truth": ground_truth,
                "predicted": predicted,
                "confidence": confidence,
                "reasoning": reasoning,
                "tokens": tokens,
                "latency": latency,
                "correct": is_correct
            })
        else:
            print("   ❌ Error: No response from API")
            results.append({
                "paper_id": paper_id,
                "title": paper["title"],
                "ground_truth": ground_truth,
                "predicted": "error",
                "error": "API call failed",
                "tokens": tokens,
                "latency": latency,
                "correct": False
            })

        print()

    # Calculate statistics
    accuracy = (correct / len(GROUND_TRUTH)) * 100
    avg_latency = total_latency / len(GROUND_TRUTH)
    avg_input_tokens = total_tokens["input_tokens"] / len(GROUND_TRUTH)
    avg_output_tokens = total_tokens["output_tokens"] / len(GROUND_TRUTH)

    # Cost calculation for Haiku 4.5
    # Input: $0.80 per million tokens, Output: $4.00 per million tokens
    input_cost = (total_tokens["input_tokens"] / 1_000_000) * 0.80
    output_cost = (total_tokens["output_tokens"] / 1_000_000) * 4.00
    total_cost = input_cost + output_cost
    cost_per_paper = total_cost / len(GROUND_TRUTH)

    # Print results
    print("=" * 80)
    print("Results:")
    print("=" * 80)
    print(f"Accuracy:           {correct}/{len(GROUND_TRUTH)} ({accuracy:.1f}%)")
    print(f"Avg Latency:        {avg_latency:.0f}ms")
    print(f"Avg Input Tokens:   {avg_input_tokens:.0f}")
    print(f"Avg Output Tokens:  {avg_output_tokens:.0f}")
    print(f"Total Input Tokens: {total_tokens['input_tokens']:,}")
    print(f"Total Output Tokens: {total_tokens['output_tokens']:,}")
    print()
    print("💰 Cost Analysis:")
    print(f"   Input cost:  ${input_cost:.4f} ({total_tokens['input_tokens']:,} tokens @ $0.80/M)")
    print(f"   Output cost: ${output_cost:.4f} ({total_tokens['output_tokens']:,} tokens @ $4.00/M)")
    print(f"   Total cost:  ${total_cost:.4f}")
    print(f"   Per paper:   ${cost_per_paper:.4f}")
    print()

    # Save results
    output_file = Path(__file__).parent / "test_010_claude_haiku_bibtex_results.json"
    with open(output_file, 'w') as f:
        json.dump({
            "model": "claude-haiku-4-5-20251001",
            "accuracy": accuracy,
            "correct": correct,
            "total": len(GROUND_TRUTH),
            "avg_latency": avg_latency,
            "avg_input_tokens": avg_input_tokens,
            "avg_output_tokens": avg_output_tokens,
            "total_tokens": total_tokens,
            "total_cost": total_cost,
            "cost_per_paper": cost_per_paper,
            "results": results
        }, f, indent=2)

    print(f"✅ Results saved to {output_file.name}")


if __name__ == "__main__":
    main()
