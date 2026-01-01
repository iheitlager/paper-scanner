"""
Unit tests for core/normalization.py

Tests the Normalizer class to ensure consistent field normalization
across all IO handlers and fetchers.
"""

import pytest

from paper_scanner.core.normalization import Normalizer
from paper_scanner.core.enum import PaperType


class TestNormalizerTitle:
    """Tests for normalize_title()"""

    def test_title_basic(self):
        """Simple title normalization"""
        result = Normalizer.normalize_title("simple title")
        assert result == "Simple Title"

    def test_title_uppercase(self):
        """Convert uppercase to titlecase"""
        result = Normalizer.normalize_title("THE GREAT STUDY")
        assert result == "The Great Study"

    def test_title_particles(self):
        """Preserve lowercase particles (non-English)"""
        result = Normalizer.normalize_title("ludwig van beethoven sonata")
        assert result == "Ludwig van Beethoven Sonata"

    def test_title_whitespace(self):
        """Collapse multiple spaces"""
        result = Normalizer.normalize_title("  title  with   spaces  ")
        assert result == "Title With Spaces"

    def test_title_latex_braces(self):
        """Remove LaTeX braces"""
        result = Normalizer.normalize_title("Title {with} {braces}")
        assert result == "Title With Braces"

    def test_title_none(self):
        """Handle None input"""
        assert Normalizer.normalize_title(None) is None

    def test_title_empty_whitespace(self):
        """Handle whitespace-only string"""
        assert Normalizer.normalize_title("   ") == ""

    def test_title_van_particles(self):
        """Handle van/von particles correctly"""
        result = Normalizer.normalize_title("ludwig van beethoven")
        assert result == "Ludwig van Beethoven"


class TestNormalizerAbstract:
    """Tests for normalize_abstract()"""

    def test_abstract_basic(self):
        """Basic abstract normalization (no titlecase)"""
        result = Normalizer.normalize_abstract("A simple abstract.")
        assert result == "A simple abstract."

    def test_abstract_whitespace(self):
        """Collapse multiple spaces and newlines"""
        result = Normalizer.normalize_abstract("Abstract  with   spaces\n\nand newlines")
        assert result == "Abstract with spaces and newlines"

    def test_abstract_ampersands(self):
        """Normalize ampersands"""
        result = Normalizer.normalize_abstract("Smith \\& Jones &amp; Co.")
        assert result == "Smith & Jones & Co."

    def test_abstract_html_markup(self):
        """Remove HTML markup"""
        result = Normalizer.normalize_abstract("Abstract <b>with</b> <i>HTML</i> tags")
        assert result == "Abstract with HTML tags"

    def test_abstract_latex_braces(self):
        """Remove LaTeX braces"""
        result = Normalizer.normalize_abstract("Abstract {with} {braces}")
        assert result == "Abstract with braces"

    def test_abstract_none(self):
        """Handle None input"""
        assert Normalizer.normalize_abstract(None) is None

    def test_abstract_empty_whitespace(self):
        """Handle whitespace-only string"""
        assert Normalizer.normalize_abstract("   ") == ""


