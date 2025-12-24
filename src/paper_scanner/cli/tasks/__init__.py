"""
CLI tasks for paper-processor

Exports task execution functions for the CLI.
"""

from paper_scanner.cli.tasks.cache import execute_cache_clear, execute_cache_info, execute_cache_load, execute_cache_load_manual, execute_cache_clear_manual
from paper_scanner.cli.tasks.db import execute_db_clear, execute_db_stats
from paper_scanner.cli.tasks.info import execute_info_steps
from paper_scanner.cli.tasks.repl import execute_repl
from paper_scanner.cli.tasks.run import execute_run
from paper_scanner.cli.tasks.validate import execute_validate, validate_definition_file

__all__ = [
    "execute_run",
    "execute_validate",
    "validate_definition_file",
    "execute_cache_clear",
    "execute_cache_info",
    "execute_cache_load",
    "execute_cache_load_manual",
    "execute_cache_clear_manual",
    "execute_db_stats",
    "execute_db_clear",
    "execute_info_steps",
    "execute_repl",
]
