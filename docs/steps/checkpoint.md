# Checkpoint

### Title
**Checkpoint** - Saves intermediate pipeline state for resume capability and incremental processing

### Description

The Checkpoint step creates a snapshot of the current processing state, allowing the pipeline to resume from that point in future runs without reprocessing earlier steps. This is especially valuable for long-running pipelines or when you want to pause and continue work iteratively.

Checkpoints preserve all paper metadata, screening decisions, and processing history, enabling reproducible workflows and efficient incremental updates.

### Features

- ✅ **Snapshot creation**: Captures complete pipeline state at checkpoint point
- ✅ **Resume capability**: Restart from checkpoint without rerunning earlier steps
- ✅ **State validation**: Verifies checkpoint integrity before saving
- ✅ **Metadata preservation**: Saves all paper data and screening decisions
- ✅ **Efficient storage**: Uses database format for fast save/restore
- ✅ **Multiple checkpoints**: Can create multiple checkpoints at different pipeline stages

### Configuration

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `name` | `string` | Yes | - | Unique checkpoint identifier |

#### YAML Definition

```yaml
- step: Save progress checkpoint
  builtin.checkpoint:
    name: "after_categorization"
```

### Input/Output

#### Input
- **Format**: All papers and screening data in database
- **Source**: Database from all prior steps
- **Requirements**: Database must be initialized and contain papers

#### Output
- **Format**: Checkpoint state saved to database
- **Storage**: Database with checkpoint metadata
- **Metadata**: Checkpoint name, timestamp, paper count

### Validation

The step validates:
- `name`: Must be a non-empty string
- Database is accessible and initialized
- Papers exist in database

### Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| "Database error" | Cannot connect to database | Check database configuration |
| "No papers" | Database is empty | Run prior steps to populate papers |
| "Invalid checkpoint name" | Checkpoint name is empty | Provide non-empty name |

### Examples

#### Basic Example
```yaml
- step: Checkpoint after deduplication
  builtin.checkpoint:
    name: "deduplicated"
```

#### Multi-Checkpoint Pipeline
```yaml
- step: Import papers
  builtin.bibtex_import:
    batch_id: "batch1"
    imports:
      - name: "Scopus"
        file_path: "data/scopus.bib"
        source_type: "scopus"

- step: Checkpoint initial import
  builtin.checkpoint:
    name: "imported"

- step: Remove duplicates
  builtin.deduplication:
    method: "all"

- step: Checkpoint after deduplication
  builtin.checkpoint:
    name: "deduplicated"

- step: Categorize papers
  builtin.categorization:
    exclude_reviews: true

- step: Checkpoint after categorization
  builtin.checkpoint:
    name: "categorized"
```

### Related Steps

- **Upstream**: Any step (can be placed anywhere in pipeline)
- **Downstream**: Any subsequent step, or pipeline termination for save
- **Alternative**: None (checkpoint is unique for state management)

### Notes

- **Checkpoint names should be descriptive** to identify pipeline stage clearly
- **Timestamps are automatic** so you can track when checkpoints were created
- **Multiple checkpoints** are recommended at major pipeline milestones
- **Resume workflows**: Create YAML with only steps after checkpoint
- **Incremental updates**: Use checkpoints to avoid reprocessing unchanged data
- **Best practice**: Place checkpoints after expensive operations (deduplication, semantic_screening)