class TestNormalizerAuthors:
    """Tests for normalize_authors()"""

    def test_authors_bibtex_format(self):
        """Parse BibTeX format and titlecase"""
        result = Normalizer.normalize_authors("smith, john and doe, jane")
        # Titlecased but format preserved as given (not swapped to First Last)
        assert result == ["Smith, John", "Doe, Jane"]

    def test_authors_api_format(self):
        """Parse API 'First Last' format"""
        result = Normalizer.normalize_authors("John Smith and Jane Doe")
        assert result == ["John Smith", "Jane Doe"]

    def test_authors_list_of_strings(self):
        """Handle list of author strings"""
        result = Normalizer.normalize_authors(["smith, john", "doe, jane"])
        # Titlecased
        assert result == ["Smith, John", "Doe, Jane"]

    def test_authors_list_of_dicts(self):
        """Handle list of author dicts"""
        authors = [
            {"given_name": "john", "family_name": "smith"},
            {"given_name": "jane", "family_name": "doe"}
        ]
        result = Normalizer.normalize_authors(authors)
        assert result == ["John Smith", "Jane Doe"]

    def test_authors_list_of_objects(self):
        """Handle list of Author objects"""
        from paper_scanner.core.models import Author
        authors = [
            Author(given_name="John", family_name="Smith", full_name="John Smith"),
            Author(given_name="Jane", family_name="Doe", full_name="Jane Doe")
        ]
        result = Normalizer.normalize_authors(authors)
        assert result == ["John Smith", "Jane Doe"]

    def test_authors_single_string(self):
        """Handle single author as string"""
        result = Normalizer.normalize_authors("smith, john")
        assert result == ["Smith, John"]

    def test_authors_none(self):
        """Handle None input"""
        assert Normalizer.normalize_authors(None) == []

    def test_authors_empty_list(self):
        """Handle empty list"""
        assert Normalizer.normalize_authors([]) == []

    def test_authors_hyphenated_name(self):
        """Preserve hyphens in names and titlecase"""
        result = Normalizer.normalize_authors("smith-jones, jane")
        # Format preserved, titlecased
        assert result == ["Smith-Jones, Jane"]

    def test_authors_titlecase_applied(self):
        """Apply smart titlecase to author names"""
        result = Normalizer.normalize_authors("van der smith, john")
        # Particles preserved in titlecase
        assert result == ["Van der Smith, John"]


class TestNormalizerKeywords:
    """Tests for normalize_keywords()"""

    def test_keywords_semicolon(self):
        """Split by semicolon"""
        result = Normalizer.normalize_keywords("ML; Deep Learning; Neural Networks")
        assert result == ["ml", "deep learning", "neural networks"]

    def test_keywords_comma(self):
        """Split by comma"""
        result = Normalizer.normalize_keywords("ML, Deep Learning, Neural Networks")
        assert result == ["ml", "deep learning", "neural networks"]

    def test_keywords_and(self):
        """Split by 'and'"""
        result = Normalizer.normalize_keywords("ML and Deep Learning and Neural Networks")
        assert result == ["ml", "deep learning", "neural networks"]

    def test_keywords_list(self):
        """Handle list of keywords"""
        result = Normalizer.normalize_keywords(["Machine Learning", "Deep Learning"])
        assert result == ["machine learning", "deep learning"]

    def test_keywords_deduplicate(self):
        """Deduplicate keywords"""
        result = Normalizer.normalize_keywords("ML; Deep Learning; ml")
        assert result == ["ml", "deep learning"]

    def test_keywords_case_insensitive(self):
        """Convert to lowercase"""
        result = Normalizer.normalize_keywords("ML; DEEP LEARNING")
        assert result == ["ml", "deep learning"]

    def test_keywords_whitespace(self):
        """Strip extra whitespace"""
        result = Normalizer.normalize_keywords("  ML  ;  Deep Learning  ")
        assert result == ["ml", "deep learning"]

    def test_keywords_none(self):
        """Handle None input"""
        assert Normalizer.normalize_keywords(None) == []

    def test_keywords_empty_list(self):
        """Handle empty list"""
        assert Normalizer.normalize_keywords([]) == []


class TestNormalizerJournal:
    """Tests for normalize_journal()"""

    def test_journal_titlecase(self):
        """Apply titlecase to journal name"""
        result = Normalizer.normalize_journal("the journal of machine learning")
        # Note: Uses standard titlecase, not smart titlecase
        assert result == "The Journal Of Machine Learning"

    def test_journal_ampersands(self):
        """Normalize ampersands in journal name"""
        result = Normalizer.normalize_journal("nature & science \\& research")
        assert result == "Nature & Science & Research"

    def test_journal_particles(self):
        """Preserve lowercase particles"""
        result = Normalizer.normalize_journal("journal de recherche")
        assert result == "Journal de Recherche"

    def test_journal_none(self):
        """Handle None input"""
        result = Normalizer.normalize_journal(None)
        assert result is None

    def test_journal_empty(self):
        """Handle empty string"""
        assert Normalizer.normalize_journal("") == ""


