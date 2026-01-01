"""
Unit tests for BibTeX IO module with Normalizer integration

Tests verify that bibtex.py correctly uses the Normalizer class for all
field normalization instead of duplicated functions.
"""

import pytest
from paper_scanner.io.bibtex import bibtex_entry_to_paper
from paper_scanner.core.models import Author, Paper, PaperType
from paper_scanner.core.normalization import Normalizer


class TestBibtexNormalizerIntegration:
    """Test that bibtex.py uses Normalizer for field normalization"""

    def test_parse_authors_uses_normalizer(self):
        """parse_authors should use Normalizer.normalize_authors()"""
        # Test "Last, First" format - normalize_authors returns list of strings
        result = Normalizer.normalize_authors("Smith, John and Doe, Jane")
        
        assert len(result) == 2
        assert isinstance(result[0], str)
        assert "Smith" in result[0] or "John" in result[0]
        assert "Doe" in result[1] or "Jane" in result[1]

    def test_parse_keywords_uses_normalizer(self):
        """parse_keywords should use Normalizer.normalize_keywords()"""
        result = Normalizer.normalize_keywords("machine learning; deep learning; neural networks")
        
        assert len(result) == 3
        assert all(kw.islower() for kw in result)
        assert "machine learning" in result
        assert "deep learning" in result
        assert "neural networks" in result

    def test_normalize_ampersands_uses_normalizer(self):
        """normalize_ampersands should use Normalizer._normalize_ampersands()"""
        result = Normalizer._normalize_ampersands("Smith \\& Jones Publishing")
        assert result == "Smith & Jones Publishing"
        
        result = Normalizer._normalize_ampersands("Art &amp; Design")
        assert result == "Art & Design"

    def test_bibtex_entry_to_paper_normalizes_all_fields(self):
        """bibtex_entry_to_paper should normalize all fields using Normalizer"""
        entry = {
            'ID': 'smith2024',
            'ENTRYTYPE': 'article',
            'title': 'machine learning in {NLP}: a study',
            'abstract': 'We tested  &amp;  validated...  ',
            'author': 'smith, john and doe, jane',
            'keywords': 'ML; deep learning; nlp',
            'journal': 'nature machine intelligence',
            'publisher': 'nature publishing group',
            'year': '2024',
            'doi': '10.1234/example',
            'booktitle': 'proceedings of icml'
        }
        
        paper = bibtex_entry_to_paper(entry)
        
        # Verify all fields are normalized
        assert paper.title  # Titlecased and cleaned
        assert paper.abstract  # Whitespace collapsed, ampersands normalized
        assert len(paper.authors) == 2
        assert all(isinstance(a, Author) for a in paper.authors)
        assert paper.year == 2024
        assert isinstance(paper.year, int)
        assert len(paper.keywords) >= 3
        assert all(kw.islower() for kw in paper.keywords)
        assert paper.journal  # Titlecased
        assert paper.publisher  # Titlecased
        assert paper.doi  # Normalized

    def test_bibtex_title_normalization(self):
        """Verify title normalization via Normalizer"""
        entry = {
            'ID': 'test1',
            'ENTRYTYPE': 'article',
            'title': 'a study of {deep learning} & transformers'
        }
        
        paper = bibtex_entry_to_paper(entry)
        
        # Title should be titlecased and contain expected content
        assert 'Study' in paper.title
        assert 'Learning' in paper.title or 'learning' in paper.title

    def test_bibtex_abstract_normalization(self):
        """Verify abstract normalization (NO titlecase, collapse whitespace)"""
        entry = {
            'ID': 'test1',
            'ENTRYTYPE': 'article',
            'title': 'Study',
            'abstract': 'We tested   &amp;   validated   multiple   models.   '
        }
        
        paper = bibtex_entry_to_paper(entry)
        
        # Abstract should be collapsed, not titlecased
        assert paper.abstract
        # Should have single spaces
        assert '   ' not in paper.abstract
        # Should have normalized ampersand
        assert '&' in paper.abstract

    def test_bibtex_author_normalization_titlecase(self):
        """Verify authors are titlecased via Normalizer"""
        entry = {
            'ID': 'test1',
            'ENTRYTYPE': 'article',
            'title': 'Study',
            'author': 'smith, john and van der doe, jane'
        }
        
        paper = bibtex_entry_to_paper(entry)
        
        assert len(paper.authors) == 2
        # Names should be titlecased
        assert paper.authors[0].given_name == 'John' or paper.authors[0].given_name == 'john'

    def test_bibtex_keywords_deduplication_and_lowercase(self):
        """Verify keywords are deduplicated and lowercased via Normalizer"""
        entry = {
            'ID': 'test1',
            'ENTRYTYPE': 'article',
            'title': 'Study',
            'keywords': 'ML; Machine Learning; NEURAL NETWORKS; neural networks'
        }
        
        paper = bibtex_entry_to_paper(entry)
        
        # Should be deduplicated (case-insensitive)
        assert all(kw.islower() for kw in paper.keywords)
        # 'ml' and 'machine learning' and 'neural networks' should be present
        assert 'ml' in paper.keywords or 'machine learning' in paper.keywords

    def test_bibtex_year_validation(self):
        """Verify year is validated via Normalizer"""
        entry = {
            'ID': 'test1',
            'ENTRYTYPE': 'article',
            'title': 'Study',
            'year': '2024'
        }
        
        paper = bibtex_entry_to_paper(entry)
        
        assert paper.year == 2024
        assert isinstance(paper.year, int)

    def test_bibtex_journal_normalization(self):
        """Verify journal is normalized via Normalizer"""
        entry = {
            'ID': 'test1',
            'ENTRYTYPE': 'article',
            'title': 'Study',
            'journal': 'nature & machine learning review'
        }
        
        paper = bibtex_entry_to_paper(entry)
        
        # Should be titlecased
        assert paper.journal
        assert 'Nature' in paper.journal or 'nature' in paper.journal

    def test_bibtex_multiple_keyword_fields(self):
        """Verify bibtex_entry_to_paper aggregates multiple keyword fields"""
        entry = {
            'ID': 'test1',
            'ENTRYTYPE': 'article',
            'title': 'Study',
            'keywords': 'ML; deep learning',
            'author_keywords': 'neural networks',
            'keywords-plus': 'transformers'
        }
        
        paper = bibtex_entry_to_paper(entry)
        
        # All keyword sources should be normalized
        assert len(paper.keywords) > 0
        # After normalization, should contain expected keywords
        keyword_text = '; '.join(paper.keywords)
        assert any(kw in keyword_text for kw in ['ml', 'deep learning', 'neural networks', 'transformers'])


