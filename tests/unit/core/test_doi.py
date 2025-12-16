"""
Unit tests for DOI class.

Tests DOI normalization, validation, and multiple representation formats.
"""

import pytest
from paper_scanner.core.doi import DOI


class TestDOIInitialization:
    """Test DOI initialization and validation."""

    def test_init_valid_raw_doi(self):
        """Test initializing with raw DOI stem."""
        doi = DOI("10.1000/182")
        assert doi.stem == "10.1000/182"

    def test_init_valid_url_https(self):
        """Test initializing with HTTPS URL."""
        doi = DOI("https://doi.org/10.1000/182")
        assert doi.stem == "10.1000/182"

    def test_init_valid_url_http(self):
        """Test initializing with HTTP URL."""
        doi = DOI("http://doi.org/10.1000/182")
        assert doi.stem == "10.1000/182"

    def test_init_valid_prefix_doi_colon(self):
        """Test initializing with doi: prefix."""
        doi = DOI("doi:10.1000/182")
        assert doi.stem == "10.1000/182"

    def test_init_valid_prefix_doi_dot(self):
        """Test initializing with doi. prefix."""
        doi = DOI("doi.10.1000/182")
        assert doi.stem == "10.1000/182"

    def test_init_uppercase_normalized_to_lowercase(self):
        """Test that uppercase DOI is normalized to lowercase."""
        doi = DOI("10.1000/EXAMPLE")
        assert doi.stem == "10.1000/example"

    def test_init_whitespace_stripped(self):
        """Test that leading/trailing whitespace is stripped."""
        doi = DOI("  10.1000/182  ")
        assert doi.stem == "10.1000/182"

    def test_init_empty_string_raises_error(self):
        """Test that empty string raises ValueError."""
        with pytest.raises(ValueError, match="cannot be empty or None"):
            DOI("")

    def test_init_none_raises_error(self):
        """Test that None raises ValueError."""
        with pytest.raises(ValueError, match="cannot be empty or None"):
            DOI(None)

    def test_init_whitespace_only_raises_error(self):
        """Test that whitespace-only string raises ValueError."""
        with pytest.raises(ValueError, match="cannot be empty or None"):
            DOI("   ")

    def test_init_missing_slash_raises_error(self):
        """Test that DOI without slash raises ValueError."""
        with pytest.raises(ValueError, match="must contain prefix/suffix separated by '/'"):
            DOI("10.1000182")

    def test_init_invalid_prefix_not_starting_with_10_raises_error(self):
        """Test that prefix not starting with 10. raises ValueError."""
        with pytest.raises(ValueError, match="must start with '10.'"):
            DOI("11.1000/182")

    def test_init_invalid_prefix_11_raises_error(self):
        """Test that prefix 11 raises ValueError."""
        with pytest.raises(ValueError, match="must start with '10.'"):
            DOI("11.2000/example")

    def test_init_empty_prefix_raises_error(self):
        """Test that empty prefix raises ValueError."""
        with pytest.raises(ValueError, match="prefix and suffix cannot be empty"):
            DOI("/182")

    def test_init_empty_suffix_raises_error(self):
        """Test that empty suffix raises ValueError."""
        with pytest.raises(ValueError, match="prefix and suffix cannot be empty"):
            DOI("10.1000/")

    def test_init_complex_valid_doi(self):
        """Test initializing with complex valid DOI."""
        doi = DOI("10.1145/3025453.3025761")
        assert doi.stem == "10.1145/3025453.3025761"

    def test_init_multiple_slashes_uses_first(self):
        """Test that multiple slashes are handled correctly (first / separates prefix/suffix)."""
        doi = DOI("10.1000/path/to/resource")
        assert doi.stem == "10.1000/path/to/resource"


