#!/usr/bin/env python
"""
Create ground truth metadata by extracting from corpus PDFs using Claude.

This script:
1. Reads all PDFs from tests/corpus/
2. Uses Claude API to extract metadata
3. Saves individual YAML files per paper
4. Updates metamodel.yml with all extracted metadata

Usage:
    uv run python tests/spikes/020_parsing/create_ground_truth.py

Requires:
    ANTHROPIC_API_KEY environment variable
"""

import os
import sys
from pathlib import Path

import yaml

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from paper_scanner.models.anthropic import ClaudeHandler

SPIKE_DIR = Path(__file__).parent
CORPUS_DIR = SPIKE_DIR.parent.parent / "corpus"

EXTRACTION_PROMPT = """Extract bibliographic metadata from this academic paper PDF.

Return ONLY a valid JSON object (no markdown code blocks, no explanations) with this structure:

{
  "journal": "full journal name or null",
  "title": "complete paper title including subtitle",
  "authors": [
    {"name": "author full name", "affiliation": "institution or null"}
  ],
  "year": 2024,
  "volume": 42,
  "issue": 3,
  "pages": "100-120",
  "doi": "10.xxxx/xxxxx",
  "abstract": "first 500 characters of abstract or null",
  "keywords": ["keyword1", "keyword2"],
  "table_of_contents": [
    {"section": "1. Introduction", "subsections": ["1.1 Background"]}
  ]
}

Important:
- Extract exactly what appears in the paper
- Use null for fields that cannot be found
- Authors should be in order as they appear
- Include all main numbered sections in table_of_contents
- Return ONLY valid JSON, no other text
"""


def extract_metadata(pdf_path: Path, handler: ClaudeHandler) -> dict:
    """Extract metadata from a PDF using Claude."""
    print(f"  Extracting from: {pdf_path.name}")

    response, usage = handler.call(
        text=str(pdf_path),
        system_prompt=EXTRACTION_PROMPT,
        max_tokens=3000,
    )

    print(f"    Tokens: {usage.get('input_tokens', 0)} in, {usage.get('output_tokens', 0)} out")

    # Handler returns parsed JSON dict or None
    if response is None:
        print("    Warning: Response was None (JSON parsing may have failed)")
        return {}

    if isinstance(response, dict):
        print(f"    Extracted: {response.get('title', 'no title')[:50]}...")
        return response

    print(f"    Warning: Unexpected response type: {type(response)}")
    return {}


def save_paper_yaml(paper_id: str, metadata: dict, output_dir: Path):
    """Save individual paper metadata to YAML file."""
    output_path = output_dir / f"{paper_id}.yml"
    with open(output_path, "w") as f:
        yaml.dump(metadata, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    print(f"    Saved: {output_path.name}")


def update_metamodel(papers: list, output_path: Path):
    """Update metamodel.yml with all paper metadata."""
    # Read existing metamodel for schema
    existing = {}
    if output_path.exists():
        with open(output_path) as f:
            existing = yaml.safe_load(f) or {}

    metamodel = {
        "meta": existing.get("meta", {
            "description": "Bibliographic metadata extracted from academic papers",
            "format": "YAML",
            "version": "1.0",
            "created_at": "2026-01-17",
            "extraction_method": "Claude API (claude-sonnet-4-5-20250929)",
        }),
        "schema": existing.get("schema", {}),
        "papers": papers,
    }

    with open(output_path, "w") as f:
        yaml.dump(metamodel, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    print(f"\nUpdated: {output_path}")


def main():
    # Check for API key
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: ANTHROPIC_API_KEY environment variable not set")
        sys.exit(1)

    # Get PDF files
    pdf_files = sorted(CORPUS_DIR.glob("*.pdf"))
    if not pdf_files:
        print(f"Error: No PDF files found in {CORPUS_DIR}")
        sys.exit(1)

    print(f"Found {len(pdf_files)} PDF files in corpus")
    print(f"Using Claude Sonnet for extraction\n")

    # Initialize handler with Sonnet for better accuracy
    handler = ClaudeHandler(
        api_key=api_key,
        model="claude-sonnet-4-5-20250929"
    )

    # Extract metadata from each PDF
    papers = []
    for pdf_path in pdf_files:
        paper_id = pdf_path.stem
        print(f"\nProcessing: {paper_id}")

        metadata = extract_metadata(pdf_path, handler)

        if metadata:
            # Save individual YAML
            save_paper_yaml(paper_id, metadata, SPIKE_DIR)

            # Add to papers list
            papers.append({
                "id": paper_id,
                "filename": pdf_path.name,
                "metadata": metadata,
            })
        else:
            print(f"    Warning: No metadata extracted")
            papers.append({
                "id": paper_id,
                "filename": pdf_path.name,
                "metadata": None,
            })

    # Update metamodel.yml
    update_metamodel(papers, SPIKE_DIR / "metamodel.yml")

    print(f"\nExtraction complete!")
    print(f"  Papers processed: {len(papers)}")
    print(f"  Successful: {sum(1 for p in papers if p['metadata'])}")


if __name__ == "__main__":
    main()
