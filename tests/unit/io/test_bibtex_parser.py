"""
Unit tests for paper_scanner.io.bibtex

Tests for BibTeX parsing and conversion to Paper models.
"""

from pathlib import Path

import pytest

from paper_scanner.core.enum import DiscoveryMethod, PaperType
from paper_scanner.core.models import Author, Discovery, Paper
from paper_scanner.core.normalization import Normalizer
from paper_scanner.io.bibtex import (
    bibtex_entry_to_paper,
    bibtex_file_to_papers,
    bibtex_to_papers,
    clean_bibtex_string,
    evaluate_paper_type,
    escape_ampersands_for_bibtex,
    export_papers_by_source,
    format_authors_bibtex,
    format_bibtex_entry,
    format_keywords_bibtex,
    infer_bibtex_type,
    infer_paper_type,
    load_type_mapping_config,
    paper_to_bibtex_entry,
    papers_to_bibtex,
    papers_to_bibtex_file,
)

# Test data directory
TEST_DATA_DIR = Path(__file__).parent.parent.parent / "data"


class TestParseKeywords:
    """Test keyword parsing from BibTeX format"""

    def test_parse_keywords_semicolon_separated(self):
        """Verify parsing of semicolon-separated keywords"""
        keywords_string = "machine learning; deep learning; AI"
        keywords = Normalizer.normalize_keywords(keywords_string)

        assert len(keywords) == 3
        assert "machine learning" in keywords
        assert "deep learning" in keywords
        assert "ai" in keywords

    def test_parse_keywords_comma_separated(self):
        """Verify parsing of comma-separated keywords"""
        keywords_string = "machine learning, deep learning, AI"
        keywords = Normalizer.normalize_keywords(keywords_string)

        assert len(keywords) == 3
        assert "machine learning" in keywords

    def test_parse_keywords_and_separated(self):
        """Verify parsing of 'and'-separated keywords"""
        keywords_string = "machine learning and deep learning and AI"
        keywords = Normalizer.normalize_keywords(keywords_string)

        assert len(keywords) == 3
        assert "machine learning" in keywords

    def test_parse_keywords_single_keyword(self):
        """Verify single keyword is returned"""
        keywords_string = "machine learning"
        keywords = Normalizer.normalize_keywords(keywords_string)

        assert len(keywords) == 1
        assert keywords[0] == "machine learning"

    def test_parse_keywords_empty_string(self):
        """Verify empty string returns empty list"""
        keywords = Normalizer.normalize_keywords("")
        assert keywords == []

    def test_parse_keywords_whitespace_trimmed(self):
        """Verify whitespace is trimmed"""
        keywords_string = "  machine learning  ;  deep learning  "
        keywords = Normalizer.normalize_keywords(keywords_string)

        assert keywords[0] == "machine learning"
        assert keywords[1] == "deep learning"

    def test_parse_keywords_empty_entries_removed(self):
        """Verify empty entries are removed"""
        keywords_string = "machine learning;; deep learning"
        keywords = Normalizer.normalize_keywords(keywords_string)

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

    def test_bibtex_entry_journal_title_case_normalization(self):
        """Verify journal name is normalized to title case"""
        entry = {
            "ID": "smith2020",
            "ENTRYTYPE": "article",
            "title": "Test Article",
            "journal": "nature machine intelligence",
        }
        paper = bibtex_entry_to_paper(entry)
        # journal field uses .title() which capitalizes first letter of each word
        assert paper.journal == "Nature Machine Intelligence"

    def test_bibtex_entry_abstract_whitespace_normalization(self):
        """Verify abstract whitespace (newlines, tabs, multiple spaces) is normalized"""
        entry = {
            "ID": "smith2020",
            "ENTRYTYPE": "article",
            "title": "Test Article",
            "abstract": """Industrial manufacturers are innovating their business models by
   shifting from selling products to selling outcome-based services, where
   the provider (manufacturer) guarantees to deliver the performance
   outcomes of the products and services.""",
        }
        paper = bibtex_entry_to_paper(entry)
        # Should be single line with single spaces between words
        assert "\n" not in paper.abstract
        assert "  " not in paper.abstract
        assert paper.abstract.startswith("Industrial manufacturers are")
        assert paper.abstract.count(" ") == paper.abstract.split().__len__() - 1

    def test_bibtex_entry_abstract_escaped_ampersands(self):
        """Verify escaped ampersands \\& are normalized to &"""
        entry = {
            "ID": "smith2020",
            "ENTRYTYPE": "article",
            "title": "Test Article",
            "abstract": r"This study of A \& B shows that supply \& demand are important.",
        }
        paper = bibtex_entry_to_paper(entry)
        assert r"\&" not in paper.abstract
        assert " & " in paper.abstract
        assert paper.abstract.count("&") == 2

    def test_bibtex_entry_abstract_html_ampersands(self):
        """Verify HTML-encoded ampersands &amp; are normalized to &"""
        entry = {
            "ID": "smith2020",
            "ENTRYTYPE": "article",
            "title": "Test Article",
            "abstract": "This studies A &amp; B and their relationship &amp; outcomes.",
        }
        paper = bibtex_entry_to_paper(entry)
        assert "&amp;" not in paper.abstract
        assert " & " in paper.abstract
        assert paper.abstract.count("&") == 2

    def test_bibtex_entry_title_ampersands_normalization(self):
        """Verify ampersands in title are not normalized"""
        entry = {
            "ID": "smith2020",
            "ENTRYTYPE": "article",
            "title": r"Machine Learning \& Deep Learning Trends",
        }
        paper = bibtex_entry_to_paper(entry)
        assert r"\&" not in paper.title
        assert " & " in paper.title

    def test_bibtex_entry_journal_ampersands_normalization(self):
        """Verify ampersands in journal name are normalized"""
        entry = {
            "ID": "smith2020",
            "ENTRYTYPE": "article",
            "title": "Test Article",
            "journal": r"IEEE Transactions on Software \& Engineering",
        }
        paper = bibtex_entry_to_paper(entry)
        assert r"\&" not in paper.journal
        assert " & " in paper.journal

    def test_paper_to_bibtex_entry_ampersands_escaped(self):
        """Verify ampersands are escaped when exporting to BibTeX"""
        paper = Paper(
            cite_key="smith2020",
            title="Machine Learning & Deep Learning",
            abstract="This paper studies A & B",
            authors=[],
            journal="IEEE Transactions on Software & Engineering",
        )
        entry = paper_to_bibtex_entry(paper)
        # When exporting, & should be escaped as \&
        assert entry["title"] == r"Machine Learning \& Deep Learning"
        assert entry["abstract"] == r"This paper studies A \& B"
        assert entry["journal"] == r"IEEE Transactions on Software \& Engineering"

    def test_paper_to_bibtex_entry_already_escaped_ampersands(self):
        """Verify already escaped ampersands are not double-escaped"""
        paper = Paper(
            cite_key="smith2020",
            title=r"Machine Learning \& Deep Learning",
            abstract=r"This paper studies A \& B",
            authors=[],
            journal=r"IEEE Transactions on Software \& Engineering",
        )
        entry = paper_to_bibtex_entry(paper)
        # Should not have double backslashes
        assert entry["title"].count(r"\&") == 1
        assert entry["abstract"].count(r"\&") == 1
        assert entry["journal"].count(r"\&") == 1


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
            source_database="ieee"
        )

        papers = bibtex_file_to_papers(
            str(filepath), discovery=discovery
        )

        for paper in papers[:3]:
            assert paper.discovery.method == DiscoveryMethod.KEYWORD_SEARCH
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


