---
description: "Brain knowledge manager. Classifies and saves knowledge, thoughts, and notes to the brain repo."
argument-hint: "<knowledge or thought to save>"
allowed-tools: Read, Write, Edit, Bash(git *), Grep, Glob
---

# Brain — Knowledge Manager

Analyze user input and save it to the Brain repository.
Follow the workflow below in order. A pre-commit checklist gate must pass before committing.

## Input

$ARGUMENTS

---

## Step 1: Read Brain Structure

Read these two files to understand the current brain state:

1. `$BRAIN_PATH/schema.md` — frontmatter rules, file writing rules
2. `$BRAIN_PATH/index.md` — category structure, overall map

If `$BRAIN_PATH` is not set, use `~/projects/brain`.

> Do NOT read _meta.md yet. Only read the relevant folder's _meta.md after category is determined in Step 2.

---

## Step 2: Classify Input

### A. Intent Classification

| Intent | Criteria |
|---|---|
| **New note** | New knowledge, thought, or information |
| **Update existing** | Contains phrases like "추가해줘", "업데이트", "수정", "add to", "update", "modify", "previously wrote" |
| **Ambiguous** | Cannot determine → ask the user |

### B. Content Type Classification

| Type | Description | Example |
|---|---|---|
| **Factual** | Technical knowledge, definitions, facts | "RSC renders on server and streams to client" |
| **Subjective** | Personal thoughts, feelings, opinions | "I'm getting more interested in developer tools business" |
| **Mixed** | Both factual and subjective | Verify factual parts only, save everything |

### C. Category Classification

| Category | Criteria |
|---|---|
| `tech/frontend/` | UI, React, CSS, browser, UX, frontend frameworks |
| `tech/backend/` | Server, API, DB, infrastructure, DevOps |
| `tech/` | General tech that doesn't fit frontend or backend |
| `business/` | Business ideas, market analysis, strategy, revenue, marketing, work methodology, leadership, professional skills |
| `life/` | Health, habits, personal growth (non-work), relationships, hobbies |
| `journal/YYYY-MM/` | Time-based personal records, diary, retrospectives |
| `inbox/` | Cannot confidently classify into any above |

**Classification rules:**
- Subjective opinions about a technical topic (e.g., "React is great") go to the tech category, NOT journal.
- Journal is exclusively for time-based personal reflections.
- If a needed category doesn't exist, create a new folder (handled in Step 6).
- Low confidence → save to `inbox/`.

### D. Subfolder Classification

After determining the top-level category, check if the target folder has subfolders:

1. Read the target folder's `_meta.md` → check `## Subfolders` section
2. If subfolders exist → determine if content belongs to a specific subfolder based on its description
3. **If match is clear** → classify directly to the subfolder
4. **If ambiguous** → ask the user which subfolder it belongs to, or whether it's general (stays at parent level)
5. Repeat recursively if the subfolder itself has subfolders (up to max depth 3)

This ensures organization-specific or project-specific knowledge is correctly scoped without the user needing to specify context manually.

**Cross-category handling — when content spans multiple categories:**
1. Does the content touch multiple categories?
2. If yes → can each part **stand alone meaningfully** when split?
   - **Yes** → split into separate files, classify each into its natural category
   - **No** (the cross-domain connection IS the point) → keep as one document, apply tiebreaker below
3. **Tiebreaker** (single document, genuinely cross-domain):
   - Classify by **primary application context**, use tags for secondary aspects.
   - Work/organizational context → `business/`
   - Personal/non-work context → `life/`
   - Technical skill applied at work → `tech/`
   - **Fallback**: tiebreaker로도 판정 불가 → `inbox/`

---

## Step 2.5: Sensitivity Check

1. Read `$BRAIN_PATH/.sensitive/policy.md`
2. If the file has no user-defined topics (only examples with `(example)` prefix), **skip this step**
3. Compare the classified content against the sensitive topics listed in the policy
4. Classify sensitivity:

| Judgment | Action |
|---|---|
| **Clearly sensitive** | Set `SENSITIVE=true`, change target path to `$BRAIN_PATH/.sensitive/<category>/<filename>.md` |
| **Clearly not sensitive** | Set `SENSITIVE=false`, proceed normally |
| **Ambiguous** | **Ask the user** before proceeding — explain which policy topic it partially matches and let them decide |

