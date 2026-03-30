"""Tests for MetadataExtractionStep."""

import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from paper_scanner.core.enum import PaperType, StepStatus
from paper_scanner.core.models import Author, PDFInfo, Paper, ResearchMethodClassification
from paper_scanner.steps.metadata_extraction import (
    MetadataExtractionStep,
    _apply_metadata,
    _format_paper_text,
)


def _make_paper(**kwargs):
    defaults = {
        "id": str(uuid.uuid4()),
        "cite_key": f"test_{uuid.uuid4().hex[:6]}",
        "title": "Machine Learning in Healthcare",
        "abstract": "We study ML applications in hospital settings.",
        "paper_type": PaperType.JOURNAL_ARTICLE,
        "year": 2024,
        "authors": [Author(given_name="Jane", family_name="Doe", full_name="Jane Doe")],
        "keywords": ["machine learning", "healthcare"],
    }
    defaults.update(kwargs)
    return Paper(**defaults)


# ============================================================================
# Validation tests
# ============================================================================


class TestValidate:
    def test_empty_config_valid(self):
        is_valid, errors = MetadataExtractionStep.validate({})
        assert is_valid is True
        assert errors == []

    def test_invalid_model_type(self):
        is_valid, errors = MetadataExtractionStep.validate({"model": 123})
        assert is_valid is False
        assert any("model" in e for e in errors)

    def test_invalid_prompt_path(self):
        is_valid, errors = MetadataExtractionStep.validate({"prompt": "/nonexistent/path.md"})
        assert is_valid is False
        assert any("not found" in e for e in errors)

    def test_valid_prompt_path(self, tmp_path):
        prompt = tmp_path / "test.md"
        prompt.write_text("test prompt")
        is_valid, errors = MetadataExtractionStep.validate({"prompt": str(prompt)})
        assert is_valid is True

    def test_invalid_overwrite_type(self):
        is_valid, errors = MetadataExtractionStep.validate({"overwrite": "yes"})
        assert is_valid is False
        assert any("overwrite" in e for e in errors)

    def test_invalid_use_pdf_type(self):
        is_valid, errors = MetadataExtractionStep.validate({"use_pdf": "yes"})
        assert is_valid is False
        assert any("use_pdf" in e for e in errors)

    def test_valid_use_pdf(self):
        is_valid, errors = MetadataExtractionStep.validate({"use_pdf": True})
        assert is_valid is True


# ============================================================================
# Format paper text tests
# ============================================================================


class TestFormatPaperText:
    def test_formats_all_fields(self):
        paper = _make_paper()
        text = _format_paper_text(paper)
        assert "TITLE: Machine Learning in Healthcare" in text
        assert "ABSTRACT:" in text
        assert "KEYWORDS: machine learning, healthcare" in text
        assert "YEAR: 2024" in text
        assert "AUTHORS: Jane Doe" in text

    def test_handles_missing_fields(self):
        paper = _make_paper(title=None, abstract=None, keywords=[], year=None, authors=[])
        text = _format_paper_text(paper)
        assert text == ""


# ============================================================================
# Apply metadata tests
# ============================================================================


class TestApplyMetadata:
    def test_sets_research_method(self):
        paper = _make_paper()
        response = {
            "title": "Machine Learning in Healthcare",
            "research_method": {
                "empirical": True,
                "approach": "quantitative",
                "industry": "healthcare",
            },
        }
        _apply_metadata(paper, response, "claude-haiku-4-5-20251001", datetime.now(timezone.utc))

        assert paper.research_method is not None
        assert paper.research_method.empirical is True
        assert paper.research_method.approach == "quantitative"
        assert paper.research_method.industry == "healthcare"

    def test_does_not_overwrite_existing_title(self):
        paper = _make_paper(title="Original Title")
        response = {"title": "New Title", "research_method": {"empirical": False}}
        _apply_metadata(paper, response, "test", datetime.now(timezone.utc))
        assert paper.title == "Original Title"

    def test_fills_missing_title(self):
        paper = _make_paper(title=None)
        response = {"title": "Extracted Title", "research_method": {"empirical": False}}
        _apply_metadata(paper, response, "test", datetime.now(timezone.utc))
        assert paper.title == "Extracted Title"

    def test_fills_missing_authors(self):
        paper = _make_paper(authors=[])
        response = {
            "authors": [{"given_name": "John", "family_name": "Smith"}],
            "research_method": {"empirical": True},
        }
        _apply_metadata(paper, response, "test", datetime.now(timezone.utc))
        assert len(paper.authors) == 1
        assert paper.authors[0].family_name == "Smith"

    def test_rejects_invalid_approach(self):
        paper = _make_paper()
        response = {
            "research_method": {
                "empirical": True,
                "approach": "invalid_value",
                "industry": None,
            },
        }
        _apply_metadata(paper, response, "test", datetime.now(timezone.utc))
        assert paper.research_method.approach is None

    def test_handles_missing_research_method(self):
        paper = _make_paper()
        response = {"title": "Some Title"}
        _apply_metadata(paper, response, "test", datetime.now(timezone.utc))
        assert paper.research_method is None


