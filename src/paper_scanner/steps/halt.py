"""
Halt step for paper scanner

Stops the pipeline execution at this step without error
"""

import sys
from typing import Any, Dict, List, Tuple

from rich.console import Console

from paper_scanner.core.enum import StepStatus
from paper_scanner.core.exceptions import PaperScannerError

from .base import BaseStep

# Initialize rich console
console = Console(file=sys.stderr)


class HaltException(PaperScannerError):
    """Exception raised to halt pipeline execution"""
    pass


class HaltStep(BaseStep):
    """Halt step that stops the pipeline."""

    @staticmethod
    def validate(config: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate halt step configuration.
        
        Args:
            config: Step configuration
            
        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []

        # Message is optional
        if "message" in config and not isinstance(config["message"], str):
            errors.append("'message' must be a string")

        return len(errors) == 0, errors

    def execute(
        self,
        config: Dict[str, Any],
        verbose: bool = False,
        dry_run: bool = False,
        debug: bool = False
    ) -> Dict[str, Any]:
        """
        Execute halt step - stops the pipeline
        
        Args:
            config: Step configuration (optional 'message' key)
            verbose: Enable verbose output
            dry_run: Doesn't affect halt step
            debug: Enable debug output
        
        Returns:
            Dictionary with halt status (raises HaltException before return)
        """

        message = config.get("message", "Pipeline halted")

        result = {
            "status": StepStatus.HALTED,
            "message": message,
            "papers_count": self.db.count(primary_only=False)
        }

        # Raise exception to halt pipeline
        raise HaltException(message)
