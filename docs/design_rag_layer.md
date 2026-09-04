# Architectural Design: TriAPI Memory and RAG Layer

## Executive Summary

This document specifies the architectural design for TriAPI's retrieval-augmented generation (RAG) and persistent memory subsystem. The primary objective is to enhance worker context across tiers by semantically surfacing pertinent historical lessons and reusable snippets while strictly preserving TriAPI's core operating principles: zero marginal API cost for embeddings, bounded prompt growth, and deterministic execution.

## 1. Exactly-Once Retrieval Lifecycle

In TriAPI's multi-tier architecture, tasks escalate sequentially across tiers upon failure (Tier 4 -> Tier 3 -> Tier 2 -> Tier 1 -> Tier 5). Re-querying or re-embedding context at each tier escalation introduces latency, non-deterministic prompt drift between attempts, and multiplies prompt-token spend across the fallback chain.

To eliminate redundant token spend and ensure consistency, TriAPI implements an exactly-once retrieval design:
- **Fetch Point**: Retrieval occurs exactly once at task breakdown / dispatch preparation time, immediately prior to invoking the initial Tier 4 drafting attempt.
- **Injection Pipeline**: The retrieved context is formatted into a static markdown payload and injected alongside `build_context_blob()` (defined in `scripts/tier4_worker.py`).
- **Escalation Threading**: The resulting unified context payload is passed into `orchestrator.run_task(...)` and threaded through `tier4_run`, `tier3_escalate`, `tier2_escalate`, `tier1_escalate`, and `tier5_librarian` as an immutable parameter.
- **Immutability**: Escalation tiers consume the exact context generated at dispatch; no tier performs its own secondary retrieval pass, guaranteeing that escalation attempts evaluate against a consistent context baseline.

## 2. Local Embeddings with Graceful Fallback

Semantic search provides superior recall over simple token overlap for complex bug patterns and architectural lessons, but external embedding APIs introduce recurring API costs, external network dependencies, and content filter hazards.

- **Zero Marginal Cost Model**: Vector embeddings are generated locally using TriAPI's existing Ollama infrastructure (defaulting to `nomic-embed-text` or equivalent lightweight embedding models running on local hardware).
- **Graceful Fallback Requirement**: Ollama availability cannot be a hard dependency for task dispatch. If the local Ollama daemon is unreachable, times out, returns an error, or the configured embedding model is not pulled, the retrieval pipeline must immediately and gracefully fall back to the existing deterministic keyword-matching implementations in `scripts/hivemind_util.py` (for snippets) and `scripts/lessons.py` (for past mistakes). Under no circumstances should external paid embedding APIs be contacted.

## 3. Strict Context Sizing and Hard Ceilings

Unbounded prompt growth risks exhausting local context windows (e.g., Tier 4's strict context ceiling defined in `scripts/tier4_context.py`), degrading model reasoning, and inflating cloud tier token consumption.

To bound prompt growth, the memory injection layer enforces rigid boundaries:
- **Top-K Limit**: At most top-K=3 items are selected for inclusion into the prompt.
- **Global Character Cap**: A strict hard cap of 4,096 characters is enforced across the entire injected memory block (including section headers and formatting).
- **Enforcement Mechanism**: Ranked candidate items are accumulated in descending similarity/score order. If appending the next candidate exceeds the 4,096-character budget, the candidate is either cleanly truncated or omitted, ensuring the injected context never breaches the ceiling.

## 4. Dual On-Disk Schemas with Query-Time Unified In-Memory Index

Separate disk stores (`knowledge/hivemind.md` for XML-tagged reusable code snippets and `knowledge/lessons.jsonl` for structured post-mortem mistake records) remain physically decoupled on disk because their lifecycles, editing cadences, and schema structures are fundamentally distinct: hivemind contains human- and agent-curated code templates, whereas lessons records JSON-serialized fields capturing bug descriptions, root causes, and explicit do/don't directives. Merging these files on disk would create schema churn, break existing CLI tools and tests, and obscure git diffs. However, at retrieval time, the system conceptually unifies both sources into a single in-memory index, allowing a single semantic ranking pass to score and enforce the character cap globally across both sources.

## 5. Integration Architecture

    +--------------------------------------------------------------+
    |               Task Breakdown / Dispatch Phase                |
    +--------------------------------------------------------------+
                                   |
                                   v
    +--------------------------------------------------------------+
    |                    Memory / RAG Retrieval                    |
    |  - Query unified in-memory index (Ollama / nomic-embed-text) |
    |  - Fallback: hivemind_util.py + lessons.py keyword matching  |
    |  - Enforce top-K=3 and 4,096 character hard ceiling          |
    +--------------------------------------------------------------+
                                   |
                                   v
    +--------------------------------------------------------------+
    |   Injected alongside build_context_blob() into orchestrator  |
    +--------------------------------------------------------------+
                                   |
          +------------------------+------------------------+
          |                        |                        |
          v                        v                        v
    Tier 4 Worker           Tier 3 Debugger          Tier 2 Manager
    (Ollama/Nemotron)      (DeepSeek/Nemotron)      (DeepSeek/Gemini)
          |                        |                        |
          +------------------------+------------------------+
                                   |
                                   v
                            Tier 1 Planner
                             (Claude CLI)

## 6. Verification and Testing Strategy

- **Retrieval Invariant Tests**: Verify that `build_context_blob()` and memory retrieval execute exactly once per task execution in `scripts/orchestrator.py`.
- **Fallback Verification**: Unit tests simulating Ollama daemon timeout/failure to guarantee clean, exception-free fallback to keyword scoring.
- **Budget Compliance Tests**: Automated assertions confirming that the combined output never exceeds top-K=3 items and strictly stays under 4,096 characters.
- **Schema Compatibility Tests**: Confirm that existing parsing of `knowledge/hivemind.md` and `knowledge/lessons.jsonl` continues to pass existing test suites (`test_hivemind_util.py`, `test_lessons.py`) without file format modifications.