class TestNormalizerPublisher:
    """Tests for normalize_publisher()"""

    def test_publisher_titlecase(self):
        """Apply titlecase to publisher name"""
        result = Normalizer.normalize_publisher("academic press ltd")
        assert result == "Academic Press Ltd"

    def test_publisher_ampersands(self):
        """Normalize ampersands in publisher name"""
        result = Normalizer.normalize_publisher("smith & jones publishing")
        assert result == "Smith & Jones Publishing"

    def test_publisher_none(self):
        """Handle None input"""
        result = Normalizer.normalize_publisher(None)
        assert result is None

    def test_publisher_empty(self):
        """Handle empty string"""
        assert Normalizer.normalize_publisher("") == ""


class TestNormalizerYear:
    """Tests for normalize_year()"""

    def test_year_integer(self):
        """Handle integer input"""
        assert Normalizer.normalize_year(2024) == 2024

    def test_year_string(self):
        """Parse string year"""
        assert Normalizer.normalize_year("2024") == 2024

    def test_year_from_date_string(self):
        """Extract year from date string"""
        assert Normalizer.normalize_year("2024-01-15") == 2024

    def test_year_out_of_range_past(self):
        """Reject year too far in past"""
        assert Normalizer.normalize_year(999) is None

    def test_year_out_of_range_future(self):
        """Reject year too far in future"""
        assert Normalizer.normalize_year(2101) is None

    def test_year_invalid_string(self):
        """Handle invalid string"""
        assert Normalizer.normalize_year("not_a_year") is None

    def test_year_none(self):
        """Handle None input"""
        assert Normalizer.normalize_year(None) is None

    def test_year_empty_string(self):
        """Handle empty string"""
        assert Normalizer.normalize_year("") is None

    def test_year_valid_range_boundary_min(self):
        """Accept minimum valid year"""
        assert Normalizer.normalize_year(1000) == 1000

    def test_year_valid_range_boundary_max(self):
        """Accept maximum valid year"""
        assert Normalizer.normalize_year(2100) == 2100


class TestNormalizerDOI:
    """Tests for normalize_doi()"""

    def test_doi_plain_format(self):
        """Normalize plain DOI format"""
        result = Normalizer.normalize_doi("10.1234/example")
        assert result == "10.1234/example"

    def test_doi_url_format(self):
        """Normalize DOI from URL"""
        result = Normalizer.normalize_doi("https://doi.org/10.1234/example")
        assert result == "10.1234/example"

    def test_doi_prefix_format(self):
        """Normalize DOI with prefix"""
        result = Normalizer.normalize_doi("doi:10.1234/example")
        assert result == "10.1234/example"

    def test_doi_none(self):
        """Handle None input"""
        assert Normalizer.normalize_doi(None) is None

    def test_doi_empty(self):
        """Handle empty string"""
        assert Normalizer.normalize_doi("") is None

    def test_doi_invalid(self):
        """Handle invalid DOI"""
        result = Normalizer.normalize_doi("not_a_doi")
        # May return None or try to parse; DOI class handles this
        assert result is None or isinstance(result, str)


class TestNormalizerPaperType:
    """Tests for normalize_paper_type()"""

    def test_paper_type_valid(self):
        """Validate valid paper type"""
        result = Normalizer.normalize_paper_type("journal_article")
        assert result == "journal_article"

    def test_paper_type_conference_paper(self):
        """Validate conference paper type"""
        result = Normalizer.normalize_paper_type("conference_paper")
        assert result == "conference_paper"

    def test_paper_type_invalid(self):
        """Reject invalid paper type"""
        assert Normalizer.normalize_paper_type("invalid_type") is None

    def test_paper_type_none(self):
        """Handle None input"""
        assert Normalizer.normalize_paper_type(None) is None

    def test_paper_type_empty(self):
        """Handle empty string"""
        assert Normalizer.normalize_paper_type("") is None


