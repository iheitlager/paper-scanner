# Paper Processor Documentation

A flexible, production-ready CLI tool for enriching JSONLines records with LLM-generated content using Anthropic's Claude models.

## Features

✅ **Multiple Claude Models** - Support for Sonnet, Haiku, and Opus models  
✅ **Flexible Text Sources** - Extract from PDF, use record fields, or custom content  
✅ **Custom Prompts** - Load system prompts from external files  
✅ **Configurable Output** - Define where enriched data goes in the record  
✅ **Metadata Tracking** - Optional timing, token estimates, and processing info  
✅ **Record Filtering** - Skip already-processed records  
✅ **Stdin/Stdout Support** - Stream processing with pipes  
✅ **YAML Configuration** - Centralized config with CLI overrides  
✅ **Robust Error Handling** - Rate limit handling, detailed logging  
✅ **Statistics** - Track processed, successful, error, and skipped records  

## Installation

The processor is included as an entry point in the package:

```bash
pip install -e .
# or
uv sync
```

Then use as:

```bash
paper-processor [options]
```

Or call directly:

```bash
python src/paper_scanner/tools/paper_processor.py [options]
```

## Quick Start

### 1. Extract keywords from text records

```bash
python paper_processor.py \
  -i input.jsonl \
  -o output.jsonl \
  --text-source content \
  --prompt-file src/prompts/test-extract-keywords.md \
  --output-key keywords \
  --model claude-3-5-haiku-20241022
```

### 2. Using YAML configuration

```bash
python paper_processor.py \
  --config etc/processor_config.yaml \
  -i input.jsonl \
  -o output.jsonl
```

### 3. Process from stdin/stdout (pipeline)

```bash
cat input.jsonl | python paper_processor.py \
  --text-source content \
  --output-key summary \
  --prompt-file src/prompts/summarize.md \
  > output.jsonl
```

### 4. Only process new records

```bash
python paper_processor.py \
  --config etc/processor_config.yaml \
  -i new_records.jsonl \
  -o processed.jsonl \
  --skip-existing
```

## Command-Line Options

### Input/Output

```
-i, --input FILE          Input JSONLines file (default: stdin)
-o, --output FILE         Output JSONLines file (default: stdout)
```

### Model Configuration

```
--model MODEL             Claude model to use
                          Options: claude-3-5-sonnet-20241022 (default)
                                   claude-3-5-haiku-20241022
                                   claude-3-opus-20250219
--max-tokens TOKENS       Max output tokens (default: 8192)
--list-models             List available models and exit
```

### Text Processing

```
--text-source SOURCE      Where to get input text
                          'pdf' (default): Extract from file_path field
                          'content': Use content field from record
                          custom_field: Use any record field
--prompt-file FILE        Path to custom system prompt (required)
```

### Output Configuration

```
--output-key KEY          JSON key to store output (default: processed)
--mode MODE               How to store output
                          'add' (default): Add new field
                          'replace': Replace existing field
--add-metadata            Include processing metadata (timing, tokens, etc.)
```

### Processing Options

```
--workers N               Number of worker processes (default: 1)
--skip-existing           Skip records already in output file
```

### General Options

```
--api-key KEY             Anthropic API key
                          Or use ANTHROPIC_API_KEY environment variable
--config FILE             YAML config file (CLI args override)
-q, --quiet               Suppress verbose logging
-h, --help                Show help message
```

## YAML Configuration

Create a `config.yaml` file to centralize settings:

```yaml
# Model and token settings
model: claude-3-5-haiku-20241022
max_tokens: 8192

# Text and prompt configuration
text_source: pdf                    # 'pdf', 'content', or field name
prompt_file: src/prompts/extract.md

# Output settings
output_key: references              # Where to store results
mode: add                          # 'add' or 'replace'
add_metadata: true                 # Include processing metadata

# Processing options
workers: 1                          # Parallel workers
skip_existing: false

# Logging
quiet: false
```