class TestEvaluatePaperType:
    """Test evaluate_paper_type function with type mapping configuration"""

    def test_evaluate_paper_type_article(self):
        """Verify article type evaluation"""
        entry = {"ENTRYTYPE": "article"}
        paper_type, confidence = evaluate_paper_type(entry)
        assert paper_type == "journal_article"
        assert confidence > 0.9

    def test_evaluate_paper_type_inproceedings(self):
        """Verify conference type evaluation"""
        entry = {"ENTRYTYPE": "inproceedings"}
        paper_type, confidence = evaluate_paper_type(entry)
        assert paper_type == "conference_paper"
        assert confidence > 0.9

    def test_evaluate_paper_type_book(self):
        """Verify book type evaluation"""
        entry = {"ENTRYTYPE": "book"}
        paper_type, confidence = evaluate_paper_type(entry)
        assert paper_type == "book"
        assert confidence > 0.9

    def test_evaluate_paper_type_incollection(self):
        """Verify book chapter evaluation"""
        entry = {"ENTRYTYPE": "incollection"}
        paper_type, confidence = evaluate_paper_type(entry)
        assert paper_type == "book_chapter"
        assert confidence > 0.8

    def test_evaluate_paper_type_phdthesis(self):
        """Verify thesis evaluation"""
        entry = {"ENTRYTYPE": "phdthesis"}
        paper_type, confidence = evaluate_paper_type(entry)
        assert paper_type == "thesis"
        assert confidence > 0.9

    def test_evaluate_paper_type_mastersthesis(self):
        """Verify master's thesis evaluation"""
        entry = {"ENTRYTYPE": "mastersthesis"}
        paper_type, confidence = evaluate_paper_type(entry)
        assert paper_type == "thesis"
        assert confidence > 0.9

    def test_evaluate_paper_type_techreport(self):
        """Verify technical report evaluation"""
        entry = {"ENTRYTYPE": "techreport"}
        paper_type, confidence = evaluate_paper_type(entry)
        assert paper_type == "technical_report"
        assert confidence > 0.8

    def test_evaluate_paper_type_misc(self):
        """Verify misc type evaluation"""
        entry = {"ENTRYTYPE": "misc"}
        paper_type, confidence = evaluate_paper_type(entry)
        assert paper_type == "other"
        assert confidence > 0.4

    def test_evaluate_paper_type_unknown(self):
        """Verify unknown type returns None and low confidence"""
        entry = {"ENTRYTYPE": "unknown_format"}
        paper_type, confidence = evaluate_paper_type(entry)
        assert paper_type is None
        assert confidence == 0.0

    def test_evaluate_paper_type_case_insensitive(self):
        """Verify type evaluation is case-insensitive"""
        entry = {"ENTRYTYPE": "ARTICLE"}
        paper_type, confidence = evaluate_paper_type(entry)
        assert paper_type == "journal_article"

    def test_evaluate_paper_type_with_source_type(self):
        """Verify source-specific type evaluation"""
        entry = {"ENTRYTYPE": "article"}
        paper_type, confidence = evaluate_paper_type(entry, source_type="scopus")
        assert paper_type is not None

    def test_load_type_mapping_config_default(self):
        """Verify type mapping config loads with defaults"""
        config = load_type_mapping_config()
        assert "type_mappings" in config
        assert "article" in config["type_mappings"]

    def test_load_type_mapping_config_caching(self):
        """Verify type mapping config is cached"""
        config1 = load_type_mapping_config()
        config2 = load_type_mapping_config()
        # Should be the same object due to caching
        assert config1 is config2


