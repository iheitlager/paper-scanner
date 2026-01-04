# Spike 019: LLM Retrieval Architectures

## Hypothesis
We can improve paper discovery and synthesis quality by implementing multiple LLM-vector retrieval architectures beyond simple encode-and-search. The encoder is optimal for baseline performance, but agentic routing, query decomposition, and hypothetical document embeddings can better serve complex comparative queries typical in systematic reviews.

## Unified Architecture & Design

All five retrieval approaches share a common underlying architecture with 6 core components. This framework enables swappable implementations while maintaining consistent orchestration logic.

### Core Components (Objects)

#### 1. Router
**Responsibility:** Orchestrator managing overall control flow and component coordination.

**Capabilities:**
- Routes query through entire pipeline (Get → Plan → Query → Evaluate → Finalize)
- Manages component lifecycle and state transitions
- Handles error recovery and fallback logic
- Coordinates between Planner, Tool, Evaluator, Synthesizer, and Memory

**Key Methods:**
- `route_query(question)` - Main entry point
- `_get_context()` - Load papers from database
- `_finalize(results)` - Format final output with metrics

**Dependencies:** Orchestrates all other components

#### 2. Planner (Abstract Base)
**Responsibility:** Strategy decision-maker - determines *what* data to retrieve and *how*.

**Capabilities:**
- Analyzes incoming questions
- Decides which Tool methods to call and with what parameters
- Produces structured retrieval plan
- Can invoke LLM to generate search strategies

**Key Methods:**
- `formalize(question, papers)` - Analyze question, return search strategy
- `refine(question, initial_results)` - Optionally refine strategy based on results
- Different implementations: SimplifyingPlanner, RouterPlanner, DecompositionPlanner, HyDEPlanner, IterativePlanner

**Dependencies:** Tool interface for execution

**Implementations Map to Architectures:**
- Architecture 1 (baseline) - NullPlanner (no planning, direct query)
- Architecture 1b (simplification) - SimplifyingPlanner (extracts keywords)
- Architecture 2 (LLM-router) - RouterPlanner (LLM selects tools)
- Architecture 3 (decomposition) - DecompositionPlanner (generates sub-queries)
- Architecture 4 (HyDE) - HyDEPlanner (generates hypothetical)
- Architecture 5 (iterative) - IterativePlanner (multi-turn with feedback)

#### 3. Tool
**Responsibility:** Database interface - executes all data retrieval operations.

**Capabilities:**
- Searches paper metadata (title, DOI, authors, year)
- Vector searches via pgvector
- Structured searches on `deep_analysis` fields (methodology, findings, limitations)
- Citation graph traversal
- Result deduplication and ranking

**Key Methods:**
- `search_methodology(keywords)` - Query structured methodology data
- `vector_search(embedding)` - pgvector similarity search
- `search_findings(keywords)` - Query structured findings data
- `search_citations(paper_id)` - Get forward/backward citations
- `filter_papers(criteria)` - Filter by year, keywords, or custom predicates
- `deduplicate_results(results)` - Remove duplicate chunks

**Dependencies:** PostgreSQL connection, pgvector extension

#### 4. Evaluator
**Responsibility:** Quality control - assesses whether retrieved results are adequate.

**Capabilities:**
- Scores result quality across multiple dimensions
- Decides if more retrieval needed (iterative case)
- Checks coverage, relevance, freshness
- Returns structured quality assessment

**Key Methods:**
- `evaluate(results, question)` - Return QualityScore object
  - `coverage` (0-100): Do results span multiple papers?
  - `relevance` (0-100): How directly relevant to question?
  - `freshness` (0-100): Recency of cited papers?
  - `is_adequate()` - Boolean pass/fail

**Dependencies:** None (pure scoring logic)

#### 5. Synthesizer
**Responsibility:** LLM wrapper - generates final answer from retrieved context.

**Capabilities:**
- Accepts question + retrieved chunks + metadata
- Calls Claude API with structured prompting
- Tracks token usage and latency
- Formats answer with citations and metadata

