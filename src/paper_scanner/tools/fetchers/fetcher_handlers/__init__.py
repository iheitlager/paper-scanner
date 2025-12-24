"""API-specific fetcher handler implementations."""

from paper_scanner.tools.fetchers.fetcher_handlers.base import BaseFetcherHandler
from paper_scanner.tools.fetchers.fetcher_handlers.crossref_handler import CrossrefHandler
from paper_scanner.tools.fetchers.fetcher_handlers.manual_handler import ManualHandler

__all__ = ["BaseFetcherHandler", "CrossrefHandler", "ManualHandler"]
