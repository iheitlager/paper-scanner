# Spike 004: Vector Embeddings

## Objective

Explore and implement vector embedding capabilities for the paper-scanner project to enable semantic search and similarity matching across research papers.

## Goals

- [ ] Research embedding model options (Claude, sentence-transformers, etc.)
- [ ] Explore embedding storage strategies (PostgreSQL pgvector, vector DBs)
- [ ] Design embedding generation pipeline
- [ ] Implement semantic search functionality
- [ ] Test performance and accuracy

## Extensions

- Have a frontend SLM model capturing questions and forwarding to the right menu option or action
- Be able to upload the document to claude and have it process further
- Found some deeper approaches to compare and analyse starting from the database
- Go to the web and make sure the PDF viewer is there including a cluster browser
- Work on the references too
- Have links to other databases
- Be able to click on sections

## Scripts

### `load_papers.py`
Loads papers from JSONL file into PostgreSQL database using only existing fields from the original `papers` table schema.

**Usage:**
```bash
python load_papers.py <path_to_jsonl> [--db-url postgresql://...]
python load_papers.py out2.jsonl
```

**Features:**
- Extracts relevant fields from nested JSONL structure
- Handles file_path, file_name, directory, timestamps, and metadata
- Maps file-details (title, citekey, year) to papers table
- Supports insert or update on conflict
- Detailed logging and statistics

**Example:**
```bash
cd tests/spikes/004_embedding
python load_papers.py ../../data/out2.jsonl --verbose
```

## Notes

Work in progress...
