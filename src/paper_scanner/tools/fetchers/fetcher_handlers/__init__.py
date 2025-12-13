"""API-specific fetcher handler implementations."""

from paper_scanner.tools.fetchers.fetcher_handlers.base import BaseFetcherHandler
from paper_scanner.tools.fetchers.fetcher_handlers.crossref_handler import (
    CrossrefMetadataFetcher,
)

__all__ = ["BaseFetcherHandler", "CrossrefMetadataFetcher"]
