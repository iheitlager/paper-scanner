# ADR-0002: Class-Based Step Architecture with Explicit Configuration Levels

**Status**: Accepted

**Date**: 2025-12-20

## Context

The paper-scanner pipeline originally used dynamic discovery to find and load step implementations. This approach had several drawbacks:

- **Performance**: Filesystem scanning (~0.1s overhead per run)
- **Type Safety**: No IDE autocomplete or static type checking for steps
- **Implicit Behavior**: Steps were "discovered" dynamically, making the codebase harder to understand
- **Testing Difficulty**: Hard to test steps in isolation without running discovery
- **Maintenance Risk**: Renaming or reorganizing files could silently break workflows
- **Configuration Confusion**: Three levels of configuration (general, step-specific, runtime) were unclear

We needed an architecture that is:
1. **Explicit and discoverable**: Clear list of available steps
2. **Type-safe**: Full IDE support and static analysis
3. **Fast**: No filesystem scanning overhead
4. **Testable**: Steps can be tested independently
5. **Clear**: Configuration model is explicit and well-documented

## Decision

Migrate to a **class-based architecture with explicit step registration** and a **three-level configuration model**:

### Architecture Components

#### 1. BaseStep Abstract Class
All pipeline steps inherit from `BaseStep`:
```python
class BaseStep(ABC):
    def __init__(self, general_config, db, cache_dir):
        """Initialize with project-level dependencies"""
    
    @staticmethod
    @abstractmethod
    def validate(step_config) -> Tuple[bool, List[str]]:
        """Validate step configuration (called at parse-time)"""
    
    @abstractmethod
    def execute(step_config, verbose, dry_run, debug) -> Dict:
        """Execute the step (called at runtime)"""
```

#### 2. Three-Level Configuration Model

**Level 1: General Configuration** (project-level)
- Passed to ALL steps during initialization
- Examples: API keys, timeouts, retry counts, output formats
- Set once per project, reused by multiple steps

**Level 2: Step Configuration** (step-specific)
- Parameters defined in workflow YAML for individual steps
- Examples: `sources: ['crossref']`, `keywords: ['AI', 'ML']`
- Validated via static `validate()` method at parse-time

**Level 3: Runtime Flags** (execution modifiers)
- Passed during step execution: `verbose`, `dry_run`, `debug`
- Same for all steps, modify execution behavior

#### 3. Explicit Step Registry
Hardcoded registry in CLI (no filesystem scanning):
```python
STEP_REGISTRY_PATHS = {
    "bibtex_import": "paper_scanner.steps.bibtex_import:BibtexImportStep",
    "report": "paper_scanner.steps.report:ReportStep",
    # ... all steps listed explicitly
}
```

### Usage Pattern

```python
# 1. Parse and validate (at parse time - once)
is_valid, errors = StepClass.validate(step_config)
if not is_valid:
    raise ConfigurationError(errors)

# 2. Instantiate (at workflow start)
step = StepClass(general_config, db, cache_dir)

# 3. Execute (at step execution time)
results = step.execute(step_config, verbose=True, dry_run=False)

# 4. Check results
if results["status"] == "success":
    print(f"Processed {results['count']} items")
```

## Consequences

### Positive
- ✅ **10x faster startup**: No filesystem scanning (~0.1s removed per run)
- ✅ **Full type safety**: IDE autocomplete, mypy type checking works
- ✅ **Explicit codebase**: Clear list of available steps (no "magic")
- ✅ **Better testability**: Each step tested independently with mocked dependencies
- ✅ **Safe refactoring**: Clear dependencies, static analysis catches issues
- ✅ **Clear configuration**: Three-level model removes ambiguity
- ✅ **Better error messages**: Configuration validation at parse-time, not runtime
- ✅ **Easier onboarding**: New developers see structure immediately

### Negative
- ⚠️ **Manual registry maintenance**: Must update `STEP_REGISTRY_PATHS` when adding steps (minor overhead)
- ⚠️ **No dynamic step loading**: Can't add steps via plugins at runtime (acceptable trade-off)
- ⚠️ **Migration effort**: Must convert existing function-based steps to classes (done gradually)
- ⚠️ **Backward compatibility**: Old YAML configs must be updated to use new step names

### Risks Mitigated
- **Unused step problem**: Registry makes it obvious if steps aren't being used
- **Configuration drift**: Clear validation prevents silent misconfigurations
- **Version skew**: Explicit imports catch missing dependencies early

## Alternatives Considered

### 1. Keep Dynamic Discovery, Add Type Hints
- ❌ Rejected: Still has performance cost and type checking gaps
- Would require scanning and introspection, defeating purpose

### 2. Plugin System (Dynamic Loading)
- ❌ Rejected: Added complexity, performance cost, harder to debug
- Works well for extension ecosystems, not needed for paper-scanner

### 3. Dataclass-Based Configuration
- ❌ Rejected as primary: Less flexible for steps with varied configs
- ✅ Adopted as secondary: Used for type-safe step initialization

### 4. Hybrid Approach (Discovery + Registry)
- ❌ Rejected: Adds complexity without clear benefit
- Chose pure explicit registry for simplicity

## Implementation