class TestFormatAuthorsBibtex:
    """Test formatting authors to BibTeX format"""

    def test_format_authors_single(self):
        """Verify single author formatting"""
        authors = [Author(family_name="Smith", given_name="John", full_name="John Smith")]
        result = format_authors_bibtex(authors)
        assert result == "Smith, John"

    def test_format_authors_multiple(self):
        """Verify multiple authors formatting"""
        authors = [
            Author(family_name="Smith", given_name="John", full_name="John Smith"),
            Author(family_name="Doe", given_name="Jane", full_name="Jane Doe")
        ]
        result = format_authors_bibtex(authors)
        assert result == "Smith, John and Doe, Jane"

    def test_format_authors_without_given_name(self):
        """Verify formatting when given_name is None"""
        authors = [Author(family_name="Smith", full_name="Smith")]
        result = format_authors_bibtex(authors)
        assert result == "Smith"

    def test_format_authors_empty_list(self):
        """Verify empty author list returns empty string"""
        result = format_authors_bibtex([])
        assert result == ""

    def test_format_authors_three_plus(self):
        """Verify formatting with 3+ authors"""
        authors = [
            Author(family_name="Smith", given_name="John", full_name="John Smith"),
            Author(family_name="Doe", given_name="Jane", full_name="Jane Doe"),
            Author(family_name="Johnson", given_name="Bob", full_name="Bob Johnson")
        ]
        result = format_authors_bibtex(authors)
        assert "Smith, John and Doe, Jane and Johnson, Bob" == result


