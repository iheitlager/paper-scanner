"""
Unit tests for AbstractParser in tools/documents
"""

import pytest

from paper_scanner.tools.documents import AbstractParser


class TestAbstractParser:
    """Test suite for AbstractParser class"""

    def test_clean_with_jats_markup(self):
        """Test cleaning JATS XML formatted abstract"""
        jats_abstract = (
            '<jats:title>Abstract</jats:title>'
            '<jats:p>Digital transformation is a pivotal strategic pillar.</jats:p>'
        )
        cleaned = AbstractParser.clean(jats_abstract)

        assert cleaned is not None
        assert cleaned.startswith("Digital")
        assert "<jats:" not in cleaned
        assert "Abstract" not in cleaned

    def test_clean_with_html_markup(self):
        """Test cleaning HTML formatted abstract"""
        html_abstract = '<p>This is a test <b>abstract</b> with HTML tags.</p>'
        cleaned = AbstractParser.clean(html_abstract)

        assert cleaned == "This is a test abstract with HTML tags."
        assert "<p>" not in cleaned
        assert "<b>" not in cleaned

    def test_clean_removes_abstract_prefix(self):
        """Test that 'Abstract' prefix is removed"""
        abstract = "Abstract This is the actual abstract content."
        cleaned = AbstractParser.clean(abstract)

        assert cleaned == "This is the actual abstract content."

    def test_clean_case_insensitive_abstract_prefix(self):
        """Test that 'Abstract' prefix is removed case-insensitively"""
        abstract = "ABSTRACT This is the content."
        cleaned = AbstractParser.clean(abstract)

        assert cleaned == "This is the content."

    def test_clean_normalizes_whitespace(self):
        """Test that multiple spaces and newlines are normalized"""
        abstract = (
            "This  is   a   test\n\n"
            "with   multiple\n\n\nspaces   and   newlines."
        )
        cleaned = AbstractParser.clean(abstract)

        assert cleaned == "This is a test with multiple spaces and newlines."
        assert "\n" not in cleaned
        assert "  " not in cleaned

    def test_clean_handles_none(self):
        """Test that None input returns None"""
        assert AbstractParser.clean(None) is None

    def test_clean_handles_empty_string(self):
        """Test that empty string returns None"""
        assert AbstractParser.clean("") is None

    def test_clean_handles_whitespace_only(self):
        """Test that whitespace-only string returns None"""
        assert AbstractParser.clean("   \n\n  ") is None

    def test_clean_with_complex_jats_markup(self):
        """Test cleaning complex JATS abstract with title and multiple paragraphs"""
        complex_abstract = (
            '<jats:title>Abstract</jats:title>'
            '<jats:p>First paragraph with content.</jats:p>'
            '<jats:p>Second paragraph with more content.</jats:p>'
        )
        cleaned = AbstractParser.clean(complex_abstract)

        assert cleaned.startswith("First paragraph")
        assert "First paragraph with content." in cleaned
        assert "Second paragraph with more content." in cleaned
        assert "<jats:" not in cleaned

    def test_clean_preserves_text_content(self):
        """Test that actual text content is preserved"""
        abstract = (
            '<jats:title>Abstract</jats:title>'
            '<jats:p>Digital transformation is a pivotal strategic pillar for '
            'companies. Despite its relevance, incumbent companies still face '
            'challenges in implementation.</jats:p>'
        )
        cleaned = AbstractParser.clean(abstract)

        assert "Digital transformation" in cleaned
        assert "pivotal strategic pillar" in cleaned
        assert "incumbent companies" in cleaned
        assert "challenges in implementation" in cleaned

    def test_clean_with_mixed_markup(self):
        """Test cleaning abstract with mixed HTML and JATS tags"""
        mixed_abstract = (
            '<jats:title>Abstract</jats:title>'
            '<p><jats:p>This is a test.</jats:p></p>'
        )
        cleaned = AbstractParser.clean(mixed_abstract)

        assert cleaned == "This is a test."
        assert "<" not in cleaned
        assert ">" not in cleaned

    def test_clean_handles_special_characters(self):
        """Test that special characters are preserved"""
        abstract = "This includes: quotes\"test\", apostrophes\\'test\\', and symbols: &, <, >."
        cleaned = AbstractParser.clean(abstract)

        assert "quotes" in cleaned
        assert "apostrophes" in cleaned
        assert "symbols" in cleaned

    def test_clean_long_abstract(self):
        """Test cleaning a realistic long abstract"""
        long_abstract = (
            '<jats:title>Abstract</jats:title>'
            '<jats:p>Digital transformation is a pivotal strategic pillar for companies. '
            'Despite its relevance, incumbent companies still face challenges in '
            'implementation due to the complex character of transformation processes. '
            'We provide a framework serving as guidance for leaders of digital '
            'transformations. Based on an explorative research design, we conducted '
            '33 semi-structured interviews with experts of digital transformations '
            'of incumbent companies. Our findings indicate that leaders need to '
            'understand the terminologies related to exploration, exploitation, '
            'and digital transformation, and the complex interaction between all '
            'three areas.</jats:p>'
        )
        cleaned = AbstractParser.clean(long_abstract)

        assert cleaned.startswith("Digital transformation")
        assert "33 semi-structured interviews" in cleaned
        assert "<jats:" not in cleaned
        assert "Abstract" not in cleaned

    def test_remove_jats_tags_directly(self):
        """Test _remove_jats_tags method directly"""
        text = "<jats:title>Title</jats:title><jats:p>Content</jats:p>"
        result = AbstractParser._remove_jats_tags(text)

        # Should preserve content but remove tags
        assert "Title" in result
        assert "Content" in result
        assert "<jats:" not in result

    def test_remove_html_tags_directly(self):
        """Test _remove_html_tags method directly"""
        text = "<p>Hello</p><div>World</div>"
        result = AbstractParser._remove_html_tags(text)

        assert "Hello" in result
        assert "World" in result
        assert "<p>" not in result
        assert "<div>" not in result

    def test_normalize_whitespace_directly(self):
        """Test _normalize_whitespace method directly"""
        text = "Multiple   spaces\n\nand    newlines\t\there"
        result = AbstractParser._normalize_whitespace(text)

        assert result == "Multiple spaces and newlines here"

    def test_clean_idempotent(self):
        """Test that cleaning twice gives the same result"""
        abstract = '<jats:p>Test abstract.</jats:p>'
        first_clean = AbstractParser.clean(abstract)
        second_clean = AbstractParser.clean(first_clean)

        assert first_clean == second_clean


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
