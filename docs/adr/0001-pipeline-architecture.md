# ADR-0001: Pipeline Architecture with Three-Level Configuration

**Status**: Accepted

**Date**: 2025-01-01

## Context

paper-scanner needed a flexible way to define data processing pipelines that could:
1. Support complex multi-step workflows
2. Allow both declarative (YAML) and programmatic (Python) definitions
3. Support checkpointing and resumable execution
4. Provide clear separation of concerns between workflow, step, and runtime configuration
5. Enable easy testing and validation of steps

Previously, there was no standardized way to define pipelines, making it difficult to:
- Reuse pipeline definitions
- Version control workflows
- Share configurations across teams
- Understand pipeline structure at a glance

## Decision

We adopted a **three-level configuration model** for pipelines:

### Level 1: General Configuration
Project-level settings passed to all steps:
```yaml
general:
  db_path: papers.db
  cache_dir: ./cache
  max_workers: 4
```

### Level 2: Step Configuration
Step-specific settings defined in workflow YAML:
```yaml
steps:
  - name: citations
    backward:
      citations: [crossref]
      continue_on_not_found: true
```

### Level 3: Runtime Flags
Execution-time options passed during execution:
```bash
paper-processor definition.yml --verbose --dry-run --debug
```

## Implementation

- **YAML-based**: Primary approach for production workflows
- **Fluent Python API**: Alternative for programmatic definition
- **BaseStep**: Base class that all steps inherit from
- **StepExecutor**: Orchestrates step execution with proper state management
- **Checkpointing**: Resume from specific steps using step names

## Consequences

### Positive
- ✅ Clear separation of concerns (what, where, and how)
- ✅ Easy to version control and share workflow definitions
- ✅ Supports both declarative and programmatic approaches
- ✅ Enables easy testing of individual steps
- ✅ Flexible checkpointing and resumable execution
- ✅ Consistent error handling across all steps
- ✅ Natural progression from simple to complex pipelines

### Negative
- ⚠️ Three-level model can be confusing for new users initially
- ⚠️ Requires careful documentation of which level each setting belongs to
- ⚠️ YAML indentation errors can be hard to debug

## Alternatives Considered

### Single Configuration Level
**Rejected**: Would force all settings into one place, mixing concerns and making workflows less flexible

### Database-Stored Workflows
**Rejected**: Adds complexity and reduces version control benefits; YAML is better for git workflows

### No Checkpointing
**Rejected**: Large workflows would be too slow to re-run from the beginning on failures

## Related Links

- [Pipeline Architecture Documentation](../architecture/pipeline.md)
- [Step Documentation](../steps/overview.md)
- [Three-Level Configuration Guide](../architecture/three-level-config.md)
