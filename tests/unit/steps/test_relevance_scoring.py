"""Tests for RelevanceScoringStep."""

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from paper_scanner.core.enum import PaperType, ScreeningDecision, StepStatus
from paper_scanner.core.models import Author, PDFInfo, Paper, RelevanceScore
from paper_scanner.steps.relevance_scoring import (
    RelevanceScoringStep,
    _format_paper_text,
    _parse_relevance,
)


def _make_paper(**kwargs):
    defaults = {
        "id": str(uuid.uuid4()),
        "cite_key": f"test_{uuid.uuid4().hex[:6]}",
        "title": "Innovation in Supply Chains",
        "abstract": "We study digital innovation in supply chain management.",
        "paper_type": PaperType.JOURNAL_ARTICLE,
        "year": 2023,
        "authors": [Author(given_name="John", family_name="Smith", full_name="John Smith")],
        "keywords": ["innovation", "supply chain"],
    }
    defaults.update(kwargs)
    return Paper(**defaults)


# ============================================================================
# Validation tests
# ============================================================================


class TestValidate:
    def test_empty_config_valid(self):
        is_valid, errors = RelevanceScoringStep.validate({})
        assert is_valid is True

    def test_invalid_model_type(self):
        is_valid, errors = RelevanceScoringStep.validate({"model": 123})
        assert is_valid is False
        assert any("model" in e for e in errors)

    def test_invalid_prompt_path(self):
        is_valid, errors = RelevanceScoringStep.validate({"prompt": "/no/such/file.md"})
        assert is_valid is False

    def test_valid_prompt(self, tmp_path):
        p = tmp_path / "prompt.md"
        p.write_text("test")
        is_valid, errors = RelevanceScoringStep.validate({"prompt": str(p)})
        assert is_valid is True

    def test_invalid_use_pdf_type(self):
        is_valid, errors = RelevanceScoringStep.validate({"use_pdf": "yes"})
        assert is_valid is False
        assert any("use_pdf" in e for e in errors)

    def test_valid_use_pdf(self):
        is_valid, errors = RelevanceScoringStep.validate({"use_pdf": False})
        assert is_valid is True


# ============================================================================
# Parse relevance tests
# ============================================================================


class TestParseRelevance:
    def test_valid_response(self):
        response = {
            "relevance": 0.8,
            "confidence": 0.9,
            "justification": "Directly addresses the topic",
            "matching_keywords": ["innovation"],
            "research_question_alignment": "Strong alignment",
        }
        result = _parse_relevance(response, "test-model", datetime.now(timezone.utc))
        assert result is not None
        assert result.relevance == 0.8
        assert result.confidence == 0.9
        assert result.justification == "Directly addresses the topic"

    def test_out_of_range_relevance(self):
        response = {"relevance": 1.5, "confidence": 0.5, "justification": ""}
        result = _parse_relevance(response, "test", datetime.now(timezone.utc))
        assert result is None

    def test_out_of_range_confidence(self):
        response = {"relevance": 0.5, "confidence": -0.1, "justification": ""}
        result = _parse_relevance(response, "test", datetime.now(timezone.utc))
        assert result is None

    def test_missing_relevance(self):
        response = {"confidence": 0.5, "justification": ""}
        result = _parse_relevance(response, "test", datetime.now(timezone.utc))
        assert result is None

    def test_non_numeric_values(self):
        response = {"relevance": "high", "confidence": "low", "justification": ""}
        result = _parse_relevance(response, "test", datetime.now(timezone.utc))
        assert result is None

    def test_boundary_values(self):
        response = {"relevance": 0.0, "confidence": 1.0, "justification": "Edge case"}
        result = _parse_relevance(response, "test", datetime.now(timezone.utc))
        assert result is not None
        assert result.relevance == 0.0
        assert result.confidence == 1.0


# ============================================================================
# Format paper text tests
# ============================================================================


class TestFormatPaperText:
    def test_formats_all_fields(self):
        paper = _make_paper()
        text = _format_paper_text(paper)
        assert "TITLE:" in text
        assert "ABSTRACT:" in text
        assert "KEYWORDS:" in text

    def test_handles_empty_paper(self):
        paper = _make_paper(title=None, abstract=None, keywords=[], year=None, authors=[])
        text = _format_paper_text(paper)
        assert text == ""


# ============================================================================
# Execute tests (mocked Claude)
# ============================================================================


