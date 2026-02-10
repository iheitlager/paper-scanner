# Paper-Scanner Project Context

**Name:** paper-scanner
**Version:** 3.8.0
**Status:** Pre-alpha
**License:** Apache 2.0
**Repository:** https://github.com/iheitlager/paper-scanner

## Tech Stack

- **Language:** Python 3.11+
- **Package Manager:** uv
- **Web Framework:** Flask
- **Database:** PostgreSQL + pgvector
- **LLM Providers:** Anthropic Claude, Ollama
- **Embeddings:** SentenceTransformers (all-mpnet-base-v2, 768d)
- **Testing:** pytest
- **Linting:** ruff, mypy

## Architecture

The system follows a pipeline architecture with YAML-driven step execution:

```
Import → Enrichment → Screening → Analysis → Output
```

### Key Components

| Component | Location | Purpose |
|-----------|----------|---------|
| Data Models | `src/paper_scanner/core/models.py` | Pydantic models (Paper, Author, Citation, Screening, etc.) |
| Database | `src/paper_scanner/core/database.py` | In-memory indexed PapersDatabase |
| Pipeline Engine | `src/paper_scanner/core/executor.py` | YAML-based StepExecutor with checkpoints |
| Steps (29) | `src/paper_scanner/steps/` | Pipeline step implementations |
| Fetchers | `src/paper_scanner/tools/fetchers/` | Multi-source metadata fetching |
| Embeddings | `src/paper_scanner/tools/embedding/` | Text chunking and embedding generation |
| IO | `src/paper_scanner/io/` | BibTeX, RIS, JSON, SQL import/export |
| CLI | `src/paper_scanner/cli/` | paper-processor command |
| Web | `src/paper_scanner/web/` | Flask web interface |
| LLM Models | `src/paper_scanner/models/` | Anthropic + Ollama providers |

### Data Flow

```
BibTeX/RIS/PDF → Import Steps → PapersDatabase → Enrichment Steps →
Screening Steps → Analysis Steps → Export (JSONL/BibTeX/CSV/PostgreSQL)
```

## Conventions

- All inter-step communication via in-memory PapersDatabase
- Pipeline configuration via YAML definition files
- Checkpoint system for resumable workflows
- Multi-stage screening with progressive filtering
- Embedding-based semantic analysis with pgvector
