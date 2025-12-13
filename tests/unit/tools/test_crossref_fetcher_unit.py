#!/usr/bin/env python3
"""
Unit tests for Crossref fetcher module.

Tests the PoliteCrossrefClient and CrossrefReferenceFetcher classes
with mocked HTTP requests and database interactions.
"""

import json
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

import pytest

from paper_scanner.tools.fetcher_handlers.crossref_fetcher import (
    PoliteCrossrefClient,
    CrossrefReferenceFetcher,
    CROSSREF_EMAIL,
    CROSSREF_API_BASE,
)


class TestPoliteCrossrefClient:
    """Test suite for PoliteCrossrefClient class."""

    @pytest.fixture
    def temp_cache_dir(self, tmp_path):
        """Create a temporary cache directory."""
        return tmp_path / "cache"

    @pytest.fixture
    def client(self, temp_cache_dir):
        """Create a client instance with temporary cache."""
        return PoliteCrossrefClient(
            email="test@example.com",
            app_name="TestApp",
            rate_limit=100.0,
            cache_dir=temp_cache_dir
        )

    def test_initialization(self, client):
        """Test client initialization."""
        assert client.email == "test@example.com"
        assert client.rate_limit == 100.0
        assert client.delay_between_requests == 0.01  # 1/100
        assert client.base_url == CROSSREF_API_BASE
        assert client.cache is not None

    def test_user_agent_header(self, client):
        """Test that User-Agent header is set correctly."""
        user_agent = client.session.headers.get('User-Agent')
        assert user_agent is not None
        assert 'TestApp/1.0' in user_agent
        assert 'test@example.com' in user_agent

    @patch('paper_scanner.tools.fetchers.crossref_fetcher.requests.Session.get')
    def test_get_work_success(self, mock_get, client):
        """Test successful work retrieval."""
        mock_response = Mock()
        mock_response.json.return_value = {
            'status': 'ok',
            'message': {
                'DOI': '10.1234/test.2024.1234',
                'title': ['Test Paper'],
                'author': [{'family': 'Smith', 'given': 'John'}],
                'published-print': {'date-parts': [[2024]]}
            }
        }
        mock_get.return_value = mock_response

        result = client.get_work('10.1234/test.2024.1234')

        assert result is not None
        assert result['status'] == 'ok'
        assert 'message' in result

    @patch('paper_scanner.tools.fetchers.crossref_fetcher.requests.Session.get')
    def test_get_work_caching(self, mock_get, client):
        """Test that results are cached."""
        mock_response = Mock()
        mock_response.json.return_value = {'status': 'ok', 'message': {'DOI': '10.1234/test'}}
        mock_get.return_value = mock_response

        doi = '10.1234/test'
        
        # First call
        result1 = client.get_work(doi)
        assert mock_get.call_count == 1

        # Second call should use cache
        result2 = client.get_work(doi)
        assert mock_get.call_count == 1  # No additional call
        assert result1 == result2

    @patch('paper_scanner.tools.fetchers.crossref_fetcher.requests.Session.get')
    def test_get_work_http_error(self, mock_get, client):
        """Test handling of HTTP errors."""
        mock_get.side_effect = Exception("HTTP 404 Not Found")

        with pytest.raises(Exception):
            client.get_work('10.1234/nonexistent')

    def test_rate_limiting(self, client, tmp_path):
        """Test that rate limiting delay is calculated correctly."""
        assert client.delay_between_requests == 0.01
        
        client_slow = PoliteCrossrefClient(
            email="test@example.com",
            rate_limit=10.0,
            cache_dir=tmp_path
        )
        assert client_slow.delay_between_requests == 0.1


