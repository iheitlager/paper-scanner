#!/usr/bin/env python3

"""Unit tests for paper_details module."""

import json
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest

from paper_scanner.tools.paper_details import PaperDetailsExtractor


@pytest.fixture
def mock_api_key():
    """Provide a mock API key for testing."""
    return "test-api-key"


@pytest.fixture
def sample_record():
    """Provide a sample paper analysis record."""
    return {
        "file_path": "/path/to/paper.pdf",
    }


@pytest.fixture
def sample_pdf_text():
    """Provide sample PDF text content."""
    return """
    Title: Machine Learning for Healthcare Analytics
    Authors: John Smith, Jane Doe, Bob Johnson
    Year: 2023
    Journal: Journal of Medical Informatics
    Volume: 45
    Issue: 3
    Pages: 234-256
    DOI: 10.1234/jmi.2023.45.3

    Abstract: This paper explores machine learning applications in healthcare...
    """


@pytest.fixture
def sample_details_response():
    """Provide a sample Claude response for bibliographic details."""
    return {
        "citekey": "SmithDoe2023",
        "doi": "10.1234/jmi.2023.45.3",
        "citation_apa": "Smith, J., Doe, J., & Johnson, B. (2023). Machine learning for healthcare analytics. Journal of Medical Informatics, 45(3), 234-256. https://doi.org/10.1234/jmi.2023.45.3",
        "authors": ["John Smith", "Jane Doe", "Bob Johnson"],
        "year": "2023",
        "title": "Machine Learning for Healthcare Analytics",
        "journal": "Journal of Medical Informatics",
        "volume": "45",
        "issue": "3",
        "pages": "234-256",
        "publisher": None
    }


