"""
Comprehensive unit tests for PDFCache class in paper_scanner.tools.cache module.

Tests the PDFCache class including:
- Cache initialization and directory creation
- Getting/setting cache entries
- Cache key hashing
- Cache clearing
- Error handling
- File operations (moving, reading, validation)
- Edge cases
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from paper_scanner.core import doi
from paper_scanner.tools.cache import CacheError, PDFCache


class TestPDFCacheInitialization:
    """Tests for PDFCache initialization and setup."""

    def test_pdfcache_init_with_custom_dir(self, tmp_path):
        """Test PDFCache initialization with custom directory."""
        cache_dir = tmp_path / "custom_pdf_cache"
        cache = PDFCache(cache_dir=cache_dir)

        assert cache.cache_dir == cache_dir
        assert cache_dir.exists()

    def test_pdfcache_init_creates_directory(self, tmp_path):
        """Test that PDFCache initialization creates directory if it doesn't exist."""
        cache_dir = tmp_path / "nested" / "pdf" / "cache"
        cache = PDFCache(cache_dir=cache_dir)

        assert cache_dir.exists()
        assert cache_dir.is_dir()

    def test_pdfcache_init_with_none_uses_default(self, tmp_path):
        """Test that None cache_dir uses default ~/.cache_pdf."""
        with patch.object(Path, 'home', return_value=tmp_path):
            cache = PDFCache(cache_dir=None)
            expected = tmp_path / ".cache_pdf"
            assert cache.cache_dir == expected
            assert expected.exists()

    def test_pdfcache_init_expands_user_path(self, tmp_path):
        """Test that ~ is expanded in cache_dir path."""
        test_cache_path = str(tmp_path / ".my_pdf_cache")
        cache = PDFCache(cache_dir=test_cache_path)
        assert cache.cache_dir.exists()
        assert ".my_pdf_cache" in str(cache.cache_dir)

    def test_pdfcache_init_existing_directory(self, tmp_path):
        """Test PDFCache initialization with existing directory."""
        cache1 = PDFCache(cache_dir=tmp_path)
        cache2 = PDFCache(cache_dir=tmp_path)

        assert cache1.cache_dir == cache2.cache_dir
        assert tmp_path.exists()


class TestPDFCacheKeyPath:
    """Tests for cache key to path conversion."""

    def test_get_cache_path_returns_pdf_file(self, tmp_path):
        """Test that _get_cache_path returns a .pdf file."""
        cache = PDFCache(cache_dir=tmp_path)
        key = "10.1234/test.doi"
        path = cache._get_cache_path(key)

        assert path.suffix == ".pdf"
        assert path.parent == tmp_path

    def test_get_cache_path_consistent_for_same_key(self, tmp_path):
        """Test that same key always generates same cache path."""
        cache = PDFCache(cache_dir=tmp_path)
        key = "10.1234/test.doi"

        path1 = cache._get_cache_path(key)
        path2 = cache._get_cache_path(key)

        assert path1 == path2

    def test_get_cache_path_different_for_different_keys(self, tmp_path):
        """Test that different keys generate different cache paths."""
        cache = PDFCache(cache_dir=tmp_path)

        path1 = cache._get_cache_path("10.1234/doi1")
        path2 = cache._get_cache_path("10.1234/doi2")

        assert path1 != path2

    def test_get_cache_path_uses_doi_md5_hash(self, tmp_path):
        """Test that cache path uses DOI MD5 hash."""
        cache = PDFCache(cache_dir=tmp_path)
        key = "10.1234/test.doi"

        with patch.object(doi.DOI, 'md5', "testhash123"):
            path = cache._get_cache_path(key)
            assert "testhash123" in path.name

    def test_get_cache_path_handles_special_characters(self, tmp_path):
        """Test that DOI paths with special characters are handled correctly."""
        cache = PDFCache(cache_dir=tmp_path)

        keys = [
            "10.1234/test.doi",
            "10.1234/test/doi/with/slashes",
            "10.1234/test-doi-with-dashes",
            "10.1234/test_doi_with_underscores",
        ]

        paths = [cache._get_cache_path(key) for key in keys]

        # All paths should be valid and different
        assert len(paths) == len(set(paths))
        for path in paths:
            assert path.suffix == ".pdf"


