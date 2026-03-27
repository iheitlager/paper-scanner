"""
Test 03: Journal Lookup - Query journal definitions with variations
Tests journal lookup by name with case/whitespace variations and error handling.
"""
import pytest

from paper_scanner.tools.documents.journals import JournalLookup


class TestJournalLookup:
    """Test journal lookup and definition loading."""

    @pytest.fixture
    def journal_lookup(self):
        """Create journal lookup instance with test definitions."""
        # Use the actual etc/journal_definitions.yml file
        return JournalLookup()

    def test_load_definitions(self, journal_lookup):
        """Test that definitions are loaded successfully."""
        assert journal_lookup.get_journal_count() > 0
        print(f"\nLoaded {journal_lookup.get_journal_count()} journals")

    def test_journal_count(self, journal_lookup):
        """Test that reasonable number of journals are loaded."""
        count = journal_lookup.get_journal_count()
        assert count >= 50, f"Expected at least 50 journals, got {count}"
        print(f"\nLoaded {count} journals")

    def test_exact_match_lookup(self, journal_lookup):
        """Test exact journal name lookup."""
        result = journal_lookup.lookup("Journal of Business Research")
        assert result[0] == "Journal of Business Research"
        assert result[1] == "JBR"
        assert result[2] == "J. Bus. Res."
        print(f"\nExact match: {result}")

    def test_case_insensitive_lookup(self, journal_lookup):
        """Test case-insensitive journal lookup."""
        test_cases = [
            "Journal of Business Research",
            "journal of business research",
            "JOURNAL OF BUSINESS RESEARCH",
            "Journal Of Business Research",
        ]

        results = [journal_lookup.lookup(name) for name in test_cases]

        # All should return same journal
        names = [r[0] for r in results]
        assert len(set(names)) == 1, f"Different names returned: {names}"
        print(f"\nCase insensitive results: {results[0]}")

    def test_whitespace_normalization_lookup(self, journal_lookup):
        """Test whitespace-normalized lookup."""
        test_cases = [
            "IEEE Transactions on Engineering Management",
            "IEEE  Transactions  on  Engineering  Management",
            "  IEEE Transactions on Engineering Management  ",
        ]

        results = [journal_lookup.lookup(name) for name in test_cases]

        # All should return same journal
        names = [r[0] for r in results]
        assert len(set(names)) == 1
        assert results[0][1] == "TEM"
        print(f"\nWhitespace normalized: {results[0]}")

    def test_academy_journals_lookup(self, journal_lookup):
        """Test lookup of Academy of Management journals."""
        academy_journals = [
            "Academy of Management Journal",
            "Academy of Management Review",
            "Academy of Management Discoveries",
            "Academy of Management Learning & Education",
        ]

        for journal in academy_journals:
            result = journal_lookup.lookup(journal)
            assert result[0] == journal
            assert result[1] is not None
            assert result[2] is not None
            print(f"\n{journal:50} → {result[1]:5} / {result[2]}")

    def test_information_systems_journals(self, journal_lookup):
        """Test lookup of information systems journals."""
        is_journals = [
            "MIS Quarterly",
            "Journal of Management Information Systems",
            "Information Systems Research",
            "Journal of the Association for Information Systems",
        ]

        for journal in is_journals:
            result = journal_lookup.lookup(journal)
            assert result[0] == journal
            print(f"\n{journal:50} → {result[1]:5} / {result[2]}")

    def test_innovation_journals_lookup(self, journal_lookup):
        """Test lookup of innovation and entrepreneurship journals."""
        innovation_journals = [
            "Technovation",
            "Strategic Entrepreneurship Journal",
            "European Journal of Innovation Management",
            "Journal of Innovation and Entrepreneurship",
        ]

        for journal in innovation_journals:
            result = journal_lookup.lookup(journal)
            assert result[0] == journal
            print(f"\n{journal:50} → {result[1]:5} / {result[2]}")

    def test_lookup_returns_triplet(self, journal_lookup):
        """Test that lookup returns proper triplet."""
        name, acronym, iso4 = journal_lookup.lookup("Technovation")

        assert isinstance(name, str) and len(name) > 0
        assert isinstance(acronym, str) and len(acronym) > 0
        assert isinstance(iso4, str) and len(iso4) > 0
        print(f"\nTriplet: ({name}, {acronym}, {iso4})")

    def test_journal_not_found_error(self, journal_lookup):
        """Test that ValueError is raised for unknown journal."""
        with pytest.raises(ValueError):
            journal_lookup.lookup("Nonexistent Journal Name XYZ")

    def test_journal_not_found_error_message(self, journal_lookup):
        """Test error message contains helpful information."""
        with pytest.raises(ValueError) as exc_info:
            journal_lookup.lookup("Unknown Journal")

        error_msg = str(exc_info.value)
        assert "Unknown Journal" in error_msg
        print(f"\nError message: {error_msg}")

    def test_invalid_input_error(self, journal_lookup):
        """Test that invalid inputs raise ValueError."""
        test_cases = [
            None,
            "",
            "   ",
        ]

        for test_input in test_cases:
            with pytest.raises(ValueError):
                journal_lookup.lookup(test_input)

    def test_list_journals(self, journal_lookup):
        """Test listing all journals."""
        journals = journal_lookup.list_journals()
        assert len(journals) > 0
        assert "MIS Quarterly" in journals
        assert "Technovation" in journals
        print(f"\nTotal journals available: {len(journals)}")

    def test_lookup_with_generation(self, journal_lookup):
        """Test lookup with ISO4 generation fallback."""
        result = journal_lookup.lookup_with_generation("Journal of Business Research")
        name, acronym, iso4 = result

        assert name == "Journal of Business Research"
        assert acronym == "JBR"
        assert iso4 == "J. Bus. Res."
        print(f"\nWith generation: {result}")

    def test_all_retrieved_journals_valid(self, journal_lookup):
        """Test that all retrieved journals have valid metadata."""
        journals = journal_lookup.list_journals()

        for journal in journals[:20]:  # Test first 20
            name, acronym, iso4 = journal_lookup.lookup(journal)

            assert name == journal
            assert len(name) > 0
            assert len(acronym) > 0
            assert len(iso4) > 0

    def test_batch_lookup(self, journal_lookup):
        """Test looking up multiple journals."""
        test_journals = [
            "MIS Quarterly",
            "Technovation",
            "IEEE Transactions on Engineering Management",
            "Academy of Management Journal",
        ]

        results = {}
        for journal in test_journals:
            results[journal] = journal_lookup.lookup(journal)

        assert len(results) == len(test_journals)

        for journal, (name, acronym, iso4) in results.items():
            print(f"\n{journal:60} → {acronym:5} / {iso4}")

    def test_definition_file_location(self):
        """Test that default definition file path is correct."""
        # Should load without error
        lookup = JournalLookup()
        assert lookup.get_journal_count() > 0

    def test_custom_definition_file(self, tmp_path):
        """Test loading from custom definition file path."""
        # Create a minimal test definitions file
        test_yaml = tmp_path / "test_journals.yml"
        test_yaml.write_text("""
journals:
  "Test Journal":
    acronym: "TJ"
    iso4: "Test J."
""")

        lookup = JournalLookup(str(test_yaml))
        result = lookup.lookup("Test Journal")
        assert result[0] == "Test Journal"
        assert result[1] == "TJ"
        assert result[2] == "Test J."

    def test_missing_definition_file_error(self):
        """Test that FileNotFoundError is raised for missing file."""
        with pytest.raises(FileNotFoundError):
            JournalLookup("/nonexistent/path/journals.yml")

    def test_normalize_method(self):
        """Test journal name normalization."""
        test_cases = [
            ("Journal of Business Research", "journal of business research"),
            ("JOURNAL OF BUSINESS RESEARCH", "journal of business research"),
            ("  Journal  of  Business  Research  ", "journal of business research"),
            ("JoUrNaL oF bUsInEsS rEsEaRcH", "journal of business research"),
        ]

        for input_name, expected in test_cases:
            result = JournalLookup._normalize(input_name)
            assert result == expected, f"Normalization failed for '{input_name}'"


class TestJournalLookupEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.fixture
    def journal_lookup(self):
        """Create journal lookup instance."""
        return JournalLookup()

    def test_special_characters_in_names(self, journal_lookup):
        """Test journals with special characters."""
        test_journals = [
            "Information & Management",
            "Innovation - Organization & Management",
            "Supply Chain Management - An International Journal",
        ]

        for journal in test_journals:
            result = journal_lookup.lookup(journal)
            assert result[0] == journal
            print(f"\nSpecial chars: {journal} → {result[1]}")

    def test_repeated_lookups_consistency(self, journal_lookup):
        """Test that repeated lookups return same result."""
        journal = "MIS Quarterly"

        results = [journal_lookup.lookup(journal) for _ in range(5)]
        unique = set(results)

        assert len(unique) == 1, f"Inconsistent results: {results}"

    def test_acronym_format(self, journal_lookup):
        """Test that acronyms are reasonable."""
        journals = journal_lookup.list_journals()[:10]

        for journal in journals:
            _, acronym, _ = journal_lookup.lookup(journal)

            # Acronym should be non-empty and reasonable length
            assert len(acronym) > 0
            assert len(acronym) <= 20
            print(f"\nAcronym check: {journal:50} → {acronym}")

    def test_iso4_format(self, journal_lookup):
        """Test that ISO4 abbreviations have proper format."""
        journals = journal_lookup.list_journals()[:10]

        for journal in journals:
            _, _, iso4 = journal_lookup.lookup(journal)

            # ISO4 should be non-empty and reasonable
            assert len(iso4) > 0
            # Some ISO4 may not end with period (e.g., compound abbreviations)
            # but should contain abbreviation structure
            assert iso4[0].isupper() or iso4[0].isdigit(), f"ISO4 should start with capital: {iso4}"
            print(f"\nISO4 check: {journal:50} → {iso4}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
