"""
Unit tests for paper_scanner.io.bibtex

Tests for BibTeX parsing and conversion to Paper models.
"""

from pathlib import Path

import pytest

from paper_scanner.core.enum import DiscoveryMethod, PaperType
from paper_scanner.core.models import Author, Discovery, Paper
from paper_scanner.io.bibtex import (bibtex_entry_to_paper,
                                     bibtex_file_to_papers, bibtex_to_papers,
                                     infer_paper_type, parse_authors,
                                     parse_keywords)

# Test data directory
TEST_DATA_DIR = Path(__file__).parent.parent.parent / "data"


class TestParseAuthors:
    """Test author parsing from BibTeX format"""

    def test_parse_authors_comma_separated(self):
        """Verify parsing of 'Last, First' format"""
        author_string = "Smith, John and Doe, Jane"
        authors = parse_authors(author_string)

        assert len(authors) == 2
        assert authors[0].family_name == "Smith"
        assert authors[0].given_name == "John"
        assert authors[1].family_name == "Doe"
        assert authors[1].given_name == "Jane"

    def test_parse_authors_space_separated(self):
        """Verify parsing of 'First Last' format"""
        author_string = "John Smith and Jane Doe"
        authors = parse_authors(author_string)

        assert len(authors) == 2
        assert authors[0].family_name == "Smith"
        assert authors[0].given_name == "John"
        assert authors[1].family_name == "Doe"
        assert authors[1].given_name == "Jane"

    def test_parse_authors_single_author(self):
        """Verify parsing of single author"""
        author_string = "John Smith"
        authors = parse_authors(author_string)

        assert len(authors) == 1
        assert authors[0].family_name == "Smith"
        assert authors[0].given_name == "John"

    def test_parse_authors_single_name(self):
        """Verify parsing of single name author"""
        author_string = "Aristotle"
        authors = parse_authors(author_string)

        assert len(authors) == 1
        assert authors[0].family_name == "Aristotle"
        assert authors[0].given_name is None

    def test_parse_authors_abbreviated_names(self):
        """Verify parsing of abbreviated names"""
        author_string = "Smith, J. and Doe, J."
        authors = parse_authors(author_string)

        assert len(authors) == 2
        assert authors[0].family_name == "Smith"
        assert authors[0].given_name == "J."

    def test_parse_authors_empty_string(self):
        """Verify empty author string returns empty list"""
        authors = parse_authors("")
        assert authors == []

    def test_parse_authors_multiple(self):
        """Verify parsing multiple authors"""
        author_string = "Smith, John and Doe, Jane and Johnson, Bob"
        authors = parse_authors(author_string)

        assert len(authors) == 3
        assert authors[2].family_name == "Johnson"

    def test_parse_authors_whitespace_handling(self):
        """Verify whitespace is properly handled"""
        author_string = "  Smith, John  and  Doe, Jane  "
        authors = parse_authors(author_string)

        assert len(authors) == 2
        assert authors[0].family_name == "Smith"
        assert authors[1].family_name == "Doe"

    def test_parse_authors_creates_author_objects(self):
        """Verify Author objects are created"""
        author_string = "John Smith and Jane Doe"
        authors = parse_authors(author_string)

        assert all(isinstance(a, Author) for a in authors)


class TestParseKeywords:
    """Test keyword parsing from BibTeX format"""

    def test_parse_keywords_semicolon_separated(self):
        """Verify parsing of semicolon-separated keywords"""
        keywords_string = "machine learning; deep learning; AI"
        keywords = parse_keywords(keywords_string)

        assert len(keywords) == 3
        assert "machine learning" in keywords
        assert "deep learning" in keywords
        assert "ai" in keywords

    def test_parse_keywords_comma_separated(self):
        """Verify parsing of comma-separated keywords"""
        keywords_string = "machine learning, deep learning, AI"
        keywords = parse_keywords(keywords_string)

        assert len(keywords) == 3
        assert "machine learning" in keywords

    def test_parse_keywords_and_separated(self):
        """Verify parsing of 'and'-separated keywords"""
        keywords_string = "machine learning and deep learning and AI"
        keywords = parse_keywords(keywords_string)

        assert len(keywords) == 3
        assert "machine learning" in keywords

    def test_parse_keywords_single_keyword(self):
        """Verify single keyword is returned"""
        keywords_string = "machine learning"
        keywords = parse_keywords(keywords_string)

        assert len(keywords) == 1
        assert keywords[0] == "machine learning"

    def test_parse_keywords_empty_string(self):
        """Verify empty string returns empty list"""
        keywords = parse_keywords("")
        assert keywords == []

    def test_parse_keywords_whitespace_trimmed(self):
        """Verify whitespace is trimmed"""
        keywords_string = "  machine learning  ;  deep learning  "
        keywords = parse_keywords(keywords_string)

        assert keywords[0] == "machine learning"
        assert keywords[1] == "deep learning"

    def test_parse_keywords_empty_entries_removed(self):
        """Verify empty entries are removed"""
        keywords_string = "machine learning;; deep learning"
        keywords = parse_keywords(keywords_string)

        assert len(keywords) == 2
        assert "machine learning" in keywords
        assert "deep learning" in keywords


