---
title: "Brain — Operations (Cost, Security, Risk)"
tags: [brain, operations, cost, security, risk-management]
created: 2026-02-18
updated: 2026-02-18
summary: "Operational details for the Brain system: build scope (custom vs open-source), monthly cost ~$0.30-0.50, security design with cloud-to-local migration path, and 6 identified risks with mitigations."
related:
  - tech/brain-system-overview.md
  - tech/brain-architecture.md
  - tech/brain-implementation-log.md
confidence: high
---

# Brain — Operations

## Build Scope

| Component | Approach | Notes |
|---|---|---|
| Search engine | Open-source (LightRAG) | No custom development needed |
| Infrastructure (2 DBs) | Cloud free tiers | No Docker needed |
| Ingestion pipeline | Custom (Python) | Markdown parsing -> LightRAG |
| MCP servers | Neo4j official + custom Qdrant | Neo4j=open-source, Qdrant=custom ~150 lines (official MCP payload incompatible) |
| `/brain` custom skill | Custom | Knowledge input automation (1 skill file, global symlink) |
| Inbox auto-classification | Custom | GitHub Actions cron (weekly) |
| Folder structure / schema | Custom design | AI navigation optimized |

Core engines use proven open-source; only the personalization layer is custom-built.

## Monthly Cost

| Item | Cost | Notes |
|---|---|---|
| GitHub Private Repo | Free | |
| Qdrant Cloud | Free | Free tier (1GB) |
| Neo4j Aura | Free | Free tier |
| Embeddings | Free | sentence-transformers, runs in GitHub Actions |
| OpenAI API (entity extraction) | ~$0.30-0.50 | GPT-4o-mini, only personal payment item |
| Conversation | Team plan | Claude Code |
| **Personal total** | **~$0.30-0.50/month** | |

## Security Design

Current stage prioritizes convenience.

| Processing stage | Location | Notes |
|---|---|---|
| Document storage | GitHub Private Repo | Private |
| Embedding generation | Local in GitHub Actions | No external transmission |
| Entity extraction | OpenAI API | API data not used for training (policy) |
| Vector/graph storage | Qdrant Cloud / Neo4j Aura | Cloud-managed |
| Conversation | Claude Code (team plan) | Only retrieved knowledge fragments sent |

### Migration Path (if security sensitivity increases)

```
Current (full cloud)
    | if needed
Embeddings: Already local (no change needed)
Entity extraction: OpenAI API -> Ollama local
DB: Cloud -> Docker local
    | if further needed
Conversation LLM: Claude API -> local LLM
```

Data source is markdown, so re-running ingestion handles migration. Architecture unchanged — only backends swap.

## Risk Assessment

| Risk | Impact | Mitigation |
|---|---|---|
| Cloud free tier limit exceeded | Low | 1GB / tens of thousands of docs — plenty of room. Upgrade to paid or migrate local |
| GitHub Actions free limit | Low | Private repo: 2,000 min/month. At 5-10 min/run, 200-400 runs possible. Sufficient for personal use |
| LightRAG project discontinued | Medium | DBs operate independently, only engine needs replacement |
| API service outage | Low | Source preserved on GitHub, temporary inconvenience |
| Mac hardware failure | Low | Source on GitHub, vector/graph on cloud — no impact |
| Neo4j Aura Free pause | Medium | Instance pauses after 3 days of inactivity. Need periodic queries or keep-alive cron |