**Key Methods:**
- `synthesize(question, chunks, metadata)` - Return answer + metadata
  - `answer_text` - Generated synthesis
  - `tokens_used` - Prompt + completion tokens
  - `latency_ms` - Response time

**Dependencies:** Claude API, Anthropic SDK

#### 6. Memory
**Responsibility:** Caching and history - enables result reuse and conversation context.

**Capabilities:**
- Caches previous query results by semantic similarity
- Stores interaction history with all metadata
- Retrieves cached results when similar query asked again
- Enables conversation context awareness

**Key Methods:**
- `find_similar_query(question)` - Check if similar query cached
- `store_interaction(question, plan, results, answer, quality_score)` - Store result
- `get_conversation_context(n=5)` - Last n interactions
- `invalidate_cache()` - When corpus changes

**Dependencies:** Cache storage (in-memory dict or Redis), SQLite for history

### Architecture Pattern: 5-Stage Pipeline

All implementations follow this 5-stage pattern:

1. **Get** - Router loads papers from database into context
2. **Plan** - Planner analyzes question, decides retrieval strategy
3. **Query** - Tool executes retrieval plan (multiple searches possible)
4. **Evaluate** - Evaluator assesses result quality
5. **Finalize** - Synthesizer generates answer, Router formats output with metrics

This pattern unifies all approaches while allowing component specialization.

## Problem Statement
Current spike 018 implementation uses **retrieve-then-read** architecture:
```
Query → Embed → pgvector search → LLM synthesizes
```

This works well for simple Q&A but struggles with:
- Comparative queries ("How do methodologies differ?")
- Multi-faceted questions ("What findings exist AND what are the limitations?")
- Vocabulary mismatch (user terms vs. document terminology)
- Context-aware filtering (e.g., "only recent methods")

## Research Questions
1. **Agentic routing**: Can LLM-selected tool calls (section filters, paper selection) improve retrieval relevance?
2. **Query decomposition**: Do multiple sub-queries find more complete comparative information?
3. **HyDE**: Does hypothetical answer generation better match paper language patterns?
4. **Iterative retrieval**: Can multi-turn feedback loops surface deeper insights than single-pass retrieval?
5. **Implementation efficiency**: Which architecture minimizes tokens while maximizing quality?

## Scope & Deliverables

### Phase 1: Architecture Prototyping (text-based CLI)
- [x] **Retrieve-then-read** (try_01: spike 018 baseline for comparison)
- [x] **Retrieve-then-read with Query Simplification** (try_02: LLM-based simplification fix)
- [ ] **LLM-as-router** (agentic with tool calling)
- [ ] **Query decomposition** (LLM generates sub-queries, parallel embed-search)
- [ ] **HyDE** (hypothetical answer generation before search)
- [ ] **Iterative retrieval** (feedback-driven multi-turn search)

### Phase 2: UI Exploration (Streamlit optional)
- [ ] Comparative demo showing all 5 architectures side-by-side
- [ ] Section filtering and paper selection UX
- [ ] Token usage and latency metrics visualization

### Phase 3: Database Leverage (entity optimization)
Maximize database capabilities across entities:
1. **Paper database**: Title, abstract, DOI-based filtering
2. **Citations**: Forward/backward citation graph traversal
3. **Chunks & Embeddings**: Hierarchical section-aware retrieval (methods, findings, conclusions)
4. **Clustering**: Cluster-aware filtering ("papers similar to X")

## Architecture Details

### Architecture 1: Retrieve-then-Read (Baseline - try_01)
**File:** `try_01_retrieve_then_read.py`

**Framework Integration:**
- **Planner:** NullPlanner (no planning, direct embedding)
- **Tool Methods:** `vector_search()` only
- **Evaluator:** BasicEvaluator (checks if any results returned)
- **Pipeline:** Get → Query (direct) → Finalize

