# Unified RAG Architecture - Component Reference

## Overview
All 5 retrieval architectures share a common unified framework built from 6 core components. Each architecture is a different combination of these components, particularly different Planner implementations.

## 6 Core Components

### 1. Router (Orchestrator)
**File:** `components/router.py`
**Role:** Master orchestrator managing the 5-stage pipeline

**5-Stage Pipeline:**
```
Get → Plan → Query → Evaluate → Finalize
```

**Key Methods:**
- `route_query(question)` - Main entry point
- `_stage_get()` - Load papers (Stage 1)
- `_stage_plan()` - Generate retrieval plan (Stage 2)
- `_stage_query()` - Execute retrieval (Stage 3)
- `_stage_evaluate()` - Assess quality (Stage 4)
- `_stage_finalize()` - Generate answer (Stage 5)

**Coordinates:** All other components in sequence

---

### 2. Planner (Strategy Decider)
**File:** `components/planner.py`
**Role:** Decides *what* to search for and *how* to search

**Base Class:** `BasePlanner` (abstract)

**Implementations:**
| Implementation | Architecture | Behavior |
|---|---|---|
| `NullPlanner` | 1 (Baseline) | Direct vector search, no planning |
| `SimplifyingPlanner` | 1b (Query Simplification) | LLM extracts keywords before embedding |
| `RouterPlanner` | 2 (LLM-as-Router) | LLM decides which Tool methods to call |
| `DecompositionPlanner` | 3 (Query Decomposition) | LLM breaks into multiple sub-queries |
| `HyDEPlanner` | 4 (HyDE) | LLM generates hypothetical answer |
| `IterativePlanner` | 5 (Iterative) | Multi-turn with feedback loops |

**Key Methods:**
- `formalize(question, papers)` - Create SearchPlan
- `refine(question, results)` - Optional refinement based on quality

**Returns:** `SearchPlan` with:
- `plan_type` - Type of planning
- `queries` - List of queries to search
- `tool_methods` - Which Tool methods to call
- `parameters` - Additional config
- `reasoning` - Why this plan was chosen

---

### 3. Tool (Database Interface)
**File:** `components/tool.py`
**Role:** Execute all data retrieval operations from database

**Key Methods:**
- `vector_search(query)` - pgvector similarity search
- `search_methodology(keywords)` - Structured metadata search
- `search_findings(keywords)` - Findings-specific search
- `deduplicate_results(results)` - Merge multiple search results
- `filter_papers(criteria)` - Filter by year, keywords, etc.

**Returns:** `RetrievalResult` with:
- `chunks` - List of retrieved chunks with metadata
- `paper_count` - Number of unique papers
- `total_similarity` - Sum of relevance scores
- `search_method` - Which method found these

**Supports All 5 Architectures:**
- Baseline (1) - Uses `vector_search()`
- Simplification (1b) - Uses `vector_search()` with simplified query
- Router (2) - Uses multiple methods based on LLM plan
- Decomposition (3) - Uses `vector_search()` multiple times (parallel)
- HyDE (4) - Uses `vector_search()` with hypothetical embedding
- Iterative (5) - Uses `vector_search()` multiple times (sequential)

---

### 4. Evaluator (Quality Assessor)
**File:** `components/evaluator.py`
**Role:** Assess quality of retrieval results

**Scoring Dimensions:**
- `coverage` (0-100) - % of papers represented in results
- `relevance` (0-100) - Average similarity to question
- `freshness` (0-100) - Recency of papers (recent better)

**Key Methods:**
- `evaluate(result, question, papers)` - Return QualityScore

**Returns:** `QualityScore` with:
- Numeric scores for coverage, relevance, freshness
- `is_adequate` - Pass/fail boolean
- `feedback` - Human-readable assessment

**Used By:**
- Router - Determines if more retrieval needed
- IterativePlanner - Decides whether to refine search
- Memory - Stores quality metrics for learning

---

### 5. Synthesizer (Answer Generator)
**File:** `components/synthesizer.py`
**Role:** Generate final answer from retrieved context

**LLM Interaction:**
- Takes question + chunks as input
- Calls Claude Haiku with synthesis prompt
- Returns answer with token usage and latency

**Key Methods:**
- `synthesize(question, retrieval_result)` - Generate answer

**Returns:** `SynthesisResult` with:
- `answer_text` - Generated synthesis
- `tokens_used` - Prompt + completion tokens
- `latency_ms` - Response time
- `citations` - Extracted paper references

---

### 6. Memory (Cache & History)
**File:** `components/memory.py`
**Role:** Enable result reuse and conversation context awareness

**Caching Strategy:**
- In-memory query cache
- Semantic similarity search (embedding-based)
- Threshold: 85% similarity for cache hit

**Storage:**
- SQLite database for persistent history
- Records: question, answer, metrics, quality scores
- Enables learning from previous queries

