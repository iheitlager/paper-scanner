"""
Halt step for paper scanner

Stops the pipeline execution at this step without error
"""

from typing import Dict, Any, List
from rich.console import Console

from ..core.models import Paper
from ..core.database import PapersDatabase
from ..core.database import PapersDatabase

# Initialize rich console
console = Console()


class HaltException(Exception):
    """Exception raised to halt pipeline execution"""
    pass


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
    config: Dict[str, Any],
    papers_db: PapersDatabase,
    verbose: bool = False,
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Execute halt step - stops the pipeline
    
    Args:
        config: Step configuration (optional 'message' key)
        papers_db: Current papers database (not modified)
        verbose: Enable verbose output
        dry_run: Doesn't affect halt step
    
    Returns:
        Dictionary with halt status (raises HaltException before return)
    """
    
    message = config.get("message", "Pipeline halted")
    
    result = {
        "status": "halted",
        "message": message,
        "papers_count": papers_db.count(primary_only=False)
    }
    
    if verbose:
        console.print(f"\n  [bold yellow]⏸ Halt:[/bold yellow] {message}")
        console.print(f"  [cyan]Papers in database:[/cyan] {papers_db.count(primary_only=False)}")
    
    # Raise exception to halt pipeline
    raise HaltException(message)
