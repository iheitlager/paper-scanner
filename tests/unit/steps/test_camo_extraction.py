"""Tests for CAMOExtractionStep."""

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from paper_scanner.core.database import PapersDatabase
from paper_scanner.core.enum import PaperType, ScreeningDecision, StepStatus
from paper_scanner.core.models import Author, ConceptualAnalysis, PDFInfo, Paper
from paper_scanner.steps.camo_extraction import (
    CAMOExtractionStep,
    _format_paper_text,
    _parse_camo_statements,
)


def _make_paper(included=True, **kwargs):
    defaults = {
        "id": str(uuid.uuid4()),
        "cite_key": f"test_{uuid.uuid4().hex[:6]}",
        "title": "Digital Innovation in Manufacturing",
        "abstract": "We study how manufacturers adopt digital platforms.",
        "paper_type": PaperType.JOURNAL_ARTICLE,
        "year": 2023,
        "authors": [Author(given_name="Alice", family_name="Chen", full_name="Alice Chen")],
        "keywords": ["digital innovation", "manufacturing"],
    }
    defaults.update(kwargs)
    paper = Paper(**defaults)
    if included:
        paper.screening.final_decision = ScreeningDecision.INCLUDED
    return paper


SAMPLE_RESPONSE = {
    "camo_statements": [
        {
            "context": "Manufacturing firms facing digital transformation",
            "agency": "IT departments and external consultants",
            "mechanism": "Adoption of cloud-based ERP systems",
            "outcome": "Improved operational efficiency and reduced costs",
            "full_statement": "Manufacturing firms facing digital transformation engaged IT departments and external consultants to adopt cloud-based ERP systems, resulting in improved operational efficiency.",
            "confidence": 0.85,
            "innovation_type": "process",
            "it_suppliers": ["SAP", "Oracle"],
            "regular_suppliers": [],
        },
        {
            "context": "Supply chain coordination challenges",
            "agency": "Supply chain managers",
            "mechanism": "Implementation of blockchain-based tracking",
            "outcome": "Enhanced transparency and trust among partners",
            "full_statement": "Supply chain managers implemented blockchain-based tracking to address coordination challenges, enhancing transparency and trust.",
            "confidence": 0.72,
            "innovation_type": "technological",
            "it_suppliers": ["IBM"],
            "regular_suppliers": ["Maersk"],
        },
    ]
}


# ============================================================================
# Validation tests
# ============================================================================


class TestValidate:
    def test_empty_config(self):
        is_valid, errors = CAMOExtractionStep.validate({})
        assert is_valid is True

    def test_invalid_model_type(self):
        is_valid, errors = CAMOExtractionStep.validate({"model": 123})
        assert is_valid is False

    def test_invalid_prompt_path(self):
        is_valid, errors = CAMOExtractionStep.validate({"prompt": "/no/such.md"})
        assert is_valid is False

    def test_valid_prompt(self, tmp_path):
        p = tmp_path / "prompt.md"
        p.write_text("test")
        is_valid, errors = CAMOExtractionStep.validate({"prompt": str(p)})
        assert is_valid is True

    def test_invalid_use_pdf_type(self):
        is_valid, errors = CAMOExtractionStep.validate({"use_pdf": "yes"})
        assert is_valid is False
        assert any("use_pdf" in e for e in errors)

    def test_valid_use_pdf(self):
        is_valid, errors = CAMOExtractionStep.validate({"use_pdf": True})
        assert is_valid is True


# ============================================================================
# Parse CAMO statements tests
# ============================================================================


