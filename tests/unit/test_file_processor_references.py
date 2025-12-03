"""
Tests for file_processor reference extraction functionality.

Tests cover:
- Reference extraction with Claude API
- Error handling and retries for rate limits
- Reference prompt loading from file
- Integration with JSONLines processing
"""

import json
import os
import tempfile
from io import StringIO
from unittest.mock import MagicMock, Mock, patch

import pytest

from paper_scanner.tools.file_processor import PDFClaudeScanner, DEFAULT_MODEL


@pytest.fixture
def mock_api_key():
    """Mock API key for testing."""
    return "sk-test-key-12345"


@pytest.fixture
def sample_pdf_text():
    """Sample PDF text for testing."""
    return """
    This is a sample academic paper.
    
    References:
    1. Smith, J. (2023). A study on innovation. Journal of Technology, 45(3), 123-145.
    2. Doe, A., & Jones, B. (2022). Digital transformation. IT Management Review, 12(1), 34-56.
    """


@pytest.fixture
def sample_references_response():
    """Sample reference extraction response from Claude."""
    return {
        "total_references": 2,
        "extraction_date": "2025-12-02T10:00:00Z",
        "source_paper": {
            "citekey": "AuthorA2025",
            "title": "Sample Paper",
            "authors": ["Author, A"],
            "year": "2025"
        },
        "references": [
            {
                "id": 1,
                "citekey": "SmithJ2023",
                "reference_type": "journal_article",
                "authors": [
                    {"last_name": "Smith", "first_name": "John", "initials": "J", "order": 1}
                ],
                "year": "2023",
                "title": "A study on innovation",
                "source": {
                    "type": "journal",
                    "name": "Journal of Technology",
                    "volume": "45",
                    "issue": "3",
                    "pages": {"start": "123", "end": "145", "range": "123-145"}
                },
                "identifiers": {
                    "doi": "10.1234/jtech.2023.45.3",
                    "url": None,
                    "arxiv": None,
                    "ssrn": None
                },
                "raw_citation": "Smith, J. (2023). A study on innovation. Journal of Technology, 45(3), 123-145.",
                "notes": None
            },
            {
                "id": 2,
                "citekey": "DoeA2022",
                "reference_type": "journal_article",
                "authors": [
                    {"last_name": "Doe", "first_name": "Alice", "initials": "A", "order": 1},
                    {"last_name": "Jones", "first_name": "Bob", "initials": "B", "order": 2}
                ],
                "year": "2022",
                "title": "Digital transformation",
                "source": {
                    "type": "journal",
                    "name": "IT Management Review",
                    "volume": "12",
                    "issue": "1",
                    "pages": {"start": "34", "end": "56", "range": "34-56"}
                },
                "identifiers": {
                    "doi": None,
                    "url": "https://example.com/article",
                    "arxiv": None,
                    "ssrn": None
                },
                "raw_citation": "Doe, A., & Jones, B. (2022). Digital transformation. IT Management Review, 12(1), 34-56.",
                "notes": None
            }
        ],
        "parsing_metadata": {
            "successfully_parsed": 2,
            "parsing_issues": [],
            "citation_style": "APA"
        }
    }


