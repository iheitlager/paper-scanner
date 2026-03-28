# ADR-0001: External Prompt Templates for LLM Steps

## Status

Accepted

## Date

2026-03-28

## Context

The paper-scanner pipeline has multiple LLM-powered steps (#42), each requiring
a prompt that instructs Claude to return structured output. We need to decide
where prompts live and how steps load them.

Two patterns already coexist in the codebase:

1. **Inline prompts** — `LLMClassificationStep` stores its system prompt as a
   class constant (`SYSTEM_PROMPT_TEMPLATE`). Prompt and parsing logic are
   co-located, but changing the prompt requires a code change.

2. **External prompt files** — `src/prompts/` contains six markdown templates
   (`paper-summary.md`, `paper-metadata.md`, `extract-references.md`, etc.)
   used by the older tools pipeline. These can be edited and versioned
   independently of step code.

With four new steps planned (#43 metadata extraction, #44 relevance scoring,
#45 CAMO extraction, #46 relevance filtering — though #46 needs no prompt),
we need a consistent approach.

## Decision

**Prompts are stored as external markdown files in `src/prompts/` and loaded
by steps at validation time.**

### Rules

1. Each LLM step declares a `prompt` config key pointing to a markdown file
   path relative to the project root (e.g., `src/prompts/extract-metadata.md`).
2. The step loads and caches the prompt content during `validate()`, not per
   paper invocation.
3. Prompt files may contain `{variable}` placeholders that the step interpolates
   at call time (e.g., `{research_question}`, `{json_schema}`).
4. Steps SHOULD inject the target Pydantic model's JSON schema into the prompt
   so Claude knows the exact output structure expected.
5. The workflow YAML references prompts explicitly:

   ```yaml
   - step: "Metadata Extraction"
     builtin.metadata_extraction:
       model: "claude-haiku-4-5-20251001"
       prompt: "src/prompts/extract-metadata.md"
   ```

6. If no `prompt` key is provided, the step MAY fall back to a default path
   by convention: `src/prompts/{step-name}.md`.

### Naming Convention

Prompt files follow the pattern: `{verb}-{noun}.md`

- `extract-metadata.md` — metadata extraction (#43)
- `score-relevance.md` — relevance scoring (#44)
- `extract-camo.md` — CAMO statement extraction (#45)

## Consequences

### Positive

- **Separation of concerns** — prompt wording can be tuned without touching
  step logic; step logic can be refactored without touching prompts.
- **Consistent pattern** — aligns with the six existing files in `src/prompts/`.
- **Diffable** — prompt changes show up as clean markdown diffs in PRs.
- **Configurable per workflow** — different workflows can use different prompts
  for the same step type (e.g., a domain-specific metadata prompt).
- **Schema injection** — embedding the Pydantic JSON schema in the prompt
  keeps the contract between prompt and parser in sync automatically.

### Negative

- **Two files to maintain** — a prompt change may require a corresponding
  parser change (mitigated by schema injection).
- **Migration needed** — `LLMClassificationStep` should be migrated from
  inline to external to maintain consistency (not blocking, can be done later).

### Neutral

- Non-LLM steps (like #46 relevance filtering) are unaffected.

## Related

- #42 — Epic: Structured LLM document analysis pipeline
- #43 — Metadata extraction step
- #44 — Semantic relevance scoring step
- #45 — CAMO statement extraction step
- `src/prompts/` — Existing prompt template directory
- `src/paper_scanner/steps/llm_classification.py` — Current inline prompt pattern
