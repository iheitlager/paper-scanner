"""
Test 02: Claude API Metadata Extraction

Tests for extracting metadata from PDFs using Claude API (Haiku/Sonnet).
This approach has high accuracy but requires API key and has associated costs.

Run with: uv run pytest tests/spikes/020_parsing/test_02_claude_extractor.py -v -s

Note: Tests marked with @pytest.mark.requires_api need ANTHROPIC_API_KEY set.
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

# Mark entire module as spike test
pytestmark = [pytest.mark.spike, pytest.mark.requires_api]


@dataclass
class ExtractionResult:
    """Result from a metadata extraction attempt."""

    paper_id: str
    extractor: str
    metadata: Dict[str, Any]
    success: bool = True
    error: Optional[str] = None
    duration_seconds: float = 0.0
    cost_usd: float = 0.0
    tokens_in: int = 0
    tokens_out: int = 0


class ClaudeExtractor:
    """Extract metadata using Claude API with PDF input."""

    SYSTEM_PROMPT = """Extract bibliographic metadata from this academic paper PDF.

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

    # Approximate pricing (per 1M tokens)
    PRICING = {
        "claude-haiku-4-5-20251001": {"input": 0.25, "output": 1.25},
        "claude-sonnet-4-5-20250929": {"input": 3.0, "output": 15.0},
        "claude-opus-4-20250514": {"input": 15.0, "output": 75.0},
    }

    def __init__(self, model: str = "claude-haiku-4-5-20251001", api_key: Optional[str] = None):
        self.model = model
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        # Extract short model name (haiku, sonnet, opus)
        model_short = model.split("-")[1] if "-" in model else model
        self.name = f"claude_{model_short}"

    def extract(self, pdf_path: Path) -> tuple[Dict[str, Any], Dict[str, int]]:
        """Extract metadata from a single PDF."""
        from paper_scanner.models.anthropic import ClaudeHandler

        handler = ClaudeHandler(api_key=self.api_key, model=self.model)
        response, usage = handler.call(
            text=str(pdf_path),
            system_prompt=self.SYSTEM_PROMPT,
            max_tokens=2000,
        )

        return response or {}, usage

    def extract_all(self, pdf_files: List[Path]) -> List[ExtractionResult]:
        """Extract metadata from multiple PDF files."""
        import time

        results = []
        for pdf_path in pdf_files:
            paper_id = pdf_path.stem
            start_time = time.time()
            try:
                metadata, usage = self.extract(pdf_path)
                duration = time.time() - start_time

                # Calculate cost
                tokens_in = usage.get("input_tokens", 0)
                tokens_out = usage.get("output_tokens", 0)
                pricing = self.PRICING.get(self.model, {"input": 0, "output": 0})
                cost = (tokens_in * pricing["input"] + tokens_out * pricing["output"]) / 1_000_000

                results.append(
                    ExtractionResult(
                        paper_id=paper_id,
                        extractor=self.name,
                        metadata=metadata,
                        duration_seconds=duration,
                        cost_usd=cost,
                        tokens_in=tokens_in,
                        tokens_out=tokens_out,
                    )
                )
            except Exception as e:
                duration = time.time() - start_time
                results.append(
                    ExtractionResult(
                        paper_id=paper_id,
                        extractor=self.name,
                        metadata={},
                        success=False,
                        error=str(e),
                        duration_seconds=duration,
                    )
                )
        return results


# =============================================================================
# TEST CASES
# =============================================================================


class TestClaudeHaikuExtractor:
    """Tests for Claude Haiku extraction (fastest, cheapest)."""

    @pytest.mark.slow
    def test_extracts_single_pdf(self, corpus_files, anthropic_api_key):
        """Test extraction from a single PDF with Haiku."""
        extractor = ClaudeExtractor(
            model="claude-haiku-4-5-20251001",
            api_key=anthropic_api_key
        )
        metadata, usage = extractor.extract(corpus_files[0])

        assert metadata, "Should extract metadata"
        assert metadata.get("title"), "Should extract title"
        assert metadata.get("authors"), "Should extract authors"
        assert metadata.get("year"), "Should extract year"

        print(f"\nExtracted from {corpus_files[0].stem[:8]}...")
        print(f"  Title: {metadata.get('title', 'N/A')[:60]}...")
        print(f"  Year: {metadata.get('year')}")
        print(f"  Authors: {len(metadata.get('authors', []))} found")
        print(f"  Tokens: {usage.get('input_tokens', 0)} in, {usage.get('output_tokens', 0)} out")

    @pytest.mark.slow
    def test_extracts_all_pdfs(self, corpus_files, anthropic_api_key):
        """Test extraction from all PDFs with Haiku."""
        extractor = ClaudeExtractor(
            model="claude-haiku-4-5-20251001",
            api_key=anthropic_api_key
        )
        results = extractor.extract_all(corpus_files)

        total_cost = sum(r.cost_usd for r in results)
        total_tokens = sum(r.tokens_in + r.tokens_out for r in results)

        print(f"\nHaiku extraction results:")
        print(f"  Papers: {len(results)}")
        print(f"  Success: {sum(1 for r in results if r.success)}")
        print(f"  Total tokens: {total_tokens:,}")
        print(f"  Total cost: ${total_cost:.4f}")

        for result in results:
            assert result.success, f"Failed on {result.paper_id}: {result.error}"
            assert result.metadata.get("title"), f"No title for {result.paper_id}"


