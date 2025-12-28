# Code Standards

Code quality and consistency standards for paper-scanner.

## Style Guide

### Python Version
- **Minimum**: Python 3.11
- **Target**: Modern Python 3.11+ features
- Use type hints throughout

### Naming Conventions

#### Modules and Packages
```python
# Good: lowercase with underscores
my_module.py
my_package/

# Bad: CamelCase, spaces, or hyphens
MyModule.py
```

#### Classes
```python
# Good: CapitalizedWords (PascalCase)
class CitationsStep:
    pass

# Bad: lowercase, snake_case
class citations_step:
    pass
```

#### Functions and Methods
```python
# Good: lowercase with underscores
def fetch_citations(doi: str) -> List[Citation]:
    pass

# Bad: CamelCase
def FetchCitations(doi):
    pass
```

#### Constants
```python
# Good: UPPERCASE with underscores
MAX_RETRIES = 3
DEFAULT_TIMEOUT = 30

# Bad: lowercase, mixed case
max_retries = 3
MaxRetries = 3
```

#### Private Members
```python
# Good: prefix with single underscore
def _internal_method(self):
    pass

_cache = {}

# Good: prefix with double underscore for name mangling
def __very_private_method(self):
    pass
```

## Type Hints

Always include type hints:

```python
# Good
def process_papers(
    papers: List[Paper],
    verbose: bool = False
) -> Dict[str, int]:
    """Process papers and return statistics"""
    pass

# Bad
def process_papers(papers, verbose=False):
    """Process papers and return statistics"""
    pass
```

### Optional Types
```python
# Good
def get_paper(doi: str) -> Optional[Paper]:
    pass

# Bad
def get_paper(doi):
    pass
```

### Union Types
```python
from typing import Union

# Good
def parse_input(data: Union[str, Dict]) -> Paper:
    pass

# Good (Python 3.10+)
def parse_input(data: str | Dict) -> Paper:
    pass
```

## Docstrings

Use Google-style docstrings:

```python
def fetch_citations(
    doi: str,
    limit: Optional[int] = None
) -> Tuple[List[Citation], bool]:
    """
    Fetch citations from external source.
    
    Args:
        doi: Digital Object Identifier of paper
        limit: Maximum number of citations (None = all)
    
    Returns:
        Tuple of (citations_list, cache_hit)
    
    Raises:
        ValueError: If DOI is invalid
        TimeoutError: If request times out
    
    Example:
        >>> citations, cached = fetch_citations("10.1234/test")
        >>> print(len(citations))
    """
    pass
```

### Class Docstrings
```python
class CitationsStep(BaseStep):
    """Extract forward and backward citations for papers.
    
    This step fetches citation data from external sources (Crossref,
    OpenAlex, etc.) and resolves them to existing papers or creates
    new Paper records for unresolved citations.
    
    Attributes:
        db: Papers database instance
        cache_dir: Directory for caching API responses
    
    Example:
        >>> step = CitationsStep(db=db, cache_dir=".cache")
        >>> config = {"backward": {"citations": ["crossref"]}}
        >>> result = step.execute(config)
    """
    pass
```

## Imports

### Organization
```python
# Good: organized by type
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

import click
from rich.console import Console

from paper_scanner.core.models import Paper
from paper_scanner.core.database import PapersDatabase
from paper_scanner.tools.fetchers import Fetcher

# Bad: random order
from paper_scanner.core.database import PapersDatabase
import json
from paper_scanner.core.models import Paper
import logging
```

### Import Rules
1. Standard library
2. Third-party packages
3. Local imports

Alphabetical within each group.

### Avoid Star Imports
```python
# Good
from typing import List, Dict, Optional

# Bad
from typing import *
```

## Code Formatting

### Line Length
- **Maximum**: 100 characters
- **Docstrings**: up to 88 characters

### Indentation
- **4 spaces** (not tabs)
- Consistent throughout

