# Brain Index

Top-level map of the Brain. AI reads this file first when navigating.

## Categories

| Folder | Description |
|---|---|
| `inbox/` | Uncategorized memos, quick captures. Temporary storage before organization |
| `tech/` | Technology knowledge |
| `tech/backend/` | Server, API, DB, infrastructure |
| `tech/frontend/` | UI, React, browser, CSS |
| `business/` | Business ideas, market analysis, strategy |
| `life/` | Health, habits, self-improvement, relationships |
| `journal/` | Diary, retrospectives, monthly records |

## Navigation Rules

1. Read each folder's `_meta.md` for domain summary and subtopic list.
2. Use frontmatter `summary` field to understand a document without reading the body.
3. Navigation order: `index.md` → `_meta.md` → frontmatter summary → body

## Stats

- Total documents: 5