**Key Methods:**
- `find_similar_query(question)` - Check cache
- `store_interaction(...)` - Save result
- `get_conversation_context(n=5)` - Retrieve last N interactions
- `invalidate_cache()` - Clear when corpus changes
- `get_statistics()` - Cache and performance stats

---

## How They Work Together

### Query Processing Flow (try_03 Example)

```
User: "What barriers do incumbents face to digital innovation?"
       ↓
   [Router.route_query()]
       ↓
   Stage 1: GET
   ├─ Load papers from database
   └─ Check Memory.find_similar_query() for cache hit
       ↓
   Stage 2: PLAN
   ├─ SimplifyingPlanner.formalize()
   ├─ LLM call: Extract keywords
   └─ Returns SearchPlan with simplified query
       ↓
   Stage 3: QUERY  
   ├─ Tool.vector_search() with simplified query
   ├─ Embed "incumbents digital innovation organizational barriers"
   ├─ pgvector search
   └─ Returns RetrievalResult with chunks
       ↓
   Stage 4: EVALUATE
   ├─ Evaluator.evaluate()
   ├─ Calculate: coverage 60%, relevance 85%, freshness 90%
   └─ Returns QualityScore
       ↓
   Stage 5: FINALIZE
   ├─ Synthesizer.synthesize()
   ├─ LLM call: Generate answer from chunks
   ├─ Extract citations
   └─ Returns SynthesisResult
       ↓
   Memory.store_interaction()
   ├─ Cache result
   ├─ Save to history database
   └─ Enable future cache hits
       ↓
   Return: {answer, citations, chunks, quality_score, metrics}
```

---

## Swapping Architectures

To use a different architecture, just change the Planner:

```python
# Architecture 1b: Query Simplification (try_03)
router = Router(
    planner=SimplifyingPlanner(llm_client),  # ← Different planner
    tool=tool,
    evaluator=evaluator,
    synthesizer=synthesizer,
    memory=memory
)

# Architecture 2: LLM-as-Router (try_04)
router = Router(
    planner=RouterPlanner(llm_client),  # ← Just change this
    tool=tool,
    ...
)

# Architecture 3: Query Decomposition (try_05)
router = Router(
    planner=DecompositionPlanner(llm_client),  # ← Just change this
    tool=tool,
    ...
)
```

The Router handles all orchestration uniformly regardless of Planner implementation.

---

## Data Types

**Common Types** (`components/common.py`):

```python
SearchPlan          # From Planner: what to search
QualityScore        # From Evaluator: quality assessment
RetrievalResult     # From Tool: retrieved chunks
SynthesisResult     # From Synthesizer: generated answer
PipelineMetrics     # Tracking: tokens, latency, timestamps
```

---

## File Organization

```
tests/spikes/019_llm_retrieval/
├── components/
│   ├── __init__.py        # Package exports
│   ├── common.py          # Shared types and enums
│   ├── planner.py         # All Planner implementations
│   ├── tool.py            # Database interface
│   ├── evaluator.py       # Quality assessment
│   ├── synthesizer.py     # LLM-based synthesis
│   ├── memory.py          # Caching and history
│   └── router.py          # Orchestrator
├── try_01_retrieve_then_read.py           # Baseline (Architecture 1)
├── try_02_retrieve_then_read_llm_simplification.py  # Simplification (1b)
├── try_03_unified_rag_agent.py            # Unified with components (1b)
├── try_04_query_decomposition.py          # To implement (3)
├── try_05_hyde.py                         # To implement (4)
├── try_06_iterative_retrieval.py          # To implement (5)
└── README.md              # Architecture documentation
```

---

## Running try_03

```bash
# From project root
cd tests/spikes/019_llm_retrieval

# Run with components
python try_03_unified_rag_agent.py

# Interactive commands:
# - Type a question to query
# - 'papers' - Show available papers
# - 'memory' - Show cache stats
# - 'history' - Show previous queries
# - 'help' - Show all commands
# - 'exit' / Ctrl+D - Exit
```

---

## Key Design Principles

1. **Separation of Concerns** - Each component has a single responsibility
2. **Pluggable Planners** - Swap architectures by changing Planner implementation
3. **Uniform Orchestration** - Router handles all architectures identically
4. **Semantic Caching** - Memory uses embeddings for intelligent cache hits
5. **Extensibility** - Easy to add new Planner types or Tool methods
6. **Metrics Tracking** - Full visibility into token usage, latency, quality

---

## Next Steps

- **try_04**: Implement RouterPlanner for agentic tool selection
- **try_05**: Implement HyDEPlanner for hypothetical answers
- **try_06**: Implement IterativePlanner with feedback loops
- **Comparative UI**: Streamlit demo showing all architectures
- **Production Integration**: Best-performing architecture into main pipeline
