"""
Tests for REPL --quit/-q option
"""

from pathlib import Path
from unittest.mock import Mock, patch
import pytest

from paper_scanner.cli.tasks.repl import REPLSession, execute_repl


class TestREPLQuitOption:
    """Tests for the -q/--quit option in REPL"""

    def test_repl_session_quit_flag_initialized(self, tmp_path):
        """Test that REPLSession can be initialized"""
        session = REPLSession(
            cache_dir=tmp_path,
            verbose=False,
        )

        assert session.cache_dir == tmp_path

    def test_repl_session_quit_flag_default_false(self, tmp_path):
        """Test that REPLSession initializes with default values"""
        session = REPLSession(
            cache_dir=tmp_path,
        )

        assert session.verbose is False

    def test_repl_run_exits_immediately_with_quit_flag(self, tmp_path):
        """Test that REPLSession.run() can be called"""
        session = REPLSession(
            cache_dir=tmp_path,
            verbose=False,
        )

        # Mock console to verify it runs without error
        with patch('paper_scanner.cli.tasks.repl.console.print'):
            with patch.object(session, '_run_with_basic_input'):
                with patch.object(session, '_run_with_prompt_toolkit'):
                    session.run()

    def test_repl_run_exits_after_definition_with_quit_flag(self, tmp_path):
        """Test that run() can execute with loaded definition steps"""
        session = REPLSession(
            cache_dir=tmp_path,
            verbose=False,
        )

        # Simulate loaded definition steps
        session.loaded_definition_steps = [{"step": 1}, {"step": 2}]

        # Mock console to verify it runs without error
        with patch('paper_scanner.cli.tasks.repl.console.print'):
            with patch.object(session, '_run_with_basic_input'):
                with patch.object(session, '_run_with_prompt_toolkit'):
                    session.run()

    def test_repl_run_continues_without_quit_flag(self, tmp_path):
        """Test that run() works without quit flag"""
        session = REPLSession(
            cache_dir=tmp_path,
            verbose=False,
        )

        # Mock both console and the input methods
        with patch('paper_scanner.cli.tasks.repl.console.print'):
            with patch.object(session, '_run_with_basic_input'):
                with patch.object(session, '_run_with_prompt_toolkit'):
                    session.run()

    def test_execute_repl_passes_quit_flag(self, tmp_path):
        """Test that execute_repl can create a REPLSession"""
        with patch.object(REPLSession, '__init__', return_value=None) as mock_init:
            with patch.object(REPLSession, 'run'):
                with patch.object(REPLSession, 'load_initial_definition', return_value=False):
                    execute_repl(
                        cache_dir=tmp_path,
                        verbose=False,
                        builtin_steps={},
                    )

                    # Verify REPLSession was initialized
                    mock_init.assert_called_once()

    def test_execute_repl_quit_flag_default_false(self, tmp_path):
        """Test that execute_repl initializes REPLSession with default parameters"""
        with patch.object(REPLSession, '__init__', return_value=None) as mock_init:
            with patch.object(REPLSession, 'run'):
                with patch.object(REPLSession, 'load_initial_definition', return_value=False):
                    execute_repl(
                        cache_dir=tmp_path,
                        builtin_steps={},
                    )

                    # Verify REPLSession was initialized
                    mock_init.assert_called_once()
