# Unified RAG Architecture - Visual Guide

## Component Interaction Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                          ROUTER (Orchestrator)                      │
│                   Manages 5-Stage Pipeline Execution                │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    │               │               │
                    ▼               ▼               ▼
        ┌─────────────────┐ ┌──────────────┐ ┌────────────────┐
        │   Stage 1: GET  │ │ Stage 2: PLAN│ │ Stage 3: QUERY │
        │  Load Papers    │ │ Generate     │ │ Execute        │
        │  Check Cache    │ │ Strategy     │ │ Retrieval      │
        └─────────────────┘ └──────────────┘ └────────────────┘
                 │                │                 │
                 │         ┌───────────────┐        │
                 │         │   PLANNER     │        │
                 │         │   (6 types)   │        │
                 │         └───────────────┘        │
                 │                                  │
                 │                          ┌─────────────────┐
                 │                          │     TOOL        │
                 │                          │  vector_search  │
                 │                          │  search_*       │
                 │                          └─────────────────┘
                 │                                  │
                 ▼                                  ▼
        ┌─────────────────────────────────────────────────────┐
        │         Stage 4: EVALUATE                           │
        │  Quality Scoring (coverage, relevance, freshness)   │
        └─────────────────────────────────────────────────────┘
                          │
                ┌─────────┴─────────┐
                │                   │
         Is Adequate?          Need More?
           (Baseline)         (Iterative)
                │                   │
                ▼                   ▼
        ┌──────────────┐    ┌──────────────┐
        │  SYNTHESIZER │    │  REFINE PLAN │
        │ Generate     │    │ (if iterative)
        │ Answer       │    └──────────────┘
        └──────────────┘            │
                │                   │
                │                   │
                ▼                   ▼
        ┌──────────────────────────────────┐
        │     MEMORY (Cache & History)     │
        │  Store result for future reuse   │
        └──────────────────────────────────┘
                         │
                         ▼
        ┌──────────────────────────────────┐
        │  Return Results with Metrics     │
        │  {answer, citations, chunks,     │
        │   quality_score, metrics}        │
        └──────────────────────────────────┘
```

---

## Stage-by-Stage Pipeline

### Stage 1: GET
```
Load papers from database
        ↓
Check Memory for cached result
        ↓
If cache hit: Return cached answer
If no hit: Proceed to Stage 2
```

### Stage 2: PLAN
```
Question: "What barriers do incumbents face?"
        ↓
PLANNER analyzes:
├─ SimplifyingPlanner: Extract keywords
│  → "incumbents organizational barriers digital innovation"
├─ RouterPlanner: Which tools to use?
│  → Use vector_search + search_methodology
├─ DecompositionPlanner: Break into sub-queries?
│  → "barriers", "incumbents", "innovation"
├─ HyDEPlanner: Generate hypothetical?
│  → "Incumbents face organizational barriers..."
└─ IterativePlanner: Multi-turn needed?
   → Start with broad search
        ↓
Returns SearchPlan with:
├─ Queries to search
├─ Tool methods to use
├─ Parameters
└─ Reasoning
```

### Stage 3: QUERY
```
Execute SearchPlan:
├─ Tool.vector_search(query1)
├─ Tool.search_methodology(query2)
├─ Tool.search_findings(query3)
└─ ... (depends on plan)
        ↓
TOOL connects to pgvector database:
├─ Embed queries
├─ Search similar chunks
├─ Return top-k results
└─ Deduplicate if multiple methods
        ↓
Returns RetrievalResult:
├─ Chunks with metadata
├─ Paper count
├─ Similarity scores
└─ Search method used
```

### Stage 4: EVALUATE
```
RetrievalResult received:
├─ 15 chunks from 8 papers
├─ Average similarity: 0.82
├─ Average year: 2021
        ↓
EVALUATOR calculates:
├─ Coverage = 8 papers / 100 total = 8%
├─ Relevance = 0.82 * 100 = 82%
├─ Freshness = 100 - ((2024-2021)/10 * 70) = 79%
        ↓
