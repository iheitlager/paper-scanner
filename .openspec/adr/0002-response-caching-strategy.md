# ADR-0002: Response Caching Strategy for API and LLM Steps

## Status

Accepted

## Date

2026-03-30

## Context

The paper-scanner pipeline makes external calls in two categories:

1. **API calls** — `retrieve_metadata` fetches from CrossRef, OpenAlex, and
   other bibliographic APIs. The `citations` step also queries these APIs.
2. **LLM calls** — `metadata_extraction`, `relevance_scoring`, `camo_extraction`,
   and `llm_classification` send paper content to Claude for structured analysis.

API responses are already cached via `JSONFileCache` in the fetcher layer
(`Fetcher` / handler classes), keyed by DOI with a 30-day TTL. This works well
and has been stable since early development.

LLM responses were **not** cached. During evaluation pipeline runs
(`definition-llm-evaluation.yml`) the same 5 papers are sent to Claude
repeatedly, wasting API credits and adding latency. The same problem applies
to any iterative workflow where a pipeline is re-run after tweaking later steps.

We need a consistent caching strategy that covers both categories while giving
pipeline authors control over when to bypass the cache.

## Decision

**All steps that make external calls (API or LLM) support file-based response
caching via `JSONFileCache`, keyed by DOI, with two user-facing config options.**

### Cache location

```
$XDG_CACHE_HOME/paper-scanner/
  api/                          # API response cache (existing)
    crossref/                   # CrossRef responses
    openalex/                   # OpenAlex responses
    ...
  llm/                          # LLM response cache (new)
    metadata_extraction/        # Claude responses for metadata extraction
    relevance_scoring/          # Claude responses for relevance scoring
    camo_extraction/            # Claude responses for CAMO extraction
    llm_classification/         # Claude responses for classification
```

API caches live under `api/` with handler-specific subdirectories (existing
pattern). LLM caches live under a new `llm/` namespace with step-specific
subdirectories, accessible via `get_json_cache_dir() / "llm" / "<step_name>"`.

### Config options

Every caching step exposes two boolean config options in the pipeline YAML:

| Option      | Default | Meaning                                         |
|-------------|---------|--------------------------------------------------|
| `cache`     | `true`  | Store responses in the file cache after the call |
| `use_cache` | `true`  | Check cache before making the external call      |

Combinations:

- `cache: true, use_cache: true` (default) — normal operation, read and write cache
- `cache: true, use_cache: false` — force fresh calls but update cache (useful for refreshing stale entries)
- `cache: false, use_cache: true` — use existing cache but don't pollute it with new entries
- `cache: false, use_cache: false` — no caching at all (full evaluation mode)

### Cache key

The cache key is the paper's **DOI**. Papers without a DOI cannot be cached
because there is no stable identifier; they always make a fresh external call.

### TTL policy

| Cache type | Default TTL | Rationale |
|------------|-------------|-----------|
| API        | 30 days     | Bibliographic metadata changes infrequently but corrections happen |
| LLM        | No expiry   | Same input + same prompt = same output; prompt changes invalidate by cache directory |

LLM caches use no TTL because the response is deterministic for a given input.
When prompts change significantly, the pipeline author can clear the cache
(`paper-processor cache clear`) or use `use_cache: false` for a fresh run.

### Implementation pattern for LLM steps

Each LLM step follows this pattern in `execute()`:

```python
# Initialize cache if needed
cache = None
if cache_enabled or use_cache:
    cache_dir = get_json_cache_dir() / "llm" / "step_name"
    cache = JSONFileCache(cache_dir=cache_dir, default_ttl=None)

for paper in papers:
    cache_key = paper.doi if paper.doi else None

    # Try cache first
    if use_cache and cache and cache_key:
        cached = cache.get(cache_key)
        if cached is not None:
            apply_response(paper, cached)
            stats["cache_hits"] += 1
            continue

    # Call LLM
    response = claude.call(...)

    # Store in cache
    if cache_enabled and cache and cache_key:
        cache.set(cache_key, response)

    apply_response(paper, response)
```

### Steps requiring caching support

| Step | Category | Cache status |
|------|----------|-------------|
| `retrieve_metadata` | API | Already cached via Fetcher layer |
| `citations` | API | Already cached via Fetcher layer |
| `download_pdfs` | API | Already cached via PDFCache |
| `metadata_extraction` | LLM | Implemented (#57) |
| `relevance_scoring` | LLM | To be implemented |
| `camo_extraction` | LLM | To be implemented |
| `llm_classification` | LLM | To be implemented |

## Consequences

### Positive

- **Cost savings** — repeated pipeline runs reuse cached LLM responses,
  avoiding redundant API credits.
- **Faster iteration** — cached responses return instantly, enabling rapid
  pipeline development and debugging.
- **Consistent interface** — all caching steps share the same `cache` /
  `use_cache` config options, easy to remember.
- **Granular control** — pipeline authors can enable/disable caching per step
  and per run without code changes.
- **Existing infrastructure** — reuses `JSONFileCache` and XDG-compliant paths
  from ADR-less but well-established patterns in `core/cache.py` and
  `core/paths.py`.

### Negative

- **Cache invalidation on prompt changes** — if a prompt template is updated,
  stale cached responses may be served. Mitigation: use `use_cache: false` or
  clear the cache. A future improvement could hash the prompt into the cache key.
- **Disk usage** — LLM responses accumulate without TTL. Mitigation: the
  `paper-processor cache clear` command exists, and responses are small JSON
  files (typically < 5 KB each).

### Neutral

- Non-external steps (deduplication, keyword_screening, export, etc.) are
  unaffected.
- The API fetcher layer continues to manage its own caching independently;
  this ADR does not change that pattern but documents it for consistency.

## Related

- #57 — LLM response caching for metadata extraction (first implementation)
- ADR-0001 — External prompt templates for LLM steps
- `src/paper_scanner/core/cache.py` — JSONFileCache and PDFCache implementations
- `src/paper_scanner/core/paths.py` — XDG-compliant cache path resolution
