"""
Unit tests for PaperTypeTranslator in tools/documents
"""

import pytest
from paper_scanner.tools.documents import PaperTypeTranslator
from paper_scanner.core.enum import PaperType


class TestPaperTypeTranslator:
    """Test suite for PaperTypeTranslator class"""

    # ====================================================================
    # Tests for from_crossref method
    # ====================================================================

    def test_from_crossref_journal_article(self):
        """Test translating Crossref journal-article type"""
        result = PaperTypeTranslator.from_crossref("journal-article")
        assert result == PaperType.ARTICLE

    def test_from_crossref_article_underscore(self):
        """Test translating Crossref article_article type (underscore variant)"""
        result = PaperTypeTranslator.from_crossref("journal_article")
        assert result == PaperType.ARTICLE

    def test_from_crossref_proceedings_article(self):
        """Test translating Crossref proceedings-article type"""
        result = PaperTypeTranslator.from_crossref("proceedings-article")
        assert result == PaperType.CONFERENCE

    def test_from_crossref_conference_paper(self):
        """Test translating Crossref conference-paper type"""
        result = PaperTypeTranslator.from_crossref("conference-paper")
        assert result == PaperType.CONFERENCE

    def test_from_crossref_inproceedings(self):
        """Test translating Crossref inproceedings type"""
        result = PaperTypeTranslator.from_crossref("inproceedings")
        assert result == PaperType.CONFERENCE

    def test_from_crossref_book(self):
        """Test translating Crossref book type"""
        result = PaperTypeTranslator.from_crossref("book")
        assert result == PaperType.BOOK

    def test_from_crossref_book_chapter(self):
        """Test translating Crossref book-chapter type"""
        result = PaperTypeTranslator.from_crossref("book-chapter")
        assert result == PaperType.BOOK_CHAPTER

    def test_from_crossref_chapter(self):
        """Test translating Crossref chapter type"""
        result = PaperTypeTranslator.from_crossref("chapter")
        assert result == PaperType.BOOK_CHAPTER

    def test_from_crossref_thesis(self):
        """Test translating Crossref thesis type"""
        result = PaperTypeTranslator.from_crossref("thesis")
        assert result == PaperType.THESIS

    def test_from_crossref_dissertation(self):
        """Test translating Crossref dissertation type"""
        result = PaperTypeTranslator.from_crossref("dissertation")
        assert result == PaperType.THESIS

    def test_from_crossref_report(self):
        """Test translating Crossref report type"""
        result = PaperTypeTranslator.from_crossref("report")
        assert result == PaperType.TECHNICAL_REPORT

    def test_from_crossref_technical_report(self):
        """Test translating Crossref technical-report type"""
        result = PaperTypeTranslator.from_crossref("technical-report")
        assert result == PaperType.TECHNICAL_REPORT

    def test_from_crossref_working_paper(self):
        """Test translating Crossref working-paper type"""
        result = PaperTypeTranslator.from_crossref("working-paper")
        assert result == PaperType.WORKING_PAPER

    def test_from_crossref_preprint(self):
        """Test translating Crossref preprint type"""
        result = PaperTypeTranslator.from_crossref("preprint")
        assert result == PaperType.PREPRINT

    def test_from_crossref_arxiv(self):
        """Test translating Crossref arxiv type"""
        result = PaperTypeTranslator.from_crossref("arxiv")
        assert result == PaperType.PREPRINT

    def test_from_crossref_patent(self):
        """Test translating Crossref patent type"""
        result = PaperTypeTranslator.from_crossref("patent")
        assert result == PaperType.PATENT

    def test_from_crossref_misc(self):
        """Test translating Crossref misc type"""
        result = PaperTypeTranslator.from_crossref("misc")
        assert result == PaperType.OTHER

    def test_from_crossref_unknown_type(self):
        """Test translating unknown Crossref type defaults to OTHER"""
        result = PaperTypeTranslator.from_crossref("unknown-type-xyz")
        assert result == PaperType.OTHER

    def test_from_crossref_none(self):
        """Test translating None input"""
        result = PaperTypeTranslator.from_crossref(None)
        assert result == PaperType.OTHER

    def test_from_crossref_empty_string(self):
        """Test translating empty string"""
        result = PaperTypeTranslator.from_crossref("")
        assert result == PaperType.OTHER

    def test_from_crossref_case_insensitive(self):
        """Test that Crossref translation is case-insensitive"""
        result1 = PaperTypeTranslator.from_crossref("JOURNAL-ARTICLE")
        result2 = PaperTypeTranslator.from_crossref("Journal-Article")
        result3 = PaperTypeTranslator.from_crossref("journal-article")
        assert result1 == result2 == result3 == PaperType.ARTICLE

    def test_from_crossref_whitespace_handling(self):
        """Test that Crossref translation handles whitespace"""
        result = PaperTypeTranslator.from_crossref("  journal-article  ")
        assert result == PaperType.ARTICLE

    # ====================================================================
    # Tests for from_bibtex method
    # ====================================================================

    def test_from_bibtex_article(self):
        """Test translating BibTeX article type"""
        result = PaperTypeTranslator.from_bibtex("article")
        assert result == PaperType.ARTICLE

    def test_from_bibtex_article_with_at(self):
        """Test translating BibTeX @article type"""
        result = PaperTypeTranslator.from_bibtex("@article")
        assert result == PaperType.ARTICLE

    def test_from_bibtex_inproceedings(self):
        """Test translating BibTeX inproceedings type"""
        result = PaperTypeTranslator.from_bibtex("inproceedings")
        assert result == PaperType.CONFERENCE

    def test_from_bibtex_inproceedings_with_at(self):
        """Test translating BibTeX @inproceedings type"""
        result = PaperTypeTranslator.from_bibtex("@inproceedings")
        assert result == PaperType.CONFERENCE

    def test_from_bibtex_conference(self):
        """Test translating BibTeX conference type"""
        result = PaperTypeTranslator.from_bibtex("conference")
        assert result == PaperType.CONFERENCE

    def test_from_bibtex_book(self):
        """Test translating BibTeX book type"""
        result = PaperTypeTranslator.from_bibtex("book")
        assert result == PaperType.BOOK

    def test_from_bibtex_inbook(self):
        """Test translating BibTeX inbook type"""
        result = PaperTypeTranslator.from_bibtex("inbook")
        assert result == PaperType.BOOK_CHAPTER

    def test_from_bibtex_incollection(self):
        """Test translating BibTeX incollection type"""
        result = PaperTypeTranslator.from_bibtex("incollection")
        assert result == PaperType.BOOK_CHAPTER

    def test_from_bibtex_phdthesis(self):
        """Test translating BibTeX phdthesis type"""
        result = PaperTypeTranslator.from_bibtex("phdthesis")
        assert result == PaperType.THESIS

    def test_from_bibtex_mastersthesis(self):
        """Test translating BibTeX mastersthesis type"""
        result = PaperTypeTranslator.from_bibtex("mastersthesis")
        assert result == PaperType.THESIS

    def test_from_bibtex_thesis(self):
        """Test translating BibTeX thesis type"""
        result = PaperTypeTranslator.from_bibtex("thesis")
        assert result == PaperType.THESIS

    def test_from_bibtex_techreport(self):
        """Test translating BibTeX techreport type"""
        result = PaperTypeTranslator.from_bibtex("techreport")
        assert result == PaperType.TECHNICAL_REPORT

    def test_from_bibtex_misc(self):
        """Test translating BibTeX misc type"""
        result = PaperTypeTranslator.from_bibtex("misc")
        assert result == PaperType.OTHER

    def test_from_bibtex_unknown(self):
        """Test translating unknown BibTeX type"""
        result = PaperTypeTranslator.from_bibtex("unknown")
        assert result == PaperType.OTHER

    def test_from_bibtex_none(self):
        """Test translating None input"""
        result = PaperTypeTranslator.from_bibtex(None)
        assert result == PaperType.OTHER

    def test_from_bibtex_empty_string(self):
        """Test translating empty string"""
        result = PaperTypeTranslator.from_bibtex("")
        assert result == PaperType.OTHER

    def test_from_bibtex_case_insensitive(self):
        """Test that BibTeX translation is case-insensitive"""
        result1 = PaperTypeTranslator.from_bibtex("ARTICLE")
        result2 = PaperTypeTranslator.from_bibtex("Article")
        result3 = PaperTypeTranslator.from_bibtex("article")
        assert result1 == result2 == result3 == PaperType.ARTICLE

    def test_from_bibtex_whitespace_handling(self):
        """Test that BibTeX translation handles whitespace"""
        result = PaperTypeTranslator.from_bibtex("  @article  ")
        assert result == PaperType.ARTICLE

    # ====================================================================
    # Tests for from_generic method
    # ====================================================================

    def test_from_generic_crossref_format(self):
        """Test generic translation with Crossref format"""
        result = PaperTypeTranslator.from_generic("journal-article")
        assert result == PaperType.ARTICLE

    def test_from_generic_bibtex_format(self):
        """Test generic translation with BibTeX format"""
        result = PaperTypeTranslator.from_generic("@article")
        assert result == PaperType.ARTICLE

    def test_from_generic_bibtex_without_at(self):
        """Test generic translation with BibTeX format without @"""
        result = PaperTypeTranslator.from_generic("inproceedings")
        assert result == PaperType.CONFERENCE

    def test_from_generic_enum_value(self):
        """Test generic translation with enum value"""
        result = PaperTypeTranslator.from_generic("article")
        assert result == PaperType.ARTICLE

    def test_from_generic_uppercase(self):
        """Test generic translation with uppercase"""
        result = PaperTypeTranslator.from_generic("ARTICLE")
        assert result == PaperType.ARTICLE

    def test_from_generic_mixed_case(self):
        """Test generic translation with mixed case"""
        result = PaperTypeTranslator.from_generic("Conference-Paper")
        assert result == PaperType.CONFERENCE

    def test_from_generic_unknown(self):
        """Test generic translation with unknown type"""
        result = PaperTypeTranslator.from_generic("xyz-unknown")
        assert result == PaperType.OTHER

    def test_from_generic_none(self):
        """Test generic translation with None"""
        result = PaperTypeTranslator.from_generic(None)
        assert result == PaperType.OTHER

    def test_from_generic_empty_string(self):
        """Test generic translation with empty string"""
        result = PaperTypeTranslator.from_generic("")
        assert result == PaperType.OTHER

    def test_from_generic_whitespace_only(self):
        """Test generic translation with whitespace only"""
        result = PaperTypeTranslator.from_generic("   ")
        assert result == PaperType.OTHER

    # ====================================================================
    # Tests for to_enum method with source parameter
    # ====================================================================

    def test_to_enum_with_crossref_source(self):
        """Test to_enum with crossref source"""
        result = PaperTypeTranslator.to_enum("journal-article", source="crossref")
        assert result == PaperType.ARTICLE

    def test_to_enum_with_bibtex_source(self):
        """Test to_enum with bibtex source"""
        result = PaperTypeTranslator.to_enum("@article", source="bibtex")
        assert result == PaperType.ARTICLE

    def test_to_enum_with_generic_source(self):
        """Test to_enum with generic source"""
        result = PaperTypeTranslator.to_enum("conference-paper", source="generic")
        assert result == PaperType.CONFERENCE

    def test_to_enum_default_source_is_generic(self):
        """Test that to_enum defaults to generic source"""
        result1 = PaperTypeTranslator.to_enum("journal-article")
        result2 = PaperTypeTranslator.to_enum("journal-article", source="generic")
        assert result1 == result2 == PaperType.ARTICLE

    def test_to_enum_crossref_prefers_crossref_mapping(self):
        """Test that crossref source uses Crossref mapping first"""
        # "article" is in both Crossref and BibTeX mappings
        result = PaperTypeTranslator.to_enum("article", source="crossref")
        assert result == PaperType.ARTICLE

    def test_to_enum_bibtex_prefers_bibtex_mapping(self):
        """Test that bibtex source uses BibTeX mapping first"""
        # "article" is in both Crossref and BibTeX mappings
        result = PaperTypeTranslator.to_enum("article", source="bibtex")
        assert result == PaperType.ARTICLE

    def test_to_enum_none_input(self):
        """Test to_enum with None input"""
        result = PaperTypeTranslator.to_enum(None)
        assert result == PaperType.OTHER

    def test_to_enum_empty_string(self):
        """Test to_enum with empty string"""
        result = PaperTypeTranslator.to_enum("")
        assert result == PaperType.OTHER

    # ====================================================================
    # Integration tests
    # ====================================================================

    def test_crossref_to_paper_type_mapping_comprehensive(self):
        """Test comprehensive Crossref type mappings"""
        mappings = {
            "journal-article": PaperType.ARTICLE,
            "proceedings-article": PaperType.CONFERENCE,
            "book-chapter": PaperType.BOOK_CHAPTER,
            "book": PaperType.BOOK,
            "thesis": PaperType.THESIS,
            "report": PaperType.TECHNICAL_REPORT,
            "working-paper": PaperType.WORKING_PAPER,
            "preprint": PaperType.PREPRINT,
            "patent": PaperType.PATENT,
        }
        
        for crossref_type, expected in mappings.items():
            result = PaperTypeTranslator.from_crossref(crossref_type)
            assert result == expected, f"Failed for {crossref_type}"

    def test_bibtex_to_paper_type_mapping_comprehensive(self):
        """Test comprehensive BibTeX type mappings"""
        mappings = {
            "article": PaperType.ARTICLE,
            "inproceedings": PaperType.CONFERENCE,
            "inbook": PaperType.BOOK_CHAPTER,
            "book": PaperType.BOOK,
            "phdthesis": PaperType.THESIS,
            "techreport": PaperType.TECHNICAL_REPORT,
        }
        
        for bibtex_type, expected in mappings.items():
            result = PaperTypeTranslator.from_bibtex(bibtex_type)
            assert result == expected, f"Failed for {bibtex_type}"

    def test_generic_fallback_order(self):
        """Test that generic detection tries Crossref first, then BibTeX"""
        # "article" exists in both mappings, should return article
        result = PaperTypeTranslator.from_generic("article")
        assert result == PaperType.ARTICLE
        
        # "inproceedings" exists in BibTeX, should be found
        result = PaperTypeTranslator.from_generic("inproceedings")
        assert result == PaperType.CONFERENCE

    def test_all_paper_types_have_mappings(self):
        """Test that all PaperType enum values have at least one mapping"""
        crossref_values = set(PaperTypeTranslator.CROSSREF_TO_PAPER_TYPE.values())
        bibtex_values = set(PaperTypeTranslator.BIBTEX_TO_PAPER_TYPE.values())
        all_mapped = crossref_values | bibtex_values
        
        for paper_type in PaperType:
            assert paper_type in all_mapped, f"No mapping for {paper_type}"

    def test_normalization_consistency(self):
        """Test that different input formats normalize to same result"""
        formats = [
            "journal-article",
            "JOURNAL-ARTICLE",
            "Journal-Article",
            "  journal-article  ",
        ]
        
        results = [PaperTypeTranslator.from_crossref(fmt) for fmt in formats]
        assert all(r == PaperType.ARTICLE for r in results)
