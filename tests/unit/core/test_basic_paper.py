"""
Unit tests for paper_scanner.core.models

Tests for Author and other core model classes.
"""

import pytest
from datetime import datetime, timezone
from pydantic import ValidationError
from uuid import uuid4

from paper_scanner.core.models import Author, Paper, Discovery
from paper_scanner.core.enum import DiscoveryMethod, ScreeningDecision


class TestAuthorClass:
    """Test Author model"""

    def test_author_basic_creation(self):
        """Verify Author can be created with required fields"""
        author = Author(
            family_name="Smith",
            full_name="John Smith"
        )
        assert author.family_name == "Smith"
        assert author.full_name == "John Smith"
        assert author.given_name is None

    def test_author_with_all_fields(self):
        """Verify Author can be created with all fields"""
        author = Author(
            given_name="John",
            family_name="Smith",
            full_name="John Smith",
            affiliation="MIT",
            orcid="0000-0001-2345-6789",
            email="john.smith@mit.edu"
        )
        assert author.given_name == "John"
        assert author.family_name == "Smith"
        assert author.full_name == "John Smith"
        assert author.affiliation == "MIT"
        assert author.orcid == "0000-0001-2345-6789"
        assert author.email == "john.smith@mit.edu"

    def test_author_family_name_required(self):
        """Verify family_name is required"""
        with pytest.raises(ValidationError) as exc_info:
            Author(full_name="John Smith")
        
        errors = exc_info.value.errors()
        assert any(e['loc'] == ('family_name',) for e in errors)

    def test_author_full_name_required(self):
        """Verify full_name is required"""
        with pytest.raises(ValidationError) as exc_info:
            Author(family_name="Smith")
        
        errors = exc_info.value.errors()
        assert any(e['loc'] == ('full_name',) for e in errors)

    def test_author_last_name_property(self):
        """Verify last_name property returns family_name"""
        author = Author(
            family_name="Smith",
            full_name="John Smith"
        )
        assert author.last_name == "Smith"
        assert author.last_name == author.family_name

    def test_author_str_representation(self):
        """Verify __str__ returns full_name"""
        author = Author(
            family_name="Smith",
            full_name="John Smith"
        )
        assert str(author) == "John Smith"

    def test_author_str_with_special_characters(self):
        """Verify __str__ works with special characters in name"""
        author = Author(
            family_name="Müller",
            full_name="Hans Müller"
        )
        assert str(author) == "Hans Müller"

    def test_author_optional_fields_default_to_none(self):
        """Verify optional fields default to None"""
        author = Author(
            family_name="Smith",
            full_name="John Smith"
        )
        assert author.given_name is None
        assert author.affiliation is None
        assert author.orcid is None
        assert author.email is None

    def test_author_with_given_name_only(self):
        """Verify Author with given_name"""
        author = Author(
            given_name="Jane",
            family_name="Doe",
            full_name="Jane Doe"
        )
        assert author.given_name == "Jane"
        assert author.family_name == "Doe"

    def test_author_with_affiliation_only(self):
        """Verify Author with affiliation"""
        author = Author(
            family_name="Johnson",
            full_name="Alice Johnson",
            affiliation="Stanford University"
        )
        assert author.affiliation == "Stanford University"

    def test_author_with_orcid(self):
        """Verify Author with ORCID"""
        author = Author(
            family_name="Brown",
            full_name="Bob Brown",
            orcid="0000-0002-1234-5678"
        )
        assert author.orcid == "0000-0002-1234-5678"

    def test_author_with_email(self):
        """Verify Author with email"""
        author = Author(
            family_name="Wilson",
            full_name="Charlie Wilson",
            email="charlie@example.com"
        )
        assert author.email == "charlie@example.com"

    def test_author_equality(self):
        """Verify two authors with same data are equal"""
        author1 = Author(
            given_name="David",
            family_name="Lee",
            full_name="David Lee",
            affiliation="Oxford"
        )
        author2 = Author(
            given_name="David",
            family_name="Lee",
            full_name="David Lee",
            affiliation="Oxford"
        )
        assert author1 == author2

    def test_author_inequality(self):
        """Verify two authors with different data are not equal"""
        author1 = Author(
            family_name="Lee",
            full_name="David Lee"
        )
        author2 = Author(
            family_name="Kim",
            full_name="Sarah Kim"
        )
        assert author1 != author2

    def test_author_with_unicode_names(self):
        """Verify Author works with unicode names"""
        author = Author(
            family_name="Α λέκος",
            full_name="Ιωάννης Α λέκος"
        )
        assert author.family_name == "Α λέκος"
        assert author.full_name == "Ιωάννης Α λέκος"

    def test_author_with_hyphenated_name(self):
        """Verify Author works with hyphenated names"""
        author = Author(
            given_name="Mary-Jane",
            family_name="Smith-Johnson",
            full_name="Mary-Jane Smith-Johnson"
        )
        assert author.given_name == "Mary-Jane"
        assert author.family_name == "Smith-Johnson"

    def test_author_model_dump(self):
        """Verify Author can be dumped to dict"""
        author = Author(
            given_name="Emma",
            family_name="Taylor",
            full_name="Emma Taylor",
            affiliation="Cambridge",
            orcid="0000-0003-9999-8888",
            email="emma@cambridge.ac.uk"
        )
        dumped = author.model_dump()
        assert dumped["given_name"] == "Emma"
        assert dumped["family_name"] == "Taylor"
        assert dumped["full_name"] == "Emma Taylor"
        assert dumped["affiliation"] == "Cambridge"
        assert dumped["orcid"] == "0000-0003-9999-8888"
        assert dumped["email"] == "emma@cambridge.ac.uk"

    def test_author_model_dump_json(self):
        """Verify Author can be dumped to JSON"""
        author = Author(
            given_name="Frank",
            family_name="Miller",
            full_name="Frank Miller",
            affiliation="Harvard"
        )
        json_str = author.model_dump_json()
        assert "Frank" in json_str
        assert "Miller" in json_str
        assert "Harvard" in json_str

    def test_author_from_dict(self):
        """Verify Author can be created from dict"""
        data = {
            "given_name": "Grace",
            "family_name": "Harper",
            "full_name": "Grace Harper",
            "affiliation": "Yale"
        }
        author = Author(**data)
        assert author.given_name == "Grace"
        assert author.family_name == "Harper"

    def test_author_with_empty_given_name(self):
        """Verify Author handles empty string given_name"""
        author = Author(
            given_name="",
            family_name="Cohen",
            full_name="Cohen"
        )
        assert author.given_name == ""

    def test_author_with_empty_affiliation(self):
        """Verify Author handles empty string affiliation"""
        author = Author(
            family_name="Adams",
            full_name="Adam Adams",
            affiliation=""
        )
        assert author.affiliation == ""

    def test_author_with_empty_orcid(self):
        """Verify Author handles empty string ORCID"""
        author = Author(
            family_name="Baker",
            full_name="Ben Baker",
            orcid=""
        )
        assert author.orcid == ""

    def test_author_with_whitespace_in_fields(self):
        """Verify Author preserves whitespace in fields"""
        author = Author(
            given_name="  John  ",
            family_name="  Smith  ",
            full_name="  John Smith  ",
            affiliation="  MIT  "
        )
        assert author.given_name == "  John  "
        assert author.family_name == "  Smith  "
        assert author.affiliation == "  MIT  "

    def test_author_field_types(self):
        """Verify Author field types are correct"""
        author = Author(
            given_name="Isabel",
            family_name="Garcia",
            full_name="Isabel Garcia",
            affiliation="Stanford",
            orcid="0000-0001-2345-6789",
            email="isabel@stanford.edu"
        )
        assert isinstance(author.given_name, str)
        assert isinstance(author.family_name, str)
        assert isinstance(author.full_name, str)
        assert isinstance(author.affiliation, str)
        assert isinstance(author.orcid, str)
        assert isinstance(author.email, str)

    def test_author_pydantic_model(self):
        """Verify Author is a Pydantic BaseModel"""
        from pydantic import BaseModel
        author = Author(
            family_name="King",
            full_name="Kevin King"
        )
        assert isinstance(author, BaseModel)

    def test_author_copy(self):
        """Verify Author can be copied"""
        author1 = Author(
            given_name="Laura",
            family_name="Nelson",
            full_name="Laura Nelson",
            affiliation="Berkeley"
        )
        author2 = author1.model_copy()
        assert author1 == author2
        assert author1 is not author2

    def test_author_copy_with_update(self):
        """Verify Author can be copied with updates"""
        author1 = Author(
            given_name="Michael",
            family_name="Owen",
            full_name="Michael Owen",
            affiliation="Oxford"
        )
        author2 = author1.model_copy(update={"affiliation": "Cambridge"})
        assert author1.affiliation == "Oxford"
        assert author2.affiliation == "Cambridge"
        assert author1.given_name == author2.given_name

    def test_author_with_numbers_in_name(self):
        """Verify Author works with numbers in names"""
        author = Author(
            family_name="123ABC",
            full_name="John 123ABC"
        )
        assert author.family_name == "123ABC"

    def test_author_with_special_characters_in_email(self):
        """Verify Author works with various email formats"""
        author = Author(
            family_name="Perry",
            full_name="Paul Perry",
            email="paul+tag@example.co.uk"
        )
        assert author.email == "paul+tag@example.co.uk"

    def test_author_multiple_instances_independent(self):
        """Verify multiple Author instances are independent"""
        author1 = Author(
            given_name="Quinn",
            family_name="Quinn",
            full_name="Quinn Quinn",
            affiliation="MIT"
        )
        author2 = Author(
            given_name="Riley",
            family_name="Riley",
            full_name="Riley Riley",
            affiliation="Harvard"
        )
        assert author1.given_name == "Quinn"
        assert author2.given_name == "Riley"
        assert author1.affiliation == "MIT"
        assert author2.affiliation == "Harvard"


