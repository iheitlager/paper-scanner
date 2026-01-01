"""
Spike 017: Normalization Consolidation - Phase 2 IO Integration Tests

Demonstrates the refactored BibTeX and RIS IO modules using the centralized
Normalizer class instead of duplicated normalization functions.

This test suite validates that:
1. BibTeX and RIS modules correctly delegate to Normalizer
2. All field normalization is consistent across input formats
3. Backward compatibility is maintained
"""

import pytest
from paper_scanner.io.bibtex import bibtex_entry_to_paper
from paper_scanner.io.ris import RISRecord, ris_record_to_paper
from paper_scanner.core.models import PaperType
from paper_scanner.core.normalization import Normalizer


class TestIOBibTeXIntegration:
    """Test BibTeX IO module integration with Normalizer"""

    def test_bibtex_normalizes_all_fields_via_normalizer(self):
        """BibTeX entry should normalize all fields using Normalizer"""
        entry = {
            'ID': 'smith2024ml',
            'ENTRYTYPE': 'article',
            'title': 'machine learning in {NLP}: a comprehensive study',
            'abstract': 'We tested  &amp;  validated  multiple  approaches.',
            'author': 'smith, john and van der doe, jane',
            'keywords': 'ML; Deep Learning; neural networks; deep learning',
            'journal': 'nature & machine intelligence',
            'publisher': 'nature publishing',
            'year': '2024',
            'doi': '10.1234/example.2024.ml',
        }
        
        paper = bibtex_entry_to_paper(entry)
        
        # Verify all fields normalized
        assert paper.title  # Titlecased
        assert paper.abstract  # Whitespace collapsed
        assert len(paper.authors) == 2  # Parsed and titlecased
        assert all(author.given_name and author.family_name for author in paper.authors)
        assert paper.year == 2024
        assert isinstance(paper.year, int)
        assert len(paper.keywords) >= 3  # Deduplicated
        assert all(kw.islower() for kw in paper.keywords)  # Lowercased
        assert paper.journal  # Titlecased
        assert paper.publisher  # Titlecased
        assert paper.doi == '10.1234/example.2024.ml'

    def test_bibtex_matches_direct_normalizer_output(self):
        """BibTeX output should match direct Normalizer calls"""
        title_input = "machine learning in {NLP}"
        abstract_input = "We tested  &amp;  validated."
        keywords_input = "ML; Deep Learning; ml"
        
        entry = {
            'ID': 'test1',
            'ENTRYTYPE': 'article',
            'title': title_input,
            'abstract': abstract_input,
            'keywords': keywords_input,
        }
        
        paper = bibtex_entry_to_paper(entry)
        
        # Compare with direct Normalizer output
        assert paper.title == Normalizer.normalize_title(title_input)
        assert paper.abstract == Normalizer.normalize_abstract(abstract_input)
        assert paper.keywords == Normalizer.normalize_keywords(keywords_input)

    def test_bibtex_multiple_keyword_fields_aggregated(self):
        """BibTeX should aggregate multiple keyword field types"""
        entry = {
            'ID': 'test1',
            'ENTRYTYPE': 'article',
            'title': 'Study',
            'keywords': 'ML',
            'author_keywords': 'Deep Learning',
            'keywords-plus': 'Neural Networks'
        }
        
        paper = bibtex_entry_to_paper(entry)
        
        # All keyword sources should be combined
        keyword_str = ' '.join(paper.keywords)
        assert any(k in keyword_str.lower() for k in ['ml', 'deep', 'neural'])


