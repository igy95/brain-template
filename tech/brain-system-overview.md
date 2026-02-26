---
title: "Brain AI Assistant System — Design Proposal"
tags: [brain, rag, knowledge-management, architecture, lightrag]
created: 2026-02-18
updated: 2026-02-18
summary: "Hub document for the Brain system proposal. Covers why it was built, architecture decisions, operational details, and implementation log across 4 phases."
related:
  - tech/brain-architecture.md
  - tech/brain-operations.md
  - tech/brain-implementation-log.md
confidence: high
---

# Brain AI Assistant System — Design Proposal

This is the hub document for the Brain system's original design proposal and implementation record. The system accumulates personal knowledge, thoughts, and experiences, then enables AI-assisted conversations grounded in that knowledge — not general world knowledge, but the user's own knowledge.

Key differentiator: A general LLM answers from "the world's knowledge"; the Brain AI answers from "my knowledge", citing specific file paths.

## Subtopic Documents

- **[Architecture & Design Decisions](brain-architecture.md)** — Background, requirements, alternatives evaluation (4 options), chosen hybrid architecture (vector + graph, full cloud), technology stack with selection rationale
- **[Operations](brain-operations.md)** — Build scope (what's custom vs open-source), monthly cost breakdown, security design with migration path, risk assessment
- **[Implementation Log](brain-implementation-log.md)** — Phase 1-4 completion status, proposal-vs-actual deltas, MCP server evaluation results, current data stats, external service status, reference links