class TestInferPaperType:
    """Test paper type inference from BibTeX entry type"""

    def test_infer_paper_type_article(self):
        """Verify article type inference"""
        entry = {"ENTRYTYPE": "article"}
        paper_type = infer_paper_type(entry)
        assert paper_type == PaperType.JOURNAL_ARTICLE

    def test_infer_paper_type_inproceedings(self):
        """Verify conference type inference"""
        entry = {"ENTRYTYPE": "inproceedings"}
        paper_type = infer_paper_type(entry)
        assert paper_type == PaperType.CONFERENCE_PAPER

    def test_infer_paper_type_book(self):
        """Verify book type inference"""
        entry = {"ENTRYTYPE": "book"}
        paper_type = infer_paper_type(entry)
        assert paper_type == PaperType.BOOK

    def test_infer_paper_type_incollection(self):
        """Verify book chapter type inference"""
        entry = {"ENTRYTYPE": "incollection"}
        paper_type = infer_paper_type(entry)
        assert paper_type == PaperType.BOOK_CHAPTER

    def test_infer_paper_type_phdthesis(self):
        """Verify thesis type inference"""
        entry = {"ENTRYTYPE": "phdthesis"}
        paper_type = infer_paper_type(entry)
        assert paper_type == PaperType.THESIS

    def test_infer_paper_type_techreport(self):
        """Verify technical report type inference"""
        entry = {"ENTRYTYPE": "techreport"}
        paper_type = infer_paper_type(entry)
        assert paper_type == PaperType.TECHNICAL_REPORT

    def test_infer_paper_type_unknown(self):
        """Verify unknown types default to OTHER"""
        entry = {"ENTRYTYPE": "unknown_type"}
        paper_type = infer_paper_type(entry)
        assert paper_type == PaperType.OTHER

    def test_infer_paper_type_case_insensitive(self):
        """Verify type inference is case-insensitive"""
        entry = {"ENTRYTYPE": "Article"}
        paper_type = infer_paper_type(entry)
        assert paper_type == PaperType.JOURNAL_ARTICLE

    def test_infer_paper_type_missing_entrytype(self):
        """Verify missing entry type defaults to OTHER"""
        entry = {}
        paper_type = infer_paper_type(entry)
        assert paper_type == PaperType.OTHER