class TestPaperClass:
    """Test Paper model"""

    def test_paper_basic_creation(self):
        """Verify Paper can be created with required fields"""
        discovery = Discovery(method=DiscoveryMethod.KEYWORD_SEARCH)
        paper = Paper(
            cite_key="smith2020",
            title="Test Paper",
            discovery=discovery
        )
        assert paper.cite_key == "smith2020"
        assert paper.title == "Test Paper"
        assert isinstance(paper.id, str)

    def test_paper_cite_key_required(self):
        """Verify cite_key is required"""
        with pytest.raises(ValidationError) as exc_info:
            Paper(
                title="Test Paper"
            )
        errors = exc_info.value.errors()
        assert any(e['loc'] == ('cite_key',) for e in errors)

    def test_paper_title_required(self):
        """Verify title is required"""
        discovery = Discovery(method=DiscoveryMethod.KEYWORD_SEARCH)
        with pytest.raises(ValidationError) as exc_info:
            Paper(
                cite_key="test2020"
            )
        errors = exc_info.value.errors()
        assert any(e['loc'] == ('title',) for e in errors)

    def test_paper_with_all_identifiers(self):
        """Verify Paper can have all identifier fields"""
        paper = Paper(
            cite_key="smith2020",
            title="Test Paper",
            doi="10.1234/test",
            arxiv_id="2001.00001",
            pmid="12345678",
            isbn="978-3-16-148410-0",
            issn="1234-5678",
            url="https://example.com/paper"
        )
        assert paper.doi == "10.1234/test"
        assert paper.arxiv_id == "2001.00001"
        assert paper.pmid == "12345678"
        assert paper.isbn == "978-3-16-148410-0"
        assert paper.issn == "1234-5678"
        assert paper.url == "https://example.com/paper"

    def test_paper_with_authors(self):
        """Verify Paper can have authors"""
        author1 = Author(given_name="John", family_name="Smith", full_name="John Smith")
        author2 = Author(given_name="Jane", family_name="Doe", full_name="Jane Doe")
        paper = Paper(
            cite_key="smith2020",
            title="Test Paper",
            authors=[author1, author2]
        )
        assert len(paper.authors) == 2
        assert paper.authors[0].family_name == "Smith"
        assert paper.authors[1].family_name == "Doe"

    def test_paper_with_publication_details(self):
        """Verify Paper can have publication details"""
        paper = Paper(
            cite_key="smith2020",
            title="Test Paper",
            journal="Nature",
            volume="500",
            number="5",
            pages="123-145",
            publisher="Springer",
            year=2020
        )
        assert paper.journal == "Nature"
        assert paper.volume == "500"
        assert paper.number == "5"
        assert paper.pages == "123-145"
        assert paper.publisher == "Springer"
        assert paper.year == 2020

    def test_paper_author_string_single_author(self):
        """Verify author_string property with single author"""
        author = Author(given_name="John", family_name="Smith", full_name="John Smith")
        paper = Paper(
            cite_key="smith2020",
            title="Test Paper",
            authors=[author]
        )
        assert paper.author_string == "Smith"

    def test_paper_author_string_two_authors(self):
        """Verify author_string property with two authors"""
        author1 = Author(given_name="John", family_name="Smith", full_name="John Smith")
        author2 = Author(given_name="Jane", family_name="Doe", full_name="Jane Doe")
        paper = Paper(
            cite_key="smith2020",
            title="Test Paper",
            authors=[author1, author2]
        )
        assert paper.author_string == "Smith & Doe"

    def test_paper_author_string_multiple_authors(self):
        """Verify author_string property with multiple authors"""
        author1 = Author(given_name="John", family_name="Smith", full_name="John Smith")
        author2 = Author(given_name="Jane", family_name="Doe", full_name="Jane Doe")
        author3 = Author(given_name="Bob", family_name="Johnson", full_name="Bob Johnson")
        discovery = Discovery(method=DiscoveryMethod.KEYWORD_SEARCH)
        paper = Paper(
            cite_key="smith2020",
            title="Test Paper",
            authors=[author1, author2, author3],
            discovery=discovery
        )
        assert paper.author_string == "Smith et al."

    def test_paper_author_string_no_authors(self):
        """Verify author_string property with no authors"""
        discovery = Discovery(method=DiscoveryMethod.KEYWORD_SEARCH)
        paper = Paper(
            cite_key="unknown2020",
            title="Test Paper",
            discovery=discovery
        )
        assert paper.author_string == "Unknown"

    def test_paper_citation_key_apa_with_author(self):
        """Verify citation_key_apa property with author"""
        author = Author(given_name="John", family_name="Smith", full_name="John Smith")
        discovery = Discovery(method=DiscoveryMethod.KEYWORD_SEARCH)
        paper = Paper(
            cite_key="smith2020",
            title="Test Paper",
            authors=[author],
            year=2020,
            discovery=discovery
        )
        assert paper.citation_key_apa == "Smith, 2020"

    def test_paper_citation_key_apa_no_author(self):
        """Verify citation_key_apa property without author"""
        discovery = Discovery(method=DiscoveryMethod.KEYWORD_SEARCH)
        paper = Paper(
            cite_key="unknown",
            title="Test Paper",
            year=2020,
            discovery=discovery
        )
        assert paper.citation_key_apa == "Unknown, 2020"

    def test_paper_citation_key_apa_no_year(self):
        """Verify citation_key_apa property without year"""
        author = Author(given_name="John", family_name="Smith", full_name="John Smith")
        discovery = Discovery(method=DiscoveryMethod.KEYWORD_SEARCH)
        paper = Paper(
            cite_key="smith",
            title="Test Paper",
            authors=[author],
            discovery=discovery
        )
        assert paper.citation_key_apa == "Smith, n.d."

    def test_paper_is_included_property(self):
        """Verify is_included property reflects screening decision"""
        discovery = Discovery(method=DiscoveryMethod.KEYWORD_SEARCH)
        paper = Paper(
            cite_key="test2020",
            title="Test Paper",
            discovery=discovery
        )
        # Default is PENDING
        assert paper.is_included is False
        
        # Update to INCLUDED
        paper.screening.final_decision = ScreeningDecision.INCLUDED
        assert paper.is_included is True

    def test_paper_is_processed_with_pending_decision(self):
        """Verify is_processed property returns False for PENDING"""
        discovery = Discovery(method=DiscoveryMethod.KEYWORD_SEARCH)
        paper = Paper(
            cite_key="test2020",
            title="Test Paper",
            discovery=discovery
        )
        # Default screening decision is PENDING
        assert paper.is_processed is False

    def test_paper_is_processed_with_excluded_decision(self):
        """Verify is_processed property returns True for EXCLUDED"""
        discovery = Discovery(method=DiscoveryMethod.KEYWORD_SEARCH)
        paper = Paper(
            cite_key="test2020",
            title="Test Paper",
            discovery=discovery
        )
        paper.screening.final_decision = ScreeningDecision.EXCLUDED
        assert paper.is_processed is True

    def test_paper_keywords_list(self):
        """Verify Paper can have keywords"""
        discovery = Discovery(method=DiscoveryMethod.KEYWORD_SEARCH)
        paper = Paper(
            cite_key="test2020",
            title="Test Paper",
            keywords=["machine learning", "AI", "neural networks"],
            discovery=discovery
        )
        assert len(paper.keywords) == 3
        assert "machine learning" in paper.keywords

    def test_paper_abstract(self):
        """Verify Paper can have abstract"""
        abstract_text = "This is a test abstract about machine learning."
        discovery = Discovery(method=DiscoveryMethod.KEYWORD_SEARCH)
        paper = Paper(
            cite_key="test2020",
            title="Test Paper",
            abstract=abstract_text,
            discovery=discovery
        )
        assert paper.abstract == abstract_text

    def test_paper_deduplication_fields(self):
        """Verify Paper deduplication fields"""
        discovery = Discovery(method=DiscoveryMethod.KEYWORD_SEARCH)
        orig_paper = Paper(
            cite_key="test2020",
            title="Test Paper",
            discovery=discovery
        )
        paper = Paper(
            cite_key="test2010",
            title="Test Paper 2",
            duplicate_of=orig_paper,
            discovery=discovery
        )
        assert paper.duplicate_of.cite_key == "test2020"

    def test_paper_citation_counts(self):
        """Verify Paper citation count fields"""
        discovery = Discovery(method=DiscoveryMethod.KEYWORD_SEARCH)
        paper = Paper(
            cite_key="test2020",
            title="Test Paper",
            reference_count=15,
            citation_count=42,
            discovery=discovery
        )
        assert paper.reference_count == 15
        assert paper.citation_count == 42

    def test_paper_raw_data_fields(self):
        """Verify Paper can store raw data"""
        discovery = Discovery(method=DiscoveryMethod.KEYWORD_SEARCH)
        raw_bibtex = "@article{test2020, title={Test}, year={2020}}"
        raw_json = {"title": "Test", "year": 2020}
        paper = Paper(
            cite_key="test2020",
            title="Test Paper",
            raw_bibtex=raw_bibtex,
            raw_json=raw_json,
            discovery=discovery
        )
        assert paper.raw_bibtex == raw_bibtex
        assert paper.raw_json == raw_json

    def test_paper_timestamps_auto_generated(self):
        """Verify Paper timestamps are auto-generated"""
        discovery = Discovery(method=DiscoveryMethod.KEYWORD_SEARCH)
        paper = Paper(
            cite_key="test2020",
            title="Test Paper",
            discovery=discovery
        )
        assert isinstance(paper.created_at, datetime)
        assert isinstance(paper.updated_at, datetime)
        assert paper.created_at.tzinfo is not None

    def test_paper_validation_fields(self):
        """Verify Paper validation tracking fields"""
        discovery = Discovery(method=DiscoveryMethod.KEYWORD_SEARCH)
        paper = Paper(
            cite_key="test2020",
            title="Test Paper",
            manually_validated=True,
            validation_notes="Manually checked for quality",
            validated_by="user123",
            validated_at=datetime.now(timezone.utc),
            discovery=discovery
        )
        assert paper.manually_validated is True
        assert paper.validation_notes == "Manually checked for quality"
        assert paper.validated_by == "user123"

    def test_paper_language_default(self):
        """Verify Paper language defaults to English"""
        discovery = Discovery(method=DiscoveryMethod.KEYWORD_SEARCH)
        paper = Paper(
            cite_key="test2020",
            title="Test Paper",
            discovery=discovery
        )
        assert paper.language == "en"

    def test_paper_language_custom(self):
        """Verify Paper language can be set"""
        discovery = Discovery(method=DiscoveryMethod.KEYWORD_SEARCH)
        paper = Paper(
            cite_key="test2020",
            title="Test Paper",
            language="fr",
            discovery=discovery
        )
        assert paper.language == "fr"

    def test_paper_discovery_with_different_methods(self):
        """Verify Paper discovery can use different methods"""
        methods = [
            DiscoveryMethod.KEYWORD_SEARCH,
            DiscoveryMethod.BACKWARD_CITATION,
            DiscoveryMethod.FORWARD_CITATION,
            DiscoveryMethod.MANUAL,
        ]
        for method in methods:
            discovery = Discovery(method=method)
            paper = Paper(
                cite_key="test",
                title="Test Paper",
                discovery=discovery
            )
            assert paper.discovery.method == method

    def test_paper_model_dump(self):
        """Verify Paper can be dumped to dict"""
        author = Author(given_name="John", family_name="Smith", full_name="John Smith")
        discovery = Discovery(method=DiscoveryMethod.KEYWORD_SEARCH)
        paper = Paper(
            cite_key="test2020",
            title="Test Paper",
            doi="10.1234/test",
            authors=[author],
            year=2020,
            discovery=discovery
        )
        dumped = paper.model_dump()
        assert dumped["cite_key"] == "test2020"
        assert dumped["title"] == "Test Paper"
        assert dumped["doi"] == "10.1234/test"
        assert dumped["year"] == 2020

    def test_paper_cited_by_references(self):
        """Verify Paper can track citations"""
        discovery = Discovery(method=DiscoveryMethod.KEYWORD_SEARCH)
        paper = Paper(
            cite_key="test2020",
            title="Test Paper",
            cited_by=["paper1", "paper2", "paper3"],
            discovery=discovery
        )
        assert len(paper.cited_by) == 3
        assert "paper1" in paper.cited_by

    def test_paper_booktitle_for_conference(self):
        """Verify Paper can have booktitle for conference papers"""
        discovery = Discovery(method=DiscoveryMethod.KEYWORD_SEARCH)
        paper = Paper(
            cite_key="conf2020",
            title="Conference Paper",
            booktitle="Proceedings of ICML 2020",
            discovery=discovery
        )
        assert paper.booktitle == "Proceedings of ICML 2020"

    def test_paper_journal_abbreviation(self):
        """Verify Paper can have journal abbreviation"""
        discovery = Discovery(method=DiscoveryMethod.KEYWORD_SEARCH)
        paper = Paper(
            cite_key="nature2020",
            title="Nature Paper",
            journal="Nature Machine Intelligence",
            journal_abbreviation="Nat. Mach. Intell.",
            discovery=discovery
        )
        assert paper.journal_abbreviation == "Nat. Mach. Intell."

    def test_paper_publication_date(self):
        """Verify Paper can have publication date"""
        pub_date = datetime(2020, 3, 15, tzinfo=timezone.utc)
        discovery = Discovery(method=DiscoveryMethod.KEYWORD_SEARCH)
        paper = Paper(
            cite_key="test2020",
            title="Test Paper",
            publication_date=pub_date,
            discovery=discovery
        )
        assert paper.publication_date == pub_date

    def test_paper_unique_ids_generated(self):
        """Verify each Paper gets unique ID"""
        discovery = Discovery(method=DiscoveryMethod.KEYWORD_SEARCH)
        paper1 = Paper(
            cite_key="test1",
            title="Test Paper 1",
            discovery=discovery
        )
        paper2 = Paper(
            cite_key="test2",
            title="Test Paper 2",
            discovery=discovery
        )
        assert paper1.id != paper2.id

    def test_paper_str_representation(self):
        """Verify Paper has string representation"""
        discovery = Discovery(method=DiscoveryMethod.KEYWORD_SEARCH)
        paper = Paper(
            cite_key="smith2020",
            title="Test Paper",
            discovery=discovery
        )
        # Just verify __str__ doesn't raise an error
        str_repr = str(paper)
        assert isinstance(str_repr, str)
