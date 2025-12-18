"""
Unit tests for REPL functionality

Tests macro command parsing, state management, and integration with paper_scanner
"""

import pytest
import tempfile
import json
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

from paper_scanner.cli.tasks.repl import REPLSession
from paper_scanner.core.database import PapersDatabase
from paper_scanner.core.models import Paper
from paper_scanner.definition import Definition


class TestREPLSessionInit:
    """Test REPLSession initialization"""

    def test_init_default_values(self):
        """Test initialization with default values"""
        session = REPLSession()

        assert session.project_id == "interactive_session"
        assert session.verbose is False
        assert session.debug is False
        assert session.papers_db is None
        assert session.definition is None
        assert session.step_history == []

    def test_init_with_custom_values(self):
        """Test initialization with custom values"""
        cache_dir = Path("/tmp/cache")
        session = REPLSession(
            project_id="my_project",
            cache_dir=cache_dir,
            verbose=True,
            debug=True,
        )

        assert session.project_id == "my_project"
        assert session.cache_dir == cache_dir
        assert session.verbose is True
        assert session.debug is True


class TestMacroCommandParsing:
    """Test @command parsing logic"""

    def test_parse_simple_command(self):
        """Test parsing command without args"""
        session = REPLSession()
        command, args, kwargs = session._parse_macro_command("@help")

        assert command == "help"
        assert args == []
        assert kwargs == {}

    def test_parse_command_with_positional_args(self):
        """Test parsing command with positional arguments"""
        session = REPLSession()
        command, args, kwargs = session._parse_macro_command("@export jsonl /tmp/out.jsonl")

        assert command == "export"
        assert args == ["jsonl", "/tmp/out.jsonl"]
        assert kwargs == {}

    def test_parse_command_with_kwargs(self):
        """Test parsing command with keyword arguments"""
        session = REPLSession()
        command, args, kwargs = session._parse_macro_command(
            "@export jsonl /tmp/output.jsonl key1=value1 key2=value2"
        )

        assert command == "export"
        assert args == ["jsonl", "/tmp/output.jsonl"]
        assert kwargs == {"key1": "value1", "key2": "value2"}

    def test_parse_command_with_mixed_args(self):
        """Test parsing command with mixed positional and keyword args"""
        session = REPLSession()
        command, args, kwargs = session._parse_macro_command(
            "@export jsonl /tmp/out.jsonl limit=100 format=compact"
        )

        assert command == "export"
        assert args == ["jsonl", "/tmp/out.jsonl"]
        assert kwargs == {"limit": "100", "format": "compact"}


