"""
CLI tasks for paper-processor

Exports task execution functions for the CLI.
"""

from paper_scanner.cli.tasks.run import execute_run
from paper_scanner.cli.tasks.validate import execute_validate, validate_definition_file
from paper_scanner.cli.tasks.cache import execute_cache_clear, execute_cache_info

__all__ = [
    "execute_run",
    "execute_validate",
    "validate_definition_file",
    "execute_cache_clear",
    "execute_cache_info",
]
