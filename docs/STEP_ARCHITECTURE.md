# Step Architecture

## Overview

This document describes the class-based architecture for pipeline steps in the paper-scanner project. The new architecture replaces dynamic discovery with explicit class inheritance, improving maintainability, performance, and type safety.

## Design Principles

1. **Separation of Concerns**: Clear distinction between general configuration (project-level), step-specific configuration, and runtime parameters
2. **Lazy Initialization**: Dependencies (database, cache) are injected during instantiation, not discovery
3. **Explicit Validation**: Configuration validation is performed at parse-time via static methods
4. **Type Safety**: Full type hints throughout for better IDE support and error detection
5. **Performance**: Hardcoded step registry eliminates filesystem scanning (~0.1s overhead removed)

## Architecture

### BaseStep Class

All pipeline steps inherit from `BaseStep`, an abstract base class that defines the standard interface.

```python
from abc import ABC, abstractmethod
from typing import Any, Dict, Tuple, List
from pydantic import BaseModel

class BaseStep(ABC):
    """
    Abstract base class for all pipeline steps.
    
    Steps follow a three-level configuration model:
    1. general_config: Project-level configuration (passed to all steps)
    2. step_config: Step-specific configuration (parsed from YAML workflow)
    3. Runtime flags: verbose, dry_run, debug (passed during execution)
    """
    
    def __init__(
        self,
        general_config: Dict[str, Any],
        db: 'PapersDatabase',
        cache_dir: str
    ):
        """
        Initialize step with project-level dependencies.
        
        Args:
            general_config: Project-level configuration dictionary containing
                          settings that may be needed by multiple steps
            db: PapersDatabase instance for reading/writing papers
            cache_dir: Directory for caching fetched data and intermediate results
        """
        self.general_config = general_config
        self.db = db
        self.cache_dir = cache_dir
    
    @staticmethod
    @abstractmethod
    def validate(step_config: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate step-specific configuration.
        
        This static method is called at workflow parse time to validate the
        step configuration before instantiation. It allows early detection of
        configuration errors.
        
        Args:
            step_config: Step-specific configuration from workflow YAML
            
        Returns:
            Tuple of (is_valid, errors) where:
            - is_valid: True if configuration is valid, False otherwise
            - errors: List of validation error messages (empty if valid)
            
        Example:
            >>> is_valid, errors = RetrieveMetadataStep.validate(config)
            >>> if not is_valid:
            ...     print(f"Config errors: {errors}")
        """
        pass
    
    @abstractmethod
    def execute(
        self,
        step_config: Dict[str, Any],
        verbose: bool = False,
        dry_run: bool = False,
        debug: bool = False
    ) -> Dict[str, Any]:
        """
        Execute the step with given configuration.
        
        This instance method performs the actual work. It has access to:
        - self.general_config: Project configuration
        - self.db: Database instance
        - self.cache_dir: Cache directory path
        
        Args:
            step_config: Step-specific configuration from workflow YAML
            verbose: Enable verbose output
            dry_run: If True, don't persist changes (read-only execution)
            debug: Enable debug logging
            
        Returns:
            Dictionary with execution results:
            - "status": "success" or "error"
            - "count": Number of items processed
            - "details": Step-specific result details
            - "error": Error message (if status is "error")
            
        Example:
            >>> results = step.execute(config, verbose=True)
            >>> print(f"Processed {results['count']} papers")
        """
        pass
```

### Configuration Model

Pipeline steps use a three-level configuration model:

#### Level 1: General Configuration
Project-level settings passed to ALL steps during initialization. Examples:
- `api_keys`: API credentials for external services
- `timeout`: Request timeout values
- `retry_count`: Number of retry attempts
- `output_format`: Default output format

#### Level 2: Step Configuration
Step-specific parameters defined in the workflow YAML. Examples:
- For `retrieve_metadata`: `sources: ['crossref']`, `cache: true`
- For `categorization`: `model: 'keywords'`, `num_categories: 5`
- For `export`: `format: 'bibtex'`, `include_abstracts: true`

#### Level 3: Runtime Flags
Execution modifiers passed during step execution:
- `verbose`: Detailed logging output
- `dry_run`: Read-only execution without persisting changes
- `debug`: Enable debug-level diagnostics

### Usage Pattern

The typical usage pattern for steps is:

```python
# 1. Parse and validate configuration (at workflow parse time)
is_valid, errors = RetrieveMetadataStep.validate(step_config)
if not is_valid:
    raise ConfigurationError(f"Invalid config: {errors}")

# 2. Instantiate step with project dependencies
step = RetrieveMetadataStep(
    general_config=project_config,
    db=papers_db,
    cache_dir="/path/to/cache"
)

# 3. Execute step with step-specific config and runtime flags
results = step.execute(
    step_config=step_config,
    verbose=True,
    dry_run=False,
    debug=False
)

# 4. Check results
if results["status"] == "success":
    print(f"Processed {results['count']} papers")
else:
    print(f"Error: {results['error']}")
```