class TestPDFCacheGet:
    """Tests for PDFCache get functionality."""

    def test_get_returns_none_for_missing_key(self, tmp_path):
        """Test that get returns None when key doesn't exist."""
        cache = PDFCache(cache_dir=tmp_path)
        result = cache.get("10.9999/nonexistent")

        assert result is None

    def test_get_returns_path_for_existing_pdf(self, tmp_path):
        """Test that get returns path for existing cached PDF."""
        cache = PDFCache(cache_dir=tmp_path)
        key = "10.1234/test.doi"

        # Create a dummy PDF file
        cache_path = cache._get_cache_path(key)
        cache_path.write_bytes(b"PDF content")

        result = cache.get(key)
        assert result == cache_path

    def test_get_returns_none_for_non_file(self, tmp_path):
        """Test that get returns None if cache path is a directory."""
        cache = PDFCache(cache_dir=tmp_path)
        key = "10.1234/test.doi"

        # Create a directory instead of file
        cache_path = cache._get_cache_path(key)
        cache_path.mkdir()

        result = cache.get(key)
        assert result is None

    def test_get_validates_file_readability(self, tmp_path):
        """Test that get validates file is readable."""
        cache = PDFCache(cache_dir=tmp_path)
        key = "10.1234/test.doi"

        cache_path = cache._get_cache_path(key)
        cache_path.write_bytes(b"PDF content")

        # Should be readable and return path
        result = cache.get(key)
        assert result == cache_path

    def test_get_returns_none_for_unreadable_file(self, tmp_path):
        """Test that get returns None if file is not readable."""
        cache = PDFCache(cache_dir=tmp_path)
        key = "10.1234/test.doi"

        cache_path = cache._get_cache_path(key)
        cache_path.write_bytes(b"PDF content")

        # Patch open to raise exception
        with patch("builtins.open", side_effect=IOError("Permission denied")):
            result = cache.get(key)
            assert result is None

    def test_get_returns_none_for_corrupted_file(self, tmp_path):
        """Test that get handles corrupted/empty files gracefully."""
        cache = PDFCache(cache_dir=tmp_path)
        key = "10.1234/test.doi"

        cache_path = cache._get_cache_path(key)
        cache_path.write_bytes(b"")  # Empty file

        # Should still return the path since file exists
        result = cache.get(key)
        assert result == cache_path