5. If the user confirms sensitive → `SENSITIVE=true`; if not → `SENSITIVE=false`

> When content is marked sensitive, it will be saved locally only — not pushed to git, not ingested into cloud services.

---

## Step 3: Verify (Factual Content Only)

**Skip this step entirely for subjective content.**

For factual claims:

1. **Cross-check**: Compare with Claude's training data for accuracy
2. **Check contradictions with existing notes**: Grep `$BRAIN_PATH` for related keywords. Flag if existing notes contradict.
3. **Assign confidence**:

| Confidence | Condition | Action |
|---|---|---|
| `high` | Verified accurate, no contradictions | Save directly |
| `medium` | Partially accurate or some parts unverifiable | Save + inform which parts differ |
| `low` | Likely incorrect | Save + clearly warn the user |

### Critical rule: NEVER block saving

Always save, even if incorrect. The user chose to save by invoking `/brain`.
Your role is to inform, not to block.

Verification report examples:
- "RSC description is accurate. Saving with confidence: high."
- "'React is a backend framework' is inaccurate. React is a frontend UI library. Saving with confidence: low, adding correction note."

---

## Step 4: Find or Create File

### When updating an existing note
1. Grep `$BRAIN_PATH` for topic-related keywords
2. Check relevant `_meta.md` for matching titles
3. If found → read it, proceed to Step 5 (update)
4. If not found → inform user, create as new note

### When creating a new note
1. Read target folder's `_meta.md` (if `SENSITIVE=true`, skip — `.sensitive/` has no `_meta.md`)
2. Generate filename (kebab-case):
   - "RSC renders on server..." → `react-server-components.md`
   - "Developer tools business..." → `developer-tools-business-interest.md`
   - Journal entries: `YYYY-MM-DD-title.md` (e.g., `2026-02-17-weekly-review.md`)
3. Glob for existing similar filenames (search both `$BRAIN_PATH/` and `$BRAIN_PATH/.sensitive/` to avoid duplicates)
   - If exists → ask user: update existing vs create separate
4. File path:
   - **If `SENSITIVE=false`**: `$BRAIN_PATH/<category>/<filename>.md`
   - **If `SENSITIVE=true`**: `$BRAIN_PATH/.sensitive/<category>/<filename>.md`

---

## Step 5: Write Content

### Language rules

| Scope | Language |
|---|---|
| Frontmatter (title, tags, summary) | **English always** |
| Factual content body (tech, business) | **English** |
| Subjective content body (journal, life) | **Author's input language** |
| AI response to user | **Match user's language** |

### Frontmatter generation

Generate YAML frontmatter per `schema.md` rules:

```yaml
---
title: "<English descriptive title>"
tags: [<3-7 tags, English, lowercase>]
created: <YYYY-MM-DD>
updated: <YYYY-MM-DD>
summary: "<1-2 sentence English summary for AI navigation>"
related:
  - <path/to/related-note.md>
confidence: <high|medium|low>
---
```

**Tag rules:**
- English, lowercase only
- Mix specific + broad tags (e.g., react-server-components + react + frontend)
- **Strictly 3-7 tags. Never exceed 7.**

**Summary rules:**
- Must be self-contained — understandable without reading the body
- Include likely search keywords

**Related notes:**
- Grep for notes with overlapping tags/keywords
- Maximum 5 connections
- Use relative paths (e.g., `tech/frontend/react-hooks.md`)
- Add reverse links to connected notes' `related` fields (bidirectional)
- **If `SENSITIVE=true`**: Do NOT add reverse links to non-sensitive files (this would expose `.sensitive/` paths in pushed files). Only add forward links from the sensitive file.

### Document size check

**If the input is large or covers multiple topics, split into separate files:**

- Single document exceeding **200 lines** or containing **3+ independent topics** → split
- Create a **hub document** (`<topic>-overview.md`): overall summary + links to subtopic files
- Create **subtopic documents** (`<topic>-subtopic.md`): individual topic details
- Connect all files via `related` fields (bidirectional)

### Folder density check

**Before saving, count files in the target folder (excluding `_meta.md`):**

