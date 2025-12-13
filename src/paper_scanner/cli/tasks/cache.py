"""
Cache task - Manage cache operations

This task handles cache operations like clearing checkpoints and other
cache management functions.
"""

import sys
import shutil
from pathlib import Path
from typing import Optional

from rich.console import Console

console = Console(file=sys.stderr)


def execute_cache_clear(
    target: str,
    cache_dir: Optional[Path] = None,
    verbose: bool = False,
) -> int:
    """
    Clear cache contents.

    Args:
        target: What to clear ('checkpoints', etc.)
        cache_dir: Cache directory (default: ~/.paper-scanner)
        verbose: Enable verbose output

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    import os

    # Determine cache_dir
    if cache_dir is None:
        cache_dir = Path(os.getenv("CACHE_DIR", ""))
        if not cache_dir or str(cache_dir) == ".":
            cache_dir = None

    if cache_dir is None:
        cache_dir = Path("~/.paper-scanner").expanduser()
    else:
        cache_dir = cache_dir.expanduser()

    if verbose:
        console.print(f"Cache directory: [cyan]{cache_dir}[/cyan]")
        console.print(f"Target: [yellow]{target}[/yellow]")

    if target == "checkpoints":
        checkpoints_dir = cache_dir / "checkpoints"

        if checkpoints_dir.exists():
            shutil.rmtree(checkpoints_dir)
            console.print(f"[green]✓ Cleared checkpoints[/green]: {checkpoints_dir}")
        else:
            console.print(f"[green]✓ No checkpoints to clear[/green] (directory is clean)")

        return 0

    return 1