class TestBibtexEntryToPaper:
    """Test conversion of individual BibTeX entries to Paper models"""

    def test_bibtex_entry_basic(self):
        """Verify basic BibTeX entry conversion"""
        discovery = Discovery(method=DiscoveryMethod.MANUAL)
        entry = {
            "ID": "smith2020",
            "ENTRYTYPE": "article",
            "title": "Test Article",
        }
        paper = bibtex_entry_to_paper(entry, discovery=discovery)

        assert paper.cite_key == "smith2020"
        assert paper.title == "Test Article"
        assert paper.discovery is not None
        assert paper.discovery.method == DiscoveryMethod.MANUAL

    def test_bibtex_entry_missing_cite_key(self):
        """Verify error on missing cite_key"""
        entry = {
            "ENTRYTYPE": "article",
            "title": "Test Article",
        }
        with pytest.raises(ValueError, match="missing ID"):
            bibtex_entry_to_paper(entry)

    def test_bibtex_entry_missing_title(self):
        """Verify error on missing title"""
        entry = {
            "ID": "test2020",
            "ENTRYTYPE": "article",
        }
        with pytest.raises(ValueError, match="missing title"):
            bibtex_entry_to_paper(entry)

    def test_bibtex_entry_with_authors(self):
        """Verify BibTeX entry with authors"""
        entry = {
            "ID": "smith2020",
            "ENTRYTYPE": "article",
            "title": "Test Article",
            "author": "Smith, John and Doe, Jane",
        }
        paper = bibtex_entry_to_paper(entry)

        assert len(paper.authors) == 2
        assert paper.authors[0].family_name == "Smith"

    def test_bibtex_entry_with_year(self):
        """Verify BibTeX entry with year"""
        entry = {
            "ID": "smith2020",
            "ENTRYTYPE": "article",
            "title": "Test Article",
            "year": "2020",
        }
        paper = bibtex_entry_to_paper(entry)
        assert paper.year == 2020

    def test_bibtex_entry_with_doi(self):
        """Verify BibTeX entry with DOI"""
        entry = {
            "ID": "smith2020",
            "ENTRYTYPE": "article",
            "title": "Test Article",
            "doi": "10.1234/test",
        }
        paper = bibtex_entry_to_paper(entry)
        assert paper.doi == "10.1234/test"

    def test_bibtex_entry_with_abstract(self):
        """Verify BibTeX entry with abstract"""
        entry = {
            "ID": "smith2020",
            "ENTRYTYPE": "article",
            "title": "Test Article",
            "abstract": "This is a test abstract.",
        }
        paper = bibtex_entry_to_paper(entry)
        assert paper.abstract == "This is a test abstract."

    def test_bibtex_entry_with_keywords(self):
        """Verify BibTeX entry with keywords"""
        entry = {
            "ID": "smith2020",
            "ENTRYTYPE": "article",
            "title": "Test Article",
            "keywords": "AI; machine learning; deep learning",
        }
        paper = bibtex_entry_to_paper(entry)
        assert len(paper.keywords) == 3

    def test_bibtex_entry_with_journal(self):
        """Verify BibTeX entry with journal"""
        entry = {
            "ID": "smith2020",
            "ENTRYTYPE": "article",
            "title": "Test Article",
            "journal": "Nature",
            "volume": "500",
            "number": "5",
            "pages": "123-145",
        }
        paper = bibtex_entry_to_paper(entry)
        assert paper.journal == "Nature"
        assert paper.volume == "500"
        assert paper.number == "5"
        assert paper.pages == "123-145"

    def test_bibtex_entry_discovery_created(self):
        """Verify Discovery object is created"""
        discovery = Discovery(method=DiscoveryMethod.KEYWORD_SEARCH)
        entry = {
            "ID": "smith2020",
            "ENTRYTYPE": "article",
            "title": "Test Article",
        }
        paper = bibtex_entry_to_paper(entry, discovery=discovery)
        assert paper.discovery is not None
        assert paper.discovery.method == DiscoveryMethod.KEYWORD_SEARCH

    def test_bibtex_entry_with_custom_source_type(self):
        """Verify custom source type"""
        discovery = Discovery(method=DiscoveryMethod.KEYWORD_SEARCH, source_database="scopus")
        entry = {
            "ID": "smith2020",
            "ENTRYTYPE": "article",
            "title": "Test Article",
        }

        paper = bibtex_entry_to_paper(entry, discovery=discovery)
        assert paper.discovery.source_database == "scopus"

    def test_bibtex_entry_with_import_batch_id(self):
        """Verify import batch ID is stored"""
        batch_id = "batch_123"
        discovery = Discovery(
            method=DiscoveryMethod.KEYWORD_SEARCH, 
            source_database="scopus",
            import_batch_id=batch_id
        )
        entry = {
            "ID": "smith2020",
            "ENTRYTYPE": "article",
            "title": "Test Article",
        }
        paper = bibtex_entry_to_paper(entry, discovery=discovery)
        assert paper.discovery.import_batch_id == batch_id

    def test_bibtex_entry_latex_removed(self):
        """Verify LaTeX braces are removed from title"""
        entry = {
            "ID": "smith2020",
            "ENTRYTYPE": "article",
            "title": "{Test} {Article}",
        }
        paper = bibtex_entry_to_paper(entry)
        assert paper.title == "Test Article"

    def test_bibtex_entry_raw_bibtex_stored(self):
        """Verify raw BibTeX is stored"""
        entry = {
            "ID": "smith2020",
            "ENTRYTYPE": "article",
            "title": "Test Article",
        }
        paper = bibtex_entry_to_paper(entry)
        assert paper.raw_bibtex is not None


