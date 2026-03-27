"""Tests for paper_scanner.core.paths — XDG-compliant path resolution."""


import pytest

from paper_scanner.core.paths import get_cache_dir, get_json_cache_dir, get_pdf_cache_dir


@pytest.fixture(autouse=True)
def _isolate_paths(tmp_path, monkeypatch):
    """Neutralize legacy paths and CACHE_DIR so tests are hermetic."""
    monkeypatch.delenv("CACHE_DIR", raising=False)
    monkeypatch.setattr("paper_scanner.core.paths._LEGACY_CACHE_DIR", tmp_path / "nonexistent-legacy")
    monkeypatch.setattr("paper_scanner.core.paths._LEGACY_JSON_CACHE_DIR", tmp_path / "nonexistent-legacy-json")
    monkeypatch.setattr("paper_scanner.core.paths._LEGACY_PDF_CACHE_DIR", tmp_path / "nonexistent-legacy-pdf")


class TestGetCacheDir:
    """Test main cache directory resolution."""

    def test_xdg_default(self, tmp_path, monkeypatch):
        """Without any overrides, uses $XDG_CACHE_HOME/paper-scanner."""
        monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / ".cache"))
        result = get_cache_dir()
        assert result == tmp_path / ".cache" / "paper-scanner"

    def test_xdg_env_override(self, tmp_path, monkeypatch):
        """XDG_CACHE_HOME env var is respected."""
        monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "custom-cache"))
        result = get_cache_dir()
        assert result == tmp_path / "custom-cache" / "paper-scanner"

    def test_cache_dir_env_override(self, tmp_path, monkeypatch):
        """CACHE_DIR env var takes priority over XDG."""
        monkeypatch.setenv("CACHE_DIR", str(tmp_path / "explicit"))
        result = get_cache_dir()
        assert result == tmp_path / "explicit"

    def test_explicit_override(self, tmp_path, monkeypatch):
        """Explicit path argument takes highest priority."""
        monkeypatch.setenv("CACHE_DIR", str(tmp_path / "env"))
        result = get_cache_dir(override=tmp_path / "arg")
        assert result == tmp_path / "arg"

    def test_legacy_fallback(self, tmp_path, monkeypatch):
        """Falls back to legacy path if it exists and XDG dir does not."""
        monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / ".cache"))
        legacy = tmp_path / ".paper-scanner-legacy"
        legacy.mkdir()
        monkeypatch.setattr("paper_scanner.core.paths._LEGACY_CACHE_DIR", legacy)
        result = get_cache_dir()
        assert result == legacy

    def test_xdg_preferred_over_legacy(self, tmp_path, monkeypatch):
        """XDG path wins if both XDG and legacy exist."""
        monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / ".cache"))
        xdg = tmp_path / ".cache" / "paper-scanner"
        xdg.mkdir(parents=True)
        legacy = tmp_path / ".paper-scanner-legacy"
        legacy.mkdir()
        monkeypatch.setattr("paper_scanner.core.paths._LEGACY_CACHE_DIR", legacy)
        result = get_cache_dir()
        assert result == xdg


class TestGetJsonCacheDir:
    """Test JSON API cache directory resolution."""

    def test_xdg_default(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / ".cache"))
        result = get_json_cache_dir()
        assert result == tmp_path / ".cache" / "paper-scanner" / "api"

    def test_explicit_override(self, tmp_path):
        result = get_json_cache_dir(override=tmp_path / "custom")
        assert result == tmp_path / "custom"

    def test_legacy_fallback(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / ".cache"))
        legacy = tmp_path / ".cache_files-legacy"
        legacy.mkdir()
        monkeypatch.setattr("paper_scanner.core.paths._LEGACY_JSON_CACHE_DIR", legacy)
        result = get_json_cache_dir()
        assert result == legacy


class TestGetPdfCacheDir:
    """Test PDF cache directory resolution."""

    def test_xdg_default(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / ".cache"))
        result = get_pdf_cache_dir()
        assert result == tmp_path / ".cache" / "paper-scanner" / "pdf"

    def test_explicit_override(self, tmp_path):
        result = get_pdf_cache_dir(override=tmp_path / "custom")
        assert result == tmp_path / "custom"

    def test_legacy_fallback(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / ".cache"))
        legacy = tmp_path / ".cache_pdf-legacy"
        legacy.mkdir()
        monkeypatch.setattr("paper_scanner.core.paths._LEGACY_PDF_CACHE_DIR", legacy)
        result = get_pdf_cache_dir()
        assert result == legacy