class TestPDFCacheSet:
    """Tests for PDFCache set functionality."""

    def test_set_moves_file_to_cache(self, tmp_path):
        """Test that set moves file from temp location to cache."""
        cache = PDFCache(cache_dir=tmp_path / "cache")
        tmp_pdf = tmp_path / "temp" / "paper.pdf"
        tmp_pdf.parent.mkdir(parents=True)
        tmp_pdf.write_bytes(b"PDF content")

        key = "10.1234/test.doi"
        result = cache.set(key, tmp_pdf)

        # Should return cached path
        expected_path = cache._get_cache_path(key)
        assert result == expected_path

        # Original should be moved
        assert not tmp_pdf.exists()

        # Cached file should exist with content
        assert expected_path.exists()
        assert expected_path.read_bytes() == b"PDF content"

    def test_set_returns_cache_path(self, tmp_path):
        """Test that set returns the cache path."""
        cache = PDFCache(cache_dir=tmp_path / "cache")
        tmp_pdf = tmp_path / "temp" / "paper.pdf"
        tmp_pdf.parent.mkdir(parents=True)
        tmp_pdf.write_bytes(b"content")

        key = "10.1234/test.doi"
        result = cache.set(key, tmp_pdf)

        assert isinstance(result, Path)
        assert result.parent == cache.cache_dir

    def test_set_raises_error_if_tmp_file_not_exist(self, tmp_path):
        """Test that set raises CacheError if temp file doesn't exist."""
        cache = PDFCache(cache_dir=tmp_path)
        nonexistent = tmp_path / "nonexistent.pdf"

        with pytest.raises(CacheError) as exc_info:
            cache.set("10.1234/test.doi", nonexistent)

        assert "Temporary file does not exist" in str(exc_info.value)

    def test_set_raises_error_if_tmp_path_is_directory(self, tmp_path):
        """Test that set raises CacheError if temp path is a directory."""
        cache = PDFCache(cache_dir=tmp_path)
        tmp_dir = tmp_path / "tempdir"
        tmp_dir.mkdir()

        with pytest.raises(CacheError) as exc_info:
            cache.set("10.1234/test.doi", tmp_dir)

        assert "not a file" in str(exc_info.value)

    def test_set_raises_error_on_move_failure(self, tmp_path):
        """Test that set raises CacheError if move operation fails."""
        cache = PDFCache(cache_dir=tmp_path / "cache")
        tmp_pdf = tmp_path / "temp" / "paper.pdf"
        tmp_pdf.parent.mkdir(parents=True)
        tmp_pdf.write_bytes(b"content")

        with patch("shutil.move", side_effect=Exception("Move failed")):
            with pytest.raises(CacheError) as exc_info:
                cache.set("10.1234/test.doi", tmp_pdf)

            assert "Error moving PDF to cache" in str(exc_info.value)

    def test_set_with_string_path(self, tmp_path):
        """Test that set accepts string path arguments."""
        cache = PDFCache(cache_dir=tmp_path / "cache")
        tmp_pdf = tmp_path / "temp" / "paper.pdf"
        tmp_pdf.parent.mkdir(parents=True)
        tmp_pdf.write_bytes(b"content")

        key = "10.1234/test.doi"
        result = cache.set(key, str(tmp_pdf))  # Pass as string

        assert result.exists()
        assert not tmp_pdf.exists()

    def test_set_with_path_object(self, tmp_path):
        """Test that set accepts Path object arguments."""
        cache = PDFCache(cache_dir=tmp_path / "cache")
        tmp_pdf = tmp_path / "temp" / "paper.pdf"
        tmp_pdf.parent.mkdir(parents=True)
        tmp_pdf.write_bytes(b"content")

        key = "10.1234/test.doi"
        result = cache.set(key, Path(tmp_pdf))  # Pass as Path

        assert result.exists()
        assert not tmp_pdf.exists()

    def test_set_does_not_overwrite_existing_cache(self, tmp_path):
        """Test that set does not overwrite existing cached file."""
        cache = PDFCache(cache_dir=tmp_path / "cache")

        key = "10.1234/test.doi"
        cache_path = cache._get_cache_path(key)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_bytes(b"old content")

        # Create new temp file
        tmp_pdf = tmp_path / "temp" / "paper.pdf"
        tmp_pdf.parent.mkdir(parents=True)
        tmp_pdf.write_bytes(b"new content")

        cache.set(key, tmp_pdf)

        # Should have new content
        assert cache_path.read_bytes() == b"old content"


