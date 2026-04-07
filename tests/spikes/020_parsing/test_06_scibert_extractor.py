"""
Test 06: SciBERT-based Metadata Extraction

Tests for extracting metadata using SciBERT (Scientific BERT) model.
SciBERT is a BERT model trained on scientific text from Semantic Scholar.

Note: SciBERT is a language model, not an extraction model. For metadata
extraction, we need to either:
1. Use it with a NER head (requires fine-tuning)
2. Use embeddings + heuristics
3. Use a pre-trained scientific NER model

This implementation uses approach #2: embeddings + heuristics.

Run with: uv run pytest tests/spikes/020_parsing/test_06_scibert_extractor.py -v -s
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

# Mark entire module as spike test
pytestmark = pytest.mark.spike


@dataclass
class ExtractionResult:
    """Result from a metadata extraction attempt."""

    paper_id: str
    extractor: str
    metadata: Dict[str, Any]
    success: bool = True
    error: Optional[str] = None
    duration_seconds: float = 0.0


class SciBERTExtractor:
    """Extract metadata using SciBERT model with heuristics.

    SciBERT (allenai/scibert_scivocab_uncased) is trained on 1.14M papers
    from Semantic Scholar. While it excels at scientific NLP tasks,
    metadata extraction requires additional logic on top of the model.

    This implementation:
    1. Loads SciBERT for text encoding
    2. Uses the model's tokenizer for text preprocessing
    3. Applies heuristics similar to regex but with better text handling
    4. For true NER-based extraction, would need fine-tuning on labeled data
    """

    name = "scibert"
    model_name = "allenai/scibert_scivocab_uncased"

    def __init__(self):
        """Initialize SciBERT model and tokenizer."""
        self.model = None
        self.tokenizer = None
        self._load_model()

    def _load_model(self):
        """Load SciBERT model and tokenizer."""
        try:
            from transformers import AutoModel, AutoTokenizer

            print(f"Loading SciBERT model: {self.model_name}")
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            self.model = AutoModel.from_pretrained(self.model_name)
            print("SciBERT loaded successfully")
        except Exception as e:
            print(f"Failed to load SciBERT: {e}")
            raise

    def extract(self, pdf_path: Path) -> Dict[str, Any]:
        """Extract metadata from PDF using SciBERT-enhanced heuristics."""
        from pypdf import PdfReader

        reader = PdfReader(str(pdf_path))

        # Extract text from first few pages
        pages_text = []
        for i, page in enumerate(reader.pages[:5]):
            text = page.extract_text() or ""
            pages_text.append(text)

        full_text = "\n\n".join(pages_text)
        first_page = pages_text[0] if pages_text else ""

        # Use SciBERT tokenizer to preprocess text
        # This handles scientific vocabulary better than standard tokenizers
        tokens = self.tokenizer.tokenize(first_page[:2000])

        return {
            "title": self._extract_title(first_page, tokens),
            "authors": self._extract_authors(first_page, tokens),
            "year": self._extract_year(first_page),
            "journal": self._extract_journal(first_page),
            "doi": self._extract_doi(full_text),
            "abstract": self._extract_abstract(full_text),
            "table_of_contents": self._extract_toc(full_text),
            "_scibert_info": {
                "model": self.model_name,
                "token_count": len(tokens),
                "note": "SciBERT used for tokenization; extraction uses heuristics"
            }
        }

    def _extract_title(self, text: str, tokens: List[str]) -> Optional[str]:
        """Extract title using SciBERT tokenization awareness.

        SciBERT's vocabulary is trained on scientific text, so it tokenizes
        scientific terms better than general BERT. However, title extraction
        still relies on layout heuristics.
        """
        lines = text.split("\n")

        # Look for title in first 20 non-empty lines
        candidate_lines = []
        for line in lines[:30]:
            line = line.strip()
            if not line:
                continue
            # Skip common non-title patterns
            if any(skip in line.lower() for skip in [
                "journal", "volume", "doi:", "http", "©", "copyright",
                "received", "accepted", "published", "issn"
            ]):
                continue
            # Title is usually longer than 20 chars
            if len(line) > 20:
                candidate_lines.append(line)

        # Use SciBERT tokenization to score candidates
        # Titles tend to have more content words (fewer subword tokens per word)
        best_title = None
        best_score = 0

        for line in candidate_lines[:5]:
            # Tokenize with SciBERT
            line_tokens = self.tokenizer.tokenize(line)
            words = line.split()

            if not words:
                continue

            # Score: fewer subword tokens per word = more complete words = likely title
            # Scientific titles use complete words, not abbreviations
            subword_ratio = len(line_tokens) / len(words) if words else 10
            length_score = min(len(line) / 100, 1.0)  # Prefer longer titles

            # Combined score (lower subword ratio is better)
            score = length_score / subword_ratio

            if score > best_score:
                best_score = score
                best_title = line

        return best_title

    def _extract_authors(self, text: str, tokens: List[str]) -> List[Dict[str, str]]:
        """Extract authors using pattern matching.

        Note: For true NER-based author extraction, SciBERT would need to be
        fine-tuned with a token classification head on author name data.
        """
        authors = []

        # Look for author patterns in first 2000 chars
        first_part = text[:2000]

        # Pattern for names (First Last or First M. Last)
        name_pattern = r"\b([A-Z][a-z]+(?:\s+[A-Z]\.?\s*)?[A-Z][a-z]+)\b"

        # Find potential author names
        matches = re.findall(name_pattern, first_part)

        seen = set()
        for name in matches[:10]:
            name = name.strip()
            # Filter out common non-names
            if name.lower() in ["abstract", "introduction", "keywords", "received",
                                "accepted", "corresponding", "author"]:
                continue
            if name not in seen and len(name) > 5:
                seen.add(name)
                authors.append({"name": name})

        return authors

    def _extract_year(self, text: str) -> Optional[int]:
        """Extract publication year."""
        # Look for years in common patterns
        patterns = [
            r"(?:published|accepted|received)[:\s]+.*?(\d{4})",
            r"©\s*(\d{4})",
            r"\b(20[0-2]\d)\b",
            r"\b(199\d)\b",
        ]

        for pattern in patterns:
            match = re.search(pattern, text[:3000], re.IGNORECASE)
            if match:
                year = int(match.group(1))
                if 1990 <= year <= 2030:
                    return year

        return None

    def _extract_journal(self, text: str) -> Optional[str]:
        """Extract journal name."""
        patterns = [
            r"(?:published\s+(?:in|by)|journal:?)\s+([A-Z][^\n]{10,50})",
            r"^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+(?:Journal|Review|Letters))",
        ]

        for pattern in patterns:
            match = re.search(pattern, text[:2000], re.MULTILINE | re.IGNORECASE)
            if match:
                return match.group(1).strip()

        return None

    def _extract_doi(self, text: str) -> Optional[str]:
        """Extract DOI."""
        doi_pattern = r"10\.\d{4,}/[^\s]+"
        match = re.search(doi_pattern, text)
        if match:
            doi = match.group(0)
            # Clean trailing punctuation
            doi = doi.rstrip(".,;)")
            return doi
        return None

    def _extract_abstract(self, text: str) -> Optional[str]:
        """Extract abstract."""
        abstract_match = re.search(
            r"(?:abstract|summary)[:\s]*\n?(.*?)(?=\n\s*(?:introduction|keywords|1\.|$))",
            text[:5000],
            re.IGNORECASE | re.DOTALL
        )
        if abstract_match:
            abstract = abstract_match.group(1).strip()
            # Clean up whitespace
            abstract = " ".join(abstract.split())
            return abstract[:500] if abstract else None
        return None

    def _extract_toc(self, text: str) -> List[Dict[str, Any]]:
        """Extract table of contents.

        Note: SciBERT could help identify section headers by encoding them
        and comparing to known section title embeddings. This implementation
        uses simpler pattern matching.
        """
        toc = []
        current_section = None

        # Pattern for numbered sections
        section_pattern = r"^(\d+)\.\s+([A-Z][^\n]{5,100})"
        subsection_pattern = r"^(\d+)\.(\d+)\s+([A-Z][^\n]{5,100})"

        for line in text.split("\n"):
            line = line.strip()

            # Check for subsection first (more specific pattern)
            sub_match = re.match(subsection_pattern, line)
            if sub_match and current_section:
                subsection_name = sub_match.group(3).strip()
                current_section["subsections"].append(f"{sub_match.group(1)}.{sub_match.group(2)} {subsection_name}")
                continue

            # Check for main section
            sec_match = re.match(section_pattern, line)
            if sec_match:
                if current_section:
                    toc.append(current_section)
                section_name = sec_match.group(2).strip()
                current_section = {
                    "section": f"{sec_match.group(1)}. {section_name}",
                    "subsections": []
                }

        if current_section:
            toc.append(current_section)

        return toc

    def extract_all(self, pdf_files: List[Path]) -> List[ExtractionResult]:
        """Extract metadata from multiple PDF files."""
        import time

        results = []
        for pdf_path in pdf_files:
            paper_id = pdf_path.stem
            start_time = time.time()
            try:
                metadata = self.extract(pdf_path)
                duration = time.time() - start_time
                results.append(
                    ExtractionResult(
                        paper_id=paper_id,
                        extractor=self.name,
                        metadata=metadata,
                        duration_seconds=duration,
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


class TestSciBERTAvailability:
    """Test SciBERT model availability."""

    def test_transformers_installed(self):
        """Test that transformers library is available."""
        try:
            import transformers
            print(f"\ntransformers version: {transformers.__version__}")
            assert True
        except ImportError:
            pytest.skip("transformers not installed")

    def test_scibert_model_loads(self):
        """Test that SciBERT model can be loaded."""
        try:
            from transformers import AutoModel, AutoTokenizer

            model_name = "allenai/scibert_scivocab_uncased"
            print(f"\nLoading model: {model_name}")

            tokenizer = AutoTokenizer.from_pretrained(model_name)
            model = AutoModel.from_pretrained(model_name)

            print(f"Model loaded: {model.config.hidden_size} hidden size")
            print(f"Vocab size: {tokenizer.vocab_size}")

            # Test tokenization of scientific text
            test_text = "Ecosystem development framework for digital transformation"
            tokens = tokenizer.tokenize(test_text)
            print(f"Test tokenization: {tokens}")

            assert model is not None
            assert tokenizer is not None
        except Exception as e:
            pytest.skip(f"SciBERT model could not be loaded: {e}")


class TestSciBERTExtractor:
    """Tests for SciBERT-based extraction."""

    @pytest.fixture
    def extractor(self):
        """Create SciBERT extractor."""
        try:
            return SciBERTExtractor()
        except Exception as e:
            pytest.skip(f"SciBERT extractor failed to initialize: {e}")

    def test_extractor_initializes(self, extractor):
        """Test extractor can be created."""
        assert extractor.name == "scibert"
        assert extractor.model is not None
        assert extractor.tokenizer is not None

    def test_extracts_from_single_pdf(self, extractor, corpus_files):
        """Test extraction from a single PDF."""
        result = extractor.extract(corpus_files[0])

        assert isinstance(result, dict)
        print(f"\nExtracted from {corpus_files[0].stem[:8]}...")
        print(f"  Title: {result.get('title', 'N/A')[:60] if result.get('title') else 'N/A'}...")
        print(f"  Authors: {len(result.get('authors', []))} found")
        print(f"  Year: {result.get('year')}")
        print(f"  DOI: {result.get('doi')}")
        print(f"  TOC sections: {len(result.get('table_of_contents', []))}")

        scibert_info = result.get("_scibert_info", {})
        print(f"  SciBERT tokens: {scibert_info.get('token_count', 'N/A')}")

    def test_extracts_all_pdfs(self, extractor, corpus_files):
        """Test extraction from all corpus PDFs."""
        results = extractor.extract_all(corpus_files)

        assert len(results) == len(corpus_files)

        print("\nSciBERT extraction results:")
        for result in results:
            status = "✓" if result.success else "✗"
            print(f"  {status} {result.paper_id[:8]}... ({result.duration_seconds:.2f}s)")
            if result.success:
                meta = result.metadata
                print(f"    Title: {meta.get('title', 'N/A')[:50] if meta.get('title') else 'N/A'}...")
                print(f"    Year: {meta.get('year')}, DOI: {meta.get('doi', 'N/A')[:30] if meta.get('doi') else 'N/A'}...")


class TestSciBERTAccuracy:
    """Tests comparing SciBERT extraction against ground truth."""

    @pytest.fixture
    def extractor(self):
        """Create SciBERT extractor."""
        try:
            return SciBERTExtractor()
        except Exception as e:
            pytest.skip(f"SciBERT extractor failed to initialize: {e}")

    def test_accuracy_vs_ground_truth(self, extractor, corpus_files, ground_truth):
        """Test SciBERT extraction accuracy against ground truth."""
        results = extractor.extract_all(corpus_files)

        title_scores = []
        author_scores = []
        year_matches = 0
        doi_matches = 0
        journal_scores = []
        total = 0

        print("\nSciBERT vs Ground Truth:")

        for result in results:
            expected = ground_truth.get(result.paper_id, {})
            if not expected:
                continue

            total += 1
            extracted = result.metadata

            # Title comparison (fuzzy)
            ext_title = (extracted.get("title") or "").lower()
            exp_title = (expected.get("title") or "").lower()
            if ext_title and exp_title:
                # Check for substring match
                if exp_title[:30] in ext_title or ext_title[:30] in exp_title:
                    title_scores.append(1.0)
                else:
                    title_scores.append(0.0)
            else:
                title_scores.append(0.0)

            # Author comparison
            ext_authors = {a.get("name", "").lower() for a in extracted.get("authors", [])}
            exp_authors = {a.get("name", "").lower() for a in expected.get("authors", [])}
            if exp_authors:
                overlap = len(ext_authors & exp_authors)
                author_scores.append(overlap / len(exp_authors))
            else:
                author_scores.append(1.0 if not ext_authors else 0.0)

            # Year comparison (exact)
            if extracted.get("year") == expected.get("year"):
                year_matches += 1

            # DOI comparison (partial match OK)
            ext_doi = extracted.get("doi") or ""
            exp_doi = expected.get("doi") or ""
            if exp_doi and ext_doi and exp_doi in ext_doi:
                doi_matches += 1

            # Journal comparison (fuzzy)
            ext_journal = (extracted.get("journal") or "").lower()
            exp_journal = (expected.get("journal") or "").lower()
            if ext_journal and exp_journal:
                if exp_journal[:15] in ext_journal or ext_journal[:15] in exp_journal:
                    journal_scores.append(1.0)
                else:
                    journal_scores.append(0.0)
            else:
                journal_scores.append(0.0)

            print(f"\n  {result.paper_id[:8]}...")
            print(f"    Title: {'✓' if title_scores[-1] > 0 else '✗'} {ext_title[:40]}...")
            print(f"    Authors: {author_scores[-1]:.0%} ({len(ext_authors)}/{len(exp_authors)} matched)")
            print(f"    Year: {'✓' if extracted.get('year') == expected.get('year') else '✗'} {extracted.get('year')} vs {expected.get('year')}")
            print(f"    DOI: {'✓' if exp_doi in ext_doi else '✗'}")

        if total > 0:
            avg_title = sum(title_scores) / len(title_scores) if title_scores else 0
            avg_author = sum(author_scores) / len(author_scores) if author_scores else 0
            avg_journal = sum(journal_scores) / len(journal_scores) if journal_scores else 0

            print(f"\n{'='*50}")
            print(f"SciBERT Accuracy Summary (n={total}):")
            print(f"  Title:   {avg_title:.0%}")
            print(f"  Authors: {avg_author:.0%}")
            print(f"  Year:    {year_matches/total:.0%}")
            print(f"  DOI:     {doi_matches/total:.0%}")
            print(f"  Journal: {avg_journal:.0%}")

            overall = (avg_title + avg_author + year_matches/total + doi_matches/total + avg_journal) / 5
            print(f"  Overall: {overall:.0%}")
            print(f"{'='*50}")

    def test_generate_accuracy_report(self, extractor, corpus_files, ground_truth, outputs_dir):
        """Generate accuracy report for SciBERT extraction."""
        import json

        results = extractor.extract_all(corpus_files)

        report = {
            "extractor": "scibert",
            "model": extractor.model_name,
            "total_papers": len(results),
            "title_accuracy": 0.0,
            "author_accuracy": 0.0,
            "year_accuracy": 0.0,
            "journal_accuracy": 0.0,
            "doi_accuracy": 0.0,
            "overall_accuracy": 0.0,
            "total_cost_usd": 0.0,  # Local model, no API cost
            "avg_duration_seconds": 0.0,
            "note": "SciBERT is a language model, not extraction model. Uses heuristics on top of tokenization.",
            "errors": [],
            "raw_results": [],
        }

        title_scores = []
        author_scores = []
        year_matches = 0
        doi_matches = 0
        journal_scores = []
        total_duration = 0
        total = 0

        for result in results:
            total_duration += result.duration_seconds

            if not result.success:
                report["errors"].append({
                    "paper_id": result.paper_id,
                    "error": result.error
                })
                continue

            expected = ground_truth.get(result.paper_id, {})
            if not expected:
                continue

            total += 1
            extracted = result.metadata

            # Calculate accuracies (same logic as above)
            ext_title = (extracted.get("title") or "").lower()
            exp_title = (expected.get("title") or "").lower()
            title_match = 1.0 if (ext_title and exp_title and (exp_title[:30] in ext_title or ext_title[:30] in exp_title)) else 0.0
            title_scores.append(title_match)

            ext_authors = {a.get("name", "").lower() for a in extracted.get("authors", [])}
            exp_authors = {a.get("name", "").lower() for a in expected.get("authors", [])}
            author_match = len(ext_authors & exp_authors) / len(exp_authors) if exp_authors else (1.0 if not ext_authors else 0.0)
            author_scores.append(author_match)

            if extracted.get("year") == expected.get("year"):
                year_matches += 1

            ext_doi = extracted.get("doi") or ""
            exp_doi = expected.get("doi") or ""
            if exp_doi and ext_doi and exp_doi in ext_doi:
                doi_matches += 1

            ext_journal = (extracted.get("journal") or "").lower()
            exp_journal = (expected.get("journal") or "").lower()
            journal_match = 1.0 if (ext_journal and exp_journal and (exp_journal[:15] in ext_journal or ext_journal[:15] in exp_journal)) else 0.0
            journal_scores.append(journal_match)

            # Remove internal scibert info from raw results
            raw_metadata = {k: v for k, v in extracted.items() if not k.startswith("_")}

            report["raw_results"].append({
                "paper_id": result.paper_id,
                "metadata": raw_metadata,
                "success": result.success,
                "error": result.error,
                "duration_seconds": result.duration_seconds,
            })

        if total > 0:
            report["title_accuracy"] = sum(title_scores) / len(title_scores) if title_scores else 0
            report["author_accuracy"] = sum(author_scores) / len(author_scores) if author_scores else 0
            report["year_accuracy"] = year_matches / total
            report["doi_accuracy"] = doi_matches / total
            report["journal_accuracy"] = sum(journal_scores) / len(journal_scores) if journal_scores else 0
            report["overall_accuracy"] = (
                report["title_accuracy"] +
                report["author_accuracy"] +
                report["year_accuracy"] +
                report["doi_accuracy"] +
                report["journal_accuracy"]
            ) / 5
            report["avg_duration_seconds"] = total_duration / len(results)

        # Save report
        report_path = outputs_dir / "scibert_accuracy_report.json"
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2)

        print(f"\nSciBERT accuracy report saved to: {report_path}")
        print(f"Overall accuracy: {report['overall_accuracy']:.0%}")

        return report


class TestSciBERTComparison:
    """Compare SciBERT with other methods."""

    def test_comparison_summary(self, corpus_files, ground_truth, outputs_dir):
        """Generate comparison including SciBERT."""
        import json

        # Load existing reports
        reports = {}
        report_files = [
            ("regex", "regex_accuracy_report.json"),
            ("claude_haiku", "claude_haiku_accuracy_report.json"),
            ("scibert", "scibert_accuracy_report.json"),
        ]

        for name, filename in report_files:
            report_path = outputs_dir / filename
            if report_path.exists():
                with open(report_path) as f:
                    reports[name] = json.load(f)

        if not reports:
            pytest.skip("No accuracy reports found")

        print("\n" + "="*60)
        print("EXTRACTION METHOD COMPARISON")
        print("="*60)

        headers = ["Method", "Title", "Authors", "Year", "DOI", "Journal", "Overall", "Cost"]
        print(f"\n{headers[0]:<15} {headers[1]:<8} {headers[2]:<8} {headers[3]:<8} {headers[4]:<8} {headers[5]:<8} {headers[6]:<8} {headers[7]:<8}")
        print("-" * 80)

        for method, report in reports.items():
            print(f"{method:<15} "
                  f"{report.get('title_accuracy', 0):.0%}     "
                  f"{report.get('author_accuracy', 0):.0%}     "
                  f"{report.get('year_accuracy', 0):.0%}     "
                  f"{report.get('doi_accuracy', 0):.0%}     "
                  f"{report.get('journal_accuracy', 0):.0%}     "
                  f"{report.get('overall_accuracy', 0):.0%}     "
                  f"${report.get('total_cost_usd', 0):.3f}")

        print("="*60)

        # Update comparison summary with SciBERT
        summary_path = outputs_dir / "comparison_summary_with_scibert.json"
        summary = {
            "methods": list(reports.keys()),
            "results": reports,
            "winner": max(reports.keys(), key=lambda k: reports[k].get("overall_accuracy", 0)),
            "note": "SciBERT uses local model (no API cost) but requires ~400MB download"
        }

        with open(summary_path, "w") as f:
            json.dump(summary, f, indent=2)

        print(f"\nComparison saved to: {summary_path}")
        print(f"Winner: {summary['winner']} ({reports[summary['winner']].get('overall_accuracy', 0):.0%})")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