Returns QualityScore:
├─ coverage: 8%
├─ relevance: 82%
├─ freshness: 79%
├─ is_adequate: false (coverage < 50%)
└─ feedback: "Low coverage"
        ↓
Router decision:
├─ If adequate: → Stage 5 (Finalize)
└─ If iterative: → Refine plan & repeat query
```

### Stage 5: FINALIZE
```
Question: "What barriers do incumbents face?"
Chunks: [chunk1, chunk2, ..., chunk15]
        ↓
SYNTHESIZER creates prompt:
├─ Question
├─ Formatted chunks with metadata
├─ Instructions for comprehensive answer
        ↓
LLM (Claude Haiku) generates answer:
├─ Tokens: 487
├─ Latency: 1200ms
├─ Citations: ["Smith2021", "Jones2022", ...]
        ↓
Returns SynthesisResult:
├─ answer_text: "Based on the papers..."
├─ citations: [...]
├─ tokens_used: 487
└─ latency_ms: 1200
```

---

## Planner Implementation Comparison

```
┌──────────────────────────────────────────────────────────────────┐
│ PLANNER STRATEGY COMPARISON                                      │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│ NullPlanner (Architecture 1)                                     │
│ └─ Strategy: None (direct search)                               │
│    Formalize: Query → SearchPlan(direct, [query], [vector])     │
│    Returns: SearchPlan immediately                              │
│    Best for: Simple keyword searches                            │
│                                                                   │
│ SimplifyingPlanner (Architecture 1b) ⭐                          │
│ └─ Strategy: LLM extracts keywords                              │
│    Formalize: Question → LLM → Keywords → SearchPlan            │
│    LLM cost: ~100 tokens                                         │
│    Returns: SearchPlan(simplify, [keywords], [vector])          │
│    Best for: Complex questions with meta-language              │
│                                                                   │
│ RouterPlanner (Architecture 2)                                  │
│ └─ Strategy: LLM decides which tools to use                     │
│    Formalize: Question → LLM → Tool selection → SearchPlan      │
│    LLM cost: ~150 tokens                                         │
│    Returns: SearchPlan(route, [queries], [methods])             │
│    Best for: Multi-faceted searches                             │
│                                                                   │
│ DecompositionPlanner (Architecture 3)                           │
│ └─ Strategy: LLM breaks into sub-queries                        │
│    Formalize: Question → LLM → Sub-queries → SearchPlan         │
│    LLM cost: ~120 tokens                                         │
│    Returns: SearchPlan(decompose, [q1,q2,q3], [v,v,v])         │
│    Best for: Comparative analysis                               │
│                                                                   │
│ HyDEPlanner (Architecture 4)                                    │
│ └─ Strategy: LLM generates hypothetical answer                  │
│    Formalize: Question → LLM → Hypothetical → SearchPlan        │
│    LLM cost: ~130 tokens                                         │
│    Returns: SearchPlan(hypothetical, [hypo_text], [vector])    │
│    Best for: Vocabulary mismatch                                │
│                                                                   │
│ IterativePlanner (Architecture 5)                               │
│ └─ Strategy: Multi-turn with feedback                           │
│    Formalize: Question → SearchPlan(first search)               │
│    Refine: Results → Evaluator feedback → New query             │
│    LLM cost: ~100 per iteration                                 │
│    Returns: SearchPlan(iterative, [refined], [vector])          │
│    Best for: Deep research exploration                          │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

---

## Data Flow: Chunk Perspective

