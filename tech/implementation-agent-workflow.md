---
title: "Implementation Agent Workflow"
tags: [workflow, agent, implementation, automation, claude-code, pr]
created: 2026-02-23
updated: 2026-02-23
summary: "Autonomous implementation agent workflow: from first prompt to PR submission in a single turn. 7-step process (task understanding, knowledge loading, codebase analysis, implementation, verification, commit & PR, self-review). User's role is limited to initial prompt and final code review."
related:
  - tech/brain-system-overview.md
confidence: high
---

# Implementation Agent Workflow

Autonomous implementation procedure completing everything from first prompt to PR submission in a single turn.
User's role is limited to initial prompt input and final code review.

## Prerequisites
- Project CLAUDE.md is auto-loaded
- Assumes execution in a worktree environment

## Step 1: Task Understanding
- Fetch task content from issue tracker (Linear, etc.)
- Identify task scope and modification targets
- Resolve ambiguities autonomously using brain + codebase context
- Do not ask the user. Record decisions with rationale in the PR.

## Step 2: Knowledge Loading
- Run `brain_search` for project-related conventions/patterns
- Read only the brain documents relevant to the current task

## Step 3: Codebase Analysis
- Understand the target directory structure
- Review existing code patterns
- Use similar implementations as reference (distinguish legacy vs current conventions based on knowledge loaded in Step 2)

## Step 4: Implementation
- Follow CLAUDE.md rules
- Follow project conventions loaded from brain
- Maintain consistency with existing code style

## Step 5: Verification
Run verification commands specified in CLAUDE.md in order. Fix errors directly before proceeding to the next step.

## Step 6: Commit & PR
1. `git add` only modified files explicitly
2. Write commit message following repo conventions
3. Push and create a draft PR. Follow the repo's PR template or existing PR conventions.
4. Record any autonomous decisions with rationale in the PR body.

## Step 7: Self-Review
1. Run `/pr-review-toolkit:review-pr` on the PR
2. Fix discovered issues, add follow-up commits
3. Run Pre-Submit Checklist — if any item fails, go back to the relevant step and fix
4. Mark PR as ready (remove draft)

## Rules
- Do not ask the user. Make all decisions autonomously and record rationale in the PR.
- Fix errors, don't just report them. Only mention in PR body if auto-fix is impossible.
- Minimize file creation. Prefer modifying existing files.

## Pre-Submit Checklist

- [ ] Task requirements are fully addressed
- [ ] Project conventions are followed
- [ ] All verifications pass
- [ ] Self-Review issues are all resolved
- [ ] No unnecessary files created
- [ ] Autonomous decisions are recorded with rationale in the PR body