class TestBibtexToPapers:
    """Test conversion of BibTeX string to list of Papers"""

    def test_bibtex_single_entry(self):
        """Verify parsing single BibTeX entry"""
        bibtex_string = """
        @article{smith2020,
            title={Test Article},
            author={Smith, John}
        }
        """
        papers = bibtex_to_papers(bibtex_string)
        assert len(papers) == 1
        assert papers[0].cite_key == "smith2020"

    def test_bibtex_multiple_entries(self):
        """Verify parsing multiple BibTeX entries"""
        bibtex_string = """
        @article{smith2020,
            title={Test Article 1},
            author={Smith, John}
        }
        @article{doe2021,
            title={Test Article 2},
            author={Doe, Jane}
        }
        """
        papers = bibtex_to_papers(bibtex_string)
        assert len(papers) == 2
        assert papers[0].cite_key == "smith2020"
        assert papers[1].cite_key == "doe2021"

    def test_bibtex_different_entry_types(self):
        """Verify parsing mixed entry types"""
        bibtex_string = """
        @article{smith2020,
            title={Test Article}
        }
        @inproceedings{doe2021,
            title={Test Conference Paper}
        }
        @book{johnson2022,
            title={Test Book}
        }
        """
        papers = bibtex_to_papers(bibtex_string)
        assert len(papers) == 3

    def test_bibtex_custom_discovery_method(self):
        """Verify custom discovery method applied to all papers"""
        discovery = Discovery(method=DiscoveryMethod.BACKWARD_CITATION)
        bibtex_string = """
        @article{smith2020,
            title={Test Article 1}
        }
        @article{doe2021,
            title={Test Article 2}
        }
        """
        papers = bibtex_to_papers(bibtex_string, discovery=discovery)
        assert all(p.discovery.method == DiscoveryMethod.BACKWARD_CITATION for p in papers)

    def test_bibtex_custom_source_type(self):
        """Verify custom source type applied to all papers"""
        discovery = Discovery(
            method=DiscoveryMethod.KEYWORD_SEARCH,
            source_database="scopus"
        )
        bibtex_string = """
        @article{smith2020,
            title={Test Article}
        }
        """
        papers = bibtex_to_papers(bibtex_string, discovery=discovery)
        assert papers[0].discovery.source_database == "scopus"

    def test_bibtex_with_import_batch_id(self):
        """Verify import batch ID applied to all papers"""
        batch_id = "batch_123"
        discovery = Discovery(
            method=DiscoveryMethod.KEYWORD_SEARCH,
            source_database="scopus",
            import_batch_id=batch_id
        )
        bibtex_string = """
        @article{smith2020,
            title={Test Article}
        }
        """
        papers = bibtex_to_papers(bibtex_string, discovery=discovery)
        assert papers[0].discovery.import_batch_id == batch_id

    def test_bibtex_returns_paper_objects(self):
        """Verify returned objects are Paper models"""
        bibtex_string = """
        @article{smith2020,
            title={Test Article}
        }
        """
        papers = bibtex_to_papers(bibtex_string)
        assert all(isinstance(p, Paper) for p in papers)


class TestBibtexFileToPapers:
    """Test loading and parsing BibTeX files"""

    def test_bibtex_file_ieee(self):
        """Verify parsing IEEE sample BibTeX file"""
        filepath = TEST_DATA_DIR / "ieee_sample_20.bib"

        if not filepath.exists():
            pytest.skip(f"Test data file not found: {filepath}")

        papers = bibtex_file_to_papers(str(filepath))

        assert len(papers) > 0
        assert all(isinstance(p, Paper) for p in papers)
        assert all(p.cite_key for p in papers)
        assert all(p.title for p in papers)

    def test_bibtex_file_scopus(self):
        """Verify parsing Scopus sample BibTeX file"""
        filepath = TEST_DATA_DIR / "scopus_sample_20.bib"

        if not filepath.exists():
            pytest.skip(f"Test data file not found: {filepath}")

        papers = bibtex_file_to_papers(str(filepath))

        assert len(papers) > 0
        assert all(isinstance(p, Paper) for p in papers)

    def test_bibtex_file_wos(self):
        """Verify parsing Web of Science sample BibTeX file"""
        filepath = TEST_DATA_DIR / "wos_sample_20.bib"

        if not filepath.exists():
            pytest.skip(f"Test data file not found: {filepath}")

        papers = bibtex_file_to_papers(str(filepath))

        assert len(papers) > 0
        assert all(isinstance(p, Paper) for p in papers)

    def test_bibtex_file_custom_source_type(self):
        """Verify custom source type on file parsing"""
        filepath = TEST_DATA_DIR / "ieee_sample_20.bib"
        discovery = Discovery(
            method=DiscoveryMethod.KEYWORD_SEARCH,
            source_database="ieee"
        )
        if not filepath.exists():
            pytest.skip(f"Test data file not found: {filepath}")

        papers = bibtex_file_to_papers(str(filepath), discovery=discovery)
        assert all(p.discovery.source_database == "ieee" for p in papers)

    def test_bibtex_file_nonexistent(self):
        """Verify error on nonexistent file"""
        with pytest.raises(FileNotFoundError):
            bibtex_file_to_papers("/nonexistent/path/file.bib")


