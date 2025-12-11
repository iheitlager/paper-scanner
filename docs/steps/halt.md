# Halt

### Title
**Halt** - Conditionally stops pipeline execution based on paper count or other criteria

### Description

The Halt step enables conditional pipeline termination. Use it to prevent downstream processing when data quality issues are detected, paper count thresholds aren't met, or other stopping conditions are true. This provides a safety mechanism to avoid processing incomplete or invalid datasets.

Halt is useful for validation workflows, preventing accidental exports, or stopping after errors during development and testing.

### Features

- ✅ **Conditional stopping**: Halt execution if conditions are met
- ✅ **Minimum paper threshold**: Stop if paper count below threshold
- ✅ **Custom message**: Display reason for halt on stop
- ✅ **Error reporting**: Can output exit code for scripting
- ✅ **Safe defaults**: Configurable halt criteria

### Configuration

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `min_papers` | `integer` | No | - | Minimum required papers to continue |
| `message` | `string` | No | - | Message to display before halting |

#### YAML Definition

```yaml
- step: Verify minimum papers
  builtin.halt:
    min_papers: 50
    message: "Not enough papers for analysis"
```

### Input/Output

#### Input
- **Format**: Papers from prior steps
- **Source**: Database
- **Requirements**: Database must be initialized

#### Output
- **Format**: Pipeline halts or continues
- **Exit**: Returns without error if conditions not met
- **Stop**: Terminates pipeline execution if conditions met
- **No database changes**: Read-only step

### Validation

The step validates:
- `min_papers`: If provided, must be positive integer
- `message`: If provided, must be string

### Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| "Halted: insufficient papers" | Paper count below min_papers | Check data imports, run earlier steps |
| "Invalid configuration" | min_papers or message malformed | Use valid values in configuration |

### Examples

#### Basic Example - Minimum Paper Check
```yaml
- step: Require minimum papers
  builtin.halt:
    min_papers: 100
```

#### Advanced Example - Safety Check Before Export
```yaml
- step: Verify data before export
  builtin.halt:
    min_papers: 50
    message: "Insufficient papers for export. Check import completed successfully."

- step: Export results
  builtin.export:
    format: "jsonl"
    output_file: "results.jsonl"
```

#### Development Example - Early Termination
```yaml
- step: Development checkpoint
  builtin.halt:
    min_papers: 10
    message: "DEBUG: Stopping after initial filtering for inspection"
```

### Related Steps

- **Upstream**: Any step
- **Downstream**: Usually followed by export or final step
- **Alternative**: None (halt provides unique control flow)

### Notes

- **Safety feature**: Use halt before critical operations like export
- **Development**: Place halt steps during development to test pipeline partially
- **Production**: Remove halt steps for full pipeline runs
- **Minimum papers**: Set based on your quality threshold
- **Default behavior**: If conditions not met, pipeline continues normally
