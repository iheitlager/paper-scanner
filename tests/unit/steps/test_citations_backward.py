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
                "sources": ["crossref"]
            }
        }
        
        is_valid, errors = CitationsStep.validate(config)
        
        assert is_valid is True
        assert len(errors) == 0

    def test_validate_valid_config_with_paper_types(self):
        """Test validation with explicit paper-types"""
        config = {
            "paper-type": ["journal_article", "conference_paper"],
            "backward": {
                "sources": ["crossref"],
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
                "sources": ["crossref"]
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
                "sources": "crossref"
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

    def test_validate_backward_sources_not_string_or_list(self):
        """Test validation fails when backward.sources is not string or list"""
        config = {
            "backward": {
                "citations": 123
            }
        }
        
        is_valid, errors = CitationsStep.validate(config)
        
        assert is_valid is False
        assert any("'backward.citations' must be a string or list" in err for err in errors)

    def test_validate_continue_on_not_found_not_bool(self):
        """Test validation fails when continue_on_not_found is not bool"""
        config = {
            "backward": {
                "citations": ["crossref"],
                "continue_on_not_found": "true"
            }
        }
        
        is_valid, errors = CitationsStep.validate(config)
        
        assert is_valid is False
        assert any("'backward.continue_on_not_found' must be a boolean" in err for err in errors)

    def test_validate_sources_as_string(self):
        """Test validation accepts sources as a string"""
        config = {
            "backward": {
                "citations": "crossref"
            }
        }
        
        is_valid, errors = CitationsStep.validate(config)
        
        assert is_valid is True
        assert len(errors) == 0

    def test_validate_sources_as_list(self):
        """Test validation accepts sources as a list of fetcher names"""
        config = {
            "backward": {
                "sources": ["crossref", "openalex"]
            }
        }
        
        is_valid, errors = CitationsStep.validate(config)
        
        assert is_valid is True
        assert len(errors) == 0

    def test_validate_sources_list_with_invalid_item(self):
        """Test validation fails when sources list contains non-string items"""
        config = {
            "backward": {
                "citations": ["crossref", 123]
            }
        }
        
        is_valid, errors = CitationsStep.validate(config)
        
        assert is_valid is False
        assert any("items must be strings" in err for err in errors)


class TestFetchCitationsForPapers:
    """Test CitationsStep._fetch_citations_for_papers() method - PASS 1"""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database"""
        db = MagicMock(spec=PapersDatabase)
        return db

    @pytest.fixture
    def step(self, tmp_path, mock_db):
        """Create a CitationsStep instance"""
        step = CitationsStep(general_config={}, db=mock_db, cache_dir=tmp_path)
        # Initialize attributes used by the step
        step.verbose = False
        step.debug = False
        step.output_errors = None
        return step

    @patch("paper_scanner.steps.citations.Fetcher")
    def test_fetch_citations_for_paper_with_doi(self, mock_fetcher_class, step):
        """Test fetching citations for paper with DOI"""
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

        mock_fetcher = MagicMock()
        mock_fetcher.fetch_citations.return_value = ([citation], False)
        mock_fetcher_class.return_value = mock_fetcher

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
        )

        assert len(paper.citations) == 1
        assert paper.citations[0].doi == "10.1234/cited"
        assert results["citations_fetched"] == 1
        assert results["cache_misses"] == 1

    @patch("paper_scanner.steps.citations.Fetcher")
    def test_fetch_citations_no_citations_found(self, mock_fetcher_class, step):
        """Test handling of papers with no citations"""
        paper = Paper(
            cite_key="test2020",
            title="Test Paper",
            doi="10.1234/test",
            year=2020,
            paper_type=PaperType.JOURNAL_ARTICLE
        )

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
        )

        assert len(paper.citations) == 0
        assert results["citations_fetched"] == 0
        assert results["papers_with_citations"] == 0

    @patch("paper_scanner.steps.citations.Fetcher")
    def test_fetch_citations_cache_hit(self, mock_fetcher_class, step):
        """Test cache hit tracking"""
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

        mock_fetcher = MagicMock()
        mock_fetcher.fetch_citations.return_value = ([citation], True)  # Cache hit

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
        )

        assert results["cache_hits"] == 1
        assert results["cache_misses"] == 0

    def test_fetch_citations_paper_without_doi(self, step):
        """Test skipping papers without DOI"""
        paper = Paper(
            cite_key="test2020",
            title="Test Paper",
            year=2020,
            paper_type=PaperType.JOURNAL_ARTICLE
        )

        mock_fetcher = MagicMock()

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
        )

        mock_fetcher.fetch_citations.assert_not_called()
        assert results["citations_fetched"] == 0


class TestResolveCitationsAndFetchPapers:
    """Test CitationsStep._resolve_citations_and_fetch_papers() method - PASS 2"""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database"""
        db = MagicMock(spec=PapersDatabase)
        db.get_by_doi.return_value = []
        db.add = MagicMock()
        return db

    @pytest.fixture
    def step(self, tmp_path, mock_db):
        """Create a CitationsStep instance"""
        step = CitationsStep(general_config={}, db=mock_db, cache_dir=tmp_path)
        # Initialize attributes used by the step
        step.verbose = False
        step.debug = False
        step.output_errors = None
        return step

    @patch("paper_scanner.steps.citations.Fetcher")
    def test_resolve_citations_by_doi_existing_paper(self, mock_fetcher_class, step):
        """Test resolving citation by DOI to existing paper"""
        existing_paper = Paper(
            cite_key="existing2020",
            title="Existing Paper",
            doi="10.1234/existing",
            year=2020,
            paper_type=PaperType.JOURNAL_ARTICLE
        )

        citing_paper = Paper(
            cite_key="citing2020",
            title="Citing Paper",
            doi="10.1234/citing",
            year=2020,
            paper_type=PaperType.JOURNAL_ARTICLE,
            discovery=Discovery(method=DiscoveryMethod.KEYWORD_SEARCH, iteration=0)
        )

        citation = Citation(
            doi="10.1234/existing",
            title="Cited Paper",
            extraction_method="crossref"
        )
        citing_paper.citations = [citation]

        step.db.get_by_doi.return_value = [existing_paper]

        mock_fetcher = MagicMock()

        results = {
            "citations_resolved": 0,
            "citations_created_new_paper": 0,
            "citations_unresolved": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "errors": []
        }

        step._resolve_citations_and_fetch_papers(
            papers=[citing_paper],
            fetcher=mock_fetcher,
            continue_on_not_found=False,
            results=results
        )

        assert citation.resolved_paper == existing_paper
        assert results["citations_resolved"] == 1
        assert results["citations_created_new_paper"] == 0

    @patch("paper_scanner.steps.citations.Fetcher")
    def test_resolve_citations_unresolved_continue_false(self, mock_fetcher_class, step):
        """Test unresolved citation without DOI raises error when continue_on_not_found=False"""
        citing_paper = Paper(
            cite_key="citing2020",
            title="Citing Paper",
            doi="10.1234/citing",
            year=2020,
            paper_type=PaperType.JOURNAL_ARTICLE
        )

        # Citation without DOI will not resolve
        citation = Citation(
            title="Unknown Paper",
            extraction_method="crossref"
        )
        citing_paper.citations = [citation]

        step.db.get_by_doi.return_value = []

        mock_fetcher = MagicMock()
        mock_fetcher.fetch_paper.return_value = (None, False)

        results = {
            "citations_resolved": 0,
            "citations_created_new_paper": 0,
            "citations_unresolved": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "errors": []
        }

        # When continue_on_not_found=False and citation has no DOI, should raise ValueError
        step._resolve_citations_and_fetch_papers(
            papers=[citing_paper],
            fetcher=mock_fetcher,
            continue_on_not_found=False,
            results=results
        )

        # Exception is caught in try/except block and added to errors
        assert len(results["errors"]) > 0
        assert "could not be resolved" in results["errors"][0]

    @patch("paper_scanner.steps.citations.Fetcher")
    def test_resolve_citations_create_new_paper(self, mock_fetcher_class, step):
        """Test creating new paper for unresolved citation"""
        citing_paper = Paper(
            cite_key="citing2020",
            title="Citing Paper",
            doi="10.1234/citing",
            year=2020,
            paper_type=PaperType.JOURNAL_ARTICLE,
            discovery=Discovery(method=DiscoveryMethod.KEYWORD_SEARCH, iteration=0)
        )

        new_paper = Paper(
            cite_key="new2020",
            title="New Paper from Citation",
            doi="10.1234/new",
            year=2019,
            paper_type=PaperType.JOURNAL_ARTICLE
        )

        citation = Citation(
            doi="10.1234/new",
            title="New Paper from Citation",
            year=2019,
            extraction_method="crossref"
        )
        citing_paper.citations = [citation]

        step.db.get_by_doi.return_value = []

        mock_fetcher = MagicMock()
        mock_fetcher.fetch_paper.return_value = (new_paper, False)

        results = {
            "citations_resolved": 0,
            "citations_created_new_paper": 0,
            "citations_unresolved": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "errors": []
        }

        step._resolve_citations_and_fetch_papers(
            papers=[citing_paper],
            fetcher=mock_fetcher,
            continue_on_not_found=True,
            results=results
        )

        assert citation.resolved_paper == new_paper
        assert results["citations_resolved"] == 1
        assert results["citations_created_new_paper"] == 1
        step.db.add.assert_called_with(new_paper)

    def test_resolve_citations_paper_without_citations(self, step):
        """Test handling papers without citations"""
        paper = Paper(
            cite_key="test2020",
            title="Test Paper",
            doi="10.1234/test",
            year=2020
        )

        mock_fetcher = MagicMock()

        results = {
            "citations_resolved": 0,
            "citations_created_new_paper": 0,
            "citations_unresolved": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "errors": []
        }

        step._resolve_citations_and_fetch_papers(
            papers=[paper],
            fetcher=mock_fetcher,
            results=results
        )

        mock_fetcher.fetch_paper.assert_not_called()
        assert results["citations_resolved"] == 0


class TestLinkCitations:
    """Test CitationsStep._link_citations() method - PASS 3"""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database"""
        db = MagicMock(spec=PapersDatabase)
        return db

    @pytest.fixture
    def step(self, tmp_path, mock_db):
        """Create a CitationsStep instance"""
        step = CitationsStep(general_config={}, db=mock_db, cache_dir=tmp_path)
        # Initialize attributes used by the step
        step.verbose = False
        step.debug = False
        step.output_errors = None
        return step

    def test_link_citations_bidirectional(self, step):
        """Test bidirectional linking of citations"""
        cited_paper = Paper(
            cite_key="cited2020",
            title="Cited Paper",
            doi="10.1234/cited",
            year=2020
        )

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
        citation.resolved_paper = cited_paper
        citing_paper.citations = [citation]

        results = {
            "forward_links_created": 0,
            "reverse_links_created": 0,
        }

        step._link_citations(papers=[citing_paper, cited_paper], results=results)

        assert cited_paper in citing_paper.cited_papers
        assert citing_paper in cited_paper.cited_by_papers
        assert results["forward_links_created"] == 1
        assert results["reverse_links_created"] == 1

    def test_link_citations_no_duplicates(self, step):
        """Test that duplicate links are not created"""
        cited_paper = Paper(
            cite_key="cited2020",
            title="Cited Paper",
            doi="10.1234/cited",
            year=2020
        )

        citing_paper = Paper(
            cite_key="citing2020",
            title="Citing Paper",
            doi="10.1234/citing",
            year=2020
        )

        # Pre-add the link
        citing_paper.cited_papers.append(cited_paper)
        cited_paper.cited_by_papers.append(citing_paper)

        citation = Citation(
            doi="10.1234/cited",
            title="Cited Paper",
            extraction_method="crossref"
        )
        citation.resolved_paper = cited_paper
        citing_paper.citations = [citation]

        results = {
            "forward_links_created": 0,
            "reverse_links_created": 0,
        }

        step._link_citations(papers=[citing_paper, cited_paper], results=results)

        assert results["forward_links_created"] == 0
        assert results["reverse_links_created"] == 0

    def test_link_citations_unresolved_citation(self, step):
        """Test handling of unresolved citations"""
        citing_paper = Paper(
            cite_key="citing2020",
            title="Citing Paper",
            doi="10.1234/citing",
            year=2020
        )

        citation = Citation(
            doi="10.1234/unknown",
            title="Unknown Paper",
            extraction_method="crossref"
        )
        citation.resolved_paper = None
        citing_paper.citations = [citation]

        results = {
            "forward_links_created": 0,
            "reverse_links_created": 0,
        }

        step._link_citations(papers=[citing_paper], results=results)

        assert results["forward_links_created"] == 0
        assert results["reverse_links_created"] == 0

    def test_link_citations_paper_without_citations(self, step):
        """Test handling papers without citations"""
        paper = Paper(
            cite_key="test2020",
            title="Test Paper",
            doi="10.1234/test",
            year=2020
        )

        results = {
            "forward_links_created": 0,
            "reverse_links_created": 0,
        }

        step._link_citations(papers=[paper], results=results)

        assert results["forward_links_created"] == 0
        assert results["reverse_links_created"] == 0


class TestExecute:
    """Test CitationsStep.execute() method"""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database"""
        db = MagicMock(spec=PapersDatabase)
        db.count.return_value = 1
        db.find.return_value = []
        db.all.return_value = []
        db.add = MagicMock()
        db.update_batch = MagicMock()
        return db

    @pytest.fixture
    def step(self, tmp_path, mock_db):
        """Create a CitationsStep instance with mock database"""
        step = CitationsStep(general_config={}, db=mock_db, cache_dir=tmp_path)
        return step

    @patch("paper_scanner.steps.citations.Fetcher")
    def test_execute_with_no_papers(self, mock_fetcher_class, step):
        """Test execution when no papers in database"""
        step.db.count.return_value = 0
        step.db.find.return_value = []

        config = {
            "backward": {
                "sources": ["crossref"],
                "continue_on_not_found": True
            }
        }

        results = step.execute(config, verbose=False, dry_run=True)

        assert results["total_papers"] == 0
        assert results["target_papers"] == 0
        assert results["citations_fetched"] == 0
        assert results["status"] == "ok"

    @patch("paper_scanner.steps.citations.Fetcher")
    def test_execute_with_papers(self, mock_fetcher_class, step):
        """Test execution with papers"""
        paper = Paper(
            cite_key="test2020",
            title="Test Paper",
            doi="10.1234/test",
            year=2020,
            paper_type=PaperType.JOURNAL_ARTICLE,
            discovery=Discovery(method=DiscoveryMethod.KEYWORD_SEARCH, iteration=0)
        )

        step.db.count.return_value = 1
        step.db.find.return_value = [paper]
        step.db.all.return_value = [paper]

        mock_fetcher = MagicMock()
        mock_fetcher.fetch_citations.return_value = ([], False)
        mock_fetcher_class.return_value = mock_fetcher

        config = {
            "backward": {
                "sources": ["crossref"],
                "continue_on_not_found": True
            }
        }

        results = step.execute(config, verbose=False, dry_run=True)

        assert results["total_papers"] == 1
        assert results["target_papers"] == 1
        assert results["status"] == "ok"

    @patch("paper_scanner.steps.citations.Fetcher")
    def test_execute_with_errors(self, mock_fetcher_class, step):
        """Test execute reports errors correctly"""
        paper = Paper(
            cite_key="test2020",
            title="Test Paper",
            doi="10.1234/test",
            year=2020,
            paper_type=PaperType.JOURNAL_ARTICLE
        )

        step.db.count.return_value = 1
        step.db.find.return_value = [paper]
        step.db.all.return_value = [paper]

        mock_fetcher = MagicMock()
        mock_fetcher.fetch_citations.side_effect = Exception("API Error")
        mock_fetcher_class.return_value = mock_fetcher

        config = {
            "backward": {
                "sources": ["crossref"]
            }
        }

        results = step.execute(config, verbose=False, dry_run=False)

        assert len(results["errors"]) > 0
        assert results["status"] == "completed_with_errors"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])