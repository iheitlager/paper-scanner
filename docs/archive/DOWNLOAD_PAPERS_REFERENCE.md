# Paper Downloader - Quick Reference

## Overview
Downloads PDFs for papers that passed screening stages from multiple free and legal sources.

## Features
- **Multi-source fallback**: Tries Unpaywall, OpenAlex, CORE, then publisher
- **Smart caching**: Skips papers already downloaded
- **Database integration**: Updates download source in database
- **Progress tracking**: Rich progress bar with status
- **Flexible filtering**: Download by stage (stage0, stage1, stage2)
- **Dry-run mode**: Preview downloads without executing

## Installation
Requires UV to manage dependencies:
```bash
cd tests/spikes/006_bibtex
uv pip install -r requirements.txt
```

## Usage

### Basic: Download all stage 2 papers
```bash
python download_papers.py
```

### Download to specific directory
```bash
python download_papers.py -o ~/my_papers
python download_papers.py --out-dir /path/to/papers
```

### Download from different stage
```bash
# All papers that passed stage 1 keyword filtering
python download_papers.py --stage stage1

# All papers that passed stage 0 quality filter
python download_papers.py --stage stage0
```

### Dry run (preview only)
```bash
python download_papers.py --dry-run
```

### Custom database
```bash
python download_papers.py --db-url postgresql://user:pass@host/db
```

## Environment Variables
- `DATABASE_URL`: PostgreSQL connection (default: `postgresql://pdfuser:pdfuser@localhost/pdfdb`)
- `RESEARCHER_EMAIL`: Email for Unpaywall API (default: `researcher@example.com`)
- `CORE_API_KEY`: Optional CORE API key for enhanced access

## Configuration
Edit `.env` file:
```bash
DATABASE_URL=postgresql://pdfuser:pdfuser@localhost/pdfdb
RESEARCHER_EMAIL=your.email@institution.edu
CORE_API_KEY=your_core_api_key_if_available
```

## Paper Selection Logic
- **stage0**: Papers that passed quality filter (empirical, peer-reviewed, not duplicate)
- **stage1**: Papers that passed keyword screening (have relevant keywords)
- **stage2**: Papers that passed semantic similarity filter (marked as `stage2_pass` or `stage2_review`)

## Download Sources (Priority Order)
1. **Unpaywall** - Legal open access papers, no authentication needed
2. **OpenAlex** - Curated open access metadata, includes PDF URLs
3. **CORE** - Academic repository, requires optional API key
4. **Publisher** - Via institutional access (requires VPN/university network)

## Output
- **Location**: `./papers/` (default) or custom with `-o`
- **Format**: DOI used as filename (e.g., `10_1234_example.pdf`)
- **Database**: Updates `papers.pdf_download_source` with method used
- **Summary**: Statistics showing success rate and methods used

## Troubleshooting

### No papers found
- Check database connection: `--db-url`
- Verify papers have DOIs
- Try earlier stage: `--stage stage1`

### Low success rate
- Some papers may not have open PDFs available
- Publishers require institutional access
- Check email in `RESEARCHER_EMAIL` for Unpaywall

### Database update issues
- Ensure `papers` table has `pdf_download_source` and `pdf_downloaded_at` columns
- Check database permissions

## SQL Schema Requirements
```sql
-- These columns should exist in the papers table
ALTER TABLE papers ADD COLUMN IF NOT EXISTS pdf_download_source VARCHAR(50);
ALTER TABLE papers ADD COLUMN IF NOT EXISTS pdf_downloaded_at TIMESTAMP;
```

## Example Commands
```bash
# Download stage 2 papers to ~/research/pdfs
python download_papers.py -o ~/research/pdfs

# Preview what would be downloaded
python download_papers.py --dry-run

# Download all available papers including stage 1 candidates
python download_papers.py --stage stage1 -o ./candidates

# Check if papers are already cached before downloading
# (cached papers are skipped and counted separately)
```
