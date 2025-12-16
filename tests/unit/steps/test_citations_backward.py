"""
Tests for the citations step

Tests backward citations extraction, resolution, and database updates
"""

import pytest
from unittest.mock import MagicMock, patch, Mock
from datetime import datetime, timezone
from pathlib import Path

from paper_scanner.steps.citations import CitationsStep
from paper_scanner.core.database import PapersDatabase
from paper_scanner.core.models import Paper, Citation, Discovery, DiscoveryMethod, Author
from paper_scanner.core.enum import PaperType


class TestValidate:
    """Test CitationsStep.validate() static method"""

    def test_validate_valid_config_defaults(self):
        """Test validation of minimal valid configuration"""
        config = {
            "backward": {
                "source": ["crossref"]
            }
        }
        
        is_valid, errors = CitationsStep.validate(config)
        
        assert is_valid is True
        assert len(errors) == 0

    def test_validate_valid_config_with_paper_types(self):
        """Test validation with explicit paper-types"""
        config = {
            "paper-types": ["journal_article", "conference_paper"],
            "backward": {
                "source": ["crossref"],
                "continue_on_not_found": True
            }
        }
        
        is_valid, errors = CitationsStep.validate(config)
        
        assert is_valid is True
        assert len(errors) == 0

    def test_validate_invalid_paper_type(self):
        """Test validation fails with invalid paper_type"""
        config = {
            "paper-type": ["invalid_type"],
            "backward": {
                "source": ["crossref"]
            }
        }
        
        is_valid, errors = CitationsStep.validate(config)
        
        assert is_valid is False
        assert any("not a valid PaperType" in err for err in errors)

    def test_validate_paper_types_not_list(self):
        """Test validation fails when paper-types is not a list"""
        config = {
            "paper-type": "journal_article",
            "backward": {
                "source": "crossref"
            }
        }
        
        is_valid, errors = CitationsStep.validate(config)
        
        assert is_valid is False
        assert any("'paper-types' must be a list" in err for err in errors)

    def test_validate_backward_not_dict(self):
        """Test validation fails when backward is not a dict"""
        config = {
            "backward": "crossref"
        }
        
        is_valid, errors = CitationsStep.validate(config)
        
        assert is_valid is False
        assert any("'backward' must be a dictionary" in err for err in errors)

    def test_validate_backward_source_not_string(self):
        """Test validation fails when backward.source is not string"""
        config = {
            "backward": {
                "source": 123
            }
        }
        
        is_valid, errors = CitationsStep.validate(config)
        
        assert is_valid is False
        assert any("'backward.source' must be a string" in err for err in errors)

    def test_validate_continue_on_not_found_not_bool(self):
        """Test validation fails when continue_on_not_found is not bool"""
        config = {
            "backward": {
                "continue_on_not_found": "true"
            }
        }
        
        is_valid, errors = CitationsStep.validate(config)
        
        assert is_valid is False
        assert any("'backward.continue_on_not_found' must be a boolean" in err for err in errors)

    def test_validate_paper_type_hyphen_key(self):
        """Test validation accepts paper-type (hyphenated) as alias for paper-types"""
        config = {
            "paper-type": ["journal_article"],
            "backward": {
                "source": "crossref"
            }
        }
        
        is_valid, errors = CitationsStep.validate(config)
        
        assert is_valid is True
        assert len(errors) == 0

    def test_validate_source_as_list(self):
        """Test validation accepts source as a list of fetcher names"""
        config = {
            "backward": {
                "source": ["crossref", "openalex"]
            }
        }
        
        is_valid, errors = CitationsStep.validate(config)
        
        assert is_valid is True
        assert len(errors) == 0

    def test_validate_source_list_with_invalid_item(self):
        """Test validation fails when source list contains non-string items"""
        config = {
            "backward": {
                "source": ["crossref", 123]
            }
        }
        
        is_valid, errors = CitationsStep.validate(config)
        
        assert is_valid is False
        assert any("items must be strings" in err for err in errors)


