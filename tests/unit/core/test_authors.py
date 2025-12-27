"""
Tests for Author model and name handling

Covers:
- Hyphenated names (Smith-Jones)
- Multi-word names (Van Der Berg)
- Unicode names
- Whitespace stripping
- Mixed alphanumeric handling
- Cite key generation with authors
"""

import pytest
from paper_scanner.core.models import Author, Paper
from paper_scanner.core.cite_key import generate_cite_key


class TestAuthorBasics:
    """Test basic Author instantiation and field handling"""

    def test_author_creation_with_all_fields(self):
        """Should create author with all fields"""
        author = Author(
            family_name="Smith",
            given_name="John",
            full_name="John Smith"
        )
        assert author.family_name == "Smith"
        assert author.given_name == "John"
        assert author.full_name == "John Smith"

    def test_author_creation_minimal(self):
        """Should create author with minimal fields"""
        author = Author(
            family_name="Smith",
            given_name="John",
            full_name="John Smith"
        )
        assert author.family_name == "Smith"
        assert author.given_name == "John"
        assert author.full_name == "John Smith"

    def test_author_with_only_family_name(self):
        """Should create author with only family name"""
        author = Author(
            family_name="Smith",
            full_name="Smith"
        )
        assert author.family_name == "Smith"
        # given_name can be None or empty
        assert author.full_name == "Smith"


class TestHyphenatedNames:
    """Test handling of hyphenated names (e.g., Smith-Jones)"""

    def test_hyphenated_family_name(self):
        """Should preserve hyphens and capitalize each part in family name"""
        author = Author(
            family_name="smith-jones",
            given_name="John",
            full_name="John Smith-Jones"
        )
        assert author.family_name == "Smith-Jones"
        assert author.given_name == "John"

    def test_hyphenated_given_name(self):
        """Should preserve hyphens and capitalize each part in given name"""
        author = Author(
            family_name="Smith",
            given_name="mary-jane",
            full_name="Mary-Jane Smith"
        )
        assert author.family_name == "Smith"
        assert author.given_name == "Mary-Jane"

    def test_triple_hyphenated_name(self):
        """Should handle multiple hyphens correctly"""
        author = Author(
            family_name="saint-john-smith",
            given_name="Anne-Marie-Louise",
            full_name="Anne-Marie-Louise Saint-John-Smith"
        )
        assert author.family_name == "Saint-John-Smith"
        assert author.given_name == "Anne-Marie-Louise"

    def test_hyphenated_full_name(self):
        """Should preserve hyphens in full name"""
        author = Author(
            family_name="smith-jones",
            given_name="mary-jane",
            full_name="Mary-Jane Smith-Jones"
        )
        assert author.family_name == "Smith-Jones"
        assert author.given_name == "Mary-Jane"
        assert author.full_name == "Mary-Jane Smith-Jones"


class TestMultiWordNames:
    """Test handling of multi-word names (e.g., Van Der Berg)"""

    def test_multi_word_family_name_lowercase(self):
        """Should capitalize all words in multi-word family name"""
        author = Author(
            family_name="van der berg",
            given_name="John",
            full_name="John Van Der Berg"
        )
        assert author.family_name == "Van Der Berg"

    def test_multi_word_family_name_mixed_case(self):
        """Should normalize multi-word family names to proper case"""
        author = Author(
            family_name="Van der BERG",
            given_name="John",
            full_name="John Van Der Berg"
        )
        assert author.family_name == "Van Der Berg"

    def test_multi_word_given_name(self):
        """Should handle multi-word given names with smart casing"""
        author = Author(
            family_name="Smith",
            given_name="jean paul",
            full_name="Jean Paul Smith"
        )
        # Given names use smart titlecase (may lowercase particles)
        assert author.given_name == "Jean Paul"

    def test_multi_word_full_name(self):
        """Should handle multi-word full names"""
        author = Author(
            family_name="van der berg",
            given_name="john",
            full_name="john van der berg"
        )
        assert author.family_name == "Van Der Berg"
        assert author.given_name == "John"


