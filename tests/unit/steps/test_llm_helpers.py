"""Tests for shared LLM step helpers."""

from paper_scanner.core.models import PDFInfo, Paper
from paper_scanner.steps._llm_helpers import resolve_llm_input, validate_use_pdf


def _dummy_format(paper: Paper) -> str:
    return f"TITLE: {paper.title}"


class TestResolveLlmInput:
    def test_returns_pdf_path_when_exists(self, tmp_path):
        pdf = tmp_path / "paper.pdf"
        pdf.write_bytes(b"%PDF-1.4 fake")
        paper = Paper(id="1", cite_key="t1", pdf_info=PDFInfo(file_path=str(pdf)))

        result = resolve_llm_input(paper, use_pdf=True, format_paper_text=_dummy_format)
        assert result == str(pdf)

    def test_falls_back_when_pdf_missing_on_disk(self):
        paper = Paper(
            id="1", cite_key="t1", title="Test",
            pdf_info=PDFInfo(file_path="/nonexistent/paper.pdf"),
        )

        result = resolve_llm_input(paper, use_pdf=True, format_paper_text=_dummy_format)
        assert result == "TITLE: Test"

    def test_falls_back_when_no_pdf_info(self):
        paper = Paper(id="1", cite_key="t1", title="Test")

        result = resolve_llm_input(paper, use_pdf=True, format_paper_text=_dummy_format)
        assert result == "TITLE: Test"

    def test_falls_back_when_use_pdf_false(self, tmp_path):
        pdf = tmp_path / "paper.pdf"
        pdf.write_bytes(b"%PDF-1.4 fake")
        paper = Paper(
            id="1", cite_key="t1", title="Test",
            pdf_info=PDFInfo(file_path=str(pdf)),
        )

        result = resolve_llm_input(paper, use_pdf=False, format_paper_text=_dummy_format)
        assert result == "TITLE: Test"


class TestValidateUsePdf:
    def test_valid_bool(self):
        errors = []
        validate_use_pdf({"use_pdf": True}, errors)
        assert errors == []

    def test_invalid_string(self):
        errors = []
        validate_use_pdf({"use_pdf": "yes"}, errors)
        assert len(errors) == 1
        assert "use_pdf" in errors[0]

    def test_missing_key_is_ok(self):
        errors = []
        validate_use_pdf({}, errors)
        assert errors == []