```
Database (PostgreSQL + pgvector)
├─ papers table
│  ├─ id, title, abstract, cite_key, year
│  └─ deep_analysis (structured findings)
└─ chunk_embeddings table
   ├─ id, content, embedding (768-dim)
   ├─ paper_id, section_label, page_number
   └─ created_at (for freshness)
          │
          │ Tool.vector_search()
          ▼
Vector Search (pgvector)
├─ Normalize query embedding
├─ Compute cosine distance: 1 - (a <=> b)
├─ ORDER BY similarity DESC
└─ LIMIT k (top-5)
          │
          │ RetrievalResult
          ▼
Retrieved Chunks (with metadata)
├─ content: "The methodology used..."
├─ similarity: 0.87
├─ paper_id: 42
├─ title: "Digital Transformation..."
├─ cite_key: "Smith2021"
├─ year: 2021
├─ section: "Methods"
└─ page: 12
          │
          │ Synthesizer._format_context()
          ▼
Formatted Context (for LLM)
├─ [1] Smith2021 - Digital Transformation (2021)
│      Section: Methods, Relevance: 0.87
│      Content: "The methodology used..."
├─ [2] Jones2022 - ...
└─ ...
          │
          │ LLM Synthesis
          ▼
Final Answer
├─ "Based on the papers, the barriers include..."
├─ Citations: [Smith2021, Jones2022]
└─ Quality Score metadata
```

---

## Memory Caching Strategy

```
Query 1: "What barriers do incumbents face?"
├─ Compute embedding: e₁
├─ Generate answer: A₁
├─ Store in Memory: {question, embedding, answer}
        ▼
Query 2: "What obstacles do market leaders encounter?"
├─ Compute embedding: e₂
├─ Memory.find_similar_query():
│  ├─ Compute similarity: cos(e₁, e₂) = 0.92
│  ├─ Threshold: 0.85
│  └─ Result: CACHE HIT! ✓
├─ Return cached answer: A₁
└─ Skip all stages (Plan, Query, Evaluate, Synthesize)
        ▼
Query 3: "What are the latest trends in AI?"
├─ Compute embedding: e₃
├─ Memory.find_similar_query():
│  ├─ Compute similarity: cos(e₁, e₃) = 0.31
│  └─ Result: CACHE MISS
├─ Run full pipeline
└─ Store new result: {question, embedding, answer}
```

---

## Router State Diagram

```
           ┌─────────────┐
           │   START     │
           └──────┬──────┘
                  │
                  ▼
        ┌─────────────────┐
        │  Stage 1: GET   │
        │ Load papers     │
        └────────┬────────┘
                 │
          ┌──────┴──────┐
          │             │
          ▼             ▼
    Cache Hit?     ┌──────────┐
         │         │ No cache │
         │         └────┬─────┘
         │              │
         ▼              ▼
    Return      ┌──────────────┐
    Cached      │ Stage 2: PLAN│
    Answer      │ Create plan  │
         │      └────┬─────────┘
         │           │
         │           ▼
         │      ┌──────────────┐
         │      │ Stage 3: QUERY
         │      │ Execute plan │
         │      └────┬─────────┘
         │           │
         │           ▼
         │      ┌──────────────┐
         │      │ Stage 4: EVAL
         │      │ Score result │
         │      └────┬─────────┘
         │           │
         │      ┌────┴────┐
         │      │          │
         │   Adequate?  Iterative?
         │      │          │
         │      │ YES      │ YES
         │      ▼          │
         │  Stage 5     ┌──┴──────────────┐
         │  Finalize    │ Refine strategy │
         │      │       └────┬───────────┘
         │      │            │
         │      │      ┌─────┴────┐
         │      │      │           │
         │      │   Max iter?   Go to
         │      │  exceeded?    Stage 3
         │      │      │           │
         │      └──────┴───────────┘
         │             │
         └─────────────┘
                │
                ▼
        ┌──────────────────┐
        │  MEMORY: STORE   │
        │  Cache result    │
        └────────┬─────────┘
                 │
                 ▼
        ┌──────────────────┐
        │   RETURN RESULT  │
        │  (answer, stats) │
        └──────────────────┘
```

---

## Component Dependencies

```
        ┌─────────────────┐
        │  Router         │ ◄─── Main entry point
        └────┬────────────┘
             │ Uses all:
      ┌──────┼──────┬─────────────┬────────────┬─────────┐
      │      │      │             │            │         │
      ▼      ▼      ▼             ▼            ▼         ▼
   ┌────┐ ┌────┐ ┌──────┐    ┌─────────┐  ┌──────┐  ┌──────┐
   │Tool│ │Eval│ │Synth │    │Planner  │  │Memory│  │Common│
   └────┘ └────┘ └──────┘    └─────────┘  └──────┘  └──────┘
      │      │       │             │          │         ▲
      └──────┼───────┴─────────────┴──────────┘         │
             │                                           │
             └───────────────────────────────────────────┘
                    All depend on: common.py
                    (types: SearchPlan, QualityScore, etc)
```