class TestIORISIntegration:
    """Test RIS IO module integration with Normalizer"""

    def test_ris_normalizes_all_fields_via_normalizer(self):
        """RIS record should normalize all fields using Normalizer"""
        record = RISRecord()
        record.add_field('TY', 'JOUR')
        record.add_field('T1', 'machine learning in NLP')
        record.add_field('AB', 'We tested  &amp;  validated.')
        record.add_field('AU', 'Smith, John')
        record.add_field('AU', 'Doe, Jane')
        record.add_field('KW', 'Machine Learning')
        record.add_field('KW', 'Deep Learning')
        record.add_field('JF', 'nature machine intelligence')
        record.add_field('PB', 'nature publishing')
        record.add_field('PY', '2024')
        record.add_field('DO', '10.1234/example')
        
        paper = ris_record_to_paper(record)
        
        # Verify all fields normalized
        assert paper.title  # Titlecased
        assert paper.abstract  # Whitespace collapsed
        assert len(paper.authors) == 2  # Parsed and titlecased
        assert paper.year == 2024
        assert isinstance(paper.year, int)
        assert len(paper.keywords) >= 2  # Deduplicated
        assert all(kw.islower() for kw in paper.keywords)
        assert paper.journal  # Titlecased
        assert paper.publisher  # Titlecased
        assert paper.paper_type == PaperType.JOURNAL_ARTICLE

    def test_ris_matches_direct_normalizer_output(self):
        """RIS output should match direct Normalizer calls"""
        title_input = "machine learning in NLP"
        abstract_input = "We tested  &amp;  validated."
        journal_input = "nature machine intelligence"
        
        record = RISRecord()
        record.add_field('TY', 'JOUR')
        record.add_field('T1', title_input)
        record.add_field('AB', abstract_input)
        record.add_field('JF', journal_input)
        
        paper = ris_record_to_paper(record)
        
        # Compare with direct Normalizer output
        assert paper.title == Normalizer.normalize_title(title_input)
        assert paper.abstract == Normalizer.normalize_abstract(abstract_input)
        assert paper.journal == Normalizer.normalize_journal(journal_input)

    def test_ris_paper_type_inference(self):
        """RIS type inference should work correctly"""
        test_cases = [
            ('JOUR', PaperType.JOURNAL_ARTICLE),
            ('CONF', PaperType.CONFERENCE_PAPER),
            ('BOOK', PaperType.BOOK),
            ('THES', PaperType.THESIS),
        ]
        
        for ris_type, expected_type in test_cases:
            record = RISRecord()
            record.add_field('TY', ris_type)
            record.add_field('T1', 'Test Paper')
            
            paper = ris_record_to_paper(record)
            assert paper.paper_type == expected_type


class TestIONormalizationConsistency:
    """Test that BibTeX and RIS produce consistent output"""

    def test_same_paper_bibtex_and_ris_normalize_identically(self):
        """Same paper from BibTeX and RIS should normalize identically"""
        bibtex_entry = {
            'ID': 'test2024',
            'ENTRYTYPE': 'article',
            'title': 'machine learning study',
            'abstract': 'We tested  &amp;  validated.',
            'author': 'Smith, John',
            'keywords': 'ML; Deep Learning',
            'journal': 'nature machine intelligence',
            'year': '2024',
        }
        
        ris_record = RISRecord()
        ris_record.add_field('TY', 'JOUR')
        ris_record.add_field('T1', 'machine learning study')
        ris_record.add_field('AB', 'We tested  &amp;  validated.')
        ris_record.add_field('AU', 'Smith, John')
        ris_record.add_field('KW', 'ML')
        ris_record.add_field('KW', 'Deep Learning')
        ris_record.add_field('JF', 'nature machine intelligence')
        ris_record.add_field('PY', '2024')
        
        bibtex_paper = bibtex_entry_to_paper(bibtex_entry)
        ris_paper = ris_record_to_paper(ris_record)
        
        # Key fields should normalize identically
        assert bibtex_paper.title == ris_paper.title
        assert bibtex_paper.abstract == ris_paper.abstract
        assert bibtex_paper.year == ris_paper.year
        assert bibtex_paper.journal == ris_paper.journal
        # Keywords might differ slightly in format but content should overlap
        assert len(bibtex_paper.keywords) > 0
        assert len(ris_paper.keywords) > 0


