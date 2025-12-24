# Ollama Optimization Guide for Apple Silicon (M2 Mac)

## Overview
Ollama automatically uses Apple's Metal Performance Shaders (MPS) for GPU acceleration on Apple Silicon. This guide ensures you're getting optimal performance.

## 1. Verify Ollama Installation

```bash
# Check Ollama version
ollama --version

# Should be 0.1.20 or higher for best M2 support
```

## 2. GPU Acceleration Setup

### Automatic Metal Detection
Ollama automatically detects and uses Metal on Apple Silicon. No configuration needed!

### Verify GPU Usage
1. **Activity Monitor**:
   - Open Activity Monitor
   - Window → GPU History
   - You should see GPU activity when Ollama is running

2. **Terminal Check**:
```bash
# Check if Metal is available
system_profiler SPDisplaysDataType | grep Metal

# Should show: Metal: Supported, feature set macOS GPUFamily2 v1
```

## 3. Model Selection for M2 Mac

### Memory Considerations
Your M2 Mac Mini has unified memory shared between CPU and GPU.

| Model Size | Min RAM | Recommended RAM | Speed on M2 |
|------------|---------|-----------------|-------------|
| 3B params  | 8GB     | 16GB            | ~40 tok/s   |
| 7B params  | 16GB    | 32GB            | ~20 tok/s   |
| 13B params | 32GB    | 64GB            | ~10 tok/s   |

### Recommended Models for Classification

1. **llama3.2:3b** (Best for speed)
```bash
ollama pull llama3.2:3b
```
- Fast: ~40 tokens/second
- Good reasoning
- Low memory: ~4GB

2. **mistral:7b** (Best for accuracy)
```bash
ollama pull mistral:7b
```
- Balanced: ~20 tokens/second
- Excellent reasoning
- Moderate memory: ~8GB

3. **qwen2.5:7b** (Alternative)
```bash
ollama pull qwen2.5:7b
```
- Similar to Mistral
- Good for technical text
- ~8GB memory

## 4. Performance Optimization

### A. Keep Models in Memory
```bash
# Set keep_alive to prevent model unloading
export OLLAMA_KEEP_ALIVE=-1

# Or in your code:
# Set keep_alive parameter when calling Ollama
```

### B. Adjust Context Size
```bash
# Reduce context window if running out of memory
# In Modelfile or API call:
# num_ctx: 2048  (instead of default 4096)
```

### C. Optimize Batch Size
```python
# In your API calls:
{
    "num_batch": 128,  # Smaller batches for M2
    "num_thread": 4    # Utilize CPU cores efficiently
}
```

## 5. Running Ollama Service

### Start Ollama Server
```bash
# Method 1: Standard (runs in background)
ollama serve

# Method 2: With logging
ollama serve 2>&1 | tee ollama.log

# Method 3: Using Docker (alternative)
docker run -d -v ollama:/root/.ollama -p 11434:11434 --name ollama ollama/ollama
```

### Check Service Status
```bash
# Test if Ollama is running
curl http://localhost:11434/api/tags

# Should return list of downloaded models
```

### Restart Ollama (Clean Slate)
```bash
# Kill existing Ollama processes
pkill ollama

# Wait a moment
sleep 2

# Restart
ollama serve &

# Or if installed as service
brew services restart ollama
```

## 6. Monitoring Performance

### Real-time Monitoring
```bash
# Monitor GPU usage
sudo powermetrics --samplers gpu_power -i 1000

# Monitor memory
while true; do
    ps aux | grep ollama | grep -v grep | awk '{print $6/1024 " MB"}'
    sleep 5
done
```

### API Response Times
Add this to your Python code:
```python
import time

start = time.time()
response = ollama.chat(...)
latency = time.time() - start

print(f"Latency: {latency*1000:.0f}ms")
print(f"Tokens/sec: {len(response)/latency:.1f}")
```

## 7. Troubleshooting

### Issue: Slow Performance
**Solutions**:
1. Restart Ollama: `pkill ollama && ollama serve`
2. Reduce context: Use `num_ctx: 2048`
3. Try smaller model: Use 3B instead of 7B
4. Check memory: Close other apps

### Issue: Timeouts
**Solutions**:
1. Increase timeout in code: `timeout=180`
2. Simplify prompt (shorter)
3. Pre-warm model: Run a test query first

### Issue: Inconsistent JSON Responses
**Solutions**:
1. Use `format: "json"` in API call
2. Add strict JSON schema to prompt
3. Parse response more robustly (extract {...})

## 8. Before Running Test 008

```bash
# 1. Ensure Ollama is stopped
pkill ollama

# 2. Start fresh
ollama serve &

# 3. Wait for startup
sleep 5

# 4. Pull required models
ollama pull llama3.2:3b
ollama pull mistral:7b

# 5. Test connectivity
curl http://localhost:11434/api/tags

# 6. Run test
uv run python ./tests/spikes/012_empirical_qualification/test_008_ollama_on_bibtex.py
```

## 9. Expected Performance on M2 Mac

| Model       | Latency/Paper | Memory Usage | GPU Utilization |
|-------------|---------------|--------------|-----------------|
| llama3.2:3b | 3-5s         | ~4GB         | 60-80%          |
| mistral:7b  | 6-10s        | ~8GB         | 70-90%          |

## 10. Why BibTeX vs PDF?

**Problem with PDF Extraction**:
- Adds extra processing time
- Text extraction can fail
- Mixed results with formatting

**Advantage of BibTeX**:
- Clean, structured data
- Pre-extracted abstract
- Keywords readily available
- Separates fact extraction from classification

This is what we're testing in **test_008** and **test_009**!