class TestPaperDetailsExtractor:
    """Tests for PaperDetailsExtractor class."""

    def test_initialization(self, mock_api_key):
        """Test extractor initialization."""
        extractor = PaperDetailsExtractor(api_key=mock_api_key, verbose=False)
        assert extractor.client is not None
        assert extractor.verbose is False
        assert extractor.model == "claude-sonnet-4-20250514"

    def test_initialization_with_custom_model(self, mock_api_key):
        """Test initialization with custom model."""
        extractor = PaperDetailsExtractor(api_key=mock_api_key, model="claude-opus")
        assert extractor.model == "claude-opus"

    def test_log_message_when_verbose(self, mock_api_key, capsys):
        """Test logging when verbose mode is enabled."""
        extractor = PaperDetailsExtractor(api_key=mock_api_key, verbose=True)
        extractor.log("Test message")
        captured = capsys.readouterr()
        assert "Test message" in captured.err

    def test_log_message_when_not_verbose(self, mock_api_key, capsys):
        """Test no logging when verbose mode is disabled."""
        extractor = PaperDetailsExtractor(api_key=mock_api_key, verbose=False)
        extractor.log("Test message")
        captured = capsys.readouterr()
        assert captured.err == ""

    def test_extract_text_from_pdf_success(self, mock_api_key, tmp_path):
        """Test successful PDF text extraction."""
        from pypdf import PdfWriter

        # Create a simple PDF file
        pdf_path = tmp_path / "test.pdf"
        writer = PdfWriter()
        writer.add_blank_page(width=200, height=200)
        with open(pdf_path, "wb") as f:
            writer.write(f)

        extractor = PaperDetailsExtractor(api_key=mock_api_key)
        text = extractor.extract_text_from_pdf(str(pdf_path))

        assert text is not None
        assert isinstance(text, str)

    def test_extract_text_from_pdf_missing_file(self, mock_api_key, capsys):
        """Test handling of missing PDF file."""
        extractor = PaperDetailsExtractor(api_key=mock_api_key, verbose=False)
        text = extractor.extract_text_from_pdf("/nonexistent/path/paper.pdf")

        assert text is None
        captured = capsys.readouterr()
        assert "Error extracting text" in captured.err

    @patch("paper_scanner.tools.paper_details.Anthropic")
    def test_extract_details_success(self, mock_anthropic_class, mock_api_key, sample_pdf_text, sample_details_response):
        """Test successful extraction of bibliographic details."""
        # Setup mock
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=json.dumps(sample_details_response))]
        mock_client.messages.create.return_value = mock_response

        # Test
        extractor = PaperDetailsExtractor(api_key=mock_api_key)
        result = extractor.extract_details_with_claude(sample_pdf_text)

        # Verify
        assert result is not None
        assert result["citekey"] == "SmithDoe2023"
        assert result["doi"] == "10.1234/jmi.2023.45.3"
        assert len(result["authors"]) == 3
        assert result["year"] == "2023"

    @patch("paper_scanner.tools.paper_details.Anthropic")
    def test_extract_details_invalid_json_response(self, mock_anthropic_class, mock_api_key, sample_pdf_text):
        """Test handling of invalid JSON response from Claude."""
        # Setup mock to return invalid JSON
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Invalid JSON {not valid")]
        mock_client.messages.create.return_value = mock_response

        # Test
        extractor = PaperDetailsExtractor(api_key=mock_api_key, verbose=False)
        result = extractor.extract_details_with_claude(sample_pdf_text)

        # Verify
        assert result is None

    @patch("paper_scanner.tools.paper_details.Anthropic")
    def test_extract_details_markdown_wrapped_json(self, mock_anthropic_class, mock_api_key, sample_pdf_text, sample_details_response):
        """Test handling of JSON wrapped in markdown code blocks."""
        # Setup mock to return JSON wrapped in markdown code blocks
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client
        json_str = json.dumps(sample_details_response)
        markdown_wrapped = f"```json\n{json_str}\n```"
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=markdown_wrapped)]
        mock_client.messages.create.return_value = mock_response

        # Test
        extractor = PaperDetailsExtractor(api_key=mock_api_key, verbose=False)
        result = extractor.extract_details_with_claude(sample_pdf_text)

        # Verify
        assert result is not None
        assert result["citekey"] == "SmithDoe2023"
        assert result["doi"] == "10.1234/jmi.2023.45.3"

    @patch("paper_scanner.tools.paper_details.Anthropic")
    def test_extract_details_rate_limit_retry(self, mock_anthropic_class, mock_api_key, sample_pdf_text, sample_details_response):
        """Test retry logic on rate limit errors."""
        # Setup mock to fail once then succeed
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client

        # First call raises rate limit error, second succeeds
        rate_limit_error = Exception()
        rate_limit_error.status_code = 429

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=json.dumps(sample_details_response))]
        mock_client.messages.create.side_effect = [rate_limit_error, mock_response]

        # Test (with patched sleep to avoid actual delay)
        with patch("paper_scanner.tools.paper_details.time.sleep"):
            extractor = PaperDetailsExtractor(api_key=mock_api_key)
            result = extractor.extract_details_with_claude(sample_pdf_text)

        # Verify
        assert result is not None
        assert result["citekey"] == "SmithDoe2023"

    @patch("paper_scanner.tools.paper_details.Anthropic")
    def test_process_records_single_record(self, mock_anthropic_class, mock_api_key, sample_record, sample_details_response, tmp_path):
        """Test processing a single record with PDF extraction."""
        # Create a simple PDF file
        from pypdf import PdfWriter

        pdf_path = tmp_path / "test.pdf"
        writer = PdfWriter()
        writer.add_blank_page(width=200, height=200)
        with open(pdf_path, "wb") as f:
            writer.write(f)

        # Setup mock for Claude
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=json.dumps(sample_details_response))]
        mock_client.messages.create.return_value = mock_response

        # Create input/output streams
        record = {"file_path": str(pdf_path)}
        input_stream = StringIO(json.dumps(record) + "\n")
        output_stream = StringIO()

        # Test
        extractor = PaperDetailsExtractor(api_key=mock_api_key)
        results = extractor.process_records(input_stream, output_stream)

        # Verify
        assert len(results) == 1
        assert "title-details" in results[0]
        assert results[0]["title-details"]["citekey"] == "SmithDoe2023"
        assert "details-timing" in results[0]["title-details"]

        # Verify output
        output_stream.seek(0)
        output_line = output_stream.readline()
        output_record = json.loads(output_line)
        assert "title-details" in output_record
        assert "details-timing" in output_record["title-details"]

    @patch("paper_scanner.tools.paper_details.Anthropic")
    def test_process_records_multiple_records(self, mock_anthropic_class, mock_api_key, sample_details_response, tmp_path):
        """Test processing multiple records with PDF extraction."""
        from pypdf import PdfWriter

        # Create PDF files
        pdf_paths = []
        for i in range(2):
            pdf_path = tmp_path / f"test{i}.pdf"
            writer = PdfWriter()
            writer.add_blank_page(width=200, height=200)
            with open(pdf_path, "wb") as f:
                writer.write(f)
            pdf_paths.append(str(pdf_path))

        # Setup mock for Claude
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=json.dumps(sample_details_response))]
        mock_client.messages.create.return_value = mock_response

        # Create multiple records
        records = [
            {"file_path": pdf_paths[0]},
            {"file_path": pdf_paths[1]},
        ]
        input_stream = StringIO("\n".join(json.dumps(r) for r in records) + "\n")
        output_stream = StringIO()

        # Test
        extractor = PaperDetailsExtractor(api_key=mock_api_key)
        results = extractor.process_records(input_stream, output_stream)

        # Verify
        assert len(results) == 2
        for result in results:
            assert "title-details" in result

    @patch("paper_scanner.tools.paper_details.Anthropic")
    def test_process_records_invalid_json_skipped(self, mock_anthropic_class, mock_api_key, sample_details_response):
        """Test that invalid JSON records are skipped."""
        # Setup mock
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=json.dumps(sample_details_response))]
        mock_client.messages.create.return_value = mock_response

        # Create input with one invalid and one valid record (but valid needs file path)
        input_stream = StringIO("Invalid JSON\n")
        output_stream = StringIO()

        # Test
        extractor = PaperDetailsExtractor(api_key=mock_api_key)
        results = extractor.process_records(input_stream, output_stream)

        # Verify only valid records processed (none in this case)
        assert len(results) == 0

    @patch("paper_scanner.tools.paper_details.Anthropic")
    def test_process_records_missing_file_path(self, mock_anthropic_class, mock_api_key):
        """Test that records without file_path are skipped."""
        # Setup mock
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client

        # Create input with record missing file_path
        record = {"some_other_field": "value"}
        input_stream = StringIO(json.dumps(record) + "\n")
        output_stream = StringIO()

        # Test
        extractor = PaperDetailsExtractor(api_key=mock_api_key)
        results = extractor.process_records(input_stream, output_stream)

        # Verify no results
        assert len(results) == 0

    @patch("paper_scanner.tools.paper_details.Anthropic")
    def test_process_records_no_metadata(self, mock_anthropic_class, mock_api_key, sample_details_response, tmp_path):
        """Test processing with metadata disabled."""
        from pypdf import PdfWriter

        # Create a simple PDF file
        pdf_path = tmp_path / "test.pdf"
        writer = PdfWriter()
        writer.add_blank_page(width=200, height=200)
        with open(pdf_path, "wb") as f:
            writer.write(f)

        # Setup mock
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=json.dumps(sample_details_response))]
        mock_client.messages.create.return_value = mock_response

        # Create input/output streams
        record = {"file_path": str(pdf_path)}
        input_stream = StringIO(json.dumps(record) + "\n")
        output_stream = StringIO()

        # Test with metadata disabled
        extractor = PaperDetailsExtractor(api_key=mock_api_key)
        results = extractor.process_records(input_stream, output_stream, include_metadata=False)

        # Verify metadata not included
        assert "details-timing" not in results[0]["title-details"]

        # Verify output
        output_stream.seek(0)
        output_line = output_stream.readline()
        output_record = json.loads(output_line)
        assert "details-timing" not in output_record["title-details"]
