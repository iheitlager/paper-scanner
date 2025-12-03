# Small Language Model (SLM) Support via Ollama

Feature branch: `feat/slm`

## Overview

The paper-processor now supports local Small Language Models (SLMs) via Ollama, enabling on-device processing without API dependencies or costs. This feature complements the existing Anthropic Claude integration.

## Architecture

### Dual Handler Pattern

The processor implements a **second handler** (`_call_ollama`) alongside the existing Claude API handler (`_call_claude`):

```
paper-processor
├── Model Detection
│   ├── If model in MODELS → Route to _call_claude()
│   └── If model in SLM_MODELS → Route to _call_ollama()
├── _call_claude()        # Anthropic Claude API
│   ├── Base64 PDF encoding
│   ├── Native document blocks
│   └── Actual token tracking from API
└── _call_ollama()        # Local SLM via subprocess
    ├── Text extraction (requires max_chars)
    ├── Subprocess execution
    └── Estimated token counting
```

### Handler Routing

In `process_record()`, the appropriate handler is selected based on model type:

```python
if self.config.model in SLM_MODELS:
    result, token_usage = self._call_ollama(input_text, system_prompt)
else:
    result, token_usage = self._call_claude(input_text, system_prompt)
```

## Configuration

### YAML Configuration for SLM

```yaml
# config.yml - Example for local Phi model
model: phi                              # SLM model name
max_chars: 10000                        # REQUIRED: Limit PDF text extraction
text_source: pdf                        # PDF file path
prompt_file: src/prompts/metadata.md    # Custom prompt
output_key: extracted_metadata          # Output field
add_metadata: true                      # Track timing/tokens
```

### Key Requirement: max_chars

**SLM models REQUIRE `--max-chars` to be set.** This is necessary because:
- SLMs have limited context windows
- Text extraction via pypdf is required (no native PDF support)
- Prevents memory exhaustion with large PDFs

The processor will warn if max_chars is not set with an SLM model:
```
Warning: SLM model 'phi' works best with --max-chars limit. Consider adding -c <chars>
```

## Usage Examples

### Using Phi Model with Character Limit

```bash
# Extract first 10,000 characters from PDFs and process with Phi
file-scanner ../papers | paper-processor \
  --model phi \
  -c 10000 \
  --prompt-file src/prompts/metadata.md \
  -v >| output.jsonl
```

### Configuration File Approach

Create `config-phi.yml`:
```yaml
model: phi
max_chars: 15000
text_source: pdf
prompt_file: src/prompts/paper-metadata.md
output_key: metadata
add_metadata: true
verbose: true
```

Then run:
```bash
file-scanner ../papers | paper-processor --config config-phi.yml -q >| output.jsonl
```

### Pipeline Processing

```bash
# 1. Scan PDFs
file-scanner ../papers -o pdfs_found.jsonl

# 2. Process with local Phi model (fast, no API)
paper-processor \
  -i pdfs_found.jsonl \
  -o analyzed_local.jsonl \
  --model tinyllama \
  -c 8000 \
  --add-metadata \
  -v

# 3. Parse results
file-parser -i analyzed_local.jsonl -o parsed.jsonl

# 4. Export to CSV
file-reader -i parsed.jsonl -o results.csv
```

## Available Models

### SLM Models (Local via Ollama)

| Model | Output Tokens | Use Case | Speed |
|-------|-------|----------|-------|
| `phi` | 2048 | General extraction | Fast |
| `tinyllama` | 2048 | Lightweight extraction | Very Fast |
| `llama2` | 4096 | More capable analysis | Moderate |

To use a model, install it first:
```bash
ollama pull phi
ollama pull tinyllama
ollama pull llama2
```

### Claude Models (API)

Still available for comparison:
- `claude-opus-4-20250514` - Most capable
- `claude-sonnet-4-5-20250929` - Balanced (default)
- `claude-haiku-4-5-20251001` - Fast
- Legacy Claude 3 models

