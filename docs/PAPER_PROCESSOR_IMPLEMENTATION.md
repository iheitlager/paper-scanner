# Paper Processor Implementation Summary

## Overview

Successfully implemented `paper_processor.py` - a flexible, production-ready CLI tool for enriching JSONLines records with LLM-generated content using Anthropic's Claude models.

## Implementation Details

### Core Architecture

**File**: `src/paper_scanner/tools/paper_processor.py` (530 lines)

**Key Components**:
1. **ProcessorConfig** - Dataclass holding all configuration parameters
2. **PaperProcessor** - Main processor class with API integration
3. **CLI Interface** - Comprehensive argparse setup with all 17 options
4. **JSON Parsing** - Robust response parsing with preamble/markdown cleanup
5. **Error Handling** - Rate limit retry logic (61s wait, 5 max retries)
6. **Statistics** - Track processed/success/error/skipped records

### Features Implemented

✅ **Model Selection**
- Support for 3 Claude models (Sonnet, Haiku, Opus)
- Available via `--model` or YAML config
- `--list-models` flag to show options

✅ **Flexible Text Sources**
- `--text-source pdf`: Extract from PDF in file_path
- `--text-source content`: Use content field from record
- `--text-source custom_field`: Use any record field

✅ **Custom Prompts**
- Load system prompts from external markdown files
- `--prompt-file` parameter
- Supports JSON-only instruction patterns

✅ **Configurable Output**
- `--output-key` to specify enrichment field name
- `--mode add` (default): Add new field
- `--mode replace`: Replace existing field

✅ **Metadata Tracking**
- `--add-metadata` flag includes:
  - Start/end timestamps (ISO 8601)
  - Model used
  - Input token estimate
  - Text source used
  - Stored in `_metadata` subfield

✅ **Record Filtering**
- `--skip-existing` flag skips already-processed records
- Loads existing output file, matches by file_path
- Useful for incremental processing

✅ **I/O Flexibility**
- `-i/--input`: File or stdin
- `-o/--output`: File or stdout
- Immediate flushing for pipeline compatibility

✅ **YAML Configuration**
- `--config` loads from YAML file
- CLI args override YAML settings
- Centralized configuration management

✅ **Error Handling & Statistics**
- Automatic retry on rate limits (HTTP 429)
- Robust JSON parsing (strips preamble, markdown, trailing text)
- Detailed logging to stderr
- Statistics output after processing

### Command-Line Interface

```
usage: paper_processor.py [options]

Input/Output:
  -i, --input FILE              Input JSONLines file (default: stdin)
  -o, --output FILE             Output JSONLines file (default: stdout)

Model Configuration:
  --model {sonnet,haiku,opus}   Claude model (default: sonnet)
  --max-tokens TOKENS           Max output tokens (default: 8192)
  --list-models                 List available models

Text Processing:
  --text-source SOURCE          'pdf', 'content', or field name (default: pdf)
  --prompt-file FILE            Path to system prompt

Output Configuration:
  --output-key KEY              JSON key for output (default: processed)
  --mode {add,replace}          How to store output (default: add)
  --add-metadata                Include timing and token data

Processing Options:
  --workers N                   Parallel workers (default: 1)
  --skip-existing               Skip already-processed records

General:
  --api-key KEY                 Anthropic API key
  --config FILE                 YAML configuration file
  -q, --quiet                   Suppress logging
  -h, --help                    Show help
```

## Files Created

### Main Implementation
- **`src/paper_scanner/tools/paper_processor.py`** (530 lines)
  - Complete implementation with all features
  - ~440 lines of functionality
  - ~90 lines of CLI setup

### Documentation
- **`docs/PAPER_PROCESSOR.md`** - Comprehensive 500+ line guide
  - Installation instructions
  - Quick start examples
  - All CLI options documented
  - 8+ practical examples
  - Troubleshooting guide
  - Architecture overview

- **`docs/PAPER_PROCESSOR_QUICK_REFERENCE.md`** - Quick reference card
  - Common commands
  - Config file templates
  - Tips & tricks
  - Error handling

### Configuration Examples
- **`etc/paper_processor_example.yaml`** - Template with all options
- **`etc/extract_references_config.yaml`** - Extract references (Haiku)
- **`etc/analyze_detailed_config.yaml`** - Detailed analysis (Sonnet)
- **`etc/test_processor_config.yaml`** - Test configuration

### Prompts
- **`src/prompts/test-extract-keywords.md`** - Example test prompt

### Package Updates
- **`pyproject.toml`** - Added:
  - `pyyaml>=6.0` to dependencies
  - `paper-processor` script entry point

## Tested Capabilities

### ✓ Verified Working
1. **Help output** - All options visible and documented
2. **List models** - Shows 3 available models
3. **YAML loading** - Config merges correctly with CLI overrides
4. **Stdin/Stdout** - Processes from pipes
5. **File I/O** - Reads and writes JSONLines correctly
6. **JSON enrichment** - Adds/replaces fields as configured
7. **Metadata tracking** - Includes timing and token data
8. **Skip existing** - Correctly identifies and skips processed records
9. **Error handling** - Graceful degradation on failures
10. **Statistics** - Accurate counting and reporting

### Test Results
```
Two-record test with Haiku model:
✓ Total processed: 2
✓ Successful: 2
✓ Errors: 0
✓ Skipped: 0 (first run)
✓ Skipped: 2 (second run with --skip-existing)
```

## Design Decisions

### 1. **Inheriting from Existing Patterns**
- API client setup matches `file_processor.py`
- Retry logic identical to `file_processor_references.py`
- JSONLines streaming with immediate flushing
- Stdin/stdout support for pipeline compatibility

