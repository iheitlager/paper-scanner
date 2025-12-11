# feat/slm Quick Reference

## What's New

Extended `paper-processor` to support local Small Language Models (SLMs) via Ollama as an alternative to Anthropic Claude API.

## Key Changes

### 1. **Dual Handler Architecture**
- `_call_claude()` - Existing Anthropic Claude handler
- `_call_ollama()` - NEW local SLM handler via subprocess

### 2. **SLM Models Support**
```python
SLM_MODELS = {
    "phi": 2048,              # Fast, general
    "tinyllama": 2048,        # Very fast, lightweight
    "llama2": 4096,           # More capable
}
```

### 3. **Intelligent Routing**
Automatically selects the correct handler based on model selection:
```bash
paper-processor --model phi -c 10000        # Routes to _call_ollama()
paper-processor --model claude-sonnet...    # Routes to _call_claude()
```

### 4. **max_chars Requirement**
SLM models **require** character limit for text extraction (max_chars is mandatory):
```bash
# ✅ Valid - max_chars specified
paper-processor --model phi -c 10000

# ⚠️  Warning - max_chars recommended but not required
paper-processor --model phi
```

## Architecture Diagram

```
paper-processor
  ├── Config validation
  │   ├── Check if model in SLM_MODELS
  │   ├── If yes: Optional API key
  │   └── If no: Require API key
  │
  └── process_record()
      ├── _get_input_text()
      │   └── If max_chars: Extract PDF text (pypdf)
      │       └── Truncate to max_chars
      │
      ├── Model routing
      │   ├── If SLM: _call_ollama()
      │   │   ├── Run subprocess: ollama run <model> <prompt>
      │   │   ├── Parse JSON response
      │   │   └── Estimate tokens
      │   │
      │   └── If Claude: _call_claude()
      │       ├── Base64 encode PDF
      │       ├── Call Claude API
      │       └── Track actual tokens
      │
      └── Output
          └── Same format for both handlers
```

## Usage Patterns

### Pattern 1: Direct Model Selection
```bash
# Use Phi model with 10K character limit
paper-processor -i input.jsonl -o output.jsonl \
  --model phi \
  -c 10000 \
  --add-metadata \
  -v
```

### Pattern 2: YAML Configuration
```yaml
# config-slm.yml
model: phi
max_chars: 10000
text_source: pdf
output_key: metadata
add_metadata: true
```
```bash
paper-processor -i input.jsonl -o output.jsonl --config config-slm.yml -q
```

### Pattern 3: Pipeline
```bash
file-scanner ./papers | \
  paper-processor --model tinyllama -c 8000 -v | \
  tee output.jsonl | \
  file-parser | \
  file-reader -o results.csv
```

## Code Structure Changes

### New Methods
- `_call_ollama(text, system_prompt)` - Ollama subprocess handler

### Modified Methods
- `process_record()` - Added model routing logic
- `__init__()` - Made Anthropic client optional
- `main()` - Added model validation for SLM vs Claude

### New Constants
```python
SLM_MODELS = {
    "phi": 2048,
    "tinyllama": 2048,
    "llama2": 4096,
}
```

### Config Validation Enhancements
```python
# SLM models
if config.model in SLM_MODELS:
    if not config.max_chars:
        warn("Consider setting --max-chars")
    config.api_key = None  # Not needed

# Claude models (existing behavior)
if config.model in MODELS:
    require(api_key)
```

## Feature Flags

### CLI Flags
```bash
--model {phi, tinyllama, llama2, claude-...}  # Select model
-c, --max-chars CHARS                         # Limit PDF text
--config FILE.yml                             # Load configuration
```

### YAML Config
```yaml
model: phi                    # SLM or Claude
max_chars: 10000             # Character limit for PDF extraction
max_tokens: 2048             # Output token limit (Claude only)
```

## Testing

### Pre-requisites
```bash
# Install Ollama models
ollama pull phi
ollama pull tinyllama

# Ensure Ollama daemon is running
ollama serve  # In separate terminal
```

### Quick Test
```bash
# Check SLM models are available
python paper-processor --list-models

# Help includes SLM models
python paper-processor --help | grep -A 5 "Available Small"

# Test with SLM (requires Ollama running)
echo '{"file_path": "test.pdf"}' | paper-processor --model phi -c 5000 -v
```

## Behavior Differences

### Claude API Handler
- Sends native PDF documents (base64 encoded)
- Actual token counts from API response
- ~2-5 seconds per page
- Requires API key
- Requires internet connection

### Ollama SLM Handler
- Extracts PDF text (requires max_chars)
- Estimated token counts (chars ÷ 4)
- ~10-30 seconds per page (CPU-dependent)
- No API key needed
- Fully local/offline capable

## Error Handling

### Missing Ollama
```
Error: Ollama command not found. Install Ollama to use phi
```

### Model Not Installed
```
Error calling Ollama (phi): child process exited unexpectedly
```
Solution: `ollama pull phi`

### Timeout
```
Error: Ollama request timed out after 300s
```
Solution: Reduce `max_chars` or use faster model

## Files Modified

1. `src/paper_scanner/tools/paper_processor.py` (+122 lines, -25 lines)
   - Added SLM_MODELS constant
   - Added subprocess import
   - Added _call_ollama() method
   - Modified process_record() for routing
   - Updated validation logic
   - Updated help text

2. `docs/SLM_FEATURE.md` (NEW)
   - Comprehensive feature documentation

## Git Info

**Branch**: `feat/slm`
**Status**: Ready for review and testing

## Next Steps

1. Test with running Ollama instance
2. Validate JSON output parsing
3. Test error handling and timeouts
4. Test with different prompt files
5. Merge into main after validation
