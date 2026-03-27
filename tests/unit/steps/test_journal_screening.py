"""Unit tests for JournalScreeningStep."""
import tempfile
from pathlib import Path
from unittest.mock import Mock

import pytest
import yaml

from paper_scanner.core.enum import StepStatus
from paper_scanner.core.models import Paper
from paper_scanner.steps.journal_screening import JournalScreeningStep


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
            'academy': ['Academy of Management Journal'],
            'business': ['Journal of Business Research', 'Management Science']
        }
    }

    with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
        yaml.dump(journals_data, f)
        temp_path = f.name

    yield temp_path

    Path(temp_path).unlink(missing_ok=True)


@pytest.fixture
def mock_db():
    """Create a mock database."""
    db = Mock()
    db.all = Mock(return_value=[])
    db.update = Mock()
    return db


@pytest.fixture
def step(mock_db, tmp_path):
    """Create JournalScreeningStep instance."""
    general_config = {'project_name': 'test'}
    return JournalScreeningStep(
        general_config=general_config,
        db=mock_db,
        cache_dir=tmp_path
    )


class TestJournalScreeningValidate:
    """Test validation of journal_screening step configuration."""

    def test_validate_empty_config(self):
        """Test that empty config is valid."""
        is_valid, errors = JournalScreeningStep.validate({})
        assert is_valid
        assert len(errors) == 0

    def test_validate_with_valid_path(self, temp_journal_definitions):
        """Test validation with valid definitions path."""
        config = {'journal_definitions_path': temp_journal_definitions}
        is_valid, errors = JournalScreeningStep.validate(config)
        assert is_valid
        assert len(errors) == 0

    def test_validate_with_invalid_path(self):
        """Test validation with non-existent file."""
        config = {'journal_definitions_path': '/nonexistent/path.yml'}
        is_valid, errors = JournalScreeningStep.validate(config)
        assert not is_valid
        assert any('not found' in str(e).lower() for e in errors)

    def test_validate_with_invalid_path_type(self):
        """Test validation with non-string path."""
        config = {'journal_definitions_path': 123}
        is_valid, errors = JournalScreeningStep.validate(config)
        assert not is_valid
        assert any('must be a string' in str(e) for e in errors)

    def test_validate_required_views_valid(self):
        """Test validation with valid required_views."""
        config = {'required_views': ['academy', 'business']}
        is_valid, errors = JournalScreeningStep.validate(config)
        assert is_valid

    def test_validate_required_views_invalid_type(self):
        """Test validation with required_views not a list."""
        config = {'required_views': 'academy'}
        is_valid, errors = JournalScreeningStep.validate(config)
        assert not is_valid
        assert any('must be a list' in str(e) for e in errors)

    def test_validate_required_views_invalid_items(self):
        """Test validation with non-string items in required_views."""
        config = {'required_views': ['academy', 123]}
        is_valid, errors = JournalScreeningStep.validate(config)
        assert not is_valid

    def test_validate_generate_iso4_valid(self):
        """Test validation with valid generate_iso4."""
        config = {'generate_iso4': True}
        is_valid, errors = JournalScreeningStep.validate(config)
        assert is_valid

    def test_validate_generate_iso4_invalid(self):
        """Test validation with non-boolean generate_iso4."""
        config = {'generate_iso4': 'true'}
        is_valid, errors = JournalScreeningStep.validate(config)
        assert not is_valid

    def test_validate_skip_missing_valid(self):
        """Test validation with valid skip_missing."""
        config = {'skip_missing': True}
        is_valid, errors = JournalScreeningStep.validate(config)
        assert is_valid

    def test_validate_skip_missing_invalid(self):
        """Test validation with non-boolean skip_missing."""
        config = {'skip_missing': 'yes'}
        is_valid, errors = JournalScreeningStep.validate(config)
        assert not is_valid