# ============================================================================
# Execute tests (mocked Claude)
# ============================================================================


class TestExecute:
    @patch("paper_scanner.steps.metadata_extraction.ClaudeHandler")
    def test_extracts_metadata_for_papers(self, mock_claude_class, tmp_path):
        mock_claude = MagicMock()
        mock_claude_class.return_value = mock_claude
        mock_claude.call.return_value = (
            {
                "title": "ML in Healthcare",
                "authors": [{"given_name": "Jane", "family_name": "Doe"}],
                "abstract": "Abstract text",
                "keywords": ["ml"],
                "year": 2024,
                "research_method": {
                    "empirical": True,
                    "approach": "quantitative",
                    "industry": "healthcare",
                },
            },
            {"input_tokens": 500, "output_tokens": 200},
        )

        # Create a prompt file
        prompt_file = tmp_path / "prompt.md"
        prompt_file.write_text("Test prompt {json_schema}")

        # Set up step
        from paper_scanner.core.database import PapersDatabase

        db = PapersDatabase()
        paper = _make_paper(research_method=None)
        db.add(paper)

        step = MetadataExtractionStep(
            general_config={},
            db=db,
            cache_dir=tmp_path,
        )

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            result = step.execute({"prompt": str(prompt_file)})

        assert result.status == StepStatus.SUCCESS
        assert result.stats["extracted"] == 1
        assert result.stats["errors"] == 0
        mock_claude.call.assert_called_once()

    @patch("paper_scanner.steps.metadata_extraction.ClaudeHandler")
    def test_handles_api_error(self, mock_claude_class, tmp_path):
        mock_claude = MagicMock()
        mock_claude_class.return_value = mock_claude
        mock_claude.call.return_value = (None, {"input_tokens": 0, "output_tokens": 0})

        prompt_file = tmp_path / "prompt.md"
        prompt_file.write_text("Test prompt {json_schema}")

        from paper_scanner.core.database import PapersDatabase

        db = PapersDatabase()
        paper = _make_paper(research_method=None)
        db.add(paper)

        step = MetadataExtractionStep(
            general_config={},
            db=db,
            cache_dir=tmp_path,
        )

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            result = step.execute({"prompt": str(prompt_file)})

        assert result.status == StepStatus.SUCCESS
        assert result.stats["errors"] == 1
        assert result.stats["extracted"] == 0

    def test_raises_without_api_key(self, tmp_path):
        from paper_scanner.core.database import PapersDatabase

        step = MetadataExtractionStep(
            general_config={},
            db=PapersDatabase(),
            cache_dir=tmp_path,
        )

        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(Exception, match="ANTHROPIC_API_KEY"):
                step.execute({})

    @patch("paper_scanner.steps.metadata_extraction.ClaudeHandler")
    def test_no_papers_returns_success(self, mock_claude_class, tmp_path):
        prompt_file = tmp_path / "prompt.md"
        prompt_file.write_text("Test prompt {json_schema}")

        from paper_scanner.core.database import PapersDatabase

        step = MetadataExtractionStep(
            general_config={},
            db=PapersDatabase(),
            cache_dir=tmp_path,
        )

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            result = step.execute({"prompt": str(prompt_file)})

        assert result.status == StepStatus.SUCCESS
        assert result.stats["total_papers"] == 0

    @patch("paper_scanner.steps.metadata_extraction.ClaudeHandler")
    def test_dry_run_does_not_persist(self, mock_claude_class, tmp_path):
        mock_claude = MagicMock()
        mock_claude_class.return_value = mock_claude
        mock_claude.call.return_value = (
            {
                "research_method": {"empirical": True, "approach": "qualitative", "industry": None},
            },
            {"input_tokens": 100, "output_tokens": 50},
        )

        prompt_file = tmp_path / "prompt.md"
        prompt_file.write_text("Test prompt {json_schema}")

        from paper_scanner.core.database import PapersDatabase

        db = PapersDatabase()
        paper = _make_paper(research_method=None)
        db.add(paper)

        step = MetadataExtractionStep(general_config={}, db=db, cache_dir=tmp_path)

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            result = step.execute({"prompt": str(prompt_file)}, dry_run=True)

        assert result.stats["extracted"] == 1
        # Paper should NOT have been updated in db
        assert paper.research_method is None

    @patch("paper_scanner.steps.metadata_extraction.ClaudeHandler")
    def test_sends_pdf_when_available(self, mock_claude_class, tmp_path):
        """When use_pdf=True (default) and PDF exists, send PDF path to Claude."""
        mock_claude = MagicMock()
        mock_claude_class.return_value = mock_claude
        mock_claude.call.return_value = (
            {"research_method": {"empirical": True, "approach": "quantitative", "industry": None}},
            {"input_tokens": 500, "output_tokens": 200},
        )

        prompt_file = tmp_path / "prompt.md"
        prompt_file.write_text("Test prompt {json_schema}")

        # Create a fake PDF file
        pdf_file = tmp_path / "paper.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake content")

        from paper_scanner.core.database import PapersDatabase

        db = PapersDatabase()
        paper = _make_paper(
            research_method=None,
            pdf_info=PDFInfo(file_path=str(pdf_file)),
        )
        db.add(paper)

        step = MetadataExtractionStep(general_config={}, db=db, cache_dir=tmp_path)

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            step.execute({"prompt": str(prompt_file)})

        # Verify PDF path was sent to Claude
        call_args = mock_claude.call.call_args
        assert call_args.kwargs["text"] == str(pdf_file)

    @patch("paper_scanner.steps.metadata_extraction.ClaudeHandler")
    def test_falls_back_to_text_when_no_pdf(self, mock_claude_class, tmp_path):
        """When paper has no PDF info, fall back to formatted text."""
        mock_claude = MagicMock()
        mock_claude_class.return_value = mock_claude
        mock_claude.call.return_value = (
            {"research_method": {"empirical": True, "approach": "qualitative", "industry": None}},
            {"input_tokens": 100, "output_tokens": 50},
        )

        prompt_file = tmp_path / "prompt.md"
        prompt_file.write_text("Test prompt {json_schema}")

        from paper_scanner.core.database import PapersDatabase

        db = PapersDatabase()
        paper = _make_paper(research_method=None)  # No pdf_info
        db.add(paper)

        step = MetadataExtractionStep(general_config={}, db=db, cache_dir=tmp_path)

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            step.execute({"prompt": str(prompt_file)})

        call_args = mock_claude.call.call_args
        assert "TITLE:" in call_args.kwargs["text"]

    @patch("paper_scanner.steps.metadata_extraction.ClaudeHandler")
    def test_use_pdf_false_forces_text(self, mock_claude_class, tmp_path):
        """When use_pdf=False, always use text even if PDF exists."""
        mock_claude = MagicMock()
        mock_claude_class.return_value = mock_claude
        mock_claude.call.return_value = (
            {"research_method": {"empirical": False}},
            {"input_tokens": 100, "output_tokens": 50},
        )

        prompt_file = tmp_path / "prompt.md"
        prompt_file.write_text("Test prompt {json_schema}")

        pdf_file = tmp_path / "paper.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake content")

        from paper_scanner.core.database import PapersDatabase

        db = PapersDatabase()
        paper = _make_paper(
            research_method=None,
            pdf_info=PDFInfo(file_path=str(pdf_file)),
        )
        db.add(paper)

        step = MetadataExtractionStep(general_config={}, db=db, cache_dir=tmp_path)

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            step.execute({"prompt": str(prompt_file), "use_pdf": False})

        call_args = mock_claude.call.call_args
        assert "TITLE:" in call_args.kwargs["text"]

    @patch("paper_scanner.steps.metadata_extraction.ClaudeHandler")
    def test_falls_back_to_text_when_pdf_missing_on_disk(self, mock_claude_class, tmp_path):
        """When pdf_info.file_path is set but file doesn't exist, fall back to text."""
        mock_claude = MagicMock()
        mock_claude_class.return_value = mock_claude
        mock_claude.call.return_value = (
            {"research_method": {"empirical": True, "approach": "quantitative", "industry": None}},
            {"input_tokens": 100, "output_tokens": 50},
        )

        prompt_file = tmp_path / "prompt.md"
        prompt_file.write_text("Test prompt {json_schema}")

        from paper_scanner.core.database import PapersDatabase

        db = PapersDatabase()
        paper = _make_paper(
            research_method=None,
            pdf_info=PDFInfo(file_path="/nonexistent/paper.pdf"),
        )
        db.add(paper)

        step = MetadataExtractionStep(general_config={}, db=db, cache_dir=tmp_path)

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            step.execute({"prompt": str(prompt_file)})

        call_args = mock_claude.call.call_args
        assert "TITLE:" in call_args.kwargs["text"]


