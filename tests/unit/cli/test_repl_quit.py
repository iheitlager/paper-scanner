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
        """Test that quit_after_definition flag is properly initialized"""
        session = REPLSession(
            project_id="test",
            cache_dir=tmp_path,
            quit_after_definition=True,
        )
        
        assert session.quit_after_definition is True

    def test_repl_session_quit_flag_default_false(self, tmp_path):
        """Test that quit_after_definition defaults to False"""
        session = REPLSession(
            project_id="test",
            cache_dir=tmp_path,
        )
        
        assert session.quit_after_definition is False

    def test_repl_run_exits_immediately_with_quit_flag(self, tmp_path):
        """Test that run() exits immediately when quit_after_definition=True and no definition"""
        session = REPLSession(
            project_id="test",
            cache_dir=tmp_path,
            quit_after_definition=True,
        )
        
        # Mock console.print to verify output
        with patch('paper_scanner.cli.tasks.repl.console.print') as mock_print:
            session.run()
            
            # Verify exit message was printed
            calls = [str(call) for call in mock_print.call_args_list]
            assert any("No definition loaded and --quit specified" in str(call) for call in calls)

    def test_repl_run_exits_after_definition_with_quit_flag(self, tmp_path):
        """Test that run() exits after definition execution when quit_after_definition=True"""
        session = REPLSession(
            project_id="test",
            cache_dir=tmp_path,
            quit_after_definition=True,
        )
        
        # Simulate loaded definition steps
        session.loaded_definition_steps = [{"step": 1}, {"step": 2}]
        
        # Mock console.print to verify output
        with patch('paper_scanner.cli.tasks.repl.console.print') as mock_print:
            session.run()
            
            # Verify exit message was printed
            calls = [str(call) for call in mock_print.call_args_list]
            assert any("Definition execution complete" in str(call) and "--quit mode" in str(call) for call in calls)

    def test_repl_run_continues_without_quit_flag(self, tmp_path):
        """Test that run() continues to interactive mode when quit_after_definition=False"""
        session = REPLSession(
            project_id="test",
            cache_dir=tmp_path,
            quit_after_definition=False,
        )
        
        # Mock both prompt_toolkit check and the interactive run methods
        with patch('paper_scanner.cli.tasks.repl.HAS_PROMPT_TOOLKIT', False):
            with patch.object(session, '_run_with_basic_input') as mock_basic:
                session.run()
                
                # Verify basic input was called (would start interactive mode)
                mock_basic.assert_called_once()

    def test_execute_repl_passes_quit_flag(self, tmp_path):
        """Test that execute_repl passes quit flag to REPLSession"""
        with patch.object(REPLSession, '__init__', return_value=None) as mock_init:
            with patch.object(REPLSession, 'run'):
                execute_repl(
                    project_id="test",
                    cache_dir=tmp_path,
                    quit_after_definition=True,
                    builtin_steps={},
                )
                
                # Verify quit_after_definition was passed to constructor
                mock_init.assert_called_once()
                call_kwargs = mock_init.call_args[1]
                assert call_kwargs['quit_after_definition'] is True

    def test_execute_repl_quit_flag_default_false(self, tmp_path):
        """Test that execute_repl passes quit_after_definition=False by default"""
        with patch.object(REPLSession, '__init__', return_value=None) as mock_init:
            with patch.object(REPLSession, 'run'):
                execute_repl(
                    project_id="test",
                    cache_dir=tmp_path,
                    builtin_steps={},
                )
                
                # Verify quit_after_definition was passed as False
                mock_init.assert_called_once()
                call_kwargs = mock_init.call_args[1]
                assert call_kwargs['quit_after_definition'] is False