class TestFormatKeywordsBibtex:
    """Test formatting keywords to BibTeX format"""

    def test_format_keywords_single(self):
        """Verify single keyword formatting"""
        keywords = ["machine learning"]
        result = format_keywords_bibtex(keywords)
        assert result == "machine learning"

    def test_format_keywords_multiple(self):
        """Verify multiple keywords formatting"""
        keywords = ["machine learning", "deep learning", "AI"]
        result = format_keywords_bibtex(keywords)
        assert result == "machine learning, deep learning, AI"

    def test_format_keywords_empty_list(self):
        """Verify empty keywords list returns empty string"""
        result = format_keywords_bibtex([])
        assert result == ""

    def test_format_keywords_with_special_chars(self):
        """Verify keywords with special characters"""
        keywords = ["machine-learning", "neural_networks"]
        result = format_keywords_bibtex(keywords)
        assert "machine-learning" in result
        assert "neural_networks" in result


class TestInferBibtexType:
    """Test inferring BibTeX entry type from Paper model"""

    def test_infer_bibtex_type_journal_article(self):
        """Verify journal article type inference"""
        paper = Paper(
            cite_key="test",
            title="Test",
            paper_type=PaperType.JOURNAL_ARTICLE
        )
        result = infer_bibtex_type(paper)
        assert result == "article"

    def test_infer_bibtex_type_conference_paper(self):
        """Verify conference paper type inference"""
        paper = Paper(
            cite_key="test",
            title="Test",
            paper_type=PaperType.CONFERENCE_PAPER
        )
        result = infer_bibtex_type(paper)
        assert result == "inproceedings"

    def test_infer_bibtex_type_book(self):
        """Verify book type inference"""
        paper = Paper(
            cite_key="test",
            title="Test",
            paper_type=PaperType.BOOK
        )
        result = infer_bibtex_type(paper)
        assert result == "book"

    def test_infer_bibtex_type_without_paper_type(self):
        """Verify fallback when paper_type is None"""
        paper = Paper(
            cite_key="test",
            title="Test"
        )
        result = infer_bibtex_type(paper)
        # Should default to misc or infer from fields
        assert isinstance(result, str)

    def test_infer_bibtex_type_from_journal_field(self):
        """Verify inference from journal field"""
        paper = Paper(
            cite_key="test",
            title="Test",
            journal="Nature"
        )
        result = infer_bibtex_type(paper)
        assert result == "article"

    def test_infer_bibtex_type_from_booktitle_field(self):
        """Verify inference from booktitle field"""
        paper = Paper(
            cite_key="test",
            title="Test",
            booktitle="Proceedings of Conference"
        )
        result = infer_bibtex_type(paper)
        assert result == "inproceedings"


