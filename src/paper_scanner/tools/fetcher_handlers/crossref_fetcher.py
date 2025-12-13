"""
Crossref API client for fetching reference metadata.

Provides classes for interacting with the Crossref REST API to fetch
bibliographic metadata for academic papers and their references.
"""

import json
import logging
import re
import time
from typing import Any, Dict, Optional
from pathlib import Path

import requests

from paper_scanner import __version__
from paper_scanner.tools.cache import JSONFileCache

logger = logging.getLogger(__name__)

# Crossref API configuration for fair use / polite pool
CROSSREF_EMAIL = "i.heitlager@tue.nl"
CROSSREF_APP_NAME = f"PhD - PaperScanner/{__version__}"
CROSSREF_API_BASE = "https://api.crossref.org/works"


class PoliteCrossrefClient:
    """
    Crossref client that follows etiquette guidelines and uses the polite pool.
    
    The polite pool provides significantly higher rate limits (50 req/sec vs 1 req/sec)
    when you include your email in the User-Agent header.
    
    See: https://github.com/CrossRef/rest-api-doc#etiquette
    """
    
    def __init__(self, email: str = CROSSREF_EMAIL, app_name: str = CROSSREF_APP_NAME, rate_limit: float = 50.0, 
                 cache_dir: Optional[Path] = None):
        """
        Initialize polite Crossref client.
        
        Args:
            email: Your email for polite pool access
            app_name: Your application name for User-Agent header
            rate_limit: Requests per second limit (default: 50)
            cache_dir: REQUIRED. Directory for caching API responses. Crossref cache goes in cache_dir/crossref/
        
        Raises:
            ValueError: If cache_dir is None
        """
        if cache_dir is None:
            raise ValueError("cache_dir is required for PoliteCrossrefClient. Crossref responses must be cached in $CACHE_DIR/crossref")
        
        self.session = requests.Session()
        
        # Ensure app_name has a version component
        if '/' not in app_name:
            app_name = f'{app_name}/1.0'
        
        # POLITE POOL: Include contact info in User-Agent
        # This gives us higher rate limits and better service
        self.session.headers.update({
            'User-Agent': f'{app_name} (mailto:{email})'
        })
        
        self.email = email
        self.base_url = CROSSREF_API_BASE
        self.rate_limit = rate_limit
        self.delay_between_requests = 1.0 / rate_limit  # Convert requests/sec to seconds
        
        # Set cache directory to cache_dir/crossref
        crossref_cache_dir = Path(cache_dir).expanduser() / "crossref"
        
        self.cache = JSONFileCache(crossref_cache_dir)
        self.last_cache_hit = False  # Track if last request was from cache

    def get_work(self, doi: str) -> Dict[str, Any]:
        """
        Get work metadata from Crossref.
        
        Args:
            doi: Digital Object Identifier (without https://doi.org/ prefix)
            
        Returns:
            JSON response from Crossref API
        """
        # Normalize DOI for cache consistency (lowercase, remove URL prefix)
        normalized_doi = doi.strip().lower()
        if normalized_doi.startswith('doi:'):
            normalized_doi = normalized_doi[4:]
        if normalized_doi.startswith('https://doi.org/'):
            normalized_doi = normalized_doi[16:]
        
        # Check cache first
        cached = self.cache.get(normalized_doi)
        if cached:
            self.last_cache_hit = True
            return cached
        
        self.last_cache_hit = False
        
        # Rate limiting: sleep before making the request
        time.sleep(self.delay_between_requests)
        
        url = f'{self.base_url}/{normalized_doi}'
        response = self.session.get(url)
        response.raise_for_status()
        data = response.json()
        
        # Save to cache with normalized DOI
        cache_saved = self.cache.set(normalized_doi, data)
        if not cache_saved:
            logger.warning(f"Failed to cache response for DOI {normalized_doi}")
        
        return data


