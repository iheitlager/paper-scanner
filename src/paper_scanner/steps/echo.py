"""
Echo step - simply outputs the step description

Useful for debugging and documenting definition file execution
"""

from typing import Dict, Any, List
from rich.console import Console
from ..core.models import Paper

# Initialize rich console
console = Console()


def execute(
    config: Dict[str, Any],
    papers_db: List[Paper],
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
        "papers_count": len(papers_db)
    }

    console.print(f"[bold blue]Message:[/bold blue] [yellow]{message}[/yellow]")
    if verbose:
        console.print(f"  [cyan]Papers in database:[/cyan] {len(papers_db)}")

    return result
