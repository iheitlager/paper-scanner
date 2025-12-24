# Updated Comparison: All Methods vs Ground Truth

## Accuracy Summary

| Method | Correct | Total | Accuracy |
|--------|---------|-------|----------|
| Claude Sonnet 4.5 | 6/8 | 8 | 75.0% |
| Enhanced Regex | 5/8 | 8 | 62.5% |
| Regex (Original) | 3/8 | 8 | 37.5% |
| Sentence Embedding | 2/8 | 8 | 25.0% |
| Ollama (phi3:mini) | 0/8 | 8 | 0.0% |

## Paper-by-Paper Comparison

| Paper | Ground Truth | Regex | Enhanced Regex | Embedding | Ollama | Claude |
|-------|--------------|-------|----------------|-----------|--------|--------|
| 0c288904 | **case_study** | ✗ conceptual | ✓ case_study | ✗ editorial | ✗ unknown | ✓ case_study |
| 0e20b252 | **conceptual** | ✗ editorial | ✗ editorial | ✗ editorial | ✗ unknown | ✓ conceptual |
| 17af2c40 | **case_study** | ✗ conceptual | ✓ case_study | ✗ literature_review | ✗ unknown | ✓ case_study |
| 4f71d2ca | **case_study** | ✗ editorial | ✗ qualitative | ✗ conceptual | ✗ unknown | ✓ case_study |
| 5c8f6a9b | **editorial** | ✓ editorial | ✓ editorial | ✓ editorial | ✗ unknown | ✗ conceptual |
| 5f3b02b4 | **literature_review** | ✓ literature_review | ✓ literature_review | ✗ conceptual | ✗ unknown | ✓ literature_review |
| 639d1860 | **qualitative** | ✓ qualitative | ✓ qualitative | ✓ qualitative | ✗ unknown | ✓ qualitative |
| 77ecffcd | **qualitative** | ✗ unknown | ✗ unknown | ✗ editorial | ✗ unknown | ✗ case_study |

## Detailed Analysis

### Best Performing Method: Claude Sonnet 4.5
- Accuracy: 75.0%
- Correct: 6/8

### Regex (Original) Mismatches

- **0c288904**: Expected `case_study`, got `conceptual` - Note: Empirical case studies - starts with lit review but adds new empirical context
- **0e20b252**: Expected `conceptual`, got `editorial` - Note: Commentary/conceptual piece
- **17af2c40**: Expected `case_study`, got `conceptual` - Note: 3 case studies
- **4f71d2ca**: Expected `case_study`, got `editorial` - Note: 15 cases
- **77ecffcd**: Expected `qualitative`, got `unknown` - Note: 2 intermediaries, 5 incumbents, 11 start-ups

### Enhanced Regex Mismatches

- **0e20b252**: Expected `conceptual`, got `editorial` - Note: Commentary/conceptual piece
- **4f71d2ca**: Expected `case_study`, got `qualitative` - Note: 15 cases
- **77ecffcd**: Expected `qualitative`, got `unknown` - Note: 2 intermediaries, 5 incumbents, 11 start-ups

### Sentence Embedding Mismatches

- **0c288904**: Expected `case_study`, got `editorial` (confidence: 0.21205970644950867) - Note: Empirical case studies - starts with lit review but adds new empirical context
- **0e20b252**: Expected `conceptual`, got `editorial` (confidence: 0.23423978686332703) - Note: Commentary/conceptual piece
- **17af2c40**: Expected `case_study`, got `literature_review` (confidence: 0.2829282879829407) - Note: 3 case studies
- **4f71d2ca**: Expected `case_study`, got `conceptual` (confidence: 0.26924794912338257) - Note: 15 cases
- **5f3b02b4**: Expected `literature_review`, got `conceptual` (confidence: 0.25200527906417847)
- **77ecffcd**: Expected `qualitative`, got `editorial` (confidence: 0.21543103456497192) - Note: 2 intermediaries, 5 incumbents, 11 start-ups

### Ollama (phi3:mini) Mismatches

- **0c288904**: Expected `case_study`, got `unknown` - Note: Empirical case studies - starts with lit review but adds new empirical context
- **0e20b252**: Expected `conceptual`, got `unknown` - Note: Commentary/conceptual piece
- **17af2c40**: Expected `case_study`, got `unknown` - Note: 3 case studies
- **4f71d2ca**: Expected `case_study`, got `unknown` - Note: 15 cases
- **5c8f6a9b**: Expected `editorial`, got `unknown`
- **5f3b02b4**: Expected `literature_review`, got `unknown`
- **639d1860**: Expected `qualitative`, got `unknown` - Note: 33 semi-structured interviews
- **77ecffcd**: Expected `qualitative`, got `unknown` - Note: 2 intermediaries, 5 incumbents, 11 start-ups

### Claude Sonnet 4.5 Mismatches

- **5c8f6a9b**: Expected `editorial`, got `conceptual` (confidence: high)
- **77ecffcd**: Expected `qualitative`, got `case_study` (confidence: high) - Note: 2 intermediaries, 5 incumbents, 11 start-ups

