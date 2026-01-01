"""
Spike 017: Normalization Consolidation - Phase 1 Tests

Demonstrates the centralized Normalizer class consolidating 16+ duplicated
normalization functions from IO handlers and fetchers into a single source of truth.

This spike test validates that the Normalizer correctly:
1. Normalizes all 9 paper fields (title, abstract, authors, keywords, journal, publisher, year, DOI, paper_type)
2. Handles multiple input formats (strings, lists, dicts, objects)
3. Applies field-specific formatting rules (titlecase, whitespace collapse, ampersand normalization)
4. Preserves critical information (hyphens in names, particle handling, keyword deduplication)
"""

from paper_scanner.core.normalization import Normalizer
from paper_scanner.core.models import Author, Paper
from paper_scanner.core.enum import PaperType


class TestNormalizerPhase1:
    """Phase 1: Normalize all 9 fields with comprehensive input format support"""

    def test_normalize_complete_paper_from_bibtex_entry(self):
        """Test realistic BibTeX entry normalization"""
        raw_paper = {
            'title': 'machine learning in {NLP}: a systematic review',
            'abstract': 'We review  advances in  ML-based NLP systems &amp; their performance.',
            'authors': 'Smith, John and van der Doe, Jane',
            'keywords': 'machine learning; deep learning; nlp',
            'journal': 'journal of artificial intelligence research',
            'publisher': 'association for computational linguistics',
            'year': '2024',
            'doi': '10.1234/example.2024.001',
            'paper_type': 'journal_article'
        }
        
        normalized = Normalizer.normalize(raw_paper)
        
        # Title: titlecase + collapse whitespace + remove braces
        # Verify it's titlecased and contains expected content
        assert 'Machine Learning' in normalized['title']
        assert 'Systematic Review' in normalized['title']
        
        # Abstract: NO titlecase, just collapse whitespace + normalize ampersands
        assert normalized['abstract'] == 'We review advances in ML-based NLP systems & their performance.'
        
        # Authors: Parse BibTeX "Last, First" format + titlecase names
        assert normalized['authors'] == ['Smith, John', 'Van der Doe, Jane']
        
        # Keywords: Split by semicolon (highest priority) + lowercase + deduplicate
        assert normalized['keywords'] == ['machine learning', 'deep learning', 'nlp']
        
        # Journal: titlecase + normalize ampersands
        assert normalized['journal'] == 'Journal Of Artificial Intelligence Research'
        
        # Publisher: titlecase + normalize ampersands
        assert normalized['publisher'] == 'Association For Computational Linguistics'
        
        # Year: parse string to int + validate range
        assert normalized['year'] == 2024
        assert isinstance(normalized['year'], int)
        
        # DOI: standardize format
        assert normalized['doi'] == '10.1234/example.2024.001'
        
        # Paper Type: validate enum
        assert normalized['paper_type'] == PaperType.JOURNAL_ARTICLE

    def test_normalize_complete_paper_from_api_response(self):
        """Test realistic API response normalization (OpenAlex, Crossref format)"""
        raw_paper = {
            'title': 'The Impact of Transformer Models on Natural Language Understanding',
            'abstract': 'This article surveys recent developments in transformer-based models & their applications.',
            'authors': [
                {'given_name': 'alice', 'family_name': 'johnson'},
                {'given_name': 'bob', 'family_name': 'smith'}
            ],
            'keywords': 'transformers,language models,attention mechanisms',  # Comma-separated
            'journal': 'nature machine intelligence',
            'publisher': 'nature publishing group',
            'year': 2024,  # Already int
            'doi': 'https://doi.org/10.1038/s42256-024-00841-5',
            'paper_type': 'journal_article'
        }
        
        normalized = Normalizer.normalize(raw_paper)
        
        # Title: titlecase (already good, verify it stays)
        assert normalized['title'] == 'The Impact Of Transformer Models On Natural Language Understanding'
        
        # Abstract: collapse whitespace + normalize ampersands
        assert normalized['abstract'] == 'This article surveys recent developments in transformer-based models & their applications.'
        
        # Authors: from dicts, combined to "First Family" format + titlecase
        assert normalized['authors'] == ['Alice Johnson', 'Bob Smith']
        
        # Keywords: split by comma (second priority) + lowercase + deduplicate
        assert normalized['keywords'] == ['transformers', 'language models', 'attention mechanisms']
        
        # Journal: titlecase
        assert normalized['journal'] == 'Nature Machine Intelligence'
        
        # Publisher: titlecase
        assert normalized['publisher'] == 'Nature Publishing Group'
        
        # Year: already int, validated
        assert normalized['year'] == 2024
        
        # DOI: extract from URL format
        assert normalized['doi'] == '10.1038/s42256-024-00841-5'
        
        # Paper Type: validate
        assert normalized['paper_type'] == PaperType.JOURNAL_ARTICLE

    def test_normalize_with_author_objects(self):
        """Test normalization with existing Author model instances"""
        raw_paper = {
            'title': 'deep learning fundamentals',
            'authors': [
                Author(given_name='john', family_name='doe', full_name='John Doe'),
                Author(given_name='jane', family_name='smith', full_name='Jane Smith')
            ],
            'year': 2023,
        }
        
        normalized = Normalizer.normalize(raw_paper)
        
        # Authors from objects: titlecase applied
        assert normalized['authors'] == ['John Doe', 'Jane Smith']
        assert normalized['title'] == 'Deep Learning Fundamentals'
        assert normalized['year'] == 2023

    def test_normalize_preserves_hyphenated_names(self):
        """Test that hyphenated names are preserved during normalization"""
        raw_paper = {
            'authors': 'smith-jones, alice and van-der-waals, bob'
        }
        
        normalized = Normalizer.normalize(raw_paper)
        
        # Hyphens preserved in names
        assert normalized['authors'] == ['Smith-Jones, Alice', 'Van-Der-Waals, Bob']

    def test_normalize_handles_missing_fields(self):
        """Test that missing fields are handled gracefully"""
        raw_paper = {
            'title': 'incomplete paper',
            'year': 2024,
            # No abstract, authors, keywords, etc.
        }
        
        normalized = Normalizer.normalize(raw_paper)
        
        assert normalized['title'] == 'Incomplete Paper'
        assert normalized['year'] == 2024
        # Missing fields should be None or empty
        assert normalized['abstract'] is None or normalized['abstract'] == ''
        assert normalized['authors'] == [] or normalized['authors'] is None
        assert normalized['keywords'] == [] or normalized['keywords'] is None

    def test_normalize_keyword_deduplication(self):
        """Test that duplicate keywords are removed (case-insensitive)"""
        raw_paper = {
            'keywords': 'machine learning; ML; Deep Learning; deep learning; NEURAL NETWORKS'
        }
        
        normalized = Normalizer.normalize(raw_paper)
        
        # Deduplicated, lowercased
        assert 'machine learning' in normalized['keywords']
        assert 'ml' in normalized['keywords']
        assert 'deep learning' in normalized['keywords']
        assert 'neural networks' in normalized['keywords']
        # Should only have unique values (case-insensitive)
        assert len(normalized['keywords']) == 4

    def test_normalize_year_validation(self):
        """Test year range validation"""
        # Valid year
        assert Normalizer.normalize_year(2024) == 2024
        
        # Valid year from string
        assert Normalizer.normalize_year('2024') == 2024
        
        # Valid year from date
        assert Normalizer.normalize_year('2024-01-15') == 2024
        
        # Out of range (too old)
        assert Normalizer.normalize_year(500) is None
        
        # Out of range (too far future)
        assert Normalizer.normalize_year(2101) is None
        
        # Invalid string
        assert Normalizer.normalize_year('not-a-year') is None

    def test_normalize_title_preserves_critical_markers(self):
        """Test that important symbols in titles are preserved"""
        raw_paper = {
            'title': 'bert: pre-training of deep bidirectional transformers for language understanding'
        }
        
        normalized = Normalizer.normalize(raw_paper)
        
        # Colon preserved, hyphen preserved
        assert ':' in normalized['title']
        assert '-' in normalized['title']
        assert normalized['title'] == 'Bert: Pre-Training Of Deep Bidirectional Transformers For Language Understanding'

    def test_normalize_doi_multiple_formats(self):
        """Test DOI normalization from various formats"""
        # Plain format
        assert Normalizer.normalize_doi('10.1234/example') == '10.1234/example'
        
        # URL format
        assert Normalizer.normalize_doi('https://doi.org/10.1234/example') == '10.1234/example'
        
        # Prefix format
        assert Normalizer.normalize_doi('doi:10.1234/example') == '10.1234/example'
        
        # Invalid returns None
        assert Normalizer.normalize_doi('invalid-doi') is None