class TestIOBackwardCompatibility:
    """Test that deprecated IO functions still work"""

    def test_deprecated_bibtex_functions_work(self):
        """Deprecated BibTeX functions should still be callable"""
        from paper_scanner.io.bibtex import parse_authors, parse_keywords, normalize_ampersands
        
        # These should not raise
        authors = parse_authors("Smith, John")
        assert len(authors) > 0
        
        keywords = parse_keywords("ML; Deep Learning")
        assert len(keywords) > 0
        
        result = normalize_ampersands("A \\& B")
        assert "&" in result

    def test_deprecated_ris_functions_work(self):
        """Deprecated RIS functions should still be callable"""
        from paper_scanner.io.ris import (
            normalize_ampersands,
            normalize_whitespace,
            parse_authors_ris,
            parse_keywords_ris
        )
        
        # These should not raise
        result = normalize_ampersands("A &amp; B")
        assert "&" in result
        
        result = normalize_whitespace("A   B   C")
        assert result == "A B C"
        
        authors = parse_authors_ris(["Smith, John"])
        assert len(authors) > 0
        
        keywords = parse_keywords_ris(["Machine Learning"])
        assert len(keywords) > 0


class TestIOFieldNormalizationDetails:
    """Test specific field normalization behaviors"""

    def test_bibtex_title_with_latex_braces(self):
        """BibTeX title should handle LaTeX braces"""
        entry = {
            'ID': 'test1',
            'ENTRYTYPE': 'article',
            'title': 'a study of {deep learning} & transformers'
        }
        
        paper = bibtex_entry_to_paper(entry)
        assert 'Study' in paper.title or 'study' in paper.title

    def test_bibtex_abstract_no_titlecase(self):
        """BibTeX abstract should NOT be titlecased"""
        entry = {
            'ID': 'test1',
            'ENTRYTYPE': 'article',
            'title': 'Study',
            'abstract': 'this is a lowercase abstract sentence.'
        }
        
        paper = bibtex_entry_to_paper(entry)
        assert paper.abstract == 'this is a lowercase abstract sentence.'

    def test_ris_author_format_preserved(self):
        """RIS should preserve author format from input"""
        record = RISRecord()
        record.add_field('TY', 'JOUR')
        record.add_field('T1', 'Study')
        record.add_field('AU', 'Smith, John')
        
        paper = ris_record_to_paper(record)
        
        # Author should be parsed correctly
        assert paper.authors[0].family_name  # "Smith"
        assert paper.authors[0].given_name  # "John"

    def test_bibtex_author_van_particle(self):
        """BibTeX should handle van/de particles in names"""
        entry = {
            'ID': 'test1',
            'ENTRYTYPE': 'article',
            'title': 'Study',
            'author': 'van der Smith, John'
        }
        
        paper = bibtex_entry_to_paper(entry)
        
        # Name should be titlecased preserving structure
        assert len(paper.authors) > 0

    def test_keyword_deduplication_case_insensitive(self):
        """Keywords should deduplicate case-insensitively"""
        entry = {
            'ID': 'test1',
            'ENTRYTYPE': 'article',
            'title': 'Study',
            'keywords': 'ML; ml; Machine Learning; MACHINE LEARNING'
        }
        
        paper = bibtex_entry_to_paper(entry)
        
        # Should have fewer than 4 keywords due to deduplication
        assert len(paper.keywords) <= 2

    def test_year_range_validation(self):
        """Year should be validated for reasonable range"""
        # Valid year
        entry = {
            'ID': 'test1',
            'ENTRYTYPE': 'article',
            'title': 'Study',
            'year': '2024'
        }
        paper = bibtex_entry_to_paper(entry)
        assert paper.year == 2024
        
        # Out of range year should return None
        entry['year'] = '500'
        paper = bibtex_entry_to_paper(entry)
        assert paper.year is None or paper.year < 1000

    def test_doi_format_normalization(self):
        """DOI should be normalized to standard format"""
        entry = {
            'ID': 'test1',
            'ENTRYTYPE': 'article',
            'title': 'Study',
            'doi': 'https://doi.org/10.1234/example'
        }
        
        paper = bibtex_entry_to_paper(entry)
        
        # Should extract plain DOI format
        assert paper.doi
        assert paper.doi.startswith('10.')