### Phase 1: Infrastructure (Complete)
- [x] Create `src/paper_scanner/steps/base.py` with `BaseStep`
- [x] Update CLI to use explicit `STEP_REGISTRY_PATHS`
- [x] Define three-level configuration model in docs

### Phase 2: Core Steps (Complete)
- [x] Migrate: echo, input, checkpoint, halt
- [x] Migrate: retrieve_metadata, report, export
- [x] Migrate: bibtex_import, ris_import, load_files
- [x] Migrate: download_pdfs, fix_cite_keys, patch

### Phase 3: Advanced Steps (In Progress)
- [ ] Migrate: deduplication, keyword_screening
- [ ] Migrate: semantic_screening, journal_screening
- [ ] Migrate: llm_classification, rocchio_classifier
- [ ] Migrate: citations, generate_embeddings
- [ ] Migrate: metadata_screening, rocchio_screening
- [ ] Migrate: upload_database, run-template

### Validation Strategy
For each migrated step:
1. Keep existing tests, update to new class interface
2. Test `validate()` static method catches bad configs
3. Test `execute()` works with valid configs
4. Test dry-run mode doesn't persist changes
5. Test verbose/debug flags work

### File Organization
```
src/paper_scanner/steps/
├── base.py                       # BaseStep (shared)
├── bibtex_import.py             # BibtexImportStep
├── checkpoint.py                # CheckpointStep
├── citations.py                 # CitationsStep
├── deduplication.py             # DeduplicationStep
├── download_pdfs.py             # DownloadPDFsStep
├── echo.py                      # EchoStep
├── export.py                    # ExportStep
├── fix_cite_keys.py             # FixCiteKeysStep
├── generate_embeddings.py       # GenerateEmbeddingsStep
├── halt.py                      # HaltStep
├── input.py                     # InputStep
├── journal_screening.py         # JournalScreeningStep
├── keyword_screening.py         # KeywordScreeningStep
├── llm_classification.py        # LLMClassificationStep
├── load_files.py                # LoadFilesStep
├── metadata_screening.py        # MetadataScreeningStep
├── paper.py                     # PaperStep
├── patch.py                     # PatchStep
├── report.py                    # ReportStep
├── retrieve_metadata.py         # RetrieveMetadataStep
├── ris_import.py                # RisImportStep
├── rocchio_classifier.py        # RocchioClassifierStep
├── rocchio_screening.py         # RocchioScreeningStep
├── run_template.py              # RunTemplateStep
├── semantic_screening.py        # SemanticScreeningStep
└── upload_database.py           # UploadDatabaseStep
```

## Backward Compatibility

Graceful transition path:
```python
# In step executor
def get_step_executor(step_name, config):
    # Try new class-based registry first
    if step_name in STEP_REGISTRY:
        step_class = STEP_REGISTRY[step_name]
        return ClassBasedStepExecutor(step_class, config)
    
    # Fall back to legacy (deprecated)
    return LegacyStepExecutor(step_name, config)
```

Steps migrated gradually without breaking existing workflows. Old function-based implementations remain available during migration window.

## Example: RetrieveMetadataStep

```python
class RetrieveMetadataStep(BaseStep):
    """Retrieve and enrich paper metadata from external sources."""
    
    @staticmethod
    def validate(config):
        errors = []
        sources = config.get('sources', ['crossref'])
        
        if not isinstance(sources, list):
            errors.append("'sources' must be a list")
        
        known_sources = {'crossref', 'openalex', 'core'}
        invalid = set(sources) - known_sources
        if invalid:
            errors.append(f"Unknown sources: {invalid}")
        
        return (len(errors) == 0, errors)
    
    def execute(self, config, verbose=False, dry_run=False, debug=False):
        sources = config.get('sources', ['crossref'])
        papers = self.db.get_all()
        
        for paper in papers:
            for source in sources:
                fetcher = self._get_fetcher(source)
                metadata = fetcher.fetch(paper)
                
                if metadata and not dry_run:
                    self.db.update(paper.id, metadata)
        
        return {
            "status": "success",
            "count": len(papers),
            "sources": sources
        }
```

## Migration Checklist

For each step being migrated:
- [ ] Create class inheriting from `BaseStep`
- [ ] Implement static `validate()` method
- [ ] Implement instance `execute()` method
- [ ] Add to `STEP_REGISTRY_PATHS`
- [ ] Create/update unit tests
- [ ] Create documentation in `docs/steps/`
- [ ] Test with example YAML definitions
- [ ] Update CHANGELOG

## Relevant Links

- [ADR-0001: Pipeline Architecture](./0001-pipeline-architecture.md)
- [Step Base Class Documentation](../steps/base_step.md)
- [All Steps Reference](../steps/overview.md)
- [PR: Initial class-based architecture](https://github.com/user/paper-scanner/pull/XXX)

## Questions & Future Decisions

1. **Dynamic step discovery**: Should we support loading steps from plugins later? (Deferred)
2. **Configuration versioning**: How to handle config schema evolution? (To be decided)
3. **Step composition**: Should steps be composable/chainable? (Deferred)
4. **Async execution**: Should long-running steps support async? (To be evaluated)
