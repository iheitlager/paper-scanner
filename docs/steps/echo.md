# Echo

### Title
**Echo** - Outputs a message to the console for documentation and debugging

### Description

The Echo step provides a simple way to insert informational messages into your pipeline. Use it to document pipeline milestones, add section headers to output, display intermediate summaries, or provide hints to users running the pipeline interactively.

Echo messages are displayed with the current paper count, helping track progress and provide context at key pipeline points.

### Features

- ✅ **Flexible messaging**: Display any text message during pipeline execution
- ✅ **Progress context**: Shows current paper count with message
- ✅ **Documentation**: Insert explanatory text for readability
- ✅ **Debugging**: Quick way to verify pipeline is running
- ✅ **Optional messages**: Message parameter is optional (no-op if omitted)

### Configuration

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `message` | `string` | No | - | Message to display (optional) |

#### YAML Definition

```yaml
- step: Display status message
  builtin.echo:
    message: "Starting keyword screening phase"
```

### Input/Output

#### Input
- **Format**: Papers from prior steps (if any)
- **Source**: Database
- **Requirements**: None (can be first step)

#### Output
- **Format**: Console message with paper count
- **Display**: Human-readable output to terminal
- **Effects**: No database changes (read-only step)

### Validation

The step validates:
- `message`: If provided, must be a string

### Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| "Invalid message" | Message is not a string | Use quoted text for messages |

### Examples

#### Basic Example - Section Header
```yaml
- step: Mark deduplication complete
  builtin.echo:
    message: "Deduplication complete. Starting categorization..."
```

#### Advanced Example - Pipeline Checkpoints
```yaml
- step: Import complete
  builtin.echo:
    message: "✓ Papers imported successfully"

- step: Deduplication complete
  builtin.echo:
    message: "✓ Duplicates removed"

- step: Categorization complete
  builtin.echo:
    message: "✓ Papers categorized"

- step: Ready for manual screening
  builtin.echo:
    message: "→ Ready for manual screening. Open database for review."
```

#### Debugging Example
```yaml
- step: Verify configuration
  builtin.echo:
    message: "DEBUG: Starting with 1000 papers from initial import"
```

### Related Steps

- **Upstream**: Any step
- **Downstream**: Any step
- **Alternative**: None (echo is unique for user messaging)

### Notes

- **No-op if no message**: Omit message parameter for silent step
- **Read-only operation**: Echo does not modify papers or database
- **Use for readability**: Insert messages at major pipeline milestones
- **Combine with checkpoint**: Echo after checkpoints to document pipeline flow
- **Terminal output**: Messages appear on same output stream as other step output