class TestParseCamoStatements:
    def test_parses_valid_statements(self):
        statements = _parse_camo_statements(SAMPLE_RESPONSE, "test", datetime.now(timezone.utc))
        assert len(statements) == 2
        assert statements[0].context == "Manufacturing firms facing digital transformation"
        assert statements[0].mechanism == "Adoption of cloud-based ERP systems"
        assert statements[0].confidence == 0.85
        assert statements[0].it_suppliers == ["SAP", "Oracle"]
        assert statements[1].innovation_type == "technological"

    def test_skips_incomplete_statements(self):
        response = {
            "camo_statements": [
                {"context": "Some context", "agency": "", "mechanism": "Something", "outcome": "Result"},
            ]
        }
        statements = _parse_camo_statements(response, "test", datetime.now(timezone.utc))
        assert len(statements) == 0  # agency is empty string

    def test_handles_empty_array(self):
        response = {"camo_statements": []}
        statements = _parse_camo_statements(response, "test", datetime.now(timezone.utc))
        assert len(statements) == 0

    def test_handles_missing_key(self):
        response = {}
        statements = _parse_camo_statements(response, "test", datetime.now(timezone.utc))
        assert len(statements) == 0

    def test_handles_non_list(self):
        response = {"camo_statements": "invalid"}
        statements = _parse_camo_statements(response, "test", datetime.now(timezone.utc))
        assert len(statements) == 0

    def test_clamps_confidence(self):
        response = {
            "camo_statements": [
                {
                    "context": "C",
                    "agency": "A",
                    "mechanism": "M",
                    "outcome": "O",
                    "confidence": 1.5,
                }
            ]
        }
        statements = _parse_camo_statements(response, "test", datetime.now(timezone.utc))
        assert len(statements) == 1
        assert statements[0].confidence == 1.0

    def test_handles_non_numeric_confidence(self):
        response = {
            "camo_statements": [
                {
                    "context": "C",
                    "agency": "A",
                    "mechanism": "M",
                    "outcome": "O",
                    "confidence": "high",
                }
            ]
        }
        statements = _parse_camo_statements(response, "test", datetime.now(timezone.utc))
        assert len(statements) == 1
        assert statements[0].confidence == 0.5  # default

    def test_generates_full_statement_if_missing(self):
        response = {
            "camo_statements": [
                {"context": "C", "agency": "A", "mechanism": "M", "outcome": "O"}
            ]
        }
        statements = _parse_camo_statements(response, "test", datetime.now(timezone.utc))
        assert statements[0].full_statement == "C A M O"

    def test_skips_non_dict_items(self):
        response = {"camo_statements": ["not a dict", 42, None]}
        statements = _parse_camo_statements(response, "test", datetime.now(timezone.utc))
        assert len(statements) == 0


# ============================================================================
# Format paper text tests
# ============================================================================


class TestFormatPaperText:
    def test_formats_all_fields(self):
        paper = _make_paper()
        text = _format_paper_text(paper)
        assert "TITLE:" in text
        assert "ABSTRACT:" in text

    def test_handles_empty_paper(self):
        paper = _make_paper(title=None, abstract=None, keywords=[], year=None, authors=[])
        text = _format_paper_text(paper)
        assert text == ""


# ============================================================================
# Execute tests (mocked Claude)
# ============================================================================


