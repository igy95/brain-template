# Brain

AI-powered personal knowledge management system.

A Markdown-based personal knowledge repository. Claude Code acts as an AI assistant to navigate, add, and organize knowledge.

## Data Flow & Privacy

When you push markdown files, your content is processed by external services:

```
Your markdown files
  ├─► GitHub (private repo)         — full source files stored
  ├─► OpenAI API (GPT-4o-mini)     — full text sent for entity extraction
  ├─► Qdrant Cloud                  — embeddings + original text stored
  └─► Neo4j Aura                    — entity names, descriptions, relationships stored
```

**What this means:**
- Your document content (including full text) is sent to and stored on third-party servers
- Each service is under **your own account and API keys** — no one else has access
- OpenAI API data is not used for model training ([OpenAI policy](https://openai.com/enterprise-privacy/))
- Embeddings are generated locally (`all-MiniLM-L6-v2`) — no API call needed for this step
- **Keep this repository private.** Your brain contains personal knowledge — a public repo would expose all of it. Always create this as a private GitHub repository.

**If you store sensitive information** (company internals, trade secrets, personal data), be aware that this content will exist on external cloud infrastructure outside your direct control. This project provides a built-in sensitive content mechanism — define your criteria in `.sensitive/policy.md` and matching content will be kept local-only automatically. You can also:
- Self-host Qdrant and Neo4j via Docker for full data sovereignty (see below)
- Manually exclude files via `EXCLUDED_FILES` in `pipeline/config.py`

**Disclaimer:** This project provides tools to help manage sensitive content locally, but the responsibility for classifying and protecting sensitive information lies entirely with the user. The maintainers accept no liability for data exposure resulting from misconfiguration or user error.

<details>
<summary><strong>Self-hosting option (Docker)</strong></summary>

Replace cloud services with local instances:

```bash
# Qdrant (vector DB)
docker run -p 6333:6333 qdrant/qdrant

# Neo4j (graph DB)
docker run -p 7687:7687 -e NEO4J_AUTH=neo4j/password neo4j

# Update pipeline/.env
QDRANT_URL=http://localhost:6333
NEO4J_URI=bolt://localhost:7687
```

To also remove OpenAI dependency, replace the LLM entity extraction with a local model (e.g., Ollama). This requires modifying `pipeline/ingest.py` to use a local LLM provider.

</details>

## Prerequisites

- [Claude Code](https://claude.com/claude-code) CLI
- [uv](https://docs.astral.sh/uv/) — `curl -LsSf https://astral.sh/uv/install.sh | sh`

## Automated Setup (Claude Code Does This)

Open Claude Code in this repo and ask to set up the project. It will handle:

```bash
# Environment variable
echo 'export BRAIN_PATH=~/projects/brain' >> ~/.zshrc && source ~/.zshrc

# Skills (global symlinks)
mkdir -p ~/.claude/commands
ln -sf $BRAIN_PATH/.claude/commands/brain-update.md ~/.claude/commands/brain-update.md
ln -sf $BRAIN_PATH/.claude/commands/brain-think.md ~/.claude/commands/brain-think.md
ln -sf $BRAIN_PATH/.claude/commands/brain-implement.md ~/.claude/commands/brain-implement.md

# Python environment
uv venv pipeline/.venv --python 3.11
uv pip install --python pipeline/.venv/bin/python \
  "mcp[cli]>=1.0.0" "qdrant-client>=1.12.0" "sentence-transformers>=3.0.0" "python-dotenv>=1.0.0"

# Credentials file
cp pipeline/.env.example pipeline/.env
```

## Manual Setup (You Do This)

These steps require a browser or a regular terminal — Claude Code cannot do them for you.

### 1. Create external service accounts

Sign up and get credentials from these three services:

| Service | Sign up | What to copy |
|---|---|---|
| [Qdrant Cloud](https://cloud.qdrant.io) | Create a free cluster | Cluster URL, API Key |
| [Neo4j Aura](https://console.neo4j.io) | Create a free instance | Connection URI, Password (username is `neo4j`) |
| [OpenAI](https://platform.openai.com/api-keys) | Generate an API key | API Key |

### 2. Fill in credentials

Edit `pipeline/.env` (created in Automated Setup) and fill in the actual values:

- `QDRANT_URL` — cluster URL from [cloud.qdrant.io](https://cloud.qdrant.io)
- `QDRANT_API_KEY` — API key from [cloud.qdrant.io](https://cloud.qdrant.io)
- `NEO4J_URI` — connection URI from [console.neo4j.io](https://console.neo4j.io)
- `NEO4J_USERNAME` — typically `neo4j`
- `NEO4J_PASSWORD` — password from [console.neo4j.io](https://console.neo4j.io)

### 3. Register GitHub Secrets

Go to your GitHub repo → Settings → Secrets and variables → Actions, and add:

- `OPENAI_API_KEY` — OpenAI API key (for entity extraction)
- `QDRANT_URL` — Qdrant Cloud cluster URL
- `QDRANT_API_KEY` — Qdrant Cloud API key
- `NEO4J_URI` — Neo4j Aura connection URI
- `NEO4J_USERNAME` — typically `neo4j`
- `NEO4J_PASSWORD` — Neo4j Aura password
- `SLACK_WEBHOOK_URL` — (Optional) Slack webhook for failure alerts

### 4. Define sensitive content policy

Open `.sensitive/policy.md` and replace the examples with your own criteria. Content matching these topics will be saved locally only — never pushed to git or ingested into cloud services.

If you don't store sensitive information, you can skip this step.

### 5. Register MCP servers

Run in a **regular terminal** (not inside Claude Code):

```bash
cd ~/projects/brain && source pipeline/.env

# Neo4j (graph search)
claude mcp add-json neo4j-brain "{
  \"type\":\"stdio\",
  \"command\":\"uvx\",
  \"args\":[\"mcp-neo4j-cypher\"],
  \"env\":{
    \"NEO4J_URI\":\"$NEO4J_URI\",
    \"NEO4J_USERNAME\":\"$NEO4J_USERNAME\",
    \"NEO4J_PASSWORD\":\"$NEO4J_PASSWORD\",
    \"NEO4J_DATABASE\":\"neo4j\"
  }
}" --scope user

# Qdrant (vector search)
claude mcp add-json brain-search "{
  \"type\":\"stdio\",
  \"command\":\"$(pwd)/pipeline/.venv/bin/python\",
  \"args\":[\"$(pwd)/pipeline/mcp_brain_search.py\"],
  \"env\":{
    \"QDRANT_URL\":\"$QDRANT_URL\",
    \"QDRANT_API_KEY\":\"$QDRANT_API_KEY\"
  }
}" --scope user
```

## Verification

After completing all steps above, open Claude Code and verify:

1. **MCP servers loaded** — On startup, Claude Code should show both `neo4j-brain` and `brain-search` as connected MCP servers.
2. **Vector search works** — Ask: `"Search my brain for React"`. The `brain_search` tool should return document chunks with scores and file paths.
3. **Graph search works** — Ask: `"What entities are in my knowledge graph?"`. The `brain_entities` tool or a Cypher query via `read_neo4j_cypher` should return results.
4. **Skill works** — Type `/brain-update test note` and confirm it creates a markdown file in the repo.

If all four checks pass, setup is complete.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| MCP server not listed on startup | Registration failed or ran inside Claude Code | Re-run `claude mcp add-json` commands in a **regular terminal** (not Claude Code) |
| `brain_search` returns empty or errors | Qdrant credentials wrong or cluster paused | Verify `QDRANT_URL` and `QDRANT_API_KEY` in `pipeline/.env`; check cluster status at [cloud.qdrant.io](https://cloud.qdrant.io) |
| `read_neo4j_cypher` fails | Neo4j credentials wrong or instance paused | Verify `NEO4J_URI` and `NEO4J_PASSWORD` in `pipeline/.env`; Neo4j Aura Free pauses after 3 days of inactivity — resume at [console.neo4j.io](https://console.neo4j.io) |
| `sentence-transformers` import error | Python venv not set up or packages missing | Re-run the `uv venv` and `uv pip install` commands from the Automated Setup section |
| `/brain-update` or `/brain-think` not found | Symlink missing | Run the symlink commands from the Automated Setup section |
| `BRAIN_PATH` not set | Shell config not sourced | Run `source ~/.zshrc` or open a new terminal |

## Usage

Open Claude Code from any directory. Both MCP servers activate automatically.

**Add knowledge:**
```
/brain-update RSC renders on server and streams to client
```

The `/brain-update` skill handles classification, file creation, metadata update, and git push. If you've defined a sensitive content policy, matching content is automatically saved to `.sensitive/` (local-only) instead.

**Think with your brain:**
```
/brain-think https://example.com/article-about-ai
/brain-think I think the value of expertise is declining
```

The `/brain-think` skill searches the brain broadly and responds as a thinking partner grounded in accumulated knowledge.

**Implement autonomously:**
```
/brain-implement https://github.com/your-org/repo/issues/123
/brain-implement Add unread message badge to chat list
```

The `/brain-implement` skill follows the full implementation workflow: task understanding, knowledge loading, codebase analysis, implementation, verification, commit & PR, and self-review.

**Retrieve knowledge:**
```
"Summarize what I wrote about React recently"
```

## Customizing Your Brain

### Adding categories

1. Create a new folder (e.g., `finance/`)
2. Add a `_meta.md` file following the pattern of existing folders
3. Add the category to `index.md`

### Folder structure

Categories grow organically. Start with the defaults and split when folders get crowded (15+ files with shared tags → create subfolder). See `schema.md` for detailed rules.

### Language

| Scope | Language |
|---|---|
| Frontmatter, factual content | English |
| Subjective content (journal, life) | Your language |
| AI responses | Matches your language |

## Architecture

```
brain/
├── CLAUDE.md         # AI instructions
├── index.md          # Category map (lists all folders)
├── schema.md         # Schema & rules
├── .sensitive/       # Local-only sensitive content (gitignored)
│   └── policy.md     # User-defined sensitivity criteria (tracked)
├── inbox/            # Uncategorized — auto-classified weekly
├── <category>/       # Topic folders (tech/, business/, life/, journal/, ...)
│   └── _meta.md      # Domain summary and subtopic list
└── pipeline/         # Ingestion & MCP server
```

See `tech/brain-architecture.md` for the full system design.
