# Paper Processor - Quick Reference

## Installation

```bash
uv sync
# or
pip install -e .
```

## Basic Usage

```bash
# From config file
paper-processor --config etc/extract_references_config.yaml \
  -i input.jsonl -o output.jsonl

# Direct command
paper-processor \
  --model claude-3-5-haiku-20241022 \
  --text-source pdf \
  --prompt-file src/prompts/extract-references.md \
  --output-key references \
  -i input.jsonl -o output.jsonl

# Via stdin/stdout
cat papers.jsonl | paper-processor --config config.yaml > enriched.jsonl
```

## Configuration Files

Located in `etc/`:
- `paper_processor_example.yaml` - Template with all options
- `extract_references_config.yaml` - Extract references from PDFs (Haiku)
- `analyze_detailed_config.yaml` - Detailed analysis (Sonnet)
- `test_processor_config.yaml` - Test configuration for keyword extraction

## Available Models

```bash
paper-processor --list-models
```

- `claude-3-5-sonnet-20241022` - Best quality, higher cost
- `claude-3-5-haiku-20241022` - Fast, cheap (recommended for extraction)
- `claude-3-opus-20250219` - Most capable

## Common Options

```
-i FILE          Input JSONLines (stdin if omitted)
-o FILE          Output JSONLines (stdout if omitted)
--config FILE    Load from YAML config
--model MODEL    Claude model to use
--text-source    'pdf', 'content', or record field name
--prompt-file    Path to system prompt file
--output-key     JSON key for output (default: processed)
--add-metadata   Include timing and token metadata
--skip-existing  Don't reprocess records in output file
--quiet          Suppress logging
```

## Text Sources

```bash
# Extract from PDF (specified in file_path field)
--text-source pdf

# Use 'content' field from record
--text-source content

# Use any other field (e.g., 'abstract')
--text-source abstract
```

## Example Commands

### Extract references from all PDFs
```bash
paper-processor \
  --config etc/extract_references_config.yaml \
  -i papers.jsonl \
  -o papers_with_refs.jsonl
```

### Extract keywords from text content
```bash
paper-processor \
  --model claude-3-5-haiku-20241022 \
  --text-source content \
  --prompt-file src/prompts/test-extract-keywords.md \
  --output-key keywords \
  --add-metadata \
  -i input.jsonl -o output.jsonl
```

### Incremental processing (skip already processed)
```bash
paper-processor \
  --config config.yaml \
  --skip-existing \
  -i all_papers.jsonl \
  -o processed.jsonl
```

### Process from pipeline
```bash
file-scanner | file-reader | \
  paper-processor --config config.yaml \
  > enriched.jsonl
```

## Environment Setup

```bash
# Set API key
export ANTHROPIC_API_KEY=sk-ant-...

# Or pass on command line
paper-processor --api-key sk-ant-... ...
```

## Output Format

Input record:
```json
{"file_path": "paper.pdf", "file_name": "paper", "title": "Title"}
```

Output (with `--output-key keywords --add-metadata`):
```json
{
  "file_path": "paper.pdf",
  "file_name": "paper",
  "title": "Title",
  "keywords": {
    "keywords": ["ml", "nlp", "transformers"],
    "summary": "Paper about transformers",
    "_metadata": {
      "start_time": "2025-12-03T16:44:06.990971+00:00",
      "end_time": "2025-12-03T16:44:09.097482+00:00",
      "model": "claude-3-5-haiku-20241022",
      "input_tokens_estimate": 71,
      "text_source": "pdf"
    }
  }
}
```

## Tips & Tricks

### Use Haiku for extraction tasks (~75% cheaper than Sonnet)
```bash
--model claude-3-5-haiku-20241022
```

### Limit token usage to save costs
```bash
--max-tokens 4096
```

### Process in stages
```bash
# Stage 1: Extract with Haiku
paper-processor -i input.jsonl -o stage1.jsonl \
  --model claude-3-5-haiku-20241022 \
  --output-key keywords

# Stage 2: Analyze with Sonnet
cat stage1.jsonl | paper-processor \
  --model claude-3-5-sonnet-20241022 \
  --output-key analysis \
  > final.jsonl
```

### Monitor progress with metadata
```bash
jq '.keywords._metadata | {model, duration: (.end_time - .start_time)}' output.jsonl
```

## Error Handling

The processor automatically:
- Retries on rate limits (429) - waits 61s, max 5 retries
- Strips preamble from Claude responses
- Removes markdown code blocks
- Truncates trailing text after JSON

If JSON parsing fails:
1. Check prompt instructs "output ONLY valid JSON"
2. Review logs: "Response start: ..."
3. Refine prompt to avoid conversational text

## Documentation

See full documentation at `docs/PAPER_PROCESSOR.md`