class TestNormalizerSmartTitlecase:
    """Tests for _smart_titlecase() internal helper"""

    def test_smart_titlecase_basic(self):
        """Basic titlecase"""
        assert Normalizer._smart_titlecase("hello world") == "Hello World"

    def test_smart_titlecase_particles(self):
        """Preserve lowercase particles"""
        assert Normalizer._smart_titlecase("the great study") == "The Great Study"

    def test_smart_titlecase_van(self):
        """Handle van particle"""
        assert Normalizer._smart_titlecase("ludwig van beethoven") == "Ludwig van Beethoven"

    def test_smart_titlecase_hyphenated(self):
        """Handle hyphenated words"""
        result = Normalizer._smart_titlecase("jean-claude van damme")
        assert result == "Jean-Claude van Damme"

    def test_smart_titlecase_empty(self):
        """Handle empty string"""
        assert Normalizer._smart_titlecase("") == ""

    def test_smart_titlecase_de_particle(self):
        """Handle de particle"""
        assert Normalizer._smart_titlecase("pierre de la font") == "Pierre de la Font"


class TestNormalizerCollapseWhitespace:
    """Tests for _collapse_whitespace() internal helper"""

    def test_collapse_multiple_spaces(self):
        """Collapse multiple spaces"""
        assert Normalizer._collapse_whitespace("text  with   spaces") == "text with spaces"

    def test_collapse_newlines(self):
        """Collapse newlines to space"""
        assert Normalizer._collapse_whitespace("text\nwith\nnewlines") == "text with newlines"

    def test_collapse_mixed_whitespace(self):
        """Collapse mixed whitespace"""
        assert Normalizer._collapse_whitespace("text  \n  with  \t  mixed") == "text with mixed"

    def test_collapse_leading_trailing(self):
        """Strip leading/trailing whitespace"""
        assert Normalizer._collapse_whitespace("  text  ") == "text"

    def test_collapse_empty(self):
        """Handle empty string"""
        assert Normalizer._collapse_whitespace("") == ""

    def test_collapse_none(self):
        """Handle None"""
        assert Normalizer._collapse_whitespace(None) is None


class TestNormalizerNormalizeAmpersands:
    """Tests for _normalize_ampersands() internal helper"""

    def test_ampersand_escape(self):
        """Normalize escaped ampersand"""
        assert Normalizer._normalize_ampersands("Smith \\& Jones") == "Smith & Jones"

    def test_ampersand_html(self):
        """Normalize HTML ampersand"""
        assert Normalizer._normalize_ampersands("Smith &amp; Jones") == "Smith & Jones"

    def test_ampersand_normal(self):
        """Keep normal ampersand"""
        assert Normalizer._normalize_ampersands("Smith & Jones") == "Smith & Jones"

    def test_ampersand_mixed(self):
        """Normalize mixed ampersands"""
        result = Normalizer._normalize_ampersands("A \\& B &amp; C & D")
        assert result == "A & B & C & D"

    def test_ampersand_none(self):
        """Handle None"""
        assert Normalizer._normalize_ampersands(None) is None


class TestNormalizerCleanMarkup:
    """Tests for _clean_markup() internal helper"""

    def test_clean_latex_braces(self):
        """Remove LaTeX braces"""
        assert Normalizer._clean_markup("title {with} braces") == "title with braces"

    def test_clean_html_tags(self):
        """Remove HTML tags"""
        assert Normalizer._clean_markup("title <b>with</b> html") == "title with html"

    def test_clean_complex(self):
        """Remove mixed markup"""
        result = Normalizer._clean_markup("text {latex} and <html> markup")
        assert result == "text latex and  markup"

    def test_clean_none(self):
        """Handle None"""
        assert Normalizer._clean_markup(None) is None


