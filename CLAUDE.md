# Brain — AI-Powered Knowledge Assistant

Personal knowledge management system. Claude Code must read this file first when working in this repo.

## Project Overview

This repository is a Brain that structures and stores personal knowledge, ideas, and records so that AI can navigate and manage them.

## Key Files

- `index.md` — Category map. Starting point for navigation
- `schema.md` — Frontmatter schema, AI navigation rules, file writing rules
- `_meta.md` in each folder — Domain summary and subtopic list

## Rules

### When writing documents
1. **Read `schema.md` first** and follow frontmatter rules
2. Filenames in kebab-case (`my-topic.md`)
3. After creating a new document, add an entry to the folder's `_meta.md`
4. Link related documents via `related` field bidirectionally
5. If a document exceeds 200 lines or covers 3+ independent topics, split into hub + subtopic files

### Language rules
- Frontmatter (title, tags, summary): **English always**
- Factual content body (tech, business): **English**
- Subjective content body (journal, life): **Author's input language**
- AI responses: **Match user's language**

### When navigating
1. `index.md` for overall structure
2. Target folder's `_meta.md` for topic list
3. Frontmatter `summary` for content preview
4. Full body only when necessary

### When moving/organizing documents
1. Move `inbox/` documents to appropriate categories
2. Update `_meta.md` in both source and target folders
3. Update `index.md` Stats section

## Folder Structure

```
brain/
├── index.md          # Category map
├── schema.md         # Schema & rules
├── .claude/commands/ # Custom skills (/brain)
├── pipeline/         # Ingestion pipeline (Python)
│   ├── config.py     # Environment & constants
│   ├── ingest.py     # LightRAG ingestion script
│   ├── classify_inbox.py  # Inbox auto-classification
│   └── requirements.txt
├── .github/workflows/
│   ├── ingest.yml         # Auto-ingest on push
│   └── inbox-classify.yml # Weekly inbox classification
├── inbox/            # Uncategorized memos
├── tech/             # Technology
│   ├── backend/      # Server, API, DB
│   └── frontend/     # UI, React, CSS
├── business/         # Business, strategy
├── life/             # Health, habits
└── journal/          # Diary, retrospectives
```

## Ingestion Pipeline (Phase 3)

On every push to main that changes `.md` files, GitHub Actions automatically:
1. Detects changed/deleted markdown files via git diff
2. Parses frontmatter + body from each file
3. Generates embeddings (sentence-transformers, all-MiniLM-L6-v2)
4. Extracts entities/relationships (OpenAI GPT-4o-mini)
5. Stores vectors in Qdrant Cloud, knowledge graph in Neo4j Aura

Weekly cron job classifies `inbox/` files into appropriate categories.

### External Services

| Service | Purpose | Tier |
|---------|---------|------|
| Qdrant Cloud | Vector DB (semantic search) | Free (1GB) |
| Neo4j Aura | Graph DB (knowledge graph) | Free |
| OpenAI API | Entity extraction (GPT-4o-mini) | ~$0.30-0.50/mo |

Credentials stored in GitHub Secrets (not in repo).

### Pipeline files

- `pipeline/config.py` — Loads env vars, defines constants
- `pipeline/ingest.py` — Main ingestion via LightRAG (Qdrant + Neo4j)
- `pipeline/postprocess.py` — Post-ingestion Neo4j quality processing (dedup, orphan cleanup, SEP trim)
- `pipeline/classify_inbox.py` — Classifies inbox files into categories
- `.github/workflows/ingest.yml` — Triggers on .md file push (with concurrency control + post-processing)
- `.github/workflows/inbox-classify.yml` — Weekly cron + manual trigger

## Knowledge Retrieval (Phase 4 — MCP Integration)

Two MCP servers provide knowledge search from any project directory.

### MCP Tools

#### brain-search (Custom — Qdrant vector search)
- **`brain_search(query, top_k=5)`** — Semantic search over document chunks. Returns content, source file path, and similarity score.
- **`brain_entities(query, top_k=10)`** — Search entities (concepts, people, products) in the knowledge graph. Returns entity names, descriptions, and source documents.

#### neo4j-brain (Official — Neo4j Cypher)
- **`get_neo4j_schema`** — Retrieve graph structure (node labels, relationship types, properties).
- **`read_neo4j_cypher`** — Execute read Cypher queries against the knowledge graph.
- **`write_neo4j_cypher`** — Execute write Cypher queries.

### Neo4j Graph Schema (LightRAG-generated)

- **Primary node label**: `base` (`entity_id` is indexed)
- **Entity-type labels**: `concept`, `person`, `method`, `organization`, `content`, `data`, `event`, `location`, `team`, `artifact`, `metric`, etc.
- **Node properties**: `entity_id` (indexed), `entity_type`, `description`, `source_id`, `file_path`, `created_at`
- **Relationship type**: `DIRECTED` (single type for all relationships)
- **Edge properties**: `weight`, `description`, `keywords`, `source_id`, `file_path`, `created_at`

### Qdrant Collections

| Collection | Content | Key payload fields |
|---|---|---|
| `lightrag_vdb_chunks_all_minilm_l6_v2_384d` | Document chunks | `content`, `full_doc_id`, `file_path` |
| `lightrag_vdb_entities_all_minilm_l6_v2_384d` | Entity embeddings | `entity_name`, `content`, `source_id`, `file_path` |
| `lightrag_vdb_relationships_all_minilm_l6_v2_384d` | Relationship embeddings | `src_id`, `tgt_id`, `content`, `source_id`, `file_path` |

### Search Strategy

When answering knowledge questions, use this order:

1. **Semantic search first** (`brain_search`): Find relevant document chunks by meaning
2. **Entity exploration** (`brain_entities`): Discover related concepts and entities
3. **Graph traversal** (`read_neo4j_cypher`): Explore entity relationships via Cypher
   ```cypher
   -- Find entities by keyword (use base label for indexed entity_id)
   MATCH (n:base) WHERE n.entity_id CONTAINS 'keyword' RETURN n.entity_id, n.entity_type, n.description LIMIT 10

   -- Find relationships for an entity
   MATCH (a:base)-[r:DIRECTED]-(b:base) WHERE a.entity_id CONTAINS 'keyword'
   RETURN a.entity_id, b.entity_id, r.description, r.keywords LIMIT 20

   -- Connected subgraph (2 hops)
   MATCH path = (a:base)-[:DIRECTED*1..2]-(b:base) WHERE a.entity_id = 'EXACT_NAME'
   RETURN [n IN nodes(path) | n.entity_id] AS entities LIMIT 30

   -- List all entities by type
   MATCH (n:base) WHERE n.entity_type = 'person' RETURN n.entity_id, n.description LIMIT 20
   ```
4. **Read source files** if full document context is needed (use file paths from search results)
5. **Always cite sources**: Include file paths in responses (e.g., `tech/brain-architecture.md`)

### MCP Server Files

- `pipeline/mcp_brain_search.py` — Custom Qdrant MCP server (brain_search, brain_entities)
- `pipeline/.env` — Local credentials (gitignored)
- `pipeline/.env.example` — Credential template

For installation and MCP server setup, see `README.md`.

## Environment

- `$BRAIN_PATH` — Local path to this repo (`~/projects/brain`)
- `.lightrag_data/` — LightRAG working directory (cached in GitHub Actions, gitignored)
