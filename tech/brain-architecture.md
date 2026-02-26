---
title: "Brain — Architecture & Design Decisions"
tags: [brain, architecture, lightrag, qdrant, neo4j, vector-db, knowledge-graph]
created: 2026-02-18
updated: 2026-02-18
summary: "Why the Brain was built, core requirements, 4 architecture alternatives evaluated (markdown-only, vector-only, hybrid-local, hybrid-cloud), and the chosen full-cloud hybrid architecture using LightRAG + Qdrant + Neo4j."
related:
  - tech/brain-system-overview.md
  - tech/brain-operations.md
  - tech/brain-implementation-log.md
confidence: high
---

# Brain — Architecture & Design Decisions

## Background & Purpose

The system accumulates personal knowledge and enables AI conversations grounded in that knowledge. Unlike general LLMs that answer from world knowledge, this system answers from the user's own recorded knowledge — citing file paths and connecting related ideas across domains.

| Aspect | General LLM | Brain AI |
|---|---|---|
| Answer basis | World knowledge | User's recorded knowledge and thoughts |
| Sourcing | None | File paths cited |
| Personalization | Impossible | Reflects thought patterns and interest changes |

## Core Requirements

| Item | Description |
|---|---|
| Storage targets | Personal thoughts, technical knowledge, business ideas — all domains |
| Data scale | Hundreds initially, growing to tens of thousands over years |
| Search method | Semantic search + knowledge relationship traversal simultaneously |
| Input method | Minimize decision cost. Natural language in, AI classifies/organizes/saves |
| Priority | Convenience and speed first; security escalated as sensitivity grows |
| Operational burden | Solo operation, minimize maintenance |

## Alternatives Evaluated

| Option | Description | Verdict |
|---|---|---|
| A. Markdown only | GitHub storage, AI reads directly | X — Cannot scale beyond hundreds of documents |
| B. Vector DB only | Semantic search only | X — Cannot traverse knowledge relationships |
| C. Hybrid (local) | Vector + graph, local Docker | X — Infrastructure management burden |
| **D. Hybrid (full cloud)** | Vector + graph, all infrastructure on cloud | **Adopted** |

## Chosen Architecture

```
GitHub Private Repo (knowledge source, markdown)
    | push triggers (GitHub Actions)
LightRAG Ingestion Pipeline
    |-- sentence-transformers -> embeddings (free, runs in Actions)
    |-- OpenAI API (GPT-4o-mini) -> entity/relationship extraction
    |-- Qdrant Cloud -> vector storage
    +-- Neo4j Aura -> knowledge graph storage
    |
Claude Code (terminal conversation, team plan)
```

Local installation: Claude Code + MCP servers (lightweight processes auto-launched by Claude Code). All DB infrastructure is cloud-hosted.

## Technology Stack

| Component | Selection | Rationale |
|---|---|---|
| RAG engine | LightRAG | Vector+graph unified, EMNLP 2025 validated, lightweight |
| Vector DB | Qdrant Cloud (free tier) | 1GB free, zero management |
| Graph DB | Neo4j Aura (free tier) | Industry standard, free tier, zero management |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) | Free, no API needed, runs in GitHub Actions |
| Entity extraction | OpenAI API (GPT-4o-mini) | Quality extraction, automation pipeline |
| MCP servers | Neo4j official + custom Qdrant | See implementation log for evaluation details |
| Conversation interface | Claude Code (terminal) | Team plan, easy to swap later |

## Why Vector + Graph

| Approach | Behavior | Result |
|---|---|---|
| Vector only | Keyword similarity search | Lists individual documents |
| **Vector + graph** | Graph path traversal from "interest" entity to "career" entity | Discovers connections between knowledge |

Building an "AI that understands me" requires relationship awareness, which is impossible without a Knowledge Graph.

## MCP Server Candidates (Original Proposal)

| MCP Server | Purpose |
|---|---|
| Daniel LightRAG MCP Server | LightRAG integration (22 tools) |
| Qdrant Official MCP Server | Direct Qdrant vector search |
| Neo4j Official MCP Server | Direct Neo4j graph traversal |
| GraphRAG MCP Server | Neo4j + Qdrant hybrid search |

Final MCP server evaluation and selection are documented in the implementation log.