class TestClaudeSonnetExtractor:
    """Tests for Claude Sonnet extraction (better quality, higher cost)."""

    @pytest.mark.slow
    def test_extracts_single_pdf(self, corpus_files, anthropic_api_key):
        """Test extraction from a single PDF with Sonnet."""
        extractor = ClaudeExtractor(
            model="claude-sonnet-4-5-20250929",
            api_key=anthropic_api_key
        )
        metadata, usage = extractor.extract(corpus_files[0])

        assert metadata, "Should extract metadata"
        assert metadata.get("title"), "Should extract title"

        print(f"\nSonnet extracted from {corpus_files[0].stem[:8]}...")
        print(f"  Title: {metadata.get('title', 'N/A')[:60]}...")
        print(f"  Tokens: {usage.get('input_tokens', 0)} in, {usage.get('output_tokens', 0)} out")


class TestClaudeAccuracy:
    """Tests comparing Claude extraction against ground truth."""

    @pytest.mark.slow
    def test_haiku_accuracy(self, corpus_files, ground_truth, anthropic_api_key):
        """Test Haiku extraction accuracy against ground truth."""
        extractor = ClaudeExtractor(
            model="claude-haiku-4-5-20251001",
            api_key=anthropic_api_key
        )
        results = extractor.extract_all(corpus_files)

        title_match = 0
        year_match = 0
        total = 0

        for result in results:
            expected = ground_truth.get(result.paper_id, {})
            if not expected:
                continue

            total += 1

            # Title comparison (fuzzy)
            ext_title = (result.metadata.get("title") or "").lower().strip()
            exp_title = (expected.get("title") or "").lower().strip()
            if ext_title and exp_title and (ext_title in exp_title or exp_title in ext_title):
                title_match += 1

            # Year comparison (exact)
            if result.metadata.get("year") == expected.get("year"):
                year_match += 1

        if total > 0:
            print(f"\nHaiku accuracy against ground truth:")
            print(f"  Title: {title_match}/{total} ({title_match/total:.0%})")
            print(f"  Year: {year_match}/{total} ({year_match/total:.0%})")

            # Claude should have high accuracy
            assert year_match / total >= 0.9, "Year accuracy should be >= 90%"


class TestCostEstimation:
    """Tests for understanding API costs."""

    @pytest.mark.slow
    def test_estimate_batch_cost(self, corpus_files, anthropic_api_key):
        """Estimate cost for processing a batch of papers."""
        # Process just one paper to get token estimate
        extractor = ClaudeExtractor(
            model="claude-haiku-4-5-20251001",
            api_key=anthropic_api_key
        )
        _, usage = extractor.extract(corpus_files[0])

        avg_tokens_in = usage.get("input_tokens", 50000)
        avg_tokens_out = usage.get("output_tokens", 700)

        # Estimate costs for different batch sizes
        print("\nCost estimation (Haiku):")
        print(f"  Avg tokens per paper: {avg_tokens_in:,} in, {avg_tokens_out:,} out")

        for model, pricing in ClaudeExtractor.PRICING.items():
            cost_per_paper = (
                avg_tokens_in * pricing["input"] + avg_tokens_out * pricing["output"]
            ) / 1_000_000

            print(f"\n  {model}:")
            print(f"    Per paper: ${cost_per_paper:.4f}")
            print(f"    100 papers: ${cost_per_paper * 100:.2f}")
            print(f"    1000 papers: ${cost_per_paper * 1000:.2f}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