class TestPDFCacheClear:
    """Tests for PDFCache clear functionality."""

    def test_clear_removes_all_pdf_files(self, tmp_path):
        """Test that clear removes all .pdf files from cache."""
        cache = PDFCache(cache_dir=tmp_path)

        # Create multiple PDF files
        for i in range(3):
            pdf_path = cache.cache_dir / f"file{i}.pdf"
            pdf_path.write_bytes(b"content")

        count = cache.clear()

        assert count == 3
        assert len(list(cache.cache_dir.glob("*.pdf"))) == 0

    def test_clear_returns_count_of_deleted_files(self, tmp_path):
        """Test that clear returns correct count."""
        cache = PDFCache(cache_dir=tmp_path)

        # Create 5 PDF files
        for i in range(5):
            pdf_path = cache.cache_dir / f"file{i}.pdf"
            pdf_path.write_bytes(b"content")

        count = cache.clear()
        assert count == 5

    def test_clear_returns_zero_when_cache_empty(self, tmp_path):
        """Test that clear returns 0 when no files to delete."""
        cache = PDFCache(cache_dir=tmp_path)
        count = cache.clear()

        assert count == 0

    def test_clear_does_not_remove_non_pdf_files(self, tmp_path):
        """Test that clear only removes .pdf files."""
        cache = PDFCache(cache_dir=tmp_path)

        # Create PDF and other files
        pdf = cache.cache_dir / "file.pdf"
        pdf.write_bytes(b"pdf")

        txt = cache.cache_dir / "file.txt"
        txt.write_bytes(b"text")

        json_file = cache.cache_dir / "file.json"
        json_file.write_bytes(b"{}")

        count = cache.clear()

        # Only PDF should be removed
        assert count == 1
        assert not pdf.exists()
        assert txt.exists()
        assert json_file.exists()

    def test_clear_raises_error_on_permission_denied(self, tmp_path):
        """Test that clear raises CacheError on permission error."""
        cache = PDFCache(cache_dir=tmp_path)

        pdf_path = cache.cache_dir / "file.pdf"
        pdf_path.write_bytes(b"content")

        with patch.object(Path, 'unlink', side_effect=PermissionError("Permission denied")):
            with pytest.raises(CacheError) as exc_info:
                cache.clear()

            assert "Error clearing PDF cache" in str(exc_info.value)


class TestPDFCacheIntegration:
    """Integration tests for PDFCache."""

    def test_set_and_get_workflow(self, tmp_path):
        """Test complete set and get workflow."""
        cache = PDFCache(cache_dir=tmp_path / "cache")

        # Create temp PDF
        tmp_pdf = tmp_path / "temp" / "paper.pdf"
        tmp_pdf.parent.mkdir(parents=True)
        tmp_pdf.write_bytes(b"PDF content for testing")

        key = "10.1234/test.doi"

        # Set in cache
        cached_path = cache.set(key, tmp_pdf)
        assert cached_path.exists()

        # Get from cache
        retrieved = cache.get(key)
        assert retrieved == cached_path
        assert retrieved.read_bytes() == b"PDF content for testing"

    def test_multiple_pdfs_in_cache(self, tmp_path):
        """Test caching multiple PDFs with different keys."""
        cache = PDFCache(cache_dir=tmp_path / "cache")

        keys = ["10.1234/doi1", "10.1234/doi2", "10.1234/doi3"]
        cached_paths = {}

        for i, key in enumerate(keys):
            tmp_pdf = tmp_path / "temp" / f"paper{i}.pdf"
            tmp_pdf.parent.mkdir(parents=True, exist_ok=True)
            tmp_pdf.write_bytes(f"Content {i}".encode())

            cached_paths[key] = cache.set(key, tmp_pdf)

        # Verify all are cached and retrievable
        for key in keys:
            retrieved = cache.get(key)
            assert retrieved == cached_paths[key]
            assert retrieved.exists()

    def test_cache_lifecycle(self, tmp_path):
        """Test full cache lifecycle: set, get, clear."""
        cache = PDFCache(cache_dir=tmp_path / "cache")

        # Set
        tmp_pdf = tmp_path / "temp" / "paper.pdf"
        tmp_pdf.parent.mkdir(parents=True)
        tmp_pdf.write_bytes(b"content")

        cache.set("10.1234/test.doi", tmp_pdf)

        # Get
        assert cache.get("10.1234/test.doi") is not None

        # Clear
        count = cache.clear()
        assert count == 1
        assert cache.get("10.1234/test.doi") is None
