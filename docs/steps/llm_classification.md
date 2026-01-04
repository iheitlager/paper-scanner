# LLM Classification

### Title
**LLM Classification** - Classifies papers using Claude LLM with custom categories and confidence thresholds

### Description

The LLM Classification step uses Claude to automatically categorize papers into user-defined categories based on paper content, abstracts, and metadata. It provides confidence scores for each classification and can handle multi-class and hierarchical classification schemes. Use this step to automatically categorize papers by research area, methodology, study type, or any custom taxonomy.

### Features

- ✅ **Custom categories**: Define any classification scheme
- ✅ **Confidence scores**: Get reliability metrics for each classification
- ✅ **Multi-class support**: Classify papers into multiple categories
- ✅ **Claude integration**: Leverages advanced LLM capabilities
- ✅ **Caching**: Avoid re-classifying identical papers
- ✅ **Batch processing**: Efficient processing of large datasets
- ✅ **System prompts**: Customize classification instructions

### Configuration

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `categories` | `list` | Yes | - | List of classification categories |
| `description` | `string` | No | - | Classification scheme description for Claude |
| `confidence_threshold` | `float` | No | `0.5` | Minimum confidence (0.0-1.0) for accepting classification |
| `system_prompt` | `string` | No | `[default]` | Custom LLM system prompt for classification |
| `batch_size` | `int` | No | `10` | Papers to classify per API call |

#### YAML Definition

```yaml
# Basic classification
- step: Classify papers by research methodology
  builtin.llm_classification:
    categories:
      - "Experimental Study"
      - "Literature Review"
      - "Methodological Paper"
      - "Survey"
    description: "Classify by primary research methodology"

# Advanced classification with confidence threshold
- step: High-confidence methodology classification
  builtin.llm_classification:
    categories:
      - "Empirical Research"
      - "Theoretical Study"
      - "Case Study"
      - "Meta-Analysis"
    description: "Classify research methodology with high confidence"
    confidence_threshold: 0.8
    batch_size: 20
```

### Input/Output

#### Input
- **Format**: Papers from database with title, abstract, and metadata
- **Source**: Database populated by prior import steps
- **Requirements**: Papers with sufficient text for classification

#### Output
- **Format**: Paper classifications with confidence scores stored in database
- **Tags**: Classifications added as paper tags
- **Stats**: Count of classified papers, confidence statistics
- **Metadata**: Stored in paper metadata for filtering

### Validation

The step validates:
- `categories` is required and must be non-empty list
- `confidence_threshold` must be float between 0.0 and 1.0
- `batch_size` must be positive integer
- `description` must be string if provided
- All categories are strings

### Classification Process

1. **Prepare**: Extract paper content (title, abstract, metadata)
2. **Batch**: Group papers for efficient API calls
3. **Classify**: Send to Claude with category options
4. **Score**: Receive confidence scores for each category
5. **Filter**: Apply confidence threshold
6. **Store**: Save classifications to database

### Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| "categories list is empty" | No categories specified | Add classification categories |
| "Invalid confidence_threshold" | Not between 0.0 and 1.0 | Use value in range [0.0, 1.0] |
| "LLM API error" | Claude API unavailable | Check API key and network |
| "Insufficient paper metadata" | Papers too sparse for classification | Ensure papers have abstracts |

### Examples

#### Basic Example - Research Methodology
```yaml
- step: Classify by research type
  builtin.llm_classification:
    categories:
      - "Empirical Study"
      - "Literature Review"
      - "Methodological Development"
```

#### Advanced Example - Multi-Level Classification
```yaml
- step: Classify by research area
  builtin.llm_classification:
    categories:
      - "Machine Learning"
      - "Natural Language Processing"
      - "Computer Vision"
      - "Robotics"
      - "Data Mining"
    description: "Classify papers by AI research area"
    confidence_threshold: 0.7

- step: Classify by methodology
  builtin.llm_classification:
    categories:
      - "Theoretical"
      - "Experimental"
      - "Comparative Study"
      - "Case Study"
    description: "Classify by research methodology"
    confidence_threshold: 0.7

- step: Export classifications
  builtin.export:
    format: "jsonl"
    output_file: "classified_papers.jsonl"
```

#### Domain-Specific Example - Healthcare Research
```yaml
- step: Classify clinical domains
  builtin.llm_classification:
    categories:
      - "Oncology"
      - "Cardiology"
      - "Neurology"
      - "Infectious Disease"
      - "Surgery"
      - "Pediatrics"
    description: "Classify medical papers by clinical domain"
    confidence_threshold: 0.8
    batch_size: 25

- step: Report classifications
  builtin.report:
    histogram: true
    screening: true
```

#### Full Pipeline with Classification
```yaml
- step: Import papers
  builtin.bibtex_import:
    batch_id: "medical_research_2024"
    imports:
      - name: "PubMed"
        file_path: "data/pubmed.bib"

- step: Deduplicate
  builtin.deduplication:
    method: "exact"

- step: Classify by clinical area
  builtin.llm_classification:
    categories:
      - "Oncology"
      - "Cardiology"
      - "Neurology"
    description: "Classify medical papers by primary clinical domain"
    confidence_threshold: 0.75

- step: Show classification results
  builtin.report:
    screening: true
    source: true

- step: Export classified papers
  builtin.export:
    format: "jsonl"
    output_file: "classified_medical_papers.jsonl"
```

### Configuration Notes

- **Categories**: Keep list focused (5-10 categories optimal)
- **Descriptions**: Provide context for Claude to make better classifications
- **Thresholds**: Higher (0.8-0.9) for strict classification, lower (0.5-0.6) for permissive
- **Batch size**: Larger batches more efficient but may hit rate limits
- **System prompts**: Advanced users can customize classification instructions

### Confidence Metrics

The step provides:
- `confidence_distribution`: How many papers at each confidence level
- `high_confidence`: Papers above threshold
- `low_confidence`: Papers below threshold (not classified)
- `unclassified`: Papers that couldn't be classified

### Performance Notes

- **API usage**: Depends on paper count and batch size
- **Cost**: Each batch calls Claude API
- **Caching**: Identical papers cached to reduce API calls
- **Rate limits**: Respects Claude API rate limits

### See Also

- [Keyword Screening](keyword_screening.md) - Keyword-based filtering
- [Semantic Screening](semantic_screening.md) - Semantic similarity classification
- [Rocchio Classifier](rocchio_classifier.md) - Machine learning classification
- [Report](report.md) - View classification results
- [Export](export.md) - Save classified papers