class TestJournalScreeningExecute:
    """Test execution of journal_screening step."""

    def test_execute_empty_database(self, step, mock_db):
        """Test execution with no papers in database."""
        mock_db.all.return_value = []

        result = step.execute({})

        assert result.status == StepStatus.SUCCESS
        assert result.stats['total_papers'] == 0
        assert result.stats['papers_matched'] == 0

    def test_execute_with_matching_journals(self, step, mock_db, temp_journal_definitions):
        """Test execution with journals that match definitions."""
        paper1 = Mock(spec=Paper)
        paper1.id = '1'
        paper1.journal = 'Journal of Business Research'
        paper1.screening = {}

        paper2 = Mock(spec=Paper)
        paper2.id = '2'
        paper2.journal = 'Management Science'
        paper2.screening = {}

        mock_db.all.return_value = [paper1, paper2]

        result = step.execute({
            'journal_definitions_path': temp_journal_definitions
        })

        assert result.status == StepStatus.SUCCESS
        assert result.stats['total_papers'] == 2
        assert result.stats['papers_matched'] == 2

    def test_execute_with_missing_journals(self, step, mock_db):
        """Test execution with papers missing journal names."""
        paper = Mock(spec=Paper)
        paper.id = '1'
        paper.journal = None
        paper.screening = {}

        mock_db.all.return_value = [paper]

        result = step.execute({})

        assert result.stats['total_papers'] == 1
        assert result.stats['papers_with_errors'] == 1

    def test_execute_skip_missing_journals(self, step, mock_db):
        """Test execution with skip_missing enabled."""
        paper = Mock(spec=Paper)
        paper.id = '1'
        paper.journal = None
        paper.screening = {}

        mock_db.all.return_value = [paper]

        result = step.execute({
            'skip_missing': True
        })

        assert result.stats['total_papers'] == 1
        assert result.stats['papers_skipped'] == 1
        assert result.stats['papers_with_errors'] == 0

    def test_execute_dry_run(self, step, mock_db, temp_journal_definitions):
        """Test execution in dry-run mode."""
        paper = Mock(spec=Paper)
        paper.id = '1'
        paper.journal = 'Journal of Business Research'
        paper.screening = {}

        mock_db.all.return_value = [paper]

        result = step.execute(
            {'journal_definitions_path': temp_journal_definitions},
            dry_run=True
        )

        assert result.status == StepStatus.SUCCESS
        # update should not be called in dry-run mode
        mock_db.update_paper.assert_not_called()

    def test_execute_with_verbose(self, step, mock_db, temp_journal_definitions, capsys):
        """Test execution with verbose output."""
        paper = Mock(spec=Paper)
        paper.id = '1'
        paper.journal = 'Journal of Business Research'
        paper.screening = {}

        mock_db.all.return_value = [paper]

        result = step.execute(
            {'journal_definitions_path': temp_journal_definitions},
            verbose=True
        )

        assert result.status == StepStatus.SUCCESS

    def test_execute_invalid_definitions_path(self, step, mock_db):
        """Test execution with invalid definitions path."""
        result = step.execute({
            'journal_definitions_path': '/nonexistent/path.yml'
        })

        assert result.status == StepStatus.ERROR
        assert 'not found' in result.message.lower()

    def test_execute_updates_paper_metadata(self, step, mock_db, temp_journal_definitions):
        """Test that paper metadata is updated correctly."""
        paper = Mock(spec=Paper)
        paper.id = '1'
        paper.journal = 'Journal of Business Research'
        paper.screening = Mock()

        mock_db.all.return_value = [paper]

        result = step.execute({
            'journal_definitions_path': temp_journal_definitions
        })

        assert result.status == StepStatus.SUCCESS
        # Verify update_paper was called
        mock_db.update.assert_called()

        # Verify screening metadata was set
        calls = mock_db.update.call_args_list
        assert len(calls) > 0
        updated_paper = calls[0][0][0]
        assert updated_paper.screening.journal_screening is not None
        assert updated_paper.screening.journal_screening.journal_name == 'Journal of Business Research'


class TestJournalScreeningIntegration:
    """Integration tests for JournalScreeningStep."""

    def test_full_workflow(self, mock_db, tmp_path, temp_journal_definitions):
        """Test complete workflow from config validation through execution."""
        # Validate config
        config = {
            'journal_definitions_path': temp_journal_definitions,
            'generate_iso4': True,
            'skip_missing': False
        }

        is_valid, errors = JournalScreeningStep.validate(config)
        assert is_valid

        # Create step and execute
        general_config = {'project_name': 'test'}
        step = JournalScreeningStep(
            general_config=general_config,
            db=mock_db,
            cache_dir=tmp_path
        )

        paper = Mock(spec=Paper)
        paper.id = '1'
        paper.journal = 'Journal of Business Research'
        paper.screening = {}

        mock_db.all.return_value = [paper]

        result = step.execute(config)

        assert result.status == StepStatus.SUCCESS
        assert 'papers_matched' in result.stats