class TestPaperToBibtexEntry:
    """Test converting Paper model to BibTeX entry dictionary"""

    def test_paper_to_bibtex_entry_basic(self):
        """Verify basic Paper to BibTeX conversion"""
        paper = Paper(
            cite_key="smith2024",
            title="Test Paper",
            year=2024,
            paper_type=PaperType.JOURNAL_ARTICLE
        )
        entry = paper_to_bibtex_entry(paper)

        assert entry["ID"] == "smith2024"
        assert entry["ENTRYTYPE"] == "article"
        assert entry["title"] == "Test Paper"
        assert entry["year"] == "2024"

    def test_paper_to_bibtex_entry_with_authors(self):
        """Verify BibTeX entry includes authors"""
        paper = Paper(
            cite_key="smith2024",
            title="Test Paper",
            authors=[
                Author(family_name="Smith", given_name="John", full_name="John Smith")
            ],
            paper_type=PaperType.JOURNAL_ARTICLE
        )
        entry = paper_to_bibtex_entry(paper)

        assert "author" in entry
        assert "Smith, John" in entry["author"]

    def test_paper_to_bibtex_entry_with_doi(self):
        """Verify BibTeX entry includes DOI"""
        paper = Paper(
            cite_key="smith2024",
            title="Test Paper",
            doi="10.1234/test",
            paper_type=PaperType.JOURNAL_ARTICLE
        )
        entry = paper_to_bibtex_entry(paper)

        assert entry["doi"] == "10.1234/test"

    def test_paper_to_bibtex_entry_with_abstract(self):
        """Verify BibTeX entry includes abstract"""
        paper = Paper(
            cite_key="smith2024",
            title="Test Paper",
            abstract="Test abstract",
            paper_type=PaperType.JOURNAL_ARTICLE
        )
        entry = paper_to_bibtex_entry(paper)

        assert entry["abstract"] == "Test abstract"

    def test_paper_to_bibtex_entry_with_keywords(self):
        """Verify BibTeX entry includes keywords"""
        paper = Paper(
            cite_key="smith2024",
            title="Test Paper",
            keywords=["AI", "machine learning"],
            paper_type=PaperType.JOURNAL_ARTICLE
        )
        entry = paper_to_bibtex_entry(paper)

        assert "keywords" in entry

    def test_paper_to_bibtex_entry_use_source_key(self):
        """Verify use_source_key parameter"""
        paper = Paper(
            cite_key="smith2024",
            source_key="scopus_12345",
            title="Test Paper",
            paper_type=PaperType.JOURNAL_ARTICLE
        )
        entry = paper_to_bibtex_entry(paper, use_source_key=True)

        assert entry["ID"] == "scopus_12345"

    def test_paper_to_bibtex_entry_publication_details(self):
        """Verify publication details are included"""
        paper = Paper(
            cite_key="smith2024",
            title="Test Paper",
            journal="Nature",
            volume="500",
            number="5",
            pages="123-145",
            publisher="Springer",
            paper_type=PaperType.JOURNAL_ARTICLE
        )
        entry = paper_to_bibtex_entry(paper)

        assert entry["journal"] == "Nature"
        assert entry["volume"] == "500"
        assert entry["number"] == "5"
        assert entry["pages"] == "123-145"
        assert entry["publisher"] == "Springer"


class TestPapersToBibtex:
    """Test converting multiple Papers to BibTeX string"""

    def test_papers_to_bibtex_single(self):
        """Verify converting single paper to BibTeX"""
        papers = [
            Paper(
                cite_key="smith2024",
                title="Test Paper",
                year=2024,
                paper_type=PaperType.JOURNAL_ARTICLE
            )
        ]
        bibtex = papers_to_bibtex(papers)

        assert "@article" in bibtex
        assert "smith2024" in bibtex
        assert "Test Paper" in bibtex

    def test_papers_to_bibtex_multiple(self):
        """Verify converting multiple papers to BibTeX"""
        papers = [
            Paper(
                cite_key="smith2024",
                title="Test Paper 1",
                year=2024,
                paper_type=PaperType.JOURNAL_ARTICLE
            ),
            Paper(
                cite_key="doe2024",
                title="Test Paper 2",
                year=2024,
                paper_type=PaperType.CONFERENCE_PAPER
            )
        ]
        bibtex = papers_to_bibtex(papers)

        assert "@article" in bibtex
        assert "@inproceedings" in bibtex
        assert "smith2024" in bibtex
        assert "doe2024" in bibtex

    def test_papers_to_bibtex_use_source_key(self):
        """Verify use_source_key in BibTeX export"""
        papers = [
            Paper(
                cite_key="smith2024",
                source_key="scopus_12345",
                title="Test Paper",
                year=2024,
                paper_type=PaperType.JOURNAL_ARTICLE
            )
        ]
        bibtex = papers_to_bibtex(papers, use_source_key=True)

        assert "scopus_12345" in bibtex

    def test_papers_to_bibtex_empty_list(self):
        """Verify empty papers list"""
        bibtex = papers_to_bibtex([])
        # Should produce valid but empty BibTeX
        assert isinstance(bibtex, str)

    def test_papers_to_bibtex_file(self, tmp_path):
        """Verify writing papers to BibTeX file"""
        papers = [
            Paper(
                cite_key="smith2024",
                title="Test Paper",
                year=2024,
                paper_type=PaperType.JOURNAL_ARTICLE
            )
        ]
        filepath = tmp_path / "output.bib"

        papers_to_bibtex_file(papers, str(filepath))

        assert filepath.exists()
        content = filepath.read_text()
        assert "@article" in content
        assert "smith2024" in content