class TestExecute:
    @patch("paper_scanner.steps.relevance_scoring.ClaudeHandler")
    def test_scores_papers(self, mock_claude_class, tmp_path):
        mock_claude = MagicMock()
        mock_claude_class.return_value = mock_claude
        mock_claude.call.return_value = (
            {
                "relevance": 0.85,
                "confidence": 0.92,
                "justification": "Directly addresses supply chain innovation",
                "matching_keywords": ["innovation", "supply chain"],
                "research_question_alignment": "Strong alignment with RQ",
            },
            {"input_tokens": 400, "output_tokens": 150},
        )

        prompt_file = tmp_path / "prompt.md"
        prompt_file.write_text("Test {json_schema} {research_question} {keywords}")

        from paper_scanner.core.database import PapersDatabase

        db = PapersDatabase()
        paper = _make_paper()
        db.add(paper)

        step = RelevanceScoringStep(
            general_config={
                "research_question": "How does digital innovation affect supply chains?",
                "keywords": ["innovation", "digital", "supply chain"],
            },
            db=db,
            cache_dir=tmp_path,
        )

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            result = step.execute({"prompt": str(prompt_file)})

        assert result.status == StepStatus.SUCCESS
        assert result.stats["scored"] == 1
        assert result.stats["avg_relevance"] == 0.85
        # Verify paper was updated
        assert paper.screening.relevance_scoring is not None
        assert paper.screening.relevance_scoring.relevance == 0.85

    @patch("paper_scanner.steps.relevance_scoring.ClaudeHandler")
    def test_skips_excluded_papers(self, mock_claude_class, tmp_path):
        mock_claude = MagicMock()
        mock_claude_class.return_value = mock_claude

        prompt_file = tmp_path / "prompt.md"
        prompt_file.write_text("Test {json_schema} {research_question} {keywords}")

        from paper_scanner.core.database import PapersDatabase

        db = PapersDatabase()
        paper = _make_paper()
        paper.screening.final_decision = ScreeningDecision.EXCLUDED
        db.add(paper)

        step = RelevanceScoringStep(
            general_config={"research_question": "Test RQ", "keywords": []},
            db=db,
            cache_dir=tmp_path,
        )

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            result = step.execute({"prompt": str(prompt_file)})

        assert result.stats["total_papers"] == 0
        mock_claude.call.assert_not_called()

    @patch("paper_scanner.steps.relevance_scoring.ClaudeHandler")
    def test_handles_api_failure(self, mock_claude_class, tmp_path):
        mock_claude = MagicMock()
        mock_claude_class.return_value = mock_claude
        mock_claude.call.return_value = (None, {"input_tokens": 0, "output_tokens": 0})

        prompt_file = tmp_path / "prompt.md"
        prompt_file.write_text("Test {json_schema} {research_question} {keywords}")

        from paper_scanner.core.database import PapersDatabase

        db = PapersDatabase()
        db.add(_make_paper())

        step = RelevanceScoringStep(
            general_config={"research_question": "Test", "keywords": []},
            db=db,
            cache_dir=tmp_path,
        )

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            result = step.execute({"prompt": str(prompt_file)})

        assert result.stats["errors"] == 1
        assert result.stats["scored"] == 0

    def test_raises_without_research_question(self, tmp_path):
        from paper_scanner.core.database import PapersDatabase

        step = RelevanceScoringStep(
            general_config={},
            db=PapersDatabase(),
            cache_dir=tmp_path,
        )

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            with pytest.raises(Exception, match="research_question"):
                step.execute({})

    @patch("paper_scanner.steps.relevance_scoring.ClaudeHandler")
    def test_dry_run_does_not_persist(self, mock_claude_class, tmp_path):
        mock_claude = MagicMock()
        mock_claude_class.return_value = mock_claude
        mock_claude.call.return_value = (
            {
                "relevance": 0.7,
                "confidence": 0.8,
                "justification": "Relevant",
                "matching_keywords": [],
                "research_question_alignment": "Aligned",
            },
            {"input_tokens": 100, "output_tokens": 50},
        )

        prompt_file = tmp_path / "prompt.md"
        prompt_file.write_text("Test {json_schema} {research_question} {keywords}")

        from paper_scanner.core.database import PapersDatabase

        db = PapersDatabase()
        paper = _make_paper()
        db.add(paper)

        step = RelevanceScoringStep(
            general_config={"research_question": "Test", "keywords": []},
            db=db,
            cache_dir=tmp_path,
        )

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            result = step.execute({"prompt": str(prompt_file)}, dry_run=True)

        assert result.stats["scored"] == 1
        assert paper.screening.relevance_scoring is None

    @patch("paper_scanner.steps.relevance_scoring.ClaudeHandler")
    def test_sends_pdf_when_available(self, mock_claude_class, tmp_path):
        """When use_pdf=True (default) and PDF exists, send PDF path to Claude."""
        mock_claude = MagicMock()
        mock_claude_class.return_value = mock_claude
        mock_claude.call.return_value = (
            {
                "relevance": 0.9,
                "confidence": 0.95,
                "justification": "Full paper analysis",
                "matching_keywords": ["innovation"],
                "research_question_alignment": "Strong",
            },
            {"input_tokens": 5000, "output_tokens": 150},
        )

        prompt_file = tmp_path / "prompt.md"
        prompt_file.write_text("Test {json_schema} {research_question} {keywords}")

        pdf_file = tmp_path / "paper.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake content")

        from paper_scanner.core.database import PapersDatabase

        db = PapersDatabase()
        paper = _make_paper(pdf_info=PDFInfo(file_path=str(pdf_file)))
        db.add(paper)

        step = RelevanceScoringStep(
            general_config={"research_question": "Test RQ", "keywords": ["innovation"]},
            db=db,
            cache_dir=tmp_path,
        )

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            step.execute({"prompt": str(prompt_file)})

        call_args = mock_claude.call.call_args
        assert call_args.kwargs["text"] == str(pdf_file)

    @patch("paper_scanner.steps.relevance_scoring.ClaudeHandler")
    def test_falls_back_to_text_when_no_pdf(self, mock_claude_class, tmp_path):
        """When paper has no PDF info, fall back to formatted text."""
        mock_claude = MagicMock()
        mock_claude_class.return_value = mock_claude
        mock_claude.call.return_value = (
            {
                "relevance": 0.7,
                "confidence": 0.8,
                "justification": "Based on abstract",
                "matching_keywords": [],
                "research_question_alignment": "Moderate",
            },
            {"input_tokens": 100, "output_tokens": 50},
        )

        prompt_file = tmp_path / "prompt.md"
        prompt_file.write_text("Test {json_schema} {research_question} {keywords}")

        from paper_scanner.core.database import PapersDatabase

        db = PapersDatabase()
        paper = _make_paper()  # No pdf_info
        db.add(paper)

        step = RelevanceScoringStep(
            general_config={"research_question": "Test RQ", "keywords": []},
            db=db,
            cache_dir=tmp_path,
        )

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            step.execute({"prompt": str(prompt_file)})

        call_args = mock_claude.call.call_args
        assert "TITLE:" in call_args.kwargs["text"]

    @patch("paper_scanner.steps.relevance_scoring.ClaudeHandler")
    def test_use_pdf_false_forces_text(self, mock_claude_class, tmp_path):
        """When use_pdf=False, always use text even if PDF exists."""
        mock_claude = MagicMock()
        mock_claude_class.return_value = mock_claude
        mock_claude.call.return_value = (
            {
                "relevance": 0.6,
                "confidence": 0.7,
                "justification": "Abstract only",
                "matching_keywords": [],
                "research_question_alignment": "Weak",
            },
            {"input_tokens": 100, "output_tokens": 50},
        )

        prompt_file = tmp_path / "prompt.md"
        prompt_file.write_text("Test {json_schema} {research_question} {keywords}")

        pdf_file = tmp_path / "paper.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake content")

        from paper_scanner.core.database import PapersDatabase

        db = PapersDatabase()
        paper = _make_paper(pdf_info=PDFInfo(file_path=str(pdf_file)))
        db.add(paper)

        step = RelevanceScoringStep(
            general_config={"research_question": "Test RQ", "keywords": []},
            db=db,
            cache_dir=tmp_path,
        )

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            step.execute({"prompt": str(prompt_file), "use_pdf": False})

        call_args = mock_claude.call.call_args
        assert "TITLE:" in call_args.kwargs["text"]

    @patch("paper_scanner.steps.relevance_scoring.ClaudeHandler")
    def test_falls_back_to_text_when_pdf_missing_on_disk(self, mock_claude_class, tmp_path):
        """When pdf_info.file_path is set but file doesn't exist, fall back to text."""
        mock_claude = MagicMock()
        mock_claude_class.return_value = mock_claude
        mock_claude.call.return_value = (
            {
                "relevance": 0.7,
                "confidence": 0.8,
                "justification": "Fallback to text",
                "matching_keywords": [],
                "research_question_alignment": "Moderate",
            },
            {"input_tokens": 100, "output_tokens": 50},
        )

        prompt_file = tmp_path / "prompt.md"
        prompt_file.write_text("Test {json_schema} {research_question} {keywords}")

        from paper_scanner.core.database import PapersDatabase

        db = PapersDatabase()
        paper = _make_paper(pdf_info=PDFInfo(file_path="/nonexistent/paper.pdf"))
        db.add(paper)

        step = RelevanceScoringStep(
            general_config={"research_question": "Test RQ", "keywords": []},
            db=db,
            cache_dir=tmp_path,
        )

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            step.execute({"prompt": str(prompt_file)})

        call_args = mock_claude.call.call_args
        assert "TITLE:" in call_args.kwargs["text"]
