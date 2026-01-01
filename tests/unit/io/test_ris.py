"""
Unit tests for RIS format parser
Tests parsing, normalization, and Paper model conversion
"""

import pytest
from pathlib import Path

from paper_scanner.io.ris import (
    RISParser,
    RISRecord,
    ris_file_to_papers,
    ris_to_papers,
    infer_paper_type_ris,
)
from paper_scanner.core.enum import PaperType, DiscoveryMethod


class TestRISRecord:
    """Test RISRecord data structure"""

    def test_single_field(self):
        """Test adding single field"""
        record = RISRecord()
        record.add_field("T1", "Test Title")
        assert record.get("T1") == "Test Title"

    def test_multi_value_field(self):
        """Test adding multiple values to same field"""
        record = RISRecord()
        record.add_field("AU", "Smith, John")
        record.add_field("AU", "Doe, Jane")
        
        values = record.get_list("AU")
        assert len(values) == 2
        assert "Smith, John" in values
        assert "Doe, Jane" in values

    def test_get_list_empty(self):
        """Test get_list on empty field"""
        record = RISRecord()
        assert record.get_list("NONEXISTENT") == []

    def test_get_list_single_value(self):
        """Test get_list converts single value to list"""
        record = RISRecord()
        record.add_field("KW", "keyword1")
        assert record.get_list("KW") == ["keyword1"]


class TestPaperTypeInference:
    """Test RIS publication type to PaperType conversion"""

    def test_infer_journal_article(self):
        """Test inferring journal article"""
        assert infer_paper_type_ris("JOUR") == PaperType.JOURNAL_ARTICLE
        assert infer_paper_type_ris("jour") == PaperType.JOURNAL_ARTICLE

    def test_infer_conference_paper(self):
        """Test inferring conference paper"""
        assert infer_paper_type_ris("CONF") == PaperType.CONFERENCE_PAPER
        assert infer_paper_type_ris("CPAPER") == PaperType.CONFERENCE_PAPER

    def test_infer_book(self):
        """Test inferring book"""
        assert infer_paper_type_ris("BOOK") == PaperType.BOOK

    def test_infer_book_chapter(self):
        """Test inferring book chapter"""
        assert infer_paper_type_ris("CHAP") == PaperType.BOOK_CHAPTER

    def test_infer_thesis(self):
        """Test inferring thesis"""
        assert infer_paper_type_ris("THES") == PaperType.THESIS
        assert infer_paper_type_ris("PHDTHESIS") == PaperType.THESIS

    def test_infer_default_other(self):
        """Test that unknown types default to OTHER"""
        assert infer_paper_type_ris("UNKNOWN") == PaperType.OTHER
        assert infer_paper_type_ris("") == PaperType.OTHER


class TestRISParser:
    """Test RIS file parser"""

    def test_parse_simple_record(self, tmp_path):
        """Test parsing simple RIS record"""
        ris_file = tmp_path / "test.ris"
        ris_file.write_text("""TY  - JOUR
T1  - Test Title
AU  - Smith, John
PY  - 2025
ER  - """)
        
        records = RISParser.parse_file(str(ris_file))
        assert len(records) == 1
        assert records[0].get("T1") == "Test Title"
        assert records[0].get("PY") == "2025"

    def test_parse_multiple_records(self, tmp_path):
        """Test parsing multiple RIS records"""
        ris_file = tmp_path / "test.ris"
        ris_file.write_text("""TY  - JOUR
T1  - Title 1
ER  - 

TY  - JOUR
T1  - Title 2
ER  - """)
        
        records = RISParser.parse_file(str(ris_file))
        assert len(records) == 2
        assert records[0].get("T1") == "Title 1"
        assert records[1].get("T1") == "Title 2"

    def test_parse_multi_value_fields(self, tmp_path):
        """Test parsing records with multi-value fields"""
        ris_file = tmp_path / "test.ris"
        ris_file.write_text("""TY  - JOUR
T1  - Test Title
AU  - Smith, John
AU  - Doe, Jane
KW  - keyword1
KW  - keyword2
ER  - """)
        
        records = RISParser.parse_file(str(ris_file))
        assert len(records[0].get_list("AU")) == 2
        assert len(records[0].get_list("KW")) == 2