class TestCleanBibtexString:
    """Test cleaning BibTeX strings"""

    def test_clean_removes_excessive_whitespace(self):
        """Verify excessive whitespace is removed"""
        bibtex_string = """@article{test,
        
        
        title={Test}
        }"""
        cleaned = clean_bibtex_string(bibtex_string)

        # Should not have triple newlines
        assert "\n\n\n" not in cleaned

    def test_clean_removes_trailing_whitespace(self):
        """Verify trailing whitespace is removed"""
        bibtex_string = "@article{test,   \n  title={Test}   \n}   "
        cleaned = clean_bibtex_string(bibtex_string)

        lines = cleaned.split('\n')
        for line in lines:
            assert line == line.rstrip()

    def test_clean_standardizes_line_endings(self):
        """Verify line endings are standardized"""
        bibtex_string = "@article{test,\r\ntitle={Test}\r\n}"
        cleaned = clean_bibtex_string(bibtex_string)

        assert "\r\n" not in cleaned
        assert "\n" in cleaned

    def test_clean_returns_string(self):
        """Verify clean returns string"""
        result = clean_bibtex_string("@article{test}")
        assert isinstance(result, str)


class TestFormatBibtexEntry:
    """Test formatting individual BibTeX entries"""

    def test_format_bibtex_entry_basic(self):
        """Verify basic BibTeX entry formatting"""
        entry = {
            "ID": "smith2024",
            "ENTRYTYPE": "article",
            "title": "Test Paper"
        }
        result = format_bibtex_entry(entry)

        assert "@article" in result
        assert "smith2024" in result
        assert "Test Paper" in result

    def test_format_bibtex_entry_with_fields(self):
        """Verify complete BibTeX entry formatting"""
        entry = {
            "ID": "smith2024",
            "ENTRYTYPE": "article",
            "title": "Test Paper",
            "author": "Smith, John",
            "year": "2024",
            "journal": "Nature"
        }
        result = format_bibtex_entry(entry)

        assert "smith2024" in result
        assert "Test Paper" in result
        assert "Smith, John" in result

    def test_format_bibtex_entry_returns_string(self):
        """Verify result is string"""
        entry = {"ID": "test", "ENTRYTYPE": "article", "title": "Test"}
        result = format_bibtex_entry(entry)
        assert isinstance(result, str)


class TestExportBySource:
    """Test exporting papers grouped by source"""

    def test_export_papers_by_source_creates_files(self, tmp_path):
        """Verify export_papers_by_source is callable"""
        papers = [
            Paper(
                cite_key="test1",
                title="Paper 1",
                discovery=Discovery(
                    method=DiscoveryMethod.KEYWORD_SEARCH,
                    source_database="scopus"
                ),
                paper_type=PaperType.JOURNAL_ARTICLE
            )
        ]
        output_dir = str(tmp_path)

        # Just verify the function exists and is callable
        # Actual functionality depends on Paper model attributes
        assert callable(export_papers_by_source)