class TestExecute:
    """Test CitationsStep.execute() method"""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database"""
        db = MagicMock(spec=PapersDatabase)
        db.all.return_value = []
        db.update = MagicMock()
        db.save = MagicMock()
        return db

    @pytest.fixture
    def step(self, tmp_path, mock_db):
        """Create a CitationsStep instance with mock database"""
        general_config = {}
        step = CitationsStep(general_config=general_config, db=mock_db, cache_dir=tmp_path)
        return step

    def test_execute_with_no_papers(self, step):
        """Test execution when no papers in database"""
        config = {
            "paper-types": ["journal_article"],
            "backward": {
                "source": ["crossref"],
                "continue_on_not_found": True
            }
        }
        
        results = step.execute(config, verbose=False, dry_run=True)
        
        assert results["total_papers"] == 0
        assert results["target_papers"] == 0
        assert results["citations_fetched"] == 0

    @patch("paper_scanner.steps.citations.Fetcher.fetch_citations")
    def test_execute_with_papers_no_citations(self, mock_fetch_citations, step):
        """Test execution when papers have no citations"""
        # Setup mock database with papers
        paper1 = Paper(
            cite_key="test2020",
            title="Test Paper",
            doi="10.1234/test1",
            year=2020,
            paper_type=PaperType.JOURNAL_ARTICLE,
            discovery=Discovery(method=DiscoveryMethod.KEYWORD_SEARCH, iteration=0)
        )
        step.db.all.return_value = [paper1]

        # Mock only the fetch_citations method
        mock_fetch_citations.return_value = ([], False)

        config = {
            "paper-types": ["journal_article"],
            "backward": {
                "source": ["crossref"],
                "continue_on_not_found": True
            }
        }
        
        results = step.execute(config, verbose=False, dry_run=True)
        
        assert results["total_papers"] == 1
        assert results["target_papers"] == 1
        assert results["citations_fetched"] == 0

    @patch("paper_scanner.steps.citations.Fetcher.fetch_citations")
    def test_execute_with_citations(self, mock_fetch_citations, step):
        """Test execution with actual citations"""
        # Setup mock database with paper
        citing_paper = Paper(
            cite_key="citing2020",
            title="Citing Paper",
            doi="10.1234/citing",
            year=2020,
            paper_type=PaperType.JOURNAL_ARTICLE,
            discovery=Discovery(method=DiscoveryMethod.KEYWORD_SEARCH, iteration=0)
        )
        
        # Setup mock citations
        citation1 = Citation(
            doi="10.1234/cited1",
            title="Cited Paper 1",
            year=2019,
            extraction_method="crossref",
            confidence=0.95
        )
        citation2 = Citation(
            title="Cited Paper 2",
            year=2018,
            extraction_method="crossref",
            confidence=0.75
        )

        # Mock fetch_citations to return citations
        mock_fetcher = MagicMock()
        mock_fetcher.fetch_citations.return_value = ([citation1, citation2], False)
        
        # Mock db.all() to return citing_paper for both calls (initial filter and resolve pass)
        step.db.all.side_effect = [[citing_paper], [citing_paper]]
        
        # Mock get_by_doi to return None (citations not found in DB)
        step.db.get_by_doi.return_value = []
        
        # Patch Fetcher initialization
        with patch("paper_scanner.steps.citations.Fetcher", return_value=mock_fetcher):
            config = {
                "paper-types": ["journal_article"],
                "backward": {
                    "source": ["crossref"],
                    "continue_on_not_found": False
                }
            }
            
            results = step.execute(config, verbose=False, dry_run=True, debug=False)
            
            assert results["total_papers"] == 1
            assert results["target_papers"] == 1
            assert results["citations_fetched"] == 2
            assert results["papers_with_citations"] == 1
            assert results["citations_unresolved"] == 2  # Not found, continue_on_not_found=False

    # @patch("paper_scanner.steps.citations.Fetcher.fetch_citations")
    # def test_execute_cache_hit_tracking(self, mock_fetch_citations, step):
    #     """Test cache hit/miss tracking"""
    #     paper = Paper(
    #         cite_key="test2020",
    #         title="Test Paper",
    #         doi="10.1234/test",
    #         year=2020,
    #         paper_type=PaperType.JOURNAL_ARTICLE,
    #         discovery=Discovery(method=DiscoveryMethod.KEYWORD_SEARCH, iteration=0)
    #     )
    #     step.db.all.return_value = [paper]

    #     citation = Citation(
    #         doi="10.1234/cited",
    #         title="Cited",
    #         extraction_method="crossref",
    #         confidence=0.9
    #     )

    #     # Mock fetch_citations to return cache hits/misses in sequence
    #     mock_fetch_citations.side_effect = [
    #         ([citation], True),   # First call: cache hit
    #         ([citation], False),  # Second call: cache miss
    #     ]

    #     config = {
    #         "paper-types": ["journal_article"],
    #         "backward": {"source": ["crossref"]}
    #     }
        
    #     # First execution
    #     results1 = step.execute(config, verbose=False, dry_run=True)
    #     assert results1["cache_hits"] == 1
    #     assert results1["cache_misses"] == 0

    #     # Reset for second execution
    #     step.db.all.return_value = [paper]
    #     results2 = step.execute(config, verbose=False, dry_run=True)
    #     assert results2["cache_hits"] == 0
    #     assert results2["cache_misses"] == 1


class TestFetchCitationsForPapers:
    """Test CitationsStep._fetch_citations_for_papers() method"""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database"""
        db = MagicMock(spec=PapersDatabase)
        db.all.return_value = []
        db.update = MagicMock()
        return db

    @pytest.fixture
    def step(self, tmp_path, mock_db):
        """Create a CitationsStep instance"""
        general_config = {}
        step = CitationsStep(general_config=general_config, db=mock_db, cache_dir=tmp_path)
        return step

    @patch("paper_scanner.steps.citations.Fetcher.fetch_citations")
    def test_fetch_citations_stores_in_papers(self, mock_fetch_citations, step):
        """Test that fetched citations are stored in papers"""
        paper = Paper(
            cite_key="test2020",
            title="Test Paper",
            doi="10.1234/test",
            year=2020,
            paper_type=PaperType.JOURNAL_ARTICLE,
            discovery=Discovery(method=DiscoveryMethod.KEYWORD_SEARCH, iteration=0)
        )

        citation = Citation(
            doi="10.1234/cited",
            title="Cited Paper",
            extraction_method="crossref",
            confidence=0.9
        )

        mock_fetch_citations.return_value = ([citation], False)
        
        mock_fetcher = MagicMock()
        mock_fetcher.fetch_citations.return_value = ([citation], False)
        
        results = {
            "citations_fetched": 0,
            "papers_with_citations": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "errors": []
        }

        step._fetch_citations_for_papers(
            target_papers=[paper],
            fetcher=mock_fetcher,
            results=results,
            verbose=False
        )

        assert len(paper.citations) == 1
        assert paper.citations[0].doi == "10.1234/cited"
        assert results["citations_fetched"] == 1
        assert results["cache_misses"] == 1

    @patch("paper_scanner.steps.citations.Fetcher.fetch_citations")
    def test_fetch_citations_empty_results(self, mock_fetch_citations, step):
        """Test handling of papers with no citations"""
        paper = Paper(
            cite_key="test2020",
            title="Test Paper",
            doi="10.1234/test",
            year=2020,
            paper_type=PaperType.JOURNAL_ARTICLE
        )

        mock_fetch_citations.return_value = ([], False)
        
        mock_fetcher = MagicMock()
        mock_fetcher.fetch_citations.return_value = ([], False)
        
        results = {
            "citations_fetched": 0,
            "papers_with_citations": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "errors": []
        }

        step._fetch_citations_for_papers(
            target_papers=[paper],
            fetcher=mock_fetcher,
            results=results,
            verbose=False
        )

        assert len(paper.citations) == 0
        assert results["citations_fetched"] == 0
        assert results["papers_with_citations"] == 0

    @patch("paper_scanner.steps.citations.Fetcher.fetch_citations")
    def test_fetch_citations_cache_tracking(self, mock_fetch_citations, step):
        """Test cache hit/miss tracking"""
        paper = Paper(
            cite_key="test2020",
            title="Test Paper",
            doi="10.1234/test",
            year=2020,
            paper_type=PaperType.JOURNAL_ARTICLE
        )

        citation = Citation(
            doi="10.1234/cited",
            title="Cited",
            extraction_method="crossref"
        )

        mock_fetch_citations.return_value = ([citation], True)  # Cache hit
        
        mock_fetcher = MagicMock()
        mock_fetcher.fetch_citations.return_value = ([citation], True)
        
        results = {
            "citations_fetched": 0,
            "papers_with_citations": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "errors": []
        }

        step._fetch_citations_for_papers(
            target_papers=[paper],
            fetcher=mock_fetcher,
            results=results,
            verbose=False
        )

        assert results["cache_hits"] == 1
        assert results["cache_misses"] == 0


