# Architecture Decision Records

This directory contains Architecture Decision Records (ADRs) - documents that capture important architectural decisions made during the development of paper-scanner.

## What is an ADR?

An ADR is a short text file in a specific format that captures:
- **Status**: The decision state (Proposed, Accepted, Deprecated, Superseded)
- **Context**: The issue or problem we're addressing
- **Decision**: What we decided to do
- **Consequences**: The results and implications of this decision
- **Alternatives**: Other options we considered

## Creating New ADRs

When proposing a significant architectural decision:

1. Copy `0000-template.md` to a new file with the next sequence number
2. Fill in the template sections
3. Submit as part of code review
4. Once accepted, update status from "Proposed" to "Accepted"

## ADR Naming Convention

Files are named: `NNNN-short-description.md`

Where:
- `NNNN` is the sequence number (0001, 0002, etc.)
- `short-description` is a hyphenated brief description

## Current ADRs

Records are listed below in reverse chronological order:

| # | Title | Status | Date |
|---|-------|--------|------|
| [0001](0001-pipeline-architecture.md) | Pipeline Architecture with Three-Level Config | Accepted | 2025-01-01 |

## References

- [ADR GitHub](https://adr.github.io/)
- [Nygard's Original ADR Format](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions)