class TestNormalizerEdgeCases:
    """Test edge cases and boundary conditions"""

    def test_normalize_empty_inputs(self):
        """Test normalization with empty values"""
        raw_paper = {
            'title': '',
            'abstract': '   ',  # Whitespace only
            'authors': [],
            'keywords': '',
            'journal': None,
            'year': None
        }
        
        normalized = Normalizer.normalize(raw_paper)
        
        # Empty/None values handled appropriately
        assert normalized['title'] == '' or normalized['title'] is None
        assert normalized['abstract'] == '' or normalized['abstract'] is None
        assert normalized['authors'] == []
        assert normalized['keywords'] == [] or normalized['keywords'] is None
        assert normalized['journal'] is None or normalized['journal'] == ''
        assert normalized['year'] is None

    def test_normalize_special_characters_in_titles(self):
        """Test handling of special characters in titles"""
        raw_paper = {
            'title': 'a study of {LaTeX}, <HTML>, & special symbols!'
        }
        
        normalized = Normalizer.normalize(raw_paper)
        
        # Verify basic titlecase and ampersand normalization happened
        assert normalized['title'][0].isupper()  # First char uppercase
        assert '&' in normalized['title'] or 'and' in normalized['title'].lower()
        assert normalized['title']  # Non-empty result

    def test_normalize_unicode_handling(self):
        """Test handling of unicode characters"""
        raw_paper = {
            'title': 'étude de résolution étymologique',
            'authors': 'François, Jean and Müller, Hans'
        }
        
        normalized = Normalizer.normalize(raw_paper)
        
        # Unicode should be preserved or handled gracefully
        assert normalized['title']  # Non-empty
        assert len(normalized['authors']) == 2
        assert 'Jean' in normalized['authors'][0]
        assert 'Hans' in normalized['authors'][1]

    def test_normalize_very_long_titles(self):
        """Test handling of extremely long titles"""
        long_title = 'A ' + ' '.join(['very'] * 50) + ' long title'
        raw_paper = {'title': long_title}
        
        normalized = Normalizer.normalize(raw_paper)
        
        # Should still normalize without truncation
        assert normalized['title']  # Non-empty result
        assert 'Long' in normalized['title']  # Contains titlecased portion

    def test_normalize_mixed_case_keywords(self):
        """Test keyword normalization with semicolon priority"""
        raw_paper = {
            'keywords': 'ML;Deep Learning;Neural Networks'
        }
        
        normalized = Normalizer.normalize(raw_paper)
        
        # Should split by semicolon and lowercase
        assert all(kw.islower() for kw in normalized['keywords'])
        assert len(normalized['keywords']) >= 3