- If the folder already has **15+ files** and 5+ share a common tag → create a subfolder for that group
- Move the related files into the new subfolder, create its `_meta.md`, update parent `_meta.md` and `index.md`
- **Maximum folder depth: 3 levels** (e.g., `tech/frontend/react/`). Never create a 4th level.
- At depth 3, use filename prefixes instead (e.g., `react-hooks-use-effect.md`)

### Body content

- **Factual content**: Write in English. Structure with subheadings. Expand without distorting.
- **Subjective content**: Preserve the user's tone and language. Minimal restructuring.
- **Journal entries**: Date-based, personal/reflective tone, user's native language.
- **URLs/links**: Always preserve URLs from user input (Figma, Linear, Notion, GitHub, etc.). Place in a `## References` section or inline where contextually appropriate. Never strip links.
- If confidence is not high, add a blockquote verification note:
  ```
  > **Note**: [explanation of potentially inaccurate parts]
  ```

### Updating existing notes

- Use Edit tool to modify existing file
- Update `updated` date in frontmatter
- **Preserve existing content**, add new content at appropriate location
- Update `tags` (add new tags, keep total ≤ 7)
- Update `summary` if scope significantly changed
- If update pushes document over 200 lines → consider splitting

---

## Step 6: Update Metadata

**If `SENSITIVE=true`:** Skip this step entirely. Sensitive files must not appear in `_meta.md` or `index.md` since those files are pushed to git.

**If `SENSITIVE=false`:**

### Update _meta.md

Read and update the folder's `_meta.md`:

1. Add entry under `## Topics`:
   ```
   - [<title>](<filename>.md) — <summary>
   ```
2. If `_아직 문서가 없습니다._` exists, replace it with the new entry
3. Update `updated` date in frontmatter

### Create new folder (if category doesn't exist)

1. Create the folder
2. Create `_meta.md` following existing patterns
3. Add subfolder entry in parent folder's `_meta.md`
4. Add new category to `index.md` Categories table

### Update index.md

- Increment `Total documents` in `## Stats`
- Update `Last updated` date
- Update Categories table if new category was added

---

## Pre-commit Checklist (Gate)

**Before committing, verify every item. If any item is unchecked, go back and complete it.**

- [ ] **Step 1**: schema.md + index.md read
- [ ] **Step 2**: Classification complete (intent / content type / category / cross-category split-or-tiebreaker applied)
- [ ] **Step 3**: Verification handled (factual/mixed → cross-check + contradiction grep + report written, subjective → explicitly skipped)
- [ ] **Step 4**: Similar file check (grep content + glob filenames)
- [ ] **Step 2.5**: Sensitivity check (policy.md read → sensitive/not-sensitive determined)
- [ ] **Step 5 size**: Document size check (200+ lines or 3+ topics → split)
- [ ] **Step 5 density**: Folder density check (count files in target folder, 15+ with 5+ common tag → subfolder)
- [ ] **Step 6**: Metadata updated (if not sensitive: _meta.md entry + index.md stats + reverse links on related notes)

---

## Step 7: Git Commit & Push

**If `SENSITIVE=true`:** Skip this step entirely. The file is already saved locally in `.sensitive/` and must not be pushed.

**If `SENSITIVE=false`:** Execute from `$BRAIN_PATH`:

```bash
git -C $BRAIN_PATH add <explicitly list modified files>
git -C $BRAIN_PATH commit -m "<type>(<category>): <brief description>"
git -C $BRAIN_PATH push
```

**Commit message format:**
- `add(tech/frontend): React Server Components overview`
- `update(tech/backend): add PostgreSQL MVCC details`
- `add(inbox): unclassified memo`
- `add(journal): 2026-02-17 weekly review`

**Type rules:**
- `add` — new note
- `update` — modify existing note
- `move` — relocate note
- `fix` — correct information

**Important:**
- Use explicit file paths, NOT `git add -A`
- If push fails: report local save success first, then note push failure separately

---

## Step 8: Report Results

After completing all steps, summarize for the user:

```
Brain saved

File: <category>/<filename>.md
Category: <category>
Tags: <tag1>, <tag2>, ...
Confidence: <confidence>
Related: <related note titles, or "none">
Storage: <local-only (sensitive) | synced>

(if verification performed)
Verification: <brief summary>

(if issues)
Warning: <what to check>
```

- **Match the user's input language for the report** (Korean input → Korean report)
- Be concise. Only the essentials.