---

## Typical Query Processing Sequence

```
User Input: "What barriers do incumbents face to digital innovation?"
                    │
                    ▼ (try_03.py)
        ┌──────────────────────┐
        │ router.route_query() │
        └──────┬───────────────┘
               │
    ┌──────────┴─────────────────────────────────────────┐
    │                                                      │
    ▼                                                      ▼
Router._stage_get()              Router._stage_plan()
    │                                │
    └─> Load papers                 └─> SimplifyingPlanner.formalize()
        (empty list OK)                 │
                                       └─> LLM: Extract keywords
                                           (50-100 tokens)
                                           ↓
                                        Keywords: "incumbents barriers
                                        digital innovation"
                                        ↓
                                        SearchPlan(
                                          plan_type=SIMPLIFY,
                                          queries=["incumbents barriers..."],
                                          tool_methods=["vector_search"]
                                        )
                │                            │
                └────────────────┬───────────┘
                                 │
                        ┌────────▼─────────┐
                        │ Router._stage_query()
                        │                   │
                        └─────┬─────────────┘
                              │
                ┌─────────────┴──────────────┐
                │                            │
        Tool.vector_search()             Returns:
            │                            RetrievalResult(
            ├─ Embed simplified query        chunks=[...],
            ├─ pgvector search               paper_count=8,
            └─ Return top-5 chunks           total_similarity=4.1,
                                             search_method="vector"
                                           )
                │                         │
                └──────────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │ Router._stage_evaluate()
                    │                      │
                    └───────┬──────────────┘
                            │
                Evaluator.evaluate()
                    │
                    ├─ coverage: 8/100 = 8%
                    ├─ relevance: 0.82*100 = 82%
                    ├─ freshness: 79%
                    └─ is_adequate: False (coverage<50%)
                            │
                ┌───────────▼──────────┐
                │ Router._stage_finalize()
                │                       │
                └────────┬──────────────┘
                         │
                Synthesizer.synthesize()
                    │
                    ├─ Format chunks
                    ├─ LLM: Generate answer
                    │  (400-500 tokens)
                    │  ↓
                    │  "Based on the papers, incumbents face..."
                    │
                    └─ Extract citations
                            │
            ┌───────────────▼──────────┐
            │ Memory.store_interaction()
            │                           │
            └─────────┬────────────────┘
                      │
            ├─ Cache in memory
            ├─ Store to SQLite
            └─ Track metrics
                      │
            ┌─────────▼────────────┐
            │ Return Results Dict  │
            ├─ answer: "..."       │
            ├─ citations: [...]    │
            ├─ chunks: [...]       │
            ├─ quality_score: {...}
            ├─ plan_type: "simplify"
            └─ metrics: {...}
```

---

## Performance Characteristics

```
Architecture  │ Planning │ Searching │ Synthesis │ Total  │ Best For
──────────────┼──────────┼───────────┼───────────┼────────┼──────────
Baseline (1)  │   0ms    │  500ms    │  1000ms   │ ~1.5s  │ Simple Q&A
Simplify (1b) │  300ms   │  500ms    │  1000ms   │ ~1.8s  │ Meta-language
Router (2)    │  400ms   │ 1200ms*   │  1200ms   │ ~2.8s  │ Multi-facet
Decompose (3) │  350ms   │ 1500ms*   │  1200ms   │ ~3.1s  │ Comparative
HyDE (4)      │  350ms   │  500ms    │  1100ms   │ ~2.0s  │ Vocab mismatch
Iterative (5) │  varies  │  varies*  │  varies   │ varies │ Deep research

* Parallel execution where possible reduces total time
* Plan time includes LLM tokens (~100-200 per call)
```