class TestUnicodeNames:
    """Test handling of unicode characters in names"""

    def test_greek_letters_family_name(self):
        """Should titlecase unicode characters in family name"""
        author = Author(
            family_name="Α λέκος",
            given_name="Ιωάννης",
            full_name="Ιωάννης Α Λέκος"
        )
        assert author.family_name == "Α Λέκος"
        assert author.given_name == "Ιωάννης"

    def test_greek_letters_full_name(self):
        """Should titlecase unicode in full name"""
        author = Author(
            family_name="Α λέκος",
            given_name="Ιωάννης",
            full_name="Ιωάννης Α λέκος"
        )
        assert author.family_name == "Α Λέκος"
        assert author.full_name == "Ιωάννης Α Λέκος"

    def test_accented_characters(self):
        """Should preserve accented characters while titlecasing"""
        author = Author(
            family_name="müller",
            given_name="françois",
            full_name="François Müller"
        )
        # Titlecase should work with accented characters
        assert author.family_name.lower() == "müller"
        assert author.given_name.lower() == "françois"


class TestWhitespaceHandling:
    """Test whitespace stripping and normalization"""

    def test_leading_trailing_whitespace_family_name(self):
        """Should strip leading/trailing whitespace from family name"""
        author = Author(
            family_name="  Smith  ",
            given_name="John",
            full_name="John Smith"
        )
        assert author.family_name == "Smith"
        assert author.given_name == "John"

    def test_leading_trailing_whitespace_given_name(self):
        """Should strip whitespace from given name"""
        author = Author(
            family_name="Smith",
            given_name="  John  ",
            full_name="John Smith"
        )
        assert author.family_name == "Smith"
        assert author.given_name == "John"

    def test_multiple_internal_spaces(self):
        """Should preserve internal spaces but normalize them"""
        author = Author(
            family_name="van  der  berg",
            given_name="John",
            full_name="John Van Der Berg"
        )
        # Internal spaces should be preserved in the title casing
        assert "der" in author.family_name.lower()


class TestNumbersAndSpecialChars:
    """Test handling of numbers and special characters"""

    def test_numbers_in_family_name(self):
        """Should lowercase alphanumeric combinations"""
        author = Author(
            family_name="123ABC",
            given_name="John",
            full_name="John 123abc"
        )
        # Numbers with letters get lowercased
        assert author.family_name == "123abc"

    def test_numbers_in_given_name(self):
        """Should handle numbers in given names"""
        author = Author(
            family_name="Smith",
            given_name="Jean2",
            full_name="Jean2 Smith"
        )
        assert author.given_name == "Jean2"

    def test_special_characters_preserved(self):
        """Should preserve apostrophes and other valid characters"""
        author = Author(
            family_name="O'Brien",
            given_name="John",
            full_name="John O'Brien"
        )
        assert "brien" in author.family_name.lower()
        assert "John" in author.given_name


class TestCiteKeyGeneration:
    """Test cite key generation from author names"""

    def test_cite_key_from_simple_name(self):
        """Should generate cite key from simple author name"""
        author = Author(
            family_name="Smith",
            given_name="John",
            full_name="John Smith"
        )
        paper = Paper(
            cite_key="",  # Will be generated
            title="Test Paper",
            authors=[author],
            year=2021
        )
        cite_key = generate_cite_key(paper)
        assert cite_key == "Smith2021"

    def test_cite_key_from_hyphenated_name(self):
        """Should remove hyphens when generating cite key"""
        author = Author(
            family_name="Smith-Jones",
            given_name="John",
            full_name="John Smith-Jones"
        )
        paper = Paper(
            cite_key="",
            title="Test Paper",
            authors=[author],
            year=2021
        )
        cite_key = generate_cite_key(paper)
        assert cite_key == "SmithJones2021"

    def test_cite_key_from_multi_word_name(self):
        """Should concatenate all parts in multi-word names"""
        author = Author(
            family_name="Van Der Berg",
            given_name="John",
            full_name="John Van Der Berg"
        )
        paper = Paper(
            cite_key="",
            title="Test Paper",
            authors=[author],
            year=2024
        )
        cite_key = generate_cite_key(paper)
        assert cite_key == "VanDerBerg2024"

    def test_cite_key_with_multiple_authors(self):
        """Should use first author's name for cite key"""
        authors = [
            Author(family_name="Smith", given_name="John", full_name="John Smith"),
            Author(family_name="Jones", given_name="Jane", full_name="Jane Jones")
        ]
        paper = Paper(
            cite_key="",
            title="Test Paper",
            authors=authors,
            year=2022
        )
        cite_key = generate_cite_key(paper)
        assert cite_key == "Smith2022"

    def test_cite_key_with_no_year(self):
        """Should raise error when cite key generation requires year"""
        author = Author(
            family_name="Smith",
            given_name="John",
            full_name="John Smith"
        )
        paper = Paper(
            cite_key="",
            title="Test Paper",
            authors=[author],
            year=None
        )
        # Should raise ValueError when year is missing
        with pytest.raises(ValueError, match="no publication year"):
            generate_cite_key(paper)


