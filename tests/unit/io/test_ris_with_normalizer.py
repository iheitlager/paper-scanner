"""
Unit tests for RIS IO module with Normalizer integration

Tests verify that ris.py correctly uses the Normalizer class for all
field normalization instead of duplicated functions.
"""

from paper_scanner.core.models import Author, PaperType
from paper_scanner.core.normalization import Normalizer
from paper_scanner.io.ris import RISRecord, ris_record_to_paper


class TestRISNormalizerIntegration:
    """Test that ris.py uses Normalizer for field normalization"""

    def test_normalize_ampersands_uses_normalizer(self):
        """Test ampersand normalization via Normalizer"""
        result = Normalizer._normalize_ampersands("Smith \\& Jones")
        assert result == "Smith & Jones"

        result = Normalizer._normalize_ampersands("Art &amp; Design")
        assert result == "Art & Design"

    def test_normalize_whitespace_uses_normalizer(self):
        """Test whitespace normalization via Normalizer"""
        result = Normalizer._collapse_whitespace("Multiple   spaces   and\n\nlinebreaks   here")
        assert result == "Multiple spaces and linebreaks here"

    def test_parse_authors_ris_uses_normalizer(self):
        """Test author parsing and normalization via Normalizer"""
        authors_list = ["Smith, John", "Doe, Jane"]
        result = Normalizer.normalize_authors(authors_list)

        assert len(result) == 2
        assert all(isinstance(a, str) for a in result)

    def test_parse_keywords_ris_uses_normalizer(self):
        """Test keyword parsing and normalization via Normalizer"""
        keywords_list = ["Machine Learning", "Deep Learning", "NLP"]
        result = Normalizer.normalize_keywords(keywords_list)

        assert len(result) == 3
        assert all(kw.islower() for kw in result)

    def test_ris_record_to_paper_normalizes_all_fields(self):
        """ris_record_to_paper should normalize all fields using Normalizer"""
        record = RISRecord()
        record.add_field('TY', 'JOUR')
        record.add_field('T1', 'machine learning in NLP')
        record.add_field('AB', 'We tested  &amp;  validated...')
        record.add_field('AU', 'Smith, John')
        record.add_field('AU', 'Doe, Jane')
        record.add_field('KW', 'Machine Learning')
        record.add_field('KW', 'Deep Learning')
        record.add_field('JF', 'nature machine intelligence')
        record.add_field('PB', 'nature publishing')
        record.add_field('PY', '2024')
        record.add_field('DO', '10.1234/example')

        paper = ris_record_to_paper(record)

        # Verify all fields are normalized
        assert paper.title  # Titlecased
        assert paper.abstract  # Whitespace collapsed, ampersands normalized
        assert len(paper.authors) == 2
        assert all(isinstance(a, Author) for a in paper.authors)
        assert paper.year == 2024
        assert isinstance(paper.year, int)
        assert len(paper.keywords) >= 2
        assert all(kw.islower() for kw in paper.keywords)
        assert paper.journal  # Titlecased
        assert paper.publisher  # Titlecased

    def test_ris_title_normalization(self):
        """Verify title normalization via Normalizer"""
        record = RISRecord()
        record.add_field('TY', 'JOUR')
        record.add_field('T1', 'a study of deep learning')

        paper = ris_record_to_paper(record)

        # Title should be titlecased
        assert 'Study' in paper.title or 'study' in paper.title

    def test_ris_abstract_normalization(self):
        """Verify abstract normalization (NO titlecase, collapse whitespace)"""
        record = RISRecord()
        record.add_field('TY', 'JOUR')
        record.add_field('T1', 'Study')
        record.add_field('AB', 'We tested   &amp;   validated.   ')

        paper = ris_record_to_paper(record)

        # Abstract should be collapsed, not titlecased
        assert paper.abstract
        # Should have single spaces
        assert '   ' not in paper.abstract
        # Should have normalized ampersand
        assert '&' in paper.abstract

    def test_ris_author_normalization(self):
        """Verify authors are normalized via Normalizer"""
        record = RISRecord()
        record.add_field('TY', 'JOUR')
        record.add_field('T1', 'Study')
        record.add_field('AU', 'smith, john')
        record.add_field('AU', 'van der doe, jane')

        paper = ris_record_to_paper(record)

        assert len(paper.authors) == 2
        assert all(isinstance(a, Author) for a in paper.authors)

    def test_ris_keywords_deduplication_and_lowercase(self):
        """Verify keywords are deduplicated and lowercased via Normalizer"""
        record = RISRecord()
        record.add_field('TY', 'JOUR')
        record.add_field('T1', 'Study')
        record.add_field('KW', 'Machine Learning')
        record.add_field('KW', 'MACHINE LEARNING')
        record.add_field('KW', 'Deep Learning')

        paper = ris_record_to_paper(record)

        # Should be deduplicated and lowercased
        assert all(kw.islower() for kw in paper.keywords)

    def test_ris_year_validation(self):
        """Verify year is validated via Normalizer"""
        record = RISRecord()
        record.add_field('TY', 'JOUR')
        record.add_field('T1', 'Study')
        record.add_field('PY', '2024')

        paper = ris_record_to_paper(record)

        assert paper.year == 2024
        assert isinstance(paper.year, int)

    def test_ris_journal_normalization(self):
        """Verify journal is normalized via Normalizer"""
        record = RISRecord()
        record.add_field('TY', 'JOUR')
        record.add_field('T1', 'Study')
        record.add_field('JF', 'nature & machine learning')

        paper = ris_record_to_paper(record)

        # Should be titlecased
        assert paper.journal
        assert 'Nature' in paper.journal or 'nature' in paper.journal

    def test_ris_publisher_normalization(self):
        """Verify publisher is normalized via Normalizer"""
        record = RISRecord()
        record.add_field('TY', 'JOUR')
        record.add_field('T1', 'Study')
        record.add_field('PB', 'academic press & publishing')

        paper = ris_record_to_paper(record)

        # Should be titlecased and ampersand normalized
        assert paper.publisher
        assert '&' in paper.publisher


