---
description: "Autonomous implementation agent. From task input to PR submission following brain-powered workflow."
argument-hint: "<Linear issue URL, task description, or implementation request>"
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, WebFetch, Task, EnterPlanMode, ExitPlanMode, EnterWorktree, Skill, mcp__brain-search__brain_search, mcp__brain-search__brain_entities, mcp__github__create_pull_request, mcp__github__pull_request_read, mcp__github__update_pull_request, mcp__github__get_issue, mcp__linear__get_issue
---

# Implement — Autonomous Implementation Agent

Complete everything from task understanding to PR submission in a single turn.
User's role is limited to initial prompt input and final code review.

## Input

$ARGUMENTS

---

## Prerequisites

- Project CLAUDE.md is auto-loaded (contains build/test/lint commands and architecture rules)
- Execute in a worktree environment (call `EnterWorktree` at the start)

---

## Step 1: Task Understanding

1. Parse the input — identify if it's a Linear issue URL, GitHub issue URL, or plain text description
2. If URL: fetch task content using the appropriate tool (`mcp__linear__get_issue`, `mcp__github__get_issue`)
3. Identify task scope and modification targets
4. Resolve ambiguities autonomously using brain + codebase context
5. Do NOT ask the user. Record decisions with rationale in the PR body later.

---

## Step 2: Knowledge Loading

1. Run `brain_search` for project-related conventions and patterns relevant to this task
2. Read only the brain documents that are directly relevant (e.g., architecture guide, SRP conventions, state management patterns)
3. Load any project-specific brain knowledge (e.g., feature-layer-architecture, zustand-slice-structure)

Key brain queries to consider:
- Project architecture conventions
- Similar feature implementations
- Code style and patterns

---

## Step 3: Codebase Analysis

1. Understand the target directory structure
2. Review existing code patterns in the affected area
3. Find similar implementations as reference
4. Distinguish legacy vs current conventions based on knowledge loaded in Step 2
5. Identify all files that need modification

---

## Step 4: Implementation

1. Follow CLAUDE.md rules strictly
2. Follow project conventions loaded from brain
3. Maintain consistency with existing code style
4. Prefer modifying existing files over creating new ones

---

## Step 5: Verification

Run verification commands specified in CLAUDE.md in order. Fix errors directly before proceeding.

Typical verification sequence:
1. TypeCheck — `NODE_OPTIONS="--max-old-space-size=8192" yarn typecheck` (or workspace-scoped)
2. Lint — `yarn eslint`
3. Test — `yarn test` (or specific test files)

If any check fails: fix the issue, then re-run. Do NOT proceed with failures.

---

## Step 6: Commit & PR

1. `git add` only modified files explicitly — never use `git add -A` or `git add .`
2. Write commit message following repo conventions
3. Push and create a **draft PR**
4. PR body must include:
   - Summary of changes
   - Any autonomous decisions made, with rationale
   - Test plan

---

## Step 7: Self-Review

1. Run `/pr-review-toolkit:review-pr` on the created PR
2. Fix discovered issues, add follow-up commits
3. Run Pre-Submit Checklist — if any item fails, go back to the relevant step and fix

---

## Step 8: PR Update & Finalize

1. If any code changes were made in Step 7, update the PR title and body to accurately reflect the final state:
   - Summary must describe the actual shipped changes, not the pre-review version
   - Add a "Self-Review Changes" section noting what was fixed and why
   - Ensure autonomous decisions section is still accurate after modifications
2. Mark PR as ready (remove draft status)

---

## Rules

- **Do not ask the user.** Make all decisions autonomously and record rationale in the PR.
- **Fix errors, don't report them.** Only mention in PR body if auto-fix is truly impossible.
- **Minimize file creation.** Prefer modifying existing files.
- **Follow layer dependency rules.** Never violate the project's architecture constraints.

---

## Pre-Submit Checklist

Before marking PR as ready, every item must pass:

- [ ] Task requirements are fully addressed
- [ ] Project conventions are followed (architecture, naming, patterns)
- [ ] All verifications pass (typecheck, lint, test)
- [ ] Self-Review issues are all resolved
- [ ] PR body accurately reflects the final code (updated after any post-review fixes)
- [ ] No unnecessary files created
- [ ] Autonomous decisions are recorded with rationale in the PR body
