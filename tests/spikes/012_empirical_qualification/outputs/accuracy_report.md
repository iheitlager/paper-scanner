# Spike 012: Comparison and Accuracy Analysis

## Summary
- Papers analyzed: 3
- Methods compared: regex, embedding, ollama

## Speed Ranking
1. **regex**: 63.5ms avg per paper
2. **embedding**: 1141.0ms avg per paper
3. **ollama**: 10345.9ms avg per paper

## Detailed Latency Analysis
| Method | Min | Max | Avg | Total (w/o load) |
|--------|-----|-----|-----|------------------|
| regex | 33.2ms | 120.5ms | 63.5ms | 190.6ms |
| embedding | 159.7ms | 3045.8ms | 1141.0ms | 3422.9ms |
| ollama | 3094.2ms | 22219.6ms | 10345.9ms | 31037.8ms |

## Inter-Method Agreement
- **regex_vs_embedding**: 0.0% agreement
- **regex_vs_ollama**: 33.3% agreement
- **embedding_vs_ollama**: 33.3% agreement

## Paper Classifications
| File | Regex | Embedding | Ollama |
|------|-------|-----------|--------|
| 17af2c40-3c32-fc5f-7937-f73141... | conceptual | literature_review | literature_review |
| 5f3b02b4-e497-39bf-2339-4c3c0a... | literature_review | conceptual | literature_review |
| 0e20b252-374a-8055-3ce5-672257... | qualitative | conceptual | literature_review |

## Recommendations
- Regex method is extremely fast (<100ms) - suitable for real-time use
- Embedding method provides good balance of speed and semantic understanding
- Ollama is slower - suitable only for batch processing or non-real-time workflows
- Low agreement between methods (avg 22.2%) - methods capture different aspects