class TestAuthorComparison:
    """Test author equality and comparison"""

    def test_equal_authors(self):
        """Should identify equal authors"""
        author1 = Author(family_name="Smith", given_name="John", full_name="John Smith")
        author2 = Author(family_name="Smith", given_name="John", full_name="John Smith")
        assert author1 == author2

    def test_different_authors(self):
        """Should differentiate different authors"""
        author1 = Author(family_name="Smith", given_name="John", full_name="John Smith")
        author2 = Author(family_name="Jones", given_name="John", full_name="John Jones")
        assert author1 != author2

    def test_case_normalized_comparison(self):
        """Should compare case-normalized names"""
        # After normalization, these should be equal
        author1 = Author(family_name="SMITH", given_name="JOHN", full_name="JOHN SMITH")
        author2 = Author(family_name="smith", given_name="john", full_name="john smith")
        # Both get titlecased, so should be equal
        assert author1.family_name == author2.family_name
        assert author1.given_name == author2.given_name


class TestAuthorSerialization:
    """Test author serialization and deserialization"""

    def test_author_to_dict(self):
        """Should serialize author to dict-like structure"""
        author = Author(family_name="Smith", given_name="John", full_name="John Smith")
        # Authors should be convertible to dicts via model_dump
        author_dict = author.model_dump()
        assert author_dict["family_name"] == "Smith"
        assert author_dict["given_name"] == "John"

    def test_author_from_dict(self):
        """Should deserialize author from dict"""
        author_dict = {
            "family_name": "smith",
            "given_name": "john",
            "full_name": "john smith"
        }
        author = Author(**author_dict)
        assert author.family_name == "Smith"
        assert author.given_name == "John"


class TestEdgeCases:
    """Test edge cases and boundary conditions"""

    def test_empty_given_name(self):
        """Should handle empty given name"""
        author = Author(family_name="Smith", given_name="", full_name="Smith")
        assert author.family_name == "Smith"
        assert author.given_name == ""

    def test_single_letter_names(self):
        """Should handle single letter names"""
        author = Author(family_name="S", given_name="J", full_name="J S")
        assert author.family_name == "S"
        assert author.given_name == "J"

    def test_very_long_name(self):
        """Should handle very long names"""
        long_name = "Von Der Bauer-Smithson-Johnson"
        author = Author(
            family_name=long_name,
            given_name="John",
            full_name=f"John {long_name}"
        )
        assert author.family_name  # Should not fail

    def test_name_with_dots(self):
        """Should handle names with dots (initials)"""
        author = Author(
            family_name="Smith",
            given_name="J. M.",
            full_name="J. M. Smith"
        )
        # Should preserve the dots
        assert "." in author.given_name

    def test_null_given_name_optional(self):
        """Should handle None given name gracefully"""
        author = Author(family_name="Smith", given_name=None, full_name="Smith")
        assert author.family_name == "Smith"
        # given_name might be None
        assert author.given_name is None or author.given_name == ""
