"""
Tests for PublisherHandler PDF fetching.

Tests direct publisher PDF download functionality via DOI resolution.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from paper_scanner.core.models import PDFInfo
from paper_scanner.tools.fetchers.fetcher_handlers.publisher_handler import \
    PublisherHandler


class TestPublisherHandlerInstantiation:
    """Test PublisherHandler instantiation and configuration."""

    def test_publisher_handler_instantiation(self, tmp_path):
        """Test that PublisherHandler can be instantiated."""
        handler = PublisherHandler(cache_dir=tmp_path)
        assert handler.name == "publisher"
        assert handler.cache_dir == tmp_path

    def test_publisher_handler_not_implemented_methods(self, tmp_path):
        """Test that non-PDF methods raise NotImplementedError."""
        handler = PublisherHandler(cache_dir=tmp_path)

        with pytest.raises(NotImplementedError):
            handler.fetch_paper("10.1234/test")

        with pytest.raises(NotImplementedError):
            handler.fetch_citations("10.1234/test")

        with pytest.raises(NotImplementedError):
            handler._fetch_from_api("10.1234/test")

        with pytest.raises(NotImplementedError):
            handler._find_download_url({})


class TestPublisherDetection:
    """Test publisher detection from URLs."""

    def test_detect_tandfonline_publisher(self, tmp_path):
        """Test detecting Taylor & Francis publisher."""
        handler = PublisherHandler(cache_dir=tmp_path)

        url = "https://www.tandfonline.com/doi/full/10.1080/10864415.2024.2332047"
        publisher = handler._detect_publisher(url)
        assert publisher == "tandfonline.com"

    def test_detect_springer_publisher(self, tmp_path):
        """Test detecting Springer publisher."""
        handler = PublisherHandler(cache_dir=tmp_path)

        url = "https://link.springer.com/article/10.1186/s13731-024-00404-5"
        publisher = handler._detect_publisher(url)
        assert publisher == "springer.com"

    def test_detect_wiley_publisher(self, tmp_path):
        """Test detecting Wiley publisher."""
        handler = PublisherHandler(cache_dir=tmp_path)

        url = "https://onlinelibrary.wiley.com/doi/full/10.1234/example"
        publisher = handler._detect_publisher(url)
        assert publisher == "wiley.com"

    def test_detect_unknown_publisher(self, tmp_path):
        """Test handling unknown publishers."""
        handler = PublisherHandler(cache_dir=tmp_path)

        url = "https://unknown-publisher.com/article/12345"
        publisher = handler._detect_publisher(url)
        assert publisher is None


class TestDOIResolution:
    """Test DOI to landing page resolution."""

    def test_resolve_doi_to_tandfonline(self, tmp_path):
        """Test DOI resolution to Taylor & Francis landing page."""
        handler = PublisherHandler(cache_dir=tmp_path)

        with patch("paper_scanner.tools.fetchers.fetcher_handlers.publisher_handler.requests.Session.get") as mock_get:
            mock_response = MagicMock()
            mock_response.url = "https://www.tandfonline.com/doi/full/10.1080/10864415.2024.2332047"
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            url = handler._resolve_doi_to_landing_page("10.1080/10864415.2024.2332047")
            assert url == "https://www.tandfonline.com/doi/full/10.1080/10864415.2024.2332047"

    def test_resolve_doi_to_springer(self, tmp_path):
        """Test DOI resolution to Springer landing page."""
        handler = PublisherHandler(cache_dir=tmp_path)

        with patch("paper_scanner.tools.fetchers.fetcher_handlers.publisher_handler.requests.Session.get") as mock_get:
            mock_response = MagicMock()
            mock_response.url = "https://link.springer.com/article/10.1186/s13731-024-00404-5"
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            url = handler._resolve_doi_to_landing_page("10.1186/s13731-024-00404-5")
            assert url == "https://link.springer.com/article/10.1186/s13731-024-00404-5"

    def test_resolve_doi_returns_none_on_failure(self, tmp_path):
        """Test DOI resolution returns None on failure."""
        handler = PublisherHandler(cache_dir=tmp_path)

        with patch("paper_scanner.tools.fetchers.fetcher_handlers.publisher_handler.requests.Session.get") as mock_get:
            mock_get.side_effect = Exception("Connection error")

            url = handler._resolve_doi_to_landing_page("10.1234/invalid")
            assert url is None


class TestPDFURLConstruction:
    """Test PDF URL construction from publisher templates."""

    def test_construct_tandfonline_pdf_url(self, tmp_path):
        """Test PDF URL construction for Taylor & Francis."""
        handler = PublisherHandler(cache_dir=tmp_path)

        doi = "10.1080/10864415.2024.2332047"
        url = "https://www.tandfonline.com/doi/full/10.1080/10864415.2024.2332047"
        publisher = handler._detect_publisher(url)

        pdf_url = handler._extract_pdf_url_from_landing_page(url, publisher, doi)
        expected = "https://www.tandfonline.com/doi/pdf/10.1080/10864415.2024.2332047?download=true"
        assert pdf_url == expected

    def test_construct_springer_pdf_url(self, tmp_path):
        """Test PDF URL construction for Springer."""
        handler = PublisherHandler(cache_dir=tmp_path)

        doi = "10.1186/s13731-024-00404-5"
        url = "https://link.springer.com/article/10.1186/s13731-024-00404-5"
        publisher = handler._detect_publisher(url)

        pdf_url = handler._extract_pdf_url_from_landing_page(url, publisher, doi)
        expected = "https://link.springer.com/content/pdf/10.1186/s13731-024-00404-5.pdf"
        assert pdf_url == expected


class TestPDFDownload:
    """Test actual PDF download flow."""

    def test_fetch_pdf_full_flow_tandfonline(self, tmp_path):
        """Test complete PDF fetch flow for Taylor & Francis."""
        handler = PublisherHandler(cache_dir=tmp_path)

        doi = "10.1080/10864415.2024.2332047"
        pdf_content = b"PDF content" * 100

        with patch("paper_scanner.tools.fetchers.fetcher_handlers.publisher_handler.requests.Session.get") as mock_get:
            # Mock DOI resolution
            resolution_response = MagicMock()
            resolution_response.url = "https://www.tandfonline.com/doi/full/" + doi
            resolution_response.raise_for_status = MagicMock()

            # Mock PDF download
            download_response = MagicMock()
            download_response.status_code = 200
            download_response.headers = {"content-type": "application/pdf"}
            download_response.content = pdf_content
            download_response.raise_for_status = MagicMock()

            # Return different mocks for resolution vs download
            mock_get.side_effect = [resolution_response, download_response]

            pdf_info = handler.fetch_pdf(doi)

            assert pdf_info is not None
            assert isinstance(pdf_info, PDFInfo)
            assert pdf_info.download_source == "publisher"
            assert "tandfonline" in pdf_info.download_url
            assert Path(pdf_info.file_path).exists()

    def test_fetch_pdf_returns_none_on_resolution_failure(self, tmp_path):
        """Test fetch_pdf returns None when DOI resolution fails."""
        handler = PublisherHandler(cache_dir=tmp_path)

        with patch("paper_scanner.tools.fetchers.fetcher_handlers.publisher_handler.requests.Session.get") as mock_get:
            mock_get.side_effect = Exception("Network error")

            pdf_info = handler.fetch_pdf("10.1234/invalid")
            assert pdf_info is None

    def test_fetch_pdf_returns_none_on_unknown_publisher(self, tmp_path):
        """Test fetch_pdf returns None for unknown publishers."""
        handler = PublisherHandler(cache_dir=tmp_path)

        with patch("paper_scanner.tools.fetchers.fetcher_handlers.publisher_handler.requests.Session.get") as mock_get:
            # Mock DOI resolution to unknown publisher
            resolution_response = MagicMock()
            resolution_response.url = "https://unknown-publisher.com/article/123"
            resolution_response.raise_for_status = MagicMock()
            mock_get.return_value = resolution_response

            pdf_info = handler.fetch_pdf("10.1234/unknown")
            assert pdf_info is None

    def test_fetch_pdf_returns_none_on_html_response(self, tmp_path):
        """Test fetch_pdf returns None when HTML is returned instead of PDF."""
        handler = PublisherHandler(cache_dir=tmp_path)

        with patch("paper_scanner.tools.fetchers.fetcher_handlers.publisher_handler.requests.Session.get") as mock_get:
            # Mock DOI resolution
            resolution_response = MagicMock()
            resolution_response.url = "https://www.tandfonline.com/doi/full/10.1080/test"
            resolution_response.raise_for_status = MagicMock()

            # Mock HTML response instead of PDF
            html_response = MagicMock()
            html_response.status_code = 200
            html_response.headers = {"content-type": "text/html"}
            html_response.content = b"<html>Login required</html>"
            html_response.raise_for_status = MagicMock()

            mock_get.side_effect = [resolution_response, html_response]

            pdf_info = handler.fetch_pdf("10.1080/test")
            assert pdf_info is None

    def test_fetch_pdf_returns_none_on_download_error(self, tmp_path):
        """Test fetch_pdf returns None on download errors."""
        handler = PublisherHandler(cache_dir=tmp_path)

        with patch("paper_scanner.tools.fetchers.fetcher_handlers.publisher_handler.requests.Session.get") as mock_get:
            # Mock DOI resolution
            resolution_response = MagicMock()
            resolution_response.url = "https://www.tandfonline.com/doi/full/10.1080/test"
            resolution_response.raise_for_status = MagicMock()

            # Mock download error
            download_response = MagicMock()
            download_response.raise_for_status.side_effect = Exception("Download failed")

            mock_get.side_effect = [resolution_response, download_response]

            pdf_info = handler.fetch_pdf("10.1080/test")
            assert pdf_info is None


class TestPatternBasedPublisherDetection:
    """Test DOI pattern-based publisher detection for arXiv, PLOS, MDPI."""

    def test_detect_arxiv_by_doi_pattern(self, tmp_path):
        """Test detecting arXiv by DOI pattern."""
        handler = PublisherHandler(cache_dir=tmp_path)

        arxiv_doi = "10.48550/arxiv.2302.12345"
        publisher = handler._detect_publisher("", doi=arxiv_doi)
        assert publisher == "arxiv.org"

    def test_detect_plos_by_doi_pattern(self, tmp_path):
        """Test detecting PLOS by DOI pattern."""
        handler = PublisherHandler(cache_dir=tmp_path)

        plos_doi = "10.1371/journal.pone.0123456"
        publisher = handler._detect_publisher("", doi=plos_doi)
        assert publisher == "plos.org"

    def test_detect_mdpi_by_doi_pattern(self, tmp_path):
        """Test detecting MDPI by DOI pattern."""
        handler = PublisherHandler(cache_dir=tmp_path)

        mdpi_doi = "10.3390/app10010001"
        publisher = handler._detect_publisher("", doi=mdpi_doi)
        assert publisher == "mdpi.com"

    def test_extract_arxiv_pdf_url(self, tmp_path):
        """Test constructing arXiv PDF URL from DOI."""
        handler = PublisherHandler(cache_dir=tmp_path)

        arxiv_doi = "10.48550/arxiv.2302.12345"
        pdf_url = handler._extract_pdf_url_from_landing_page("", "arxiv.org", arxiv_doi)
        
        # Should extract the arxiv ID from the DOI
        assert pdf_url is not None
        assert "https://arxiv.org/pdf/" in pdf_url
        assert "2302.12345" in pdf_url

    def test_extract_plos_pdf_url(self, tmp_path):
        """Test constructing PLOS PDF URL from DOI."""
        handler = PublisherHandler(cache_dir=tmp_path)

        plos_doi = "10.1371/journal.pone.0123456"
        pdf_url = handler._extract_pdf_url_from_landing_page("", "plos.org", plos_doi)
        
        # PLOS uses the full DOI in the URL
        assert pdf_url is not None
        assert "https://journals.plos.org/plosone/article/file?id=" in pdf_url

    def test_extract_mdpi_pdf_url(self, tmp_path):
        """Test constructing MDPI PDF URL from DOI."""
        handler = PublisherHandler(cache_dir=tmp_path)

        mdpi_doi = "10.3390/app10010001"
        pdf_url = handler._extract_pdf_url_from_landing_page("", "mdpi.com", mdpi_doi)
        
        # MDPI uses the full DOI in the URL
        assert pdf_url is not None
        assert "https://www.mdpi.com/" in pdf_url
        assert "/pdf" in pdf_url

    def test_fetch_pdf_arxiv_pattern_based_flow(self, tmp_path):
        """Test full fetch_pdf flow for arXiv using DOI pattern detection."""
        handler = PublisherHandler(cache_dir=tmp_path)

        with patch("paper_scanner.tools.fetchers.fetcher_handlers.publisher_handler.requests.Session.get") as mock_get:
            # For arXiv, no DOI resolution needed - goes straight to pattern detection
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.headers = {"content-type": "application/pdf"}
            mock_response.content = b"PDF content"
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            arxiv_doi = "10.48550/arxiv.2302.12345"
            pdf_info = handler.fetch_pdf(arxiv_doi)

            assert pdf_info is not None
            assert pdf_info.download_source == "publisher"
            assert "arxiv" in pdf_info.download_url.lower()

    def test_fetch_pdf_plos_pattern_based_flow(self, tmp_path):
        """Test full fetch_pdf flow for PLOS using DOI pattern detection."""
        handler = PublisherHandler(cache_dir=tmp_path)

        with patch("paper_scanner.tools.fetchers.fetcher_handlers.publisher_handler.requests.Session.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.headers = {"content-type": "application/pdf"}
            mock_response.content = b"PDF content"
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            plos_doi = "10.1371/journal.pone.0123456"
            pdf_info = handler.fetch_pdf(plos_doi)

            assert pdf_info is not None
            assert pdf_info.download_source == "publisher"
            assert "plos" in pdf_info.download_url.lower()

    def test_fetch_pdf_mdpi_pattern_based_flow(self, tmp_path):
        """Test full fetch_pdf flow for MDPI using DOI pattern detection."""
        handler = PublisherHandler(cache_dir=tmp_path)



        with patch("paper_scanner.tools.fetchers.fetcher_handlers.publisher_handler.requests.Session.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.headers = {"content-type": "application/pdf"}
            mock_response.content = b"PDF content"
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            mdpi_doi = "10.3390/app10010001"
            pdf_info = handler.fetch_pdf(mdpi_doi)

            assert pdf_info is not None
            assert pdf_info.download_source == "publisher"
            assert "mdpi" in pdf_info.download_url.lower()


class TestPublisherHandlerExcludedMethods:
    r"""Test that PublisherHandler explicitly excludes non-PDF methods."""

    def test_fetch_cited_by_not_implemented(self, tmp_path):
        """Test that fetch_cited_by raises NotImplementedError."""
        handler = PublisherHandler(cache_dir=tmp_path)
        
        with pytest.raises(NotImplementedError, match="PublisherHandler only downloads PDFs via fetch_pdf"):
            handler.fetch_cited_by("10.1234/test")

    def test_fetch_metadata_not_implemented(self, tmp_path):
        """Test that fetch_metadata raises NotImplementedError."""
        handler = PublisherHandler(cache_dir=tmp_path)
        
        with pytest.raises(NotImplementedError, match="PublisherHandler only downloads PDFs via fetch_pdf"):
            handler.fetch_metadata("10.1234/test")

    def test_fetch_paper_not_implemented(self, tmp_path):
        """Test that fetch_paper raises NotImplementedError."""
        handler = PublisherHandler(cache_dir=tmp_path)
        
        with pytest.raises(NotImplementedError, match="PublisherHandler only downloads PDFs via fetch_pdf"):
            handler.fetch_paper("10.1234/test")

    def test_fetch_citations_not_implemented(self, tmp_path):
        """Test that fetch_citations raises NotImplementedError."""
        handler = PublisherHandler(cache_dir=tmp_path)
        
        with pytest.raises(NotImplementedError, match="PublisherHandler only downloads PDFs via fetch_pdf"):
            handler.fetch_citations("10.1234/test")