## Implementation Details

### Text Extraction with max_chars

When using SLM with max_chars:

1. **Get Input Text**: `_get_input_text()` detects max_chars is set
2. **Extract PDF**: `_extract_pdf_text()` uses pypdf to extract text
3. **Limit Content**: Text is truncated to max_chars limit
4. **Pass to Model**: Limited text sent to Ollama

```python
# Example: Extract first 5000 characters from a PDF
input_text = extract_pdf_text("paper.pdf", max_chars=5000)
# Result: "Digital technologies, innovation, and skills: Emerg..." (5000 chars)
```

### Ollama Handler (`_call_ollama`)

- Runs model via subprocess: `ollama run <model> <prompt>`
- 300 second timeout per request
- Graceful error handling for missing/crashed Ollama
- Token estimation (chars ÷ 4)
- JSON response parsing (same as Claude handler)

### Model Validation

```python
# During initialization:
if config.model in SLM_MODELS:
    # Warning about max_chars
    if not config.max_chars:
        warn("Consider adding --max-chars")
    # No API key required
    config.api_key = None
elif config.model in MODELS:
    # Claude model - require API key
    if not api_key:
        error("API key required")
else:
    error("Unknown model")
```

## Performance Characteristics

### Phi (Recommended for Getting Started)

- **Speed**: ~10-30s per page (on CPU)
- **Quality**: Good for metadata extraction
- **Size**: ~1.4GB disk
- **Memory**: ~4GB RAM during inference

### TinyLlama

- **Speed**: ~5-15s per page (fast)
- **Quality**: Basic extraction
- **Size**: ~500MB disk
- **Memory**: ~2GB RAM during inference

### Llama2

- **Speed**: ~30-60s per page
- **Quality**: Better reasoning/analysis
- **Size**: ~3.8GB disk
- **Memory**: ~8GB RAM during inference

## Troubleshooting

### "Ollama command not found"
```
Error: Ollama command not found. Install Ollama to use phi
```
**Solution**: Install Ollama from https://ollama.ai

### "Model not found"
```
Error calling Ollama (phi): child process exited unexpectedly
```
**Solution**: Download the model first:
```bash
ollama pull phi
```

### "Timeout after 300s"
```
Error: Ollama request timed out after 300s
```
**Solution**: Either:
- Reduce max_chars
- Use a faster model (tinyllama)
- Increase timeout in code (only for local dev)

### "JSON parsing failed"
The model output isn't valid JSON. Check:
- System prompt instructs JSON output
- Model understands the prompt
- Try with a different prompt file

## Comparison: SLM vs Claude API

| Factor | SLM (Local) | Claude API |
|--------|------------|-----------|
| Cost | Free | ~$0.015 per 1M input tokens |
| Speed | ~10-30s per page | ~2-5s per page |
| Privacy | 100% local | Sent to Anthropic |
| Accuracy | 70-85% | 95%+ |
| Setup | Need Ollama + model | Need API key |
| Model Size | 500MB-4GB disk | N/A |
| Memory | 2-8GB RAM | N/A |
| GPU Support | Yes (optional) | N/A |

## Future Enhancements

- [ ] GPU acceleration support detection
- [ ] Batch processing optimization
- [ ] Multi-model comparison (Claude vs local)
- [ ] Caching layer for identical inputs
- [ ] Additional SLM models (Mistral, etc.)
- [ ] Custom model fine-tuning support
- [ ] Performance profiling utilities

## Related Files

- `src/paper_scanner/tools/paper_processor.py` - Main implementation
- `tests/spikes/003_local_llm/test_ollama.py` - Original Ollama test code
- `docs/README.md` - User guide (to be updated)

## References

- [Ollama Documentation](https://ollama.ai)
- [Phi Model Card](https://huggingface.co/microsoft/phi-2)
- [TinyLlama Documentation](https://github.com/jzhang38/TinyLlama)