class TestNormalizerIntegration:
    """Integration tests demonstrating Phase 1 consolidation"""

    def test_normalizer_is_single_source_of_truth(self):
        """Verify Normalizer has all necessary normalization methods"""
        required_methods = [
            'normalize_title',
            'normalize_abstract',
            'normalize_authors',
            'normalize_keywords',
            'normalize_journal',
            'normalize_publisher',
            'normalize_year',
            'normalize_doi',
            'normalize_paper_type',
            'normalize'  # Main orchestration method
        ]
        
        for method in required_methods:
            assert hasattr(Normalizer, method), f"Normalizer missing method: {method}"
            assert callable(getattr(Normalizer, method))

    def test_normalizer_centralization_eliminates_duplication(self):
        """Demonstrate that Normalizer consolidates previously duplicated logic"""
        # This test shows the consolidation principle: instead of 16+ functions
        # scattered across IO handlers and fetchers, all normalization flows through one class
        
        paper_from_bibtex = {
            'title': 'study of machine learning',
            'authors': 'Smith, John',
        }
        
        paper_from_api = {
            'title': 'study of machine learning',
            'authors': [{'given_name': 'john', 'family_name': 'smith'}],
        }
        
        # Different input formats, same normalization
        result_bibtex = Normalizer.normalize(paper_from_bibtex)
        result_api = Normalizer.normalize(paper_from_api)
        
        # Titles should normalize identically
        assert result_bibtex['title'] == result_api['title'] == 'Study Of Machine Learning'
        
        # Authors should normalize identically (both titlecased)
        assert 'John' in result_bibtex['authors'][0]
        assert 'John' in result_api['authors'][0]
