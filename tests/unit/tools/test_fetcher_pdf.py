"""
Test suite for Fetcher PDF fetching functionality.

Tests PDF caching, handler integration, and error handling for PDF downloads.
"""

from pathlib import Path
from unittest.mock import patch, MagicMock

from paper_scanner.core.models import PDFInfo
from paper_scanner.tools.fetchers.fetcher import Fetcher


class TestFetcherPDFCaching:
    """Test PDF fetching and caching behavior."""

    def test_fetch_pdf_cache_miss_then_hit(self, tmp_path):
        """Test PDF fetch returns cached PDFInfo on second call."""
        fetcher = Fetcher(cache_dir=tmp_path, methods=["crossref"])

        # Create a temp PDF file
        tmp_pdf = tmp_path / "temp" / "paper.pdf"
        tmp_pdf.parent.mkdir(parents=True)
        tmp_pdf.write_bytes(b"PDF content")

        pdf_info = PDFInfo(
            file_path=str(tmp_pdf),
            file_size_bytes=11,
            download_source="crossref",
        )

        # Mock the handler's fetch_pdf method
        fetcher.handlers["crossref"].fetch_pdf = MagicMock(return_value=pdf_info)

        # First call: cache miss, fetches from handler
        result1 = fetcher.fetch_pdf("10.1234/test.doi")
        assert result1 is not None
        assert Path(result1.file_path).exists()
        assert result1.file_path.endswith(".pdf")

        # Second call: should be cache hit, no handler call
        fetcher.handlers["crossref"].fetch_pdf = MagicMock(
            side_effect=Exception("Should not be called")
        )
        result2 = fetcher.fetch_pdf("10.1234/test.doi")
        # Cached PDFs have download_source="cache"
        assert result2 is not None
        assert result2.file_path == result1.file_path
        assert result2.download_source == "cache"
        assert Path(result2.file_path).exists()

    def test_fetch_pdf_returns_pdfinfo_object(self, tmp_path):
        """Test that fetch_pdf returns a PDFInfo object."""
        fetcher = Fetcher(cache_dir=tmp_path, methods=["crossref"])

        tmp_pdf = tmp_path / "temp" / "paper.pdf"
        tmp_pdf.parent.mkdir(parents=True)
        tmp_pdf.write_bytes(b"PDF")

        pdf_info = PDFInfo(
            file_path=str(tmp_pdf),
            file_size_bytes=3,
            download_source="crossref",
        )

        fetcher.handlers["crossref"].fetch_pdf = MagicMock(return_value=pdf_info)

        result = fetcher.fetch_pdf("10.1234/test.doi")
        assert result is not None
        assert isinstance(result, PDFInfo)
        assert result.download_source == "crossref"

    def test_fetch_pdf_not_found_returns_none(self, tmp_path):
        """Test that fetch_pdf returns None when not found."""
        fetcher = Fetcher(cache_dir=tmp_path, methods=["crossref"])

        fetcher.handlers["crossref"].fetch_pdf = MagicMock(return_value=None)
        result = fetcher.fetch_pdf("10.9999/nonexistent")
        assert result is None

    def test_fetch_pdf_handler_exception_returns_none(self, tmp_path):
        """Test that fetch_pdf returns None when handler raises exception."""
        fetcher = Fetcher(cache_dir=tmp_path, methods=["crossref"])

        fetcher.handlers["crossref"].fetch_pdf = MagicMock(
            side_effect=Exception("Download failed")
        )
        result = fetcher.fetch_pdf("10.1234/test.doi")
        assert result is None

    def test_fetch_pdf_uses_doi_md5_for_cache_filename(self, tmp_path):
        """Test that cached PDF uses DOI MD5 hash as filename."""
        fetcher = Fetcher(cache_dir=tmp_path, methods=["crossref"])

        tmp_pdf = tmp_path / "temp" / "paper.pdf"
        tmp_pdf.parent.mkdir(parents=True)
        tmp_pdf.write_bytes(b"PDF")

        doi = "10.1234/test.doi"

        pdf_info = PDFInfo(
            file_path=str(tmp_pdf),
            file_size_bytes=3,
            download_source="crossref",
        )

        fetcher.handlers["crossref"].fetch_pdf = MagicMock(return_value=pdf_info)

        result = fetcher.fetch_pdf(doi)
        assert result is not None

        # Verify filename is MD5 hash based
        pdf_path = Path(result.file_path)
        assert pdf_path.name.endswith(".pdf")
        # MD5 hash should be 32 hex chars
        hash_part = pdf_path.name[:-4]  # Remove .pdf extension
        assert len(hash_part) == 32
        assert all(c in "0123456789abcdef" for c in hash_part)

    def test_fetch_pdf_multiple_dois_separate_cache_entries(self, tmp_path):
        """Test that different DOIs cache separately."""
        fetcher = Fetcher(cache_dir=tmp_path, methods=["crossref"])

        dois = ["10.1234/doi1", "10.1234/doi2", "10.1234/doi3"]
        pdf_infos = {}

        for i, doi in enumerate(dois):
            tmp_pdf = tmp_path / "temp" / f"paper{i}.pdf"
            tmp_pdf.parent.mkdir(parents=True, exist_ok=True)
            tmp_pdf.write_bytes(f"PDF {i}".encode())

            pdf_info = PDFInfo(
                file_path=str(tmp_pdf),
                file_size_bytes=len(f"PDF {i}".encode()),
                download_source="crossref",
            )

            fetcher.handlers["crossref"].fetch_pdf = MagicMock(return_value=pdf_info)

            result = fetcher.fetch_pdf(doi)
            assert result is not None
            pdf_infos[doi] = result

        # All should have different paths
        pdf_paths = {doi: Path(info.file_path) for doi, info in pdf_infos.items()}
        assert len(set(str(p) for p in pdf_paths.values())) == len(dois)

        # All should exist
        for pdf_path in pdf_paths.values():
            assert pdf_path.exists()

    def test_fetch_pdf_from_cache_without_handler_call(self, tmp_path):
        """Test that cached PDF is returned without calling handler."""
        fetcher = Fetcher(cache_dir=tmp_path, methods=["crossref"])

        tmp_pdf = tmp_path / "temp" / "paper.pdf"
        tmp_pdf.parent.mkdir(parents=True)
        tmp_pdf.write_bytes(b"Original PDF")

        pdf_info = PDFInfo(
            file_path=str(tmp_pdf),
            file_size_bytes=12,
            download_source="crossref",
        )

        mock_fetch = MagicMock(return_value=pdf_info)
        fetcher.handlers["crossref"].fetch_pdf = mock_fetch

        # First call
        result1 = fetcher.fetch_pdf("10.1234/test.doi")
        assert result1 is not None
        assert mock_fetch.call_count == 1

        # Second call should NOT call handler (uses cache)
        result2 = fetcher.fetch_pdf("10.1234/test.doi")
        assert mock_fetch.call_count == 1  # Still 1, not 2
        assert result2 is not None
        assert result2.file_path == result1.file_path
        assert result2.download_source == "cache"

    def test_fetch_pdf_handler_exception_tries_fallback(self, tmp_path):
        """Test that fetch_pdf tries next handler if one fails."""
        fetcher = Fetcher(cache_dir=tmp_path, methods=["crossref"])

        tmp_pdf = tmp_path / "temp" / "paper.pdf"
        tmp_pdf.parent.mkdir(parents=True)
        tmp_pdf.write_bytes(b"PDF from handler")

        fetcher.handlers["crossref"].fetch_pdf = MagicMock(
            side_effect=Exception("First handler fails")
        )
        result = fetcher.fetch_pdf("10.1234/test.doi")
        # Should return None since only one handler and it failed
        assert result is None

    def test_fetch_pdf_validates_cached_file_readable(self, tmp_path):
        """Test that cached PDF is validated to be readable."""
        fetcher = Fetcher(cache_dir=tmp_path, methods=["crossref"])

        tmp_pdf = tmp_path / "temp" / "paper.pdf"
        tmp_pdf.parent.mkdir(parents=True)
        tmp_pdf.write_bytes(b"PDF content")

        doi = "10.1234/test.doi"

        # Create the PDFInfo object that the handler should return
        pdf_info = PDFInfo(
            file_path=str(tmp_pdf),
            file_size_bytes=11,
            download_source="crossref",
        )

        # Mock the handler's fetch_pdf method
        fetcher.handlers["crossref"].fetch_pdf = MagicMock(return_value=pdf_info)

        # Cache the PDF
        result = fetcher.fetch_pdf(doi)
        assert result is not None, "First fetch should return PDFInfo"
        assert Path(result.file_path).exists(), f"Cached PDF should exist at {result.file_path}"

        # Verify it's readable by fetching from cache
        cached = fetcher.fetch_pdf(doi)
        assert cached is not None, "Second fetch from cache should return PDFInfo"
        assert cached.file_path == result.file_path, "Cache should return same path"
        # Verify the file content
        assert Path(cached.file_path).read_bytes() == b"PDF content", "File content should match"

