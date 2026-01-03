"""
Tests for the cache CLI task

Tests the cache info and cache clear functions
"""

from pathlib import Path

from paper_scanner.cli.tasks.cache import (
    _count_files,
    _format_size,
    _get_dir_size,
    execute_cache_clear,
    execute_cache_info,
)


class TestCacheHelpers:
    """Test helper functions for cache operations"""

    def test_format_size_bytes(self):
        """Test formatting bytes"""
        assert _format_size(512) == "512.0B"

    def test_format_size_kilobytes(self):
        """Test formatting kilobytes"""
        assert _format_size(2048) == "2.0KB"

    def test_format_size_megabytes(self):
        """Test formatting megabytes"""
        assert _format_size(1024 * 1024 * 5) == "5.0MB"

    def test_format_size_gigabytes(self):
        """Test formatting gigabytes"""
        assert _format_size(1024 * 1024 * 1024 * 2) == "2.0GB"

    def test_format_size_terabytes(self):
        """Test formatting terabytes"""
        assert _format_size(1024 * 1024 * 1024 * 1024 * 3) == "3.0TB"

    def test_get_dir_size_nonexistent(self):
        """Test directory size for non-existent directory"""
        result = _get_dir_size(Path("/nonexistent/path"))
        assert result == 0

    def test_get_dir_size_with_files(self, tmp_path):
        """Test calculating directory size with files"""
        # Create test files
        (tmp_path / "file1.txt").write_text("hello")  # 5 bytes
        (tmp_path / "file2.txt").write_text("world!")  # 6 bytes

        size = _get_dir_size(tmp_path)
        assert size == 11

    def test_get_dir_size_nested(self, tmp_path):
        """Test directory size with nested directories"""
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (tmp_path / "file1.txt").write_text("hello")  # 5 bytes
        (subdir / "file2.txt").write_text("world!")  # 6 bytes

        size = _get_dir_size(tmp_path)
        assert size == 11

    def test_count_files_nonexistent(self):
        """Test file count for non-existent directory"""
        result = _count_files(Path("/nonexistent/path"))
        assert result == 0

    def test_count_files_empty_directory(self, tmp_path):
        """Test file count for empty directory"""
        result = _count_files(tmp_path)
        assert result == 0

    def test_count_files_with_files(self, tmp_path):
        """Test counting files in directory"""
        (tmp_path / "file1.txt").write_text("hello")
        (tmp_path / "file2.txt").write_text("world")

        result = _count_files(tmp_path)
        assert result == 2

    def test_count_files_nested(self, tmp_path):
        """Test counting files with nested directories"""
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (tmp_path / "file1.txt").write_text("hello")
        (subdir / "file2.txt").write_text("world")

        result = _count_files(tmp_path)
        # Counts both files and subdirectory
        assert result >= 2


class TestCacheInfo:
    """Test cache info functionality"""

    def test_cache_info_with_empty_cache(self, tmp_path):
        """Test cache info with empty cache directory"""
        # Create empty cache directory structure
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        (cache_dir / "checkpoints").mkdir()
        (cache_dir / "crossref").mkdir()

        result = execute_cache_info(cache_dir=cache_dir, verbose=False)
        assert result == 0

    def test_cache_info_with_populated_cache(self, tmp_path):
        """Test cache info with files in cache"""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        # Create checkpoints
        checkpoints_dir = cache_dir / "checkpoints"
        checkpoints_dir.mkdir()
        (checkpoints_dir / "checkpoint_1.json").write_text('{"test": "data"}')
        (checkpoints_dir / "checkpoint_2.json").write_text('{"test": "data"}')

        # Create crossref cache
        crossref_dir = cache_dir / "crossref"
        crossref_dir.mkdir()
        (crossref_dir / "cache.db").write_text('cache data')

        result = execute_cache_info(cache_dir=cache_dir, verbose=False)
        assert result == 0

    def test_cache_info_verbose_mode(self, tmp_path, capsys):
        """Test cache info in verbose mode"""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        (cache_dir / "checkpoints").mkdir()
        (cache_dir / "crossref").mkdir()

        result = execute_cache_info(cache_dir=cache_dir, verbose=True)
        assert result == 0

    def test_cache_info_default_cache_dir(self, tmp_path, monkeypatch):
        """Test cache info uses default cache directory"""
        # Create test cache directory structure
        cache_dir = tmp_path / ".paper-scanner"
        cache_dir.mkdir()
        (cache_dir / "checkpoints").mkdir()
        (cache_dir / "crossref").mkdir()
        
        # Mock HOME to use temp directory instead of actual user home
        monkeypatch.setenv("HOME", str(tmp_path))

        result = execute_cache_info(cache_dir=None, verbose=False)
        assert result == 0

    def test_cache_info_with_env_var(self, tmp_path, monkeypatch):
        """Test cache info respects CACHE_DIR environment variable"""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        (cache_dir / "checkpoints").mkdir()
        (cache_dir / "crossref").mkdir()

        monkeypatch.setenv("CACHE_DIR", str(cache_dir))

        result = execute_cache_info(cache_dir=None, verbose=False)
        assert result == 0