class TestRISToPapers:
    """Test RIS to Paper model conversion"""

    def test_convert_simple_record(self):
        """Test converting simple RIS record to Paper"""
        ris_string = """TY  - JOUR
T1  - Test Article
AU  - Smith, John
AB  - This is a test abstract.
JF  - Test Journal
PY  - 2025
DO  - 10.1234/test
ER  - """
        
        papers = ris_to_papers(ris_string)
        assert len(papers) == 1
        
        paper = papers[0]
        assert paper.title == "Test Article"
        assert paper.year == 2025
        assert len(paper.authors) == 1
        assert paper.authors[0].family_name == "Smith"
        assert paper.journal == "Test Journal"
        assert paper.doi == "10.1234/test"

    def test_convert_record_with_keywords(self):
        """Test converting record with keywords"""
        ris_string = """TY  - JOUR
T1  - Test Title
KW  - keyword1
KW  - keyword2
KW  - keyword3
ER  - """
        
        papers = ris_to_papers(ris_string)
        assert len(papers[0].keywords) == 3

    def test_convert_cite_key_from_accession_number(self):
        """Test cite_key generated from accession number"""
        ris_string = """TY  - JOUR
T1  - Test Title
AN  - 3282856007
ER  - """
        
        papers = ris_to_papers(ris_string)
        assert papers[0].source_key == "ris_an_3282856007"
        assert papers[0].cite_key == "ris_an_3282856007"

    def test_convert_cite_key_from_doi(self):
        """Test cite_key generated from DOI when no accession number"""
        ris_string = """TY  - JOUR
T1  - Test Title
DO  - 10.1234/test
ER  - """
        
        papers = ris_to_papers(ris_string)
        assert papers[0].source_key == "ris_doi_10.1234/test"
        assert papers[0].cite_key == "ris_doi_10.1234/test"

    def test_convert_cite_key_auto_generated(self):
        """Test cite_key auto-generated from title and author"""
        ris_string = """TY  - JOUR
T1  - Test Title
AU  - Smith, John
ER  - """
        
        papers = ris_to_papers(ris_string)
        assert papers[0].source_key.startswith("ris_auto_")
        assert papers[0].cite_key == papers[0].source_key

    def test_missing_title_raises_error(self):
        """Test that missing title raises error"""
        ris_string = """TY  - JOUR
AU  - Smith, John
ER  - """
        
        # ris_to_papers catches and skips invalid records, returns empty list
        papers = ris_to_papers(ris_string)
        assert len(papers) == 0

    def test_convert_multiple_records(self):
        """Test converting multiple records"""
        ris_string = """TY  - JOUR
T1  - Title 1
AU  - Smith, John
ER  - 

TY  - JOUR
T1  - Title 2
AU  - Doe, Jane
ER  - """
        
        papers = ris_to_papers(ris_string)
        assert len(papers) == 2
        assert papers[0].title == "Title 1"
        assert papers[1].title == "Title 2"


class TestRISFileToPapers:
    """Test loading RIS files"""

    def test_load_ris_file(self, tmp_path):
        """Test loading RIS file"""
        ris_file = tmp_path / "test.ris"
        ris_file.write_text("""TY  - JOUR
T1  - Test Article
AU  - Smith, John
PY  - 2025
ER  - """)
        
        papers = ris_file_to_papers(str(ris_file))
        assert len(papers) == 1
        assert papers[0].title == "Test Article"
        # Default discovery method should be KEYWORD_SEARCH
        assert papers[0].discovery.method == DiscoveryMethod.KEYWORD_SEARCH

    def test_load_ris_file_with_source_database(self, tmp_path):
        """Test loading RIS file with source database"""
        ris_file = tmp_path / "test.ris"
        ris_file.write_text("""TY  - JOUR
T1  - Test Article
ER  - """)
        
        papers = ris_file_to_papers(
            str(ris_file),
            source_database="ProQuest"
        )
        assert papers[0].discovery.source_database == "ProQuest"
