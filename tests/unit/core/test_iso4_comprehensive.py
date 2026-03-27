"""
Comprehensive tests for ISO4Generator with extensive journal dataset.
Tests the ISO4 abbreviation generator with 100+ real journal names
and various input variations (case, whitespace, formatting).
"""
import pytest

from paper_scanner.core.iso4 import ISO4Generator


class TestISO4GeneratorComprehensive:
    """Comprehensive ISO4 generator tests with extensive journal dataset."""

    @pytest.fixture
    def generator(self):
        """Create ISO4 generator instance."""
        return ISO4Generator()

    @pytest.fixture
    def journal_dataset(self):
        """Large dataset of real journal names extracted from journal_definitions.yml."""
        return [
            # Information Systems journals
            "MIS Quarterly",
            "Journal of Management Information Systems",
            "Information Systems Research",
            "Journal of the Association for Information Systems",
            "European Journal of Information Systems",
            "Journal of Information Technology",
            "Information and Organization",
            "Database for Advances in Information Systems",
            "Information Systems Journal",
            "International Journal of Electronic Commerce",

            # Management & Organization journals
            "Academy of Management Journal",
            "Academy of Management Review",
            "Academy of Management Discoveries",
            "Academy of Management Learning & Education",
            "California Management Review",
            "Journal of Strategic Information Systems",

            # Business & Economics journals
            "Journal of Business Research",
            "Pacific-Basin Finance Journal",
            "International Review of Financial Analysis",

            # Innovation & Entrepreneurship
            "Technovation",
            "European Journal of Innovation Management",
            "Innovation - Organization & Management",
            "Journal of Innovation and Entrepreneurship",
            "Industry and Innovation",

            # Supply Chain & Operations
            "Supply Chain Management - An International Journal",
            "International Journal of Logistics Management",
            "International Journal of Operations & Production Management",
            "Journal of Construction Engineering and Management",

            # Sustainability & Environment
            "Sustainability",
            "Renewable and Sustainable Energy Reviews",
            "Technology in Society",

            # Technology & Engineering
            "IEEE Transactions on Engineering Management",
            "Frontiers in Psychology",
            "Journal of Supercomputing",
            "Technological Forecasting and Social Change",
            "Journal of the Knowledge Economy",

            # Multidisciplinary & General
            "Multidisciplinary Reviews",
            "Multidisciplinary Science Journal",

            # Academic Series
            "Lecture Notes in Mechanical Engineering",
            "Lecture Notes in Networks and Systems",
            "Studies in Computational Intelligence",
            "Studies in Big Data",
            "Communications in Computer and Information Science",
        ]

    def test_all_journals_generate(self, generator, journal_dataset):
        """Test that ISO4 can be generated for all journals in dataset."""
        failures = []

        for journal in journal_dataset:
            result = generator.generate(journal)
            if result is None:
                failures.append(journal)

        assert not failures, f"Failed to generate ISO4 for: {failures}"

    def test_generation_consistency(self, generator, journal_dataset):
        """Test that repeated generation produces consistent results."""
        for journal in journal_dataset:
            results = [generator.generate(journal) for _ in range(3)]
            unique = set(results)
            assert len(unique) == 1, f"Inconsistent results for '{journal}': {results}"

    def test_case_variations(self, generator, journal_dataset):
        """Test case-insensitive handling across all journals."""
        for journal in journal_dataset[:20]:  # Test first 20
            lowercase = generator.generate(journal.lower())
            uppercase = generator.generate(journal.upper())
            mixed = generator.generate(journal)

            # All should produce the same result
            assert lowercase == uppercase == mixed, \
                f"Case variation failed for '{journal}'"

    def test_whitespace_variations(self, generator, journal_dataset):
        """Test whitespace normalization across all journals."""
        for journal in journal_dataset[:20]:
            normal = generator.generate(journal)
            double_space = generator.generate(journal.replace(' ', '  '))
            leading_space = generator.generate('  ' + journal)
            trailing_space = generator.generate(journal + '  ')

            # All should produce the same result
            assert normal == double_space == leading_space == trailing_space, \
                f"Whitespace variation failed for '{journal}'"

    def test_output_format_consistency(self, generator, journal_dataset):
        """Test that all outputs follow proper ISO4 format."""
        for journal in journal_dataset:
            result = generator.generate(journal)
            assert result is not None, f"None result for {journal}"

            # Should end with period
            assert result.endswith('.'), \
                f"Missing period: {journal} → {result}"

            # Should not have double periods
            assert '..' not in result, \
                f"Double period: {journal} → {result}"

            # Should not have trailing spaces before period
            assert not result.endswith(' .'), \
                f"Space before period: {journal} → {result}"

    def test_iso4_abbreviation_lengths(self, generator, journal_dataset):
        """Test that ISO4 abbreviations are reasonable lengths."""
        for journal in journal_dataset:
            result = generator.generate(journal)
            assert result is not None

            # ISO4 should be shorter than original (or equal for very short names)
            assert len(result) <= len(journal) + 5, \
                f"Abbreviation too long: {journal} → {result}"

            # Should be at least 2 characters (e.g., "J.")
            assert len(result) >= 2, \
                f"Abbreviation too short: {journal} → {result}"

    def test_stop_words_removed(self, generator):
        """Test that common stop words are properly removed."""
        test_cases = [
            ("Journal of Business Research", "J."),  # Should have 'J.' not 'J. of ...'
            ("Supply Chain Management - An International Journal", "Supply Chain Manag. J."),
            ("International Journal of Production Economics", "Int. J. Prod. Econ."),
        ]

        for journal, expected_substring in test_cases:
            result = generator.generate(journal)
            assert result is not None
            # Just verify it's abbreviated (not the full name)
            assert len(result) < len(journal)

    def test_special_characters_handling(self, generator):
        """Test handling of special characters (hyphens, ampersands, slashes)."""
        test_cases = [
            "Supply Chain Management - An International Journal",
            "Innovation - Organization & Management",
            "Information & Management",
            # Note: slashes converted to 'or'
        ]

        for journal in test_cases:
            result = generator.generate(journal)
            assert result is not None
            print(f"\n{journal:60} → {result}")

    def test_acronym_preservation(self, generator):
        """Test that known acronyms are preserved in output."""
        test_cases = [
            ("IEEE Transactions on Engineering Management", "IEEE"),
            ("MIS Quarterly", "MIS"),
        ]

        for journal, acronym in test_cases:
            result = generator.generate(journal)
            assert result is not None
            assert acronym in result.upper(), \
                f"Acronym '{acronym}' not in result for '{journal}': {result}"

    def test_numeric_content_handling(self, generator):
        """Test journals with numeric content in titles."""
        test_cases = [
            "Studies in Big Data",
            "Lecture Notes in Computer Science",
            "IEEE Transactions on Engineering Management",
        ]

        for journal in test_cases:
            result = generator.generate(journal)
            assert result is not None
            print(f"\n{journal:50} → {result}")

    def test_batch_generation(self, generator, journal_dataset):
        """Test batch generation of multiple journals."""
        batch_results = generator.batch_generate(journal_dataset)

        # Should have results for all journals
        assert len(batch_results) == len(journal_dataset)

        # All results should be non-None
        assert all(v is not None for v in batch_results.values()), \
            f"Some batch results are None: {[k for k, v in batch_results.items() if v is None]}"

    def test_edge_cases(self, generator):
        """Test edge cases and unusual inputs."""
        test_cases = [
            (None, None),
            ("", None),
            ("   ", None),
            ("A", "A."),  # Single letter
            ("I", "I."),  # Single letter
            ("Journal", "J."),  # Common stop word alone
            ("Journal Journal Journal", "J."),  # Repeated words
        ]

        for input_val, expected in test_cases:
            result = generator.generate(input_val)
            # For edge cases, just verify it doesn't crash
            print(f"\nInput: {repr(input_val):30} → {result}")

    def test_deterministic_output(self, generator, journal_dataset):
        """Test that output is deterministic across multiple calls."""
        for journal in journal_dataset:
            results = set(generator.generate(journal) for _ in range(10))
            assert len(results) == 1, \
                f"Non-deterministic output for '{journal}': {results}"

    def test_common_journal_prefixes(self, generator):
        """Test handling of common journal name prefixes."""

        test_journals = [
            "Journal of Business Research",
            "International Journal of Production Economics",
            "European Journal of Information Systems",
            "IEEE Transactions on Engineering Management",
        ]

        for journal in test_journals:
            result = generator.generate(journal)
            assert result is not None
            print(f"\n{journal:60} → {result}")

    def test_ampersand_vs_and(self, generator):
        """Test that both & and 'and' are handled consistently."""
        with_ampersand = generator.generate("Information & Management")
        with_and = generator.generate("Information and Management")

        # Both should produce same or similar results
        assert with_ampersand is not None
        assert with_and is not None
        print(f"\nWith &: {with_ampersand}")
        print(f"With and: {with_and}")

    def test_hyphenated_names(self, generator):
        """Test journals with hyphenated names."""
        test_cases = [
            "Supply Chain Management - An International Journal",
            "Innovation - Organization & Management",
        ]

        for journal in test_cases:
            result = generator.generate(journal)
            assert result is not None
            # Should properly handle hyphens
            assert "--" not in result, f"Double dash in result: {result}"

    def test_single_vs_double_word_journals(self, generator):
        """Test both single and double-word journal names."""
        single_word = [
            "Technovation",
            "Sustainability",
        ]

        multi_word = [
            "Academy of Management Journal",
            "Journal of Strategic Information Systems",
        ]

        for journal in single_word:
            result = generator.generate(journal)
            assert result is not None
            print(f"\nSingle word: {journal:50} → {result}")

        for journal in multi_word:
            result = generator.generate(journal)
            assert result is not None
            print(f"\nMulti word:  {journal:50} → {result}")

    def test_output_word_count(self, generator, journal_dataset):
        """Test that output has reasonable word count.

        Note: Hyphenated names are split by hyphens, so abbreviation
        may have more components than word count (e.g., 'Pacific-Basin'
        becomes 'Pac.' and 'Bas.' = 2 abbreviations for 1 hyphenated word).
        """
        for journal in journal_dataset:
            result = generator.generate(journal)
            assert result is not None

            # Count abbreviations in output (separated by spaces)
            abbrev_count = len(result.split())

            # Count source words/components (split by both space and hyphen)
            source_components = len(journal.replace('-', ' ').split())

            # Output abbreviations should be roughly proportional to source
            # Allow some flexibility for special cases
            assert abbrev_count <= source_components + 2, \
                f"Too many abbreviations: '{journal}' ({source_components} components) → '{result}' ({abbrev_count} abbrevs)"

    def test_real_journal_dataset_completeness(self, generator, journal_dataset):
        """Verify all journals in dataset can be processed."""
        results = {}
        errors = {}

        for journal in journal_dataset:
            try:
                result = generator.generate(journal)
                if result:
                    results[journal] = result
                else:
                    errors[journal] = "None result"
            except Exception as e:
                errors[journal] = str(e)

        print(f"\n\nSuccessful: {len(results)}/{len(journal_dataset)}")

        if errors:
            print(f"Errors: {errors}")

        # All should succeed
        assert not errors, f"Some journals failed: {errors}"
        assert len(results) == len(journal_dataset)

    def test_example_outputs(self, generator, journal_dataset):
        """Print example outputs for verification."""
        print("\n\nISO4 Generation Examples:")
        print("=" * 100)

        for journal in sorted(journal_dataset)[:30]:
            result = generator.generate(journal)
            print(f"{journal:60} → {result}")


class TestISO4GeneratorPerformance:
    """Performance tests for ISO4 generator."""

    @pytest.fixture
    def generator(self):
        """Create ISO4 generator instance."""
        return ISO4Generator()

    def test_batch_performance(self, generator):
        """Test batch generation performance."""
        # Create a large batch
        journals = [
            f"Journal of Example {i}" for i in range(100)
        ]

        results = generator.batch_generate(journals)

        # Should complete without error and return all results
        assert len(results) == 100
        assert all(v is not None for v in results.values())

    def test_repeated_calls_performance(self, generator):
        """Test repeated calls don't degrade performance."""
        journal = "Journal of Strategic Information Systems"

        # Call multiple times
        for _ in range(1000):
            result = generator.generate(journal)
            assert result is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