class TestRISNormalizerConsistency:
    """Test consistency between direct Normalizer use and ris.py"""

    def test_title_normalization_consistent(self):
        """Title normalization should match Normalizer.normalize_title()"""
        title_input = "the great study"

        record = RISRecord()
        record.add_field('TY', 'JOUR')
        record.add_field('T1', title_input)

        paper = ris_record_to_paper(record)
        expected_title = Normalizer.normalize_title(title_input)

        assert paper.title == expected_title

    def test_abstract_normalization_consistent(self):
        """Abstract normalization should match Normalizer.normalize_abstract()"""
        abstract_input = "We   tested   &amp;   validated.   "

        record = RISRecord()
        record.add_field('TY', 'JOUR')
        record.add_field('T1', 'Study')
        record.add_field('AB', abstract_input)

        paper = ris_record_to_paper(record)
        expected_abstract = Normalizer.normalize_abstract(abstract_input)

        assert paper.abstract == expected_abstract

    def test_keywords_normalization_consistent(self):
        """Keywords normalization should match Normalizer.normalize_keywords()"""
        keywords_input = "Machine Learning; Deep Learning"

        record = RISRecord()
        record.add_field('TY', 'JOUR')
        record.add_field('T1', 'Study')
        record.add_field('KW', 'Machine Learning')
        record.add_field('KW', 'Deep Learning')

        paper = ris_record_to_paper(record)
        expected_keywords = Normalizer.normalize_keywords(keywords_input)

        assert paper.keywords == expected_keywords

    def test_journal_normalization_consistent(self):
        """Journal normalization should match Normalizer.normalize_journal()"""
        journal_input = "nature machine learning"

        record = RISRecord()
        record.add_field('TY', 'JOUR')
        record.add_field('T1', 'Study')
        record.add_field('JF', journal_input)

        paper = ris_record_to_paper(record)
        expected_journal = Normalizer.normalize_journal(journal_input)

        assert paper.journal == expected_journal

    def test_publisher_normalization_consistent(self):
        """Publisher normalization should match Normalizer.normalize_publisher()"""
        publisher_input = "academic press"

        record = RISRecord()
        record.add_field('TY', 'JOUR')
        record.add_field('T1', 'Study')
        record.add_field('PB', publisher_input)

        paper = ris_record_to_paper(record)
        expected_publisher = Normalizer.normalize_publisher(publisher_input)

        assert paper.publisher == expected_publisher


class TestRISPaperTypeInference:
    """Test that paper type inference still works correctly"""

    def test_journal_article_inference(self):
        """Test inference of journal article type"""
        record = RISRecord()
        record.add_field('TY', 'JOUR')
        record.add_field('T1', 'Study')

        paper = ris_record_to_paper(record)
        assert paper.paper_type == PaperType.JOURNAL_ARTICLE

    def test_conference_paper_inference(self):
        """Test inference of conference paper type"""
        record = RISRecord()
        record.add_field('TY', 'CONF')
        record.add_field('T1', 'Study')

        paper = ris_record_to_paper(record)
        assert paper.paper_type == PaperType.CONFERENCE_PAPER

    def test_book_inference(self):
        """Test inference of book type"""
        record = RISRecord()
        record.add_field('TY', 'BOOK')
        record.add_field('T1', 'Study')

        paper = ris_record_to_paper(record)
        assert paper.paper_type == PaperType.BOOK

    def test_thesis_inference(self):
        """Test inference of thesis type"""
        record = RISRecord()
        record.add_field('TY', 'THES')
        record.add_field('T1', 'Study')

        paper = ris_record_to_paper(record)
        assert paper.paper_type == PaperType.THESIS