# ============================================================================
# Cache tests
# ============================================================================


class TestCache:
    LLM_RESPONSE = {
        "title": "ML in Healthcare",
        "authors": [{"given_name": "Jane", "family_name": "Doe"}],
        "abstract": "Abstract text",
        "keywords": ["ml"],
        "year": 2024,
        "research_method": {
            "empirical": True,
            "approach": "quantitative",
            "industry": "healthcare",
        },
    }

    @patch("paper_scanner.steps.metadata_extraction.ClaudeHandler")
    @patch("paper_scanner.steps.metadata_extraction.get_json_cache_dir")
    def test_caches_llm_response(self, mock_cache_dir, mock_claude_class, tmp_path):
        """When cache=True (default), LLM responses are stored in cache."""
        mock_cache_dir.return_value = tmp_path / "cache"
        mock_claude = MagicMock()
        mock_claude_class.return_value = mock_claude
        mock_claude.call.return_value = (self.LLM_RESPONSE, {"input_tokens": 500, "output_tokens": 200})

        prompt_file = tmp_path / "prompt.md"
        prompt_file.write_text("Test prompt {json_schema}")

        from paper_scanner.core.database import PapersDatabase

        db = PapersDatabase()
        paper = _make_paper(research_method=None, doi="10.1234/test.001")
        db.add(paper)

        step = MetadataExtractionStep(general_config={}, db=db, cache_dir=tmp_path)

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            step.execute({"prompt": str(prompt_file)})

        # Verify cache directory was populated
        cache_files = list((tmp_path / "cache" / "llm" / "metadata_extraction").glob("*.json"))
        assert len(cache_files) == 1

    @patch("paper_scanner.steps.metadata_extraction.ClaudeHandler")
    @patch("paper_scanner.steps.metadata_extraction.get_json_cache_dir")
    def test_uses_cached_response(self, mock_cache_dir, mock_claude_class, tmp_path):
        """When use_cache=True (default), cached responses are used instead of LLM calls."""
        mock_cache_dir.return_value = tmp_path / "cache"
        mock_claude = MagicMock()
        mock_claude_class.return_value = mock_claude
        mock_claude.call.return_value = (self.LLM_RESPONSE, {"input_tokens": 500, "output_tokens": 200})

        prompt_file = tmp_path / "prompt.md"
        prompt_file.write_text("Test prompt {json_schema}")

        from paper_scanner.core.database import PapersDatabase

        # First run: populate cache
        db1 = PapersDatabase()
        paper1 = _make_paper(research_method=None, doi="10.1234/test.002")
        db1.add(paper1)

        step1 = MetadataExtractionStep(general_config={}, db=db1, cache_dir=tmp_path)
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            step1.execute({"prompt": str(prompt_file)})

        assert mock_claude.call.call_count == 1

        # Second run: should use cache, not call LLM
        db2 = PapersDatabase()
        paper2 = _make_paper(research_method=None, doi="10.1234/test.002")
        db2.add(paper2)

        step2 = MetadataExtractionStep(general_config={}, db=db2, cache_dir=tmp_path)
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            result = step2.execute({"prompt": str(prompt_file)})

        assert mock_claude.call.call_count == 1  # No additional LLM call
        assert result.stats["cache_hits"] == 1
        assert result.stats["extracted"] == 1

    @patch("paper_scanner.steps.metadata_extraction.ClaudeHandler")
    @patch("paper_scanner.steps.metadata_extraction.get_json_cache_dir")
    def test_use_cache_false_skips_cache_lookup(self, mock_cache_dir, mock_claude_class, tmp_path):
        """When use_cache=False, always call LLM even if cache exists."""
        mock_cache_dir.return_value = tmp_path / "cache"
        mock_claude = MagicMock()
        mock_claude_class.return_value = mock_claude
        mock_claude.call.return_value = (self.LLM_RESPONSE, {"input_tokens": 500, "output_tokens": 200})

        prompt_file = tmp_path / "prompt.md"
        prompt_file.write_text("Test prompt {json_schema}")

        from paper_scanner.core.database import PapersDatabase

        # First run: populate cache
        db1 = PapersDatabase()
        paper1 = _make_paper(research_method=None, doi="10.1234/test.003")
        db1.add(paper1)

        step1 = MetadataExtractionStep(general_config={}, db=db1, cache_dir=tmp_path)
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            step1.execute({"prompt": str(prompt_file)})

        # Second run with use_cache=False: should call LLM again
        db2 = PapersDatabase()
        paper2 = _make_paper(research_method=None, doi="10.1234/test.003")
        db2.add(paper2)

        step2 = MetadataExtractionStep(general_config={}, db=db2, cache_dir=tmp_path)
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            result = step2.execute({"prompt": str(prompt_file), "use_cache": False})

        assert mock_claude.call.call_count == 2  # Called LLM both times
        assert result.stats["cache_hits"] == 0

    @patch("paper_scanner.steps.metadata_extraction.ClaudeHandler")
    @patch("paper_scanner.steps.metadata_extraction.get_json_cache_dir")
    def test_cache_false_does_not_store(self, mock_cache_dir, mock_claude_class, tmp_path):
        """When cache=False, LLM responses are not stored."""
        mock_cache_dir.return_value = tmp_path / "cache"
        mock_claude = MagicMock()
        mock_claude_class.return_value = mock_claude
        mock_claude.call.return_value = (self.LLM_RESPONSE, {"input_tokens": 500, "output_tokens": 200})

        prompt_file = tmp_path / "prompt.md"
        prompt_file.write_text("Test prompt {json_schema}")

        from paper_scanner.core.database import PapersDatabase

        db = PapersDatabase()
        paper = _make_paper(research_method=None, doi="10.1234/test.004")
        db.add(paper)

        step = MetadataExtractionStep(general_config={}, db=db, cache_dir=tmp_path)

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            step.execute({"prompt": str(prompt_file), "cache": False, "use_cache": False})

        # Cache directory may exist but should have no files
        cache_dir = tmp_path / "cache" / "llm" / "metadata_extraction"
        if cache_dir.exists():
            cache_files = list(cache_dir.glob("*.json"))
            assert len(cache_files) == 0

    @patch("paper_scanner.steps.metadata_extraction.ClaudeHandler")
    @patch("paper_scanner.steps.metadata_extraction.get_json_cache_dir")
    def test_no_cache_for_papers_without_doi(self, mock_cache_dir, mock_claude_class, tmp_path):
        """Papers without DOI cannot be cached (no stable key)."""
        mock_cache_dir.return_value = tmp_path / "cache"
        mock_claude = MagicMock()
        mock_claude_class.return_value = mock_claude
        mock_claude.call.return_value = (self.LLM_RESPONSE, {"input_tokens": 500, "output_tokens": 200})

        prompt_file = tmp_path / "prompt.md"
        prompt_file.write_text("Test prompt {json_schema}")

        from paper_scanner.core.database import PapersDatabase

        db = PapersDatabase()
        paper = _make_paper(research_method=None, doi=None)
        db.add(paper)

        step = MetadataExtractionStep(general_config={}, db=db, cache_dir=tmp_path)

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            result = step.execute({"prompt": str(prompt_file)})

        assert result.stats["extracted"] == 1
        assert result.stats["cache_hits"] == 0
        # LLM was called (no cache available)
        mock_claude.call.assert_called_once()


# ============================================================================
# Validation — cache options
# ============================================================================


class TestValidateCache:
    def test_valid_cache_options(self):
        is_valid, errors = MetadataExtractionStep.validate({"cache": True, "use_cache": False})
        assert is_valid is True
        assert errors == []

    def test_invalid_cache_type(self):
        is_valid, errors = MetadataExtractionStep.validate({"cache": "yes"})
        assert is_valid is False
        assert any("cache" in e for e in errors)

    def test_invalid_use_cache_type(self):
        is_valid, errors = MetadataExtractionStep.validate({"use_cache": "no"})
        assert is_valid is False
        assert any("use_cache" in e for e in errors)