Use with:

```bash
paper-processor --config config.yaml -i input.jsonl -o output.jsonl
```

CLI arguments override YAML settings.

## Input/Output Format

### Input JSONLines Format

```json
{"file_path": "/path/to/paper.pdf", "file_name": "paper", "content": "..."}
{"file_path": "/path/to/paper2.pdf", "file_name": "paper2", "title": "..."}
```

### Output JSONLines Format

Without metadata:
```json
{"file_path": "...", "file_name": "...", "keywords": {"keywords": [...], "summary": "..."}}
```

With metadata (`--add-metadata`):
```json
{
  "file_path": "...",
  "file_name": "...",
  "keywords": {
    "keywords": [...],
    "summary": "...",
    "_metadata": {
      "start_time": "2025-12-03T16:44:06.990971+00:00",
      "end_time": "2025-12-03T16:44:09.097482+00:00",
      "model": "claude-3-5-haiku-20241022",
      "input_tokens_estimate": 71,
      "text_source": "content"
    }
  }
}
```

## Prompt Files

Prompts are external markdown files that are loaded as system messages. Create a prompt file like:

```markdown
You MUST output ONLY valid JSON with no preamble, explanation, or follow-up questions.

Extract keywords and a brief summary from the provided text.

JSON structure:
{
  "keywords": ["keyword1", "keyword2"],
  "summary": "One-line summary"
}

Rules:
- Extract 3-5 most important keywords
- Keep summary to one sentence
- Use null for missing data
- Output only the JSON object
```

Then use with `--prompt-file /path/to/prompt.md`.

## Text Sources

### PDF Extraction (`--text-source pdf`)

Extracts text from PDF file specified in the `file_path` field:

```json
{"file_path": "/path/to/paper.pdf", ...}
```

The processor uses pdfplumber to extract text from all pages.

### Content Field (`--text-source content`)

Uses the `content` field from the input record:

```json
{"content": "Text to process...", ...}
```

### Custom Field (`--text-source custom_field`)

Uses any field from the record:

```json
{"abstract": "Text to process...", ...}
```

Then use `--text-source abstract`.

## Processing Modes

### Add Mode (default)

Adds a new field to the record:

```json
INPUT:  {"id": 1, "title": "Paper"}
OUTPUT: {"id": 1, "title": "Paper", "keywords": {...}}
```

### Replace Mode

Overwrites an existing field:

```bash
# If the output_key already exists, it will be replaced
paper-processor --mode replace --output-key analysis ...
```

## Metadata Tracking

With `--add-metadata`, each processed record includes timing and token information:

```json
{
  "output_key": {
    "data": "...",
    "_metadata": {
      "start_time": "2025-12-03T16:44:06.990971+00:00",
      "end_time": "2025-12-03T16:44:09.097482+00:00",
      "model": "claude-3-5-haiku-20241022",
      "input_tokens_estimate": 71,
      "text_source": "content"
    }
  }
}
```

Metadata fields:
- `start_time`: ISO 8601 timestamp when processing started
- `end_time`: ISO 8601 timestamp when processing ended
- `model`: Claude model used
- `input_tokens_estimate`: Rough estimate of input tokens (chars ÷ 4)
- `text_source`: Where text was extracted from

## Error Handling

### API Rate Limiting

The processor automatically handles rate limiting (HTTP 429) with exponential backoff:
- Waits 61 seconds before retrying
- Retries up to 5 times
- Continues to next record on persistent failure

### Invalid JSON Responses

The processor robustly parses Claude responses:
- Strips preamble text before JSON
- Removes markdown code blocks
- Truncates trailing text after JSON
- Logs detailed error information

## Statistics

After processing, the processor outputs statistics to stderr:

```
=== Processing Statistics ===
Total processed: 100
Successful: 98
Errors: 2
Skipped: 0
```

## Examples

### Example 1: Extract references from PDFs

