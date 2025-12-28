# Architecture Overview

paper-scanner is built on a modern, modular architecture designed for extensibility and testability.

## Core Data Flow

```
PDF Input 
    ↓
Claude Analysis (LLM)
    ↓
Structured JSON
    ↓
PostgreSQL Database
    ↓
Web Interface
```

## System Components

### 1. Core (`src/paper_scanner/core/`)

The foundational layer handling data models and database operations.

**Key Components:**
- **Models** - Paper, Citation, Author, Keyword data structures
- **Database** - PapersDatabase for CRUD operations and queries
- **DOI Handler** - Normalize and resolve DOIs
- **LLM Interface** - Claude API integration

**Responsibilities:**
- Define canonical data structures
- Provide database abstraction
- Handle external API calls

### 2. Pipeline (`src/paper_scanner/steps/`)

The execution engine for data processing workflows.

**Architecture:**
- **BaseStep** - Abstract base class for all steps
- **StepExecutor** - Orchestrates step execution
- **Step Registry** - Maps step names to implementations

**Key Principles:**
- Each step is independent and composable
- Support YAML configuration
- Validate before executing
- Return standardized results

**Available Steps:**
- BibtexImport - Import from BibTeX files
- Citations - Extract citation networks
- Deduplication - Find and remove duplicates
- Export - Export to various formats
- Patch - Update paper metadata
- And more...

### 3. Definitions (`src/paper_scanner/definition/`)

Pythonic fluent API for building pipelines programmatically.

**Features:**
- Method chaining for natural syntax
- Python-native alternative to YAML
- Type-safe configuration

**Example:**
```python
pipeline = (Definition("Review")
    .bibtex_import("refs.bib")
    .citations(backward={"citations": ["crossref"]})
    .export("bibtex", output="out.bib")
)
```

### 4. CLI (`src/paper_scanner/cli/`)

Command-line interface for running pipelines.

**Key Commands:**
- `paper-processor definition.yml` - Run workflow
- `paper-processor validate definition.yml` - Validate
- `paper-processor info` - Show database info
- `paper-processor --init` - Initialize database

### 5. Web (`src/paper_scanner/web/`)

Flask-based web interface for paper management.

**Features:**
- PDF viewer and annotator
- Paper search and filtering
- Citation graph visualization
- Tag management

## Configuration Architecture

paper-scanner uses a **three-level configuration model**:

### Level 1: General Configuration
Project-wide settings passed to all steps:
```yaml
general:
  db_path: papers.db
  cache_dir: ./cache
  max_workers: 4
```

### Level 2: Step Configuration
Step-specific settings in workflow definition:
```yaml
steps:
  - name: citations
    backward:
      citations: [crossref]
      continue_on_not_found: true
```

### Level 3: Runtime Flags
Execution-time options via command line:
```bash
paper-processor definition.yml --verbose --dry-run --debug
```

See [ADR-0001](../adr/0001-pipeline-architecture.md) for rationale.

## Data Models

### Paper
Represents a single academic publication:
- **Metadata**: title, authors, year, journal
- **Identifiers**: DOI, URLs, cite_key
- **Content**: abstract, keywords, full_text
- **Relationships**: citations (references), cited_by (citing papers)
- **Status**: paper_type, screening_results, tags

### Citation
Represents a reference or cited_by relationship:
- **Source**: doi, title, authors
- **Direction**: backward (reference) or forward (cited_by)
- **Resolution**: doi of resolved paper, or full Paper object
- **Metadata**: extraction_method, confidence, raw_text

### Author
Represents a paper author:
- name, first_name, last_name
- email (optional)
- affiliation (optional)

## Processing Pipeline

Typical paper-scanner workflow:

```
1. Import Phase
   ├─ Read input (BibTeX, CSV, PDF, etc.)
   └─ Create Paper records in database
   
2. Enrichment Phase
   ├─ Extract citations (backward/forward)
   ├─ Fetch metadata from external sources
   └─ Update paper records
   
3. Analysis Phase
   ├─ Run ML analysis (screening, summarization, etc.)
   └─ Update paper analysis results
   
4. Export Phase
   └─ Export to desired format (BibTeX, CSV, JSON, etc.)
```

## Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **LLM** | Claude API (Anthropic) | PDF analysis and extraction |
| **Database** | PostgreSQL / SQLite | Paper and citation storage |
| **Web** | Flask | Web interface |
| **CLI** | Click | Command-line interface |
| **Configuration** | YAML / Python | Workflow definition |
| **Testing** | Pytest | Unit and integration tests |
| **Code Quality** | Ruff, mypy | Linting and type checking |

## Design Principles

### 1. Modularity
Each component has a single responsibility and clear interfaces.

### 2. Extensibility
New steps can be added by extending BaseStep without modifying core.

### 3. Testability
Steps are independent and mockable; database is abstracted.

### 4. Reproducibility
Workflows defined as YAML enable versioning and sharing.

### 5. Transparency
Logging at each step shows what's happening and why.

## Key Workflows

### Import and Process Papers
```yaml
steps:
  - name: bibtex_import
    file: references.bib
  - name: retrieve_metadata
    methods: [crossref, openalex]
  - name: summarize
    summary: true
  - name: export
    format: bibtex
    output: processed.bib
```

### Build Citation Networks
```yaml
steps:
  - name: citations
    backward:
      citations: [crossref]
    forward:
      citations: [openalex]
```

### Screen and Analyze
```yaml
steps:
  - name: semantic_screening
    model: sentence-transformers/all-MiniLM-L6-v2
    thresholds:
      include: 0.7
      exclude: 0.3
  - name: run_template
    template: extract_findings
```

## Database Schema

Key tables:
- `papers` - Paper metadata
- `authors` - Author information
- `keywords` - Paper keywords
- `citations` - Citation relationships
- `screening_results` - ML-based paper screening

See [Models Documentation](models.md) for detailed schema.

## Next Steps

- [Pipeline Architecture Deep Dive](pipeline.md)
- [Data Models](models.md)
- [Step Development Guide](../steps/overview.md)
- [Architecture Decisions](../adr/index.md)
