# Pipeline Architecture

The pipeline architecture in paper-scanner enables flexible, composable data processing workflows.

## Core Concepts

### Workflows
A workflow is a sequence of steps defined in YAML or Python that process papers through the pipeline.

### Steps
Individual processing units that:
- Have a single responsibility
- Accept configuration
- Return standardized results
- Can be chained together

### Execution Model
Steps are executed sequentially with:
- Validation before execution
- Checkpointing support
- Error handling and reporting
- Dry-run capability

## Step Lifecycle

```
1. Validate
   └─ Check configuration is correct

2. Initialize
   └─ Create step instance with config

3. Execute
   └─ Process papers through database

4. Result
   └─ Return stats and errors

5. Report
   └─ Display results to user
```

## Configuration Model

See the [three-level configuration guide](../adr/0001-pipeline-architecture.md) for detailed explanation.

### YAML Example
```yaml
general:
  db_path: papers.db
  cache_dir: ./cache

steps:
  - name: bibtex_import
    file: references.bib
    batch_size: 10
    
  - name: citations
    backward:
      citations: [crossref]
      details: [openalex]
    continue_on_not_found: true
    
  - name: export
    format: bibtex
    output: processed.bib
```

### Python API Example
```python
from paper_scanner.definition import Definition

pipeline = (Definition("My Review")
    .bibtex_import("references.bib", batch_size=10)
    .citations(
        backward={"citations": ["crossref"], "details": ["openalex"]},
        continue_on_not_found=True
    )
    .export(format="bibtex", output="processed.bib")
)

result = pipeline.run()
```

## Step Registry

The step registry maps step names to implementations:

```python
BUILTIN_STEPS = {
    "bibtex_import": BibtexImportStep,
    "citations": CitationsStep,
    "deduplication": DeduplicationStep,
    "export": ExportStep,
    "patch": PatchStep,
    "retrieve_metadata": RetrieveMetadataStep,
    "run_template": RunTemplateStep,
    "semantic_screening": SemanticScreeningStep,
    "summarize": SummarizeStep,
    "upload_database": UploadDatabaseStep,
}
```

## Checkpointing

Resume execution from a specific step:

```bash
# Run normally
uv run paper-processor definition.yml

# Resume from step 3
uv run paper-processor definition.yml --checkpoint step_name

# See available checkpoints
uv run paper-processor definition.yml --list-checkpoints
```

## Dry Run Mode

Validate without modifying database:

```bash
# Preview changes
uv run paper-processor definition.yml --dry-run
```

## Step Development

To create a new step:

1. **Extend BaseStep**
```python
from paper_scanner.steps.base import BaseStep

class MyStep(BaseStep):
    @staticmethod
    def validate(config):
        # Validate configuration
        return is_valid, errors
    
    def execute(self, config, verbose=False, dry_run=False, debug=False):
        # Process papers
        return StepResult(...)
```

2. **Implement validation**
```python
@staticmethod
def validate(config: Dict[str, Any]) -> Tuple[bool, List[str]]:
    errors = []
    # Check required fields
    if 'field' not in config:
        errors.append("'field' is required")
    return len(errors) == 0, errors
```

3. **Implement execution**
```python
def execute(self, config, verbose=False, dry_run=False, debug=False):
    papers = self.db.all()
    
    # Process papers
    for paper in papers:
        # Do something with paper
        pass
    
    # Return results
    return StepResult(
        status=StepStatus.SUCCESS,
        message="Processing complete",
        stats={
            "processed": len(papers),
            "updated": 5,
        }
    )
```

4. **Register in executor**
```python
BUILTIN_STEPS["my_step"] = MyStep
```

5. **Document the step**
See [Step Documentation Template](../steps/overview.md)

## Execution Flow

```
User runs: paper-processor definition.yml
        ↓
Load workflow from YAML
        ↓
For each step:
    ├─ Validate config
    ├─ Instantiate step
    ├─ Execute (unless dry-run)
    ├─ Collect results
    └─ Report to user
        ↓
Display summary statistics
```

## Error Handling

Steps should:
- Catch and log errors
- Return error information in results
- Provide recovery suggestions
- Use appropriate status codes

```python
def execute(self, config, **kwargs):
    errors = []
    
    try:
        # Process papers
    except Exception as e:
        errors.append(f"Processing failed: {str(e)}")
    
    return StepResult(
        status=StepStatus.ERROR if errors else StepStatus.SUCCESS,
        stats={"errors": errors}
    )
```

## Best Practices

### 1. Single Responsibility
Each step should do one thing well.

### 2. Idempotency
Running a step twice should produce the same results.

### 3. Logging
Provide detailed logs for debugging.

### 4. Validation
Validate configuration early and completely.

### 5. Testing
Write unit tests for all steps.

### 6. Documentation
Document configuration options clearly.

## Performance Considerations

### Batch Processing
For large datasets, process in batches:
```python
batch_size = config.get('batch_size', 100)
for i in range(0, len(papers), batch_size):
    batch = papers[i:i+batch_size]
    # Process batch
```

### Caching
Cache external API results:
```python
fetcher = Fetcher(cache_dir=self.cache_dir)
paper_data, cache_hit = fetcher.fetch_paper(doi)
```

### Parallelization
Use multiprocessing for CPU-bound tasks (where appropriate).

## See Also

- [Step Reference](../steps/overview.md)
- [Architecture Overview](overview.md)
- [Pipeline ADR](../adr/0001-pipeline-architecture.md)