```bash
# Create config
cat > extract_refs.yaml << 'EOF'
model: claude-3-5-haiku-20241022
max_tokens: 8192
text_source: pdf
prompt_file: src/prompts/extract-references.md
output_key: references
add_metadata: true
EOF

# Process
paper-processor \
  --config extract_refs.yaml \
  -i papers.jsonl \
  -o papers_with_refs.jsonl

# Query results
jq '.references | length' papers_with_refs.jsonl
```

### Example 2: Incremental processing with skip-existing

```bash
# First run - process all records
paper-processor \
  --config config.yaml \
  -i all_papers.jsonl \
  -o processed.jsonl

# Later - add new papers without reprocessing
cat all_papers.jsonl new_papers.jsonl | \
  paper-processor \
    --config config.yaml \
    -o processed.jsonl \
    --skip-existing

# Statistics show only new records were processed
```

### Example 3: Pipeline with other tools

```bash
# Extract papers → process → filter → save
file-scanner \
  | file-reader \
  | paper-processor --config config.yaml \
  | jq 'select(.keywords != null)' \
  > enriched_papers.jsonl
```

### Example 4: Batch processing with different models

```bash
# Haiku for cheap extraction
paper-processor \
  --model claude-3-5-haiku-20241022 \
  --text-source pdf \
  --output-key keywords \
  -i papers.jsonl -o papers_keywords.jsonl

# Sonnet for detailed analysis (uses output from previous)
cat papers_keywords.jsonl | \
  jq 'with_entries(select(.key != "keywords"))' | \
  paper-processor \
    --model claude-3-5-sonnet-20241022 \
    --text-source pdf \
    --output-key detailed_analysis \
    > final_output.jsonl
```

## Environment Variables

```bash
# Anthropic API key (required if not in config or CLI)
export ANTHROPIC_API_KEY=sk-ant-...

# Then run without --api-key
paper-processor --config config.yaml -i input.jsonl -o output.jsonl
```

## Performance Tips

1. **Use Haiku for cheap extractions** - ~75% cheaper than Sonnet
2. **Limit max_tokens** - Don't use more than needed
3. **Batch processing** - Process large files incrementally with `--skip-existing`
4. **Limit text sources** - Use `--text-source content` instead of PDF extraction when possible
5. **Monitor metadata** - Use `--add-metadata` to track processing time

## Troubleshooting

### Module not found errors

```bash
# Ensure package is installed
pip install -e .
# or
uv sync
```

### API key not found

```bash
# Set environment variable
export ANTHROPIC_API_KEY=sk-ant-...

# Or pass explicitly
paper-processor --api-key sk-ant-... ...
```

### PDF not found

Check that `file_path` in records points to valid PDF files.

### Rate limit errors

The processor retries automatically, but adjust expectations:
- Haiku: ~5-10 requests per second
- Sonnet: ~10-20 requests per second

### JSON parsing errors

- Ensure prompt instructs output as JSON only
- Check logs for actual Claude response: "Response start: ..."
- Refine prompt to avoid conversational preamble

## Architecture

The processor follows these patterns from existing tools:

1. **Sequential JSONLines Processing** - Line-by-line streaming for memory efficiency
2. **Immediate Flushing** - Each record written immediately for pipeline compatibility
3. **Retry Logic** - Exponential backoff for rate limiting
4. **Robust JSON Parsing** - Handles conversational preamble and markdown wrapping
5. **Stdin/Stdout Support** - Works in Unix pipelines

## Contributing

To extend the processor:

1. Add new text sources in `_get_input_text()`
2. Add new parsing strategies in `_parse_json_response()`
3. Add new metadata in `process_record()`
4. Test with YAML configs in `etc/`

## Related Tools

- `file-scanner` - Scan PDFs into JSONLines
- `file-processor` - Extract title, authors, methodology, etc.
- `file-processor-references` - Extract references (specialized version of this processor)
- `paper-details` - Extract paper metadata
