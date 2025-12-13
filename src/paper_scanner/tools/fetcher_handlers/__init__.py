"""
Fetchers for retrieving bibliographic metadata from various sources.
"""

from paper_scanner.tools.fetcher_handlers.crossref_fetcher import (
    CrossrefReferenceFetcher,
    PoliteCrossrefClient,
    CROSSREF_EMAIL,
    CROSSREF_API_BASE,
)
from paper_scanner.tools.fetchers.fetcher_handlers.base import BaseFetcherHandler
from paper_scanner.tools.fetchers.fetcher_handlers.crossref_handler import (
    CrossrefMetadataFetcher,
)

__all__ = [
    'CrossrefReferenceFetcher',
    'PoliteCrossrefClient',
    'CROSSREF_EMAIL',
    'CROSSREF_API_BASE',
    'BaseFetcherHandler',
    'CrossrefMetadataFetcher',
]
