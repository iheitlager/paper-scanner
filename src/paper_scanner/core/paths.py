"""
Centralized XDG Base Directory compliant path resolution for paper-scanner.

All cache paths follow the XDG Base Directory Specification:
- Cache: $XDG_CACHE_HOME/paper-scanner/ (default: ~/.cache/paper-scanner/)

Legacy paths (~/.paper-scanner, ~/.cache_files, ~/.cache_pdf) are detected
and used as fallback with a warning logged.

Override precedence (highest to lowest):
1. Explicit path passed to function
2. CACHE_DIR environment variable
3. Legacy path (if exists and XDG path does not)
4. XDG default
"""

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

APP_NAME = "paper-scanner"

# Legacy paths that pre-date XDG compliance
_LEGACY_CACHE_DIR = Path.home() / ".paper-scanner"
_LEGACY_JSON_CACHE_DIR = Path.home() / ".cache_files"
_LEGACY_PDF_CACHE_DIR = Path.home() / ".cache_pdf"


def _xdg_cache_home() -> Path:
    """Return $XDG_CACHE_HOME or its default (~/.cache)."""
    return Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))


def _resolve_with_legacy(xdg_path: Path, legacy_path: Path, label: str) -> Path:
    """Return xdg_path unless only the legacy path exists, in which case warn and return legacy."""
    if xdg_path.exists():
        return xdg_path
    if legacy_path.exists():
        logger.warning(
            "Using legacy %s path '%s'. "
            "Migrate to '%s' (XDG compliant) to silence this warning.",
            label,
            legacy_path,
            xdg_path,
        )
        return legacy_path
    return xdg_path


def get_cache_dir(override: Path | None = None) -> Path:
    """
    Return the main cache directory for checkpoints and pipeline state.

    Resolution order:
    1. override argument
    2. CACHE_DIR env var
    3. Legacy ~/.paper-scanner (if it exists and XDG dir does not)
    4. $XDG_CACHE_HOME/paper-scanner/
    """
    if override is not None:
        return Path(override).expanduser()

    env = os.getenv("CACHE_DIR", "")
    if env:
        return Path(env).expanduser()

    xdg = _xdg_cache_home() / APP_NAME
    return _resolve_with_legacy(xdg, _LEGACY_CACHE_DIR, "cache")


def get_json_cache_dir(override: Path | None = None) -> Path:
    """
    Return the directory for cached JSON API responses.

    Resolution order:
    1. override argument
    2. Legacy ~/.cache_files (if it exists and XDG dir does not)
    3. $XDG_CACHE_HOME/paper-scanner/api/
    """
    if override is not None:
        return Path(override).expanduser()

    xdg = _xdg_cache_home() / APP_NAME / "api"
    return _resolve_with_legacy(xdg, _LEGACY_JSON_CACHE_DIR, "JSON cache")


def get_pdf_cache_dir(override: Path | None = None) -> Path:
    """
    Return the directory for cached PDF files.

    Resolution order:
    1. override argument
    2. Legacy ~/.cache_pdf (if it exists and XDG dir does not)
    3. $XDG_CACHE_HOME/paper-scanner/pdf/
    """
    if override is not None:
        return Path(override).expanduser()

    xdg = _xdg_cache_home() / APP_NAME / "pdf"
    return _resolve_with_legacy(xdg, _LEGACY_PDF_CACHE_DIR, "PDF cache")
