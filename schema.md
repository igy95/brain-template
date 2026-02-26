# Schema & AI Navigation Rules

This document defines writing rules for all documents in the Brain and the AI navigation protocol.

## Frontmatter Schema

All knowledge documents (`.md`) must include the following YAML frontmatter:

```yaml
---
title: "Document title"
tags: [tag1, tag2]
created: 2026-02-17
updated: 2026-02-17
summary: "1-2 sentence summary. AI references this before reading the body."
related:
  - path/to/related-doc.md
confidence: high  # high | medium | low | outdated
---
```

### Field Definitions

| Field | Required | Description |
|---|---|---|
| `title` | Y | Document title (English) |
| `tags` | Y | Classification tag list (English, lowercase, 3-7 tags) |
| `created` | Y | Creation date (ISO 8601) |
| `updated` | Y | Last modified date (ISO 8601) |
| `summary` | Y | 1-2 sentence summary (English). Core of AI navigation |
| `related` | N | List of related document paths |
| `confidence` | Y | Information reliability. `high`=verified, `medium`=mostly accurate, `low`=unverified, `outdated`=needs update |

## Language Rules

| Scope | Language | Rationale |
|---|---|---|
| Frontmatter (title, tags, summary) | English | Search consistency, token efficiency |
| Factual content body (tech, business) | English | Token efficiency (~30-50% savings vs Korean), global readability |
| Subjective content body (journal, life) | Author's native language | Preserve nuance and reduce capture friction |
| AI responses when retrieving knowledge | Match user's language | Natural interaction |

## Document Size Rules

A single document should cover **one focused topic**. When a document grows beyond a manageable scope, split it.

### When to split
- Document exceeds **200 lines** and covers multiple distinct subtopics
- The `summary` field can no longer capture the document's scope in 1-2 sentences
- The document contains **3+ major sections** that could each stand alone

### How to split
1. Create a **hub document** (overview + links to subtopic files)
2. Extract each subtopic into its own file with proper frontmatter
3. Connect all files via `related` fields (bidirectional)
4. Hub document's `summary` describes the overall theme; subtopic summaries describe specifics

### Hub document pattern
```
<topic>-overview.md          ← hub (summary + links)
<topic>-subtopic-a.md        ← detail
<topic>-subtopic-b.md        ← detail
```

## Folder Density Rules

- If a folder has **15+ files** (excluding `_meta.md`) and 5+ share a common tag → create a subfolder
- New subfolder gets its own `_meta.md`, parent `_meta.md` and `index.md` are updated
- **Maximum folder depth: 3 levels** (e.g., `tech/frontend/react/`). Never create a 4th level.
- At depth 3, use filename prefixes instead of subfolders (e.g., `react-hooks-use-effect.md`)
- Keeps folders navigable for both humans and AI

## AI Navigation Protocol

### Navigation order
1. **`index.md`** — Understand overall categories
2. **`_meta.md`** — Topic list and summary for the domain
3. **frontmatter `summary`** — Understand document content without reading body
4. **Body** — Read full text only when needed

### Search strategy
- Match user query keywords to `tags` → check `summary` → read body if relevant
- Follow `related` fields to explore connected documents
- Flag `confidence: outdated` documents to user as needing update

## File Naming Rules

- Filenames: kebab-case (`my-document-title.md`)
- Folder names: lowercase (`tech/backend/`)
- Date-based documents: `YYYY-MM-DD-title.md` (journal, etc.)
- `_meta.md`: One per folder, serves as table of contents

## Document Lifecycle

1. **Capture** → Save quickly to `inbox/`
2. **Organize** → Move to appropriate category folder, write frontmatter
3. **Connect** → Link related documents via `related` field
4. **Review** → Periodically update `confidence`
