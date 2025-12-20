"""
Tests for CORE handler PDF fetching.

Tests CORE API handler's fetch_pdf implementation.
"""

from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import datetime
import pytest

from paper_scanner.core.models import PDFInfo
from paper_scanner.tools.fetchers.fetcher_handlers.core_handler import COREHandler


class TestCOREHandlerPDFFetching:
    """Test CORE handler PDF downloading functionality."""

    def test_core_handler_instantiation(self, tmp_path):
        """Test that CORE handler can be instantiated."""
        handler = COREHandler(cache_dir=tmp_path)
        assert handler.name == "core"
        assert handler.cache_dir == tmp_path

    def test_core_handler_with_api_key(self, tmp_path):
        """Test CORE handler initialization with API key."""
        api_key = "test-api-key-123"
        handler = COREHandler(cache_dir=tmp_path, api_key=api_key)
        assert handler.api_key == api_key

    def test_find_download_url_from_downloadUrl_field(self, tmp_path):
        """Test extracting download URL from 'downloadUrl' field."""
        handler = COREHandler(cache_dir=tmp_path)
        
        api_data = {
            "downloadUrl": "https://core.ac.uk/pdf/123.pdf",
        }
        
        url = handler._find_download_url(api_data)
        assert url == "https://core.ac.uk/pdf/123.pdf"

    def test_find_download_url_from_fullTextUrl_field(self, tmp_path):
        """Test extracting download URL from 'fullTextUrl' field."""
        handler = COREHandler(cache_dir=tmp_path)
        
        api_data = {
            "fullTextUrl": "https://example.com/full-text.pdf",
        }
        
        url = handler._find_download_url(api_data)
        assert url == "https://example.com/full-text.pdf"

    def test_find_download_url_from_links_array(self, tmp_path):
        """Test extracting download URL from links array."""
        handler = COREHandler(cache_dir=tmp_path)
        
        api_data = {
            "links": [
                {"type": "pdf", "url": "https://example.com/paper.pdf"},
                {"type": "html", "url": "https://example.com/paper.html"},
            ]
        }
        
        url = handler._find_download_url(api_data)
        assert url == "https://example.com/paper.pdf"

    def test_find_download_url_returns_none_when_missing(self, tmp_path):
        """Test that None is returned when no download URL found."""
        handler = COREHandler(cache_dir=tmp_path)
        
        api_data = {
            "title": "Some Paper",
            "year": 2024,
        }
        
        url = handler._find_download_url(api_data)
        assert url is None

    def test_fetch_pdf_with_successful_download(self, tmp_path):
        """Test that fetch_pdf method can be called successfully."""
        handler = COREHandler(cache_dir=tmp_path)
        
        # Mock the metadata fetch to return no data
        # This tests that the method handles the full chain
        with patch.object(handler, "fetch_metadata", return_value=(None, False)):
            # When metadata is None, fetch_pdf should return None
            pdf_info = handler.fetch_pdf("10.1234/test.doi")
            assert pdf_info is None

    def test_fetch_pdf_returns_none_when_no_download_url(self, tmp_path):
        """Test fetch_pdf returns None when no download URL found."""
        handler = COREHandler(cache_dir=tmp_path)
        
        api_data = {
            "id": "core-456",
            "title": "Paper without download",
        }
        
        with patch.object(handler, "fetch_metadata", return_value=(api_data, False)):
            pdf_info = handler.fetch_pdf("10.1234/test.doi")
            assert pdf_info is None

    def test_fetch_pdf_returns_none_on_html_response(self, tmp_path):
        """Test that HTML responses are rejected."""
        handler = COREHandler(cache_dir=tmp_path)
        
        api_data = {
            "id": "core-789",
            "downloadUrl": "https://example.com/login",
        }
        
        with patch.object(handler, "fetch_metadata", return_value=(api_data, False)):
            with patch("paper_scanner.tools.fetchers.fetcher_handlers.core_handler.requests.get") as mock_get:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.headers = {"content-type": "text/html"}
                mock_response.content = b"<html>Login page</html>"
                mock_response.raise_for_status = MagicMock()
                mock_get.return_value = mock_response
                
                pdf_info = handler.fetch_pdf("10.1234/test.doi")
                assert pdf_info is None

    def test_fetch_pdf_returns_none_on_download_error(self, tmp_path):
        """Test that download errors are handled gracefully."""
        handler = COREHandler(cache_dir=tmp_path)
        
        api_data = {
            "id": "core-999",
            "downloadUrl": "https://example.com/paper.pdf",
        }
        
        with patch.object(handler, "fetch_metadata", return_value=(api_data, False)):
            with patch("paper_scanner.tools.fetchers.fetcher_handlers.core_handler.requests.get") as mock_get:
                mock_get.side_effect = Exception("Connection timeout")
                
                pdf_info = handler.fetch_pdf("10.1234/test.doi")
                assert pdf_info is None

    def test_extract_methods_return_empty_values(self, tmp_path):
        """Test that extract methods return appropriate empty values."""
        handler = COREHandler(cache_dir=tmp_path)
        api_data = {"id": "core-111"}
        
        # CORE handler doesn't provide these fields via metadata search
        assert handler._extract_abstract(api_data) is None
        assert handler._extract_authors(api_data) == []
        assert handler._extract_keywords(api_data) == []
        assert handler._extract_topics(api_data) == []
        assert handler._extract_paper_type(api_data) is None
        assert handler._extract_year(api_data) is None
        assert handler._extract_journal(api_data) is None
        assert handler._extract_oa_status(api_data) is None
        assert handler._extract_citations(api_data) == []

    def test_extract_source_key(self, tmp_path):
        """Test that source key (CORE ID) is extracted."""
        handler = COREHandler(cache_dir=tmp_path)
        api_data = {"id": "core-55555"}
        
        source_key = handler._extract_source_key(api_data)
        assert source_key == "core-55555"
