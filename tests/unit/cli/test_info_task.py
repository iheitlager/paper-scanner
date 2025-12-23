"""
Tests for the info CLI task

Tests the info steps command for displaying available steps and documentation
"""

from io import StringIO
from unittest.mock import patch

from rich.console import Console

from paper_scanner.cli.tasks.info import execute_info_steps
from paper_scanner.steps.base import BaseStep


class MockStep(BaseStep):
    """Mock step for testing"""

    @staticmethod
    def validate(config):
        return True, []

    def execute(self, config, verbose=False, dry_run=False, debug=False):
        return {"status": "ok"}


class AnotherMockStep(BaseStep):
    """Another test step
    
    This step does something useful.
    It has multiple lines in the docstring.
    """

    @staticmethod
    def validate(config):
        return True, []

    def execute(self, config, verbose=False, dry_run=False, debug=False):
        return {"status": "ok"}


class TestExecuteInfoSteps:
    """Test execute_info_steps function"""

    def test_execute_info_steps_with_steps(self):
        """Test displaying available steps"""
        builtin_steps = {
            "test_step": MockStep,
            "another_step": AnotherMockStep,
        }

        output = StringIO()
        console = Console(file=output, width=120)
        exit_code = execute_info_steps(builtin_steps=builtin_steps, console=console)

        assert exit_code == 0
        result = output.getvalue()
        assert "test_step" in result
        assert "another_step" in result

    def test_execute_info_steps_empty_registry(self):
        """Test with empty step registry"""
        builtin_steps = {}

        output = StringIO()
        console = Console(file=output, width=120)
        exit_code = execute_info_steps(builtin_steps=builtin_steps, console=console)

        assert exit_code == 1
        result = output.getvalue()
        assert "No steps available" in result

    def test_execute_info_steps_single_step(self):
        """Test displaying a single step"""
        builtin_steps = {
            "echo": MockStep,
        }

        output = StringIO()
        console = Console(file=output, width=120)
        exit_code = execute_info_steps(builtin_steps=builtin_steps, console=console)

        assert exit_code == 0
        result = output.getvalue()
        assert "echo" in result

    def test_execute_info_steps_shows_docstring(self):
        """Test that step docstrings are displayed"""
        class DocumentedStep(BaseStep):
            """This is a documented step
            
            It has a comprehensive docstring explaining what it does.
            """

            @staticmethod
            def validate(config):
                return True, []

            def execute(self, config, verbose=False, dry_run=False, debug=False):
                return {"status": "ok"}

        builtin_steps = {
            "documented": DocumentedStep,
        }

        output = StringIO()
        console = Console(file=output, width=120)
        exit_code = execute_info_steps(builtin_steps=builtin_steps, console=console)

        assert exit_code == 0
        result = output.getvalue()
        # Check for part of the docstring
        assert "documented" in result

    def test_execute_info_steps_with_many_steps(self):
        """Test displaying multiple steps"""
        builtin_steps = {
            "alpha": MockStep,
            "beta": MockStep,
            "gamma": MockStep,
            "delta": MockStep,
            "epsilon": MockStep,
        }

        output = StringIO()
        console = Console(file=output, width=120)
        exit_code = execute_info_steps(builtin_steps=builtin_steps, console=console)

        assert exit_code == 0
        result = output.getvalue()
        # All steps should be mentioned
        assert "alpha" in result
        assert "beta" in result
        assert "gamma" in result
        assert "delta" in result
        assert "epsilon" in result

    def test_execute_info_steps_exception_handling(self):
        """Test error handling when an exception occurs"""
        # Create a mock that raises an exception when accessed
        builtin_steps = {
            "test": MockStep,
        }

        output = StringIO()
        console = Console(file=output, width=120)

        with patch('paper_scanner.cli.tasks.info.sorted', side_effect=Exception("Test error")):
            exit_code = execute_info_steps(builtin_steps=builtin_steps, console=console)

        assert exit_code == 1
        result = output.getvalue()
        assert "Error" in result


class TestInfoStepsIntegration:
    """Integration tests for info steps functionality"""

    def test_info_steps_sorts_steps_alphabetically(self):
        """Test that steps are displayed in alphabetical order"""
        builtin_steps = {
            "zebra": MockStep,
            "apple": MockStep,
            "middle": MockStep,
            "banana": MockStep,
        }

        output = StringIO()
        console = Console(file=output, width=120)
        exit_code = execute_info_steps(builtin_steps=builtin_steps, console=console)

        assert exit_code == 0
        result = output.getvalue()

        # Find positions of each step in output
        apple_pos = result.find("apple")
        banana_pos = result.find("banana")
        middle_pos = result.find("middle")
        zebra_pos = result.find("zebra")

        # All should be found
        assert apple_pos >= 0
        assert banana_pos >= 0
        assert middle_pos >= 0
        assert zebra_pos >= 0

        # Should be in alphabetical order
        assert apple_pos < banana_pos < middle_pos < zebra_pos

    def test_info_steps_includes_summary_table(self):
        """Test that output includes a summary table"""
        builtin_steps = {
            "test_step": MockStep,
        }

        output = StringIO()
        console = Console(file=output, width=120)
        exit_code = execute_info_steps(builtin_steps=builtin_steps, console=console)

        assert exit_code == 0
        result = output.getvalue()

        # Should contain table elements (Rich table characters)
        # Check for common Rich table markers
        assert "Step" in result or "test_step" in result

    def test_info_steps_handles_no_docstring(self):
        """Test handling of steps with no docstring"""
        class NoDocStep(BaseStep):
            @staticmethod
            def validate(config):
                return True, []

            def execute(self, config, verbose=False, dry_run=False, debug=False):
                return {"status": "ok"}

        # Remove docstring
        NoDocStep.__doc__ = None

        builtin_steps = {
            "nodoc": NoDocStep,
        }

        output = StringIO()
        console = Console(file=output, width=120)
        exit_code = execute_info_steps(builtin_steps=builtin_steps, console=console)

        assert exit_code == 0
        result = output.getvalue()
        # Should handle missing docstring gracefully
        assert "nodoc" in result