### Spacing
```python
# Good: spacing around operators
result = value1 + value2
mapping = {"key": "value"}
list_items = [1, 2, 3]

# Bad: no spacing
result=value1+value2
mapping={"key":"value"}
list_items=[1,2,3]
```

### Blank Lines
```python
# Good: two blank lines between top-level definitions
class Paper:
    pass


class Citation:
    pass


def process_papers(papers):
    pass


# Good: one blank line between methods
class Paper:
    def __init__(self):
        pass
    
    def get_authors(self):
        pass
```

## Error Handling

### Exceptions
```python
# Good: catch specific exceptions
try:
    paper = db.get_by_doi(doi)
except ValueError as e:
    logger.error(f"Invalid DOI: {doi}")
    raise
except TimeoutError:
    logger.warning(f"Timeout fetching {doi}")
    return None

# Bad: catch all exceptions
try:
    paper = db.get_by_doi(doi)
except:
    pass
```

### Error Messages
```python
# Good: descriptive error messages
raise ValueError(f"Paper with DOI {doi} not found in database")

# Bad: vague error messages
raise ValueError("Not found")
```

## Logging

Use the logging module:

```python
import logging

logger = logging.getLogger(__name__)

def process_papers(papers):
    logger.info(f"Processing {len(papers)} papers")
    
    for paper in papers:
        logger.debug(f"Processing paper: {paper.doi}")
        
        if not paper.doi:
            logger.warning(f"Paper has no DOI: {paper.title}")
            continue
        
        logger.error(f"Failed to process {paper.doi}: {error}")
```

## Comments

### When to Comment
```python
# Good: explain WHY, not WHAT
# Use Crossref API instead of OpenAlex for better coverage
fetcher = Fetcher(methods=["crossref"])

# Bad: redundant comments
# Add 1 to x
x = x + 1
```

### Comment Style
```python
# Good: clear, concise
# TODO: Add support for forward citations

# Bad: unclear or too verbose
# need to do something here with the thing
```

## Testing Requirements

### Test Coverage
- **Minimum 80%** overall
- **Minimum 90%** for core modules
- **Minimum 70%** for UI/CLI

### Test File Naming
```bash
# Good: tests in tests/ directory
tests/unit/steps/test_citations.py

# Bad: tests mixed with code
src/paper_scanner/steps/test_citations.py
```

## Checking Code Quality

### Automatic Checking
```bash
# Linting
make lint
# or
uv run ruff check src/

# Formatting
make format
# or
uv run ruff format src/

# Type checking
make type-check
# or
uv run mypy src/

# All checks
make check
```

## Tools

### Linter: Ruff
Enforces style and catches errors.

### Formatter: Ruff
Automatically formats code.

### Type Checker: mypy
Validates type hints.

### Test Runner: Pytest
Runs test suite.

## Pre-commit

Git hooks automatically check code before commit:

```bash
# Install
pre-commit install

# Run manually
pre-commit run --all-files
```

## Common Issues and Fixes

### Type Errors
```python
# Error: "str" has no attribute "items"
for key, value in str_value.items():  # Wrong!
    pass

# Fix: check type first
if isinstance(str_value, dict):
    for key, value in str_value.items():
        pass
```

### Missing Imports
```python
# Error: NameError: name 'List' is not defined
def func(items: List[str]):  # Error!
    pass

# Fix: import it
from typing import List

def func(items: List[str]):
    pass
```

### Wide Exception Catch
```python
# Error: Too broad exception handling
try:
    result = risky_operation()
except Exception:
    pass

# Fix: catch specific exceptions
try:
    result = risky_operation()
except TimeoutError:
    logger.warning("Timeout")
except ValueError as e:
    logger.error(f"Invalid value: {e}")
```

## Next Steps

- [Development Setup](setup.md)
- [Testing Guide](testing.md)
- [Architecture Overview](../architecture/overview.md)