class TestDOIProperties:
    """Test DOI property methods."""

    def test_url_property(self):
        """Test URL property format."""
        doi = DOI("10.1000/182")
        assert doi.url == "https://doi.org/10.1000/182"

    def test_url_property_with_complex_doi(self):
        """Test URL property with complex DOI."""
        doi = DOI("10.1145/3025453.3025761")
        assert doi.url == "https://doi.org/10.1145/3025453.3025761"

    def test_prefix_property_default_delimiter(self):
        """Test prefix property with default delimiter."""
        doi = DOI("10.1000/182")
        assert doi.uri == "doi:10.1000/182"

    def test_safe_property_replaces_special_chars(self):
        """Test safe property replaces /.: with underscore."""
        doi = DOI("10.1145/3025453.3025761")
        assert doi.safe == "10_1145_3025453_3025761"

    def test_safe_property_with_colons(self):
        """Test safe property handles colons."""
        doi = DOI("10.1000/182:v1")
        assert doi.safe == "10_1000_182_v1"

    def test_md5_property(self):
        """Test MD5 hash property."""
        doi = DOI("doi:10.1000/182")
        md5_hash = doi.md5
        assert len(md5_hash) == 32  # MD5 is 32 hex characters
        assert md5_hash == "91d574c9585eb3121c660ebfcd33d46d"  # Known MD5 of "10.1000/182"

    def test_md5_property_deterministic(self):
        """Test that MD5 property is deterministic."""
        doi1 = DOI("10.1000/182")
        doi2 = DOI("10.1000/182")
        assert doi1.md5 == doi2.md5

    def test_md5_property_different_for_different_doi(self):
        """Test that different DOIs produce different MD5 hashes."""
        doi1 = DOI("10.1000/182")
        doi2 = DOI("10.1000/183")
        assert doi1.md5 != doi2.md5


class TestDOIStringRepresentations:
    """Test DOI string representations."""

    def test_str_returns_stem(self):
        """Test that str() returns the stem."""
        doi = DOI("https://doi.org/10.1000/182")
        assert str(doi) == "10.1000/182"

    def test_repr_shows_doi_class(self):
        """Test that repr() shows DOI class representation."""
        doi = DOI("10.1000/182")
        assert repr(doi) == "DOI('10.1000/182')"

    def test_repr_with_complex_doi(self):
        """Test repr with complex DOI."""
        doi = DOI("10.1145/3025453.3025761")
        assert repr(doi) == "DOI('10.1145/3025453.3025761')"


class TestDOINormalization:
    """Test DOI normalization from various formats."""

    def test_normalize_from_url_https(self):
        """Test normalization from HTTPS URL."""
        doi = DOI("HTTPS://DOI.ORG/10.1000/182")  # Uppercase
        assert doi.stem == "10.1000/182"

    def test_normalize_from_url_http(self):
        """Test normalization from HTTP URL."""
        doi = DOI("HTTP://DOI.ORG/10.1000/182")
        assert doi.stem == "10.1000/182"

    def test_normalize_preserves_case_insensitivity(self):
        """Test that all formats normalize to lowercase."""
        formats = [
            "10.1000/EXAMPLE",
            "https://doi.org/10.1000/EXAMPLE",
            "DOI:10.1000/EXAMPLE",
            "DOI.10.1000/EXAMPLE",
        ]
        stems = [DOI(fmt).stem for fmt in formats]
        assert all(stem == "10.1000/example" for stem in stems)

    def test_normalize_handles_mixed_case_url(self):
        """Test normalization with mixed case URL."""
        doi = DOI("HTTPS://DOI.ORG/10.1000/Example")
        assert doi.stem == "10.1000/example"


class TestDOIEdgeCases:
    """Test edge cases and special scenarios."""

    def test_doi_with_many_slashes_in_suffix(self):
        """Test DOI where suffix contains slashes."""
        doi = DOI("10.1000/path/to/resource/id")
        assert doi.stem == "10.1000/path/to/resource/id"
        assert "path/to/resource/id" in str(doi)

    def test_doi_with_numbers_only_prefix(self):
        """Test DOI with numeric prefix."""
        doi = DOI("10.12345/example")
        assert doi.stem == "10.12345/example"

    def test_doi_with_subdomain_prefix(self):
        """Test DOI with subdomain in prefix."""
        doi = DOI("10.1234.5678/example")
        assert doi.stem == "10.1234.5678/example"

    def test_doi_with_special_chars_in_suffix(self):
        """Test DOI with special characters in suffix."""
        doi = DOI("10.1000/example-v1_final.2024")
        assert doi.stem == "10.1000/example-v1_final.2024"

    def test_safe_property_handles_all_special_chars(self):
        """Test safe property with all special characters."""
        doi = DOI("10.1000/ex:am.ple/final(10)")
        safe = doi.safe
        assert "/" not in safe
        assert ":" not in safe
        assert "." not in safe
        assert "(" not in safe
        assert ")" not in safe
        assert "_" in safe
