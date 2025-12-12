"""
Echo step - simply outputs the step description

Useful for debugging and documenting definition file execution
"""

import sys
from typing import Dict, Any, List, Tuple
from rich.console import Console
from ..core.models import Paper
from ..core.database import PapersDatabase

# Initialize rich console
console = Console(file=sys.stderr)


def validate(config: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Validate echo step configuration.
    
    Args:
        config: Step configuration
        
    Returns:
        Tuple of (is_valid, error_messages)
    """
    errors = []
    
    # Message is optional, no validation needed
    # Just check that if provided, it's a string
    if "message" in config and not isinstance(config["message"], str):
        errors.append("'message' must be a string")
    
    return len(errors) == 0, errors


def execute(
    config: Dict[str, Any],
    papers_db: PapersDatabase,
    verbose: bool = False,
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Execute echo step - output the message
    
    Args:
        config: Step configuration (optional 'message' key)
        papers_db: Current papers database (not modified)
        verbose: Enable verbose output
        dry_run: Doesn't affect echo step
    
    Returns:
        Execution result
    """
    
    message = config.get("message", "")
    
    result = {
        "status": "ok",
        "output": message,
        "papers_count": papers_db.count(primary_only=False)
    }

    console.print(f"[bold blue]Message:[/bold blue] [yellow]{message}[/yellow]")
    if verbose:
        console.print(f"  [cyan]Papers in database:[/cyan] {papers_db.count(primary_only=False)}")

    return result
