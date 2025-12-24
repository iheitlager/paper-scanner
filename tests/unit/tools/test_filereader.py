"""
Tests for FileReader and DOIExtractor.

Verifies DOI extraction functionality, including:
- Basic DOI extraction patterns
- Trailing punctuation cleanup (dots, commas, semicolons, parentheses)
- Trailing bracket cleanup (regression test for issue fix)
- Various DOI format variations
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from typing import Optional

from paper_scanner.tools.documents.filereader import DOIExtractor


class TestDOIExtractorBasic:
    """Test basic DOI extraction patterns."""

    def setup_method(self):
        """Set up test fixtures."""
        self.extractor = DOIExtractor()

    def test_extract_doi_basic_format(self):
        """Test extraction of basic DOI format: 10.xxxx/yyyy."""
        text = "This paper has DOI 10.1080/10864415.2024.2332047 in the header."
        doi = self.extractor._extract_doi_from_text(text)
        assert doi == "10.1080/10864415.2024.2332047"

    def test_extract_doi_with_prefix(self):
        """Test extraction with 'DOI:' prefix."""
        text = "DOI: 10.1016/j.jsis.2024.101835"
        doi = self.extractor._extract_doi_from_text(text)
        assert doi == "10.1016/j.jsis.2024.101835"

    def test_extract_doi_with_url_prefix(self):
        """Test extraction with full DOI URL."""
        text = "Available at https://doi.org/10.1108/scm-09-2024-0617"
        doi = self.extractor._extract_doi_from_text(text)
        assert doi == "10.1108/scm-09-2024-0617"

    def test_extract_doi_with_dx_prefix(self):
        """Test extraction with dx.doi.org URL."""
        text = "Reference: http://dx.doi.org/10.1177/0008125620934864"
        doi = self.extractor._extract_doi_from_text(text)
        assert doi == "10.1177/0008125620934864"

    def test_extract_doi_case_insensitive(self):
        """Test that DOI extraction is case-insensitive."""
        text = "doi: 10.1109/tem.2021.3075502"
        doi = self.extractor._extract_doi_from_text(text)
        assert doi == "10.1109/tem.2021.3075502"

    def test_extract_doi_returns_lowercase(self):
        """Test that extracted DOI is returned in lowercase."""
        text = "DOI: 10.1002/SEJ.1499"
        doi = self.extractor._extract_doi_from_text(text)
        assert doi == "10.1002/sej.1499"


class TestDOIExtractorTrailingCleanup:
    """Test trailing character cleanup (regression tests)."""

    def setup_method(self):
        """Set up test fixtures."""
        self.extractor = DOIExtractor()

    def test_extract_doi_trailing_comma(self):
        """Test removal of trailing comma."""
        text = "See DOI: 10.1080/10864415.2024.2332047, for details"
        doi = self.extractor._extract_doi_from_text(text)
        assert doi == "10.1080/10864415.2024.2332047"

    def test_extract_doi_trailing_period(self):
        """Test removal of trailing period."""
        text = "Published at https://doi.org/10.1016/j.jsis.2024.101835."
        doi = self.extractor._extract_doi_from_text(text)
        assert doi == "10.1016/j.jsis.2024.101835"

    def test_extract_doi_trailing_semicolon(self):
        """Test removal of trailing semicolon."""
        text = "DOI: 10.1108/scm-09-2024-0617; published online"
        doi = self.extractor._extract_doi_from_text(text)
        assert doi == "10.1108/scm-09-2024-0617"

    def test_extract_doi_trailing_parenthesis(self):
        """Test removal of trailing closing parenthesis."""
        text = "Reference (10.1177/0008125620934864) in citations"
        doi = self.extractor._extract_doi_from_text(text)
        assert doi == "10.1177/0008125620934864"

    def test_extract_doi_trailing_bracket(self):
        """Test removal of trailing bracket (REGRESSION TEST for bracket fix)."""
        # This was the bug - FileReader was including trailing ]
        text = "Citation: [10.1108/scm-09-2024-0617]"
        doi = self.extractor._extract_doi_from_text(text)
        assert doi == "10.1108/scm-09-2024-0617"
        # Ensure no bracket in result
        assert "]" not in doi

    def test_extract_doi_trailing_bracket_regression_case_1(self):
        """Regression test: PDF 10-1108_scm-09-2024-0617-2.pdf"""
        # This PDF was extracted as 10.1108/scm-09-2024-0617] before fix
        text = "DOI identifier: 10.1108/scm-09-2024-0617]"
        doi = self.extractor._extract_doi_from_text(text)
        assert doi == "10.1108/scm-09-2024-0617"
        assert "]" not in doi

    def test_extract_doi_trailing_bracket_regression_case_2(self):
        """Regression test: PDF 5cdc85f6-d725-e989-0218-6d2f514d472a.pdf"""
        # This PDF was extracted as 10.1108/jbim-10-2021-0474] before fix
        text = "Reference [10.1108/jbim-10-2021-0474]"
        doi = self.extractor._extract_doi_from_text(text)
        assert doi == "10.1108/jbim-10-2021-0474"
        assert "]" not in doi

    def test_extract_doi_multiple_trailing_chars(self):
        """Test removal of multiple trailing characters."""
        text = "See: https://doi.org/10.1186/s13731-024-00404-5,."
        doi = self.extractor._extract_doi_from_text(text)
        assert doi == "10.1186/s13731-024-00404-5"

    def test_extract_doi_trailing_whitespace(self):
        """Test removal of trailing whitespace."""
        text = "DOI: 10.1080/13662716.2023.2189091   "
        doi = self.extractor._extract_doi_from_text(text)
        assert doi == "10.1080/13662716.2023.2189091"


class TestDOIExtractorValidation:
    """Test DOI validation logic."""

    def setup_method(self):
        """Set up test fixtures."""
        self.extractor = DOIExtractor()

    def test_invalid_doi_missing_slash(self):
        """Test that DOI without slash is rejected."""
        text = "Invalid DOI: 10.1080"
        doi = self.extractor._extract_doi_from_text(text)
        assert doi is None

    def test_invalid_doi_missing_10_prefix(self):
        """Test that number without 10. prefix is rejected."""
        text = "Not a DOI: 1080/10864415.2024.2332047"
        doi = self.extractor._extract_doi_from_text(text)
        assert doi is None

    def test_extract_doi_from_multiline_text(self):
        """Test extraction from multiline text."""
        text = """
        Title: Research Paper
        Abstract: This paper discusses...
        DOI: 10.1109/tem.2021.3075502
        Published: 2021
        """
        doi = self.extractor._extract_doi_from_text(text)
        assert doi == "10.1109/tem.2021.3075502"

    def test_extract_doi_first_match_only(self):
        """Test that only first DOI is extracted."""
        text = "Paper A: 10.1109/tem.2021.3075502 and Paper B: 10.1002/sej.1499"
        doi = self.extractor._extract_doi_from_text(text)
        assert doi == "10.1109/tem.2021.3075502"

    def test_extract_doi_from_empty_text(self):
        """Test extraction from empty text returns None."""
        text = ""
        doi = self.extractor._extract_doi_from_text(text)
        assert doi is None

    def test_extract_doi_from_text_without_doi(self):
        """Test extraction from text without DOI returns None."""
        text = "This is just plain text without any DOI identifier."
        doi = self.extractor._extract_doi_from_text(text)
        assert doi is None


class TestDOIExtractorComplexPatterns:
    """Test complex DOI patterns and edge cases."""

    def setup_method(self):
        """Set up test fixtures."""
        self.extractor = DOIExtractor()

    def test_extract_doi_with_nested_parentheses(self):
        """Test DOI with nested parentheses in text."""
        text = "See reference (Smith et al. (2023) 10.1080/10864415.2024.2332047)"
        doi = self.extractor._extract_doi_from_text(text)
        assert doi == "10.1080/10864415.2024.2332047"

    def test_extract_doi_with_hyphenated_suffix(self):
        """Test DOI with hyphens in suffix."""
        text = "DOI: 10.1108/scm-09-2024-0617"
        doi = self.extractor._extract_doi_from_text(text)
        assert doi == "10.1108/scm-09-2024-0617"

    def test_extract_doi_doi_org_url_variations(self):
        """Test various doi.org URL formats."""
        test_cases = [
            ("https://doi.org/10.1016/j.jsis.2024.101835", "10.1016/j.jsis.2024.101835"),
            ("http://doi.org/10.1016/j.jsis.2024.101835", "10.1016/j.jsis.2024.101835"),
            ("doi.org/10.1016/j.jsis.2024.101835", "10.1016/j.jsis.2024.101835"),
        ]
        for text, expected in test_cases:
            doi = self.extractor._extract_doi_from_text(text)
            assert doi == expected, f"Failed for: {text}"

    def test_extract_doi_with_version_number(self):
        """Test DOI with version numbers."""
        text = "DOI: 10.1186/s13731-024-00404-5"
        doi = self.extractor._extract_doi_from_text(text)
        assert doi == "10.1186/s13731-024-00404-5"

    def test_extract_doi_very_long_suffix(self):
        """Test DOI with long suffix."""
        text = "Reference: 10.1109/tem.2021.3075502.very.long.suffix"
        doi = self.extractor._extract_doi_from_text(text)
        # Should extract the whole thing
        assert doi.startswith("10.1109/tem.2021.3075502")

    def test_extract_doi_mixed_case_in_text(self):
        """Test extraction when DOI appears in mixed case context."""
        text = "Publication uses DOI: 10.1080/ABCD1234.5678.XXXX"
        doi = self.extractor._extract_doi_from_text(text)
        assert doi is not None
        assert doi.islower()


class TestDOIExtractorFromPDFStub:
    """Test DOI extraction from PDF files using mocks."""

    def setup_method(self):
        """Set up test fixtures."""
        self.extractor = DOIExtractor()

    @patch('paper_scanner.tools.documents.filereader.HAS_PDFPLUMBER', True)
    @patch('pdfplumber.open')
    def test_extract_from_content_using_pdfplumber(self, mock_pdfplumber_open):
        """Test DOI extraction from PDF content using pdfplumber."""
        # Mock PDF structure
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "This paper uses DOI: 10.1080/10864415.2024.2332047"
        
        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdf.__enter__ = Mock(return_value=mock_pdf)
        mock_pdf.__exit__ = Mock(return_value=False)
        
        mock_pdfplumber_open.return_value = mock_pdf
        
        # Test extraction
        test_path = Path("stub.pdf")
        doi = self.extractor._extract_from_content(test_path)
        
        assert doi == "10.1080/10864415.2024.2332047"

    def test_extract_doi_text_extraction_with_pdf_content(self):
        """Test that extracted text is properly cleaned."""
        # Simulate text from PDF with DOI
        pdf_text = """
        International Journal of Research
        DOI: 10.1016/j.jsis.2024.101835
        Published 2024
        """
        doi = self.extractor._extract_doi_from_text(pdf_text)
        assert doi == "10.1016/j.jsis.2024.101835"

    def test_extract_doi_from_multiline_pdf_stub(self):
        """Test DOI extraction from realistic multiline text."""
        # Simulate realistic PDF text
        pdf_text = """
        Title: Advanced Systems Integration
        Authors: Smith, J. et al.
        Volume: 45, Issue: 3
        DOI: 10.1109/tem.2021.3075502
        Pages: 234-256
        """
        doi = self.extractor._extract_doi_from_text(pdf_text)
        assert doi == "10.1109/tem.2021.3075502"

    def test_extract_doi_with_metadata_format(self):
        """Test extraction from metadata-like format."""
        metadata_text = '10.1108/scm-09-2024-0617'
        doi = self.extractor._extract_doi_from_text(metadata_text)
        assert doi == "10.1108/scm-09-2024-0617"

    @patch('paper_scanner.tools.documents.filereader.HAS_PYPDF', False)
    @patch('paper_scanner.tools.documents.filereader.HAS_PDFPLUMBER', False)
    def test_extract_from_content_no_pdf_libraries(self):
        """Test extraction when no PDF libraries available."""
        test_path = Path("stub.pdf")
        doi = self.extractor._extract_from_content(test_path)
        assert doi is None

    def test_extract_doi_returns_none_for_invalid_pdf_path(self):
        """Test extraction from non-existent PDF path."""
        test_path = Path("/nonexistent/stub.pdf")
        # Should return None without raising exception
        try:
            doi = self.extractor.extract_from_pdf(test_path)
            assert doi is None
        except FileNotFoundError:
            # This is acceptable - file doesn't exist
            pass