class TestMacroCommandHandling:
    """Test macro command execution"""

    def test_handle_status_command(self):
        """Test @status command"""
        session = REPLSession(project_id="test_project")
        session.papers_db = PapersDatabase()

        # Should return True (command handled)
        result = session._handle_macro_command("@status")
        assert result is True

    def test_handle_history_command_empty(self):
        """Test @history with no history"""
        session = REPLSession()
        result = session._handle_macro_command("@history")

        assert result is True
        assert session.step_history == []

    def test_handle_history_command_with_entries(self):
        """Test @history with entries"""
        session = REPLSession()
        session.step_history = ["Step 1 completed", "Step 2 completed"]

        result = session._handle_macro_command("@history")
        assert result is True

    def test_handle_show_command(self):
        """Test @show command"""
        session = REPLSession()
        session.papers_db = PapersDatabase()

        # Add test papers
        paper1 = Paper(
            id="1",
            cite_key="test_paper_1",
            title="Test Paper 1",
            doi="10.1234/test1",
        )
        paper2 = Paper(
            id="2",
            cite_key="test_paper_2",
            title="Test Paper 2",
            doi="10.1234/test2",
        )
        session.papers_db.add(paper1)
        session.papers_db.add(paper2)

        result = session._handle_macro_command("@show 5")
        assert result is True

    def test_handle_checkpoint_command(self):
        """Test @checkpoint command saves checkpoint"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            session = REPLSession(
                project_id="test_project",
                cache_dir=cache_dir,
            )
            session.papers_db = PapersDatabase()

            # Add test paper
            paper = Paper(
                id="1",
                cite_key="test_paper",
                title="Test Paper",
                doi="10.1234/test",
            )
            session.papers_db.add(paper)

            result = session._handle_macro_command("@checkpoint my_checkpoint")
            assert result is True

            # Verify checkpoint was created
            checkpoint_path = cache_dir / "test_project" / "checkpoint_my_checkpoint.json"
            assert checkpoint_path.exists()

    def test_handle_help_command(self):
        """Test @help command"""
        session = REPLSession()
        result = session._handle_macro_command("@help")

        assert result is True

    def test_handle_exit_command(self):
        """Test @exit command"""
        session = REPLSession()

        # @exit should return True (indicating command was handled)
        result = session._handle_macro_command("@exit")
        assert result is True

    def test_handle_unknown_command(self):
        """Test handling unknown @command"""
        session = REPLSession()
        result = session._handle_macro_command("@unknown_command")

        assert result is True

    def test_non_macro_line(self):
        """Test that non-@ lines return False"""
        session = REPLSession()
        result = session._handle_macro_command("print('hello')")

        assert result is False

    def test_handle_export_jsonl_command(self):
        """Test @export jsonl command"""
        with tempfile.TemporaryDirectory() as tmpdir:
            session = REPLSession()
            session.papers_db = PapersDatabase()

            # Add test papers
            paper = Paper(
                id="1",
                cite_key="test_paper",
                title="Test Paper",
                doi="10.1234/test",
            )
            session.papers_db.add(paper)

            output_path = Path(tmpdir) / "output.jsonl"
            result = session._handle_macro_command(f"@export jsonl {output_path}")

            assert result is True
            assert output_path.exists()

    def test_handle_export_json_command(self):
        """Test @export json command"""
        with tempfile.TemporaryDirectory() as tmpdir:
            session = REPLSession()
            session.papers_db = PapersDatabase()

            # Add test papers
            paper = Paper(
                id="1",
                cite_key="test_paper",
                title="Test Paper",
                doi="10.1234/test",
            )
            session.papers_db.add(paper)

            output_path = Path(tmpdir) / "output.json"
            result = session._handle_macro_command(f"@export json {output_path}")

            assert result is True
            assert output_path.exists()


class TestNamespaceCreation:
    """Test REPL namespace creation and helper functions"""

    def test_create_namespace_has_required_objects(self):
        """Test that namespace contains all required objects"""
        session = REPLSession()
        namespace = session._create_namespace()

        # Check for required objects
        assert "papers_db" in namespace
        assert "definition" in namespace
        assert "results" in namespace
        assert "general_config" in namespace

    def test_create_namespace_has_helper_functions(self):
        """Test that namespace contains helper functions"""
        session = REPLSession()
        namespace = session._create_namespace()

        # Check for helper functions
        assert "run_step" in namespace
        assert callable(namespace["run_step"])
        assert "show_papers" in namespace
        assert callable(namespace["show_papers"])
        assert "help_commands" in namespace
        assert callable(namespace["help_commands"])

    def test_create_namespace_has_imports(self):
        """Test that namespace contains convenience imports"""
        session = REPLSession()
        namespace = session._create_namespace()

        # Check for convenience imports
        assert "Definition" in namespace
        assert "PapersDatabase" in namespace
        assert "json" in namespace
        assert "Path" in namespace
        assert "datetime" in namespace

    def test_show_papers_function(self):
        """Test show_papers helper function"""
        session = REPLSession()
        session.papers_db = PapersDatabase()

        # Add test papers
        for i in range(3):
            paper = Paper(
                id=str(i),
                cite_key=f"test_paper_{i}",
                title=f"Paper {i}",
                doi=f"10.1234/test{i}",
            )
            session.papers_db.add(paper)

        namespace = session._create_namespace()
        show_papers = namespace["show_papers"]

        # Should not raise exception
        show_papers(limit=5)


class TestStateManagement:
    """Test session state management"""

    def test_step_history_tracking(self):
        """Test that step history is tracked correctly"""
        session = REPLSession()

        assert session.step_history == []

        session.step_history.append("Step 1")
        session.step_history.append("Step 2")

        assert len(session.step_history) == 2
        assert session.step_history[0] == "Step 1"

    def test_database_persistence(self):
        """Test that database persists across operations"""
        session = REPLSession()
        session.papers_db = PapersDatabase()

        paper = Paper(
            id="1",
            cite_key="test_paper",
            title="Test Paper",
            doi="10.1234/test",
        )
        session.papers_db.add(paper)

        assert session.papers_db.count() == 1

        # Add another paper
        paper2 = Paper(
            id="2",
            cite_key="test_paper_2",
            title="Another Paper",
            doi="10.1234/test2",
        )
        session.papers_db.add(paper2)

        assert session.papers_db.count() == 2

    def test_results_dictionary_update(self):
        """Test that results dictionary is updated correctly"""
        session = REPLSession()

        assert session.results == {}

        session.results = {"status": "success", "count": 42}

        assert session.results["status"] == "success"
        assert session.results["count"] == 42


class TestInitialDefinitionLoading:
    """Test loading initial YAML definitions"""

    def test_load_initial_definition_file_not_found(self):
        """Test handling missing definition file"""
        session = REPLSession()
        session._load_initial_definition(Path("/nonexistent/file.yml"))

        # Should not crash, just not load anything
        assert session.papers_db is None

    def test_load_initial_definition_with_checkpoint(self):
        """Test loading definition when checkpoint exists"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)

            # Create definition file
            definition_path = Path(tmpdir) / "definition.yml"
            definition_content = {
                "project_name": "Test Project",
                "steps": [],
            }
            with open(definition_path, "w") as f:
                import yaml
                yaml.dump(definition_content, f)

            # Create checkpoint
            checkpoint_dir = cache_dir / "test_session"
            checkpoint_dir.mkdir(parents=True)

            checkpoint_path = checkpoint_dir / "checkpoint_last.json"
            checkpoint_data = {
                "papers": [],
                "indexes": {"doi": {}, "cite_key": {}, "year": {}},
            }
            with open(checkpoint_path, "w") as f:
                json.dump(checkpoint_data, f)

            session = REPLSession(
                project_id="test_session",
                cache_dir=cache_dir,
            )
            session._load_initial_definition(definition_path)

            # Verify checkpoint was loaded
            assert session.papers_db is not None


class TestExecuteReplFunction:
    """Test execute_repl entry point function"""

    def test_execute_repl_basic(self):
        """Test basic execute_repl call"""
        from paper_scanner.cli.tasks.repl import execute_repl

        with patch.object(REPLSession, "run"):
            # Mock the run method to prevent interactive REPL
            exit_code = execute_repl(
                project_id="test",
                builtin_steps={},
            )

            assert exit_code == 0

    def test_execute_repl_with_exception(self):
        """Test execute_repl error handling"""
        from paper_scanner.cli.tasks.repl import execute_repl

        with patch.object(REPLSession, "__init__", side_effect=Exception("Test error")):
            exit_code = execute_repl()

            assert exit_code == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