class TestPDFClaudeScanner:
    """Test PDFClaudeScanner class."""

    def test_init_loads_reference_prompt(self, mock_api_key):
        """Test that __init__ loads reference extraction prompt."""
        scanner = PDFClaudeScanner(api_key=mock_api_key)
        assert scanner.client is not None
        assert scanner.verbose is False
        assert scanner.model == DEFAULT_MODEL
        # Reference prompt should be loaded (may be empty if file not found)
        assert hasattr(scanner, 'reference_prompt')

    def test_load_reference_prompt_file_exists(self, mock_api_key, tmp_path):
        """Test loading reference prompt from file."""
        # Create a temporary prompt file
        prompts_dir = tmp_path / "prompts"
        prompts_dir.mkdir()
        prompt_file = prompts_dir / "extract-references.md"
        prompt_content = "# Reference Extraction\nExtract references..."
        prompt_file.write_text(prompt_content)

        with patch('os.path.dirname') as mock_dirname:
            with patch('os.path.abspath') as mock_abspath:
                mock_dirname.return_value = str(tmp_path / "tools")
                mock_abspath.return_value = str(tmp_path / "tools" / "file_processor.py")

                # Patch the path construction
                with patch('os.path.join', side_effect=lambda *args: str(prompt_file)):
                    with patch('os.path.exists', return_value=True):
                        with patch('builtins.open', create=True) as mock_open:
                            mock_open.return_value.__enter__.return_value.read.return_value = prompt_content
                            scanner = PDFClaudeScanner(api_key=mock_api_key)
                            # Verify prompt was loaded
                            assert scanner.reference_prompt == prompt_content

    @patch("paper_scanner.tools.file_processor.Anthropic")
    def test_extract_references_with_claude_success(
        self, mock_anthropic_class, mock_api_key, sample_pdf_text, sample_references_response
    ):
        """Test successful reference extraction."""
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=json.dumps(sample_references_response))]
        mock_client.messages.create.return_value = mock_response

        scanner = PDFClaudeScanner(api_key=mock_api_key)
        scanner.reference_prompt = "# Extract references"
        result = scanner.extract_references_with_claude(sample_pdf_text)

        assert result is not None
        assert result["total_references"] == 2
        assert len(result["references"]) == 2
        assert result["references"][0]["citekey"] == "SmithJ2023"
        assert result["references"][1]["citekey"] == "DoeA2022"

    @patch("paper_scanner.tools.file_processor.Anthropic")
    def test_extract_references_empty_prompt(self, mock_anthropic_class, mock_api_key, sample_pdf_text):
        """Test reference extraction with empty prompt returns None."""
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client

        scanner = PDFClaudeScanner(api_key=mock_api_key)
        scanner.reference_prompt = ""
        result = scanner.extract_references_with_claude(sample_pdf_text)

        assert result is None

    @patch("paper_scanner.tools.file_processor.Anthropic")
    def test_extract_references_rate_limit_retry(
        self, mock_anthropic_class, mock_api_key, sample_pdf_text, sample_references_response
    ):
        """Test reference extraction with rate limit retry."""
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client

        # First call raises 429 (rate limit)
        rate_limit_error = Exception("Rate limit exceeded")
        rate_limit_error.status_code = 429

        # Second call succeeds
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=json.dumps(sample_references_response))]

        mock_client.messages.create.side_effect = [rate_limit_error, mock_response]

        with patch("paper_scanner.tools.file_processor.time.sleep"):
            scanner = PDFClaudeScanner(api_key=mock_api_key)
            scanner.reference_prompt = "# Extract references"
            result = scanner.extract_references_with_claude(sample_pdf_text, max_retries=2)

            assert result is not None
            assert result["total_references"] == 2

    @patch("paper_scanner.tools.file_processor.Anthropic")
    def test_extract_references_json_parse_error(
        self, mock_anthropic_class, mock_api_key, sample_pdf_text
    ):
        """Test reference extraction with invalid JSON response."""
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Invalid JSON {{{")]
        mock_client.messages.create.return_value = mock_response

        scanner = PDFClaudeScanner(api_key=mock_api_key)
        scanner.reference_prompt = "# Extract references"
        result = scanner.extract_references_with_claude(sample_pdf_text)

        assert result is None

    def test_process_pdfs_with_references_extraction(self, mock_api_key, sample_pdf_text):
        """Test process_pdfs with reference extraction enabled."""
        # Create sample input JSONL
        input_data = {
            "file_path": "/tmp/test.pdf",
            "file_name": "test.pdf",
            "directory": "/tmp"
        }
        input_lines = json.dumps(input_data)
        input_file = StringIO(input_lines + "\n")

        # Create output file
        output_file = StringIO()

        with patch("paper_scanner.tools.file_processor.Anthropic"):
            with patch.object(PDFClaudeScanner, "extract_text_from_pdf", return_value=sample_pdf_text):
                with patch.object(PDFClaudeScanner, "analyze_with_claude", return_value={"summary": "Test"}):
                    with patch.object(PDFClaudeScanner, "extract_references_with_claude", return_value={"references": []}):
                        scanner = PDFClaudeScanner(api_key=mock_api_key)
                        scanner.reference_prompt = "# Extract references"
                        results = scanner.process_pdfs(
                            input_file,
                            output_file,
                            extract_references=True,
                            include_metadata=False
                        )

                        assert len(results) == 1
                        assert "analysis" in results[0]
                        assert "references" in results[0]

    def test_process_pdfs_without_references_extraction(self, mock_api_key, sample_pdf_text):
        """Test process_pdfs with reference extraction disabled (default)."""
        input_data = {
            "file_path": "/tmp/test.pdf",
            "file_name": "test.pdf",
            "directory": "/tmp"
        }
        input_lines = json.dumps(input_data)
        input_file = StringIO(input_lines + "\n")
        output_file = StringIO()

        with patch("paper_scanner.tools.file_processor.Anthropic"):
            with patch.object(PDFClaudeScanner, "extract_text_from_pdf", return_value=sample_pdf_text):
                with patch.object(PDFClaudeScanner, "analyze_with_claude", return_value={"summary": "Test"}):
                    scanner = PDFClaudeScanner(api_key=mock_api_key)
                    results = scanner.process_pdfs(
                        input_file,
                        output_file,
                        extract_references=False,
                        include_metadata=False
                    )

                    assert len(results) == 1
                    assert "analysis" in results[0]
                    assert "references" not in results[0]

    def test_process_pdfs_reference_extraction_failure_continues(self, mock_api_key, sample_pdf_text):
        """Test that reference extraction failure doesn't fail paper processing."""
        input_data = {
            "file_path": "/tmp/test.pdf",
            "file_name": "test.pdf",
            "directory": "/tmp"
        }
        input_lines = json.dumps(input_data)
        input_file = StringIO(input_lines + "\n")
        output_file = StringIO()

        with patch("paper_scanner.tools.file_processor.Anthropic"):
            with patch.object(PDFClaudeScanner, "extract_text_from_pdf", return_value=sample_pdf_text):
                with patch.object(PDFClaudeScanner, "analyze_with_claude", return_value={"summary": "Test"}):
                    with patch.object(PDFClaudeScanner, "extract_references_with_claude", return_value=None):
                        scanner = PDFClaudeScanner(api_key=mock_api_key)
                        scanner.reference_prompt = "# Extract references"
                        results = scanner.process_pdfs(
                            input_file,
                            output_file,
                            extract_references=True,
                            include_metadata=False
                        )

                        # Should still process the paper even if references fail
                        assert len(results) == 1
                        assert "analysis" in results[0]
                        assert "references" not in results[0]