class TestCacheClear:
    """Test cache clear functionality"""

    def test_clear_checkpoints_existing(self, tmp_path):
        """Test clearing existing checkpoints"""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        checkpoints_dir = cache_dir / "checkpoints"
        checkpoints_dir.mkdir()
        (checkpoints_dir / "checkpoint_1.json").write_text('{"test": "data"}')
        (checkpoints_dir / "checkpoint_2.json").write_text('{"test": "data"}')

        assert checkpoints_dir.exists()

        result = execute_cache_clear("checkpoints", cache_dir=cache_dir, verbose=False)

        assert result == 0
        assert not checkpoints_dir.exists()

    def test_clear_checkpoints_not_existing(self, tmp_path):
        """Test clearing checkpoints when directory doesn't exist"""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        result = execute_cache_clear("checkpoints", cache_dir=cache_dir, verbose=False)

        assert result == 0

    def test_clear_checkpoints_verbose(self, tmp_path):
        """Test clearing checkpoints with verbose output"""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        checkpoints_dir = cache_dir / "checkpoints"
        checkpoints_dir.mkdir()
        (checkpoints_dir / "checkpoint_1.json").write_text('{"test": "data"}')

        result = execute_cache_clear("checkpoints", cache_dir=cache_dir, verbose=True)

        assert result == 0
        assert not checkpoints_dir.exists()

    def test_clear_invalid_target(self, tmp_path):
        """Test clearing with invalid target returns failure"""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        result = execute_cache_clear("invalid_target", cache_dir=cache_dir, verbose=False)

        assert result == 1

    def test_clear_checkpoints_default_cache_dir(self, tmp_path, monkeypatch):
        """Test clear checkpoints with default cache directory"""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        checkpoints_dir = cache_dir / "checkpoints"
        checkpoints_dir.mkdir()
        (checkpoints_dir / "checkpoint_1.json").write_text('{"test": "data"}')

        monkeypatch.setenv("CACHE_DIR", str(cache_dir))

        result = execute_cache_clear("checkpoints", cache_dir=None, verbose=False)

        assert result == 0
        assert not checkpoints_dir.exists()

    def test_clear_checkpoints_preserves_other_dirs(self, tmp_path):
        """Test that clearing checkpoints preserves other cache directories"""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        # Create checkpoints
        checkpoints_dir = cache_dir / "checkpoints"
        checkpoints_dir.mkdir()
        (checkpoints_dir / "checkpoint_1.json").write_text('{"test": "data"}')

        # Create crossref (should be preserved)
        crossref_dir = cache_dir / "crossref"
        crossref_dir.mkdir()
        (crossref_dir / "cache.db").write_text('cache data')

        result = execute_cache_clear("checkpoints", cache_dir=cache_dir, verbose=False)

        assert result == 0
        assert not checkpoints_dir.exists()
        assert crossref_dir.exists()