## Implementation Example: RetrieveMetadataStep

Here's a complete example of implementing a step using the BaseStep architecture:

```python
from typing import Any, Dict, Tuple, List
from .base import BaseStep

class RetrieveMetadataStep(BaseStep):
    """
    Retrieve and enrich paper metadata from external sources.
    
    This step fetches metadata for papers from APIs like Crossref and caches
    the results. It updates the database with enriched metadata.
    
    Configuration:
        sources: List of metadata sources (default: ['crossref'])
        cache: Whether to cache results (default: true)
        force_refresh: Force refresh even if cached (default: false)
    """
    
    @staticmethod
    def validate(step_config: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate retrieve_metadata step configuration."""
        errors = []
        
        # sources must be present and non-empty
        sources = step_config.get('sources', ['crossref'])
        if not isinstance(sources, list) or not sources:
            errors.append("'sources' must be a non-empty list")
        
        # validate known sources
        known_sources = {'crossref', 'semantic_scholar', 'arxiv'}
        invalid_sources = set(sources) - known_sources
        if invalid_sources:
            errors.append(f"Unknown sources: {invalid_sources}")
        
        # cache and force_refresh must be boolean
        if 'cache' in step_config and not isinstance(step_config['cache'], bool):
            errors.append("'cache' must be boolean")
        
        if 'force_refresh' in step_config and not isinstance(step_config['force_refresh'], bool):
            errors.append("'force_refresh' must be boolean")
        
        return (len(errors) == 0, errors)
    
    def execute(
        self,
        step_config: Dict[str, Any],
        verbose: bool = False,
        dry_run: bool = False,
        debug: bool = False
    ) -> Dict[str, Any]:
        """Execute metadata retrieval."""
        
        # Extract configuration with defaults
        sources = step_config.get('sources', ['crossref'])
        use_cache = step_config.get('cache', True)
        force_refresh = step_config.get('force_refresh', False)
        
        try:
            # Get all papers from database
            papers = self.db.get_all()
            processed_count = 0
            
            for paper in papers:
                if verbose:
                    print(f"Retrieving metadata for: {paper.title}")
                
                # Attempt to fetch from each source
                for source in sources:
                    fetcher = self._get_fetcher(source, use_cache)
                    
                    # Fetch metadata
                    metadata = fetcher.fetch(paper, force_refresh=force_refresh)
                    
                    if metadata:
                        if not dry_run:
                            # Merge metadata into paper
                            enriched = {**paper.dict(), **metadata}
                            self.db.update(paper.id, enriched)
                        
                        processed_count += 1
                        break  # Use first available source
            
            return {
                "status": "success",
                "count": processed_count,
                "sources": sources,
                "details": f"Retrieved metadata from {len(sources)} source(s)"
            }
        
        except Exception as e:
            return {
                "status": "error",
                "count": 0,
                "error": str(e)
            }
    
    def _get_fetcher(self, source: str, use_cache: bool):
        """Get fetcher instance for specified source."""
        from paper_scanner.tools.fetcher_handlers import CrossrefMetadataFetcher
        
        if source == 'crossref':
            return CrossrefMetadataFetcher(
                cache_dir=self.cache_dir if use_cache else None
            )
        else:
            raise ValueError(f"Unknown source: {source}")
```

## Step Registry

The step registry is maintained in `paper_processor.py` as a hardcoded dictionary:

```python
# Known steps in the pipeline
STEP_REGISTRY = {
    'bibtex_import': BibtexImportStep,
    'categorization': CategorizationStep,
    'checkpoint': CheckpointStep,
    'deduplication': DeduplicationStep,
    'dump_db': DumpDbStep,
    'echo': EchoStep,
    'export': ExportStep,
    'halt': HaltStep,
    'input': InputStep,
    'keyword_screening': KeywordScreeningStep,
    'load_files': LoadFilesStep,
    'patch': PatchStep,
    'retrieve_metadata': RetrieveMetadataStep,
    'semantic_screening': SemanticScreeningStep,
    'summarize': SummarizeStep,
}

def _discover_steps() -> Dict[str, Type[BaseStep]]:
    """Return the hardcoded step registry."""
    return STEP_REGISTRY
```

## Migration Plan

### Phase 1: Create Infrastructure
- Create `src/paper_scanner/steps/base.py` with BaseStep class
- Update `src/paper_scanner/cli/paper_processor.py` to use hardcoded registry
- Create this documentation

### Phase 2: Migrate Core Steps
Migrate steps in dependency order (steps with no/few dependencies first):
1. **echo** - No dependencies, simplest case
2. **input** - Minimal I/O dependencies
3. **checkpoint** - Simple database operations
4. **halt** - Simple control flow
5. **retrieve_metadata** - External API calls (already fixed for serialization)
6. **dump_db** - Database read operations
7. **export** - File output operations
8. **bibtex_import** - File input + parsing
9. **load_files** - File I/O + parsing