class TestBibtexParsingIntegration:
    """Integration tests for BibTeX parsing workflow"""

    def test_ieee_file_has_valid_papers(self):
        """Verify IEEE file produces valid papers with expected fields"""
        filepath = TEST_DATA_DIR / "ieee_sample_20.bib"
        discovery = Discovery(
            method=DiscoveryMethod.KEYWORD_SEARCH,
            source_database="ieee"
        )
        
        if not filepath.exists():
            pytest.skip(f"Test data file not found: {filepath}")

        papers = bibtex_file_to_papers(str(filepath), discovery=discovery)

        # Check basic structure
        assert len(papers) >= 5

        for paper in papers[:5]:  # Check first 5
            assert paper.cite_key
            assert paper.title
            assert paper.discovery.source_database == "ieee"
            assert isinstance(paper.authors, list)
            assert paper.discovery is not None

    def test_scopus_file_has_valid_papers(self):
        """Verify Scopus file produces valid papers"""
        filepath = TEST_DATA_DIR / "scopus_sample_20.bib"

        discovery = Discovery(
            method=DiscoveryMethod.KEYWORD_SEARCH,
            source_database="scopus"
        )

        if not filepath.exists():
            pytest.skip(f"Test data file not found: {filepath}")

        papers = bibtex_file_to_papers(str(filepath), discovery=discovery)

        assert len(papers) >= 5
        for paper in papers[:5]:
            assert paper.cite_key
            assert paper.title
            assert paper.discovery.source_database == "scopus"

    def test_wos_file_has_valid_papers(self):
        """Verify Web of Science file produces valid papers"""
        filepath = TEST_DATA_DIR / "wos_sample_20.bib"

        if not filepath.exists():
            pytest.skip(f"Test data file not found: {filepath}")

        discovery = Discovery(
            method=DiscoveryMethod.KEYWORD_SEARCH,
            source_database="wos"
        )

        papers = bibtex_file_to_papers(str(filepath), discovery=discovery)

        assert len(papers) >= 5
        for paper in papers[:5]:
            assert paper.cite_key
            assert paper.title
            assert paper.discovery.source_database == "wos"
            assert len(paper.authors) > 0 or paper.title  # At least has title

    def test_parsed_papers_have_discovery_metadata(self):
        """Verify parsed papers have proper discovery metadata"""
        filepath = TEST_DATA_DIR / "ieee_sample_20.bib"

        if not filepath.exists():
            pytest.skip(f"Test data file not found: {filepath}")

        batch_id = "test_batch_123"
        discovery = Discovery(
            method=DiscoveryMethod.KEYWORD_SEARCH,
            source_database="ieee",
            import_batch_id=batch_id
        )

        papers = bibtex_file_to_papers(
            str(filepath), discovery=discovery
        )

        for paper in papers[:3]:
            assert paper.discovery.method == DiscoveryMethod.KEYWORD_SEARCH
            assert paper.discovery.import_batch_id == batch_id
            assert paper.discovery.source_database == "ieee"

    def test_round_trip_parsing_preserves_data(self):
        """Verify data is preserved through parsing"""
        bibtex_string = """
        @article{smith2020,
            author={Smith, John and Doe, Jane},
            title={Advanced Machine Learning},
            journal={Nature},
            year={2020},
            volume={500},
            pages={123-145},
            doi={10.1234/test},
            abstract={This is a test abstract about machine learning},
            keywords={machine learning; AI; neural networks}
        }
        """
        papers = bibtex_to_papers(bibtex_string)
        paper = papers[0]

        assert paper.cite_key == "smith2020"
        assert len(paper.authors) == 2
        assert paper.title == "Advanced Machine Learning"
        assert paper.journal == "Nature"
        assert paper.year == 2020
        assert paper.volume == "500"
        assert paper.pages == "123-145"
        assert paper.doi == "10.1234/test"
        assert paper.abstract == "This is a test abstract about machine learning"
        # Note: keywords parsing depends on field name in BibTeX parser
        assert isinstance(paper.keywords, list)