**Flow:**
```
User question → Encoder embeds question → pgvector similarity search → Top-k chunks → LLM synthesizes
```

**How it works:**
- Encoder (not LLM) converts query to 768-dim vector
- pgvector finds nearest chunks by cosine distance
- Chunks returned with similarity scores, paper metadata, section labels
- LLM receives chunks as text context and synthesizes answer

**Strengths:**
- Simple, fast, predictable
- Clear separation of concerns (encoding vs. synthesis)
- Works with any number of papers

**Limitations:**
- Static search parameters (no adaptive filtering)
- **Vocabulary mismatch with complex queries** (meta-language doesn't match paper text)
- No section awareness in search strategy
- Complex questions often return 0 results

**Example Problem:**
```
Question: "What barriers do incumbents face to digital innovation across these papers?"
Result: 0 chunks found (meta-language "barriers", "across", "do incumbents" don't appear in papers)
```

### Architecture 1b: Retrieve-then-Read with Query Simplification (try_02) ⭐ Recommended
**File:** `try_02_retrieve_then_read_llm_simplification.py`

**Framework Integration:**
- **Planner:** SimplifyingPlanner (LLM extracts keywords)
- **Tool Methods:** `vector_search()` with simplified query
- **Evaluator:** BasicEvaluator (checks results exist)
- **Pipeline:** Get → Plan (extract keywords) → Query → Finalize

**Flow:**
```
User question → LLM extracts keywords → Simplified query → Encoder embeds → pgvector search → Top-k chunks → LLM synthesizes
```

**How it works:**
1. **Query Simplification (Plan stage):** SimplifyingPlanner LLM extracts 3-5 key academic search terms from original question
2. **Encoding (Query stage):** Simplified query (not original) is embedded to 768-dim vector
3. **Search (Query stage):** Tool.vector_search() finds chunks using simplified query vector
4. **Synthesis (Finalize stage):** Synthesizer uses original question to provide comprehensive answer

**Example Fix:**
```
Original: "What barriers do incumbents face to digital innovation across these papers?"
SimplifyingPlanner extracts: "incumbents digital innovation organizational barriers"
Result: ✓ Finds relevant chunks (concrete terms match paper text)
Synthesizer: Uses original question to provide comprehensive answer
```

**Strengths:**
- Fixes "0 results" problem with complex meta-language questions
- Minimal token overhead (small LLM call in Plan stage)
- Works immediately with existing papers
- Original question still used for synthesis context
 
**Limitations:**
- Requires additional LLM call (~50-100 tokens)
- LLM simplification quality depends on prompt clarity
- May simplify too aggressively for edge cases

**When to use:**
- ✅ Complex analytical questions
- ✅ Questions with meta-language
- ✅ Comparative queries ("How do X and Y compare?")
- ❌ Simple keyword searches ("digital innovation") - overhead not needed

### Architecture 2: LLM-as-Router (Agentic RAG)
**File:** `try_03_llm_as_router.py`

**Framework Integration:**
- **Planner:** RouterPlanner (LLM decides which Tool methods to call)
- **Tool Methods:** `search_methodology()`, `vector_search()`, `search_findings()`, conditional routing
- **Evaluator:** CoverageEvaluator (checks if multiple data sources used)
- **Pipeline:** Get → Plan (decide tools) → Query (multi-source) → Evaluate → Finalize

**Flow:**
```
User question → LLM generates optimized sub-queries → Parallel embed-search for each → Merge results → LLM synthesizes
```

**How it works:**
- RouterPlanner LLM analyzes question, decides which Tool methods to call
- Each sub-query gets embedded and searched independently
- Tool.deduplicate_results() merges by relevance
- Synthesizer generates answer across merged results

**Example:**
```
User: "How do these papers compare on methodology?"
RouterPlanner LLM decides:
  - Tool.search_methodology("qualitative methods")
  - Tool.search_methodology("case study design")  
  - Tool.vector_search("comparative analysis")
→ Parallel execution → Deduplicate → Synthesize comparative analysis
```

**Strengths:**
- Captures multi-faceted information
- Better coverage than single query
- Parallelizable searches
- Adaptive based on question type

**Limitations:**
- Extra tokens for planning
- Duplicate results need deduplication
- Optimal routing heuristics unknown

### Architecture 3: Query Decomposition
**File:** `try_04_query_decomposition.py`

**Framework Integration:**
- **Planner:** DecompositionPlanner (LLM breaks complex query into sub-queries)
- **Tool Methods:** `vector_search()` for each sub-query
- **Evaluator:** CoverageEvaluator (checks all sub-queries searched)
- **Pipeline:** Get → Plan (decompose) → Query (parallel) → Evaluate → Finalize

**Strengths:**
- Captures multi-faceted information
- Better coverage than single query
- Parallelizable searches

**Limitations:**
- Extra tokens for decomposition
- Duplicate results need deduplication
- Optimal sub-query count unknown

### Architecture 4: HyDE (Hypothetical Document Embeddings)
**File:** `try_05_hyde.py`

**Framework Integration:**
- **Planner:** HyDEPlanner (LLM generates hypothetical answer first)
- **Tool Methods:** `vector_search()` with hypothetical embedding
- **Evaluator:** RelevanceEvaluator (checks if results match hypothetical)
- **Pipeline:** Get → Plan (generate hypothetical) → Query → Evaluate → Finalize

**Flow:**
```
User question → LLM generates hypothetical answer → Embed hypothetical → pgvector search → Real chunks returned → LLM synthesizes final answer
```

**How it works:**
Instead of embedding the question, embed a hypothetical answer that the LLM generates:
```
User: "What do papers say about platform ecosystems?"
HyDEPlanner LLM generates hypothetical: 
  "Platform ecosystems enable value co-creation through complementor relationships, 
   relying on architectural standards and governance mechanisms to coordinate participants..."
→ Tool.vector_search() embeds THIS → Search for matching chunks
```

**Reference:** Gao et al. (2023). Precise zero-shot dense retrieval without relevance labels. *ACL 2023*.

**Strengths:**
- Better alignment with document language
- No training/fine-tuning required
- Handles vocabulary mismatch

**Limitations:**
- Extra LLM call for hypothesis generation
- Hypothetical quality affects retrieval
- May hallucinate domain-specific details

### Architecture 5: Iterative Retrieval
**File:** `try_06_iterative_retrieval.py`

**Framework Integration:**
- **Planner:** IterativePlanner (multi-turn with feedback loop)
- **Tool Methods:** Multiple sequential calls with Evaluator feedback
- **Evaluator:** QualityEvaluator (requests refinement if coverage < threshold)
- **Pipeline:** Get → Plan → Query → Evaluate → (loop if needed) → Finalize

**Flow:**
```
Initial query → Search → LLM reviews results → LLM requests clarification/more context 
→ Follow-up search → LLM reviews again → Synthesize final answer
```

**How it works:**
Multi-turn conversation where IterativePlanner actively manages retrieval:
1. User asks: "What do papers say about digital transformation?"
2. First search: general transformation papers
3. Evaluator assesses coverage, requests "adoption barriers"
4. Follow-up search: "adoption barriers" + filter recent papers
5. Evaluator assesses again, synthesizes

**Strengths:**
- Deep exploratory capability
- Planner controls search depth via Evaluator feedback
- Better for complex topics

**Limitations:**
- Multiple rounds = more tokens
- Requires multi-turn infrastructure
- Risk of infinite loops (bounded by max_iterations)

## Comparison Matrix

| Aspect | Retrieve-Then-Read (1) | Query Simplification (1b) | LLM-as-Router | Query Decomposition | HyDE | Iterative |
|--------|-------------------|------------------------|---------------|---------------------|------|-----------|
| **LLM Calls** | 1 | 2 | 2+ | 2+ | 2 | 3+ |
| **Search Calls** | 1 | 1 | 1-3 | 3-5 | 1 | 2-5 |
| **Token Cost** | Low | Low | Medium | Medium | Medium | High |
| **Latency** | Fastest | Fast | Fast | Medium (parallel) | Medium | Slowest |
| **Adaptive** | No | No | Yes | Yes | No | Yes |
| **Complexity** | Simple | Simple | Medium | Medium | Simple | Complex |
| **Vocabulary Match** | Poor | Excellent | Medium | Medium | Excellent | Medium |
| **Meta-Language** | ❌ Fails | ✅ Handles | ✅ Handles | ✅ Handles | ✅ Handles | ✅ Handles |
| **Complex Queries** | ❌ 0 results | ✅ Finds results | ✅ Excellent | ✅ Excellent | ✅ Good | ✅ Excellent |
| **Implementation** | ✅ Done | ✅ Done | Pending | Pending | Pending | Pending |

## Implementation Plan

### Phase 1: Text-Based CLI Implementations

#### Completed ✅
1. **try_01_retrieve_then_read.py** - Baseline from spike 018
   - Verbose step-by-step pipeline visualization
   - History-enabled REPL with prompt_toolkit
   - Comprehensive metrics tracking
   - Issue: 0 results on complex queries with meta-language

2. **try_02_retrieve_then_read_llm_simplification.py** - Query simplification fix ⭐
   - LLM extracts keywords before embedding
   - Fixes vocabulary mismatch for complex questions
   - Minimal token overhead
   - Recommended for real-world use

#### In Progress
3. **try_03_llm_as_router.py** - Agentic with tool calling
4. **try_04_query_decomposition.py** - Multi-query parallel search
5. **try_05_hyde.py** - Hypothetical answer generation
6. **try_06_iterative_retrieval.py** - Multi-turn feedback loop

**Each implementation:**
- Input: Interactive REPL queries
- Output: 
  - Retrieved chunks (with relevance scores)
  - LLM synthesis
  - Token usage metrics
  - Latency measurement

### Phase 2: Streamlit Comparative UI
Single app showcasing all implementations:
- Side-by-side results comparison
- Metrics dashboard (tokens, latency, chunk quality)
- Interactive section filtering
- Citation graph exploration

### Phase 3: Integration Points
- Integrate best-performing architecture as new CLI step (or Web UI feature)
- Update documentation with recommendations
- Benchmark against spike 018 baseline

## Success Criteria
- [ ] All 5 architectures prototyped and functional
- [ ] Metrics collected (tokens, latency, chunk quality)
- [ ] Streamlit demo operational
- [ ] Clear winner(s) identified for different query types
- [ ] Documentation complete with recommendations
- [ ] Ready for integration into main pipeline

## Notes
- Use existing encoder from spike 018 (no retraining)
- Leverage existing pgvector tables
- Test with real paper corpus from project
- Focus on quality of synthesis, not retrieval volume

## Summary of approaches

**Five RAG architectures for LLM + vector search:**

| Approach | Flow | LLM Role | Best For |
|----------|------|----------|----------|
| **1. Retrieve-then-read** (your current) | Query → embed → search → LLM synthesizes | Passive consumer of retrieved chunks | Simple Q&A, known query patterns |
| **2. LLM-as-router** (agentic) | Query → LLM picks tool/filter → targeted search → LLM synthesizes | Active decision-maker on *where* to search | Section-specific queries, complex corpora |
| **3. Query decomposition** | Query → LLM generates multiple sub-queries → parallel searches → merge → LLM synthesizes | Query optimizer | Comparative questions, multi-faceted queries |
| **4. HyDE** | Query → LLM generates hypothetical answer → embed *that* → search → LLM synthesizes | Hypothetical document generator | When user queries don't match document vocabulary |
| **5. Iterative retrieval** | Query → search → LLM reviews → requests more → search again → LLM synthesizes | Feedback loop controller | Deep research, exploratory analysis |