class CrossrefReferenceFetcher:
    """Fetch references from Crossref API"""

    def __init__(self, email: str = CROSSREF_EMAIL, rate_limit_delay: float = 0.1, 
                 cache_dir: Optional[Path] = None):
        """
        Initialize Crossref fetcher

        Args:
            email: Email for Crossref API user-agent
            rate_limit_delay: Delay in seconds between API calls
            cache_dir: REQUIRED. Directory for caching API responses. Crossref cache goes in cache_dir/crossref/
        
        Raises:
            ValueError: If cache_dir is None
        """
        if cache_dir is None:
            raise ValueError("cache_dir is required for CrossrefReferenceFetcher. Crossref responses must be cached in $CACHE_DIR/crossref")
        
        self.email = email
        self.rate_limit_delay = rate_limit_delay
        self.api_base = CROSSREF_API_BASE
        self.verbose = False

        try:
            # Create a polite Crossref client for ALL operations
            # This handles both caching and rate limiting consistently
            # cache_dir is required and will be used as-is (not made optional)
            self.polite_client = PoliteCrossrefClient(email=email, rate_limit=1/rate_limit_delay,
                                                     cache_dir=cache_dir)
            
            # Use the polite client's cache and session for all operations
            self.cache = self.polite_client.cache
            self.session = self.polite_client.session
            
        except ImportError:
            logger.error("requests library not found. Install with: pip install requests")
            raise
    
    def fetch_references_for_doi(self, doi: str) -> Optional[Dict[str, Any]]:
        """
        Fetch references for a given DOI from Crossref

        Args:
            doi: Digital Object Identifier

        Returns:
            Dict with 'references' list, or None if fetch fails
        """
        try:
            # Clean DOI
            normalized_doi = doi.strip().lower()
            if normalized_doi.startswith('doi:'):
                normalized_doi = normalized_doi[4:]
            if normalized_doi.startswith('https://doi.org/'):
                normalized_doi = normalized_doi[16:]

            # Check cache first (use normalized DOI)
            cached = self.cache.get(normalized_doi)
            if cached:
                return cached

            # Use the polite client to fetch the work
            # This ensures consistent caching and rate limiting
            work_data = self.polite_client.get_work(normalized_doi)
            
            if not work_data or "message" not in work_data:
                logger.debug(f"No message in Crossref response for {normalized_doi}")
                return None

            message = work_data["message"]
            references = message.get('reference', [])

            result = {
                'doi': normalized_doi,
                'title': message.get('title', [''])[0] if isinstance(message.get('title'), list) else message.get('title', ''),
                'year': self._extract_year(message),
                'references': references,
                'reference_count': len(references),
                'fetched_at': time.time()
            }
            
            # Save to cache with normalized DOI
            self.cache.set(normalized_doi, result)
            
            return result

        except Exception as e:
            logger.warning(f"Error fetching references for DOI {doi}: {e}")
            return None

    def _extract_year(self, work: Dict[str, Any]) -> Optional[int]:
        """Extract publication year from Crossref work"""
        try:
            if 'published-print' in work:
                date_parts = work['published-print'].get('date-parts', [[]])[0]
                if date_parts:
                    return int(date_parts[0])
            elif 'published-online' in work:
                date_parts = work['published-online'].get('date-parts', [[]])[0]
                if date_parts:
                    return int(date_parts[0])
        except (ValueError, IndexError, TypeError):
            pass
        return None

    def parse_reference(self, ref: Dict[str, Any], source_paper_id: int) -> Dict[str, Any]:
        """
        Parse a Crossref reference into a structured format

        Args:
            ref: Reference from Crossref API
            source_paper_id: ID of the paper this reference comes from

        Returns:
            Dict with parsed reference data
        """
        # Handle case where ref is not a dictionary
        if not isinstance(ref, dict):
            logger.warning(f"Reference is not a dict, got {type(ref)}: {ref}")
            return {}
        
        # Log the first reference for debugging (only in verbose mode)
        if self.verbose and source_paper_id > 0:  # Just log once per paper
            logger.debug(f"Sample reference keys: {list(ref.keys())}")
        
        # Extract authors
        authors = []
        for author in ref.get('author', []):
            if isinstance(author, dict):
                author_obj = {
                    'last_name': author.get('family', ''),
                    'first_name': author.get('given', ''),
                    'initials': self._extract_initials(author.get('given', ''))
                }
                if author_obj['last_name']:
                    authors.append(author_obj)

        # Parse year
        year = None
        if 'year' in ref:
            try:
                year = int(ref['year'])
            except (ValueError, TypeError):
                pass

        # Extract pages
        pages_range = None
        if 'first-page' in ref and 'last-page' in ref:
            pages_range = f"{ref['first-page']}-{ref['last-page']}"
        elif 'article-number' in ref:
            pages_range = ref['article-number']

        return {
            'source_paper_id': source_paper_id,
            'title': ref.get('title') or ref.get('article-title') or ref.get('volume-title') or ref.get('unstructured', ''),
            'year': year,
            'authors': authors,
            'authors_json': json.dumps(authors) if authors else None,
            'citekey': ref.get('key', ''),
            'reference_type': ref.get('type', 'unknown'),
            'paper_type': ref.get('type', 'unknown'),  # Store paper type from Crossref
            'doi': ref.get('DOI', '').lower() if ref.get('DOI') else None,
            'url': ref.get('URL'),
            'volume': ref.get('volume'),
            'issue': ref.get('issue'),
            'pages_range': pages_range,
            'journal': ref.get('journal-title'),
            'publisher': ref.get('publisher'),
            'abstract': ref.get('abstract'),
            'arxiv_id': self._extract_arxiv(ref.get('URL', '')),
            'raw_citation': json.dumps(ref),
        }

    def _extract_initials(self, given_name: str) -> str:
        """Extract initials from given name"""
        if not given_name:
            return ''
        return ''.join(c for c in given_name if c.isupper())

    def _extract_arxiv(self, url: str) -> Optional[str]:
        """Extract arXiv ID from URL if present"""
        if not url:
            return None
        match = re.search(r'arxiv\.org/abs/(\d+\.\d+)', url, re.IGNORECASE)
        return match.group(1) if match else None
    
    def get_crossref_work_for_doi(self, doi: str) -> Optional[Dict[str, Any]]:
        """
        Fetch full work metadata from Crossref for a DOI
        Uses the polite client with caching for efficient lookups
        
        Args:
            doi: Digital Object Identifier
            
        Returns:
            Crossref work data or None if not found
        """
        try:
            # Use the polite client which handles caching and rate limiting
            result = self.polite_client.get_work(doi)
            
            # Extract the work data from the API response
            if result and result.get('status') == 'ok' and 'message' in result:
                return result['message']
            return None
        except Exception as e:
            # Silently handle 404s and other HTTP errors - just skip those references
            error_str = str(e)
            if '404' not in error_str:
                logger.debug(f"Could not fetch work metadata from Crossref for {doi}: {e}")
            return None
    
    def parse_crossref_work(self, work: Dict[str, Any], source_paper_id: int) -> Dict[str, Any]:
        """
        Parse a Crossref work into our reference format
        
        Args:
            work: Crossref work data
            source_paper_id: ID of the source paper
            
        Returns:
            Parsed reference dictionary
        """
        # Extract authors
        authors = []
        for author in work.get('author', []):
            if isinstance(author, dict):
                author_obj = {
                    'last_name': author.get('family', ''),
                    'first_name': author.get('given', ''),
                    'initials': self._extract_initials(author.get('given', ''))
                }
                if author_obj['last_name']:
                    authors.append(author_obj)
        
        # Parse year
        year = self._extract_year(work)
        
        # Extract pages
        pages_range = None
        if 'first-page' in work and 'last-page' in work:
            pages_range = f"{work['first-page']}-{work['last-page']}"
        elif 'article-number' in work:
            pages_range = work['article-number']
        
        # Get title
        title = ''
        if isinstance(work.get('title'), list) and work['title']:
            title = work['title'][0]
        elif isinstance(work.get('title'), str):
            title = work['title']
        
        # Get journal title safely
        journal = None
        if isinstance(work.get('container-title'), list):
            container_titles = work.get('container-title', [])
            journal = container_titles[0] if container_titles else None
        else:
            journal = work.get('container-title')
        
        return {
            'source_paper_id': source_paper_id,
            'title': title,
            'year': year,
            'authors': authors,
            'authors_json': json.dumps(authors) if authors else None,
            'citekey': work.get('URL', ''),
            'reference_type': work.get('type', 'article'),
            'paper_type': work.get('type', 'article'),  # Store paper type from Crossref
            'doi': work.get('DOI', '').lower() if work.get('DOI') else None,
            'url': work.get('URL'),
            'volume': work.get('volume'),
            'issue': work.get('issue'),
            'pages_range': pages_range,
            'journal': journal,
            'publisher': work.get('publisher'),
            'arxiv_id': self._extract_arxiv(work.get('URL', '')),
            'raw_citation': json.dumps(work),
        }