class TestCrossrefReferenceFetcher:
    """Test suite for CrossrefReferenceFetcher class."""

    @pytest.fixture
    def temp_cache_dir(self, tmp_path):
        """Create a temporary cache directory."""
        return tmp_path / "cache"

    @pytest.fixture
    def fetcher(self, temp_cache_dir):
        """Create a fetcher instance with temporary cache."""
        return CrossrefReferenceFetcher(
            email="test@example.com",
            rate_limit_delay=0.01,
            cache_dir=temp_cache_dir
        )

    def test_initialization(self, fetcher):
        """Test fetcher initialization."""
        assert fetcher.email == "test@example.com"
        assert fetcher.rate_limit_delay == 0.01
        assert fetcher.verbose is False
        assert fetcher.session is not None
        assert fetcher.polite_client is not None
        assert fetcher.cache is not None

    @patch('paper_scanner.tools.fetchers.crossref_fetcher.requests.Session.get')
    def test_fetch_references_success(self, mock_get, fetcher):
        """Test successful reference fetching."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'message': {
                'title': ['Test Paper'],
                'published-print': {'date-parts': [[2024]]},
                'reference': [
                    {
                        'key': 'ref1',
                        'title': 'Referenced Paper',
                        'year': 2023,
                        'author': [{'family': 'Doe', 'given': 'Jane'}]
                    }
                ]
            }
        }
        mock_get.return_value = mock_response

        result = fetcher.fetch_references_for_doi('10.1234/test.2024.1234')

        assert result is not None
        assert result['doi'] == '10.1234/test.2024.1234'
        assert result['title'] == 'Test Paper'
        assert result['year'] == 2024
        assert result['reference_count'] == 1

    @patch('paper_scanner.tools.fetchers.crossref_fetcher.requests.Session.get')
    def test_fetch_references_with_doi_variations(self, mock_get, fetcher):
        """Test that DOI variations are normalized."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'message': {
                'title': ['Test'],
                'reference': []
            }
        }
        mock_get.return_value = mock_response

        # Test different DOI formats
        dois = [
            '10.1234/test',
            'doi:10.1234/test',
            'https://doi.org/10.1234/test',
            '10.1234/TEST'  # uppercase
        ]

        for doi in dois:
            result = fetcher.fetch_references_for_doi(doi)
            assert result is not None
            assert result['doi'] == '10.1234/test'

    @patch('paper_scanner.tools.fetchers.crossref_fetcher.requests.Session.get')
    def test_fetch_references_http_error(self, mock_get, fetcher):
        """Test handling of HTTP errors."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        result = fetcher.fetch_references_for_doi('10.1234/nonexistent')

        assert result is None

    @patch('paper_scanner.tools.fetchers.crossref_fetcher.requests.Session.get')
    def test_fetch_references_invalid_response(self, mock_get, fetcher):
        """Test handling of invalid API responses."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}  # Missing 'message' key
        mock_get.return_value = mock_response

        result = fetcher.fetch_references_for_doi('10.1234/test')

        assert result is None

    def test_extract_year_from_published_print(self, fetcher):
        """Test year extraction from published-print."""
        work = {
            'published-print': {'date-parts': [[2024, 3, 15]]}
        }
        year = fetcher._extract_year(work)
        assert year == 2024

    def test_extract_year_from_published_online(self, fetcher):
        """Test year extraction from published-online."""
        work = {
            'published-online': {'date-parts': [[2023, 6, 1]]}
        }
        year = fetcher._extract_year(work)
        assert year == 2023

    def test_extract_year_missing(self, fetcher):
        """Test year extraction when no date info available."""
        work = {}
        year = fetcher._extract_year(work)
        assert year is None

    def test_extract_year_invalid_format(self, fetcher):
        """Test year extraction with invalid date format."""
        work = {
            'published-print': {'date-parts': [['invalid']]}
        }
        year = fetcher._extract_year(work)
        assert year is None

    def test_extract_initials(self, fetcher):
        """Test initials extraction from given names."""
        assert fetcher._extract_initials('John') == 'J'
        assert fetcher._extract_initials('John David') == 'JD'
        assert fetcher._extract_initials('john') == ''
        assert fetcher._extract_initials('') == ''

    def test_extract_arxiv_from_url(self, fetcher):
        """Test arXiv ID extraction."""
        url_with_arxiv = 'https://arxiv.org/abs/2401.12345'
        arxiv_id = fetcher._extract_arxiv(url_with_arxiv)
        assert arxiv_id == '2401.12345'

    def test_extract_arxiv_no_arxiv(self, fetcher):
        """Test arXiv extraction from non-arXiv URL."""
        url = 'https://example.com/paper.pdf'
        arxiv_id = fetcher._extract_arxiv(url)
        assert arxiv_id is None

    def test_extract_arxiv_empty_url(self, fetcher):
        """Test arXiv extraction from empty URL."""
        arxiv_id = fetcher._extract_arxiv('')
        assert arxiv_id is None

    def test_parse_reference_basic(self, fetcher):
        """Test basic reference parsing."""
        ref = {
            'title': 'Test Reference',
            'year': 2023,
            'author': [
                {'family': 'Smith', 'given': 'John'},
                {'family': 'Doe', 'given': 'Jane'}
            ],
            'DOI': '10.5678/ref.2023.1234',
            'journal-title': 'Test Journal',
            'volume': '10',
            'issue': '2',
            'first-page': '100',
            'last-page': '110'
        }

        parsed = fetcher.parse_reference(ref, source_paper_id=1)

        assert parsed['title'] == 'Test Reference'
        assert parsed['year'] == 2023
        assert parsed['doi'] == '10.5678/ref.2023.1234'
        assert parsed['journal'] == 'Test Journal'
        assert parsed['volume'] == '10'
        assert parsed['issue'] == '2'
        assert parsed['pages_range'] == '100-110'
        assert len(parsed['authors']) == 2

    def test_parse_reference_non_dict(self, fetcher):
        """Test parsing of non-dictionary reference."""
        parsed = fetcher.parse_reference("not a dict", source_paper_id=1)
        assert parsed == {}

    def test_parse_reference_missing_fields(self, fetcher):
        """Test parsing reference with missing fields."""
        ref = {'title': 'Minimal Ref'}
        parsed = fetcher.parse_reference(ref, source_paper_id=1)

        assert parsed['title'] == 'Minimal Ref'
        assert parsed['year'] is None
        assert parsed['authors'] == []
        assert parsed['doi'] is None

    def test_parse_reference_with_article_number(self, fetcher):
        """Test parsing reference with article-number instead of pages."""
        ref = {
            'title': 'Online Journal Article',
            'article-number': 'e12345'
        }
        parsed = fetcher.parse_reference(ref, source_paper_id=1)

        assert parsed['pages_range'] == 'e12345'

    def test_parse_crossref_work_full(self, fetcher):
        """Test parsing a full Crossref work."""
        work = {
            'title': ['Full Work Title'],
            'author': [
                {'family': 'Author', 'given': 'Primary'},
                {'family': 'Coauthor', 'given': 'Secondary'}
            ],
            'published-print': {'date-parts': [[2024]]},
            'DOI': '10.1234/main.2024.5678',
            'container-title': ['Main Journal'],
            'volume': '25',
            'issue': '4',
            'first-page': '200',
            'last-page': '210',
            'publisher': 'Test Publisher',
            'URL': 'https://example.com'
        }

        parsed = fetcher.parse_crossref_work(work, source_paper_id=1)

        assert parsed['title'] == 'Full Work Title'
        assert parsed['year'] == 2024
        assert len(parsed['authors']) == 2
        assert parsed['journal'] == 'Main Journal'
        assert parsed['pages_range'] == '200-210'
        assert parsed['publisher'] == 'Test Publisher'

    def test_parse_crossref_work_with_list_title(self, fetcher):
        """Test parsing work with title as list."""
        work = {
            'title': ['Title from List', 'Alternative Title'],
            'container-title': ['Journal One', 'Journal Two']
        }

        parsed = fetcher.parse_crossref_work(work, source_paper_id=1)

        assert parsed['title'] == 'Title from List'
        assert parsed['journal'] == 'Journal One'

    def test_parse_crossref_work_with_string_title(self, fetcher):
        """Test parsing work with title as string."""
        work = {
            'title': 'String Title',
            'container-title': 'String Journal'
        }

        parsed = fetcher.parse_crossref_work(work, source_paper_id=1)

        assert parsed['title'] == 'String Title'
        assert parsed['journal'] == 'String Journal'

    def test_parse_reference_authors_extraction(self, fetcher):
        """Test detailed author extraction."""
        ref = {
            'author': [
                {'family': 'Smith', 'given': 'John David'},
                {'family': 'Doe', 'given': 'Jane'},
                {'family': 'NoGiven'}  # No given name - still included
            ],
            'title': 'Test'
        }

        parsed = fetcher.parse_reference(ref, source_paper_id=1)

        assert len(parsed['authors']) == 3
        assert parsed['authors'][0]['last_name'] == 'Smith'
        assert parsed['authors'][0]['initials'] == 'JD'
        assert parsed['authors'][1]['last_name'] == 'Doe'
        assert parsed['authors'][1]['initials'] == 'J'
        assert parsed['authors'][2]['last_name'] == 'NoGiven'
        assert parsed['authors'][2]['initials'] == ''

    def test_parse_reference_json_serialization(self, fetcher):
        """Test that authors are properly JSON serialized."""
        ref = {
            'author': [{'family': 'Smith', 'given': 'John'}],
            'title': 'Test'
        }

        parsed = fetcher.parse_reference(ref, source_paper_id=1)

        authors_json = json.loads(parsed['authors_json'])
        assert isinstance(authors_json, list)
        assert authors_json[0]['last_name'] == 'Smith'

    @patch('paper_scanner.tools.fetchers.crossref_fetcher.requests.Session.get')
    def test_fetch_references_caching(self, mock_get, fetcher):
        """Test that fetched references are cached."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'message': {
                'title': ['Cached'],
                'reference': []
            }
        }
        mock_get.return_value = mock_response

        doi = '10.1234/cached'

        # First call
        result1 = fetcher.fetch_references_for_doi(doi)
        assert mock_get.call_count == 1

        # Second call should use cache
        result2 = fetcher.fetch_references_for_doi(doi)
        assert mock_get.call_count == 1  # No additional call
        assert result1 == result2


class TestCrossrefIntegration:
    """Integration tests for Crossref fetcher components."""

    @pytest.fixture
    def temp_cache_dir(self, tmp_path):
        """Create a temporary cache directory."""
        return tmp_path / "cache"

    def test_client_and_fetcher_share_cache(self, temp_cache_dir):
        """Test that client and fetcher can share cache directory."""
        client = PoliteCrossrefClient(email="test@example.com", cache_dir=temp_cache_dir)
        fetcher = CrossrefReferenceFetcher(cache_dir=temp_cache_dir)

        assert client.cache.cache_dir == fetcher.cache.cache_dir
        assert client.cache.cache_dir == temp_cache_dir / "crossref"

    @patch('paper_scanner.tools.fetchers.crossref_fetcher.requests.Session.get')
    def test_full_fetch_and_parse_flow(self, mock_get, tmp_path):
        """Test complete flow from fetch to parse."""
        # Mock the API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'message': {
                'title': ['Integration Test Paper'],
                'published-print': {'date-parts': [[2024]]},
                'author': [{'family': 'TestAuthor', 'given': 'Test'}],
                'reference': [
                    {
                        'key': 'ref1',
                        'title': 'Referenced Paper',
                        'year': 2023,
                        'DOI': '10.5678/ref'
                    }
                ]
            }
        }
        mock_get.return_value = mock_response

        fetcher = CrossrefReferenceFetcher(cache_dir=tmp_path)
        result = fetcher.fetch_references_for_doi('10.1234/test')

        assert result['title'] == 'Integration Test Paper'
        assert result['reference_count'] == 1

        # Parse the reference
        parsed_ref = fetcher.parse_reference(result['references'][0], source_paper_id=1)
        assert parsed_ref['title'] == 'Referenced Paper'
        assert parsed_ref['year'] == 2023
        assert parsed_ref['doi'] == '10.5678/ref'