class TestExecute:
    @patch("paper_scanner.steps.camo_extraction.ClaudeHandler")
    def test_extracts_camo_statements(self, mock_claude_class, tmp_path):
        mock_claude = MagicMock()
        mock_claude_class.return_value = mock_claude
        mock_claude.call.return_value = (
            SAMPLE_RESPONSE,
            {"input_tokens": 1000, "output_tokens": 500},
        )

        prompt_file = tmp_path / "prompt.md"
        prompt_file.write_text("Test {json_schema}")

        db = PapersDatabase()
        paper = _make_paper()
        db.add(paper)

        step = CAMOExtractionStep(general_config={}, db=db, cache_dir=tmp_path)

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            result = step.execute({"prompt": str(prompt_file)})

        assert result.status == StepStatus.SUCCESS
        assert result.stats["extracted"] == 1
        assert result.stats["total_statements"] == 2
        assert paper.conceptual_analysis is not None
        assert len(paper.conceptual_analysis.camo_statements) == 2

    @patch("paper_scanner.steps.camo_extraction.ClaudeHandler")
    def test_skips_non_included_papers(self, mock_claude_class, tmp_path):
        mock_claude = MagicMock()
        mock_claude_class.return_value = mock_claude

        prompt_file = tmp_path / "prompt.md"
        prompt_file.write_text("Test {json_schema}")

        db = PapersDatabase()
        paper = _make_paper(included=False)
        db.add(paper)

        step = CAMOExtractionStep(general_config={}, db=db, cache_dir=tmp_path)

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            result = step.execute({"prompt": str(prompt_file)})

        assert result.stats["total_papers"] == 0
        mock_claude.call.assert_not_called()

    @patch("paper_scanner.steps.camo_extraction.ClaudeHandler")
    def test_skips_papers_with_existing_camo(self, mock_claude_class, tmp_path):
        mock_claude = MagicMock()
        mock_claude_class.return_value = mock_claude

        prompt_file = tmp_path / "prompt.md"
        prompt_file.write_text("Test {json_schema}")

        db = PapersDatabase()
        paper = _make_paper()
        from paper_scanner.core.models import CAMOStatement

        paper.conceptual_analysis = ConceptualAnalysis(
            camo_statements=[
                CAMOStatement(
                    context="C", agency="A", mechanism="M", outcome="O",
                    full_statement="Existing", confidence=0.9,
                )
            ]
        )
        db.add(paper)

        step = CAMOExtractionStep(general_config={}, db=db, cache_dir=tmp_path)

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            result = step.execute({"prompt": str(prompt_file)})

        assert result.stats["total_papers"] == 0

    @patch("paper_scanner.steps.camo_extraction.ClaudeHandler")
    def test_handles_api_failure(self, mock_claude_class, tmp_path):
        mock_claude = MagicMock()
        mock_claude_class.return_value = mock_claude
        mock_claude.call.return_value = (None, {"input_tokens": 0, "output_tokens": 0})

        prompt_file = tmp_path / "prompt.md"
        prompt_file.write_text("Test {json_schema}")

        db = PapersDatabase()
        db.add(_make_paper())

        step = CAMOExtractionStep(general_config={}, db=db, cache_dir=tmp_path)

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            result = step.execute({"prompt": str(prompt_file)})

        assert result.stats["errors"] == 1
        assert result.stats["extracted"] == 0

    @patch("paper_scanner.steps.camo_extraction.ClaudeHandler")
    def test_dry_run_does_not_persist(self, mock_claude_class, tmp_path):
        mock_claude = MagicMock()
        mock_claude_class.return_value = mock_claude
        mock_claude.call.return_value = (
            SAMPLE_RESPONSE,
            {"input_tokens": 500, "output_tokens": 250},
        )

        prompt_file = tmp_path / "prompt.md"
        prompt_file.write_text("Test {json_schema}")

        db = PapersDatabase()
        paper = _make_paper()
        db.add(paper)

        step = CAMOExtractionStep(general_config={}, db=db, cache_dir=tmp_path)

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            result = step.execute({"prompt": str(prompt_file)}, dry_run=True)

        assert result.stats["extracted"] == 1
        assert paper.conceptual_analysis is None

    def test_raises_without_api_key(self, tmp_path):
        step = CAMOExtractionStep(general_config={}, db=PapersDatabase(), cache_dir=tmp_path)

        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(Exception, match="ANTHROPIC_API_KEY"):
                step.execute({})

    @patch("paper_scanner.steps.camo_extraction.ClaudeHandler")
    def test_sends_pdf_when_available(self, mock_claude_class, tmp_path):
        """When use_pdf=True (default) and PDF exists, send PDF path to Claude."""
        mock_claude = MagicMock()
        mock_claude_class.return_value = mock_claude
        mock_claude.call.return_value = (
            SAMPLE_RESPONSE,
            {"input_tokens": 5000, "output_tokens": 500},
        )

        prompt_file = tmp_path / "prompt.md"
        prompt_file.write_text("Test {json_schema}")

        pdf_file = tmp_path / "paper.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake content")

        db = PapersDatabase()
        paper = _make_paper(pdf_info=PDFInfo(file_path=str(pdf_file)))
        db.add(paper)

        step = CAMOExtractionStep(general_config={}, db=db, cache_dir=tmp_path)

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            step.execute({"prompt": str(prompt_file)})

        call_args = mock_claude.call.call_args
        assert call_args.kwargs["text"] == str(pdf_file)

    @patch("paper_scanner.steps.camo_extraction.ClaudeHandler")
    def test_falls_back_to_text_when_no_pdf(self, mock_claude_class, tmp_path):
        """When paper has no PDF info, fall back to formatted text."""
        mock_claude = MagicMock()
        mock_claude_class.return_value = mock_claude
        mock_claude.call.return_value = (
            SAMPLE_RESPONSE,
            {"input_tokens": 100, "output_tokens": 50},
        )

        prompt_file = tmp_path / "prompt.md"
        prompt_file.write_text("Test {json_schema}")

        db = PapersDatabase()
        paper = _make_paper()  # No pdf_info
        db.add(paper)

        step = CAMOExtractionStep(general_config={}, db=db, cache_dir=tmp_path)

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            step.execute({"prompt": str(prompt_file)})

        call_args = mock_claude.call.call_args
        assert "TITLE:" in call_args.kwargs["text"]

    @patch("paper_scanner.steps.camo_extraction.ClaudeHandler")
    def test_use_pdf_false_forces_text(self, mock_claude_class, tmp_path):
        """When use_pdf=False, always use text even if PDF exists."""
        mock_claude = MagicMock()
        mock_claude_class.return_value = mock_claude
        mock_claude.call.return_value = (
            SAMPLE_RESPONSE,
            {"input_tokens": 100, "output_tokens": 50},
        )

        prompt_file = tmp_path / "prompt.md"
        prompt_file.write_text("Test {json_schema}")

        pdf_file = tmp_path / "paper.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake content")

        db = PapersDatabase()
        paper = _make_paper(pdf_info=PDFInfo(file_path=str(pdf_file)))
        db.add(paper)

        step = CAMOExtractionStep(general_config={}, db=db, cache_dir=tmp_path)

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            step.execute({"prompt": str(prompt_file), "use_pdf": False})

        call_args = mock_claude.call.call_args
        assert "TITLE:" in call_args.kwargs["text"]