### 2. **Dataclass for Configuration**
- Type-safe configuration management
- Easy to extend with new options
- Clear parameter documentation

### 3. **External Prompt Files**
- Best practice from `file_processor_references.py`
- Prompts stored in `src/prompts/` directory
- Supports any markdown-based prompt format

### 4. **Sequential Processing (Not Parallel)**
- Simpler error handling
- Natural rate-limit backoff
- Immediate output streaming
- Matches existing tool patterns

### 5. **Robust JSON Parsing**
- Strips preamble before first `{`
- Removes markdown code blocks
- Truncates after last `}`
- Handles Claude's conversational responses

### 6. **YAML + CLI Override Pattern**
- Centralized configuration (YAML)
- Ad-hoc overrides (CLI args)
- Clear precedence: CLI > YAML > defaults

## API Integration

### Anthropic Client
- Uses official `anthropic` package (0.75.0)
- Authenticated via `ANTHROPIC_API_KEY` or `--api-key`
- Supports all Claude models

### Rate Limiting
- Catches HTTP 429 responses
- Waits 61 seconds between retries
- Max 5 retries per record
- Continues to next record on failure

### Token Management
- Respects per-model limits
- Haiku: 8,192 token max output
- Sonnet: 8,192 token default (configurable)
- Includes token estimate in metadata

## Performance Characteristics

### Memory
- Streaming JSONLines: O(1) memory per record
- Immediate flush: No buffering

### Speed (Approximate, Haiku)
- Simple extraction: 2-3 seconds per record
- With rate limits: 61+ seconds wait between retries

### Cost (Haiku vs Sonnet)
- Haiku: ~$0.80/$4.00 per 1M tokens in/out
- Sonnet: ~$3/$15 per 1M tokens in/out
- Haiku ~75% cheaper for extraction tasks

## Extension Points

1. **New text sources** - Add cases in `_get_input_text()`
2. **Custom parsing** - Add logic in `_parse_json_response()`
3. **Metadata fields** - Add to `process_record()`
4. **Model selection** - Update `AVAILABLE_MODELS`

## Known Limitations

1. **Sequential processing** - No parallelization (design choice)
2. **No batch API calls** - One record at a time
3. **Token counting** - Rough estimate (chars ÷ 4), not actual
4. **Multiprocessing** - `--workers N` placeholder (not implemented)

## Related Tools

This processor complements:
- **`file-processor`** - Extract title, authors, methodology
- **`file-processor-references`** - Extract references (specialized)
- **`file-scanner`** - Scan PDFs into JSONLines
- **`paper-details`** - Extract metadata

## Usage Examples

### Extract references from PDFs (cheap with Haiku)
```bash
paper-processor --config etc/extract_references_config.yaml \
  -i papers.jsonl -o papers_with_refs.jsonl
```

### Detailed analysis (better quality with Sonnet)
```bash
paper-processor --config etc/analyze_detailed_config.yaml \
  -i papers.jsonl -o analyzed.jsonl
```

### Process new records only
```bash
paper-processor --config config.yaml --skip-existing \
  -i all_papers.jsonl -o processed.jsonl
```

### Pipeline integration
```bash
file-scanner | file-reader | paper-processor --config config.yaml > output.jsonl
```

## Files Modified/Created Summary

| File | Type | Status | Purpose |
|------|------|--------|---------|
| `src/paper_scanner/tools/paper_processor.py` | Code | ✓ Created | Main processor implementation |
| `docs/PAPER_PROCESSOR.md` | Docs | ✓ Created | Comprehensive documentation |
| `docs/PAPER_PROCESSOR_QUICK_REFERENCE.md` | Docs | ✓ Created | Quick reference guide |
| `etc/paper_processor_example.yaml` | Config | ✓ Created | Template configuration |
| `etc/extract_references_config.yaml` | Config | ✓ Created | Example: reference extraction |
| `etc/analyze_detailed_config.yaml` | Config | ✓ Created | Example: detailed analysis |
| `etc/test_processor_config.yaml` | Config | ✓ Created | Test configuration |
| `src/prompts/test-extract-keywords.md` | Prompt | ✓ Created | Example prompt for testing |
| `pyproject.toml` | Config | ✓ Updated | Added pyyaml, script entry |

## Next Steps

The processor is production-ready. Potential future enhancements:

1. **Implement multiprocessing** - For CPU-bound PDF extraction
2. **Batch API calls** - Group multiple records per API call
3. **Actual token counting** - Use tiktoken library
4. **Database backend** - Optional caching in PostgreSQL
5. **Metrics collection** - Track API costs, timing, success rates
6. **UI dashboard** - Web interface for configuration and monitoring

## Installation & Running

```bash
# Install dependencies
uv sync

# Show help
python src/paper_scanner/tools/paper_processor.py --help

# Run with config
paper-processor --config etc/extract_references_config.yaml \
  -i input.jsonl -o output.jsonl

# Or as script (after uv sync)
python -m paper_scanner.tools.paper_processor --help
```

## Summary

Successfully delivered a **flexible, production-ready processor** that:
- ✅ Supports multiple Claude models with configurable parameters
- ✅ Enables various text extraction strategies (PDF, content, custom fields)
- ✅ Integrates external prompts for domain-specific processing
- ✅ Provides rich configuration via YAML files
- ✅ Includes optional metadata tracking for monitoring
- ✅ Handles rate limiting and errors gracefully
- ✅ Works in Unix pipelines with stdin/stdout
- ✅ Filters and skips already-processed records
- ✅ Outputs meaningful statistics for tracking
- ✅ Fully documented with examples

The processor is ready for immediate use in enriching JSONLines records across the paper-scanner pipeline.