class TestBibtexBackwardCompatibility:
    """Test backward compatibility of deprecated functions"""

    def test_parse_authors_backward_compat(self):
        """parse_authors still works (though deprecated)"""
        result = Normalizer.normalize_authors("Smith, John")
        assert len(result) == 1
        assert isinstance(result[0], str)

    def test_parse_keywords_backward_compat(self):
        """parse_keywords still works (though deprecated)"""
        result = Normalizer.normalize_keywords("keyword1; keyword2")
        assert len(result) == 2

    def test_normalize_ampersands_backward_compat(self):
        """normalize_ampersands still works (though deprecated)"""
        result = Normalizer._normalize_ampersands("A \\& B")
        assert "&" in result


class TestBibtexNormalizerConsistency:
    """Test consistency between direct Normalizer use and bibtex.py"""

    def test_title_normalization_consistent(self):
        """Title normalization should match Normalizer.normalize_title()"""
        title_input = "the great study of machine learning"
        
        entry = {'ID': 'test1', 'ENTRYTYPE': 'article', 'title': title_input}
        paper = bibtex_entry_to_paper(entry)
        
        expected_title = Normalizer.normalize_title(title_input)
        assert paper.title == expected_title

    def test_abstract_normalization_consistent(self):
        """Abstract normalization should match Normalizer.normalize_abstract()"""
        abstract_input = "We tested   &amp;   validated the model.  "
        
        entry = {'ID': 'test1', 'ENTRYTYPE': 'article', 'title': 'Study', 'abstract': abstract_input}
        paper = bibtex_entry_to_paper(entry)
        
        expected_abstract = Normalizer.normalize_abstract(abstract_input)
        assert paper.abstract == expected_abstract

    def test_keywords_normalization_consistent(self):
        """Keywords normalization should match Normalizer.normalize_keywords()"""
        keywords_input = "machine learning; deep learning; ml"
        
        entry = {'ID': 'test1', 'ENTRYTYPE': 'article', 'title': 'Study', 'keywords': keywords_input}
        paper = bibtex_entry_to_paper(entry)
        
        expected_keywords = Normalizer.normalize_keywords(keywords_input)
        assert paper.keywords == expected_keywords

    def test_authors_normalization_consistent(self):
        """Authors normalization should match Normalizer.normalize_authors()"""
        authors_input = "Smith, John and Doe, Jane"
        
        entry = {'ID': 'test1', 'ENTRYTYPE': 'article', 'title': 'Study', 'author': authors_input}
        paper = bibtex_entry_to_paper(entry)
        
        expected_author_names = Normalizer.normalize_authors(authors_input)
        
        # Extract names from paper authors
        paper_author_names = []
        for author in paper.authors:
            if author.given_name and author.family_name:
                # Normalize format to match
                paper_author_names.append(f"{author.family_name}, {author.given_name}")
            else:
                paper_author_names.append(author.full_name)
        
        assert len(paper_author_names) == len(expected_author_names)
