# Spike 012: Comparison and Accuracy Analysis

## Summary
- Papers analyzed: 8
- Methods compared: regex, embedding, ollama

## Speed Ranking
1. **regex**: 46.6ms avg per paper
2. **embedding**: 647.6ms avg per paper
3. **ollama**: 20906.9ms avg per paper

## Detailed Latency Analysis
| Method | Min | Max | Avg | Total (w/o load) |
|--------|-----|-----|-----|------------------|
| regex | 22.9ms | 75.6ms | 46.6ms | 372.7ms |
| embedding | 114.3ms | 3874.4ms | 647.6ms | 5180.5ms |
| ollama | 1523.5ms | 123680.9ms | 20906.9ms | 167255.4ms |

## Inter-Method Agreement
- **regex_vs_embedding**: 37.5% agreement
- **regex_vs_ollama**: 0.0% agreement
- **embedding_vs_ollama**: 0.0% agreement

## Paper Classifications
| File | Regex | Embedding | Ollama |
|------|-------|-----------|--------|
| 77ecffcd-fc1d-15df-525c-ffcaec... | unknown | editorial | None |
| 4f71d2ca-999b-a1ed-1c5a-0e67ce... | editorial | conceptual | None |
| 0c288904-15b6-c0e3-18fd-52fd67... | conceptual | editorial | None |
| 5f3b02b4-e497-39bf-2339-4c3c0a... | literature_review | conceptual | None |
| 639d1860-e441-e167-2966-721eb3... | qualitative | qualitative | None |
| 5c8f6a9b-1772-8597-7e4c-7ebc1d... | editorial | editorial | None |
| 17af2c40-3c32-fc5f-7937-f73141... | conceptual | literature_review | None |
| 0e20b252-374a-8055-3ce5-672257... | editorial | editorial | None |

## Recommendations
- Regex method is extremely fast (<100ms) - suitable for real-time use
- Embedding method provides good balance of speed and semantic understanding
- Ollama is slower - suitable only for batch processing or non-real-time workflows
- Low agreement between methods (avg 12.5%) - methods capture different aspects
