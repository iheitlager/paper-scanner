"""
Tests for citation key generation and collision resolution utilities.
"""

import pytest
from paper_scanner.core.cite_key import generate_cite_key, make_collision_suffix, resolve_collision
from paper_scanner.core.models import Paper, Author


class TestGenerateCiteKey:
    """Tests for generate_cite_key function"""
    
    def test_simple_cite_key_generation(self):
        """Test basic cite key generation 'LastnameYear'"""
        author = Author(family_name="Smith", given_names="John", full_name="John Smith")
        paper = Paper(
            title="Test Paper",
            authors=[author],
            year=2020,
            cite_key="Smith2020",
        )
        
        assert generate_cite_key(paper) == "Smith2020"
    
    def test_cite_key_with_multiple_words_in_last_name(self):
        """Test cite key strips spaces from family name"""
        author = Author(family_name="Van Der Berg", given_names="John", full_name="John Van Der Berg")
        paper = Paper(
            title="Test Paper",
            authors=[author],
            year=2021,
            cite_key="VanDerBerg2021",
        )
        
        assert generate_cite_key(paper) == "VanDerBerg2021"
    
    def test_cite_key_with_hyphenated_last_name(self):
        """Test cite key removes hyphens from family name"""
        author = Author(family_name="Smith-Jones", given_names="Jane", full_name="Jane Smith-Jones")
        paper = Paper(
            title="Test Paper",
            authors=[author],
            year=2022,
            cite_key="SmithJones2022",
        )
        
        assert generate_cite_key(paper) == "SmithJones2022"
    
    def test_cite_key_uses_first_author(self):
        """Test cite key uses first author when multiple authors"""
        author1 = Author(family_name="Smith", given_names="John", full_name="John Smith")
        author2 = Author(family_name="Johnson", given_names="Jane", full_name="Jane Johnson")
        paper = Paper(
            title="Test Paper",
            authors=[author1, author2],
            year=2020,
            cite_key="Smith2020",
        )
        
        assert generate_cite_key(paper) == "Smith2020"
    
    def test_error_no_authors(self):
        """Test ValueError when paper has no authors"""
        paper = Paper(
            title="Test Paper",
            authors=[],
            year=2020,
            cite_key="NoAuthor2020",
        )
        
        with pytest.raises(ValueError, match="has no authors"):
            generate_cite_key(paper)
    
    def test_error_no_year(self):
        """Test ValueError when paper has no year"""
        author = Author(family_name="Smith", given_names="John", full_name="John Smith")
        paper = Paper(
            title="Test Paper",
            authors=[author],
            year=None,
            cite_key="Smith",
        )
        
        with pytest.raises(ValueError, match="has no publication year"):
            generate_cite_key(paper)
    
    def test_error_no_family_name(self):
        """Test ValueError when author has no family name"""
        author = Author(family_name="", given_names="John", full_name="John")
        paper = Paper(
            title="Test Paper",
            authors=[author],
            year=2020,
            cite_key="John2020",
        )
        
        with pytest.raises(ValueError, match="has no family name"):
            generate_cite_key(paper)


class TestMakeCollisionSuffix:
    """Tests for make_collision_suffix function"""
    
    def test_single_letter_suffixes(self):
        """Test single letter suffixes: a-z for indices 0-25"""
        assert make_collision_suffix(0) == "a"
        assert make_collision_suffix(1) == "b"
        assert make_collision_suffix(25) == "z"
    
    def test_double_letter_suffixes(self):
        """Test double letter suffixes starting from index 26"""
        assert make_collision_suffix(26) == "aa"
        assert make_collision_suffix(27) == "ab"
        assert make_collision_suffix(51) == "az"
    
    def test_triple_letter_suffixes(self):
        """Test triple letter suffixes"""
        assert make_collision_suffix(52) == "aaa"
        assert make_collision_suffix(77) == "aaz"
    
    def test_many_suffixes(self):
        """Test that we can generate many unique suffixes"""
        suffixes = [make_collision_suffix(i) for i in range(100)]
        # All suffixes should be unique
        assert len(suffixes) == len(set(suffixes))
        # All should be non-empty strings
        assert all(s for s in suffixes)


class TestResolveCollision:
    """Tests for resolve_collision function"""
    
    def test_no_collision(self):
        """Test returns base_key when no collision exists"""
        existing_keys = {"Smith2019", "Johnson2020"}
        result = resolve_collision("Smith2020", existing_keys)
        assert result == "Smith2020"
    
    def test_collision_with_single_letter_suffix(self):
        """Test appends single letter suffix for collision"""
        existing_keys = {"Smith2020"}
        result = resolve_collision("Smith2020", existing_keys)
        assert result == "Smith2020a"
    
    def test_collision_with_multiple_letters_suffix(self):
        """Test appends multiple letter suffix for multiple collisions"""
        existing_keys = {
            "Smith2020",
            "Smith2020a",
            "Smith2020b",
            "Smith2020c",
        }
        result = resolve_collision("Smith2020", existing_keys)
        assert result == "Smith2020d"
    
    def test_collision_resolution_exhaustive(self):
        """Test finds unique key even with many collisions"""
        # Create 30 collisions
        existing_keys = {"Smith2020"}
        existing_keys.update([f"Smith2020{make_collision_suffix(i)}" for i in range(30)])
        
        result = resolve_collision("Smith2020", existing_keys)
        assert result not in existing_keys
    
    def test_empty_existing_keys(self):
        """Test with empty existing keys dict"""
        existing_keys = {}
        result = resolve_collision("Smith2020", existing_keys)
        assert result == "Smith2020"
    
    def test_case_sensitive_collision_detection(self):
        """Test that collision detection is case-sensitive"""
        existing_keys = {"smith2020"}  # lowercase
        result = resolve_collision("Smith2020", existing_keys)
        # Different case, so no collision
        assert result == "Smith2020"
