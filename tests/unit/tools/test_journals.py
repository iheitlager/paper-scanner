"""Unit tests for JournalLookup library."""
import tempfile
from pathlib import Path

import pytest
import yaml

from paper_scanner.tools.documents.journals import JournalLookup


@pytest.fixture
def temp_journal_definitions():
    """Create a temporary journal definitions YAML file for testing."""
    journals_data = {
        'journals': {
            'Journal of Business Research': {
                'acronym': 'JBR',
                'iso4': 'J. Bus. Res.'
            },
            'Management Science': {
                'acronym': 'MS',
                'iso4': 'Manag. Sci.'
            },
            'Academy of Management Journal': {
                'acronym': 'AMJ',
                'iso4': 'Acad. Manag. J.'
            }
        },
        'views': {
            'test_view': ['Journal of Business Research', 'Management Science']
        }
    }

    with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
        yaml.dump(journals_data, f)
        temp_path = f.name

    yield temp_path

    # Cleanup
    Path(temp_path).unlink(missing_ok=True)


class TestJournalLookup:
    """Test JournalLookup with temporary definitions file."""

    def test_lookup_with_custom_file(self, temp_journal_definitions):
        """Test loading custom journal definitions file."""
        jl = JournalLookup(temp_journal_definitions)
        assert jl.get_journal_count() == 3

    def test_lookup_exact_match(self, temp_journal_definitions):
        """Test exact journal name lookup."""
        jl = JournalLookup(temp_journal_definitions)
        result = jl.lookup('Journal of Business Research')
        assert result == ('Journal of Business Research', 'JBR', 'J. Bus. Res.')

    def test_lookup_case_insensitive(self, temp_journal_definitions):
        """Test case-insensitive lookup."""
        jl = JournalLookup(temp_journal_definitions)
        result = jl.lookup('management science')
        assert result[0] == 'Management Science'
        assert result[1] == 'MS'

    def test_lookup_whitespace_normalization(self, temp_journal_definitions):
        """Test whitespace normalization in lookup."""
        jl = JournalLookup(temp_journal_definitions)
        result = jl.lookup('  Academy   of   Management   Journal  ')
        assert result[0] == 'Academy of Management Journal'
        assert result[1] == 'AMJ'

    def test_lookup_not_found(self, temp_journal_definitions):
        """Test ValueError raised for unknown journal."""
        jl = JournalLookup(temp_journal_definitions)
        with pytest.raises(ValueError) as exc_info:
            jl.lookup('Unknown Journal')
        assert 'Unknown Journal' in str(exc_info.value)

    def test_lookup_invalid_input(self, temp_journal_definitions):
        """Test ValueError raised for invalid input."""
        jl = JournalLookup(temp_journal_definitions)
        with pytest.raises(ValueError):
            jl.lookup(None)

        with pytest.raises(ValueError):
            jl.lookup('')

    def test_list_journals(self, temp_journal_definitions):
        """Test listing all journals."""
        jl = JournalLookup(temp_journal_definitions)
        journals = jl.list_journals()
        assert len(journals) == 3
        assert 'Journal of Business Research' in journals
        assert 'Management Science' in journals

    def test_missing_file_raises_error(self):
        """Test FileNotFoundError for missing definitions file."""
        with pytest.raises(FileNotFoundError):
            JournalLookup('/nonexistent/path/to/journals.yml')

    def test_lookup_with_default_file(self):
        """Test that default etc/journal_definitions.yml can be loaded."""
        # This tests the actual production file
        jl = JournalLookup()
        assert jl.get_journal_count() >= 50

        # Verify some known journals from production file
        result = jl.lookup('Journal of Business Research')
        assert result[0] == 'Journal of Business Research'
        assert len(result) == 3  # name, acronym, iso4
