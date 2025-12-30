"""
Unit tests for REPL functionality

Tests ReplController initialization, macro command registration, and REPL execution flow.
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch, Mock

import pytest

from paper_scanner.cli.tasks.repl import ReplController, ConsoleReporter
from paper_scanner.core.controller import macro_step, AbstractController
from paper_scanner.core.database import PapersDatabase
from paper_scanner.core.models import Paper
from paper_scanner.core.step_result import StepResult, StepStatus


class TestConsoleReporter:
    """Test ConsoleReporter - core reporter for REPL"""

    def test_reporter_initialization(self):
        """Test ConsoleReporter initialization"""
        reporter = ConsoleReporter()

        assert reporter.in_macro_task is False

    def test_reporter_has_logging_methods(self):
        """Test that ConsoleReporter has required logging methods"""
        reporter = ConsoleReporter()

        assert hasattr(reporter, 'log_msg')
        assert hasattr(reporter, 'log_info')
        assert hasattr(reporter, 'log_error')
        assert hasattr(reporter, 'log_debug')
        assert hasattr(reporter, 'log_warning')

    def test_reporter_on_start(self):
        """Test on_start callback sets initial state"""
        reporter = ConsoleReporter()
        reporter.log_msg = Mock()
        reporter.controller = Mock()
        reporter.controller.debug = False
        
        reporter.on_start()
        
        # on_start should log setup messages
        assert reporter.log_msg.called

    def test_reporter_on_close(self):
        """Test on_close callback"""
        reporter = ConsoleReporter()
        reporter.log_info = Mock()
        
        reporter.on_close()
        
        # Should be callable without error
        assert reporter.log_info.called


class TestMacroStepDecorator:
    """Test @macro_step decorator functionality"""

    def test_macro_step_decorator_adds_attribute(self):
        """Test that @macro_step adds _macro_names attribute"""
        
        @macro_step("test_command", "tc")
        def test_func():
            pass

        assert hasattr(test_func, '_macro_names')
        assert test_func._macro_names == ("test_command", "tc")

    def test_macro_step_single_name(self):
        """Test @macro_step with single name"""
        
        @macro_step("single")
        def func():
            pass

        assert func._macro_names == ("single",)

    def test_macro_step_multiple_names(self):
        """Test @macro_step with multiple names (command and aliases)"""
        
        @macro_step("command", "cmd", "c")
        def func():
            pass

        assert func._macro_names == ("command", "cmd", "c")


class TestConsoleReporterCallbacks:
    """Test ConsoleReporter callback methods"""

    def test_on_definition_loaded(self):
        """Test definition loaded callback"""
        reporter = ConsoleReporter()
        reporter.log_info = Mock()

        definition = {"steps": [{"step1": {}}, {"step2": {}}]}
        reporter.on_definition_loaded("test.yml", definition)

        reporter.log_info.assert_called()

    def test_on_macro_start(self):
        """Test macro command start callback"""
        reporter = ConsoleReporter()
        reporter.log_debug = Mock()

        reporter.on_macro_start("test_command")

        assert reporter.in_macro_task is True
        reporter.log_debug.assert_called()

    def test_on_macro_end_success(self):
        """Test macro command completion with success"""
        reporter = ConsoleReporter()
        reporter.log_msg = Mock()
        reporter.controller = Mock()
        reporter.controller.timings = False
        reporter.executor = Mock()
        reporter.executor.has_next_step = False

        result = StepResult(
            status=StepStatus.SUCCESS,
            message="Command completed successfully"
        )
        reporter.on_macro_end("echo", result, 100.5)

        assert reporter.in_macro_task is False

    def test_on_macro_error(self):
        """Test macro command error callback"""
        reporter = ConsoleReporter()
        reporter.log_error = Mock()

        error = Exception("Test error")
        reporter.on_macro_error("test_command", error, 50.0)

        reporter.log_error.assert_called()

    def test_on_error(self):
        """Test error callback"""
        reporter = ConsoleReporter()
        reporter.log_error = Mock()

        reporter.on_error("Test error message")

        reporter.log_error.assert_called()

    def test_on_step_start(self):
        """Test step start callback"""
        reporter = ConsoleReporter()
        reporter.log_msg = Mock()

        step_config = {"description": "Import papers", "step": "import bibtex", "command": "builtin.bibtex_import" }
        reporter.on_step_start(1, step_config, 5)

        reporter.log_msg.assert_called()

    def test_on_step_end(self):
        """Test step end callback"""
        reporter = ConsoleReporter()
        reporter.log_msg = Mock()

        step_config = {"step": "import bibtex", "command": "builtin.bibtex_import" }
        result = StepResult(status=StepStatus.SUCCESS, message="Imported 42 papers")
        reporter.on_step_end(1, step_config, result)

        # Should be callable without error
        assert reporter is not None


class TestConsoleReporterInitialization:
    """Test ConsoleReporter inheritance and interface compliance"""

    def test_console_reporter_implements_controller_reporter(self):
        """Test that ConsoleReporter implements AbstractControllerReporter"""
        from paper_scanner.core.reporter import AbstractControllerReporter
        
        reporter = ConsoleReporter()
        
        # Should have required methods
        assert hasattr(reporter, 'on_start')
        assert hasattr(reporter, 'on_close')
        assert hasattr(reporter, 'on_error')
        assert hasattr(reporter, 'on_macro_start')
        assert hasattr(reporter, 'on_macro_end')

    def test_console_reporter_implements_step_reporter(self):
        """Test that ConsoleReporter implements AbstractStepReporter"""
        from paper_scanner.core.reporter import AbstractStepReporter
        
        reporter = ConsoleReporter()
        
        # Should have required methods
        assert hasattr(reporter, 'on_step_start')
        assert hasattr(reporter, 'on_step_end')

    def test_console_reporter_logging_mixin(self):
        """Test ConsoleReporter has logging mixin methods"""
        from paper_scanner.core.reporter import ConsoleLoggingMixin
        
        reporter = ConsoleReporter()
        
        # Should have logging methods
        assert hasattr(reporter, 'log_msg')
        assert hasattr(reporter, 'log_info')
        assert hasattr(reporter, 'log_error')


class TestReplControllerStructure:
    """Test ReplController class structure and attributes"""

    def test_repl_controller_has_required_methods(self):
        """Test that ReplController has required interface methods"""
        # We can test class structure without instantiation
        assert hasattr(ReplController, '_do_initialize')
        assert hasattr(ReplController, '_prep_macro_steps')
        assert hasattr(ReplController, '_prep_repl_session')
        assert hasattr(ReplController, '_get_macro_step')
        assert hasattr(ReplController, '_get_status_line')
        assert hasattr(ReplController, '_do_exec')

    def test_repl_controller_has_macro_step_support(self):
        """Test that ReplController supports macro_step decorator"""
        # Check that macro step collection is supported
        method_names = [m for m in dir(ReplController) if not m.startswith('_')]
        
        # ReplController should have public methods for macro commands
        assert len(method_names) > 0


class TestStepResultUsage:
    """Test StepResult usage in REPL context"""

    def test_step_result_success(self):
        """Test successful step result"""
        result = StepResult(
            status=StepStatus.SUCCESS,
            message="Operation completed"
        )

        assert result.status == StepStatus.SUCCESS
        assert "Operation completed" in result.message

    def test_step_result_error(self):
        """Test error step result"""
        result = StepResult(
            status=StepStatus.ERROR,
            message="Operation failed"
        )

        assert result.status == StepStatus.ERROR
        assert "failed" in result.message

    def test_step_result_warning(self):
        """Test warning step result"""
        result = StepResult(
            status=StepStatus.WARNING,
            message="Warning message"
        )

        assert result.status == StepStatus.WARNING


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