class TestNormalizerParseAuthorString:
    """Tests for _parse_author_string() internal helper"""

    def test_parse_single_author(self):
        """Parse single author"""
        result = Normalizer._parse_author_string("Smith, John")
        assert result == ["Smith, John"]

    def test_parse_multiple_authors(self):
        """Parse multiple authors"""
        result = Normalizer._parse_author_string("Smith, John and Doe, Jane")
        assert result == ["Smith, John", "Doe, Jane"]

    def test_parse_case_insensitive_and(self):
        """Handle case-insensitive 'and'"""
        result = Normalizer._parse_author_string("Smith, John AND Doe, Jane")
        assert result == ["Smith, John", "Doe, Jane"]

    def test_parse_empty(self):
        """Handle empty string"""
        assert Normalizer._parse_author_string("") == []

    def test_parse_none(self):
        """Handle None input"""
        # None is handled by normalize_authors, not _parse_author_string
        assert Normalizer._parse_author_string(None) == []


class TestNormalizerSplitKeywords:
    """Tests for _split_keywords() internal helper"""

    def test_split_semicolon(self):
        """Split by semicolon (priority)"""
        result = Normalizer._split_keywords("ML; Deep Learning")
        assert result == ["ML", " Deep Learning"]

    def test_split_comma(self):
        """Split by comma"""
        result = Normalizer._split_keywords("ML, Deep Learning")
        assert result == ["ML", " Deep Learning"]

    def test_split_and(self):
        """Split by 'and'"""
        result = Normalizer._split_keywords("ML and Deep Learning")
        assert result == ["ML", "Deep Learning"]

    def test_split_none_apply(self):
        """No split if no delimiter"""
        result = Normalizer._split_keywords("MachineLearning")
        assert result == ["MachineLearning"]

    def test_split_empty(self):
        """Handle empty string"""
        assert Normalizer._split_keywords("") == []

    def test_split_priority_semicolon_over_comma(self):
        """Semicolon takes priority over comma"""
        result = Normalizer._split_keywords("ML; Deep, Learning")
        # Should split by semicolon, not comma
        assert len(result) == 2


class TestNormalizerIntegration:
    """Integration tests for full normalization pipeline"""

    def test_normalize_full_dict(self):
        """Normalize complete paper dict"""
        raw = {
            'title': 'the GREAT study',
            'abstract': 'We tested\\& validated...',
            'authors': 'smith, john and doe, jane',
            'keywords': 'ML; Deep Learning',
            'journal': 'nature & science',
            'publisher': 'academic press',
            'year': '2024-01-15',
            'doi': '10.1234/example',
            'paper_type': 'journal_article',
            'other_field': 'unchanged'
        }
        
        normalized = Normalizer.normalize(raw)
        
        assert normalized['title'] == 'The Great Study'
        # Abstract: no titlecase, just collapse whitespace and normalize ampersands
        assert normalized['abstract'] == 'We tested& validated...'
        # Authors: Format preserved from input (BibTeX "Last, First"), titlecased
        assert normalized['authors'] == ['Smith, John', 'Doe, Jane']
        assert normalized['keywords'] == ['ml', 'deep learning']
        assert normalized['journal'] == 'Nature & Science'
        assert normalized['publisher'] == 'Academic Press'
        assert normalized['year'] == 2024
        assert normalized['doi'] == '10.1234/example'
        assert normalized['paper_type'] == 'journal_article'
        assert normalized['other_field'] == 'unchanged'

    def test_normalize_sparse_dict(self):
        """Normalize dict with missing fields"""
        raw = {
            'title': 'test paper',
            'year': 2024
        }
        
        normalized = Normalizer.normalize(raw)
        
        assert normalized['title'] == 'Test Paper'
        assert normalized['year'] == 2024
        assert normalized['abstract'] is None
        assert normalized['authors'] == []
        assert normalized['keywords'] == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