class TestResolveAndCreateCitations:
    """Test CitationsStep._resolve_and_create_citations() method"""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database"""
        db = MagicMock(spec=PapersDatabase)
        db.all.return_value = []
        db.update = MagicMock()
        db.add = MagicMock()
        return db

    @pytest.fixture
    def step(self, tmp_path, mock_db):
        """Create a CitationsStep instance"""
        general_config = {}
        step = CitationsStep(general_config=general_config, db=mock_db, cache_dir=tmp_path)
        return step

    def test_resolve_citations_calls_link_citation(self, step):
        """Test that resolve_and_create_citations calls _link_citation"""
        citing_paper = Paper(
            cite_key="citing2020",
            title="Citing Paper",
            doi="10.1234/citing",
            year=2020,
            discovery=Discovery(method=DiscoveryMethod.KEYWORD_SEARCH, iteration=0)
        )

        citation = Citation(
            doi="10.1234/cited",
            title="Cited Paper",
            extraction_method="crossref"
        )

        citing_paper.citations = [citation]

        # Mock _link_citation
        step._link_citation = MagicMock(return_value=("paper_id", False))

        results = {
            "citations_resolved": 0,
            "citations_created_new_paper": 0,
            "citations_unresolved": 0,
            "errors": []
        }

        step._resolve_and_create_citations(
            papers=[citing_paper],
            continue_on_not_found=False,
            dry_run=True,
            results=results
        )

        assert step._link_citation.called
        assert results["citations_resolved"] == 1

    def test_resolve_citations_updates_database(self, step):
        """Test that papers are updated in database"""
        citing_paper = Paper(
            cite_key="citing2020",
            title="Citing Paper",
            doi="10.1234/citing",
            year=2020
        )

        citation = Citation(
            doi="10.1234/cited",
            title="Cited Paper",
            extraction_method="crossref"
        )

        citing_paper.citations = [citation]

        step._link_citation = MagicMock(return_value=("paper_id", False))

        results = {
            "citations_resolved": 0,
            "citations_created_new_paper": 0,
            "citations_unresolved": 0,
            "errors": []
        }

        step._resolve_and_create_citations(
            papers=[citing_paper],
            continue_on_not_found=False,
            dry_run=False,
            results=results
        )

        step.db.update.assert_called_with(citing_paper)


class TestLinkCitation:
    """Test CitationsStep._link_citation() method"""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database"""
        db = MagicMock(spec=PapersDatabase)
        db.update = MagicMock()
        db.save = MagicMock()
        db.add = MagicMock()
        return db

    @pytest.fixture
    def step(self, tmp_path, mock_db):
        """Create a CitationsStep instance"""
        general_config = {}
        step = CitationsStep(general_config=general_config, db=mock_db, cache_dir=tmp_path)
        return step

    def test_link_citation_by_doi_existing_paper(self, step):
        """Test linking citation by DOI to existing paper"""
        # Setup existing paper
        existing_paper = Paper(
            cite_key="existing2020",
            title="Existing Paper",
            doi="10.1234/existing",
            year=2020,
            paper_type=PaperType.JOURNAL_ARTICLE
        )

        # Setup citation
        citation = Citation(
            doi="10.1234/existing",
            title="Cited Paper",
            extraction_method="crossref"
        )

        # Setup citing paper
        citing_paper = Paper(
            cite_key="citing2020",
            title="Citing Paper",
            doi="10.1234/citing",
            year=2020,
            discovery=Discovery(method=DiscoveryMethod.KEYWORD_SEARCH, iteration=0)
        )

        # Mock database DOI lookup
        step.db.get_by_doi.return_value = [existing_paper]

        resolved_id, created_new = step._link_citation(
            citation,
            citing_paper,
            continue_on_not_found=False,
            dry_run=True
        )

        assert resolved_id == existing_paper.id
        assert created_new is False
        assert citing_paper.id in existing_paper.cited_by

    def test_link_citation_not_found_continue_false(self, step):
        """Test linking unresolved citation with continue_on_not_found=False"""
        citation = Citation(
            title="Unknown Paper",
            extraction_method="crossref"
        )

        citing_paper = Paper(
            cite_key="citing2020",
            title="Citing Paper",
            doi="10.1234/citing",
            year=2020
        )

        # Mock database lookups to return no results
        step.db.get_by_doi.return_value = []
        step.db.all.return_value = []

        resolved_id, created_new = step._link_citation(
            citation,
            citing_paper,
            continue_on_not_found=False,
            dry_run=True
        )

        assert resolved_id is None
        assert created_new is False

    def test_link_citation_not_found_create_new(self, step):
        """Test creating new paper for unresolved citation"""
        citation = Citation(
            doi="10.1234/new",
            title="New Paper from Citation",
            year=2019,
            extraction_method="crossref"
        )

        citing_paper = Paper(
            cite_key="citing2020",
            title="Citing Paper",
            doi="10.1234/citing",
            year=2020,
            discovery=Discovery(method=DiscoveryMethod.KEYWORD_SEARCH, iteration=0)
        )

        # Mock database lookups to return no results
        step.db.get_by_doi.return_value = []
        step.db.add = MagicMock()

        resolved_id, created_new = step._link_citation(
            citation,
            citing_paper,
            continue_on_not_found=True,
            dry_run=False
        )

        assert resolved_id is not None
        assert created_new is True
        step.db.add.assert_called_once()

    def test_link_citation_follow_duplicate_chain(self, step):
        """Test following duplicate_of chain to canonical paper"""
        # Setup duplicate papers chain
        canonical_paper = Paper(
            cite_key="canonical2020",
            title="Canonical Paper",
            doi="10.1234/canonical",
            year=2020
        )
        duplicate_paper = Paper(
            cite_key="duplicate2020",
            title="Duplicate Paper",
            doi="10.1234/dup",
            year=2020,
            duplicate_of=canonical_paper
        )

        citation = Citation(
            doi="10.1234/dup",
            title="Some Paper",
            extraction_method="crossref"
        )

        citing_paper = Paper(
            cite_key="citing2020",
            title="Citing Paper",
            doi="10.1234/citing",
            year=2020
        )

        # Mock database to return duplicate paper
        step.db.get_by_doi.return_value = [duplicate_paper]

        resolved_id, created_new = step._link_citation(
            citation,
            citing_paper,
            continue_on_not_found=False,
            dry_run=True
        )

        # Should resolve to canonical paper, not duplicate
        assert resolved_id == canonical_paper.id
        assert created_new is False

    def test_link_citation_iteration_tracking(self, step):
        """Test iteration tracking for created papers"""
        citation = Citation(
            title="New Citation",
            extraction_method="crossref"
        )

        # Citing paper at iteration 1
        citing_paper = Paper(
            cite_key="citing2020",
            title="Citing Paper",
            doi="10.1234/citing",
            year=2020,
            discovery=Discovery(method=DiscoveryMethod.KEYWORD_SEARCH, iteration=1)
        )

        # Mock database lookups to return no results
        step.db.get_by_doi.return_value = []
        step.db.all.return_value = []

        resolved_id, created_new = step._link_citation(
            citation,
            citing_paper,
            continue_on_not_found=True,
            dry_run=False
        )

        # Verify add was called
        step.db.add.assert_called_once()
        saved_paper = step.db.add.call_args[0][0]

        # New paper should be at iteration 2
        assert saved_paper.discovery.iteration == 2

if __name__ == "__main__":
    pytest.main([__file__, "-v"])