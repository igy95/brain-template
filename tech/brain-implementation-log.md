---
title: "Brain — Implementation Log (Phase 1-4)"
tags: [brain, implementation, mcp, lightrag, devlog]
created: 2026-02-18
updated: 2026-02-18
summary: "Implementation record for all 4 phases of the Brain system. Documents proposal-vs-actual deltas: GPT-4o-mini replaced Claude for entity extraction, Qdrant MCP required custom development due to payload incompatibility, Slack webhook added for failure alerts."
related:
  - tech/brain-system-overview.md
  - tech/brain-architecture.md
  - tech/brain-operations.md
confidence: high
---

# Brain — Implementation Log

## Phase Completion

| Phase | Content | Status |
|---|---|---|
| Phase 1 | Foundation (folders, schema, index, _meta, CLAUDE.md) | Complete |
| Phase 2 | /brain custom skill (global symlink, auto classify/save/push) | Complete |
| Phase 3 | Ingestion pipeline (LightRAG + Qdrant + Neo4j + GitHub Actions) | Complete |
| Phase 4 | MCP server connection (Claude Code <-> knowledge search) | Complete |

## Phase 3 — Proposal vs Actual

| Item | Original proposal | Actual implementation |
|---|---|---|
| Entity extraction LLM | Anthropic API (Claude Haiku 4.5) | **OpenAI API (GPT-4o-mini)** — leveraged user's existing credits |
| Failure alerting | None | **Slack Incoming Webhook** — alerts on workflow failure |
| Monthly cost | ~$3-5 | **~$0.30-0.50** — GPT-4o-mini much cheaper |

## Phase 4 — Proposal vs Actual

| Item | Original proposal | Actual implementation |
|---|---|---|
| MCP server setup | Use existing open-source, no custom dev | Neo4j = official open-source (`mcp-neo4j-cypher`), Qdrant = **custom development** (`mcp_brain_search.py`, ~150 lines) |
| Qdrant custom reason | — | Official Qdrant MCP payload format (`{"document": ...}`) incompatible with LightRAG storage format (`{"id": ..., "workspace_id": ...}`) — cannot read data |
| LightRAG MCP Server | Top candidate | **Rejected** — requires always-on LightRAG API server, infrastructure burden |
| GraphRAG MCP Server | Hybrid candidate | **Rejected** — 5 commits only, local Docker only, no cloud support |

## MCP Server Configuration

| MCP Server | Type | Purpose | Tools |
|---|---|---|---|
| `neo4j-brain` | Official (`mcp-neo4j-cypher`) | Graph traversal (Cypher queries) | `get_neo4j_schema`, `read_neo4j_cypher`, `write_neo4j_cypher` |
| `brain-search` | Custom (`mcp_brain_search.py`) | Vector semantic search | `brain_search`, `brain_entities` |

Both registered globally (`--scope user`) — brain knowledge searchable from any project.

## Neo4j Actual Schema

- Nodes and relationships (relationship type: `DIRECTED`)
- Major entity types: concept, data, organization, method, person, event, state, content, location, product
- All nodes share `base` label, `entity_id` indexed

## GitHub Secrets Required

- `OPENAI_API_KEY` — OpenAI API key
- `QDRANT_URL` — Qdrant Cloud cluster URL
- `QDRANT_API_KEY` — Qdrant Cloud API key
- `NEO4J_URI` — Neo4j Aura connection URI
- `NEO4J_USERNAME` — typically `neo4j`
- `NEO4J_PASSWORD` — Neo4j Aura password
- `SLACK_WEBHOOK_URL` — (Optional) Slack Incoming Webhook for failure alerts

## Local Credentials (MCP Servers)

`pipeline/.env` (gitignored) — copy from `.env.example` and fill in actual values:
- `QDRANT_URL`, `QDRANT_API_KEY` — Qdrant Cloud
- `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD` — Neo4j Aura

## References

- [LightRAG — GitHub (EMNLP 2025)](https://github.com/HKUDS/LightRAG)
- [graphrag-hybrid — Neo4j/Qdrant hybrid](https://github.com/rileylemm/graphrag-hybrid)
- [Hierarchical RAG concept](https://www.emergentmind.com/topics/hierarchical-rag)
- [Agentic RAG with Knowledge Graphs (paper)](https://arxiv.org/abs/2507.16507)
- [.context — AI-optimized document structure](https://github.com/andrefigueira/.context)
- [Anthropic — Contextual Retrieval](https://www.anthropic.com/news/contextual-retrieval)
- [Qdrant + Neo4j integration guide](https://qdrant.tech/documentation/examples/graphrag-qdrant-neo4j/)
- [Claude Code Skills docs](https://code.claude.com/docs/en/skills)
- [Mem.ai — Zero Organization Overhead](https://get.mem.ai/blog/organize-your-notes-with-ai-using-collections)
