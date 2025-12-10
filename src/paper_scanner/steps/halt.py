"""
Halt step for paper scanner

Stops the pipeline execution at this step without error
"""

from typing import Dict, Any, List
from rich.console import Console

from ..core.models import Paper

# Initialize rich console
console = Console()


class HaltException(Exception):
    """Exception raised to halt pipeline execution"""
    pass


def execute(
    config: Dict[str, Any],
    papers_db: List[Paper],
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
        "papers_count": len(papers_db)
    }
    
    if verbose:
        console.print(f"\n  [bold yellow]⏸ Halt:[/bold yellow] {message}")
        console.print(f"  [cyan]Papers in database:[/cyan] {len(papers_db)}")
    
    # Raise exception to halt pipeline
    raise HaltException(message)
