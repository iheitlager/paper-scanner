# Model Token Limits - Feature Addition

## Overview

Added model-specific maximum output token validation to the paper processor. The processor now:

1. Maintains a dictionary of max tokens per model
2. Displays model limits in help output
3. Validates `--max-tokens` against model limits
4. Fails with clear error message if limit exceeded

## Implementation Details

### Model Limits Dictionary

```python
MODEL_MAX_TOKENS = {
    "claude-3-5-sonnet-20241022": 8192,
    "claude-3-5-haiku-20241022": 8192,
    "claude-3-opus-20250219": 4096,
}
```

### Help Output

Now shows max tokens per model:

```
Available models (with max output tokens):
  claude-3-5-sonnet-20241022: 8192 tokens
  claude-3-5-haiku-20241022: 8192 tokens
  claude-3-opus-20250219: 4096 tokens
```

### Validation

In `main()`, after config merge:

```python
# Validate max_tokens against model limits
model_limit = MODEL_MAX_TOKENS.get(config.model)
if model_limit and config.max_tokens > model_limit:
    print(
        f"Error: max_tokens ({config.max_tokens}) exceeds limit for {config.model} ({model_limit})",
        file=sys.stderr,
    )
    return 1
```

## Test Results

### Test 1: Exceed Haiku limit
```bash
$ echo '{"content": "test"}' | paper-processor \
  --model claude-3-5-haiku-20241022 \
  --max-tokens 9000 \
  --text-source content

Error: max_tokens (9000) exceeds limit for claude-3-5-haiku-20241022 (8192)
```

### Test 2: Exceed Opus limit
```bash
$ echo '{"content": "test"}' | paper-processor \
  --model claude-3-opus-20250219 \
  --max-tokens 5000 \
  --text-source content

Error: max_tokens (5000) exceeds limit for claude-3-opus-20250219 (4096)
```

### Test 3: Valid token count (Passes validation)
```bash
$ echo '{"content": "test"}' | paper-processor \
  --model claude-3-5-haiku-20241022 \
  --max-tokens 8192 \
  --text-source content

(Proceeds to API call)
```

## Benefits

1. **Early validation** - Prevents API calls with invalid token counts
2. **Clear error messages** - Shows expected vs requested limits
3. **Visible limits** - Help output shows max tokens per model
4. **Fail fast** - Exits with error code 1 immediately
5. **Extensible** - Easy to add new models to the limits dictionary

## Future Enhancements

1. Could add `--show-model-limits` flag for detailed info
2. Could implement automatic token limit reduction
3. Could add actual token counting via tiktoken
4. Could fetch limits from Anthropic API at runtime