### Phase 3: Migrate Advanced Steps
Advanced steps with LLM/ML dependencies:
10. **categorization** - LLM-based classification
11. **keyword_screening** - ML-based filtering
12. **semantic_screening** - Semantic search
13. **summarize** - LLM-based summarization
14. **deduplication** - Cross-paper analysis
15. **patch** - Complex transformation logic

### Testing Strategy
For each migrated step:
1. Keep existing tests, update to use new class interface
2. Test both `validate()` static method and `execute()` instance method
3. Verify configuration validation catches bad inputs
4. Test dry-run mode doesn't persist changes
5. Test verbose and debug flags work correctly

## Benefits of New Architecture

### Immediate Benefits
- **Performance**: ~0.1s overhead removed (no filesystem scanning)
- **Type Safety**: IDE autocomplete for all step methods
- **Explicitness**: Clear list of available steps (no "magic" discovery)
- **Testability**: Each step can be tested in isolation with mocked dependencies

### Long-term Benefits
- **Maintainability**: Clear interface makes code changes safer
- **Extensibility**: Adding new steps is simple (create class, add to registry)
- **Documentation**: Each step documents its configuration schema
- **Debugging**: Stack traces are clearer (no dynamic imports)
- **Refactoring**: Can safely rename/reorganize without breaking discovery

## Configuration Validation Example

Here's how configuration validation works end-to-end:

```python
# In workflow YAML
steps:
  - name: retrieve_metadata
    config:
      sources: ['crossref']
      cache: true

# In paper_processor.py, during workflow parsing
def parse_workflow(workflow_dict):
    for step_def in workflow_dict['steps']:
        step_name = step_def['name']
        step_config = step_def.get('config', {})
        
        # Get step class from registry
        step_class = STEP_REGISTRY.get(step_name)
        if not step_class:
            raise ValueError(f"Unknown step: {step_name}")
        
        # Validate configuration at parse time
        is_valid, errors = step_class.validate(step_config)
        if not is_valid:
            raise ValueError(f"Invalid config for {step_name}: {errors}")
    
    return workflow_dict

# Invalid configuration example
# This would raise during parsing:
steps:
  - name: retrieve_metadata
    config:
      sources: []  # Error: empty list
      cache: "yes"  # Error: should be boolean
```

## File Organization

```
src/paper_scanner/steps/
├── __init__.py              # Exports all step classes
├── base.py                  # BaseStep abstract class
├── bibtex_import.py         # BibtexImportStep
├── categorization.py        # CategorizationStep
├── checkpoint.py            # CheckpointStep
├── deduplication.py         # DeduplicationStep
├── dump_db.py               # DumpDbStep
├── echo.py                  # EchoStep
├── export.py                # ExportStep
├── halt.py                  # HaltStep
├── input.py                 # InputStep
├── keyword_screening.py     # KeywordScreeningStep
├── load_files.py            # LoadFilesStep
├── patch.py                 # PatchStep
├── retrieve_metadata.py     # RetrieveMetadataStep (migrated first)
├── semantic_screening.py    # SemanticScreeningStep
└── summarize.py             # SummarizeStep
```

## Backwards Compatibility

During migration, old function-based and new class-based steps can coexist:

```python
# In paper_processor.py
def get_step_executor(step_name, config):
    # Try new class-based registry first
    if step_name in STEP_REGISTRY:
        step_class = STEP_REGISTRY[step_name]
        return ClassBasedStepExecutor(step_class, config)
    
    # Fall back to old dynamic discovery
    module = _discover_steps()[step_name]
    return FunctionBasedStepExecutor(module, config)
```

This allows gradual migration without breaking existing workflows.

## Error Handling

Steps should handle errors gracefully and return consistent error responses:

```python
def execute(...) -> Dict[str, Any]:
    try:
        # Perform work
        return {
            "status": "success",
            "count": processed_count,
            "details": {...}
        }
    except ConfigurationError as e:
        return {
            "status": "error",
            "count": 0,
            "error": f"Configuration error: {str(e)}"
        }
    except Exception as e:
        if debug:
            raise  # Re-raise for debugging
        return {
            "status": "error",
            "count": 0,
            "error": str(e)
        }
```

The caller can then check `results["status"]` to determine if execution succeeded.

## Dependencies

Each step declares its dependencies through:

1. **Constructor parameters**: Required at instantiation time (general_config, db, cache_dir)
2. **validate() requirements**: Declared in configuration schema validation
3. **execute() imports**: Imported on-demand during execution

This allows steps to:
- Load dependencies lazily (only when step is executed)
- Gracefully handle missing optional dependencies
- Report missing required dependencies during parsing phase
